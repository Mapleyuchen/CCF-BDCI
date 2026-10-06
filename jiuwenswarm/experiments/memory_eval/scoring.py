"""Pinned LongMemEval prompts and arm-blind, separately accounted model judging."""

from __future__ import annotations

import ast
import asyncio
import hashlib
import json
from pathlib import Path
import re
import time
from uuid import uuid4

from .data import HERE, read_json
from .runtime import Journal
from jiuwenswarm.agents.harness.common.memory.controlled_retrieval import canonical_hash


def benchmark_prompt_function(dependencies: dict):
    path = HERE / "data/public/longmemeval_protocol/evaluate_qa.py"
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != dependencies["scorer_sha256"]:
        raise ValueError("The benchmark scorer changed")
    tree = ast.parse(source.decode("utf-8"))
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef)
                and item.name == "get_anscheck_prompt")
    namespace = {}
    # Load just the checked prompt function, without executing the reference
    # CLI, its provider setup, imports, or its permissive substring parser.
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["get_anscheck_prompt"]


def judgment_key(row: dict, model: str, scorer_sha: str) -> str:
    return canonical_hash({
        "question_id": row["question_id"], "question": row["query"],
        "gold_answer": row["gold_answer"], "question_type": row["question_type"],
        "abstention": row["abstention"], "answer": row["answer"],
        "judge_model": model, "scorer_sha256": scorer_sha, "parser_version": "strict-yes-no-v1",
    })


def restore_adjudications(rows, previous_rows):
    """Repeated scoring must preserve review work for the identical response."""
    previous = {r["judge_key"]: r for r in previous_rows}
    for row in rows:
        old = previous.get(row["judge_key"])
        if old is None:
            continue
        if any(old.get(k) != row.get(k) for k in ("question_id", "query", "gold_answer", "response")):
            raise ValueError("Existing human adjudication refers to a changed question or response")
        for field in ("decision", "reviewer", "notes"):
            row[field] = old.get(field)
        if row["decision"] is not None and type(row["decision"]) is not bool:
            raise ValueError("Human decision must be a JSON boolean or null")
    return rows


