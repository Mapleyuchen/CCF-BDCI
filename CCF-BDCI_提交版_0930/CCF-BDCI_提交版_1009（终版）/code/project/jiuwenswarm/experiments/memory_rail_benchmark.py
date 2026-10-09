"""Reproducible context-retrieval benchmark using JiuwenSwarm implementations.

The baseline executes ProjectMemoryRail.before_model_call. The enhanced arm
uses JiuwenSwarm's MultiLevelMemory and HybridRetrievalEngine. This measures
whether evidence reaches the model context, not the quality of an LLM answer.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import re
import statistics
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

from jiuwenswarm.agents.harness.common.memory.multi_level_memory import MultiLevelMemory
from jiuwenswarm.agents.harness.common.memory.retrieval_engine import HybridRetrievalEngine
from jiuwenswarm.agents.harness.common.rails.project_memory_rail import ProjectMemoryRail
from jiuwenswarm.agents.harness.common.rails.project_memory import files as memory_files


FACT_ID_RE = re.compile(r"<FACT:([A-Za-z0-9_-]+)>")
EXTERNAL_MEMORY_SOURCES = (
    "USER_MEMORY_FILES",
    "USER_MEMORY_GLOBS",
    "MANAGED_MEMORY_FILES",
    "MANAGED_MEMORY_GLOBS",
)


class SectionCollector:
    """The prompt-builder methods exercised by ProjectMemoryRail."""

    def __init__(self) -> None:
        self.sections = {}

    def add_section(self, section):
        self.sections[section.name] = section
        return self

    def remove_section(self, name):
        self.sections.pop(name, None)
        return self

    def render(self) -> str:
        section = self.sections.get("project_memory")
        return section.render("en") if section is not None else ""


def load_dataset(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    facts = data.get("facts")
    questions = data.get("questions")
    if not isinstance(facts, list) or not facts or not isinstance(questions, list) or not questions:
        raise ValueError("Dataset needs nonempty 'facts' and 'questions' lists")
    ids = [fact.get("id") for fact in facts]
    if any(not isinstance(identifier, str) or not FACT_ID_RE.fullmatch(f"<FACT:{identifier}>") for identifier in ids):
        raise ValueError("Every fact needs a simple string id")
    if len(set(ids)) != len(ids):
        raise ValueError("Fact IDs must be unique")
    for fact in facts:
        if not isinstance(fact.get("text"), str) or not fact["text"].strip():
            raise ValueError("Every fact needs nonempty text")
    for question in questions:
        expected = question.get("relevant_ids")
        if not isinstance(question.get("id"), str) or not isinstance(question.get("query"), str):
            raise ValueError("Every question needs id and query strings")
        if not isinstance(expected, list) or not expected or not set(expected) <= set(ids):
            raise ValueError(f"Invalid relevant_ids for question {question.get('id')}")
    return data


def seed_baseline(workspace: Path, facts: list[dict]) -> None:
    # ProjectMemoryRail discovers this exact file in the isolated workspace.
    (workspace / "pyproject.toml").write_text("[project]\nname = 'memory-benchmark'\n", encoding="utf-8")
    contents = "# Benchmark facts\n\n" + "\n".join(
        f"<FACT:{fact['id']}> {fact['text']}" for fact in facts
    ) + "\n"
    (workspace / "JIUWENSWARM.md").write_text(contents, encoding="utf-8")


def seed_enhanced(facts: list[dict]) -> tuple[MultiLevelMemory, HybridRetrievalEngine]:
    memory = MultiLevelMemory()
    for fact in facts:
        memory.store(
            content=f"<FACT:{fact['id']}> {fact['text']}",
            layer="project",
            key=fact["id"],
        )
    return memory, HybridRetrievalEngine()


def enhanced_context(
    memory: MultiLevelMemory,
    engine: HybridRetrievalEngine,
    query: str,
    budget: int,
    top_k: int,
) -> str:
    ranked = engine.retrieve(query, memory.get_all_memories(), top_k=top_k)
    selected = []
    length = 0
    for item, _score in ranked:
        line = item.content + "\n"
        if length + len(line) > budget:
            continue
        selected.append(line)
        length += len(line)
    return "".join(selected)


def record(system: str, repeat: int, question: dict, context: str, latency_ms: float) -> dict:
    expected = set(question["relevant_ids"])
    observed = set(FACT_ID_RE.findall(context))
    hits = expected & observed
    return {
        "system": system,
        "repeat": repeat,
        "question_id": question["id"],
        "query": question["query"],
        "relevant_ids": sorted(expected),
        "observed_ids": sorted(observed),
        "hits": sorted(hits),
        "recall": len(hits) / len(expected),
        "context_chars": len(context),
        "latency_ms": latency_ms,
        "context": context,
    }


async def build_baseline_with_budget(workspace: Path, builder: SectionCollector, budget: int) -> ProjectMemoryRail:
    """Calibrate the Rail's body cap so its rendered section fits the full cap."""
    body_cap = budget
    for _ in range(5):
        rail = ProjectMemoryRail(workspace=str(workspace), language="en", max_chars=body_cap)
        rail.init(SimpleNamespace(system_prompt_builder=builder))
        await rail.before_model_call(SimpleNamespace(inputs=SimpleNamespace()))
        excess = len(builder.render()) - budget
        if excess <= 0:
            return rail
        body_cap = max(1, body_cap - excess)
    raise ValueError("context-chars is too small for the ProjectMemoryRail section header")


