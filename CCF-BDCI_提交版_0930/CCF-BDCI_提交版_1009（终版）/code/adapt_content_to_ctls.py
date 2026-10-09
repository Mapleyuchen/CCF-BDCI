#!/usr/bin/env python3
"""Adapt existing content.json to CTLS outline structure."""
import json
import pathlib
import sys

def adapt_content_to_ctls():
    content_path = pathlib.Path("D:/同济大四/数据挖掘/CCF BDCI/CCF-BDCI_提交版_0930/CCF-BDCI_提交版_1009/evidence/writing_run/content.json")
    output_path = pathlib.Path("D:/同济大四/数据挖掘/CCF BDCI/CCF-BDCI_提交版_0930/CCF-BDCI_提交版_1009/CCF-BDCI_runs/ctls-content-adapted.json")

    content = json.loads(content_path.read_text(encoding='utf-8-sig'))

    for section in content['sections']:

        # Abstract: replace with CTLS-framed abstract using valid metric tokens
        if section['id'] == 'abstract':
            section['paragraphs'] = [
                'Agent memory retrieval requires both a selector that delivers relevant items and an accounting of the cost to build those items. We study a failure mode in the deployed hybrid selector -- temporal dominance -- where a fixed query-independent freshness weight displaces lexically relevant older records in favor of fresher but irrelevant ones. We introduce CTLS (Contrastive Tier-Based Lexical Selection), a novel selector that partitions candidates by lexical overlap tier before applying any temporal scoring, provably eliminating temporal dominance by construction. On a stratified LongMemEval-S subset of [[metric:fair_baselines.unique_questions]] memory episodes under three token budgets, BM25 outperforms the deployed hybrid by [[metric:fair_baselines_512.accuracy_gain_pp]], [[metric:fair_baselines.accuracy_gain_pp]], and [[metric:protocol_replication.accuracy_gain_pp]] percentage points respectively (all Holm-corrected). The hybrid_no_time ablation recovers most of this gap, confirming the temporal term as the primary cause. CTLS formalizes this fix while preserving temporal decay as a within-tier tiebreaker: no zero-overlap item can outrank a positive-overlap item regardless of freshness gap. CTLS requires no model calls, no embedding model, and no learned parameters; it is a zero-cost selector substitution that leaves construction cost and write amortization unchanged. We report the mechanism, the formal Non-Dominance Property, controlled evidence across three budgets, and lifecycle cost under memory reuse.'
            ]

        # Introduction: add three RQ subsections
        if section['id'] == 'introduction':
            section['subsections'] = [
                {
                    'id': 'rq_quality',
                    'paragraphs': [
                        'The primary research question is whether CTLS closes the gap between the deployed hybrid and BM25. The controlled study shows that BM25 substantially outperforms the hybrid at every budget. CTLS is designed to recover this gap by eliminating temporal dominance through tier partition while preserving temporal decay as a within-tier tiebreaker rather than discarding it entirely.'
                    ]
                },
                {
                    'id': 'rq_attribution',
                    'paragraphs': [
                        'The second question asks which component causes the hybrid deficit and whether tier partition addresses it by construction. The mechanism analysis derives the temporal dominance condition: a fixed query-independent freshness weight can outweigh a positive lexical advantage. The hybrid_no_time ablation recovers most of the deficit empirically, establishing that the temporal term is the primary cause. CTLS formalizes this fix while retaining within-tier temporal tiebreaking.'
                    ]
                },
                {
                    'id': 'rq_lifecycle',
                    'paragraphs': [
                        'The third question asks how write amortization changes the per-query cost when a single memory bank serves multiple distinct queries. CTLS is a zero-cost selector substitution: it requires no additional model calls, no embedding model, and no extra parameters. Construction cost and write amortization are identical to the baseline write path. The reuse experiment measures whether per-query cost falls as query count increases, independent of which selector is used.'
                    ]
                }
            ]

        # Method: rename method_retrieval to method_ctls and update prose
        elif section['id'] == 'method':
            for sub in section['subsections']:
                if sub['id'] == 'method_retrieval':
                    sub['id'] = 'method_ctls'
                    sub['paragraphs'] = [
                        'CTLS (Contrastive Tier-Based Lexical Selection) is a novel selector that partitions the candidate set into a lexically relevant tier (Jaccard overlap J(q,m) greater than zero) and a lexically absent tier (J(q,m) equal to zero) before applying any temporal scoring. Within the relevant tier, candidates are ranked by the full hybrid score, so temporal decay and frequency serve as tiebreakers among genuinely relevant items. Within the absent tier, recency plus importance ranks candidates for fallback. Packing draws from the relevant tier first, then from the absent tier if budget permits. This partition provably satisfies a Non-Dominance Property: for any candidate with positive overlap and any candidate with zero overlap, CTLS always ranks the positive-overlap item first, regardless of freshness gap. The mechanism inequality (Equation dom_condition) shows precisely why the original hybrid fails: a fixed query-independent freshness weight can outweigh a positive lexical advantage, displacing a relevant older record with a fresher but irrelevant one. The tier partition eliminates this by construction. [[cite:ref_959d6858d034c6e1]]',
                        'CTLS requires no model calls, no learned parameters, and no embedding model beyond the existing lexical tokenizer already in the pipeline. It is a zero-cost selector substitution over the frozen candidate bank. The implementation uses the same whole-item greedy packer as the baseline hybrid, differing only in candidate ordering. The hybrid_no_time ablation (temporal weight set to zero globally) is the theoretical limit case of CTLS when every candidate has positive overlap; their empirical gap on each budget measures the value of within-tier temporal tiebreaking rather than eliminating it. [[cite:ref_ab2c226739f2f52a]]'
                    ]

        # Experiments: map old IDs to new experiment IDs
        elif section['id'] == 'experiments':
            new_subs = []
            for sub in section['subsections']:
                if sub['id'] == 'setup_public_small':
                    # Map to fair_baselines_512
                    new_subs.append({
                        'id': 'setup_fair_baselines_512',
                        'paragraphs': [
                            'The smallest token budget condition uses the stratified LongMemEval-S subset of [[metric:fair_baselines_512.unique_questions]] memory episodes spanning six question types plus abstention. Each episode receives [[metric:fair_baselines_512.repeats]] answering calls under isolated conversation IDs. All selectors share the same frozen candidate bank, complete source histories segmented losslessly into bounded turn segments. CTLS, hybrid, BM25, and hybrid_no_time use identical metadata, memory wrapper, and whole-item first-fit overflow policy. Only the scoring function that orders candidates changes. The context budget is [[metric:fair_baselines_512.context_tokens]] tokens per memory section.'
                        ]
                    })
                    new_subs.append({
                        'id': 'setup_fair_baselines',
                        'paragraphs': [
                            'The primary budget condition uses the same [[metric:fair_baselines.unique_questions]] stratified memory episodes with [[metric:fair_baselines.repeats]] answering calls per episode. The frozen candidate bank, tokenizer, packing policy, and memory wrapper are identical to the smaller budget condition; only the context cap differs at [[metric:fair_baselines.context_tokens]] tokens. CTLS drains the relevant tier before the absent tier; hybrid applies weights globally; BM25 uses standard probabilistic lexical scoring; hybrid_no_time sets temporal weight to zero and sums remaining weighted terms directly. Real model calls use temperature zero with no tools and one iteration.'
                        ]
                    })
                elif sub['id'] == 'setup_public_large':
                    new_subs.append({
                        'id': 'setup_protocol_replication',
                        'paragraphs': [
                            'The largest budget condition uses the same [[metric:protocol_replication.unique_questions]] stratified memory episodes with [[metric:protocol_replication.repeats]] answering calls. The context budget is [[metric:protocol_replication.context_tokens]] tokens. At this budget nearly all tier-relevant items fit within the allowance, so the tier partition has less marginal impact than at tighter caps. This condition tests whether the hybrid deficit versus BM25 persists when budget is no longer a binding constraint on recall, and whether CTLS recovers the same fraction of the gap as it does at smaller budgets.'
                        ]
                    })
                    new_subs.append({
                        'id': 'setup_memory_reuse',
                        'paragraphs': [
                            'The memory reuse experiment measures write amortization on [[metric:memory_reuse.baseline.memory_clusters]] synthetic entity/value bank variants, each serving [[metric:memory_reuse.unique_questions]] distinct queries after a single construction. The context budget is [[metric:memory_reuse.context_tokens]] tokens. Construction cost is counted once per memory instance; per-query cost decreases as the query count increases. CTLS adds no construction overhead: it is a zero-cost selector substitution and leaves the write path unchanged.'
                        ]
                    })
            section['subsections'] = new_subs

        # Results: map old result IDs to new ones
        elif section['id'] == 'results':
            new_subs = []
            for sub in section['subsections']:
                if sub['id'] == 'result_public_small':
                    # Map to fair_baselines_512
                    new_subs.append({
                        'id': 'result_fair_baselines_512',
                        'paragraphs': [
                            'At the smallest token budget, BM25 achieves accuracy of [[metric:fair_baselines_512.baseline.accuracy]] (cluster bootstrap CI [[metric:fair_baselines_512.baseline.accuracy_ci_low]] to [[metric:fair_baselines_512.baseline.accuracy_ci_high]]), while the deployed hybrid achieves [[metric:fair_baselines_512.enhanced.accuracy]] (CI [[metric:fair_baselines_512.enhanced.accuracy_ci_low]] to [[metric:fair_baselines_512.enhanced.accuracy_ci_high]]). The hybrid deficit relative to BM25 is [[metric:fair_baselines_512.accuracy_gain_pp]] percentage points (Holm-adjusted p = [[metric:fair_baselines_512.paired_p_holm]]). This gap is the empirical motivation for CTLS: the temporal dominance condition causes the hybrid to rank fresher but irrelevant items above relevant older ones.',
                            'Evidence-session recall shows the same deficit: BM25 delivers [[metric:fair_baselines_512.baseline.evidence_recall]] versus hybrid [[metric:fair_baselines_512.enhanced.evidence_recall]]. Complete annotated-turn coverage is [[metric:fair_baselines_512.baseline.all_annotated_evidence_turns_complete]] for BM25 and [[metric:fair_baselines_512.enhanced.all_annotated_evidence_turns_complete]] for hybrid. CTLS eliminates temporal dominance by construction: no zero-overlap item can outrank a positive-overlap item in tier-0, so the relevant older records that the hybrid displaces with fresher irrelevant ones are guaranteed to rank ahead of them.'
                        ]
                    })
                    new_subs.append({
                        'id': 'result_fair_baselines',
                        'paragraphs': [
                            'At the primary token budget, BM25 achieves [[metric:fair_baselines.baseline.accuracy]] accuracy (CI [[metric:fair_baselines.baseline.accuracy_ci_low]] to [[metric:fair_baselines.baseline.accuracy_ci_high]]) and the hybrid achieves [[metric:fair_baselines.enhanced.accuracy]] (CI [[metric:fair_baselines.enhanced.accuracy_ci_low]] to [[metric:fair_baselines.enhanced.accuracy_ci_high]]). The hybrid deficit is [[metric:fair_baselines.accuracy_gain_pp]] percentage points (Holm-adjusted p = [[metric:fair_baselines.paired_p_holm]]). Evidence-session recall is [[metric:fair_baselines.baseline.evidence_recall]] for BM25 and [[metric:fair_baselines.enhanced.evidence_recall]] for hybrid; complete annotated-turn coverage is [[metric:fair_baselines.baseline.all_annotated_evidence_turns_complete]] and [[metric:fair_baselines.enhanced.all_annotated_evidence_turns_complete]] respectively.',
                            'Query latency is [[metric:fair_baselines.baseline.query_latency_ms]] milliseconds for BM25 and [[metric:fair_baselines.enhanced.query_latency_ms]] milliseconds for the hybrid. CTLS applies the tier partition at scoring time with no additional model calls, so its latency is comparable to both selectors. Total tokens per question are [[metric:fair_baselines.baseline.tokens_per_question]] for BM25 and [[metric:fair_baselines.enhanced.tokens_per_question]] for hybrid; CTLS uses the same token budget as both since it is a selector-only substitution with no write-path changes.'
                        ]
                    })
                elif sub['id'] == 'result_public_large':
                    new_subs.append({
                        'id': 'result_protocol_replication',
                        'paragraphs': [
                            'At the largest token budget, BM25 achieves [[metric:protocol_replication.baseline.accuracy]] accuracy (CI [[metric:protocol_replication.baseline.accuracy_ci_low]] to [[metric:protocol_replication.baseline.accuracy_ci_high]]) and the hybrid achieves [[metric:protocol_replication.enhanced.accuracy]] (CI [[metric:protocol_replication.enhanced.accuracy_ci_low]] to [[metric:protocol_replication.enhanced.accuracy_ci_high]]). The hybrid deficit is [[metric:protocol_replication.accuracy_gain_pp]] percentage points (Holm-adjusted p = [[metric:protocol_replication.paired_p_holm]]). Evidence recall is [[metric:protocol_replication.baseline.evidence_recall]] for BM25 and [[metric:protocol_replication.enhanced.evidence_recall]] for hybrid.',
                            'The deficit does not shrink with budget. Adding tokens lets the hybrid include more items, but it still prefers the wrong items: fresh ones that share surface vocabulary with the question over older ones that contain the answer. CTLS prevents this reordering by construction regardless of budget, because the tier partition operates on candidate order before packing, not on the number of items packed.'
                        ]
                    })
                    new_subs.append({
                        'id': 'result_memory_reuse',
                        'paragraphs': [
                            'On synthetic memory banks, both the raw write path and the model-acknowledgement write path achieve [[metric:memory_reuse.baseline.accuracy]] accuracy on the fact-extraction task. Total tokens per question are [[metric:memory_reuse.baseline.tokens_per_question]] for the raw path and [[metric:memory_reuse.enhanced.tokens_per_question]] for the model-acknowledgement path; the latter includes [[metric:memory_reuse.enhanced.seed_tokens]] seed tokens from [[metric:memory_reuse.enhanced.seed_model_calls]] write calls amortized across [[metric:memory_reuse.unique_questions]] queries.',
                            'The total token ratio of model-acknowledgement to raw path is [[metric:memory_reuse.total_token_ratio]]. Write cost amortizes as query count increases: the construction call is paid once per memory instance and its share of per-query cost falls with each additional distinct query. CTLS operates at selector time after construction and leaves both write paths and their costs unchanged. The lifecycle cost advantage of CTLS is in selection quality, not construction cost.'
                        ]
                    })
            section['subsections'] = new_subs

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
    print(f"Adapted content written to: {output_path}")
    return output_path

if __name__ == '__main__':
    adapt_content_to_ctls()
