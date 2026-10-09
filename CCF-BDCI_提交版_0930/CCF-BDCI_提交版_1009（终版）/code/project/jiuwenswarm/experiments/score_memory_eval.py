"""Run the pinned, arm-blind semantic judge; keep all judge costs separate."""

import argparse
import asyncio
from pathlib import Path

from memory_eval.data import HERE
from memory_eval.scoring import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=HERE / "results/memory_eval_v2")
    parser.add_argument("--config", type=Path, default=HERE.parent / "jiuwenswarm/resources/config.yaml")
    parser.add_argument("--env-file", type=Path, default=HERE.parent / ".env")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--audit-model", default="qwen-plus-2025-12-01")
    parser.add_argument("--judge-model", default=None, help="Explicit scorer-only override, recorded in scoring_manifest")
    args = parser.parse_args()
    asyncio.run(evaluate(args.run, args.config, args.env_file,
                         concurrency=args.concurrency, audit_model=args.audit_model or None,
                         judge_model=args.judge_model))


if __name__ == "__main__":
    main()
