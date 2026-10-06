"""Pinned source data, outcome-independent sampling, and lossless memory chunks."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import random
import re
from uuid import uuid4

from jiuwenswarm.agents.harness.common.memory.controlled_retrieval import MemoryRecord, PinnedTokenizer, canonical_hash
from . import PROTOCOL_VERSION


HERE = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442"
TYPES = ("single-session-user", "single-session-assistant", "single-session-preference",
         "multi-session", "temporal-reasoning", "knowledge-update")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def timestamp(value: str) -> float:
    match = re.search(r"(\d{4})/(\d\d)/(\d\d).*?(\d\d):(\d\d)", value)
    if not match:
        raise ValueError(f"Unrecognized benchmark date: {value}")
    return datetime(*map(int, match.groups()), tzinfo=timezone.utc).timestamp()


def load_source(path: Path) -> list[dict]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("LongMemEval-S source differs from the pinned cleaned release")
    data = json.loads(raw)
    if len(data) != 500 or len({entry["question_id"] for entry in data}) != 500:
        raise ValueError("Expected all 500 unique LongMemEval-S examples")
    return data


def prepare_manifest(source: list[dict], dependencies: dict, *, per_stratum: int = 12, seed: int = 20261006) -> dict:
    strata = {kind: [row for row in source if row["question_type"] == kind
                     and "_abs" not in row["question_id"]] for kind in TYPES}
    strata["abstention"] = [row for row in source if "_abs" in row["question_id"]]
    selected = {}
    for kind, rows in strata.items():
        ordered = sorted(rows, key=lambda row: hashlib.sha256(
            f"{seed}:{row['question_id']}".encode()).hexdigest())
        if per_stratum > len(rows):
            raise ValueError(f"Only {len(rows)} questions in {kind}")
        selected[kind] = [row["question_id"] for row in ordered[:per_stratum]]
    return {
        "protocol_version": PROTOCOL_VERSION, "source_sha256": SOURCE_SHA256,
        "source_url": "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json",
        "source_count": 500, "source_license": "MIT", "dependencies": dependencies,
        "sampling_seed": seed, "per_stratum": per_stratum,
        "stratified_question_ids": selected,
        "question_ids": sorted(qid for ids in selected.values() for qid in ids),
        "budgets": [512, 1024, 2048], "repeats": 3, "chunk_body_tokens": 256,
        "solver_model": "qwen-plus-2025-12-01", "judge_model": "qwen3-max-2026-01-23",
        "decoding": {"temperature": 0, "max_tokens": 384, "enable_thinking": False},
        "selectors": ["prefix", "recency", "jaccard", "bm25", "hybrid", "hybrid_no_time"],
        "primary_comparison": ["hybrid", "bm25"],
        "confidence": 0.95, "bootstrap_seed": 20261007, "bootstrap_resamples": 10000,
        "protocol_deviations": [
            "Question-answer evaluation uses a deterministic stratified subset; retrieval evaluation covers all 500 histories.",
            "Original complete histories, questions, dates and gold answers are retained; histories are split losslessly into bounded turn segments.",
            "A frozen read-only single-layer bank is evaluated; the legacy 20-item EnhancedMemoryRail capacity is not asserted to support full histories.",
            "Token caps use the pinned public Qwen3-8B BPE; service-reported input/output tokens are logged separately and may differ.",
            "The original LongMemEval evaluation prompts are pinned; qwen3-max-2026-01-23 replaces its recommended GPT-4o judge.",
            "This is a LongMemEval-S subset with disclosed deviations, not an official leaderboard score.",
        ],
        "selection_rule": "Before generation, take the first fixed-hash-order 12 non-abstention questions in each of six categories and 12 abstention questions. No answer-length/content or outcome filter.",
    }


def full_episode(example: dict, tokenizer: PinnedTokenizer, *, chunk_tokens: int = 256) -> dict:
    records, evidence_turns = [], []
    for sid, date, session in zip(example["haystack_session_ids"], example["haystack_dates"],
                                  example["haystack_sessions"], strict=True):
        for turn_index, turn in enumerate(session):
            content = turn["content"]
            if not isinstance(content, str):
                raise ValueError("Non-text source turn")
            if turn.get("has_answer"):
                evidence_turns.append([sid, turn_index])
            for start, end, part in tokenizer.split(content, chunk_tokens):
                records.append(MemoryRecord(
                    item_id=f"M{len(records):05d}", content=part,
                    timestamp=timestamp(date), date=date, role=turn["role"],
                    session_id=sid, turn_index=turn_index, start=start, end=end,
                ))
    return {
        "memory_id": example["question_id"], "kind": "longmemeval_s_full_history",
        "records": records, "source_sessions": len(example["haystack_sessions"]),
        "evidence_turns": evidence_turns,
        "questions": [{
            "id": example["question_id"], "query": example["question"],
            "question_type": example["question_type"], "answer": str(example["answer"]),
            "question_date": example["question_date"], "reference_time": timestamp(example["question_date"]),
            "required_sessions": example["answer_session_ids"],
            "abstention": "_abs" in example["question_id"],
        }],
    }


def episode_cache(example: dict, tokenizer: PinnedTokenizer, cache: Path, *, chunk_tokens: int = 256) -> dict:
    key = canonical_hash([SOURCE_SHA256, example["question_id"], tokenizer.sha256, chunk_tokens])
    path = cache / f"{key}.json.gz"
    if path.is_file():
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                data = json.load(handle)
            data["records"] = [MemoryRecord(**row) for row in data["records"]]
            return data
        except (EOFError, json.JSONDecodeError):
            # An older worker might still be completing an uncommitted cache.
            pass
    data = full_episode(example, tokenizer, chunk_tokens=chunk_tokens)
    cache.mkdir(parents=True, exist_ok=True)
    serialized = {**data, "records": [asdict(record) for record in data["records"]]}
    temporary = path.with_name(path.name + f".{uuid4().hex}.tmp")
    temporary.write_bytes(gzip.compress(json.dumps(serialized, ensure_ascii=False).encode("utf-8"), mtime=0))
    try:
        temporary.replace(path)
    except PermissionError:
        # Windows denies replacement while another process reads the winner.
        # An identical content-addressed, fully readable cache is sufficient.
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                winner = json.load(handle)
            if canonical_hash(winner) != canonical_hash(serialized):
                raise ValueError("Concurrent cache contents differ")
        finally:
            temporary.unlink(missing_ok=True)
    return data


def micro_episodes(path: Path) -> list[dict]:
    data = read_json(path)
    episodes = []
    for source in data["episodes"]:
        records = []
        for i, fact in enumerate(source["facts"]):
            date_match = re.match(r"\[([^\]]+)\]", fact["text"])
            date = date_match.group(1) if date_match else "2023/05/30 (Tue) 23:40"
            records.append(MemoryRecord(
                item_id=fact["id"], content=fact["text"], timestamp=timestamp(date),
                date=date, role="source", session_id=source["id"], turn_index=i,
                end=len(fact["text"]),
            ))
        q = source["questions"][0]
        episodes.append({
            "memory_id": source["id"], "kind": "adapted_turn20",
            "records": records, "evidence_turns": [],
            "questions": [{"id": q["id"], "query": q["query"], "answer": q["answers"][0],
                           "answers": q["answers"], "required_items": q["relevant_ids"],
                           "question_type": source["question_type"], "abstention": False,
                           "reference_time": max(record.timestamp for record in records) + 3600,
                           "question_date": "after all provided records"}],
        })
    return episodes


def lifecycle_episodes(path: Path, *, count: int = 8, seed: int = 20261008) -> list[dict]:
    """Independent entity/value variants of a fixed synthetic 20-query workload."""
    data = read_json(path)
    names = ["Atlas", "Beacon", "Cedar", "Delta", "Echo", "Falcon", "Grove", "Harbor",
             "Iris", "Juniper", "Kestrel", "Lunar", "Maple", "Nimbus", "Orion",
             "Pine", "Quartz", "River", "Summit", "Terra"]
    values = {
        "PostgreSQL": ["MySQL", "MariaDB", "SQLite"],
        "Mailgun": ["SendGrid", "Amazon SES", "Postmark"],
        "React": ["Vue", "Svelte", "Angular"],
        "Frankfurt": ["Tokyo", "Singapore", "Dublin"],
        "Prometheus": ["Graphite", "Datadog", "InfluxDB"],
        "Redis": ["Memcached", "KeyDB", "Dragonfly"],
        "Morgan Chen": ["Jamie Park", "Alex Rivera", "Casey Lin"],
        "ICLR": ["NeurIPS", "ICML", "ACL"],
        "AES-256": ["AES-128", "ChaCha20", "AES-192"],
    }
    episodes = []
    for episode_index in range(count):
        rng = random.Random(seed + episode_index)
        replacements = {name: f"{name}{episode_index + 1}" for name in names}
        replacements.update({old: rng.choice(choices) for old, choices in values.items()})
        replacements.update({"120": str(150 + episode_index * 10),
                             "417": str(600 + episode_index),
                             "2400": str(3000 + episode_index * 100),
                             "2,400": f"{3000 + episode_index * 100:,}",
                             "30": str(40 + episode_index), "64": str(128 + episode_index * 16),
                             "November 18": f"December {episode_index + 1}"})
        replacements["AES 256"] = replacements["AES-256"]
        pattern = re.compile(r"(?<!\w)(" + "|".join(re.escape(k) for k in sorted(replacements, key=len, reverse=True)) + r")(?!\w)")
        replace = lambda text: pattern.sub(lambda match: replacements[match.group(1)], text)
        facts = [{**fact, "text": replace(fact["text"])} for fact in data["facts"]]
        rng.shuffle(facts)
        mid = f"reuse-{episode_index:02d}"
        records = [MemoryRecord(
            item_id=fact["id"], content=fact["text"], timestamp=1000000 + i,
            date="synthetic", role="source", session_id=mid, turn_index=i, end=len(fact["text"]),
        ) for i, fact in enumerate(facts)]
        questions = [{
            "id": f"{mid}-{q['id']}", "query": replace(q["query"]),
            "answer": replace(q["answers"][0]), "answers": [replace(a) for a in q["answers"]],
            "required_items": q["relevant_ids"], "question_type": "synthetic-factual",
            "abstention": False, "reference_time": 1000021, "question_date": "synthetic",
        } for q in data["questions"]]
        rng.shuffle(questions)
        episodes.append({"memory_id": mid, "kind": "synthetic_memory_reuse",
                         "records": records, "evidence_turns": [], "questions": questions})
    return episodes


def evidence_metrics(episode: dict, question: dict, selected_ids: list[str]) -> dict:
    """Session retrieval is separate from QA; skip abstention retrieval metrics."""
    if question["abstention"]:
        return {"evidence_recall": None, "all_evidence": None, "any_evidence": None}
    selected = set(selected_ids)
    if "required_items" in question:
        required = set(question["required_items"])
        hit = selected & required
    else:
        required = set(question["required_sessions"])
        delivered = {record.session_id for record in episode["records"] if record.item_id in selected}
        hit = required & delivered
    return {
        "evidence_recall": len(hit) / len(required) if required else None,
        "all_evidence": bool(required) and required <= hit,
        "any_evidence": bool(hit),
    }
