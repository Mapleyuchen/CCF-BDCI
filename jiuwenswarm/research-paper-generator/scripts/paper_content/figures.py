"""Render tables and exportable plots from normalized measurements."""

from __future__ import annotations

from pathlib import Path

from paper_framework.citations import latex_text


def table_tex(result, metrics):
    eid = result["id"]
    labels = result.get("group_labels", {"baseline": "Baseline", "enhanced": "Enhanced"})
    rows = []
    for label, name in (("Correct answers", "correct"), ("Paired observations", "n"),
                        ("Answer accuracy", "accuracy"), ("Evidence recall", "evidence_recall"),
                        ("Query tokens (total)", "query_tokens"), ("Write tokens (total)", "seed_tokens"),
                        ("Total tokens / paired observation", "tokens_per_question"),
                        ("Mean query latency (ms)", "query_latency_ms"),
                        ("Amortized total latency (ms)", "end_to_end_latency_ms"),
                        ("Excluded records", "excluded_records"), ("Failed questions", "failed_records")):
        if not all(f"{eid}.{g}.{name}" in metrics for g in ("baseline", "enhanced")):
            continue
        cells = [latex_text(metrics[f"{eid}.{group}.{name}"]["text"]) for group in ("baseline", "enhanced")]
        rows.append(latex_text(label) + " & " + " & ".join(cells) + r" \\")
    return ("\n\\begin{table}[htbp]\n\\centering\n\\small\n"
            + r"\caption{" + latex_text(result["title"] + ". Costs include memory writes; missing usage is not treated as zero.") + "}\n"
            + r"\label{tab:" + eid + "}\n"
            + "\\begin{tabular}{lrr}\n\\toprule\nMetric & " + latex_text(labels["baseline"]) + " & " + latex_text(labels["enhanced"]) + " \\\\\n\\midrule\n"
            + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")


def make_figures(results: list[dict], destination: Path) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    destination.mkdir(parents=True, exist_ok=True)
    colors = ("#335C81", "#D47C38")
    outputs = []
    for result in results:
        labels = result.get("group_labels", {"baseline": "Baseline", "enhanced": "Enhanced"})
        fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), layout="constrained")
        for index, (group, color) in enumerate(zip(("baseline", "enhanced"), colors)):
            stats = result["groups"][group]
            axes[0].bar([index * .34, 1 + index * .34],
                        [stats["accuracy"], stats["evidence_recall"]], width=.30,
                        color=color, label=labels[group], zorder=3)
            if result["kind"] == "controlled_memory_eval_live":
                axes[0].errorbar(index * .34, stats["accuracy"],
                                yerr=[[stats["accuracy"]-stats["accuracy_ci_low"]],
                                      [stats["accuracy_ci_high"]-stats["accuracy"]]],
                                fmt="none", ecolor="#222222", capsize=3, zorder=4)
            cost = stats["tokens_per_question"]
            if cost is None:
                axes[1].text(index, 0, "Not reported", ha="center", va="bottom", fontsize=8)
            else:
                axes[1].bar(index, cost, color=color, width=.55, zorder=3)
                axes[1].annotate(f"{cost:,.0f}", (index, cost), xytext=(0, 4),
                                 textcoords="offset points", ha="center", fontsize=8)
        axes[0].set_xticks([.17, 1.17], ["Answer accuracy", "Evidence recall"])
        axes[0].set_ylim(0, 1.15)
        axes[0].yaxis.set_major_formatter(PercentFormatter(1))
        axes[0].set_title("Paired answer quality", fontsize=10)
        axes[0].legend(frameon=False, fontsize=8, loc="upper left", ncols=2)
        axes[1].set_xticks([0, 1], [labels["baseline"], labels["enhanced"]])
        axes[1].set_title("Tokens per paired observation", fontsize=10)
        axes[1].set_ylabel("Including memory writes", fontsize=8)
        axes[1].margins(y=.22)
        for ax in axes:
            ax.spines[["top", "right"]].set_visible(False)
            ax.grid(axis="y", alpha=.2, zorder=0)
            ax.tick_params(labelsize=8)
        for suffix in ("png", "svg", "pdf"):
            name = f"{result['id']}.{suffix}"
            fig.savefig(destination / name, dpi=220, bbox_inches="tight")
            outputs.append(name)
        plt.close(fig)
    return outputs


def figure_tex(result):
    eid = result["id"]
    uncertainty = (" Accuracy error bars are 95% memory-cluster bootstrap intervals; repeated generations stay within their memory cluster. Failed questions remain in the denominator."
                   if result["kind"] == "controlled_memory_eval_live" else " No confidence interval is estimated.")
    return ("\n\\begin{figure}[htbp]\n\\centering\n"
            + r"\includegraphics[width=\linewidth]{figures/" + eid + ".pdf}\n"
            + r"\caption{" + latex_text(result["title"] + ". Quality and amortized total token cost on the same paired questions." + uncertainty) + "}\n"
            + r"\label{fig:" + eid + "}\n\\end{figure}\n")
