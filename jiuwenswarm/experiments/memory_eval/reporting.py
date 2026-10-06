"""Fail-closed reporting: semantic scores, paired clusters, and measured reuse."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import gzip
import json
from pathlib import Path
import statistics

from .data import read_json
from .scoring import judgment_key
from .statistics import cluster_interval, paired_permutation, holm_adjust


def annotate_and_audit(root, rows, manifest, *, verify_prompts):
    """Post-hoc gold annotations never enter the executed retrieval path."""
    from dataclasses import asdict
    from .data import HERE, episode_cache, evidence_metrics, load_source, micro_episodes, lifecycle_episodes, timestamp
    from jiuwenswarm.agents.harness.common.memory.controlled_retrieval import PinnedTokenizer, canonical_hash, WRAPPER_START, WRAPPER_END
    protocol = manifest["protocol"]
    tokenizer = PinnedTokenizer(HERE / "data/public/qwen3_tokenizer/tokenizer.json", protocol["dependencies"]["tokenizer_files"]["tokenizer.json"])
    examples = {r["question_id"]: r for r in load_source(HERE / "data/public/longmemeval_s_cleaned.json")}
    micro = {e["memory_id"]: e for e in micro_episodes(HERE / "data/longmemeval_s_turn20_v1.json")}
    reuse = {e["memory_id"]: e for e in lifecycle_episodes(HERE / "data/memory_agent_qa_v2.json", count=manifest["execution"]["lifecycle_episodes"])}
    episodes, bank_hashes, prompt_cache = {}, {}, {}
    for row in rows:
        suite = row["suite"]
        memory_id = row["memory_id"]
        if suite in ("full", "retrieval"):
            if memory_id not in episodes:
                episodes[memory_id] = episode_cache(examples[memory_id], tokenizer,
                    HERE / "data/public/memory_eval_v2_cache", chunk_tokens=protocol["chunk_body_tokens"])
                original = examples[memory_id]
                converted = episodes[memory_id]
                cursor = 0
                for sid, date, turns in zip(original["haystack_session_ids"], original["haystack_dates"], original["haystack_sessions"], strict=True):
                    for index, turn in enumerate(turns):
                        # Session IDs can repeat at different dates in the
                        # original filler corpus. Validate source order rather
                        # than collapsing them into a session-ID dictionary.
                        position = 0
                        while position < len(turn["content"]):
                            if cursor >= len(converted["records"]):
                                raise ValueError("The converted history loses source text")
                            part = converted["records"][cursor]
                            if (part.session_id != sid or part.turn_index != index or part.date != date
                                    or part.timestamp != timestamp(date) or part.role != turn["role"]):
                                raise ValueError("Cached source metadata or ordering changed")
                            if part.start != position or part.end <= position or part.content != turn["content"][part.start:part.end]:
                                raise ValueError("Cached source spans overlap, omit or change text")
                            position = part.end
                            cursor += 1
                        if position != len(turn["content"]):
                            raise ValueError("The converted history loses source text")
                if cursor != len(converted["records"]):
                    raise ValueError("Extra source records appeared in the cache")
                q = converted["questions"][0]
                if q["query"] != original["question"] or q["answer"] != str(original["answer"]) or q["question_date"] != original["question_date"]:
                    raise ValueError("Cached original question, gold answer or date changed")
            episode = episodes[memory_id]
        else:
            episode = micro[memory_id] if suite == "micro" else reuse[memory_id]
        bank_key = (suite, memory_id)
        if bank_key not in bank_hashes:
            bank_hashes[bank_key] = canonical_hash([asdict(record) for record in episode["records"]])
        if row["candidate_hash"] != bank_hashes[bank_key]:
            raise ValueError("Recorded candidate bank differs from the pinned original source")
        question = next(q for q in episode["questions"] if q["id"] == row["question_id"])
        if verify_prompts and (row["query"] != question["query"] or row["gold_answer"] != question["answer"]):
            raise ValueError("Recorded question or scoring gold differs from the source")
        by_id = {record.item_id: record for record in episode["records"]}
        if len(row["selected_ids"]) != len(set(row["selected_ids"])) or any(i not in by_id for i in row["selected_ids"]):
            raise ValueError("Selected memory IDs are missing or duplicated")
        metrics = evidence_metrics(episode, question, row["selected_ids"])
        if any(row[k] != metrics[k] for k in ("evidence_recall", "all_evidence", "any_evidence")):
            raise ValueError("Evidence metric disagrees with source annotations")
        if suite in ("full", "retrieval") and not row["abstention"]:
            required = {tuple(pair) for pair in episode["evidence_turns"]}
            lengths = defaultdict(int)
            selected_chars = defaultdict(int)
            selected_ids = set(row["selected_ids"])
            for record in episode["records"]:
                turn = (record.session_id, record.turn_index)
                if turn in required:
                    lengths[turn] += record.end - record.start
                    if record.item_id in selected_ids:
                        selected_chars[turn] += record.end - record.start
            row["evidence_turn_recall_any_fragment"] = (sum(selected_chars[t] > 0 for t in required) / len(required)) if required else None
            row["annotated_evidence_character_coverage"] = sum(selected_chars.values()) / sum(lengths.values()) if sum(lengths.values()) else None
            row["all_annotated_evidence_turns_complete"] = all(selected_chars[t] == lengths[t] for t in required) if required else None
        else:
            row.update(evidence_turn_recall_any_fragment=None, annotated_evidence_character_coverage=None,
                       all_annotated_evidence_turns_complete=None)
        if verify_prompts and row["status"] == "ok":
            reference = row["prompt"]
            if reference["sha256"] not in prompt_cache:
                path = (root / reference["path"]).resolve()
                if not path.is_relative_to(root.resolve()):
                    raise ValueError("Prompt artifact escapes experiment directory")
                payload = json.loads(gzip.decompress(path.read_bytes()))
                if canonical_hash(payload) != reference["sha256"]:
                    raise ValueError("Prompt artifact hash changed")
                prompt_cache[reference["sha256"]] = payload
            payload = prompt_cache[reference["sha256"]]
            if any(m["role"] not in ("system", "user") for m in payload):
                raise ValueError("An ordinary assistant/tool history leaked into the formal question")
            context = WRAPPER_START + "\n\n".join(by_id[i].render(row["representation"]) for i in row["selected_ids"]) + WRAPPER_END if row["selected_ids"] else ""
            # Empty banks still have the common wrapper; match pack's convention.
            if not context:
                context = WRAPPER_START + WRAPPER_END
            if not any(context in m["content"] for m in payload if m["role"] == "system"):
                raise ValueError("Selected source records differ from actual model memory prompt")
            if tokenizer.count(context) != row["memory_tokens"] or row["memory_tokens"] > row["budget_tokens"]:
                raise ValueError("Recorded memory token count differs from actual prompt")
            if [m["content"] for m in payload if m["role"] == "user"] != [f"Question date: {question['question_date']}\nQuestion: {question['query']}"]:
                raise ValueError("Ordinary history leaked into the saved prompt")
    return {"source_banks_verified": len(bank_hashes), "unique_prompt_artifacts_verified": len(prompt_cache),
            "turn_annotations_posthoc_only": True}


def records(root: Path, name: str, key: str | None = None):
    path = root / f"{name}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
    return list({row[key]: row for row in rows}.values()) if key else rows


def token_sum(rows):
    known = sum(row.get("known_total_tokens", row.get("total_tokens") or 0) for row in rows)
    return {"known_tokens": known,
            "tokens": known if all(row.get("total_tokens") is not None for row in rows) else None,
            "unknown_usage_records": sum(row.get("total_tokens") is None for row in rows)}


def cluster_values(rows, metric):
    clusters = defaultdict(list)
    strata = {}
    for row in rows:
        value = row.get(metric)
        if value is not None:
            clusters[row["memory_id"]].append(float(value))
            strata[row["memory_id"]] = "abstention" if row["abstention"] else row["question_type"]
    keys = sorted(clusters)
    return keys, [statistics.mean(clusters[key]) for key in keys], [strata[key] for key in keys]


def interval(rows, metric, protocol):
    _, values, strata = cluster_values(rows, metric)
    return (cluster_interval(values, strata=strata, resamples=protocol["bootstrap_resamples"],
                             seed=protocol["bootstrap_seed"]) if values else None)


def paired_comparison(rows, left, right, protocol):
    a = [row for row in rows if row["arm"] == left]
    b = [row for row in rows if row["arm"] == right]
    key = lambda r: (r["memory_id"], r["question_id"], r["repeat"])
    if {key(r) for r in a} != {key(r) for r in b}:
        raise ValueError("Comparison requires the same questions and repeated runs")
    keys, av, strata = cluster_values(a, "semantic_correct")
    bkeys, bv, _ = cluster_values(b, "semantic_correct")
    if keys != bkeys:
        raise ValueError("Comparison memory clusters differ")
    differences = [x - y for x, y in zip(av, bv)]
    result = cluster_interval(differences, strata=strata,
                              resamples=protocol["bootstrap_resamples"], seed=protocol["bootstrap_seed"])
    result.update(left=left, right=right,
                  p_two_sided=paired_permutation(differences, resamples=protocol["bootstrap_resamples"],
                                                seed=protocol["bootstrap_seed"]))
    return result


def validate_fairness(trials):
    pairs = defaultdict(list)
    for row in trials:
        if row["status"] == "ok":
            if not row["history_isolated"] or not row["memory_in_model_prompt"] or not row["bank_frozen"]:
                raise ValueError("Invalid history isolation, injection, or frozen bank")
            if row["memory_tokens"] > row["budget_tokens"]:
                raise ValueError("Memory token cap exceeded")
            pairs[(row["suite"], row["memory_id"], row["question_id"], row["repeat"], row["budget_tokens"])].append(row)
    for key, rows in pairs.items():
        if len({row["candidate_hash"] for row in rows}) != 1:
            raise ValueError(f"Unequal candidate banks: {key}")
        if len({row.get("nonmemory_prompt_sha256") for row in rows}) != 1 or not rows[0].get("nonmemory_prompt_sha256"):
            raise ValueError(f"Unequal non-memory prompts: {key}")
        if key[0] == "full" and len({row["representation_hash"] for row in rows}) != 1:
            raise ValueError("Selection comparison changed representation")
        raw = {row["arm"]: row for row in rows}
        if key[0] == "full" and "jaccard" in raw and "hybrid_no_time" in raw:
            if raw["jaccard"]["selected_ids"] != raw["hybrid_no_time"]["selected_ids"]:
                raise ValueError("Fixed-frequency/importance no-time sanity control changed lexical selection")
        if "hybrid_raw" in raw and "hybrid_model_ack" in raw:
            if raw["hybrid_raw"]["prompt"]["sha256"] != raw["hybrid_model_ack"]["prompt"]["sha256"]:
                raise ValueError("Write-path control changed the final solver prompt")
    return {"valid_paired_inputs": len(pairs), "candidate_banks_equal": True,
            "nonmemory_prompts_equal": True, "token_caps_satisfied": True,
            "write_control_solver_prompts_identical": True}


def expected_trials(manifest):
    e = manifest["execution"]
    cap = e["max_episodes"]
    sizes = {"full": len(manifest["protocol"]["question_ids"]), "micro": 20,
             "reuse": e["lifecycle_episodes"]}
    arms = {"full": ["prefix", "recency", "jaccard", "bm25", "hybrid", "hybrid_no_time"],
            "micro": ["hybrid_raw", "hybrid_exchange", "hybrid_model_ack"],
            "reuse": ["hybrid_raw", "hybrid_model_ack", "bm25_raw"]}
    suites = list(sizes) if e["suite"] == "all" else [e["suite"]]
    result = {}
    for suite in suites:
        n = min(sizes[suite], cap) if cap else sizes[suite]
        selected = [a for a in arms[suite] if not e["selectors"] or a in e["selectors"]]
        result[suite] = n * e["repeats"] * len(selected) * (20 if suite == "reuse" else len(e["budgets"]))
    return result


def group_summary(rows, constructions, protocol):
    instances = {row["memory_instance_id"] for row in rows}
    writes = [constructions[key] for key in sorted(instances)]
    queries = token_sum(rows)
    writing = token_sum(writes)
    total = None if queries["tokens"] is None or writing["tokens"] is None else queries["tokens"] + writing["tokens"]
    correct = sum(row["semantic_correct"] for row in rows)
    return {"n": len(rows), "correct": correct,
            "accuracy": interval(rows, "semantic_correct", protocol),
            "literal_accuracy_diagnostic": statistics.mean(row.get("literal_correct", False) for row in rows),
            "evidence_session_or_item_recall": interval(rows, "evidence_recall", protocol),
            "all_evidence_session_or_item_hit": interval(rows, "all_evidence", protocol),
            "evidence_turn_recall_any_fragment": interval(rows, "evidence_turn_recall_any_fragment", protocol),
            "annotated_evidence_character_coverage": interval(rows, "annotated_evidence_character_coverage", protocol),
            "all_annotated_evidence_turns_complete": interval(rows, "all_annotated_evidence_turns_complete", protocol),
            "errors": sum(row["status"] != "ok" for row in rows),
            "correct_without_any_annotated_evidence": sum(row["semantic_correct"] and row["evidence_recall"] == 0 for row in rows),
            "wrong_despite_all_annotated_sessions_or_items": sum(not row["semantic_correct"] and row["all_evidence"] is True for row in rows),
            "memory_tokens_mean": statistics.mean(row["memory_tokens"] for row in rows),
            "query_cost": queries, "write_cost": writing, "total_tokens": total,
            "total_tokens_per_question": total / len(rows) if total is not None else None,
            "tokens_per_correct": total / correct if total is not None and correct else None,
            "query_latency_ms_mean": statistics.mean(row["latency_ms"] for row in rows),
            "ranking_latency_ms_mean": statistics.mean(row["ranking_latency_ms"] for row in rows),
            "write_latency_ms": sum(row["latency_ms"] for row in writes),
            "memory_instances": len(instances)}


def measured_reuse(rows, constructions, protocol):
    result = []
    arms = sorted({r["arm"] for r in rows})
    for arm in arms:
        for count in (1, 5, 10, 20):
            chosen = [r for r in rows if r["arm"] == arm and r["query_index"] < count]
            if not chosen:
                continue
            per_instance = defaultdict(list)
            for row in chosen:
                per_instance[row["memory_instance_id"]].append(row)
            bank_costs = defaultdict(list)
            bank_known_costs = defaultdict(list)
            unknown_instances = 0
            for instance, queries in per_instance.items():
                if len(queries) != count or len({r["question_id"] for r in queries}) != count:
                    raise ValueError("Reuse must contain actual distinct query prefixes")
                qcost = token_sum(queries)["tokens"]
                wcost = constructions[instance]["total_tokens"]
                bank = queries[0]["memory_id"]
                bank_known_costs[bank].append((constructions[instance]["known_total_tokens"] + token_sum(queries)["known_tokens"]) / count)
                if qcost is None or wcost is None:
                    unknown_instances += 1
                else:
                    bank_costs[bank].append((wcost + qcost) / count)
            values = [statistics.mean(bank_costs[k]) for k in sorted(bank_costs)]
            known_values = [statistics.mean(bank_known_costs[k]) for k in sorted(bank_known_costs)]
            result.append({"arm": arm, "distinct_queries": count,
                           "amortized_tokens_per_query": (cluster_interval(values,
                               resamples=protocol["bootstrap_resamples"], seed=protocol["bootstrap_seed"]) if not unknown_instances else None),
                           "known_tokens_per_query_lower_bound": cluster_interval(known_values,
                               resamples=protocol["bootstrap_resamples"], seed=protocol["bootstrap_seed"]),
                           "instances_with_unknown_usage": unknown_instances,
                           "accuracy": interval(chosen, "semantic_correct", protocol),
                           "actual_query_generations": len(chosen),
                           "write_once_instances": len(per_instance)})
    return result


def judge_sensitivity(rows):
    """Descriptive sensitivity on audited answers; not a complete second score."""
    audited = [r for r in rows if type(r.get("secondary_semantic_correct")) is bool]
    disputed = [r for r in audited if r["secondary_semantic_correct"] != r["semantic_correct"]]
    n = len(rows)
    return {"primary_accuracy": sum(r["semantic_correct"] for r in rows) / n,
            "audited_substitution_accuracy": sum(r.get("secondary_semantic_correct") if type(r.get("secondary_semantic_correct")) is bool else r["semantic_correct"] for r in rows) / n,
            "known_disagreement_lower": sum(r["semantic_correct"] and r not in disputed for r in rows) / n,
            "known_disagreement_upper": sum(r["semantic_correct"] or r in disputed for r in rows) / n,
            "audited_generations": len(audited), "disputed_generations": len(disputed),
            "unaudited_generations": n - len(audited),
            "scope": "Hold all unaudited primary labels fixed; substitute only the predeclared audited labels. Bounds vary only known primary/secondary disagreements. Descriptive, not a full independent judge evaluation, confidence interval or bound on all grading errors."}


def build_report(root: Path):
    manifest = read_json(root / "run_manifest.json")
    if manifest["kind"] != "memory_eval_v2_live":
        raise ValueError("Self-tests and retrieval-only traces are not QA performance evidence")
    protocol = manifest["protocol"]
    scoring = read_json(root / "scoring/scoring_manifest.json")
    trials = records(root, "trials", "trial_id")
    expected = expected_trials(manifest)
    observed = {suite: sum(r["suite"] == suite for r in trials) for suite in expected}
    if observed != expected:
        raise ValueError(f"Incomplete solver experiment: expected {expected}; observed {observed}")
    if any(not 0 <= r["repeat"] < manifest["execution"]["repeats"] for r in trials):
        raise ValueError("Repeated run identity is outside the frozen protocol")
    if "full" in expected:
        planned_ids = protocol["question_ids"][:manifest["execution"]["max_episodes"]] if manifest["execution"]["max_episodes"] else protocol["question_ids"]
        expected_keys = {(q, repeat) for q in planned_ids for repeat in range(manifest["execution"]["repeats"])}
        for arm in manifest["execution"]["selectors"] or protocol["selectors"]:
            for budget in manifest["execution"]["budgets"]:
                actual = {(r["question_id"], r["repeat"]) for r in trials if r["suite"] == "full" and r["arm"] == arm and r["budget_tokens"] == budget}
                if actual != expected_keys:
                    raise ValueError("Full QA question IDs or repeats differ from the predeclared set")
    if scoring["valid_solver_trials"] != sum(r["status"] == "ok" for r in trials):
        raise ValueError("Semantic scoring manifest is stale")
    source_audit = annotate_and_audit(root, trials, manifest, verify_prompts=True)
    labels = {r["judge_key"]: r for r in records(root, "labels", "judge_key")}
    constructions = {r["memory_instance_id"]: r for r in records(root, "constructions", "memory_instance_id")}
    calls = records(root, "calls")
    write_calls = defaultdict(list)
    for call in calls:
        if call["phase"] == "write":
            write_calls[call["memory_instance_id"]].append(call)
    for instance, construction in constructions.items():
        actual = write_calls[instance]
        known_tokens = sum(c["usage"]["total_tokens"] for c in actual if c.get("usage"))
        if construction["model_calls"] != len(actual) or construction["known_total_tokens"] != known_tokens:
            raise ValueError("Acquisition accounting differs from recorded calls; reconcile interrupted writes before reporting lifecycle cost")
    for row in trials:
        if row["memory_instance_id"] not in constructions:
            raise ValueError("Missing memory acquisition trace")
        row["semantic_correct"] = False
        if row["status"] == "ok":
            key = judgment_key(row, scoring["primary_judge_model"], protocol["dependencies"]["scorer_sha256"])
            label = labels.get(key)
            if not label or label["status"] != "ok":
                raise ValueError(f"Missing semantic label: {row['trial_id']}")
            row["semantic_correct"] = label["label"]
            row["judge_key"] = key
            row["judge_label"] = label
            if scoring.get("secondary_judge_model"):
                secondary_key = judgment_key(row, scoring["secondary_judge_model"], protocol["dependencies"]["scorer_sha256"])
                secondary = labels.get(secondary_key)
                if secondary and secondary["status"] == "ok":
                    if secondary["response_sha256"] != hashlib.sha256(row["answer"].encode()).hexdigest():
                        raise ValueError("Secondary judge label refers to a changed response")
                    row["secondary_semantic_correct"] = secondary["label"]
                    row["secondary_judge_label"] = secondary
        else:
            # All attempted questions stay in the denominator. Retrieval metrics
            # describe successful delivery rather than an offline hypothetical.
            if row["evidence_recall"] is not None:
                row.update(evidence_recall=0.0, all_evidence=False, any_evidence=False)
            for metric in ("evidence_turn_recall_any_fragment", "annotated_evidence_character_coverage", "all_annotated_evidence_turns_complete"):
                if row[metric] is not None:
                    row[metric] = 0.0
    fairness = validate_fairness(trials)
    fairness.update(source_audit)
    groups, comparisons, categories, sensitivities = [], [], [], []
    for suite in expected:
        budgets = sorted({r["budget_tokens"] for r in trials if r["suite"] == suite})
        for budget in budgets:
            rows = [r for r in trials if r["suite"] == suite and r["budget_tokens"] == budget]
            for arm in sorted({r["arm"] for r in rows}):
                subset = [r for r in rows if r["arm"] == arm]
                groups.append({"suite": suite, "budget_tokens": budget, "arm": arm,
                               **group_summary(subset, constructions, protocol)})
                sensitivities.append({"suite": suite, "budget_tokens": budget, "arm": arm,
                                      **judge_sensitivity(subset)})
                if suite == "full":
                    for category in sorted({"abstention" if r["abstention"] else r["question_type"] for r in subset}):
                        cells = [r for r in subset if ("abstention" if r["abstention"] else r["question_type"]) == category]
                        categories.append({"arm": arm, "budget_tokens": budget, "category": category,
                                           "accuracy": interval(cells, "semantic_correct", protocol)})
            planned = ([(a, "bm25") for a in ("prefix", "recency", "jaccard", "hybrid")] + [("hybrid", "hybrid_no_time")]
                       if suite == "full" else
                       [("hybrid_exchange", "hybrid_raw"), ("hybrid_model_ack", "hybrid_raw")] if suite == "micro" else [])
            present = {r["arm"] for r in rows}
            for left, right in planned:
                if left in present and right in present:
                    comparisons.append({"id": f"{suite}:{budget}:{left}-{right}", "suite": suite,
                                        "budget_tokens": budget, **paired_comparison(rows, left, right, protocol)})
    adjusted = holm_adjust({c["id"]: c["p_two_sided"] for c in comparisons})
    for c in comparisons:
        c["p_holm"] = adjusted[c["id"]]
        c["primary"] = c["suite"] == "full" and (c["left"], c["right"]) == ("hybrid", "bm25")
    known = [c["usage"]["total_tokens"] for c in calls if c.get("usage")]
    input_offsets = [c["usage"]["input_tokens"] - c["full_prompt_content_tokens"] for c in calls if c.get("usage")]
    summary = {
        "kind": "controlled_memory_eval_live", "protocol_version": protocol["protocol_version"],
        "expected_trials": expected, "observed_trials": observed, "fairness": fairness,
        "source_manifest": manifest, "scoring": scoring,
        "groups": groups, "comparisons": comparisons, "category_results": categories,
        "judge_sensitivity": sensitivities,
        "reuse": measured_reuse([r for r in trials if r["suite"] == "reuse"], constructions, protocol),
        "accounting": {"solver_attempts": len(calls), "failed_attempts": sum(c["status"] != "ok" for c in calls),
                       "write_instances_reconciled_with_call_ledger": len(constructions),
                       "known_solver_tokens": sum(known), "unknown_usage_attempts": len(calls) - len(known),
                       "reported_input_minus_local_content_tokens_min": min(input_offsets) if input_offsets else None,
                       "reported_input_minus_local_content_tokens_max": max(input_offsets) if input_offsets else None,
                       "queue_wait_ms_total": sum(c.get("queue_wait_ms", 0) for c in calls),
                       "evaluation_attempts": len(records(root, "judge_calls")),
                       "evaluation_tokens_not_deployment_cost": sum(c["usage"]["total_tokens"] for c in records(root, "judge_calls") if c.get("usage"))},
        "inference": "Mean of repeated generations per memory, then stratified memory-cluster bootstrap; paired cluster sign-flip test; Holm correction over all prespecified full/micro comparisons.",
        "latency_scope": "Query wall clock includes Agent invocation, rate-gate queue waiting and memory packing; excludes source chunking, index creation, precomputed ranking and artifact writes. Call-level service latency excludes queue_wait_ms; rankings and index creation have separate traces. Do not claim total preprocessing or unthrottled production speed.",
        "retrieval_metric_scope": "Full histories: evidence-session hits and annotated-turn recall (any selected fragment), plus fraction of source characters in annotated turns delivered and complete annotated-turn coverage. None is a semantic proof that every answer fact was delivered. Gold annotations enter reporting only. Abstentions excluded from retrieval metrics. Micro/reuse: required fact-item recall.",
        "human_review_required": True, "official_longmemeval_score": False,
        "limitations": protocol["protocol_deviations"] + [
            "Synthetic reuse banks share templates; eight entity/value variants do not establish generality on independent natural memory workloads.",
            "Representation and model-ACK controls use the adapted 20-item workload; they are mechanism controls, not full-history benchmark results.",
            "Representation ablation keeps the selector algorithm fixed; changed exchange formatting can affect both lexical features and token packing, so it does not isolate packing alone.",
            "Construction control canonicalizes identical source facts after real ACK writes; it measures acquisition overhead, not learned summarization quality.",
            "Three temperature-zero calls measure operational repeatability, not variation across model families.",
            "Blinded primary/secondary judge audit requires human adjudication before final paper submission.",
            "The hybrid selector is an existing lexical/time heuristic; no new retrieval algorithm is claimed."]}
    summary["limitations"].append("This evaluates a memory question-answering component, not the quality of automatically generated research papers; a new manuscript and reviewer evaluation are required to measure any paper-score change.")
    return summary, trials, constructions


def retrieval_report(root: Path):
    manifest = read_json(root / "run_manifest.json")
    if manifest["kind"] != "memory_eval_v2_retrieval":
        raise ValueError("Expected retrieval-only evidence")
    rows = records(root, "trials", "trial_id")
    e = manifest["execution"]
    count = e["max_episodes"] or 500
    expected = count * len(e["selectors"] or manifest["protocol"]["selectors"]) * len(e["budgets"])
    if len(rows) != expected:
        raise ValueError(f"Incomplete retrieval sweep: {len(rows)}/{expected}")
    audit = annotate_and_audit(root, rows, manifest, verify_prompts=False)
    groups = []
    for budget in e["budgets"]:
        for arm in e["selectors"] or manifest["protocol"]["selectors"]:
            selected = [r for r in rows if r["budget_tokens"] == budget and r["arm"] == arm]
            if len({r["memory_id"] for r in selected}) != count:
                raise ValueError("Retrieval coverage differs across arms")
            if any(r["memory_tokens"] > budget for r in selected):
                raise ValueError("Retrieval token cap exceeded")
            groups.append({"arm": arm, "budget_tokens": budget, "n_histories": count,
                           "eligible_non_abstention": sum(not r["abstention"] for r in selected),
                           "evidence_session_recall": interval(selected, "evidence_recall", manifest["protocol"]),
                           "all_evidence_session_hit": interval(selected, "all_evidence", manifest["protocol"]),
                           "evidence_turn_recall_any_fragment": interval(selected, "evidence_turn_recall_any_fragment", manifest["protocol"]),
                           "annotated_evidence_character_coverage": interval(selected, "annotated_evidence_character_coverage", manifest["protocol"]),
                           "all_annotated_evidence_turns_complete": interval(selected, "all_annotated_evidence_turns_complete", manifest["protocol"])})
    return {"kind": "controlled_memory_retrieval_only", "groups": groups,
            "n_trials": len(rows), "source_manifest": manifest, "source_audit": audit,
            "not_answer_accuracy": True, "official_longmemeval_score": False}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def export_pairs(destination, summary, trials, constructions):
    """Self-contained traces for paper owners; exact selector names survive."""
    from .data import HERE
    dataset_hashes = {"full": summary["source_manifest"]["protocol"]["source_sha256"]}
    for suite, name in (("micro", "longmemeval_s_turn20_v1.json"), ("reuse", "memory_agent_qa_v2.json")):
        dataset_hashes[suite] = hashlib.sha256((HERE / "data" / name).read_bytes()).hexdigest()
    paths = []
    comparisons = list(summary["comparisons"])
    reuse = [r for r in trials if r["suite"] == "reuse"]
    if reuse:
        comparisons.append({"id": "reuse:512:hybrid_model_ack-hybrid_raw", "suite": "reuse",
                            "budget_tokens": reuse[0]["budget_tokens"], "left": "hybrid_model_ack", "right": "hybrid_raw",
                            "inference_scope": "Measured cost after 20 distinct questions; QA summary is descriptive, outside the full/micro accuracy test family."})
    for comparison in comparisons:
        rows = [r for r in trials if r["suite"] == comparison["suite"] and r["budget_tokens"] == comparison["budget_tokens"]
                and r["arm"] in (comparison["left"], comparison["right"])]
        instances = {r["memory_instance_id"] for r in rows}
        groups = {g["arm"]: g for g in summary["groups"] if g["suite"] == comparison["suite"] and g["budget_tokens"] == comparison["budget_tokens"]}
        value = {"kind": "controlled_memory_eval_live", "settings": {
                    "model_name": summary["source_manifest"]["model_name"], "budget_unit": "tokens",
                    "context_tokens": comparison["budget_tokens"], "repeats": summary["source_manifest"]["execution"]["repeats"],
                    "group_labels": {"baseline": comparison["right"], "enhanced": comparison["left"]}},
                 "dataset_sha256": dataset_hashes[comparison["suite"]],
                 "comparison": comparison, "groups": {"baseline": groups[comparison["right"]], "enhanced": groups[comparison["left"]]},
                 "records": [{**r, "group": "baseline" if r["arm"] == comparison["right"] else "enhanced",
                              "correct": r["semantic_correct"]} for r in rows],
                 "constructions": [constructions[k] for k in sorted(instances)],
                 "scoring": summary["scoring"], "limitations": summary["limitations"] + [summary["retrieval_metric_scope"], summary["latency_scope"]],
                 "source_manifest": summary["source_manifest"],
                 "comparison_family": summary["comparisons"],
                 "official_longmemeval_score": False, "human_review_required": True}
        filename = comparison["id"].replace(":", "_") + ".json"
        write_json(destination / filename, value)
        paths.append({"path": filename, "sha256": hashlib.sha256((destination / filename).read_bytes()).hexdigest()})
    write_json(destination / "manifest.json", {"kind": "controlled_memory_eval_paper_exports", "files": paths})


def figures_and_tables(destination, summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    groups = [g for g in summary["groups"] if g["suite"] == "full"]
    if groups:
        budgets = sorted({g["budget_tokens"] for g in groups})
        arms = [a for a in ("prefix", "recency", "jaccard", "bm25", "hybrid", "hybrid_no_time") if any(g["arm"] == a for g in groups)]
        fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
        for ax, metric, label in zip(axes, ("accuracy", "all_evidence_session_or_item_hit"), ("Semantic answer accuracy", "All evidence sessions hit")):
            for arm in arms:
                cells = [next(g for g in groups if g["arm"] == arm and g["budget_tokens"] == b) for b in budgets]
                estimates = [c[metric]["estimate"] for c in cells]
                ax.errorbar(budgets, estimates, yerr=[[c[metric]["estimate"]-c[metric]["low"] for c in cells],
                                                       [c[metric]["high"]-c[metric]["estimate"] for c in cells]], marker="o", capsize=3, label=arm)
            ax.set(xlabel="Memory budget (pinned Qwen3 tokens)", ylabel=label, ylim=(-0.02, 1.02), xticks=budgets)
            ax.grid(alpha=.2)
        axes[0].legend(fontsize=8)
        for extension in ("png", "svg", "pdf"):
            fig.savefig(destination / f"fair_baselines.{extension}", dpi=180)
        plt.close(fig)
        budget = 1024 if 1024 in budgets else budgets[len(budgets)//2]
        cells = [c for c in summary["category_results"] if c["budget_tokens"] == budget]
        categories = sorted({c["category"] for c in cells})
        values = [[next(c["accuracy"]["estimate"] for c in cells if c["arm"] == arm and c["category"] == category)
                   for arm in arms] for category in categories]
        fig, ax = plt.subplots(figsize=(9, 4.5), constrained_layout=True)
        plot = ax.imshow(values, vmin=0, vmax=1, cmap="Blues", aspect="auto")
        ax.set_xticks(range(len(arms)), arms, rotation=20, ha="right")
        ax.set_yticks(range(len(categories)), categories)
        ax.set_title(f"Semantic accuracy by question category; {budget} token memory cap", fontsize=11)
        for i, row in enumerate(values):
            for j, value in enumerate(row):
                ax.text(j, i, f"{100*value:.1f}%", ha="center", va="center",
                        color="white" if value > .55 else "#111111", fontsize=9)
        fig.colorbar(plot, ax=ax, label="Semantic accuracy")
        for extension in ("png", "svg", "pdf"):
            fig.savefig(destination / f"category_accuracy.{extension}", dpi=180)
        plt.close(fig)
    if summary["reuse"] and all(r["amortized_tokens_per_query"] is not None for r in summary["reuse"]):
        fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)
        for arm in sorted({r["arm"] for r in summary["reuse"]}):
            cells = [r for r in summary["reuse"] if r["arm"] == arm]
            ax.errorbar([c["distinct_queries"] for c in cells], [c["amortized_tokens_per_query"]["estimate"] for c in cells],
                        yerr=[[c["amortized_tokens_per_query"]["estimate"]-c["amortized_tokens_per_query"]["low"] for c in cells],
                              [c["amortized_tokens_per_query"]["high"]-c["amortized_tokens_per_query"]["estimate"] for c in cells]],
                        marker="o", capsize=3, label=arm)
        ax.set(xlabel="Actual distinct queries served by one memory bank", ylabel="Measured (write + query) tokens / query", xticks=[1,5,10,20])
        ax.legend(); ax.grid(alpha=.2)
        for extension in ("png", "svg", "pdf"):
            fig.savefig(destination / f"memory_reuse.{extension}", dpi=180)
        plt.close(fig)
    tex = [r"\begin{tabular}{llrrrr}", r"\toprule", r"Suite / selector & Budget & Accuracy (95\% CI) & Evidence hit & Tokens/query & Errors \\", r"\midrule"]
    for g in summary["groups"]:
        ci = g["accuracy"]
        accuracy = f"{100*ci['estimate']:.1f} [{100*ci['low']:.1f}, {100*ci['high']:.1f}]"
        evidence = g["all_evidence_session_or_item_hit"]
        hit = f"{100*evidence['estimate']:.1f}" if evidence else "--"
        cost = f"{g['total_tokens_per_question']:.0f}" if g["total_tokens_per_question"] is not None else "unknown"
        name = (g["suite"] + "/" + g["arm"]).replace("_", r"\_")
        tex.append(f"{name} & {g['budget_tokens']} & {accuracy} & {hit} & {cost} & {g['errors']} " + r"\\")
    tex.extend([r"\bottomrule", r"\end{tabular}"])
    (destination / "results_table.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")


def paper_sections(destination, summary, retrieval):
    """Trace-grounded experiment prose for paper owners, without new LLM calls."""
    method = r"""\subsection{Controlled Experimental Protocol}
