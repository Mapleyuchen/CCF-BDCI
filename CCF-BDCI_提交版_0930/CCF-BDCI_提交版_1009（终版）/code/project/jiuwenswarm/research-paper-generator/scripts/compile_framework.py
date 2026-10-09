#!/usr/bin/env python3
"""Recompile a framework after the content author edits its section files."""

import argparse
from pathlib import Path

from paper_framework.compiler import compile_project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    try:
        print(compile_project(args.project))
    except (ValueError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
