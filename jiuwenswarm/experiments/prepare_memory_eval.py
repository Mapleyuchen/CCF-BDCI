"""Freeze the v2 protocol before any model answers are generated."""

from pathlib import Path
import argparse
import json

from memory_eval.data import HERE, load_source, prepare_manifest, read_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=HERE / "data/public/longmemeval_s_cleaned.json")
    parser.add_argument("--output", type=Path, default=HERE / "data/memory_eval_protocol_v2.json")
    parser.add_argument("--per-stratum", type=int, default=12)
    args = parser.parse_args()
    if args.per_stratum <= 0:
        parser.error("per-stratum must be positive")
    manifest = prepare_manifest(load_source(args.source), read_json(HERE / "data/memory_eval_dependencies_v2.json"),
                                per_stratum=args.per_stratum)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Frozen {len(manifest['question_ids'])} QA questions; retrieval uses all 500: {args.output}")


if __name__ == "__main__":
    main()
