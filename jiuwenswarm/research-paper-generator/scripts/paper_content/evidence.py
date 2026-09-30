"""Recompute measurements from live experiment records, never from model prose."""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from pathlib import Path

LIVE_KINDS = {"live_model_experiment", "adapted_longmemeval_live"}
GROUPS = ("baseline", "enhanced")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value, label, *, optional=False, maximum=None):
    if value is None and optional:
        return None
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0 or (maximum is not None and value > maximum)):
        raise ValueError(f"Invalid measurement: {label}")
    return value


def optional_sum(values):
    return sum(values) if values and all(v is not None for v in values) else None


def normalize_result(path: Path, evidence_id: str, title: str) -> dict:
    """Adapters for the two live Agent A/B formats in experiments/."""
    data = read_json(path)
    if not isinstance(data, dict) or data.get("kind") not in LIVE_KINDS:
        raise ValueError(f"{path.name}: expected a live Agent A/B result; legacy/simulated/self-test data is not evidence")
    records, runs = data.get("records"), data.get("runs")
    if not isinstance(records, list) or not records or not isinstance(runs, list) or not runs:
        raise ValueError(f"{path.name}: records and memory-write runs are required")
    settings = data.get("settings") or {}
    model = settings.get("model_name")
    if not isinstance(model, str) or not model.strip() or "self-test" in model:
        raise ValueError("A live model identity is required")
    budget = number(settings.get("context_chars"), "context_chars")
    if budget <= 0:
        raise ValueError("context_chars must be positive")
    dataset_hash = data.get("dataset_sha256")
    if not isinstance(dataset_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", dataset_hash):
        raise ValueError("A dataset SHA-256 is required")
    indexed = {group: {} for group in GROUPS}
    all_rows = {group: [] for group in GROUPS}
    for row in records:
        if not isinstance(row, dict) or row.get("group") not in GROUPS:
            raise ValueError("Invalid experiment record group")
        group = row["group"]
        qid, repeat = row.get("question_id"), row.get("repeat")
        if not isinstance(qid, str) or type(repeat) is not int or repeat < 0:
            raise ValueError("Each record needs question_id and nonnegative repeat")
        key = (repeat, qid)
        if key in indexed[group]:
            raise ValueError(f"Duplicate trial: {group}/{key}")
        indexed[group][key] = row
        all_rows[group].append(row)
        number(row.get("total_tokens"), "total_tokens", optional=True)
        number(row.get("latency_ms"), "latency_ms", optional=row.get("status") != "ok")
        if row.get("status") == "ok":
            if type(row.get("correct")) is not bool:
                raise ValueError("Live correctness must be boolean")
            number(row.get("evidence_recall"), "evidence_recall", maximum=1)

    def valid(row):
        return (row.get("status") == "ok" and not row.get("error")
                and row.get("history_isolated") is True and row.get("memory_in_model_prompt") is True)

    paired = sorted(set(indexed["baseline"]) & set(indexed["enhanced"]))
    paired = [key for key in paired if all(valid(indexed[g][key]) for g in GROUPS)]
    if not paired:
        raise ValueError("No valid paired trials with isolated history and verified prompt injection")
    for key in paired:
        left, right = (indexed[g][key] for g in GROUPS)
        if left.get("query") != right.get("query") or left.get("answers") != right.get("answers"):
            raise ValueError(f"Paired trials have different questions or accepted answers: {key}")
    groups = {}
    for group in GROUPS:
        rows = [indexed[group][key] for key in paired]
        writes = [run for run in runs if isinstance(run, dict) and run.get("group") == group]
        if not writes:
            raise ValueError(f"Missing memory-write accounting for {group}")
        query_tokens = optional_sum([row.get("total_tokens") for row in all_rows[group]])
        seed_tokens = optional_sum([number(run.get("seed_total_tokens"), "seed_total_tokens", optional=True)
                                    for run in writes])
        total_tokens = query_tokens + seed_tokens if query_tokens is not None and seed_tokens is not None else None
        seed_calls = sum(number(run.get("seed_model_calls"), "seed_model_calls") for run in writes)
        latencies = [number(run.get("seed_latency_ms"), "seed_latency_ms", optional=True) for run in writes]
        seed_latency = optional_sum(latencies)
        # These are per-run totals; do not sum the repeated seed_latency_ms on every question.
        query_latency = optional_sum([row.get("latency_ms") for row in all_rows[group]])
        end_to_end = ((seed_latency + query_latency) / len(rows)
                      if seed_latency is not None and query_latency is not None else None)
        groups[group] = {
            "n": len(rows), "correct": sum(row["correct"] for row in rows),
            "accuracy": statistics.mean(row["correct"] for row in rows),
            "evidence_recall": statistics.mean(row["evidence_recall"] for row in rows),
            "query_tokens": query_tokens, "seed_tokens": seed_tokens, "all_tokens": total_tokens,
            "tokens_per_question": total_tokens / len(rows) if total_tokens is not None else None,
            "seed_model_calls": seed_calls,
            "query_latency_ms": statistics.mean(row["latency_ms"] for row in rows),
            "end_to_end_latency_ms": end_to_end,
            "excluded_records": len(all_rows[group]) - len(rows),
        }
    return {
        "id": evidence_id, "title": title, "kind": data["kind"], "model_name": model,
        "dataset_sha256": dataset_hash, "source_sha256": sha256(path),
        "context_chars": budget, "unique_questions": len({key[1] for key in paired}),
        "paired_observations": len(paired), "repeats": len({key[0] for key in paired}),
        "groups": groups,
        "accuracy_gain_pp": (groups["enhanced"]["accuracy"] - groups["baseline"]["accuracy"]) * 100,
        "protocol": {
            key: settings[key] for key in ("top_k", "turns_per_episode", "max_iterations", "tools", "model_request")
            if key in settings
        },
        "selection_rule": data.get("selection_rule"),
        "limitations": [
            "A paired memory question-answering experiment, not an end-to-end paper-generation evaluation.",
            "Current enhanced Rail writes only process-local L1 memory; L2/L3 persistence and team synchronization are untested.",
            "String-based accepted-answer matching requires semantic review; context metadata also consumes the character budget.",
            "Repeated questions and budgets sharing a dataset are not independent samples; no significance test is claimed.",
            "Total token cost includes memory writes and all recorded attempts, amortized over valid paired observations.",
        ] + (["This is an adapted LongMemEval slice, not an official LongMemEval score."]
             if data["kind"] == "adapted_longmemeval_live" else
             ["This dataset contains synthetic questions sharing a fact bank."]),
    }


def load_evidence(outline: dict) -> list[dict]:
    entries = outline.get("evidence", [])
    if not entries:
        raise ValueError("Content filling requires completed live experiment evidence")
    titles = {child["evidence_ids"][0]: child["title"]
              for section in outline["sections"] for child in section.get("subsections", [])
              if child.get("evidence_ids")}
    results, seen = [], set()
    for entry in entries:
        eid = entry.get("id", "")
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", eid) or eid in seen:
            raise ValueError("Invalid or duplicate evidence ID")
        seen.add(eid)
        path = Path(entry["resolved_path"])
        if not path.is_file() or sha256(path) != entry.get("sha256"):
            raise ValueError(f"Evidence changed or missing since framework generation: {eid}")
        results.append(normalize_result(path, eid, titles.get(eid, eid)))
    return results


def metric_catalog(results: list[dict]) -> dict:
    catalog = {}
    for result in results:
        prefix = result["id"]
        for name in ("context_chars", "unique_questions", "paired_observations", "repeats", "accuracy_gain_pp"):
            value = result[name]
            text = f"{value:g} percentage points" if name == "accuracy_gain_pp" else f"{value:g}"
            catalog[f"{prefix}.{name}"] = {"value": value, "text": text}
        for group, stats in result["groups"].items():
            for name, value in stats.items():
                text = "not reported" if value is None else (
                    f"{value * 100:.1f}%" if name in ("accuracy", "evidence_recall") else
                    f"{value:.2f}" if name in ("tokens_per_question", "query_latency_ms", "end_to_end_latency_ms")
                    else f"{value:g}")
                catalog[f"{prefix}.{group}.{name}"] = {"value": value, "text": text}
    return catalog
