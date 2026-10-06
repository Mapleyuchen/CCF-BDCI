"""Grade saved answers while generation continues; audit only after it finishes."""
import argparse
import asyncio
from pathlib import Path
import time
from memory_eval.data import HERE, read_json
from memory_eval.reporting import expected_trials, records
from memory_eval.scoring import evaluate


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=HERE / "results/memory_eval_v2")
    parser.add_argument("--config", type=Path, default=HERE.parent / "jiuwenswarm/resources/config.yaml")
    parser.add_argument("--env-file", type=Path, default=HERE.parent / ".env")
    parser.add_argument("--audit-model", default="qwen-plus-2025-12-01")
    args = parser.parse_args()
    last_count = 0
    while True:
        try:
            manifest = read_json(args.run / "run_manifest.json")
            expected = sum(expected_trials(manifest).values())
            count = len(records(args.run, "trials", "trial_id"))
        except (FileNotFoundError, ValueError):
            await asyncio.sleep(15)
            continue
        if count == expected or count - last_count >= 200:
            await evaluate(args.run, args.config, args.env_file, concurrency=8,
                           audit_model=args.audit_model if count == expected else None)
            last_count = count
            print(f"Scoring snapshot: {count}/{expected} solver trials", flush=True)
            if count == expected:
                break
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
