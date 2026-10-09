"""Audited methodology, diagnostic figures and per-question appendix for the L1 study."""
from pathlib import Path
import shutil

from paper_framework.citations import latex_text

MODULE = Path(__file__).resolve().parents[2]

FORMALIZATION = r'''
\subsection{Budget and cost formalization}
Let $q$ be a question, $M$ its episode memory, and $B$ the cap on the entire
injected memory section, including headings and metadata. The baseline constructs
a file-derived section and keeps its prefix. The retrieved arm scores stored
exchanges, takes at most $k=10$ candidates, and greedily appends complete formatted
items that fit. An over-budget item is skipped rather than partially appended;
later smaller items can still be considered. Thus equal $B$ does not imply equal
usable fact content or identical prompt formatting.
\begin{equation}
  s(q,m)=0.4J(T(q),T(m))+0.3\,2^{-a(m)/h}
       +0.2\min\!\left\{\frac{\log(1+f(m))}{\log(101)},1\right\}+0.1I(m),
  \label{eq:ranking}
\end{equation}
where $T$ lowercases text and keeps alphanumeric/underscore word tokens longer
than one character; $J(A,C)=|A\cap C|/|A\cup C|$ (zero for an empty set);
$a(m)$ is age in seconds; $h=86400$ is the decay half-life; $f(m)$ is the recorded
access count; and $I(m)$ is a bounded heuristic importance score. These are the
implementation's default weights, not learned or tuned coefficients. No embedding
model is invoked. L1 holds at most 20 exchanges with a one-hour time-to-live;
individual displayed exchanges are capped at 500 characters before packing.

The cost estimand includes initialization through model-backed memory writes:
\begin{equation}
 C_g=\frac{\sum_{r\in\mathcal{Q}_g}u_r+
                 \sum_{w\in\mathcal{W}_g}u_w}{N_{\rm valid}},\qquad
 L_g=\frac{\sum_{r\in\mathcal{Q}_g}t_r+
                 \sum_{w\in\mathcal{W}_g}t_w}{N_{\rm valid}}.
 \label{eq:accounting}
\end{equation}
Here $u$ and $t$ denote recorded token usage and elapsed time, respectively;
$\mathcal Q_g$ and $\mathcal W_g$ include all recorded query and write attempts.
The denominator counts valid matched question pairs. These timing sums exclude
unrecorded process initialization and are not a full application wall-clock time.
Missing usage remains unknown rather than zero.

For each valid pair, let $y_{g,i}$ indicate an accepted-answer substring match
and $e_{g,i}$ indicate that the complete target fact survived in the injected text:
\begin{equation}
 A_g=\frac{1}{N}\sum_i y_{g,i},\qquad
 R_g=\frac{1}{N}\sum_i e_{g,i},\qquad
 \Delta A=A_{\rm retrieved}-A_{\rm file}.
 \label{eq:metrics}
\end{equation}
The two indicators differ: a truncated fact can contain a sufficient answer span.
Wilson intervals describe finite-question uncertainty only. They do not estimate
model-run variability, correct the selected slice's bias, or establish significance.

\begin{table}[htbp]
\centering\small
\caption{Audited execution protocol. No component ablation or weight tuning is claimed.}
\label{tab:protocol}
\begin{tabular}{p{0.25\linewidth}p{0.66\linewidth}}\toprule
Step & Operation \\\midrule
Prepare & Create fresh isolated agents; give both arms the same fact episode. \\
Construct & Write the baseline file; seed retrieved L1 through separate fact conversations. \\
Query & Use a fresh conversation, no tools, one model iteration, and the assigned section budget. \\
Audit & Check actual prompt injection and isolated history before accepting a pair. \\
Aggregate & Match question IDs; count writes once per run; preserve excluded attempts in costs. \\
\bottomrule\end{tabular}\end{table}
'''


