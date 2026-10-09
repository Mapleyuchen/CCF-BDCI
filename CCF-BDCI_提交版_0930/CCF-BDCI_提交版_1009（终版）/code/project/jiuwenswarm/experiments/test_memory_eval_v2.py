"""Regression gates for fairness, leakage, accounting and clustered inference."""

from __future__ import annotations

from argparse import Namespace
import asyncio
from dataclasses import asdict
from pathlib import Path
import unittest

from memory_eval.data import HERE, TYPES, evidence_metrics, full_episode, lifecycle_episodes, micro_episodes, prepare_manifest, read_json
from memory_eval.runtime import Journal, arm_definitions, execute_episode, usage_summary
from memory_eval.scoring import benchmark_prompt_function, judgment_key
from memory_eval.statistics import cluster_interval, holm_adjust, paired_permutation
from agent_memory_ab import experiment_workspace
from jiuwenswarm.agents.harness.common.memory.controlled_retrieval import (
    FrozenMemoryIndex, MemoryRecord, PinnedTokenizer, canonical_hash,
)


class ControlledMemoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dependencies = read_json(HERE / "data/memory_eval_dependencies_v2.json")
        cls.tokenizer = PinnedTokenizer(HERE / "data/public/qwen3_tokenizer/tokenizer.json",
                                       cls.dependencies["tokenizer_files"]["tokenizer.json"])

    def record(self, item_id, content, timestamp=100, **kwargs):
        return MemoryRecord(item_id, content, timestamp, "date", "user", "S", 0, end=len(content), **kwargs)

    def test_pinned_tokenizer_rejects_wrong_hash(self):
        with self.assertRaisesRegex(ValueError, "pinned"):
            PinnedTokenizer(HERE / "data/public/qwen3_tokenizer/tokenizer.json", "0" * 64)

    def test_chunking_preserves_unicode_and_every_source_character(self):
        text = ("中文 🧠 café naïve\nA long memory sentence with numbers 12345. " * 30)
        chunks = self.tokenizer.split(text, 40)
        self.assertEqual("".join(part for _, _, part in chunks), text)
        self.assertEqual(chunks[0][0], 0)
        self.assertEqual(chunks[-1][1], len(text))
        self.assertTrue(all(self.tokenizer.count(part) <= 40 for _, _, part in chunks))
        for left, right in zip(chunks, chunks[1:]):
            self.assertEqual(left[1], right[0])

    def test_oversized_items_are_skipped_whole_for_every_selector(self):
        records = [self.record("LARGE", "customer database " * 1000),
                   self.record("SMALL", "Customer profiles are stored in PostgreSQL.")]
        bank = FrozenMemoryIndex(records)
        for strategy in ("prefix", "recency", "jaccard", "bm25", "hybrid", "hybrid_no_time"):
            packed = bank.pack(bank.rank("customer database", strategy, 100), self.tokenizer, 80)
            self.assertNotIn("LARGE", packed["selected_ids"])
            self.assertIn("SMALL", packed["selected_ids"])
            self.assertIn(records[1].content, packed["context"])
            self.assertLessEqual(self.tokenizer.count(packed["context"]), 80)

    def test_candidate_identity_and_wrapper_are_shared(self):
        records = [self.record("A", "alpha project"), self.record("B", "beta project")]
        bank = FrozenMemoryIndex(records)
        for strategy in ("prefix", "bm25", "hybrid"):
            packed = bank.pack(bank.rank("beta", strategy, 100), self.tokenizer, 100)
            self.assertEqual(packed["candidate_hash"], canonical_hash([asdict(r) for r in records]))
            self.assertTrue(packed["context"].startswith("<memory>\n"))
            self.assertTrue(packed["context"].endswith("\n</memory>"))

    def test_representation_changes_no_source_values_or_metadata(self):
        records = [self.record("A", "alpha project")]
        raw, exchange = FrozenMemoryIndex(records), FrozenMemoryIndex(records, representation="exchange")
        self.assertEqual(raw.content_hash, exchange.content_hash)
        self.assertNotEqual(raw.representation_hash, exchange.representation_hash)

    def test_temporal_ablation_removes_only_temporal_contribution(self):
        bank = FrozenMemoryIndex([self.record("A", "alpha", 0), self.record("B", "beta", 100)])
        full = {r["item_id"]: r for r in bank.rank("alpha", "hybrid", 200)}
        removed = {r["item_id"]: r for r in bank.rank("alpha", "hybrid_no_time", 200)}
        for item_id in full:
            self.assertAlmostEqual(full[item_id]["score"] - full[item_id]["components"]["temporal_contribution"],
                                   removed[item_id]["score"])
            self.assertEqual(full[item_id]["components"], removed[item_id]["components"])

    def test_fixed_clock_and_formal_queries_do_not_touch_memory(self):
        record = self.record("A", "alpha", 0, access_count=4)
        bank = FrozenMemoryIndex([record])
        first = bank.rank("alpha", "hybrid", 200)
        self.assertEqual(first, bank.rank("alpha", "hybrid", 200))
        bank.rank("other question", "hybrid", 200)
        self.assertEqual(record.access_count, 4)
        self.assertEqual(first, bank.rank("alpha", "hybrid", 200))

    def test_no_time_ablation_preserves_lexical_tie_order(self):
        bank = FrozenMemoryIndex([self.record(str(i), "irrelevant", i * 86400) for i in range(20)])
        lexical = bank.rank("no matching terms", "jaccard", 20 * 86400)
        removed = bank.rank("no matching terms", "hybrid_no_time", 20 * 86400)
        self.assertEqual([r["item_id"] for r in lexical], [r["item_id"] for r in removed])

    def test_source_sampling_never_uses_gold_content(self):
        source = [{"question_id": f"{kind}-{i}", "question_type": kind, "answer": "short"}
                  for kind in TYPES for i in range(20)]
        source += [{"question_id": f"{i}_abs", "question_type": "single-session-user", "answer": "missing"}
                   for i in range(20)]
        before = prepare_manifest(source, {}, per_stratum=12)
        for row in source:
            row["answer"] = "A much longer changed answer" * 100
        after = prepare_manifest(source, {}, per_stratum=12)
        self.assertEqual(before["question_ids"], after["question_ids"])
        self.assertEqual(len(before["question_ids"]), 84)
        self.assertEqual(set(before["stratified_question_ids"]), set(TYPES) | {"abstention"})

    def test_full_history_conversion_retains_all_turns_and_excludes_gold_from_candidates(self):
        example = {
            "question_id": "Q", "question_type": "single-session-user", "question": "where",
            "answer": "secret-gold-answer", "question_date": "2023/05/30 (Tue) 23:40",
            "answer_session_ids": ["S"], "haystack_session_ids": ["S"],
            "haystack_dates": ["2023/05/29 (Mon) 23:40"],
            "haystack_sessions": [[{"role": "user", "content": "raw user text " * 30, "has_answer": True},
                                   {"role": "assistant", "content": "raw assistant text"}]],
        }
        episode = full_episode(example, self.tokenizer, chunk_tokens=40)
        candidates = [asdict(record) for record in episode["records"]]
        self.assertFalse(any("secret-gold-answer" in str(record) for record in candidates))
        self.assertTrue(all("has_answer" not in record for record in candidates))
        for turn_index, turn in enumerate(example["haystack_sessions"][0]):
            parts = [record.content for record in episode["records"] if record.turn_index == turn_index]
            self.assertEqual("".join(parts), turn["content"])

    def test_abstention_is_excluded_from_retrieval_metrics(self):
        self.assertIsNone(evidence_metrics({}, {"abstention": True}, [])["evidence_recall"])

    def test_distinct_queries_share_one_synthetic_bank(self):
        episodes = lifecycle_episodes(HERE / "data/memory_agent_qa_v2.json")
        self.assertEqual(len({canonical_hash([asdict(r) for r in e["records"]]) for e in episodes}), 8)
        for episode in episodes:
            self.assertEqual(len({q["id"] for q in episode["questions"]}), 20)
            for question in episode["questions"]:
                fact = next(r.content for r in episode["records"] if r.item_id in question["required_items"])
                self.assertTrue(any(answer.casefold() in fact.casefold() for answer in question["answers"]))

    def test_retry_with_missing_usage_remains_unknown(self):
        measured = usage_summary([{"status": "ok", "usage": {"total_tokens": 10, "input_tokens": 8, "output_tokens": 2}},
                                  {"status": "error", "usage": None}])
        self.assertIsNone(measured["total_tokens"])
        self.assertEqual(measured["known_total_tokens"], 10)
        self.assertEqual(measured["failed_attempts"], 1)

    def test_semantic_judge_is_blind_to_arm_and_repeat(self):
        row = {"question_id": "Q", "query": "where", "gold_answer": "A",
               "question_type": "single-session-user", "abstention": False, "answer": "A"}
        left = judgment_key({**row, "arm": "bm25", "repeat": 0}, "judge", "sha")
        right = judgment_key({**row, "arm": "hybrid", "repeat": 2}, "judge", "sha")
        self.assertEqual(left, right)
        prompt = benchmark_prompt_function(self.dependencies)("temporal-reasoning", "Q", "18 days", "19 days")
        self.assertIn("off-by-one", prompt)

    def test_bootstrap_uses_memory_clusters_and_identical_pairs_have_zero_width(self):
        interval = cluster_interval([0, 0, 0], strata=["a", "a", "b"], resamples=100)
        self.assertEqual(interval["clusters"], 3)
        self.assertEqual(interval["low"], 0)
        self.assertEqual(interval["high"], 0)
        self.assertEqual(paired_permutation([0, 0, 0]), 1)
        self.assertEqual(holm_adjust({"a": 0.01, "b": 0.04}), {"a": 0.02, "b": 0.04})

    def test_real_agent_callbacks_verify_fairness_and_construction_identity(self):
        episode = micro_episodes(HERE / "data/longmemeval_s_turn20_v1.json")[0]
        with experiment_workspace(HERE / "results", "v2-test-") as directory:
            journal = Journal(directory)
            asyncio.run(execute_episode(episode, "micro", 0, arm_definitions("micro"), [512],
                                        {}, journal, self.tokenizer, self_test=True))
            rows = list(journal.trials.values())
            self.assertTrue(all(r["status"] == "ok" and r["history_isolated"]
                                and r["memory_in_model_prompt"] for r in rows))
            raw = next(r for r in rows if r["arm"] == "hybrid_raw")
            acquired = next(r for r in rows if r["arm"] == "hybrid_model_ack")
            self.assertEqual(raw["prompt"], acquired["prompt"])
            self.assertEqual(raw["candidate_hash"], acquired["candidate_hash"])
            self.assertEqual(len({r["nonmemory_prompt_sha256"] for r in rows}), 1)
            constructions = list(journal.constructions.values())
            self.assertEqual(sum(c["model_calls"] for c in constructions), 20)
            journal.close()


if __name__ == "__main__":
    unittest.main()