We evaluate a fixed-hash stratified subset of LongMemEval-S cleaned: twelve non-abstention questions from each of six task categories and twelve abstention questions, for eighty-four memory episodes. All source sessions, user/assistant turns, timestamps, questions and gold answers are retained. Each turn is split losslessly into segments bounded by 256 pinned Qwen3 BPE tokens. Prefix, recency, Jaccard, BM25, existing hybrid and hybrid without time share the same frozen candidate bank, metadata, memory wrapper and whole-item first-fit overflow policy under 512, 1024 and 2048 memory tokens. BM25 uses $k_1=1.2$, $b=0.75$ and positive IDF. Removing time sums the remaining weighted terms directly, preserving lexical tie order. Frequency and importance are held fixed. These are controlled selectors, not a novel learned retrieval algorithm.

Real JiuwenSwarm/openJiuwen DeepAgents use \texttt{qwen-plus-2025-12-01}, temperature zero, disabled thinking, no tools and one answering iteration. Each formal question has an isolated conversation ID; the memory bank cannot change between queries. All attempted questions remain in the accuracy denominator. Three actual generations are averaged within each memory episode before stratified memory-cluster bootstrap inference (10,000 resamples; fixed seed). Paired cluster sign-flip tests use Holm correction across all prespecified full-history and micro accuracy comparisons. The primary comparison is hybrid versus BM25. A balanced subset score is not a naturally weighted score on all 500 benchmark questions.

