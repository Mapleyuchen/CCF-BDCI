"""Paired memory A/B experiment using a real openjiuwen DeepAgent and JiuwenSwarm Rails.

``--self-test`` replaces only the LLM with a deterministic stub. Its scores
verify the execution path and must never be reported as model performance.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import logging
import os
import random
from pathlib import Path
import re
import shutil
import statistics
import time
from typing import Any
from uuid import uuid4

# The experiment must not read or write the user's normal JiuwenSwarm workspace.
# Set this before JiuwenSwarm imports initialize their logging and memory paths.
os.environ.setdefault(
    "JIUWENSWARM_DATA_DIR",
    str(Path(__file__).resolve().parent / "results" / ".runtime"),
)

import yaml

from openjiuwen.core.foundation.llm import (
    AssistantMessage,
    Model,
    ModelClientConfig,
    ModelRequestConfig,
    UsageMetadata,
)
from openjiuwen.core.single_agent import AgentCard
from openjiuwen.harness import create_deep_agent

from jiuwenswarm.agents.harness.common.memory.experiment_config import (
    code_memory_experiment_group,
)
from jiuwenswarm.agents.harness.common.rails import EnhancedMemoryRail, ProjectMemoryRail
from jiuwenswarm.agents.harness.common.rails.project_memory import files as memory_files
from jiuwenswarm.common.config import get_default_models, resolve_env_vars
from jiuwenswarm.common.reasoning_config import resolve_endpoint_profile_override
from jiuwenswarm.common.reasoning_injector import build_reasoning_model_request_kwargs
from memory_rail_benchmark import (
    FACT_ID_RE,
    SectionCollector,
    build_baseline_with_budget,
    seed_baseline,
)


PROMPT = (
    "Answer the user's question using the available project facts. "
    "If the answer is unavailable, say UNKNOWN. Do not call tools."
)
MEMORY_SOURCES = (
    "USER_MEMORY_FILES", "USER_MEMORY_GLOBS",
    "MANAGED_MEMORY_FILES", "MANAGED_MEMORY_GLOBS",
)


@contextmanager
def experiment_workspace(parent: Path, prefix: str):
    """Create a disposable workspace without tempfile's restrictive Windows ACL."""
    path = parent / f"{prefix}{uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)


