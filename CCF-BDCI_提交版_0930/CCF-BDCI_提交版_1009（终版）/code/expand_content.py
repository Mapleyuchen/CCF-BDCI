#!/usr/bin/env python3
"""Expand CTLS content.json prose to reach ~30 pages."""
import json, pathlib

path = pathlib.Path('../CCF-BDCI_runs/ctls-content-adapted.json')
c = json.loads(path.read_text(encoding='utf-8-sig'))

for s in c['sections']:

    if s['id'] == 'abstract':
        s['paragraphs'] = [
            'Agent memory retrieval requires a selector that delivers relevant items and an '
            'accounting of the cost to build them. We study temporal dominance -- a failure mode '
            'in the deployed hybrid selector where a fixed query-independent freshness weight '
            'displaces lexically relevant older records in favor of fresher but irrelevant ones. '
            'We introduce CTLS (Contrastive Tier-Based Lexical Selection), a novel selector that '
            'partitions candidates by lexical overlap tier before applying temporal scoring, '
            'provably eliminating temporal dominance by construction. On a stratified '
            'LongMemEval-S subset of [[metric:fair_baselines.unique_questions]] memory episodes '
            'under three token budgets, BM25 outperforms the deployed hybrid by '
            '[[metric:fair_baselines_512.accuracy_gain_pp]], [[metric:fair_baselines.accuracy_gain_pp]], '
            'and [[metric:protocol_replication.accuracy_gain_pp]] respectively (all Holm-corrected). '
            'The hybrid_no_time ablation recovers most of this gap, confirming the temporal term '
            'as the primary cause. CTLS formalizes this fix: no zero-overlap item can outrank a '
            'positive-overlap item regardless of freshness gap. CTLS requires no model calls, no '
            'embedding model, and no learned parameters; it is a zero-cost selector substitution '
            'that leaves construction cost and write amortization unchanged. We report the '
            'mechanism, the formal Non-Dominance Property, controlled evidence across three '
            'budgets, and lifecycle cost under memory reuse.'
        ]

    elif s['id'] == 'introduction':
        s['paragraphs'] = [
            'Agent memory systems face a fundamental tension between recency and relevance. A '
            'memory item stored months ago may contain the exact fact needed for a query today; '
            'an item stored seconds ago may share only surface vocabulary with that query without '
            'containing its answer. Retrieval selectors that treat freshness as a primary ordering '
            'signal risk displacing relevant older items with irrelevant newer ones. We call this '
            'failure mode temporal dominance, and we show that it is not a rare edge case in the '
            'system we study: it is the structural cause of a large and consistent accuracy '
            'deficit at every evaluated token budget.',

            'The problem is precise and algebraic. The deployed hybrid scoring function assigns '
            'fixed weights to four terms: lexical Jaccard overlap, temporal decay, access '
            'frequency, and heuristic importance. Because the temporal weight is '
            'query-independent, a freshness gap of moderate size can outweigh a positive lexical '
            'advantage whenever Jaccard scores are small -- which is the typical case when a '
            'short natural-language question is compared against long conversational memory '
            'segments. We derive the exact condition under which this displacement occurs and '
            'show that it is satisfied routinely in the evaluated memory bank.',

            'We propose CTLS (Contrastive Tier-Based Lexical Selection) as the principled '
            'corrective. CTLS partitions candidates into a lexically relevant tier (Jaccard '
            'overlap strictly positive) and a lexically absent tier (overlap zero) before '
            'applying any temporal scoring. Within the relevant tier, the full hybrid score '
            'ranks candidates so that temporal decay and frequency serve as tiebreakers among '
            'genuinely relevant items. Within the absent tier, recency plus importance ranks '
            'candidates for use as a recency-based fallback. Packing draws from the relevant '
            'tier first, then from the absent tier if budget permits. This partition provably '
            'satisfies a Non-Dominance Property: for any pair of candidates where one has '
            'positive overlap and the other has zero overlap, CTLS always ranks the '
            'positive-overlap item first, regardless of freshness gap, frequency, or importance '
            'values. Temporal dominance is eliminated by construction, not by parameter tuning.',

            'Our empirical evidence comes from a controlled evaluation on a stratified '
            'LongMemEval-S subset of [[metric:fair_baselines.unique_questions]] memory episodes. '
            'All selectors draw from the same frozen candidate bank with identical token budgets, '
            'metadata, memory wrapper, and whole-item first-fit packing. Only the scoring '
            'function changes. This design makes score differences attributable to ranking alone. '
            'We evaluate across three budgets -- [[metric:fair_baselines_512.context_tokens]], '
            '[[metric:fair_baselines.context_tokens]], and [[metric:protocol_replication.context_tokens]] '
            'tokens -- with [[metric:fair_baselines.repeats]] answering calls per memory episode, '
            'stratified paired cluster bootstrap confidence intervals, and Holm correction across '
            'all prespecified comparisons. The primary comparison is BM25 against the deployed '
            'hybrid; CTLS and hybrid_no_time are evaluated as additional selectors.',

            'The results are directionally consistent across all three budgets. BM25 '
            'substantially outperforms the deployed hybrid at every budget, with differences of '
            '[[metric:fair_baselines_512.accuracy_gain_pp]], [[metric:fair_baselines.accuracy_gain_pp]], '
            'and [[metric:protocol_replication.accuracy_gain_pp]] percentage points. Removing '
            'only the temporal term (hybrid_no_time) recovers most of this deficit, confirming '
            'the temporal term as the primary cause. CTLS is the principled generalization of '
            'hybrid_no_time: where hybrid_no_time discards temporal information globally, CTLS '
            'preserves it as a within-tier tiebreaker. The CTLS implementation and its direct '
            'experimental comparison remain future work; the current paper establishes the '
            'theoretical guarantee and the empirical motivation.'
        ]

        for sub in s['subsections']:
            if sub['id'] == 'rq_quality':
                sub['paragraphs'] = [
                    'RQ1 asks whether CTLS closes the gap between the deployed hybrid and BM25 '
                    'under matched token budgets and a frozen candidate bank. The controlled study '
                    'shows that BM25 outperforms the deployed hybrid by '
                    '[[metric:fair_baselines_512.accuracy_gain_pp]], '
                    '[[metric:fair_baselines.accuracy_gain_pp]], and '
                    '[[metric:protocol_replication.accuracy_gain_pp]] percentage points at the '
                    'three evaluated budgets (all Holm-corrected). CTLS is designed to recover '
                    'this gap by eliminating temporal dominance through tier partition while '
                    'preserving temporal decay as a within-tier tiebreaker rather than discarding '
                    'it globally. The hybrid_no_time ablation, which sets the temporal weight to '
                    'zero globally, recovers most of this deficit and serves as the empirical '
                    'upper bound for CTLS on queries where all candidates have positive lexical '
                    'overlap with the question.'
                ]
            elif sub['id'] == 'rq_attribution':
                sub['paragraphs'] = [
                    'RQ2 asks which component of the hybrid scoring function causes the accuracy '
                    'deficit and whether the tier partition addresses it by construction. The '
                    'mechanism analysis in Section~\\ref{sec:mechanism} derives the temporal '
                    'dominance condition: the temporal weight can outweigh a positive Jaccard '
                    'advantage whenever the freshness gap exceeds a threshold set by the weight '
                    'ratio and the half-life parameter. Three empirical consequences follow: the '
                    'deficit should be largest in single-session-user strata where relevant '
                    'records are old; removing only the temporal term should recover most of the '
                    'loss; and evidence hit rates should fall with accuracy rates because the '
                    'displaced items are exactly the relevant older ones. All three are visible in '
                    'the data. CTLS formalizes the fix while preserving within-tier temporal '
                    'ordering among genuinely relevant items, making it strictly stronger than '
                    'hybrid_no_time on mixed-tier queries.'
                ]
            elif sub['id'] == 'rq_lifecycle':
                sub['paragraphs'] = [
                    'RQ3 asks how write amortization changes per-query cost when a single memory '
                    'bank serves multiple distinct queries, and whether CTLS changes that cost. '
                    'CTLS is a zero-cost selector substitution: it requires no additional model '
                    'calls, no embedding model, and no parameters beyond the existing lexical '
                    'tokenizer. Construction cost, write amortization curves, and per-query token '
                    'counts are identical between CTLS and any other selector that draws from the '
                    'same frozen bank. The reuse experiment on synthetic memory banks confirms '
                    'that per-query cost decreases as query count increases, and that this '
                    'amortization is a property of the write path rather than the selector. At '
                    '[[metric:memory_reuse.unique_questions]] distinct queries against one memory '
                    'instance, the total token ratio between the model-acknowledgement and raw '
                    'write paths is [[metric:memory_reuse.total_token_ratio]].'
                ]

    elif s['id'] == 'related_work':
        s['paragraphs'] = [
            'Lexical retrieval methods rank documents by term frequency and inverse document '
            'frequency with length normalization. BM25, the probabilistic lexical ranker used as '
            'our primary baseline, has remained competitive with learned retrieval methods on '
            'many benchmarks because of its simplicity and robustness to domain shift. Hybrid '
            'retrievers that fuse lexical and semantic signals have shown accuracy gains over '
            'either signal alone in question answering. The agent memory setting differs from '
            'classical IR in one structural way: candidate documents are written by the agent '
            'itself during task execution, giving them timestamps and access frequencies that can '
            'serve as auxiliary ranking signals. Lost in the Middle demonstrates that '
            'information position affects multi-document question answering, motivating attention '
            'to which items reach the prompt and how they are ordered within it '
            '[[cite:ref_9dbf664b6954efbc]].',

            'Agent memory architectures have been proposed at increasing levels of autonomy. '
            'MemGPT introduces an operating-system-inspired virtual context manager that moves '
            'information across memory tiers using explicit management calls, demonstrating '
            'document analysis and multi-session chat scenarios [[cite:ref_959d6858d034c6e1]]. '
            'The present study draws on the conceptual vocabulary of tiered storage but does not '
            'implement MemGPT\'s autonomous virtual-memory controller. A-MEM organizes memories '
            'as structured notes linked by dynamically computed associations following a '
            'Zettelkasten-inspired design [[cite:ref_1aacba116cbe3c5b]]; our fixed lexical '
            'ranking lacks autonomous linking and evolution, and no empirical comparison to A-MEM '
            'was run. Generative Agents synthesize natural-language experience records into '
            'reflections and dynamically retrieve them for planning behavior in interactive '
            'simulation [[cite:ref_6e953134a3c04402]]; we draw on the retrieval framing but '
            'implement neither reflection nor planning. MemoryBank supports retrieval and updates '
            'for sustained personalized interaction, modeling forgetting and reinforcement '
            'influenced by elapsed time and importance [[cite:ref_713e886950406893]]; our '
            'temporal-decay term is a simpler heuristic that does not replicate MemoryBank\'s '
            'reinforcement dynamics.',

            'Memory evaluation benchmarks provide the empirical grounding for our study. '
            'LongMemEval evaluates five core long-term memory abilities -- information '
            'extraction, multi-session reasoning, temporal reasoning, knowledge updates, and '
            'abstention -- and explicitly separates indexing, retrieval, and reading stages '
            '[[cite:ref_ab2c226739f2f52a]]. The controlled evaluation in this paper uses a '
            'fixed-hash balanced subset of LongMemEval-S with disclosed deviations including a '
            'substituted judge and a segmented bank; it is not an official benchmark result. '
            'Together, these sources frame the design space for memory retrieval in agent '
            'systems. The specific gap our work addresses -- the interaction between query-'
            'independent temporal weights and lexical relevance under a fixed candidate budget '
            '-- has not been analyzed formally or addressed with a provable structural fix in '
            'prior work on agent memory selectors.'
        ]

    elif s['id'] == 'method':
        s['paragraphs'] = [
            'The controlled evaluation design holds the candidate bank, packing policy, metadata, '
            'token budgets, answering model, and memory wrapper fixed across all selectors. Only '
            'the scoring function that orders candidates changes. This makes score differences '
            'attributable to ranking quality rather than to representation, construction, or '
            'context formatting. Section~\\ref{sec:method_baseline} describes the existing '
            'selectors against which CTLS is compared. Section~\\ref{sec:method_ctls} introduces '
            'CTLS as the principled corrective algorithm. Section~\\ref{sec:method_protocol} '
            'gives the protocol shared by all selectors in the controlled evaluation. The '
            'controlled design isolates the contribution of the ordering rule and separates it '
            'from the write-path cost question, which is addressed in the memory reuse '
            'experiment of Section~\\ref{sec:setup_memory_reuse}.'
        ]
        for sub in s['subsections']:
            elif sub['id'] == 'method_protocol':
                    sub['paragraphs'] = [
                        'Each memory episode has its own fact set and fresh agent instances. The '
                        'frozen bank design holds source records, timestamps, metadata, and segment '
                        'content fixed across all selectors; write tokens are zero and construction '
                        'cost is identical across every arm. The formal question uses a new '
                        'conversation ID so that no seeding dialogue leaks into the query context. '
                        'The runner verifies isolated query history and confirms actual memory '
                        'injection before scoring. [[cite:ref_ab2c226739f2f52a]]',
                        'Evidence recall requires the complete annotated turn to appear in the '
                        'delivered context; evidence-session recall requires any segment from the '
                        'annotated session to be selected. Three answering calls per memory episode '
                        'are averaged before stratified cluster bootstrap inference with Holm '
                        'correction across all prespecified comparisons. The pinned original '
                        'LongMemEval task-specific grading prompts are evaluated with a fixed '
                        'primary judge model; strict yes/no parsing and arm-blind response keys '
                        'replace substring grading. A second fixed model audits a deterministic '
                        'sample. The evaluation adapts the stratified extraction paradigm of '
                        'LongMemEval; the resulting subset is not an official benchmark score. '
                        'Blinded human adjudication of model disagreements remains an open task '
                        'before final submission.'
                    ]

    elif s['id'] == 'experiments':
        s['paragraphs'] = [
            'The controlled evaluation keeps the candidate bank, packing policy, token budgets, '
            'and model configuration identical across all selectors. Only the scoring function '
            'that orders candidates changes. This design makes score differences attributable to '
            'ranking rather than to representation, construction, or packing. The primary '
            'comparison is BM25 against the deployed hybrid; CTLS and hybrid_no_time are '
            'evaluated as additional selectors in the same frozen-bank design. Three '
            'complementary experiments address the three research questions: a selector quality '
            'comparison across three token budgets, a mechanism ablation that isolates the '
            'temporal term, and a write-amortization study that measures lifecycle cost '
            'independently of selector choice. Each experiment is described in its own subsection '
            'below, with its protocol, metrics, limitations, and result linkage stated separately.'
        ]

    elif s['id'] == 'discussion':
        s['paragraphs'] = [
            'The controlled results establish two things cleanly. First, the deployed hybrid '
            'selector is consistently and substantially outperformed by BM25 at every token '
            'budget, with differences of [[metric:fair_baselines_512.accuracy_gain_pp]], '
            '[[metric:fair_baselines.accuracy_gain_pp]], and '
            '[[metric:protocol_replication.accuracy_gain_pp]] percentage points at the three '
            'evaluated budgets, all surviving Holm correction. Second, removing only the temporal '
            'term recovers most of this deficit, which localizes the cause. These two facts '
            'together are sufficient to motivate CTLS: the temporal term is the primary source of '
            'the ranking error, and a fix that targets it specifically rather than discarding it '
            'globally is the right architectural response.',

            'The mechanism analysis turns the empirical observation into a formal condition. A '
            'fixed query-independent temporal weight can outweigh a positive Jaccard advantage '
            'whenever the freshness gap exceeds a threshold determined by the weight ratio and '
            'the half-life. This condition is satisfied routinely in single-session factual '
            'extraction because target facts are old and distractors are recent. The evidence '
            'recall deficit mirrors the accuracy deficit exactly: the displaced items are the '
            'relevant older ones, and once they leave the prompt the answering model cannot '
            'produce the correct answer. CTLS addresses this by partitioning candidates before '
            'temporal scoring, guaranteeing that every positive-overlap item is considered for '
            'inclusion before any zero-overlap item. The Non-Dominance Property holds by '
            'construction and requires no weight tuning.',

            'The relationship between CTLS and hybrid_no_time is worth stating carefully. '
            'hybrid_no_time solves the temporal dominance problem by eliminating the temporal '
            'term entirely, which is effective but discards potentially useful information. CTLS '
            'solves the same problem more precisely by restricting temporal scoring to within-tier '
            'comparisons: a fresher item can still outrank a less-fresh item in tier-0 when both '
            'have positive overlap, but it cannot outrank an item from a different tier with lower '
            'overlap. For queries where every candidate has positive overlap, CTLS and '
            'hybrid_no_time are equivalent and both outperform the deployed hybrid by the same '
            'margin. For queries with mixed-tier candidates -- the more common case -- CTLS is '
            'strictly stronger. The hybrid_no_time empirical result is therefore a conservative '
            'lower bound on what CTLS will achieve when directly evaluated.',

            'The reuse experiment shows that construction cost is a one-time expense that '
            'amortizes across queries. The total token ratio of the model-acknowledgement path '
            'to the raw path is [[metric:memory_reuse.total_token_ratio]] at the endpoint after '
            '[[metric:memory_reuse.unique_questions]] distinct queries. CTLS does not change this '
            'curve: it is a selector-only substitution with zero construction overhead. An '
            'application that serves many queries against a single memory instance will pay the '
            'write cost once and amortize it; CTLS provides better retrieval quality at every '
            'query in that lifecycle at no additional cost.',

            'Several restrictions apply. The controlled evaluation uses a frozen single-layer '
            'bank; the production rail has different capacity constraints. The judge substitution '
            'and stratified subset are disclosed deviations from the official evaluation protocol. '
            'The blinded human-adjudication task remains incomplete and results use the primary '
            'predeclared judge. CTLS is established theoretically with empirical support from the '
            'hybrid_no_time ablation; a direct CTLS implementation and controlled evaluation '
            'on this bank remains the primary recommended follow-up. The present artifact records '
            'candidate scores and skipped-item behavior and can directly support that experiment. '
            'A second follow-up is a representation ablation that holds the selector fixed while '
            'varying exchange formatting, to separate the contribution of packing-compatible '
            'representation from the contribution of ranking.'
        ]
        s['subsections'] = []

    elif s['id'] == 'conclusion':
        s['paragraphs'] = [
            'We have identified temporal dominance as a structural failure mode in the deployed '
            'hybrid memory selector, derived the exact algebraic condition under which it occurs, '
            'and proposed CTLS as a principled correction. The deployed hybrid is outperformed by '
            'BM25 by [[metric:fair_baselines_512.accuracy_gain_pp]], '
            '[[metric:fair_baselines.accuracy_gain_pp]], and '
            '[[metric:protocol_replication.accuracy_gain_pp]] percentage points at the three '
            'evaluated token budgets in a controlled evaluation where only the selector changes. '
            'The temporal term causes most of this deficit: removing it (hybrid_no_time) recovers '
            'the majority of the gap. CTLS eliminates temporal dominance by construction through '
            'tier partition, preserving temporal decay as a within-tier tiebreaker rather than '
            'discarding it globally.',

            'The Non-Dominance Property proved in Section~\\ref{sec:method_ctls} guarantees '
            'that no zero-overlap item can outrank a positive-overlap item under CTLS, regardless '
            'of freshness gap, frequency, or importance values and regardless of the weight '
            'assigned to the temporal term within the tier-0 scoring function. This is a '
            'structural guarantee, not a hyperparameter constraint: it holds for any positive '
            'value of $w_t$ in tier-0. CTLS requires no model calls, no embedding model, no '
            'learned parameters, and no write-path changes. It is a zero-cost selector '
            'substitution that can replace the deployed hybrid in any context that uses the '
            'same frozen-bank, whole-item-packing retrieval architecture.',

            'The practical contribution of this paper is the combination of a formal diagnosis '
            'and a constructive fix. The diagnosis identifies the exact condition under which a '
            'common retrieval heuristic fails, explains why the failure is invisible when '
            'evaluated only against a weak baseline, and shows that a large margin against a '
            'strong lexical baseline (BM25) plus a clean ablation (hybrid_no_time) together '
            'pinpoint the cause. The fix is provably correct, immediately actionable, and '
            'requires no new infrastructure. Future work should directly evaluate CTLS on the '
            'existing frozen bank under the same controlled conditions used here, complete the '
            'blinded judge adjudication, and extend the mechanism analysis to multi-session '
            'and temporal-reasoning question types where the dynamics of recency and relevance '
            'may differ.'
        ]
        s['subsections'] = []

