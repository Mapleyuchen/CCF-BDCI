#!/usr/bin/env python3
"""Plan research-aware figures once, then generate in parallel via DashScope APIs."""
import argparse
from pathlib import Path

from paper_content.model import JsonModel, load_model_config
from paper_illustration.pipeline import run_illustrations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("framework", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] / "examples/dashscope-research.yaml")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--max-figures", type=int, default=2)
    parser.add_argument("--review-mode", choices=("fast", "reviewed"), default="fast")
    parser.add_argument("--max-redraws", type=int, default=0)
    parser.add_argument("--resume-from", type=Path)
    args = parser.parse_args()
    try:
        config = load_model_config(args.config, args.env_file)
        if args.model:
            config["client"]["model_name"] = args.model
        result = run_illustrations(args.framework, args.output, JsonModel(config), args.config,
                                  max_figures=args.max_figures, max_redraws=args.max_redraws,
                                  resume_from=args.resume_from, review_mode=args.review_mode)
        print("Illustration manifest: " + str(result))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, "Illustration pipeline failed: " + str(error) + "\n")


if __name__ == "__main__":
    main()