def load_qa_dataset(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    facts, questions = data.get("facts"), data.get("questions")
    if not isinstance(facts, list) or not facts or not isinstance(questions, list) or not questions:
        raise ValueError("Dataset requires nonempty facts and questions")
    fact_ids = set()
    for fact in facts:
        fact_id, content = fact.get("id"), fact.get("text")
        if (not isinstance(fact_id, str) or not FACT_ID_RE.fullmatch(f"<FACT:{fact_id}>")
                or not isinstance(content, str) or not content.strip() or fact_id in fact_ids):
            raise ValueError(f"Invalid or duplicate fact: {fact!r}")
        fact_ids.add(fact_id)
    if len(facts) > 20:
        raise ValueError("EnhancedMemoryRail currently stores only 20 L1 facts per episode")
    question_ids = set()
    for question in questions:
        qid, query = question.get("id"), question.get("query")
        answers, relevant = question.get("answers"), question.get("relevant_ids")
        if (not isinstance(qid, str) or qid in question_ids
                or not isinstance(query, str) or not query.strip()
                or not isinstance(answers, list) or not answers
                or any(not isinstance(a, str) or not a.strip() for a in answers)
                or not isinstance(relevant, list) or not relevant
                or not set(relevant) <= fact_ids):
            raise ValueError(f"Invalid question: {qid!r}")
        question_ids.add(qid)
    return data


def answer_is_correct(response: str, answers: list[str]) -> bool:
    return any(
        re.search(r"(?<!\w)" + re.escape(answer) + r"(?!\w)", response, re.I)
        for answer in answers
    )


def complete_fact_ids(context: str, facts: list[dict[str, str]]) -> set[str]:
    """Count evidence only when the entire fact survives context truncation."""
    return {
        fact["id"] for fact in facts
        if f"<FACT:{fact['id']}> {fact['text']}" in context
    }


def model_entry(config: dict[str, Any]) -> dict[str, Any]:
    entries = get_default_models(config)
    entry = next((item for item in entries if item.get("is_default")), entries[0])
    mcc = entry.get("model_client_config") or {}
    if not mcc.get("model_name") or not mcc.get("api_base"):
        raise ValueError("Configure a default model_name and api_base before a live run")
    if not mcc.get("api_key") and str(mcc.get("auth_mode") or "").lower() not in (
        "none", "custom_headers", "openai_account_oauth"
    ):
        raise ValueError("Default model has no API credential")
    return entry


def make_model(entry: dict[str, Any], *, self_test: bool) -> Model:
    if self_test:
        return Model(
            ModelClientConfig(
                client_provider="OpenAI", api_key="self-test",
                api_base="http://self-test.invalid/v1",
            ),
            ModelRequestConfig(model_name="deterministic-self-test"),
        )
    mcc = dict(entry["model_client_config"])
    model_name = mcc.pop("model_name")
    mcc.setdefault("client_provider", "OpenAI")
    if not mcc.get("endpoint_profile"):
        profile = resolve_endpoint_profile_override(mcc.get("api_base"))
        if profile:
            mcc["endpoint_profile"] = profile
    request = build_reasoning_model_request_kwargs(
        model_client_config=mcc,
        model_config_obj=entry.get("model_config_obj") or {},
        model_name=model_name,
    )
    return Model(
        model_client_config=ModelClientConfig(**mcc),
        model_config=ModelRequestConfig(**request),
    )


def _message_field(message: Any, field: str) -> Any:
    return message.get(field) if isinstance(message, dict) else getattr(message, field, None)


class ModelProbe:
    """Capture the exact memory section and usage at each model request."""

    def __init__(self, model: Model, rail: Any, *, self_test: bool):
        self.rail = rail
        self.agent = None
        self.calls: list[dict[str, Any]] = []
        self.expected: dict[str, Any] | None = None
        original_invoke = model.invoke

        async def invoke(messages: Any, *args: Any, **kwargs: Any) -> AssistantMessage:
            section = None
            if self.agent is not None and self.agent.system_prompt_builder is not None:
                section_name = (
                    "project_memory" if isinstance(rail, ProjectMemoryRail)
                    else EnhancedMemoryRail.SECTION_NAME
                )
                section = self.agent.system_prompt_builder.get_section(section_name)
            memory_context = section.render("en") if section else ""
            user_messages = [
                str(_message_field(m, "content") or "")
                for m in messages if _message_field(m, "role") == "user"
            ]
            system_messages = [
                str(_message_field(m, "content") or "")
                for m in messages if _message_field(m, "role") == "system"
            ]
            call = {
                "memory_context": memory_context,
                "memory_in_model_prompt": not memory_context or any(
                    memory_context in content for content in system_messages
                ),
                "user_messages": user_messages,
            }
            if self_test:
                answer = "ACK"
                if self.expected is not None:
                    expected_ids = self.expected["relevant_ids"]
                    answer = (
                        self.expected["answers"][0]
                        if set(expected_ids) <= set(FACT_ID_RE.findall(memory_context))
                        else "UNKNOWN"
                    )
                response = AssistantMessage(
                    content=answer,
                    usage_metadata=UsageMetadata(
                        model_name="deterministic-self-test",
                        input_tokens=20, output_tokens=3, total_tokens=23,
                    ),
                )
            else:
                response = await original_invoke(messages, *args, **kwargs)
            usage = getattr(response, "usage_metadata", None)
            call["usage"] = (
                {"input_tokens": usage.input_tokens,
                 "output_tokens": usage.output_tokens,
                 "total_tokens": usage.total_tokens}
                if usage is not None else None
            )
            self.calls.append(call)
            return response

        model.invoke = invoke


@contextmanager
def isolated_project_memory_sources():
    """Keep user and managed files outside the paired experiment."""
    saved = {name: getattr(memory_files, name) for name in MEMORY_SOURCES}
    try:
        for name in MEMORY_SOURCES:
            setattr(memory_files, name, ())
        memory_files.clear_project_memory_cache()
        yield
    finally:
        for name, value in saved.items():
            setattr(memory_files, name, value)
        memory_files.clear_project_memory_cache()


async def build_agent(
    group: str, workspace: Path, facts: list[dict[str, str]],
    entry: dict[str, Any], *, context_chars: int, top_k: int, self_test: bool,
):
    if group == "baseline":
        seed_baseline(workspace, facts)
        rail = await build_baseline_with_budget(
            workspace, SectionCollector(), context_chars
        )
    else:
        rail = EnhancedMemoryRail(
            workspace=str(workspace), max_context_items=top_k,
            max_context_chars=context_chars,
        )
    model = make_model(entry, self_test=self_test)
    probe = ModelProbe(model, rail, self_test=self_test)
    agent = create_deep_agent(
        model,
        card=AgentCard(name=f"memory-ab-{group}-{uuid4().hex[:10]}"),
        system_prompt=PROMPT,
        rails=[rail], tools=[], subagents=[], workspace=str(workspace),
        enable_task_loop=False, max_iterations=1, language="en",
        enable_security_rail=False,
        enable_model_anomaly_detection_rail=False,
        enable_read_image_multimodal=False,
    )
    probe.agent = agent
    await agent.ensure_initialized()
    if not agent.is_registered_rail(rail):
        raise RuntimeError(f"{type(rail).__name__} was not registered")
    probe.calls.clear()
    return agent, rail, probe


async def seed_enhanced_agent(agent: Any, rail: EnhancedMemoryRail,
                              facts: list[dict[str, str]], run_id: str) -> float:
    start = time.perf_counter()
    for fact in facts:
        prompt = (
            f"Remember this project fact: <FACT:{fact['id']}> {fact['text']} "
            "Reply ACK."
        )
        result = await agent.invoke({
            "query": prompt,
            "conversation_id": f"{run_id}-seed-{fact['id']}",
        })
        if result.get("result_type") != "answer":
            raise RuntimeError(f"Seeding {fact['id']} did not complete: {result!r}")
    contents = [item.content for item in rail._memory.get_all_memories()]
    missing = [f["id"] for f in facts if not any(f"<FACT:{f['id']}>" in c for c in contents)]
    if missing:
        raise RuntimeError(f"Enhanced Rail failed to retain seeded facts: {missing}")
    return (time.perf_counter() - start) * 1000


def _sum_usage(calls: list[dict[str, Any]], field: str) -> int | None:
    if not calls or any(call["usage"] is None for call in calls):
        return None
    return sum(call["usage"][field] for call in calls)


async def run_group(
    config: dict[str, Any], repeat: int, questions: list[dict[str, Any]],
    facts: list[dict[str, str]], workspace: Path, entry: dict[str, Any],
    *, context_chars: int, top_k: int, self_test: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    group = code_memory_experiment_group(config)
    run_id = f"memory-ab-{uuid4().hex}"
    rows: list[dict[str, Any]] = []
    run_info: dict[str, Any] = {"group": group, "repeat": repeat}
    agent = rail = probe = None
    try:
        agent, rail, probe = await build_agent(
            group, workspace, facts, entry,
            context_chars=context_chars, top_k=top_k, self_test=self_test,
        )
        seed_latency_ms = (
            await seed_enhanced_agent(agent, rail, facts, run_id)
            if group == "enhanced" else 0.0
        )
        run_info.update({
            "seed_latency_ms": seed_latency_ms,
            "seed_model_calls": len(probe.calls),
            "seed_input_tokens": _sum_usage(probe.calls, "input_tokens") if group == "enhanced" else 0,
            "seed_output_tokens": _sum_usage(probe.calls, "output_tokens") if group == "enhanced" else 0,
            "seed_total_tokens": _sum_usage(probe.calls, "total_tokens") if group == "enhanced" else 0,
        })
        seed_snapshot = deepcopy(rail._memory) if group == "enhanced" else None
        for question in questions:
            if seed_snapshot is not None:
                rail._memory = deepcopy(seed_snapshot)
            probe.calls.clear()
            probe.expected = question
            start = time.perf_counter()
            row = {
                "group": group, "repeat": repeat, "question_id": question["id"],
                "query": question["query"], "relevant_ids": question["relevant_ids"],
                "answers": question["answers"], "seed_latency_ms": seed_latency_ms,
                "conversation_id": f"{run_id}-probe-{question['id']}",
                "rail_type": type(rail).__name__,
            }
            try:
                result = await agent.invoke({
                    "query": question["query"],
                    "conversation_id": row["conversation_id"],
                })
                row["latency_ms"] = (time.perf_counter() - start) * 1000
                calls = list(probe.calls)
                memory_context = calls[0]["memory_context"] if calls else ""
                seen = set(FACT_ID_RE.findall(memory_context))
                complete = complete_fact_ids(memory_context, facts)
                answer = result.get("output", "")
                if not isinstance(answer, str):
                    answer = str(answer)
                isolated = bool(calls) and all(
                    call["user_messages"] == [question["query"]] for call in calls
                )
                row.update({
                    "answer": answer,
                    "result_type": result.get("result_type"),
                    "memory_context": memory_context,
                    "memory_chars": len(memory_context),
                    "observed_ids": sorted(seen),
                    "complete_fact_ids": sorted(complete),
                    "evidence_recall": len(complete & set(question["relevant_ids"]))
                    / len(question["relevant_ids"]),
                    "history_isolated": isolated,
                    "memory_in_model_prompt": all(
                        call["memory_in_model_prompt"] for call in calls
                    ),
                    "model_calls": len(calls),
                    "input_tokens": _sum_usage(calls, "input_tokens"),
                    "output_tokens": _sum_usage(calls, "output_tokens"),
                    "total_tokens": _sum_usage(calls, "total_tokens"),
                    "correct": answer_is_correct(answer, question["answers"]),
                    "status": "ok" if isolated and all(
                        call["memory_in_model_prompt"] for call in calls
                    ) and result.get("result_type") == "answer"
                    and len(memory_context) <= context_chars else "invalid",
                })
                if row["status"] == "invalid":
                    row["error"] = "Missing model call, history leak, missing prompt injection, incomplete answer, or context budget exceeded"
            except Exception as exc:  # keep every paired task visible
                row.update({
                    "status": "error", "error": f"{type(exc).__name__}: {exc}",
                    "latency_ms": (time.perf_counter() - start) * 1000,
                })
            rows.append(row)
    except Exception as exc:
        run_info["error"] = f"{type(exc).__name__}: {exc}"
        for question in questions:
            rows.append({
                "group": group, "repeat": repeat, "question_id": question["id"],
                "query": question["query"], "status": "error",
                "error": f"Setup/seeding failed: {type(exc).__name__}: {exc}",
            })
    finally:
        if agent is not None:
            await agent._agent_callback_manager.clear()
            if agent._react_agent is not None:
                await agent._react_agent.agent_callback_manager.clear()
    return rows, run_info


def summarize(rows: list[dict[str, Any]], runs: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for group in ("baseline", "enhanced"):
        valid = [r for r in rows if r["group"] == group and r["status"] == "ok"]
        summary[group] = {
            "valid": len(valid),
            "failed": sum(r["group"] == group and r["status"] != "ok" for r in rows),
            "accuracy": statistics.mean(r["correct"] for r in valid) if valid else None,
            "mean_evidence_recall": statistics.mean(r["evidence_recall"] for r in valid) if valid else None,
            "mean_memory_chars": statistics.mean(r["memory_chars"] for r in valid) if valid else None,
            "mean_input_tokens": statistics.mean(r["input_tokens"] for r in valid if r["input_tokens"] is not None)
            if any(r["input_tokens"] is not None for r in valid) else None,
            "mean_output_tokens": statistics.mean(r["output_tokens"] for r in valid if r["output_tokens"] is not None)
            if any(r["output_tokens"] is not None for r in valid) else None,
            "mean_total_tokens": statistics.mean(r["total_tokens"] for r in valid if r["total_tokens"] is not None)
            if any(r["total_tokens"] is not None for r in valid) else None,
            "mean_latency_ms": statistics.mean(r["latency_ms"] for r in valid) if valid else None,
        }
    paired: dict[tuple[int, str], dict[str, dict[str, Any]]] = {}
    for row in rows:
        if row["status"] == "ok":
            paired.setdefault((row["repeat"], row["question_id"]), {})[row["group"]] = row
    complete = [pair for pair in paired.values() if set(pair) == {"baseline", "enhanced"}]
    summary["paired"] = {
        "n": len(complete),
        "unique_questions": len({
            question_id for repeat, question_id in paired
            if set(paired[(repeat, question_id)]) == {"baseline", "enhanced"}
        }),
        "repeats": len({repeat for repeat, question_id in paired
                        if set(paired[(repeat, question_id)]) == {"baseline", "enhanced"}}),
        "accuracy_gain": statistics.mean(
            int(pair["enhanced"]["correct"]) - int(pair["baseline"]["correct"])
            for pair in complete
        ) if complete else None,
        "evidence_recall_gain": statistics.mean(
            pair["enhanced"]["evidence_recall"] - pair["baseline"]["evidence_recall"]
            for pair in complete
        ) if complete else None,
    }
    summary["by_repeat"] = []
    for repeat in sorted({row["repeat"] for row in rows}):
        per_repeat = [pair for (index, _), pair in paired.items()
                      if index == repeat and set(pair) == {"baseline", "enhanced"}]
        summary["by_repeat"].append({
            "repeat": repeat,
            "paired_questions": len(per_repeat),
            "baseline_accuracy": statistics.mean(int(pair["baseline"]["correct"])
                                                 for pair in per_repeat) if per_repeat else None,
            "enhanced_accuracy": statistics.mean(int(pair["enhanced"]["correct"])
                                                 for pair in per_repeat) if per_repeat else None,
        })
    summary["resource_totals"] = {}
    for group in ("baseline", "enhanced"):
        valid_rows = [row for row in rows if row["group"] == group and row["status"] == "ok"]
        group_runs = [run for run in runs if run["group"] == group]
        query_values = [row.get("total_tokens") for row in valid_rows]
        seed_values = [run.get("seed_total_tokens") for run in group_runs]
        query_total = sum(query_values) if query_values and all(v is not None for v in query_values) else None
        seed_total = sum(seed_values) if seed_values and all(v is not None for v in seed_values) else None
        all_total = query_total + seed_total if query_total is not None and seed_total is not None else None
        summary["resource_totals"][group] = {
            "query_tokens": query_total,
            "seed_tokens": seed_total,
            "all_tokens": all_total,
            "tokens_per_valid_question_including_seed": all_total / len(valid_rows)
            if all_total is not None and valid_rows else None,
            "seed_model_calls": sum(run.get("seed_model_calls", 0) for run in group_runs),
        }
    return summary


async def run_experiment(args: argparse.Namespace) -> dict[str, Any]:
    dataset = load_qa_dataset(args.dataset)
    questions = dataset["questions"][:args.max_cases] if args.max_cases else dataset["questions"]
    if args.self_test:
        config: dict[str, Any] = {}
        entry: dict[str, Any] = {}
    else:
        if not args.config.is_file():
            raise FileNotFoundError(f"Model config not found: {args.config}")
        config = resolve_env_vars(yaml.safe_load(args.config.read_text(encoding="utf-8")) or {})
        memory_config = ((config.get("modes") or {}).get("code") or {}).get("memory") or {}
        if memory_config.get("enabled") is False:
            raise ValueError("modes.code.memory.enabled must be true for this experiment")
        entry = model_entry(config)
    rows: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    with isolated_project_memory_sources():
        with experiment_workspace(args.output.parent, "agent-memory-ab-") as temp:
            for repeat in range(args.repeats):
                ordered_facts = list(dataset["facts"])
                if args.fact_order_seed is not None:
                    random.Random(args.fact_order_seed + repeat).shuffle(ordered_facts)
                order = ("baseline", "enhanced") if repeat % 2 == 0 else (
                    "enhanced", "baseline"
                )
                for group in order:
                    group_config = deepcopy(config)
                    group_config.setdefault("modes", {}).setdefault("code", {}).setdefault(
                        "memory", {}
                    )["experiment_group"] = group
                    assert code_memory_experiment_group(group_config) == group
                    workspace = Path(temp) / f"{group}-{repeat}"
                    workspace.mkdir()
                    group_rows, run_info = await run_group(
                        group_config, repeat, questions, ordered_facts, workspace, entry,
                        context_chars=args.context_chars, top_k=args.top_k,
                        self_test=args.self_test,
                    )
                    run_info["fact_order"] = [fact["id"] for fact in ordered_facts]
                    rows.extend(group_rows)
                    runs.append(run_info)
    return {
        "kind": "deterministic_self_test" if args.self_test else "live_model_experiment",
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "dataset_path": str(args.dataset.resolve()),
        "settings": {
            "model_name": "deterministic-self-test" if args.self_test else entry["model_client_config"]["model_name"],
            "model_provider": "OpenAI" if args.self_test else entry["model_client_config"].get("client_provider", "OpenAI"),
            "model_request": {
                key: (entry.get("model_config_obj") or {}).get(key)
                for key in ("temperature", "top_p", "max_tokens")
            } if not args.self_test else {},
            "context_chars": args.context_chars, "top_k": args.top_k,
            "repeats": args.repeats, "questions": len(questions),
            "fact_order_seed": args.fact_order_seed,
            "max_iterations": 1, "tools": [],
        },
        "summary": summarize(rows, runs),
        "runs": runs,
        "records": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).parent
    parser.add_argument("--dataset", type=Path, default=base / "data" / "memory_agent_qa_v2.json")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=Path.home() / ".jiuwenswarm" / "config" / "config.yaml")
    parser.add_argument("--env-file", type=Path, default=None,
                        help="Load a local .env file before resolving config variables")
    parser.add_argument("--context-chars", type=int, default=600)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-cases", type=int, default=0, help="Use 5 for the pilot; 0 runs all 20")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--fact-order-seed", type=int, default=None,
                        help="Shuffle the same facts for both arms, varying order by repeat")
    parser.add_argument("--self-test", action="store_true", help="No network: fake model validates the Agent path")
    args = parser.parse_args()
    if min(args.context_chars, args.top_k, args.repeats) <= 0 or args.max_cases < 0:
        parser.error("context-chars, top-k and repeats must be positive; max-cases must be nonnegative")
    if args.output is None:
        filename = "agent_memory_ab_self_test.json" if args.self_test else "agent_memory_ab_live.json"
        args.output = base / "results" / filename
    if args.env_file is not None:
        if not args.env_file.is_file():
            parser.error(f"Environment file not found: {args.env_file}")
        from dotenv import load_dotenv
        load_dotenv(args.env_file, override=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    logging.disable(logging.INFO)
    try:
        report = asyncio.run(run_experiment(args))
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Raw records: {args.output}")
    if args.self_test:
        print("SELF-TEST ONLY: fake LLM results are not research evidence")
    if report["summary"]["paired"]["n"] == 0:
        raise SystemExit("No valid paired trials; inspect the errors in the result file")


if __name__ == "__main__":
    main()
