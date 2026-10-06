"""Create a completed revision brief only after the full scored run validates."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from memory_eval.data import HERE, read_json
from memory_eval.reporting import build_report, export_pairs, figures_and_tables, paper_sections, mechanistic_cases, retrieval_report, retrieval_figures, protocol_diagram, write_json

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, default=HERE / "results/memory_eval_v2")
    p.add_argument("--retrieval-run", type=Path, default=HERE / "results/memory_eval_v2_retrieval_final")
    args = p.parse_args()
    summary, trials, constructions = build_report(args.run)
    execution = summary["source_manifest"]["execution"]
    if summary["scoring"]["secondary_judge_model"] != summary["source_manifest"]["protocol"]["solver_model"]:
        raise ValueError("Complete the fixed secondary scoring audit before producing the revision brief")
    if (execution["suite"] != "all" or execution["repeats"] != 3 or execution["max_episodes"] != 0
            or execution["budgets"] != [512,1024,2048] or execution["selectors"] is not None
            or execution["lifecycle_episodes"] != 8):
        raise ValueError("Completed revision brief requires the full frozen v2 design; smaller live pilots may only use report_memory_eval.py")
    retrieval = retrieval_report(args.retrieval_run)
    if retrieval["n_trials"] != 9000:
        raise ValueError("Completed revision requires all 500 histories and all six selectors at three budgets")
    report = args.run / "report"
    write_json(report / "summary.json", summary)
    write_json(report / "retrieval_summary.json", retrieval)
    export_pairs(report / "paper_exports", summary, trials, constructions)
    figures_and_tables(report, summary)
    paper_sections(report, summary, retrieval)
    retrieval_figures(report, retrieval)
    protocol_diagram(report)
    mechanistic_cases(args.run, report, trials)
    audit_rows = read_json(args.run / "scoring/blinded_adjudication_queue.json")
    write_json(report / "model_disagreement_review.json", [r for r in audit_rows if r.get("judges_agree") is False])
    examples = HERE.parent / "research-paper-generator/examples"
    brief = read_json(examples / "memory-revision.brief.json")
    brief["experiments"] = [e for e in brief["experiments"] if e["id"] not in ("public_small", "public_large")]
    brief.pop("writing_profile", None)
    brief["methods"] = [
        dict(id="baseline", title="Frozen Memory and Matched Token Packing", citation_ids=[],
             description="Full source histories are retained in a read-only single-layer bank, segmented losslessly into at most 256 pinned Qwen3 BPE tokens per turn segment. All selectors use the same source records, timestamps, metadata, memory wrapper and whole-item first-fit overflow policy under 512/1024/2048 tokens. This removes the pilot's extra file path formatting penalty. The controlled full-history bank is distinct from the legacy production Rail's 20-entry L1 capacity."),
        dict(id="retrieval", title="Stronger Selectors and Isolated Controls", citation_ids=["memgpt"],
             description="Compare prefix, recency, lexical Jaccard, BM25 and existing hybrid. BM25 uses k1=1.2, b=0.75, positive idf. Remove only the weighted temporal contribution for selection ablation. Frequency is fixed at zero and importance at 0.5, so hybrid_no_time and Jaccard provide a sanity equivalence check. Representation changes only deterministic raw versus ACK exchange formatting in the adapted 20-item micro workload. Real EnhancedMemoryRail model-ACK acquisition is followed by canonicalization to exactly identical source records and solver prompts, isolating write-path overhead rather than learned extraction quality. No new algorithm or L2/L3 behavior is claimed."),
        dict(id="protocol", title="Repeated Real Agent Evaluation and Memory Reuse", citation_ids=["longmemeval"],
             description="The 84-question stratified LongMemEval-S subset spans six question types plus abstention, with three actual solver calls per question/arm/budget and isolated conversation IDs. Full 500-history retrieval is separate from QA. Real DeepAgents use qwen-plus-2025-12-01, temperature zero, no tools, and one iteration. The pinned official task-specific grading prompts use qwen3-max-2026-01-23, with a second fixed-model audit and pending blinded human adjudication. Average repeats within each memory episode; stratified cluster bootstrap and paired cluster sign-flip tests with Holm correction. Eight synthetic banks each serve twenty distinct questions after a single build; actual query prefixes measure write amortization. Query wall time includes rate-gate waiting and excludes preprocessing; call latency and queue waiting are logged separately.")]
    files = {
        "fair_baselines": "full_1024_hybrid-bm25.json",
        "selection_ablation": "full_1024_hybrid-hybrid_no_time.json",
        "representation_ablation": "micro_1024_hybrid_exchange-hybrid_raw.json",
        "construction_ablation": "micro_1024_hybrid_model_ack-hybrid_raw.json",
        "memory_reuse": "reuse_512_hybrid_model_ack-hybrid_raw.json",
        "protocol_replication": "full_2048_hybrid-bm25.json"}
    dataset_sources = {
        "full": (HERE / "data/public/longmemeval_s_cleaned.json", summary["source_manifest"]["protocol"]["source_sha256"]),
        "micro": (HERE / "data/longmemeval_s_turn20_v1.json", None),
        "reuse": (HERE / "data/memory_agent_qa_v2.json", None)}
    for kind, (source, expected_hash) in dataset_sources.items():
        dataset_sources[kind] = (source, expected_hash or hashlib.sha256(source.read_bytes()).hexdigest())
    for experiment in brief["experiments"]:
        if experiment["id"] in files:
            path = (report / "paper_exports" / files[experiment["id"]]).resolve()
            if not path.is_file():
                raise ValueError(f"Required export is missing: {path.name}")
            import os
            experiment.update(status="completed", result_path=Path(os.path.relpath(path, examples)).as_posix())
            experiment["limitations"] = summary["limitations"] + [summary["retrieval_metric_scope"], summary["latency_scope"]]
            experiment["metrics"] = (["semantic answer accuracy", "evidence-session recall",
                "annotated-turn recall (any fragment)", "annotated-turn character coverage",
                "complete annotated-turn coverage", "write-plus-query tokens", "query latency including scheduling"]
                if experiment["id"] in ("fair_baselines", "selection_ablation", "protocol_replication") else
                ["semantic answer accuracy", "required fact-item recall", "write-plus-query tokens", "query latency including scheduling"])
            protocol = experiment["protocol"]
            protocol["budget"]["values"] = [512] if experiment["id"] == "memory_reuse" else [1024] if experiment["id"] != "protocol_replication" else [2048]
            protocol["baselines"] = [name.replace(" (requires implementation)", "") for name in protocol["baselines"]]
            dataset_kind = "full" if experiment["id"] in ("fair_baselines", "selection_ablation", "protocol_replication") else "reuse" if experiment["id"] == "memory_reuse" else "micro"
            protocol["dataset"] = dict(name="LongMemEval-S full history subset" if dataset_kind == "full" else "Adapted 20-item micro workload" if dataset_kind == "micro" else "Synthetic entity/value variants",
                split="Predeclared evaluation", version=dataset_sources[dataset_kind][1],
                sample_size=84 if experiment["id"] in ("fair_baselines", "selection_ablation", "protocol_replication") else 20 if experiment["id"] != "memory_reuse" else 8,
                adaptation="Full history source is retained. QA is a balanced subset and uses a substituted Qwen judge. Micro and synthetic reuse remain separate mechanism/cost controls; see experiment evidence limitations.")
            dependencies = summary["source_manifest"]["protocol"]["dependencies"]
            protocol["budget"]["tokenizer"] = (dependencies["tokenizer_repo"] + "@" + dependencies["tokenizer_revision"]
                + "; tokenizer.json SHA256=" + dependencies["tokenizer_files"]["tokenizer.json"])
            scoring = summary["scoring"]
            protocol["scoring"] = dict(
                method="Pinned original LongMemEval task-specific prompts; arm-blind strict yes/no parsing; primary " + scoring["primary_judge_model"] + "; secondary audit " + scoring["secondary_judge_model"] + ".",
                version=dependencies["longmemeval_commit"] + "; scorer SHA256=" + dependencies["scorer_sha256"],
                review=f"{scoring['audit_questions']} distinct responses audited; {scoring['judge_disagreements']} model disagreements. Human adjudication remains pending; main results retain the predeclared primary judge. Full scoring metadata is in the traced result export.")
            protocol["statistics"] = dict(unit="Memory episode, averaging repeats within memory", method=summary["inference"])
            if experiment["id"] == "representation_ablation":
                experiment["limitations"].append("The selector algorithm is fixed, but exchange formatting changes lexical features and token packing. This intervention does not isolate packing alone.")
            if experiment["id"] == "memory_reuse":
                protocol["baselines"] = ["Hybrid with direct canonical insertion", "Hybrid with real model-ACK acquisition and identical canonical read content"]
                protocol["controlled_variables"] = [v for v in protocol["controlled_variables"] if v != "write_path"]
                protocol["changed_variables"] = ["write_path", "observed_distinct_query_prefix_length"]
    brief["writing_notes"] = [
        "Completed v2 experimental evidence is supplied, but human scoring review remains required. Do not claim a guaranteed reviewer-score improvement or scientific approval.",
        "Use the general content renderer with the controlled_memory_eval_live adapter. Do not use the legacy jiuwenswarm_l1_v1 research profile's character-budget equations or diagrams.",
        "Lead with the token-matched BM25 comparison, including negative or inconclusive differences. Pilot character-budget results belong in historical limitations, not as principal evidence of retrieval quality.",
        "Fair-baselines and protocol-replication use the same 84 questions at different budgets; repeated calls and budgets are not independent tasks. Full 500-history retrieval is not 500-question answer accuracy.",
        "Selection, representation and construction controls have different scopes. Representation/construction micro data cannot establish causal gains on the full-history workload.",
        "Eight synthetic banks share templates. Reuse curves are measured distinct-query prefixes, not evidence for long-term natural memory generalization.",
        "The production EnhancedMemoryRail still has 20 L1 entries. The frozen full-history bank does not demonstrate production persistence, multi-layer memory or team synchronization.",
        "Figures and tables are generated from actual traced data. Report semantically judged accuracy, evidence-session hit definition, memory-cluster intervals and corrected tests without inventing algorithm novelty."]
    brief["source_notes"]["longmemeval"] = "Verified author paper/repository: LongMemEval evaluates extraction, multi-session reasoning, temporal reasoning, updates and abstention, separating indexing, retrieval and reading. Our pinned cleaned S source is retained in full; QA is a fixed-hash balanced 84-question subset, while retrieval uses all 500 histories. Segmented records and a substituted Qwen judge are explicit deviations, not an official score."
    target = examples / "memory-eval-v2.brief.json"
    write_json(target, brief)
    from archive_memory_eval_code import archive_sources
    archive_sources(args.run)
    print(f"Completed experimental handoff: {target}")

if __name__ == "__main__":
    main()