The pinned original LongMemEval task-specific grading prompts are evaluated with \texttt{qwen3-max-2026-01-23}; strict yes/no parsing and arm-blind response keys replace substring grading. A second fixed model audits string/semantic disagreements and a deterministic ten-percent sample. Human adjudication remains pending. The substituted judge, subset sampling and segmented memory bank are disclosed deviations from official evaluation. Retrieval alone is additionally evaluated on all 500 histories, excluding thirty abstention cases from evidence recall. Evidence-session hits, annotated-turn hits by any selected fragment, annotated-character coverage and complete annotated-turn coverage are distinct metrics; none alone proves semantic delivery of every answer fact.

Separate micro controls use the adapted twenty-item workload: raw versus reconstructed ACK exchanges changes representation with the selector algorithm fixed, affecting both lexical features and packing; direct versus real EnhancedMemoryRail ACK acquisition is canonicalized to identical source records and solver prompts, isolating acquisition cost. Eight synthetic entity/value memory banks each serve twenty distinct queries in a frozen order; measured prefixes of one, five, ten and twenty queries amortize a single build, rather than extrapolating isolated queries. Every call attempt records actual input/output usage, retries and errors. Missing usage is unknown. Query wall time includes rate-gate waiting and excludes source chunking and offline index construction; it is not end-to-end production latency. The full-history frozen bank does not establish that the legacy twenty-entry L1 Rail supports all histories or production persistence.
"""
    (destination / "experimental_methods.tex").write_text(method, encoding="utf-8")
    paragraphs = [r"\subsection{Token-Matched Answer Quality}"]
    for c in summary["comparisons"]:
        if c["primary"]:
            paragraphs.append(f"At {c['budget_tokens']} memory tokens, hybrid minus BM25 accuracy is {100*c['estimate']:+.1f} percentage points (95\\% paired memory-cluster interval [{100*c['low']:+.1f}, {100*c['high']:+.1f}]; two-sided paired $p={c['p_two_sided']:.4f}$, Holm-adjusted $p={c['p_holm']:.4f}$).")
    paragraphs.append("These are measured differences for the fixed model and balanced question subset; budgets and repeated calls do not add independent memory episodes. Negative and inconclusive comparisons are retained. The associated full-history retrieval sweep contains " + str(retrieval["n_trials"]) + " selector/budget traces, not additional model answers.")
    paragraphs.append(r"\subsection{Isolating the Temporal Ranking Contribution}")
    for c in summary["comparisons"]:
        if c["suite"] == "full" and c["left"] == "hybrid" and c["right"] == "hybrid_no_time" and c["budget_tokens"] == 1024:
            paragraphs.append(f"At 1024 memory tokens, full hybrid minus the same selector with only time removed is {100*c['estimate']:+.1f} accuracy points (95\\% paired memory-cluster interval [{100*c['low']:+.1f}, {100*c['high']:+.1f}]; Holm-adjusted $p={c['p_holm']:.4f}$). Source records, lexical scoring, frequency, importance, representation and packing remain fixed. With constant frequency and importance, the no-time and Jaccard controls select identical items; separate actual generations can still produce different answers. This replay uses original source timestamps and the question date, rather than assigning a common new ingestion timestamp.")
    paragraphs.append(r"\subsection{Component Controls and Measured Reuse}")
    for c in summary["comparisons"]:
        if c["suite"] == "micro" and c["budget_tokens"] == 1024:
            left, right = (name.replace("_", r"\_") for name in (c["left"], c["right"]))
            paragraphs.append(f"The adapted micro control {left} minus {right} has accuracy difference {100*c['estimate']:+.1f} points (95\\% memory-cluster interval [{100*c['low']:+.1f}, {100*c['high']:+.1f}]; Holm-adjusted $p={c['p_holm']:.4f}$). These mechanism controls have twenty adapted episodes and do not establish full-history generality.")
    for arm in sorted({r["arm"] for r in summary["reuse"]}):
        cells = sorted((r for r in summary["reuse"] if r["arm"] == arm), key=lambda r: r["distinct_queries"])
        values = [f"{r['amortized_tokens_per_query']['estimate']:.0f}" if r["amortized_tokens_per_query"] is not None else "unknown" for r in cells]
        paragraphs.append(arm.replace("_", r"\_") + " uses " + ", ".join(values) + " measured write-plus-query tokens per question after serving one, five, ten and twenty distinct questions, respectively. Construction is counted once per memory instance; the banks share synthetic templates.")
    (destination / "experimental_results.tex").write_text("\n\n".join(paragraphs) + "\n", encoding="utf-8")
    write_json(destination / "judge_sensitivity.json", summary["judge_sensitivity"])
    lines = ["# 同学2实验交接：正式结果", "", "## 已验证", "",
             f"- QA记录：{sum(summary['observed_trials'].values())}；各suite：{summary['observed_trials']}。",
             f"- 全量检索记录：{retrieval['n_trials']}；500段历史，拒答题不进入证据召回分母。",
             f"- Solver调用尝试：{summary['accounting']['solver_attempts']}；失败尝试：{summary['accounting']['failed_attempts']}；已知tokens：{summary['accounting']['known_solver_tokens']}；usage未知尝试：{summary['accounting']['unknown_usage_attempts']}。",
             f"- 评分模型分歧：{summary['scoring']['judge_disagreements']} / {summary['scoring']['audit_questions']}个复核回答。人工decision仍待填写。",
             "", "## 主比较：hybrid 减 BM25", ""]
    for c in summary["comparisons"]:
        if c["primary"]:
            lines.append(f"- {c['budget_tokens']} tokens：准确率差{100*c['estimate']:+.1f}个百分点，95%区间[{100*c['low']:+.1f}, {100*c['high']:+.1f}]，Holm p={c['p_holm']:.4f}。")
    lines += ["", "## 使用方式", "",
              "- `summary.json`为全部统计依据；`paper_exports/`自包含配对原始回答、实际评分标签和写入日志。",
              "- `experimental_methods.tex`和`experimental_results.tex`可由同学3/4纳入论文；图表为真实运行记录生成，需由论文负责人安排版面。",
              "- `fair_baselines.pdf`、`memory_reuse.pdf`及`results_table.tex`供正文/附录使用；表格覆盖全部组，正文优先主比较，避免塞入全量长表。",
              "- `category_accuracy.pdf`按任务类别呈现1,024 Token下的结果；置信区间和类别样本数见`summary.json`。",
              "- 生成器使用`examples/memory-eval-v2.brief.json`及general renderer，不能套用旧L1字符预算 research profile。",
              "", "## 提交前仍要完成", "",
              "- 人工核对盲评队列的模型分歧和抽样回答，记录 reviewer/decision/notes。",
              "- 优先查看`model_disagreement_review.json`。`judge_sensitivity.json`只替换已复核回答，未复核标签保持主评分；该范围不是人工正确率或完整第二模型评分。",
              "- 将旧pilot的因果和优越性主张替换为新版公平比较，保留负结果及适用边界。",
              "- 论文负责人更新稿件、检查图表和引用并重新提交Reviewer；本实验未产生新的Reviewer评分，不能保证分数。",
              "", "## 适用边界", ""] + ["- " + line for line in summary["limitations"]]
    (destination / "EXPERIMENT_HANDOFF.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def mechanistic_cases(root, destination, trials):
    """Deterministic explanatory examples, not additional hypothesis tests."""
    rows = {(r["question_id"], r["arm"]): r for r in trials
            if r["suite"] == "full" and r["repeat"] == 0 and r["budget_tokens"] == 1024}
    cases = []
    for qid in sorted({key[0] for key in rows}):
        h, a = rows[(qid,"hybrid")], rows[(qid,"hybrid_no_time")]
        if h["abstention"] or h["all_evidence"] or not a["all_evidence"]:
            continue
        rank_ref = h["ranking"]
        ranking_bytes = gzip.decompress((root / rank_ref["path"]).read_bytes())
        if hashlib.sha256(ranking_bytes).hexdigest() != rank_ref["sha256"]:
            raise ValueError("Explanatory ranking artifact failed its recorded hash check")
        ranked = json.loads(ranking_bytes)["scores"]
        by_id = {r["item_id"]: {**r, "rank": i+1} for i,r in enumerate(ranked)}
        gained = [i for i in a["selected_ids"] if i not in h["selected_ids"]]
        cases.append({"question_id": qid, "question": h["query"], "gold_answer": h["gold_answer"],
            "hybrid_answer": h.get("answer"), "no_time_answer": a.get("answer"),
            "hybrid_semantic_correct": h["semantic_correct"], "no_time_semantic_correct": a["semantic_correct"],
            "hybrid_selected_scores": [by_id[i] for i in h["selected_ids"]],
            "items_selected_after_removing_time": [by_id[i] for i in gained],
            "candidate_hash": h["candidate_hash"], "source_ranking": rank_ref,
            "selection_rule": "First five lexicographic IDs at repeat zero / 1024 tokens where removing time restores all evidence-session hits. Exploratory examples; no further inference."})
        if len(cases) == 5:
            break
    write_json(destination / "mechanistic_cases.json", cases)
    explanation = r"""\subsection{Why a Fixed Freshness Weight Can Displace Relevant History}