def attach_research_assets(results, output, methodology_image=None, *, include_methodology=True):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import ListedColormap

    figures = output / 'figures'
    figures.mkdir(exist_ok=True)
    image = methodology_image or MODULE / 'assets/methodology-v2.png'
    if include_methodology and not image.is_file():
        raise ValueError('Research profile requires a reviewed methodology image')
    if include_methodology:
        shutil.copy2(image, figures / 'methodology.png')
    outputs = ['methodology.png'] if include_methodology else []
    figure = r'''
\begin{figure}[htbp]
\centering\includegraphics[width=\linewidth]{figures/methodology.png}
\caption{Budget-matched evaluation of two operational memory paths. The retrieved arm
incurs model-backed write cost before its isolated query. Equal character caps include
each arm's own formatting overhead. This schematic illustrates the audited implementation;
it is not an experimental result.}
\label{fig:methodology}\end{figure}
'''
    if not include_methodology:
        figure = ''
    # One overview replaces repetitive per-budget charts in the research profile.
    colors = ['#355C7D', '#168F86']
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3.0), layout='constrained')
    for i, result in enumerate(results):
        for j, group in enumerate(('baseline', 'enhanced')):
            stats = result['groups'][group]
            x = i + (j - .5) * .25
            low, high = stats['accuracy_ci_low'], stats['accuracy_ci_high']
            axes[0].errorbar(x, stats['accuracy'] * 100,
                yerr=[[100*(stats['accuracy']-low)], [100*(high-stats['accuracy'])]],
                fmt='o', color=colors[j], capsize=4, label=group.title() if i == 0 else None)
            total = stats['tokens_per_question']
            if total is not None:
                query = stats['query_tokens'] / stats['n']
                write = stats['seed_tokens'] / stats['n']
                axes[1].bar(i*2+j, query, color=colors[j], width=.65)
                axes[1].bar(i*2+j, write, bottom=query, color=colors[j], alpha=.35, hatch='//', width=.65)
                axes[1].text(i*2+j, total+max(50,total*.025), f'{total:,.0f}', ha='center', fontsize=8)
    def _budget_label(r):
        return str(r.get('context_chars') or r.get('context_tokens', '?'))
    axes[0].set(xticks=list(range(len(results))), xticklabels=[_budget_label(r) for r in results],
                xlabel='Memory-section budget', ylabel='Answer accuracy (%)', ylim=(-4,105),
                title='Accuracy with descriptive Wilson intervals')
    axes[0].legend(frameon=False, fontsize=8, loc='lower right')
    axes[1].set(xticks=list(range(len(results)*2)),
                xticklabels=[f'{_budget_label(r)}\n{g}' for r in results for g in ('File','L1')],
                ylabel='Tokens per paired question', title='Write cost dominates retrieved memory')
    axes[1].text(.03,.96,'Solid: query   Hatched: writes',transform=axes[1].transAxes,fontsize=8,va='top')
    axes[1].margins(y=.24)
    for ax in axes:
        ax.spines[['top','right']].set_visible(False)
        ax.tick_params(labelsize=8)
        ax.grid(axis='y',alpha=.17)
        ax.title.set_fontsize(9)
    for ext in ('pdf','png','svg'):
        name='quality_cost_overview.'+ext
        fig.savefig(figures/name,dpi=260,bbox_inches='tight')
        outputs.append(name)
    plt.close(fig)
    ordered = results[0]['observed_cases']
    ids = [(c['repeat'],c['question_id']) for c in ordered]
    columns=[]
    labels=[]
    for result in results:
        by_id={(c['repeat'],c['question_id']):c for c in result['observed_cases']}
        if set(by_id)!=set(ids):
            raise ValueError('Cross-budget diagnostic requires identical question pairs')
        for group in ('baseline','enhanced'):
            for metric in ('correct','evidence_recall'):
                columns.append([float(by_id[key][group][metric]) for key in ids])
                labels.append(f'{_budget_label(result)} {"File" if group=="baseline" else "L1"}\n{"Answer" if metric=="correct" else "Evidence"}')
    fig,ax=plt.subplots(figsize=(7.4,4.7),layout='constrained')
    ax.imshow(np.array(columns).T,cmap=ListedColormap(['#E9EDF1','#168F86']),vmin=0,vmax=1,aspect='auto')
    ax.set_xticks(range(len(labels)),labels,fontsize=8)
    ax.set_yticks(range(len(ids)),[f'Q{i+1:02d}' for i in range(len(ids))],fontsize=7)
    ax.tick_params(length=0)
    ax.set_title('Per-question audit: filled = correct answer / complete evidence',fontsize=10,pad=12)
    for y in range(len(ids)-1): ax.axhline(y+.5,color='white',lw=1)
    for x in (1.5,3.5,5.5): ax.axvline(x,color='white',lw=3)
    for ext in ('pdf','png','svg'):
        name='question_audit.'+ext
        fig.savefig(figures/name,dpi=260,bbox_inches='tight')
        outputs.append(name)
    plt.close(fig)
    diagnostic = r'''
\begin{figure}[htbp]\centering
\includegraphics[width=\linewidth]{figures/quality_cost_overview.pdf}
\caption{Quality and resource tradeoff. Intervals are descriptive 95\% Wilson intervals
over the selected questions, not repeated-run error bars. Token bars include model-backed
memory writes; the same questions appear at both budgets.}
\label{fig:overview}\end{figure}
\begin{figure}[htbp]\centering
\includegraphics[width=\linewidth]{figures/question_audit.pdf}
\caption{Matched question-level correctness and full-evidence recall across both budgets.
Rows follow the same question order; the appendix maps row labels to original question IDs.
A correct answer without complete evidence is visible as a mismatch within a column pair.}
\label{fig:audit}\end{figure}
'''
    appendix = [r'\clearpage\appendix',r'\section{Question-level audit and reproducibility}',
                'The following identifiers link directly to the submitted raw records. A and E denote '
                'answer correctness and complete-evidence recall. These are recorded single-run outcomes, '
                'not independent replications across budgets.']
    for result in results:
        appendix += [r'\begin{table}[htbp]\centering\scriptsize',
                     r'\caption{Question audit at the '+str(_budget_label(result))+r'-token budget.}',
                     r'\begin{tabular}{llrrrr}\toprule Row & Original question ID & File A & File E & L1 A & L1 E \\\midrule']
        for i,c in enumerate(result['observed_cases']):
            values=[str(int(c[g][m])) for g in ('baseline','enhanced') for m in ('correct','evidence_recall')]
            appendix.append(f'Q{i+1:02d} & '+latex_text(c['question_id'])+' & '+' & '.join(values)+r' \\')
        appendix += [r'\bottomrule\end{tabular}\end{table}']
    appendix += [r'\clearpage\section{Observed diagnostic cases}',
                 'Cases below are selected deterministically for diagnostic categories, not as a random '
                 'qualitative sample. Answers are verbatim recorded outputs; questions are copied from the adapted dataset.']
    selected=[]
    for result in results:
        for c in result['observed_cases']:
            category=('partial evidence' if c['baseline']['correct'] and c['baseline']['evidence_recall']<1 else
                      'retrieval failure' if not c['enhanced']['correct'] else
                      'retrieved-only success' if c['outcome']=='enhanced_only' else None)
            if category and category not in [x[0] for x in selected]: selected.append((category,result,c))
    for category,result,c in selected:
        appendix += [r'\paragraph{'+latex_text(category.title())+'.} '+latex_text(
            f"Budget {_budget_label(result)}; question {c['question_id']}."),
            r'\textbf{Question:} '+latex_text(c['query']),
            r'\textbf{Accepted answer:} '+latex_text('; '.join(c['accepted_answers'])),
            r'\textbf{File answer:} '+latex_text(str(c['baseline']['answer'])),
            r'\textbf{Retrieved answer:} '+latex_text(str(c['enhanced']['answer']))]
    illustration_note = (
        'The methodology schematic is AI-generated and checked against the implementation; '
        if include_methodology else
        'The conceptual diagrams are AI-generated from source-linked method specifications. '
        'Their design contracts, prompts and declared review status are included; '
        'human scientific review remains required. ')
    appendix += [r'\section{Artifact and generation provenance}',
                 'The submission includes the adapted data, original write/query records, normalization '
                 'code, citation metadata and a hashed source snapshot. Writing assistance uses a separate '
                 'model from the experimental query model. Its actual requests, generated text and usage '
                 'are saved separately; none of those calls contributes to the experimental accuracy. '
                 + illustration_note +
                 'All empirical plots and tables are rendered programmatically from the recorded data.']
    (output/'appendix.tex').write_text('\n\n'.join(appendix)+'\n',encoding='utf-8')
    return figure, diagnostic, outputs
