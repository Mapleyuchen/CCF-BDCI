"""Validate live memory A/B reports and draw the context-budget experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "jiuwenswarm-memory-ab-mpl")
)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter


HERE = Path(__file__).parent
DEFAULT_REPORTS = [
    HERE / "results" / f"agent_memory_ab_{budget}.json"
    for budget in (300, 1200, 2400)
]
DEFAULT_REPORTS.insert(1, HERE / "results" / "agent_memory_ab_live_20.json")


def read_report(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("kind") != "live_model_experiment":
        raise ValueError(f"Only live-model reports are accepted: {path}")
    return report


def validate(report: dict[str, Any], path: Path, *, expected_repeats: int) -> None:
    settings = report["settings"]
    rows = report["records"]
    questions = settings["questions"]
    repeats = settings["repeats"]
    if repeats != expected_repeats or len(rows) != questions * repeats * 2:
        raise ValueError(f"Wrong repeat count or missing rows: {path}")
    keys = [(row["repeat"], row["question_id"], row["group"]) for row in rows]
    if len(set(keys)) != len(keys):
        raise ValueError(f"Duplicate paired records: {path}")
    for repeat in range(repeats):
        question_sets = []
        for group in ("baseline", "enhanced"):
            subset = [row for row in rows if row["repeat"] == repeat and row["group"] == group]
            if len(subset) != questions:
                raise ValueError(f"Incomplete paired records: {path}")
            question_sets.append({row["question_id"] for row in subset})
        if question_sets[0] != question_sets[1]:
            raise ValueError(f"Arms have different questions: {path}")
    for row in rows:
        if (row["status"] != "ok" or not row["history_isolated"]
                or not row["memory_in_model_prompt"]
                or row["memory_chars"] > settings["context_chars"]):
            raise ValueError(f"Invalid trial {row['question_id']} in {path}")


def arm_metrics(report: dict[str, Any], group: str,
                facts: list[dict[str, str]]) -> dict[str, Any]:
    rows = [row for row in report["records"] if row["group"] == group]
    runs = [run for run in report["runs"] if run["group"] == group]
    complete_ids = [
        {fact["id"] for fact in facts
         if f"<FACT:{fact['id']}> {fact['text']}" in row["memory_context"]}
        for row in rows
    ]
    full_recall = [
        len(ids & set(row["relevant_ids"])) / len(row["relevant_ids"])
        for row, ids in zip(rows, complete_ids)
    ]
    marker_only_hits = sum(
        bool(set(row["observed_ids"]) & set(row["relevant_ids"]))
        and not bool(ids & set(row["relevant_ids"]))
        for row, ids in zip(rows, complete_ids)
    )
    tokens = [row.get("total_tokens") for row in rows]
    seed_tokens = [run.get("seed_total_tokens") for run in runs]
    if any(value is None for value in tokens + seed_tokens):
        all_tokens = None
        mean_total_tokens = None
    else:
        all_tokens = sum(tokens) + sum(seed_tokens)
        mean_total_tokens = all_tokens / len(rows)
    return {
        "answered": len(rows),
        "correct": sum(bool(row["correct"]) for row in rows),
        "accuracy": statistics.mean(bool(row["correct"]) for row in rows),
        "complete_fact_recall": statistics.mean(full_recall),
        "marker_only_hits": marker_only_hits,
        "mean_memory_chars": statistics.mean(row["memory_chars"] for row in rows),
        "mean_query_latency_ms": statistics.mean(row["latency_ms"] for row in rows),
        "seed_model_calls": sum(run.get("seed_model_calls", 0) for run in runs),
        "seed_total_tokens": sum(seed_tokens) if all(value is not None for value in seed_tokens) else None,
        "all_tokens": all_tokens,
        "tokens_per_answer_including_seed": mean_total_tokens,
    }


def build_summary(paths: list[Path], repeat_path: Path | None,
                  dataset_path: Path, shuffled_path: Path | None) -> dict[str, Any]:
    reports = [(path, read_report(path)) for path in paths]
    if not reports:
        raise ValueError("At least one report is required")
    first = reports[0][1]
    fingerprint = (first["dataset_sha256"], first["settings"]["model_name"],
                   first["settings"]["questions"])
    dataset_bytes = dataset_path.read_bytes()
    if hashlib.sha256(dataset_bytes).hexdigest() != fingerprint[0]:
        raise ValueError("Dataset differs from the dataset used to produce the reports")
    facts = json.loads(dataset_bytes)["facts"]
    sweep = []
    seen_budgets = set()
    for path, report in reports:
        validate(report, path, expected_repeats=1)
        current = (report["dataset_sha256"], report["settings"]["model_name"],
                   report["settings"]["questions"])
        if current != fingerprint:
            raise ValueError(f"Dataset/model/question count differs: {path}")
        budget = report["settings"]["context_chars"]
        if budget in seen_budgets:
            raise ValueError(f"Duplicate context budget: {budget}")
        seen_budgets.add(budget)
        sweep.append({
            "context_chars": budget,
            "source": str(path.resolve()),
            "baseline": arm_metrics(report, "baseline", facts),
            "enhanced": arm_metrics(report, "enhanced", facts),
        })
    sweep.sort(key=lambda item: item["context_chars"])
    summary: dict[str, Any] = {
        "dataset_sha256": fingerprint[0],
        "model_name": fingerprint[1],
        "unique_questions": fingerprint[2],
        "budget_sweep": sweep,
        "interpretation_limit": (
            "Synthetic questions share one 20-fact project; budget points are single runs. "
            "Repeated prompts are not independent samples. The enhanced arm includes "
            "20 model calls to write facts, whereas the baseline reads a file. "
            "The 300-character baseline is especially affected by section metadata. "
            "Complete-fact recall is recomputed from saved prompt text; older raw "
            "reports counted a truncated fact marker as evidence."
        ),
    }
    if repeat_path is not None:
        repeat_report = read_report(repeat_path)
        repeat_count = repeat_report["settings"]["repeats"]
        validate(repeat_report, repeat_path, expected_repeats=repeat_count)
        current = (repeat_report["dataset_sha256"], repeat_report["settings"]["model_name"],
                   repeat_report["settings"]["questions"])
        if current != fingerprint:
            raise ValueError(f"Repeat report uses different dataset/model: {repeat_path}")
        summary["repeat_check"] = {
            "context_chars": repeat_report["settings"]["context_chars"],
            "repeats": repeat_count,
            "unique_questions": fingerprint[2],
            "source": str(repeat_path.resolve()),
            "by_repeat": repeat_report["summary"]["by_repeat"],
            "baseline": arm_metrics(repeat_report, "baseline", facts),
            "enhanced": arm_metrics(repeat_report, "enhanced", facts),
        }
    if shuffled_path is not None:
        shuffled = read_report(shuffled_path)
        shuffle_count = shuffled["settings"]["repeats"]
        validate(shuffled, shuffled_path, expected_repeats=shuffle_count)
        current = (shuffled["dataset_sha256"], shuffled["settings"]["model_name"],
                   shuffled["settings"]["questions"])
        if current != fingerprint or shuffled["settings"].get("fact_order_seed") is None:
            raise ValueError(f"Invalid shuffled run or different dataset/model: {shuffled_path}")
        orders = []
        for repeat in range(shuffle_count):
            pair = [run["fact_order"] for run in shuffled["runs"] if run["repeat"] == repeat]
            if len(pair) != 2 or pair[0] != pair[1]:
                raise ValueError(f"Fact order differs between arms: {shuffled_path}")
            orders.append(tuple(pair[0]))
        if len(set(orders)) != shuffle_count:
            raise ValueError(f"Fact order did not change across repeats: {shuffled_path}")
        summary["order_sensitivity"] = {
            "context_chars": shuffled["settings"]["context_chars"],
            "fact_order_seed": shuffled["settings"]["fact_order_seed"],
            "repeats": shuffle_count,
            "unique_questions": fingerprint[2],
            "source": str(shuffled_path.resolve()),
            "by_repeat": shuffled["summary"]["by_repeat"],
            "baseline": arm_metrics(shuffled, "baseline", facts),
            "enhanced": arm_metrics(shuffled, "enhanced", facts),
        }
    return summary


def draw(summary: dict[str, Any], output: Path) -> None:
    sweep = summary["budget_sweep"]
    budgets = [row["context_chars"] for row in sweep]
    fig, (accuracy_ax, token_ax) = plt.subplots(1, 2, figsize=(10.4, 4.1))
    for group, label, color, marker in (
        ("baseline", "ProjectMemoryRail", "#4063a1", "o"),
        ("enhanced", "EnhancedMemoryRail", "#c15a42", "s"),
    ):
        accuracy_ax.plot(
            budgets, [row[group]["accuracy"] for row in sweep],
            marker=marker, color=color, linewidth=2, label=label,
        )
        token_ax.plot(
            budgets, [row[group]["tokens_per_answer_including_seed"] for row in sweep],
            marker=marker, color=color, linewidth=2, label=label,
        )
    for ax in (accuracy_ax, token_ax):
        ax.set_xscale("log", base=2)
        ax.set_xticks(budgets, [str(budget) for budget in budgets])
        ax.grid(alpha=0.25)
        ax.set_xlabel("Memory section cap (characters)")
    accuracy_ax.set_ylim(-0.05, 1.05)
    accuracy_ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    accuracy_ax.set_ylabel("Answer accuracy")
    accuracy_ax.legend(loc="lower right", fontsize=8)
    token_ax.set_ylabel("Tokens per answer, including fact writes")
    fig.suptitle("Single-layer memory retrieval: shared context budget", fontsize=12)
    fig.text(
        0.5, 0.01,
        "20 synthetic questions; one run per budget; qwen-plus; enhanced fact-write calls included",
        ha="center", fontsize=8, color="#555555",
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.94))
    fig.savefig(output, dpi=300, bbox_inches="tight")
    fig.savefig(output.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, nargs="+", default=DEFAULT_REPORTS)
    parser.add_argument("--dataset", type=Path,
                        default=HERE / "data" / "memory_agent_qa_v2.json")
    parser.add_argument("--repeat-report", type=Path,
                        default=HERE / "results" / "agent_memory_ab_600_repeat3.json")
    parser.add_argument("--shuffled-report", type=Path,
                        default=HERE / "results" / "agent_memory_ab_600_shuffled_repeat3.json")
    parser.add_argument("--out-dir", type=Path, default=HERE / "results" / "figures")
    args = parser.parse_args()
    summary = build_summary(args.reports, args.repeat_report, args.dataset,
                            args.shuffled_report)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "memory_ab_budget_summary.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    image_path = args.out_dir / "memory_ab_budget.png"
    draw(summary, image_path)
    print(f"Summary: {json_path}")
    print(f"Figure: {image_path}")
    print(f"Vector figure: {image_path.with_suffix('.svg')}")


if __name__ == "__main__":
    main()