In this replay protocol, memory timestamps are the original conversation timestamps and the reference clock is the question date. Frequency and importance are fixed, so pairwise order under the existing hybrid is determined by
\[
S_i = 0.4 J(q,m_i) + 0.3 D_i + C,
\]
where $J$ is lexical Jaccard similarity and $D$ is the implemented temporal decay. A relevant older record outranks a fresher record only if
\[
0.4(J_{\mathrm{old}}-J_{\mathrm{fresh}})
> 0.3(D_{\mathrm{fresh}}-D_{\mathrm{old}}).
\]
Thus a query-independent freshness gap can outweigh a positive lexical relevance gap. Removing only the temporal term tests this mechanism while preserving source content, representation and packing. This is an explanation of the existing score, not a novel retrieval algorithm or a tuned replacement. The saved explanatory cases use a disclosed deterministic example-selection rule; they do not add independent evidence to the paired statistical tests. Bulk ingestion that assigns all records a new timestamp is a different scenario and is not evaluated here.
"""
    (destination / "mechanistic_analysis.tex").write_text(explanation, encoding="utf-8")


def retrieval_figures(destination, retrieval):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    groups = retrieval["groups"]
    budgets = sorted({g["budget_tokens"] for g in groups})
    arms = [a for a in ("prefix", "recency", "jaccard", "bm25", "hybrid", "hybrid_no_time") if any(g["arm"] == a for g in groups)]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for ax, metric, label in zip(axes, ("evidence_turn_recall_any_fragment", "annotated_evidence_character_coverage"),
                                  ("Annotated-turn recall (any fragment)", "Annotated-turn character coverage")):
        for arm in arms:
            cells = [next(g for g in groups if g["arm"] == arm and g["budget_tokens"] == b) for b in budgets]
            ax.errorbar(budgets, [g[metric]["estimate"] for g in cells],
                        yerr=[[g[metric]["estimate"]-g[metric]["low"] for g in cells],
                              [g[metric]["high"]-g[metric]["estimate"] for g in cells]],
                        marker="o", linestyle="--" if arm == "hybrid_no_time" else "-", capsize=3, label=arm)
        ax.set(xlabel="Memory budget (pinned Qwen3 tokens)", ylabel=label, ylim=(-.02, 1.02), xticks=budgets)
        ax.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    fig.suptitle("500 complete histories; 470 non-abstention cases in retrieval metrics", fontsize=11)
    for suffix in ("png", "svg", "pdf"):
        fig.savefig(destination / f"full500_retrieval.{suffix}", dpi=180)
    plt.close(fig)


def protocol_diagram(destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    fig, ax = plt.subplots(figsize=(10, 3.6), constrained_layout=True)
    ax.set(xlim=(0,10), ylim=(0,3.6)); ax.axis("off")
    boxes = [(.3,2.15,"Complete public histories\n500 retrieval / 84 QA"),
             (3.7,2.15,"Frozen single-layer bank\nLossless turn segments"),
             (7.1,2.15,"Six selectors\nIdentical candidates"),
             (7.1,.75,"Common token packing\n512 / 1024 / 2048"),
             (3.7,.75,"Real DeepAgent\nFresh question conversation"),
             (.3,.75,"Blind judge + inference\nMemory-cluster statistics")]
    for x,y,label in boxes:
        ax.add_patch(FancyBboxPatch((x,y),2.6,.85, boxstyle="round,pad=.08", linewidth=1.2,
                                   facecolor="#EEF4FA", edgecolor="#335C81"))
        ax.text(x+1.3,y+.425,label,ha="center",va="center",fontsize=10)
    for start,end in (((3,2.575),(3.55,2.575)),((6.4,2.575),(6.95,2.575)),
                      ((8.4,2.05),(8.4,1.72)),((7,.1175+1.075),(6.45,1.1925)),
                      ((3.6,1.175),(3.05,1.175))):
        ax.add_patch(FancyArrowPatch(start,end,arrowstyle="-|>",mutation_scale=15,color="#335C81",linewidth=1.4))
    ax.text(5,3.4,"Controlled memory evaluation in JiuwenSwarm",ha="center",fontsize=13)
    ax.text(5,.2,"Micro: representation OR acquisition changed alone. Reuse: one build, 20 distinct queries.",ha="center",fontsize=9)
    for suffix in ("png","svg","pdf"):
        fig.savefig(destination / f"evaluation_protocol.{suffix}",dpi=180)
    plt.close(fig)
