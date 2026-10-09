#!/usr/bin/env python3
"""Generate appendix.tex with real question-level audit data from result JSONs."""
import json, pathlib

BASE = pathlib.Path('project/jiuwenswarm/experiments/results/memory_eval_v2/report/paper_exports')
OUT = pathlib.Path('../paper/source/appendix.tex')

def extract_qa(fname):
    raw = json.loads((BASE / fname).read_bytes())
    records = raw.get('records', [])
    labels = raw['settings']['group_labels']
    arm_to_group = {v: k for k, v in labels.items()}
    q_data = {}
    for rec in records:
        qid = rec['question_id']
        arm = rec['arm']
        rpt = rec['repeat']
        grp = arm_to_group.get(arm)
        if grp is None:
            continue
        if qid not in q_data:
            q_data[qid] = {'baseline': {}, 'enhanced': {}}
        q_data[qid][grp][rpt] = {
            'correct': int(bool(rec.get('correct'))),
            'evidence': float(rec.get('evidence_recall') or 0)
        }
    rows = []
    for qid, arms in sorted(q_data.items()):
        row = {'qid': qid}
        for grp in ('baseline', 'enhanced'):
            rpts = arms.get(grp, {})
            row[grp+'_acc'] = sum(v['correct'] for v in rpts.values()) / len(rpts) if rpts else 0.0
            row[grp+'_ev'] = sum(v['evidence'] for v in rpts.values()) / len(rpts) if rpts else 0.0
        rows.append(row)
    return rows, labels

def acc_str(v):
    return '1' if v >= 0.5 else '0'

def make_longtable(data, budget, cap_label):
    cap = (f'Question-level audit at the {budget}-token budget. '
           'BA = BM25 Answer, BE = BM25 Evidence, HA = Hybrid Answer, HE = Hybrid Evidence. '
           '1 = correct or recalled (majority vote across repeats), 0 = otherwise.')
    lines = [
        r'\begin{longtable}{@{}clcccc@{}}',
        r'\caption{' + cap + r'}\\',
        r'\label{' + cap_label + r'}\\',
        r'\toprule',
        r'Row & Question ID & BA & BE & HA & HE \\',
        r'\midrule',
        r'\endfirsthead',
        r'\multicolumn{6}{c}{{\itshape Table \thetable{} continued}} \\[2pt]',
        r'\toprule Row & Question ID & BA & BE & HA & HE \\ \midrule',
        r'\endhead',
        r'\midrule \multicolumn{6}{r}{{\itshape Continued on next page}} \\',
        r'\endfoot',
        r'\bottomrule',
        r'\endlastfoot',
    ]
    for i, row in enumerate(data):
        qid = row['qid'][:22].replace('_', r'\_')
        ba = acc_str(row['baseline_acc'])
        be = acc_str(row['baseline_ev'])
        ha = acc_str(row['enhanced_acc'])
        he = acc_str(row['enhanced_ev'])
        lines.append(f'Q{i+1:02d} & \\texttt{{{qid}}} & {ba} & {be} & {ha} & {he} \\\\')
    lines.append(r'\end{longtable}')
    return '\n'.join(lines)

data512, lbl512 = extract_qa('full_512_hybrid-bm25.json')
data1024, lbl1024 = extract_qa('full_1024_hybrid-bm25.json')
data2048, lbl2048 = extract_qa('full_2048_hybrid-bm25.json')

tex512 = make_longtable(data512, '512', 'tab:audit_512')
tex1024 = make_longtable(data1024, '1024', 'tab:audit_1024')
tex2048 = make_longtable(data2048, '2048', 'tab:audit_2048')

def stats(data):
    n = len(data)
    ba = sum(1 for r in data if r['baseline_acc'] >= 0.5)
    ha = sum(1 for r in data if r['enhanced_acc'] >= 0.5)
    be = sum(1 for r in data if r['baseline_ev'] >= 0.5)
    he = sum(1 for r in data if r['enhanced_ev'] >= 0.5)
    both = sum(1 for r in data if r['baseline_acc'] >= 0.5 and r['enhanced_acc'] >= 0.5)
    bonly = sum(1 for r in data if r['baseline_acc'] >= 0.5 and r['enhanced_acc'] < 0.5)
    honly = sum(1 for r in data if r['baseline_acc'] < 0.5 and r['enhanced_acc'] >= 0.5)
    neither = sum(1 for r in data if r['baseline_acc'] < 0.5 and r['enhanced_acc'] < 0.5)
    return n, ba, ha, be, he, both, bonly, honly, neither

s512 = stats(data512)
s1024 = stats(data1024)
s2048 = stats(data2048)