async def evaluate(run_root: Path, config_path: Path, env_file: Path | None, *, concurrency: int = 8,
                   audit_model: str | None = None, judge_model: str | None = None):
    from dotenv import load_dotenv
    from openai import AsyncOpenAI
    import yaml
    from agent_memory_ab import model_entry
    from jiuwenswarm.common.config import resolve_env_vars

    manifest = read_json(run_root / "run_manifest.json")
    if manifest["kind"] != "memory_eval_v2_live":
        raise ValueError("Only live model results may be semantically judged")
    protocol = manifest["protocol"]
    deps = protocol["dependencies"]
    prompt_function = benchmark_prompt_function(deps)
    if env_file:
        load_dotenv(env_file, override=True)
    entry = model_entry(resolve_env_vars(yaml.safe_load(config_path.read_text(encoding="utf-8"))))
    mcc = entry["model_client_config"]
    client = AsyncOpenAI(api_key=mcc["api_key"], base_url=mcc["api_base"], max_retries=0, timeout=90)
    journal = Journal(run_root)
    score_dir = run_root / "scoring"
    score_dir.mkdir(exist_ok=True)
    previous = journal.latest("labels", "judge_key")
    solver_trials = list(journal.trials.values())
    unique = {}
    model = judge_model or protocol["judge_model"]
    for row in solver_trials:
        if row["status"] == "ok":
            key = judgment_key(row, model, deps["scorer_sha256"])
            unique.setdefault(key, row)
    semaphore = asyncio.Semaphore(concurrency)
    from .runtime import SmoothCallGate
    gates = {}
    completed = 0

    async def grade(key, row, judge_model):
        nonlocal completed
        if key in previous:
            return previous[key]
        async with semaphore:
            qtype = row["question_type"]
            if qtype == "synthetic-factual":
                qtype = "single-session-user"
            prompt = prompt_function(qtype, row["query"], row["gold_answer"], row["answer"],
                                     abstention=row["abstention"])
            prompt_artifact = journal.artifact("judge_prompts", [{"role": "user", "content": prompt}])
            for attempt in range(3):
                gate = gates.setdefault(judge_model, SmoothCallGate(.65 if judge_model == protocol["solver_model"] else .15))
                await gate.wait()
                started = time.perf_counter()
                call = {"call_id": uuid4().hex, "judge_key": key, "model_requested": judge_model,
                        "attempt": attempt, "prompt": prompt_artifact, "phase": "evaluation"}
                try:
                    response = await client.chat.completions.create(
                        model=judge_model, messages=[{"role": "user", "content": prompt}],
                        temperature=0, max_tokens=10,
                    )
                    raw = response.choices[0].message.content.strip()
                    usage = response.usage
                    call.update(status="ok", output=raw, model_returned=response.model,
                                usage=({"input_tokens": usage.prompt_tokens, "output_tokens": usage.completion_tokens,
                                        "total_tokens": usage.total_tokens} if usage else None))
                    parsed = re.fullmatch(r"(yes|no)[.!]?", raw.casefold())
                    if not parsed:
                        raise ValueError("Judge did not return a strict yes/no label")
                    label = {
                        "judge_key": key, "question_id": row["question_id"],
                        "response_sha256": hashlib.sha256(row["answer"].encode()).hexdigest(),
                        "judge_model": judge_model, "scorer_sha256": deps["scorer_sha256"],
                        "label": parsed.group(1) == "yes", "raw_label": raw,
                        "prompt": prompt_artifact, "status": "ok",
                    }
                    journal.append("labels", label)
                    previous[key] = label
                    completed += 1
                    if completed % 50 == 0:
                        print(f"Judge: {completed} new unique answers", flush=True)
                    return label
                except Exception as exc:
                    if getattr(exc, "status_code", None) == 429:
                        gate.next_start = max(gate.next_start, time.perf_counter() + 60)
                    if "status" not in call:
                        known_codes = {"access_denied", "AllocationQuota.FreeTierOnly",
                                       "rate_limit_exceeded", "insufficient_quota", "ModelNotFound"}
                        code = getattr(exc, "code", None)
                        call.update(status="error", error_type=type(exc).__name__, usage=None,
                                    error_code=code if code in known_codes else "provider_error")
                    else:
                        call["parse_error"] = True
                    if attempt == 2:
                        raise RuntimeError(f"Judging failed after 3 recorded attempts: {type(exc).__name__}") from None
                    await asyncio.sleep(2 ** attempt)
                finally:
                    call["latency_ms"] = (time.perf_counter() - started) * 1000
                    journal.append("judge_calls", call)

    try:
        await asyncio.gather(*(grade(key, row, model) for key, row in sorted(unique.items())))
        audit_rows = []
        for key, row in sorted(unique.items()):
            label = previous[key]
            disagreement = label["label"] != row["literal_correct"]
            random_audit = int(key[:8], 16) % 10 == 0
            if disagreement or random_audit:
                audit_rows.append({
                    "judge_key": key, "question_id": row["question_id"], "query": row["query"],
                    "gold_answer": row["gold_answer"], "response": row["answer"],
                    "question_type": row["question_type"], "abstention": row["abstention"],
                    "benchmark_grading_prompt": label["prompt"],
                    "primary_label": label["label"], "literal_label": row["literal_correct"],
                    "reason": "string-judge disagreement" if disagreement else "fixed-hash 10% sample",
                    "decision": None, "reviewer": None, "notes": None,
                })
        if audit_model:
            audit_results = await asyncio.gather(*(
                grade(judgment_key(unique[row["judge_key"]], audit_model, deps["scorer_sha256"]),
                      unique[row["judge_key"]], audit_model) for row in audit_rows))
            for row, audit_label in zip(audit_rows, audit_results):
                row["secondary_label"] = audit_label["label"]
                row["judges_agree"] = row["primary_label"] == audit_label["label"]
        audit_path = score_dir / "blinded_adjudication_queue.json"
        audit_rows = restore_adjudications(audit_rows, read_json(audit_path) if audit_path.is_file() else [])
        temporary = audit_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(audit_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(audit_path)
        report = {
            "primary_judge_model": model, "secondary_judge_model": audit_model,
            "scorer_url": deps["scorer_url"], "scorer_sha256": deps["scorer_sha256"],
            "unique_answers": len(unique), "valid_solver_trials": len([r for r in solver_trials if r["status"] == "ok"]),
            "audit_questions": len(audit_rows),
            "judge_disagreements": sum(row.get("judges_agree") is False for row in audit_rows),
            "human_adjudications_completed": sum(type(row.get("decision")) is bool and bool(row.get("reviewer")) for row in audit_rows),
            "human_review_required": True,
            "official_longmemeval_score": False,
            "note": "Original task-specific LongMemEval prompts; substituted Qwen judge and strict yes/no parser. Cache identical question-answer judgments, not repeated solver generations.",
        }
        (score_dir / "scoring_manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Scored {len(unique)} unique responses; blinded audit queue: {audit_path}")
    finally:
        await client.close()
        journal.close()