async def run(dataset: dict, budget: int, top_k: int, repeats: int, temp_parent: Path) -> list[dict]:
    records = []
    with tempfile.TemporaryDirectory(prefix="jiuwenswarm-memory-benchmark-", dir=temp_parent) as tmp:
        workspace = Path(tmp)
        seed_baseline(workspace, dataset["facts"])
        builder = SectionCollector()
        enhanced, engine = seed_enhanced(dataset["facts"])

        # Keep machine-specific user and managed memory out of this benchmark.
        saved_sources = {name: getattr(memory_files, name) for name in EXTERNAL_MEMORY_SOURCES}
        try:
            for name in EXTERNAL_MEMORY_SOURCES:
                setattr(memory_files, name, ())
            memory_files.clear_project_memory_cache()
            baseline = await build_baseline_with_budget(workspace, builder, budget)
            for repeat in range(repeats):
                for question in dataset["questions"]:
                    start = time.perf_counter()
                    await baseline.before_model_call(SimpleNamespace(inputs=SimpleNamespace()))
                    baseline_context = builder.render()
                    baseline_ms = (time.perf_counter() - start) * 1000
                    if len(baseline_context) > budget:
                        raise AssertionError("ProjectMemoryRail exceeded the full context budget")
                    records.append(record("project_memory_rail", repeat, question, baseline_context, baseline_ms))

                    start = time.perf_counter()
                    retrieved_context = enhanced_context(enhanced, engine, question["query"], budget, top_k)
                    enhanced_ms = (time.perf_counter() - start) * 1000
                    records.append(record("multi_level_hybrid", repeat, question, retrieved_context, enhanced_ms))
        finally:
            for name, value in saved_sources.items():
                setattr(memory_files, name, value)
            memory_files.clear_project_memory_cache()
    return records


def summarize(records: list[dict]) -> dict:
    result = {}
    for system in {row["system"] for row in records}:
        rows = [row for row in records if row["system"] == system]
        result[system] = {
            "mean_recall": statistics.mean(row["recall"] for row in rows),
            "mean_context_chars": statistics.mean(row["context_chars"] for row in rows),
            "median_latency_ms": statistics.median(row["latency_ms"] for row in rows),
            "n": len(rows),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path(__file__).parent / "data" / "memory_retrieval_v1.json")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "results" / "memory_rail_benchmark.json")
    parser.add_argument("--context-chars", type=int, default=600)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if min(args.context_chars, args.top_k, args.repeats) <= 0:
        parser.error("context-chars, top-k and repeats must be positive")

    dataset_bytes = args.dataset.read_bytes()
    dataset = load_dataset(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = asyncio.run(run(dataset, args.context_chars, args.top_k, args.repeats, args.output.parent))
    report = {
        "benchmark": "JiuwenSwarm memory context recall (no LLM)",
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "python": platform.python_version(),
        "settings": {"context_chars": args.context_chars, "top_k": args.top_k, "repeats": args.repeats},
        "summary": summarize(rows),
        "records": rows,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Raw results: {args.output}")


if __name__ == "__main__":
    main()
