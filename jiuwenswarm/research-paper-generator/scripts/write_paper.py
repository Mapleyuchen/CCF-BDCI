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
    parser.add_argument("--brief", type=Path, default=module / "examples/memory-research.brief.json")
    parser.add_argument("--literature", type=Path, default=module / "examples/memory-research.literature.json")
    parser.add_argument("--config", type=Path, default=module / "examples/dashscope-research.yaml")
    parser.add_argument("--model", help="Override the writing model only; experimental model identities are preserved")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--related-work", type=Path)
    parser.add_argument("--methodology-image", type=Path, help="Reviewed methodology PNG for the research profile")
    parser.add_argument("--generate-methodology", action="store_true", help="Call DashScope image API before writing; requires images config and DASHSCOPE_API_KEY")
    parser.add_argument("--resume-from", type=Path, help="Previous paper directory with saved editorial stages; evidence and instructions must match")
    parser.add_argument("--output", type=Path, required=True, help="New run directory containing framework/ and paper/")
    parser.add_argument("--compile", action="store_true", dest="compile_pdf")
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("Output directory already exists; select a new run directory")
        config = load_model_config(args.config, args.env_file)
        if args.generate_methodology and args.methodology_image:
            raise ValueError("Choose --generate-methodology or --methodology-image")
        if args.generate_methodology:
            from generate_methodology import generate
            args.methodology_image = args.output / "image-api" / "methodology.png"
            generate(args.config, args.methodology_image)
        if args.model:
            config["client"]["model_name"] = args.model
        model = JsonModel(config)
        generate_project(args.brief, args.output / "framework", args.literature)
        print("Framework ready; validating experiment records and requesting model prose...", flush=True)
        report = fill_project(args.output / "framework", args.output / "paper", model=model,
                              related_work=args.related_work, compile_pdf=args.compile_pdf,
                              methodology_image=args.methodology_image, resume_from=args.resume_from)
        print(f"Content: {args.output.resolve() / 'paper'}", flush=True)
        print(f"Status: {report['status']}; quality: {report['quality']}; human review required.")
        print(f"Model calls: {len(report['calls'])}")
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"Paper pipeline failed: {error}\n")
    if report["status"] == "quality_failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
