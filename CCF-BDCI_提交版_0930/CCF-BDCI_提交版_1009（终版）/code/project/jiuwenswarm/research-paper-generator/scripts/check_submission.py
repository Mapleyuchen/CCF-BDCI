#!/usr/bin/env python3
"""Check a contest submission directory for required files and accidental secrets."""

import argparse
from pathlib import Path

from paper_quality.submission import check_submission


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Unzipped team directory, not the zip itself")
    args = parser.parse_args()
    try:
        report = check_submission(args.bundle)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")
    print(f"Submission report: {(args.bundle.resolve().parent / 'submission_report.json')}")
    summary = report["summary"]
    print(f"passed={summary['passed']} errors={summary['errors']} warnings={summary['warnings']}")
    for item in report["checks"]:
        if item["passed"]:
            continue
        where = f" [{item['target']}]" if item.get("target") else ""
        print(f"{item['severity'].upper()} {item['id']}{where}: {item['message']}")
    if not report["ready_for_submission"]:
        parser.exit(1, "Submission bundle is incomplete.\n")


if __name__ == "__main__":
    main()
