"""Validate complete evidence, compute clustered statistics, export paper assets."""
import argparse
from pathlib import Path
from memory_eval.reporting import build_report, export_pairs, figures_and_tables, retrieval_report, retrieval_figures, protocol_diagram, write_json

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, default=Path(__file__).parent / "results/memory_eval_v2")
    p.add_argument("--retrieval-run", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--retrieval-only", action="store_true")
    args = p.parse_args()
    destination = args.output or args.run / "report"
    destination.mkdir(parents=True, exist_ok=True)
    if args.retrieval_only:
        retrieval = retrieval_report(args.run)
        write_json(destination / "retrieval_summary.json", retrieval)
        retrieval_figures(destination, retrieval)
    else:
        summary, trials, constructions = build_report(args.run)
        write_json(destination / "summary.json", summary)
        export_pairs(destination / "paper_exports", summary, trials, constructions)
        figures_and_tables(destination, summary)
        if args.retrieval_run:
            retrieval = retrieval_report(args.retrieval_run)
            write_json(destination / "retrieval_summary.json", retrieval)
            retrieval_figures(destination, retrieval)
        protocol_diagram(destination)
    print(f"Validated report: {destination}")

if __name__ == "__main__":
    main()