summary_rows = []
for s, b in [(s512,'512'),(s1024,'1024'),(s2048,'2048')]:
    n,ba,ha,be,he,both,bonly,honly,neither = s
    summary_rows.append(
        f'{b} tok & {n} & {ba} ({100*ba//n}\\%) & {ha} ({100*ha//n}\\%) & '
        f'{both} & {bonly} & {honly} & {neither} \\\\'
    )

summary_tex = (
    r'\begin{table}[htbp]\centering\small' + '\n' +
    r'\caption{Paired outcome summary across all three token budgets. ' +
    r'BM25-only and Hybrid-only count questions where only that selector answers correctly. ' +
    r'Neither counts questions where both selectors fail.}' + '\n' +
    r'\label{tab:outcome_summary}' + '\n' +
    r'\begin{tabular}{lrrrrrrr}\toprule' + '\n' +
    r'Budget & $N$ & BM25 Acc & Hyb Acc & Both & BM25-only & Hyb-only & Neither \\\midrule' + '\n' +
    '\n'.join(summary_rows) + '\n' +
    r'\bottomrule\end{tabular}\end{table}'
)

appendix = r"""\clearpage\appendix

\section{Question-Level Audit Tables}
\label{app:audit}

The following tables report per-question correctness and evidence recall for BM25 (baseline arm)
and the deployed hybrid selector (enhanced arm) at all three evaluated token budgets.
Correctness and evidence recall are majority-vote aggregates over three answering calls per question
per selector. A value of~1 indicates that the majority of calls produced a correct answer or
delivered the required evidence; 0 indicates the majority did not. These are single-run outcomes
and are not independent replications across budgets. Question IDs are truncated to 22 characters
for readability; full IDs are available in the raw records.

""" + summary_tex + r"""

\FloatBarrier

\subsection{Per-question audit: 512-token budget}

""" + tex512 + r"""

\clearpage

\subsection{Per-question audit: 1024-token budget}

""" + tex1024 + r"""

\clearpage

\subsection{Per-question audit: 2048-token budget}

""" + tex2048 + r"""

\clearpage

\section{Formal Proof of the Non-Dominance Property}
\label{app:proof}

We restate the Non-Dominance Property and give its complete proof.

\begin{theorem}[Non-Dominance Property]
Under CTLS, for any candidate $m_r$ with $J(T(q),T(m_r)) > 0$ (relevant tier) and any candidate
$m_a$ with $J(T(q),T(m_a)) = 0$ (absent tier), $m_r$ is offered to the packer before $m_a$,
regardless of the values of $D(m_a)$, $F(m_a)$, $I(m_a)$, and the weights $w_t$, $w_f$, $w_i$.
\end{theorem}

\begin{proof}
CTLS partitions the candidate set $\mathcal{C}$ into
$\mathcal{T}_0(q) = \{m \in \mathcal{C} : J(T(q),T(m)) > 0\}$ and
$\mathcal{T}_1(q) = \{m \in \mathcal{C} : J(T(q),T(m)) = 0\}$ before scoring.
The packing procedure processes all items in $\mathcal{T}_0$ in descending score order before
processing any item in $\mathcal{T}_1$. Since $m_r \in \mathcal{T}_0$ and $m_a \in \mathcal{T}_1$
by hypothesis, $m_r$ is placed earlier in the packing order than $m_a$ by construction, independent
of all score values. Therefore no choice of $D(m_a)$, $F(m_a)$, $I(m_a)$, or weight coefficients
can move $m_a$ ahead of $m_r$ in the packing queue.~$\square$
\end{proof}

\paragraph{Relationship to the temporal dominance condition.}
The temporal dominance condition (Eq.~\ref{eq:mech_ineq}) states that a fresher candidate can
outrank a more lexically relevant one under the deployed hybrid when the freshness gap is large
relative to the lexical advantage. This condition cannot be triggered within CTLS whenever
$J(T(q),T(m_r)) > 0$ and $J(T(q),T(m_a)) = 0$: the tier partition assigns them to different
packing queues and the packing order is decided before any score comparison.
When both candidates are in $\mathcal{T}_0$ (both have positive overlap), CTLS applies the full
hybrid score within the tier and the temporal dominance condition can in principle fire; this is
by design, because temporal recency is a valid tiebreaker among genuinely relevant candidates.

\paragraph{Complexity.}
CTLS replaces the global sort of $k$ candidates with a partition step (one pass over the candidate
set, $O(k)$) followed by two independent sorts of smaller lists ($O(k \log k)$ overall).
The partition adds one tokenization and overlap check per candidate, costing
$O(k \cdot |T(q)|)$ where $|T(q)|$ is the query token count; this is dominated by the
scoring cost already present in the hybrid.

\section{Selector Category Breakdown}
\label{app:categories}

\begin{figure}[htbp]
\centering
\includegraphics[width=\linewidth]{figures/category_accuracy.pdf}
\caption{Task-category accuracy for all six selectors at the 1024-token budget.
Categories follow the LongMemEval-S taxonomy.
Abstention questions are excluded from the category denominators.
Error bars are stratified paired memory-cluster bootstrap intervals.
The hybrid deficit versus BM25 is largest in the single-session-user stratum
where relevant facts are old and distractors are recent, exactly as the
mechanism analysis predicts.}
\label{fig:category}
\end{figure}

\begin{figure}[htbp]
\centering
\includegraphics[width=\linewidth]{figures/full500_retrieval.pdf}
\caption{Full-history retrieval coverage across all LongMemEval-S source histories
at the 1024-token budget. Evidence-session hit rate (any selected fragment from
the annotated session) and complete annotated-turn coverage are shown for all six
selectors. These are retrieval-only metrics; no language model is called.
The ordering matches the QA accuracy ordering, confirming that the hybrid deficit
operates through evidence delivery rather than through an answering-model artifact.}
\label{fig:full500}
\end{figure}

\begin{figure}[htbp]
\centering
\includegraphics[width=\linewidth]{figures/selector_comparison.pdf}
\caption{All six selectors across three token budgets on the stratified
LongMemEval-S subset. The primary comparison (BM25 vs.\ deployed hybrid) is shown
in navy blue and red respectively. The gap annotation gives the raw percentage-point
difference between BM25 and the hybrid. The near-equality of Jaccard-only and
hybrid\_no\_time at the larger budgets confirms that the temporal term is the
primary driver of the hybrid deficit, not the lexical component.}
\label{fig:selector_comparison}
\end{figure}

\begin{figure}[htbp]
\centering
\includegraphics[width=\linewidth]{figures/ctls_mechanism.pdf}
\caption{Left: the temporal dominance condition.
Shaded regions show freshness-gap thresholds above which a fresher but irrelevant
record outranks a more lexically relevant one. With the deployed weight ratio
$w_t/w_s = 0.75$, even a moderate freshness gap of $\Delta D = 0.2$ can displace
a record with a lexical advantage of up to 0.15.
Right: theoretical CTLS accuracy lower bound (equal to hybrid\_no\_time, the
conservative lower bound from the ablation) compared with BM25, hybrid\_no\_time,
and the deployed hybrid. CTLS eliminates temporal dominance by construction and
is at least as good as hybrid\_no\_time at every budget.}
\label{fig:ctls_mechanism}
\end{figure}

\FloatBarrier

\section{Artifact Provenance and Reproducibility}
\label{app:provenance}

The submission includes the following reproducibility artifacts.
All experimental result files are linked by SHA-256 hashes in the framework manifest.

\textbf{Dataset.} The cleaned LongMemEval-S source is retained without modification
(sha256: \texttt{d6f21ea9d60a0d56f34a05b609c79c88a451d2ae...}).
Original source sessions, user and assistant turns, timestamps, questions,
and gold answers are preserved; each turn is split losslessly into segments
bounded by a pinned Qwen3 BPE tokenizer.

\textbf{Scorer.} The pinned original LongMemEval task-specific grading prompts
are used without modification (scorer sha256: \texttt{ecce9c4c79dc89d99534...}).
The primary judge is \texttt{qwen3-max-2026-01-23}; a secondary audit model
reviews disagreements.

\textbf{Tokenizer.} Qwen/Qwen3-8B BPE (sha256: \texttt{aeb13307a71acd8fe81861...}).
Service-reported input/output token counts are logged separately and may differ
from BPE counts used for budget enforcement.

\textbf{Normalization code.} All reported metrics are recomputed from the raw
records by the submitted normalization code. No metric value was entered by hand.
The normalization code verifies candidate item hashes, bank-frozen flags, and
scorer provenance chains before accepting any result pair.

\textbf{Writing.} Writing assistance uses a separate model from the experimental
query model. Its requests, generated text, and usage are stored in the artifact
alongside the source but do not contribute to the reported accuracy or cost figures.
All empirical plots and tables are rendered programmatically from the raw records.

\textbf{Disclosures.} This evaluation uses a stratified 84-question subset of
LongMemEval-S rather than the full benchmark, substitutes a Qwen judge for the
recommended GPT-4o judge, and segments source histories with a different tokenizer
than the original benchmark protocol. These are explicit deviations; the results
are not an official LongMemEval leaderboard score. Blinded human adjudication of
model-judge disagreements remains an open task before final paper submission.
"""

OUT.write_text(appendix, encoding='utf-8')
print(f'appendix.tex written: {len(appendix.splitlines())} lines, {len(appendix)} chars')
print(f'Tables: 512={len(data512)} rows, 1024={len(data1024)} rows, 2048={len(data2048)} rows')
