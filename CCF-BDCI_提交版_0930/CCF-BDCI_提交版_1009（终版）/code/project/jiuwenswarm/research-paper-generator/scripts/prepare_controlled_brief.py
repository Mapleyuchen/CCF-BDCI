#!/usr/bin/env python3
"""Curate module-2 exports into a portable module-3 paper brief, without model calls."""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
REPORT = MODULE.parent / "experiments/results/memory_eval_v2/report"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_path(path, base):
    # Windows cannot express a relative source path across drives. Generation
    # snapshots either form into a portable project-relative path afterwards.
    try:
        return Path(os.path.relpath(path.resolve(), base.resolve())).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def curate(source, report, output):
    if output.exists():
        raise ValueError("Output brief already exists; choose a new filename")
    brief = deepcopy(read(source))
    manifest = read(report / "paper_exports/manifest.json")
    exports = {}
    for item in manifest["files"]:
        path = (report / "paper_exports" / item["path"]).resolve()
        if not path.is_relative_to((report / "paper_exports").resolve()):
            raise ValueError("Export manifest path escapes its directory")
        if path.name in exports or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Duplicate or changed export: {path.name}")
        exports[path.name] = (path, item["sha256"])
    # Preserve upstream IDs for existing consumers; add the missing low-budget comparison.
    low = deepcopy(next(e for e in brief["experiments"] if e["id"] == "fair_baselines"))
    low.update(id="fair_baselines_512", result_path=str(exports["full_512_hybrid-bm25.json"][0]))
    brief["experiments"].insert(0, low)
    selected = set()
    for experiment in brief["experiments"]:
        filename = Path(experiment["result_path"]).name
        path, digest = exports[filename]
        selected.add(filename)
        data = read(path)
        labels = data["settings"]["group_labels"]
        budget = data["settings"]["context_tokens"]
        suite = data["comparison"]["suite"]
        experiment.update(result_path=source_path(path, output.parent), result_sha256=digest)
        protocol = experiment["protocol"]
        protocol["budget"]["values"] = [budget]
        # Each result file contains only its named pair, even though the whole run had more arms.
        protocol["baselines"] = [labels["baseline"], labels["enhanced"]]
        protocol["repeats"] = data["settings"]["repeats"]
        experiment["limitations"].append("This subsection reports only its linked pair. Additional arms and budgets are supplied as supplementary exports; do not count overlapping comparisons as independent data.")
        titles = {
            "fair_baselines_512": "Hybrid versus BM25 under the Small Token Budget",
            "fair_baselines": "Primary Hybrid versus BM25 Comparison",
            "protocol_replication": "Budget Sensitivity on the Same Questions",
            "selection_ablation": "Temporal Contribution with Fixed Records",
            "representation_ablation": "Exchange Representation on the Micro Workload",
            "construction_ablation": "Model-ACK Acquisition with Canonical Read Content",
            "memory_reuse": "Measured Memory Reuse on Synthetic Banks",
        }
        experiment["title"] = titles[experiment["id"]]
        if experiment["id"] == "protocol_replication":
            experiment["purpose"] = "comparison"
            experiment["limitations"].append("This is the high-budget condition of the same evaluation, not an independent replication or a completed human scoring audit.")
        if suite == "reuse":
            experiment["limitations"].append("The linked pair provides the endpoint after twenty queries. The other prefix lengths and BM25 reuse comparator are in the supporting summary/figure, not this pair's metric catalog.")
    # Keep primary comparisons adjacent without renaming upstream evidence IDs.
    order = ["fair_baselines_512", "fair_baselines", "protocol_replication", "selection_ablation",
             "representation_ablation", "construction_ablation", "memory_reuse"]
    brief["experiments"].sort(key=lambda e: order.index(e["id"]))
    for concern in brief["review_concerns"]:
        if concern["id"] in ("fairness", "robustness", "contribution"):
            concern["experiment_ids"] = list(dict.fromkeys(["fair_baselines_512", "fair_baselines", "protocol_replication"] + concern["experiment_ids"]))
    brief["writing_notes"] += [
        "The three primary comparisons all show lower hybrid accuracy than BM25. Preserve these negative results and their paired intervals/corrected tests; do not reuse the pilot's superiority narrative.",
        "protocol_replication is a retained compatibility ID for high-budget sensitivity on the same questions, not independent replication. Human scoring review remains incomplete.",
        "Each result subsection maps to exactly one pair at one budget. Put the main three-budget plot and key ablation findings in the body; other baseline comparisons, categories and full-history retrieval belong in supplementary analysis.",
        "The supporting materials are hashed source assets for the writing and quality owners. Their numbers do not automatically become validated metric tokens. The current reuse pair gives the twenty-query endpoint; use the supplied measured-prefix table/plot only after integrating and checking its summary.",
        "Reviewer concerns require scientific review even though all listed experiments have result files. Keep the blinded human-adjudication task explicitly open.",
    ]
    brief["supporting_materials"] = []

    def add(mid, title, path, kind, placement, purpose, refs=()):
        brief["supporting_materials"].append({"id": mid, "title": title, "kind": kind, "placement": placement,
            "path": source_path(path, output.parent),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "purpose": purpose, "experiment_ids": list(refs)})

    for name, title, refs, placement, purpose in (
        ("fair_baselines", "Token-matched answer quality", order[:3], "main", "Main comparison across all budgets; show negative hybrid versus BM25 differences and memory-cluster intervals."),
        ("evaluation_protocol", "Controlled evaluation protocol", [], "main", "Use this measured protocol diagram instead of the old multi-layer or character-budget illustration."),
        ("memory_reuse", "Observed write amortization", ["memory_reuse"], "main", "Measured distinct-query prefixes; the QA pair's endpoint alone cannot reconstruct the full curve."),
        ("category_accuracy", "Task-category accuracy", ["fair_baselines"], "appendix", "Category counts and intervals are in the summary; not a new independent dataset."),
        ("full500_retrieval", "Full-history retrieval coverage", [], "appendix", "Retrieval-only analysis of all histories; never describe this as full-dataset answer accuracy."),
    ):
        add(name, title, report / f"{name}.pdf", "figure", placement, purpose, refs)
    for name, kind, placement, purpose in (
        ("summary.json", "statistics", "handoff", "Upstream full-run summary, including measured reuse prefixes; use with raw exports and scoring caveats."),
        ("retrieval_summary.json", "statistics", "appendix", "Retrieval-only denominators and coverage definitions."),
        ("results_table.tex", "table", "appendix", "Full group table for selective inclusion after checking caption, units and width."),
        ("experimental_methods.tex", "prose", "handoff", "Verified upstream protocol prose to adapt to the manuscript's section structure and citation keys."),
        ("experimental_results.tex", "prose", "handoff", "Upstream results including negative effects and adjusted tests; review before inserting."),
        ("mechanistic_analysis.tex", "prose", "appendix", "Diagnostic interpretation; check case evidence and avoid stronger causal attribution."),
        ("mechanistic_cases.json", "statistics", "appendix", "Question-level diagnostic cases supporting the upstream interpretation."),
        ("judge_sensitivity.json", "statistics", "appendix", "Partial secondary-judge sensitivity, not human accuracy or full second-model rescoring."),
        ("model_disagreement_review.json", "review_queue", "handoff", "239 model disagreements with member-5 boolean decisions. Main scores still use the primary judge."),
        ("EXPERIMENT_HANDOFF.md", "documentation", "handoff", "Original experimental handoff and scope restrictions."),
    ):
        add(Path(name).stem.lower(), name, report / name, kind, placement, purpose)
    add("blinded_adjudication", "Blinded human adjudication queue", report.parent / "scoring/blinded_adjudication_queue.json",
        "review_queue", "handoff", "Full audit queue. Keep human decisions pending; model agreement is not human review.")
    add("export_manifest", "Original paired-export manifest", report / "paper_exports/manifest.json", "documentation", "handoff",
        "Original filenames and expected hashes. Portable copies use the supporting-material index; original paths are provenance only.")
    for filename, (path, digest) in exports.items():
        if filename not in selected:
            add("extra_" + path.stem, filename, path, "supplementary_evidence", "appendix",
                "Additional paired raw answers and scoring provenance. Recompute with normalize_result before quoting; overlapping records must not be added to sample size.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return brief


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=MODULE / "examples/memory-eval-v2.brief.json")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        brief = curate(args.source.resolve(), args.report.resolve(), args.output.resolve())
        print(f"Prepared {len(brief['experiments'])} primary result sections and {len(brief['supporting_materials'])} supporting materials: {args.output}")
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Handoff preparation failed: {error}\n")


if __name__ == "__main__":
    main()
