"""Run v2 fair baselines, causal controls, lifecycle reuse, or offline retrieval."""

from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import logging
from pathlib import Path
import subprocess
import sys

from memory_eval import PROTOCOL_VERSION
from memory_eval.data import HERE, episode_cache, evidence_metrics, lifecycle_episodes, load_source, micro_episodes, read_json
from memory_eval.runtime import Journal, arm_definitions, execute_episode
from agent_memory_ab import model_entry
from jiuwenswarm.agents.harness.common.memory.controlled_retrieval import FrozenMemoryIndex, PinnedTokenizer, canonical_hash
from jiuwenswarm.common.config import resolve_env_vars


def entry_for(args, protocol):
    if args.self_test or args.offline_retrieval:
        return {}
    from dotenv import load_dotenv
    import yaml
    if args.env_file:
        load_dotenv(args.env_file, override=True)
    entry = model_entry(resolve_env_vars(yaml.safe_load(args.config.read_text(encoding="utf-8"))))
    entry = deepcopy(entry)
    entry["model_client_config"].update(model_name=protocol["solver_model"], max_retries=0, timeout=90)
    entry["model_config_obj"] = dict(protocol["decoding"])
    return entry


def execution_fingerprint(protocol, args):
    paths = [
        HERE / "run_memory_eval.py", HERE / "memory_eval/data.py", HERE / "memory_eval/runtime.py",
        HERE.parent / "jiuwenswarm/agents/harness/common/memory/controlled_retrieval.py",
        HERE.parent / "jiuwenswarm/agents/harness/common/memory/retrieval_engine.py",
        HERE.parent / "jiuwenswarm/agents/harness/common/rails/token_budget_memory_rail.py",
    ]
    code = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE, text=True).strip()
    return {
        "kind": ("memory_eval_v2_self_test" if args.self_test else
                 "memory_eval_v2_retrieval" if args.offline_retrieval else "memory_eval_v2_live"),
        "protocol": protocol, "protocol_sha256": canonical_hash(protocol), "code_hashes": code,
        "git_commit": commit, "official_longmemeval_score": False,
        "execution": {"suite": args.suite, "repeats": args.repeats,
                      "budgets": args.budgets, "selectors": args.selectors,
                      "max_episodes": args.max_episodes, "lifecycle_episodes": args.lifecycle_episodes,
                      "self_test": args.self_test, "offline_retrieval": args.offline_retrieval},
        "request_schedule": {"spacing_seconds": 0.65, "rate_limit_cooldown_seconds": 60},
        "model_name": "deterministic-self-test" if args.self_test else protocol["solver_model"],
    }


