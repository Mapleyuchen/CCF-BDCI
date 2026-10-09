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
    curated_brief = module / "examples/memory-eval-v2.paper-brief.json"
    revised_brief = curated_brief if curated_brief.is_file() else module / "examples/memory-eval-v2.brief.json"
    default_brief = revised_brief if revised_brief.is_file() else module / "examples/memory-research.brief.json"
    parser.add_argument("--brief", type=Path, default=default_brief,
                        help="Prefer the completed v2 experimental handoff when present; explicit --brief replays older studies")
    parser.add_argument("--literature", type=Path, default=module / "examples/memory-research.literature.json")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--config", type=Path, help="Live writer configuration; defaults to examples/dashscope-research.yaml")
    source.add_argument("--content-json", type=Path, help="Replay saved prose offline; no model configuration or API calls")
    parser.add_argument("--model", help="Override the writing model only; experimental model identities are preserved")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--related-work", type=Path)
    parser.add_argument("--methodology-image", type=Path, help="Reviewed methodology PNG for the research profile")
    parser.add_argument("--generate-methodology", "--generate-illustrations", dest="generate_methodology", action="store_true", help="One-pass research-aware diagrams via DashScope before writing")
    parser.add_argument("--illustration-manifest", type=Path, help="Reuse a recorded diagram bundle without image API calls")
    parser.add_argument("--review-mode", choices=("fast", "reviewed"), default="fast", help="Default: one planning call and one writing call; reviewed enables extra model reviews")
    parser.add_argument("--max-figures", type=int, default=2)
    parser.add_argument("--max-redraws", type=int, default=0, help="Only with --review-mode reviewed; default no redraw")
    parser.add_argument("--illustration-resume-from", type=Path, help="Reuse saved illustration stages/tasks with identical inputs")
    parser.add_argument("--resume-from", type=Path, help="Previous paper directory with saved editorial stages; evidence and instructions must match")
    parser.add_argument("--output", type=Path, required=True, help="New run directory containing framework/ and paper/")
    parser.add_argument("--compile", action="store_true", dest="compile_pdf")
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("Output directory already exists; select a new run directory")
        if args.review_mode == "fast" and (args.max_redraws or args.resume_from):
            raise ValueError("Redraws/editorial resume require --review-mode reviewed")
        if args.content_json:
            if args.model or args.env_file or args.generate_methodology or args.resume_from:
                raise ValueError("--content-json cannot be combined with --model, --env-file, --generate-methodology or --resume-from")
            if not args.content_json.is_file():
                raise ValueError(f"Saved content file does not exist: {args.content_json}")
            model = None
        else:
            config = load_model_config(args.config or module / "examples/dashscope-research.yaml", args.env_file)
            if args.model:
                config["client"]["model_name"] = args.model
            model = JsonModel(config)
        if sum(bool(v) for v in (args.generate_methodology, args.methodology_image, args.illustration_manifest)) > 1:
            raise ValueError("Choose generated illustrations, a reviewed manifest, or a legacy methodology image")
        if args.illustration_resume_from and not args.generate_methodology:
            raise ValueError("--illustration-resume-from requires --generate-illustrations")
        generate_project(args.brief, args.output / "framework", args.literature)
        if args.generate_methodology:
            from paper_illustration.pipeline import run_illustrations
            args.illustration_manifest = run_illustrations(args.output / "framework", args.output / "illustrations",
                JsonModel(config), args.config or module / "examples/dashscope-research.yaml",
                max_figures=args.max_figures, max_redraws=args.max_redraws, resume_from=args.illustration_resume_from,
                review_mode=args.review_mode)
        action = "rendering saved prose offline" if args.content_json else "requesting model prose"
        print(f"Framework ready; validating experiment records and {action}...", flush=True)
        report = fill_project(args.output / "framework", args.output / "paper", model=model,
                              content_json=args.content_json,
                              related_work=args.related_work, compile_pdf=args.compile_pdf,
                              methodology_image=args.methodology_image, resume_from=args.resume_from,
                              illustration_manifest=args.illustration_manifest, writing_mode=args.review_mode)
        print(f"Content: {args.output.resolve() / 'paper'}", flush=True)
        print(f"Status: {report['status']}; quality: {report['quality']}; human review required.")
        print(f"Model calls: {len(report['calls'])}")
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"Paper pipeline failed: {error}\n")
    if report["status"] == "quality_failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
