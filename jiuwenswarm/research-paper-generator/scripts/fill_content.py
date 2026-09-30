#!/usr/bin/env python3
"""Fill an ICLR framework using verified live measurements and model-written prose."""

import argparse
import json
from pathlib import Path

from paper_content.model import JsonModel, load_model_config
from paper_content.project import fill_project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("framework", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="A new directory; original framework is preserved")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path, help="JiuwenSwarm-compatible model YAML")
    source.add_argument("--content-json", type=Path, help="Render/review saved structured prose without another API call")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--model", help="Override the writing model from --config")
    parser.add_argument("--related-work", type=Path, help="Reviewed JSON paragraphs using [[cite:source_id]] tokens")
    parser.add_argument("--compile", action="store_true", dest="compile_pdf")
    args = parser.parse_args()
    try:
        config = load_model_config(args.config, args.env_file) if args.config else None
        if args.model and config is None:
            raise ValueError("--model requires --config")
        if args.model:
            config["client"]["model_name"] = args.model
        model = JsonModel(config) if config else None
        report = fill_project(args.framework, args.output, model=model, content_json=args.content_json,
                              related_work=args.related_work, compile_pdf=args.compile_pdf)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"Content generation failed: {error}\n")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if report["status"] == "quality_failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