async def run(args):
    protocol = read_json(args.protocol)
    deps = protocol["dependencies"]
    tokenizer = PinnedTokenizer(HERE / "data/public/qwen3_tokenizer/tokenizer.json",
                                deps["tokenizer_files"]["tokenizer.json"])
    source = load_source(args.source)
    entry = entry_for(args, protocol)
    manifest = execution_fingerprint(protocol, args)
    args.output.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output / "run_manifest.json"
    if manifest_path.is_file() and read_json(manifest_path) != manifest:
        raise ValueError("Resume requires identical protocol, execution options and code hashes; use a new output directory")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    journal = Journal(args.output)
    cache = HERE / "data/public/memory_eval_v2_cache"
    try:
        if args.offline_retrieval:
            selected = source[:args.max_episodes] if args.max_episodes else source
            for index, example in enumerate(selected):
                episode = episode_cache(example, tokenizer, cache, chunk_tokens=protocol["chunk_body_tokens"])
                bank = FrozenMemoryIndex(episode["records"])
                q = episode["questions"][0]
                for strategy in args.selectors or protocol["selectors"]:
                    ranking = bank.rank(q["query"], strategy, q["reference_time"])
                    ranked = journal.artifact("rankings", {"question_id": q["id"], "candidate_hash": bank.content_hash,
                                                           "strategy": strategy, "scores": ranking})
                    for budget in args.budgets:
                        key = f"retrieval:{q['id']}:{strategy}:{budget}"
                        if key in journal.trials:
                            continue
                        packed = bank.pack(ranking, tokenizer, budget)
                        metrics = evidence_metrics(episode, q, packed["selected_ids"])
                        journal.append("trials", {
                            "trial_id": key, "suite": "retrieval", "memory_id": episode["memory_id"],
                            "question_id": q["id"], "question_type": q["question_type"], "abstention": q["abstention"],
                            "arm": strategy, "budget_tokens": budget, "memory_tokens": packed["memory_tokens"],
                            "selected_ids": packed["selected_ids"], "candidate_hash": bank.content_hash,
                            "ranking": ranked, "required_sessions": q["required_sessions"], **metrics, "status": "ok",
                        })
                if (index + 1) % 10 == 0:
                    print(f"Retrieval {index + 1}/{len(selected)}", flush=True)
            return
        semaphore = asyncio.Semaphore(args.concurrency)
        suites = ["full", "micro", "reuse"] if args.suite == "all" else [args.suite]
        for suite in suites:
            if suite == "full":
                ids = set(protocol["question_ids"])
                examples = sorted((row for row in source if row["question_id"] in ids),
                                  key=lambda row: row["question_id"])
                if args.max_episodes:
                    examples = examples[:args.max_episodes]
                episodes = [episode_cache(row, tokenizer, cache, chunk_tokens=protocol["chunk_body_tokens"])
                            for row in examples]
            elif suite == "micro":
                episodes = micro_episodes(HERE / "data/longmemeval_s_turn20_v1.json")
                if args.max_episodes:
                    episodes = episodes[:args.max_episodes]
            else:
                episodes = lifecycle_episodes(HERE / "data/memory_agent_qa_v2.json", count=args.lifecycle_episodes)
                if args.max_episodes:
                    episodes = episodes[:args.max_episodes]
            arms = arm_definitions(suite)
            if args.selectors:
                arms = [arm for arm in arms if arm["id"] in args.selectors]
            if not arms:
                raise ValueError(f"No requested arms in suite {suite}")
            # Only one shared bank serves 20 distinct queries in the reuse suite.
            budgets = [args.budgets[0]] if suite == "reuse" else args.budgets
            for repeat in range(args.repeats):
                done = 0
                async def job(episode):
                    nonlocal done
                    async with semaphore:
                        await execute_episode(episode, suite, repeat, arms, budgets, entry, journal,
                                              tokenizer, self_test=args.self_test)
                        done += 1
                        print(f"{suite} repeat {repeat + 1}/{args.repeats}: {done}/{len(episodes)} episodes; "
                              f"{len(journal.trials)} saved trials", flush=True)
                await asyncio.gather(*(job(episode) for episode in episodes))
    finally:
        journal.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=HERE / "data/memory_eval_protocol_v2.json")
    parser.add_argument("--source", type=Path, default=HERE / "data/public/longmemeval_s_cleaned.json")
    parser.add_argument("--config", type=Path, default=HERE.parent / "jiuwenswarm/resources/config.yaml")
    parser.add_argument("--env-file", type=Path, default=HERE.parent / ".env")
    parser.add_argument("--output", type=Path, default=HERE / "results/memory_eval_v2")
    parser.add_argument("--suite", choices=["all", "full", "micro", "reuse"], default="all")
    parser.add_argument("--budgets", type=int, nargs="+", default=[512, 1024, 2048])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--selectors", nargs="+", default=None)
    parser.add_argument("--max-episodes", type=int, default=0)
    parser.add_argument("--lifecycle-episodes", type=int, default=8)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--offline-retrieval", action="store_true")
    args = parser.parse_args()
    if (args.repeats < 1 or args.concurrency < 1 or args.max_episodes < 0
            or args.lifecycle_episodes < 1 or min(args.budgets) < 32
            or len(set(args.budgets)) != len(args.budgets)):
        parser.error("Invalid counts or token budgets")
    if args.self_test and args.offline_retrieval:
        parser.error("Select self-test or offline-retrieval")
    logging.disable(logging.WARNING)
    asyncio.run(run(args))
    print(f"Saved append-only evidence: {args.output}")
    if args.self_test:
        print("SELF-TEST: not model performance evidence")


if __name__ == "__main__":
    main()
