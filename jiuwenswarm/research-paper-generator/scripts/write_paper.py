#!/usr/bin/env python3
"""Run framework -> content -> figures/BibTeX -> PDF/quality as one command."""

import argparse
from pathlib import Path

from paper_content.model import JsonModel, load_model_config
from paper_content.project import fill_project
from paper_framework.project import generate_project


def main():
    module = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", type=Path, default=module / "examples/memory-study.brief.json")
    parser.add_argument("--literature", type=Path, default=module / "examples/memory-study.literature.json")
    parser.add_argument("--config", type=Path, default=module / "examples/dashscope.yaml")
    parser.add_argument("--model", help="Override the writing model only; experimental model identities are preserved")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--related-work", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="New run directory containing framework/ and paper/")
    parser.add_argument("--compile", action="store_true", dest="compile_pdf")
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("Output directory already exists; select a new run directory")
        config = load_model_config(args.config, args.env_file)
        if args.model:
            config["client"]["model_name"] = args.model
        model = JsonModel(config)
        generate_project(args.brief, args.output / "framework", args.literature)
        print("Framework ready; validating experiment records and requesting model prose...", flush=True)
        report = fill_project(args.output / "framework", args.output / "paper", model=model,
                              related_work=args.related_work, compile_pdf=args.compile_pdf)
        print(f"Content: {args.output.resolve() / 'paper'}", flush=True)
        print(f"Status: {report['status']}; quality: {report['quality']}; human review required.")
        print(f"Model calls: {len(report['calls'])}")
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"Paper pipeline failed: {error}\n")
    if report["status"] == "quality_failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
