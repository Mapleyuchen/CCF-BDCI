"""Run a paired DeepAgent experiment on the adapted LongMemEval-S turn slice.

This evaluates 20-turn, single-session-user episodes. It is not an official
LongMemEval-S score; answer string matching is provisional.
"""

from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import yaml

from agent_memory_ab import (
    experiment_workspace,
    isolated_project_memory_sources,
    model_entry,
    run_group,
    summarize,
)
from jiuwenswarm.agents.harness.common.memory.experiment_config import (
    code_memory_experiment_group,
)
from jiuwenswarm.common.config import resolve_env_vars


HERE = Path(__file__).parent


def load_slice(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    episodes = data.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        raise ValueError("Adapted dataset has no episodes")
    ids = set()
    for episode in episodes:
        q = episode["questions"]
        facts = episode["facts"]
        if (episode["id"] in ids or len(facts) != 20 or len(q) != 1
                or q[0]["id"] != episode["id"]
                or len(q[0]["relevant_ids"]) != 1):
            raise ValueError(f"Invalid episode: {episode['id']}")
        ids.add(episode["id"])
        fact_ids = {fact["id"] for fact in facts}
        if len(fact_ids) != 20 or q[0]["relevant_ids"][0] not in fact_ids:
            raise ValueError(f"Invalid evidence id: {episode['id']}")
    return data


async def run(args: argparse.Namespace) -> dict[str, Any]:
    data = load_slice(args.dataset)
    episodes = data["episodes"][:args.max_cases] if args.max_cases else data["episodes"]
    if args.self_test:
        config: dict[str, Any] = {}
        entry: dict[str, Any] = {}
    else:
        if not args.config.is_file():
            raise FileNotFoundError(f"Model config not found: {args.config}")
        config = resolve_env_vars(yaml.safe_load(args.config.read_text(encoding="utf-8")) or {})
        entry = model_entry(config)
    rows: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    with isolated_project_memory_sources():
        with experiment_workspace(args.output.parent, "longmemeval-turn20-ab-") as temp:
            for index, episode in enumerate(episodes):
                order = ("baseline", "enhanced") if index % 2 == 0 else ("enhanced", "baseline")
                for group in order:
                    group_config = deepcopy(config)
                    group_config.setdefault("modes", {}).setdefault("code", {}).setdefault(
                        "memory", {}
                    )["experiment_group"] = group
                    assert code_memory_experiment_group(group_config) == group
                    workspace = Path(temp) / f"case-{index:03d}-{group}"
                    workspace.mkdir()
                    case_rows, run_info = await run_group(
                        group_config, 0, episode["questions"], episode["facts"], workspace, entry,
                        context_chars=args.context_chars, top_k=args.top_k,
                        self_test=args.self_test,
                    )
                    for row in case_rows:
                        row["source_question_id"] = episode["id"]
                        row["question_type"] = episode["question_type"]
                    run_info["source_question_id"] = episode["id"]
                    rows.extend(case_rows)
                    runs.append(run_info)
    summary = summarize(rows, runs)
    return {
        "kind": "adapted_longmemeval_self_test" if args.self_test else "adapted_longmemeval_live",
        "official_longmemeval_score": False,
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "source_url": data["source_url"],
        "source_sha256": data["source_sha256"],
        "source_citation": data["source_citation"],
        "selection_rule": data["selection_rule"],
        "scoring_note": (
            "Answer accuracy uses a provisional accepted-answer substring check. "
            "Inspect raw answers or use a separately documented judge before publication."
        ),
        "settings": {
            "model_name": "deterministic-self-test" if args.self_test else entry["model_client_config"]["model_name"],
            "context_chars": args.context_chars,
            "top_k": args.top_k,
            "episodes": len(episodes),
            "turns_per_episode": 20,
            "max_iterations": 1,
            "tools": [],
        },
        "summary": summary,
        "runs": runs,
        "records": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path,
                        default=HERE / "data" / "longmemeval_s_turn20_v1.json")
    parser.add_argument("--config", type=Path,
                        default=Path.home() / ".jiuwenswarm" / "config" / "config.yaml")
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--output", type=Path,
                        default=HERE / "results" / "longmemeval_s_turn20_pilot.json")
    parser.add_argument("--max-cases", type=int, default=3,
                        help="Pilot on 3 episodes; use 0 to run all 20")
    parser.add_argument("--context-chars", type=int, default=600)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.max_cases < 0 or min(args.context_chars, args.top_k) <= 0:
        parser.error("max-cases must be nonnegative; context-chars and top-k must be positive")
    if args.env_file is not None:
        if not args.env_file.is_file():
            parser.error(f"Environment file not found: {args.env_file}")
        load_dotenv(args.env_file, override=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    logging.disable(logging.INFO)
    try:
        report = asyncio.run(run(args))
    except (ValueError, FileNotFoundError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Raw records: {args.output}")
    if args.self_test:
        print("SELF-TEST ONLY: fake LLM results are not research evidence")
    if report["summary"]["paired"]["n"] == 0:
        raise SystemExit("No valid paired episodes; inspect errors in the result file")


if __name__ == "__main__":
    main()
