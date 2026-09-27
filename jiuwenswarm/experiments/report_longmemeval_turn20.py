"""Validate and plot live results on the adapted LongMemEval-S 20-turn slice."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "jiuwenswarm-memory-ab-mpl"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter


HERE = Path(__file__).parent


def load_and_validate(path: Path, dataset_sha: str, question_ids: set[str]) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    if (report.get("kind") != "adapted_longmemeval_live"
            or report.get("official_longmemeval_score") is not False
            or report.get("dataset_sha256") != dataset_sha
            or report["settings"]["episodes"] != len(question_ids)):
        raise ValueError(f"Wrong report kind, dataset or case count: {path}")
    rows = report["records"]
    if len(rows) != 2 * len(question_ids):
        raise ValueError(f"Missing paired records: {path}")
    for group in ("baseline", "enhanced"):
        arm = [row for row in rows if row["group"] == group]
        if {row["question_id"] for row in arm} != question_ids:
            raise ValueError(f"Incomplete {group} questions: {path}")
        if len(arm) != len(question_ids):
            raise ValueError(f"Duplicate {group} questions: {path}")
    for row in rows:
        if (row["status"] != "ok" or not row["history_isolated"]
                or not row["memory_in_model_prompt"]
                or row["memory_chars"] > report["settings"]["context_chars"]):
            raise ValueError(f"Invalid Agent observation in {path}: {row['question_id']}")
    if len(report["runs"]) != 2 * len(question_ids):
        raise ValueError(f"Missing seed records: {path}")
    return report


def metrics(report: dict, group: str) -> dict:
    rows = [row for row in report["records"] if row["group"] == group]
    runs = [run for run in report["runs"] if run["group"] == group]
    token_values = [row["total_tokens"] for row in rows] + [run["seed_total_tokens"] for run in runs]
    if any(value is None for value in token_values):
        raise ValueError("Model did not return complete Token usage")
    return {
        "correct": sum(bool(row["correct"]) for row in rows),
        "accuracy": statistics.mean(bool(row["correct"]) for row in rows),
        "evidence_found": sum(row["evidence_recall"] == 1 for row in rows),
        "complete_evidence_recall": statistics.mean(row["evidence_recall"] for row in rows),
        "mean_memory_chars": statistics.mean(row["memory_chars"] for row in rows),
        "query_tokens": sum(row["total_tokens"] for row in rows),
        "seed_tokens": sum(run["seed_total_tokens"] for run in runs),
        "all_tokens": sum(token_values),
        "tokens_per_question_including_seed": sum(token_values) / len(rows),
        "seed_model_calls": sum(run["seed_model_calls"] for run in runs),
        "mean_query_latency_ms": statistics.mean(row["latency_ms"] for row in rows),
        "mean_end_to_end_latency_ms": (
            sum(row["latency_ms"] for row in rows)
            + sum(run["seed_latency_ms"] for run in runs)
        ) / len(rows),
    }


def draw(sweep: list[dict], output: Path) -> None:
    budgets = [point["context_chars"] for point in sweep]
    fig, (score_ax, cost_ax) = plt.subplots(1, 2, figsize=(10.3, 4.1))
    for group, label, color, marker in (
        ("baseline", "ProjectMemoryRail", "#4063a1", "o"),
        ("enhanced", "EnhancedMemoryRail", "#c15a42", "s"),
    ):
        score_ax.plot(budgets, [point[group]["accuracy"] for point in sweep],
                      marker=marker, color=color, linewidth=2, label=f"{label}: answer")
        score_ax.plot(budgets, [point[group]["complete_evidence_recall"] for point in sweep],
                      marker=marker, color=color, linewidth=1.5, linestyle="--",
                      label=f"{label}: evidence")
        cost_ax.plot(budgets, [point[group]["tokens_per_question_including_seed"] for point in sweep],
                     marker=marker, color=color, linewidth=2, label=label)
    for ax in (score_ax, cost_ax):
        ax.set_xticks(budgets, [str(value) for value in budgets])
        ax.set_xlabel("Memory section cap (characters)")
        ax.grid(alpha=0.25)
    score_ax.set_ylim(-0.05, 1.05)
    score_ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    score_ax.set_ylabel("Fraction of questions")
    score_ax.legend(loc="lower right", fontsize=7)
    cost_ax.set_ylabel("Tokens per question, including fact writes")
    fig.suptitle("Adapted LongMemEval-S: single-layer memory retrieval", fontsize=12)
    fig.text(0.5, 0.01, "20 independent adapted questions; qwen-plus; one run per budget; not an official score",
             ha="center", fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, 0.06, 1, 0.94))
    fig.savefig(output, dpi=300, bbox_inches="tight")
    fig.savefig(output.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=HERE / "data" / "longmemeval_s_turn20_v1.json")
    parser.add_argument("--reports", nargs="+", type=Path, default=[
        HERE / "results" / "longmemeval_s_turn20_live.json",
        HERE / "results" / "longmemeval_s_turn20_live_2400.json",
    ])
    parser.add_argument("--out-dir", type=Path, default=HERE / "results" / "figures")
    args = parser.parse_args()
    dataset_bytes = args.dataset.read_bytes()
    dataset = json.loads(dataset_bytes)
    ids = {episode["id"] for episode in dataset["episodes"]}
    if len(ids) != len(dataset["episodes"]):
        raise ValueError("Duplicate question IDs in adapted dataset")
    digest = hashlib.sha256(dataset_bytes).hexdigest()
    sweep = []
    model = None
    for path in args.reports:
        report = load_and_validate(path, digest, ids)
        current_model = report["settings"]["model_name"]
        if model is not None and current_model != model:
            raise ValueError("Different models between budgets")
        model = current_model
        sweep.append({
            "context_chars": report["settings"]["context_chars"],
            "source": str(path.resolve()),
            "baseline": metrics(report, "baseline"),
            "enhanced": metrics(report, "enhanced"),
        })
    sweep.sort(key=lambda point: point["context_chars"])
    if len({point["context_chars"] for point in sweep}) != len(sweep):
        raise ValueError("Duplicate memory budget")
    summary = {
        "kind": "adapted_longmemeval_turn20_summary",
        "official_longmemeval_score": False,
        "dataset_sha256": digest,
        "source_sha256": dataset["source_sha256"],
        "model_name": model,
        "unique_questions": len(ids),
        "budget_sweep": sweep,
        "scoring_limit": "Provisional answer-string match; manually audit raw answers before publication.",
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "longmemeval_turn20_budget_summary.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    image_path = args.out_dir / "longmemeval_turn20_budget.png"
    draw(sweep, image_path)
    print(f"Summary: {json_path}")
    print(f"Figure: {image_path}")
    print(f"Vector figure: {image_path.with_suffix('.svg')}")


if __name__ == "__main__":
    main()
