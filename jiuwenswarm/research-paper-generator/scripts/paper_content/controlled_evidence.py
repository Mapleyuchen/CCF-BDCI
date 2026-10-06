"""Adapter for token-matched v2 traces; recompute rather than trust summaries."""
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def normalize_controlled(data, path, evidence_id, title):
    source = data["source_manifest"]
    if source["kind"] != "memory_eval_v2_live" or source["execution"]["self_test"]:
        raise ValueError("Controlled evidence must use real model calls")
    settings, rows = data["settings"], data["records"]
    budget = settings["context_tokens"]
    if type(budget) is not int or budget <= 0 or settings["budget_unit"] != "tokens":
        raise ValueError("A positive token budget is required")
    if "self-test" in settings["model_name"] or settings["model_name"] != source["model_name"]:
        raise ValueError("Live model identities differ")
    stats_path = Path(__file__).resolve().parents[3] / "experiments/memory_eval/statistics.py"
    spec = importlib.util.spec_from_file_location("controlled_cluster_statistics", stats_path)
    stats = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stats)
    protocol = source["protocol"]
    writes = {w["memory_instance_id"]: w for w in data["constructions"]}
    indexed = {g: {} for g in ("baseline", "enhanced")}
    for row in rows:
        key = (row["memory_id"], row["question_id"], row["repeat"])
        group = row["group"]
        if group not in indexed or key in indexed[group]:
            raise ValueError("Invalid or duplicate controlled trial")
        if row["arm"] != settings["group_labels"][group] or row["budget_tokens"] != budget:
            raise ValueError("Arm identity or token budget changed")
        if row["memory_tokens"] > budget or not row["bank_frozen"]:
            raise ValueError("Memory budget exceeded or bank mutated")
        correct = row["correct"]
        if type(correct) is not bool or correct != row["semantic_correct"]:
            raise ValueError("Semantic correctness labels differ")
        if row["status"] != "ok":
            if correct:
                raise ValueError("Failed questions must remain incorrect in the denominator")
        else:
            if not row["history_isolated"] or not row["memory_in_model_prompt"]:
                raise ValueError("Unverified isolated history or injection")
            label = row["judge_label"]
            expected_key = digest({"question_id": row["question_id"], "question": row["query"],
                "gold_answer": row["gold_answer"], "question_type": row["question_type"],
                "abstention": row["abstention"], "answer": row["answer"],
                "judge_model": data["scoring"]["primary_judge_model"],
                "scorer_sha256": protocol["dependencies"]["scorer_sha256"], "parser_version": "strict-yes-no-v1"})
            if (label["judge_key"] != expected_key or row["judge_key"] != expected_key
                    or label["label"] != correct or label["status"] != "ok"
                    or label["response_sha256"] != hashlib.sha256(row["answer"].encode()).hexdigest()):
                raise ValueError("Semantic judge provenance does not match the response")
        indexed[group][key] = row
    keys = sorted(indexed["baseline"])
    if not keys or keys != sorted(indexed["enhanced"]):
        raise ValueError("Controlled comparison requires all paired questions, including failures")
    for key in keys:
        left, right = (indexed[g][key] for g in ("baseline", "enhanced"))
        if left["query"] != right["query"] or left["gold_answer"] != right["gold_answer"] or left["candidate_hash"] != right["candidate_hash"]:
            raise ValueError("Paired source memories or questions differ")
        if left["status"] == right["status"] == "ok" and left["nonmemory_prompt_sha256"] != right["nonmemory_prompt_sha256"]:
            raise ValueError("Non-memory prompt changed")
    groups = {}
    cluster_means = {}
    strata = {}
    for group, index in indexed.items():
        selected = list(index.values())
        clusters = defaultdict(list)
        for row in selected:
            clusters[row["memory_id"]].append(row["correct"])
            strata[row["memory_id"]] = "abstention" if row["abstention"] else row["question_type"]
        ids = sorted(clusters)
        cluster_means[group] = [statistics.mean(clusters[k]) for k in ids]
        ci = stats.cluster_interval(cluster_means[group], strata=[strata[k] for k in ids],
                                    resamples=protocol["bootstrap_resamples"], seed=protocol["bootstrap_seed"])
        acquired = [writes[k] for k in sorted({r["memory_instance_id"] for r in selected})]
        optional_sum = lambda values: sum(values) if all(v is not None for v in values) else None
        query_tokens = optional_sum([r["total_tokens"] for r in selected])
        seed_tokens = optional_sum([w["total_tokens"] for w in acquired])
        total = query_tokens + seed_tokens if query_tokens is not None and seed_tokens is not None else None
        recall = [r["evidence_recall"] for r in selected if r["evidence_recall"] is not None]
        ncorrect = sum(r["correct"] for r in selected)
        groups[group] = {"n": len(selected), "correct": ncorrect, "accuracy": ci["estimate"],
            "accuracy_ci_low": ci["low"], "accuracy_ci_high": ci["high"],
            "evidence_recall": statistics.mean(recall) if recall else None,
            "query_tokens": query_tokens, "seed_tokens": seed_tokens, "all_tokens": total,
            "tokens_per_question": total / len(selected) if total is not None else None,
            "tokens_per_correct": total / ncorrect if total is not None and ncorrect else None,
            "seed_model_calls": sum(w["model_calls"] for w in acquired),
            "query_latency_ms": statistics.mean(r["latency_ms"] for r in selected),
            "end_to_end_latency_ms": None, "excluded_records": 0,
            "failed_records": sum(r["status"] != "ok" for r in selected), "memory_clusters": len(ids)}
        for metric in ("evidence_turn_recall_any_fragment", "annotated_evidence_character_coverage", "all_annotated_evidence_turns_complete"):
            values = [r[metric] for r in selected if r.get(metric) is not None]
            groups[group][metric] = statistics.mean(values) if values else None
        reported = data["groups"][group]
        if abs(reported["accuracy"]["estimate"] - ci["estimate"]) > 1e-10 or reported["n"] != len(selected):
            raise ValueError("Reported summary disagrees with raw traces")
    comparison = dict(data["comparison"])
    if "p_two_sided" in comparison:
        diffs = [a-b for a,b in zip(cluster_means["enhanced"], cluster_means["baseline"])]
        ci = stats.cluster_interval(diffs, strata=[strata[k] for k in sorted(strata)],
                                    resamples=protocol["bootstrap_resamples"], seed=protocol["bootstrap_seed"])
        p = stats.paired_permutation(diffs, resamples=protocol["bootstrap_resamples"], seed=protocol["bootstrap_seed"])
        if any(abs(comparison[k]-ci[k]) > 1e-10 for k in ("estimate", "low", "high")) or abs(comparison["p_two_sided"]-p) > 1e-10:
            raise ValueError("Paired inference disagrees with raw memory clusters")
        family = data["comparison_family"]
        corrected = stats.holm_adjust({c["id"]: c["p_two_sided"] for c in family})
        if abs(comparison["p_holm"]-corrected[comparison["id"]]) > 1e-10:
            raise ValueError("Multiple-comparison correction differs from the declared family")
    result = {"id": evidence_id, "title": title, "kind": data["kind"], "model_name": settings["model_name"],
        "dataset_sha256": data["dataset_sha256"], "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "context_tokens": budget, "budget_unit": "tokens", "group_labels": settings["group_labels"],
        "unique_questions": len({k[1] for k in keys}), "paired_observations": len(keys),
        "repeats": len({k[2] for k in keys}), "groups": groups,
        "accuracy_interval": {"method": "stratified memory-cluster bootstrap", "confidence": .95,
                              "confidence_percent": 95, "interpretation": "Repeats averaged within each memory episode"},
        "accuracy_gain_pp": 100*(groups["enhanced"]["accuracy"]-groups["baseline"]["accuracy"]),
        "total_token_ratio": groups["enhanced"]["all_tokens"]/groups["baseline"]["all_tokens"] if groups["baseline"]["all_tokens"] and groups["enhanced"]["all_tokens"] is not None else None,
        "cost_per_correct_ratio": groups["enhanced"]["tokens_per_correct"]/groups["baseline"]["tokens_per_correct"] if groups["baseline"]["tokens_per_correct"] and groups["enhanced"]["tokens_per_correct"] is not None else None,
        "comparison": comparison, "protocol": protocol, "selection_rule": protocol["selection_rule"],
        "accuracy_difference_ci_low_pp": 100*comparison["low"] if "low" in comparison else None,
        "accuracy_difference_ci_high_pp": 100*comparison["high"] if "high" in comparison else None,
        "paired_p_two_sided": comparison.get("p_two_sided"), "paired_p_holm": comparison.get("p_holm"),
        "limitations": data["limitations"], "observed_cases": [], "paired_outcomes": {},
        "human_review_required": True}
    return result
