#!/usr/bin/env python3
"""Check a paper-framework directory for completeness, format, and surface writing issues."""

import argparse
from pathlib import Path

from paper_quality.checker import check_project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Directory produced by generate_framework.py")
    args = parser.parse_args()
    try:
        report = check_project(args.project)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")
    print(f"Quality report: {(args.project.resolve() / 'quality_report.json')}")
    summary = report["summary"]
    print(f"passed={summary['passed']} errors={summary['errors']} warnings={summary['warnings']}")
    for item in report["checks"]:
        if item["passed"]:
            continue
        where = f" [{item['target']}]" if item.get("target") else ""
        print(f"{item['severity'].upper()} {item['id']}{where}: {item['message']}")
    if not report["ready_for_submission"]:
        parser.exit(1, "Not ready for submission.\n")


if __name__ == "__main__":
    main()
