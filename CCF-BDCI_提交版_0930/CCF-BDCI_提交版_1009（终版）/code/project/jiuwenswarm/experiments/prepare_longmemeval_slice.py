"""Derive a deterministic 20-turn retrieval slice from official LongMemEval-S.

The derived set is an adapted benchmark, not the official 500-question score.
Questions, answers, and turn text are copied from the released dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any


HERE = Path(__file__).parent
SOURCE_URL = (
    "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/"
    "resolve/main/longmemeval_s_cleaned.json"
)
SOURCE_SHA256 = "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442"
SELECTION_SEED = 2026


def _rng(question_id: str) -> random.Random:
    digest = hashlib.sha256(f"{SELECTION_SEED}:{question_id}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def _turns(example: dict[str, Any]):
    for session_id, date, session in zip(
        example["haystack_session_ids"], example["haystack_dates"],
        example["haystack_sessions"], strict=True,
    ):
        for turn_index, turn in enumerate(session):
            if isinstance(turn.get("content"), str):
                yield {
                    "session_id": session_id,
                    "date": date,
                    "turn_index": turn_index,
                    "role": turn.get("role", "unknown"),
                    "content": turn["content"].strip(),
                    "has_answer": turn.get("has_answer") is True,
                }


def candidate(example: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    if example.get("question_type") != "single-session-user" or not isinstance(example.get("answer"), str):
        return None
    answer = example["answer"].strip()
    query = example["question"]
    turns = list(_turns(example))
    evidence = [turn for turn in turns if turn["has_answer"]]
    if len(evidence) != 1:
        return None
    evidence_turn = evidence[0]
    if not (4 <= len(answer) <= 70
            and 20 <= len(evidence_turn["content"]) <= 250
            and answer.casefold() in evidence_turn["content"].casefold()
            and answer.casefold() not in query.casefold()):
        return None
    distractors = [
        turn for turn in turns
        if not turn["has_answer"]
        and 20 <= len(turn["content"]) <= 250
        and answer.casefold() not in turn["content"].casefold()
    ]
    if len(distractors) < 19:
        return None
    return evidence_turn, distractors


def derive(source: Path, *, limit: int = 20) -> dict[str, Any]:
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError(f"Unexpected LongMemEval-S source SHA-256: {digest}")
    examples = json.loads(raw)
    eligible = [
        (example, selected)
        for example in examples
        if (selected := candidate(example)) is not None
    ]
    eligible.sort(key=lambda item: item[0]["question_id"])
    if len(eligible) < limit:
        raise ValueError(f"Only {len(eligible)} eligible questions, need {limit}")
    episodes = []
    for example, (evidence, distractors) in eligible[:limit]:
        rng = _rng(example["question_id"])
        selected = [(evidence, True)] + [(turn, False) for turn in rng.sample(distractors, 19)]
        rng.shuffle(selected)
        facts = []
        relevant_ids = []
        for index, (turn, is_evidence) in enumerate(selected, 1):
            fact_id = f"F{index:02d}"
            if is_evidence:
                relevant_ids.append(fact_id)
            facts.append({
                "id": fact_id,
                "text": f"[{turn['date']}] {turn['role']}: {turn['content']}",
                "source_session_id": turn["session_id"],
                "source_turn_index": turn["turn_index"],
                "has_answer": is_evidence,
            })
        episodes.append({
            "id": example["question_id"],
            "question_type": example["question_type"],
            "facts": facts,
            "questions": [{
                "id": example["question_id"],
                "query": example["question"],
                "answers": [example["answer"].strip()],
                "relevant_ids": relevant_ids,
            }],
        })
    return {
        "kind": "LongMemEval-S adapted 20-turn single-session-user slice",
        "source_url": SOURCE_URL,
        "source_sha256": digest,
        "source_license": "MIT",
        "source_citation": "Wu et al., LongMemEval, ICLR 2025, arXiv:2410.10813",
        "selection_seed": SELECTION_SEED,
        "eligible_count": len(eligible),
        "selection_rule": (
            "Sort eligible single-session-user questions by question_id; take the first 20. "
            "Each has exactly one has_answer turn of 20-250 characters, a 4-70 character "
            "string answer present in that turn but absent from the question, and at least 19 "
            "same-history non-answer turns of 20-250 characters that omit the answer. "
            "Sample 19 distractors deterministically and shuffle all 20 turns."
        ),
        "episodes": episodes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=HERE / "data" / "public" / "longmemeval_s_cleaned.json")
    parser.add_argument("--output", type=Path,
                        default=HERE / "data" / "longmemeval_s_turn20_v1.json")
    args = parser.parse_args()
    data = derive(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Derived {len(data['episodes'])} episodes from {data['eligible_count']} eligible questions: {args.output}")


if __name__ == "__main__":
    main()
