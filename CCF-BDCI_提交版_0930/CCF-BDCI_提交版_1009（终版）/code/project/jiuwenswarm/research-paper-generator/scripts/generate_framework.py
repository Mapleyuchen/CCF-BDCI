#!/usr/bin/env python3
"""Generate the module-3 paper skeleton; no network or LLM credentials needed."""

import argparse
from pathlib import Path

from paper_framework.project import DEFAULT_TEMPLATE, generate_project
from paper_framework.compiler import compile_project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, type=Path, help="Version-1 research brief JSON")
    parser.add_argument("--literature", type=Path, help="Literature-search JSON array; optional")
    parser.add_argument("--output", required=True, type=Path, help="New output directory (never overwritten)")
    parser.add_argument("--template-dir", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--compile", action="store_true", help="Compile the skeleton with pdflatex and BibTeX")
    args = parser.parse_args()
    try:
        manifest = generate_project(args.brief, args.output, args.literature, args.template_dir)
        print(f"Framework generated: {args.output.resolve()}")
        for warning in manifest["warnings"]:
            print(f"NOTE: {warning}")
        if args.compile:
            print(f"PDF: {compile_project(args.output)}")
    except (ValueError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