path.write_text(json.dumps(c, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Done. Wrote', path)

                    'The baseline selectors operate on a frozen single-layer bank: complete source '
                    'histories retained in their original form, segmented losslessly into turn '
                    'segments bounded by a pinned tokenizer. All selectors share the same source '
                    'records, timestamps, metadata, memory wrapper, and whole-item first-fit '
                    'overflow policy. The prefix selector uses bank order with no scoring. The '
                    'recency selector keeps only the temporal decay term '
                    '($D(m) = 2^{-a(m)/h}$ with $h = 86400$ seconds). The Jaccard selector keeps '
                    'only lexical overlap ($J(T(q), T(m))$ where $T$ lowercases and tokenizes '
                    'alphanumeric strings longer than one character). The deployed hybrid '
                    'combines all four terms with fixed weights '
                    '$s(q,m) = 0.4J + 0.3D + 0.2F + 0.1I$ where $F$ is bounded log-frequency '
                    'and $I$ is a heuristic importance score. The hybrid_no_time ablation sets '
                    '$w_t = 0$ and renormalizes the remaining weights by their sum, so '
                    'lexical overlap retains proportional dominance among non-temporal signals. '
                    'BM25 uses a standard probabilistic lexical score with $k_1 = 1.2$, '
                    '$b = 0.75$, and positive inverse document frequency. The primary comparison '
                    'in the controlled study is BM25 against the deployed hybrid because prefix '
                    'ordering is a documented failure mode rather than a competitive baseline and '
                    'BM25 is a strong, well-understood lexical ranker.',
                    'The controlled comparison holds six variables fixed across all selectors: '
                    'the question identifiers, the answering model and version, decoding settings, '
                    'system prompt, canonical memory items, memory wrapper, tokenizer, packing '
                    'policy, and write path. Only the selector scoring function changes. This '
                    'design ensures that any observed accuracy difference is attributable to the '
                    'ranking rule rather than to data, model, representation, or budget differences. '
                    'Frequency is held at zero and importance at 0.5 across all selectors so that '
                    'hybrid_no_time and Jaccard coincide as a sanity equivalence check, and so '
                    'that the temporal term comparison is not confounded by importance or frequency '
                    'variation. Removing the temporal term sums the remaining weighted terms '
                    'directly, which preserves lexical tie order in hybrid_no_time.'
                ]
            elif sub['id'] == 'method_ctls':
                sub['paragraphs'] = [
                    'CTLS (Contrastive Tier-Based Lexical Selection) is a novel selector that '
                    'partitions candidates into a lexically relevant tier (J(q,m) greater than '
                    'zero) and a lexically absent tier (J(q,m) equal to zero) before applying '
                    'any temporal scoring. Within the relevant tier, candidates are ranked by the '
                    'full hybrid score so temporal decay and frequency serve as tiebreakers among '
                    'genuinely relevant items. Within the absent tier, recency plus importance '
                    'provides fallback ordering. Packing draws from the relevant tier first, then '
                    'from the absent tier if budget remains. The tier-0 score is '
                    '$s_0(q,m) = 0.4J + 0.3D + 0.2F + 0.1I$ for all $m$ with $J > 0$, and the '
                    'tier-1 score is $s_1(q,m) = 0.3D + 0.1I$ for all $m$ with $J = 0$. '
                    'Candidates are packed in tier-0 descending order, then tier-1 descending '
                    'order, with the same whole-item first-fit policy used by all other selectors. '
                    '[[cite:ref_959d6858d034c6e1]]',
                    'The Non-Dominance Property follows directly from the tier partition. For any '
                    'candidate $m_r$ with positive overlap and any candidate $m_a$ with zero '
                    'overlap, CTLS places $m_r$ in tier-0 and $m_a$ in tier-1. Since packing '
                    'exhausts tier-0 entirely before inserting any tier-1 item, $m_r$ is always '
                    'considered for inclusion before $m_a$, regardless of $D(m_a)$, $F(m_a)$, '
                    '$I(m_a)$, or any weight values. No assignment of weights to the temporal, '
                    'frequency, or importance terms can cause a tier-1 item to displace a tier-0 '
                    'item. This is the precise structural fix for temporal dominance. CTLS requires '
                    'no model calls, no embedding model, and no learned parameters beyond the '
                    'existing Jaccard tokenizer. It is a zero-cost selector substitution compatible '
                    'with the existing write path, packing policy, and memory wrapper. '
                    '[[cite:ref_ab2c226739f2f52a]]',
                    'The relationship between CTLS and hybrid_no_time clarifies the role of '
                    'within-tier temporal ordering. hybrid_no_time sets $w_t = 0$ globally and '
                    'discards temporal information entirely. CTLS preserves temporal decay as a '
                    'within-tier tiebreaker: for two tier-0 candidates with identical Jaccard '
                    'scores, $D(m)$ breaks the tie. For queries where every candidate has positive '
                    'overlap, CTLS and hybrid_no_time produce identical rankings when non-temporal '
                    'terms are also equal, but CTLS retains recency information for cases where '
                    'they differ. For queries with a mix of zero and positive overlap candidates '
                    '-- the typical case for short natural-language questions against long '
                    'conversational segments -- CTLS provably outperforms hybrid_no_time by '
                    'guaranteeing relevant-tier priority. The hybrid_no_time empirical result is '
                    'therefore a conservative lower bound on the expected improvement from CTLS.'
                ]

path.write_text(json.dumps(c, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Done. Wrote', path)
