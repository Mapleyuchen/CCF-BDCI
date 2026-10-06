"""Regression gates for truthful uncertainty, failures, budgets and paper input."""
from copy import deepcopy
from pathlib import Path
import asyncio
import json
import sys
import tempfile
import unittest

from memory_eval.data import HERE, read_json
from memory_eval.reporting import cluster_values, expected_trials, measured_reuse, token_sum, validate_fairness
from memory_eval.runtime import SmoothCallGate
from memory_eval.scoring import restore_adjudications
from agent_memory_ab import experiment_workspace

sys.path.insert(0, str(HERE.parent / "research-paper-generator/scripts"))
from paper_content.controlled_evidence import digest
from paper_content.evidence import metric_catalog, normalize_result
from paper_content.figures import table_tex, figure_tex


def controlled_fixture():
    """Artificial fixture used only inside temporary unit-test files."""
    protocol = read_json(HERE / "data/memory_eval_protocol_v2.json")
    rows, writes = [], []
    for group, arm in (("baseline", "bm25"), ("enhanced", "hybrid")):
        for repeat in range(3):
            for question in ("Q0", "Q1"):
                instance = f"{group}:{question}:{repeat}"
                answer = "PostgreSQL" if question == "Q0" or group == "enhanced" else "Unavailable"
                correct = answer == "PostgreSQL"
                row = dict(group=group, arm=arm, memory_id=question, question_id=question, repeat=repeat,
                    memory_instance_id=instance, query="Where is the database?", gold_answer="PostgreSQL",
                    question_type="single-session-user", abstention=False, answer=answer, correct=correct,
                    semantic_correct=correct, status="ok", history_isolated=True, memory_in_model_prompt=True,
                    candidate_hash="same", nonmemory_prompt_sha256="same", bank_frozen=True,
                    budget_tokens=512, memory_tokens=400, evidence_recall=float(correct), total_tokens=500,
                    latency_ms=1, ranking_latency_ms=1, suite="full", prompt={"sha256": answer})
                key = digest(dict(question_id=question, question=row["query"], gold_answer=row["gold_answer"],
                    question_type=row["question_type"], abstention=False, answer=answer,
                    judge_model=protocol["judge_model"], scorer_sha256=protocol["dependencies"]["scorer_sha256"],
                    parser_version="strict-yes-no-v1"))
                import hashlib
                row.update(judge_key=key, judge_label=dict(judge_key=key, label=correct, status="ok",
                    response_sha256=hashlib.sha256(answer.encode()).hexdigest()))
                rows.append(row)
                writes.append(dict(memory_instance_id=instance, total_tokens=0, model_calls=0))
    return dict(kind="controlled_memory_eval_live", settings=dict(model_name="unit-fixture",
        context_tokens=512, budget_unit="tokens", group_labels=dict(baseline="bm25", enhanced="hybrid")),
        source_manifest=dict(kind="memory_eval_v2_live", model_name="unit-fixture", protocol=protocol,
                             execution=dict(self_test=False)), dataset_sha256="a"*64,
        records=rows, constructions=writes, scoring=dict(primary_judge_model=protocol["judge_model"]),
        groups=dict(baseline=dict(accuracy=dict(estimate=.5), n=6), enhanced=dict(accuracy=dict(estimate=1), n=6)),
        comparison={}, limitations=["Unit-test fixture; never research evidence."])


class ReportingTests(unittest.TestCase):
    def normalize(self, data):
        with experiment_workspace(HERE / "results", "report-test-") as temp:
            p = temp / "fixture.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            return normalize_result(p, "controlled", "BM25 versus hybrid")

    def test_repeats_are_averaged_within_memory_clusters(self):
        rows = [dict(memory_id=memory, question_type="a", abstention=False, score=value)
                for memory, value in (("A",0),("A",1),("A",1),("B",0),("B",0),("B",0))]
        ids, values, _ = cluster_values(rows, "score")
        self.assertEqual(ids, ["A", "B"])
        self.assertEqual(values, [2/3, 0])

    def test_unknown_usage_cannot_become_zero(self):
        costs = token_sum([dict(total_tokens=10), dict(total_tokens=None, known_total_tokens=3)])
        self.assertIsNone(costs["tokens"])
        self.assertEqual(costs["known_tokens"], 13)

    def test_expected_scale_counts_answers_not_write_calls(self):
        m = dict(protocol=dict(question_ids=list(range(84))), execution=dict(suite="all", max_episodes=0,
                 lifecycle_episodes=8, repeats=3, selectors=None, budgets=[512,1024,2048]))
        self.assertEqual(expected_trials(m), dict(full=4536, micro=540, reuse=1440))

    def test_budget_violation_and_changed_prompt_are_rejected(self):
        rows = controlled_fixture()["records"]
        for row in rows:
            row["representation_hash"] = "same"
        validate_fairness(rows)
        altered = deepcopy(rows)
        altered[0]["memory_tokens"] = 513
        with self.assertRaisesRegex(ValueError, "cap"):
            validate_fairness(altered)
        altered = deepcopy(rows)
        altered[0]["nonmemory_prompt_sha256"] = "other"
        with self.assertRaisesRegex(ValueError, "prompts"):
            validate_fairness(altered)

    def test_paper_adapter_preserves_token_units_and_selector_names(self):
        result = self.normalize(controlled_fixture())
        self.assertNotIn("context_chars", result)
        self.assertEqual(result["groups"]["baseline"]["memory_clusters"], 2)
        catalog = metric_catalog([result])
        self.assertEqual(catalog["controlled.context_tokens"]["value"], 512)
        self.assertIn("bm25", table_tex(result, catalog))
        self.assertIn("memory-cluster", figure_tex(result))

    def test_paper_adapter_rejects_tampered_judgment_and_self_test(self):
        data = controlled_fixture()
        data["records"][0]["answer"] = "Changed after scoring"
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.normalize(data)
        data = controlled_fixture()
        data["source_manifest"]["execution"]["self_test"] = True
        with self.assertRaisesRegex(ValueError, "real model"):
            self.normalize(data)

    def test_failed_question_stays_in_denominator(self):
        data = controlled_fixture()
        row = data["records"][0]
        row.update(status="error", correct=False, semantic_correct=False)
        data["groups"]["baseline"]["accuracy"]["estimate"] = 1/3
        result = self.normalize(data)
        self.assertEqual(result["groups"]["baseline"]["n"], 6)
        self.assertEqual(result["groups"]["baseline"]["excluded_records"], 0)
        self.assertEqual(result["groups"]["baseline"]["failed_records"], 1)

    def test_gate_smooths_concurrent_requests(self):
        import time
        async def run():
            gate = SmoothCallGate(.02)
            async def job():
                await gate.wait()
                return time.perf_counter()
            return sorted(await asyncio.gather(*(job() for _ in range(4))))
        starts = asyncio.run(run())
        self.assertTrue(all(b-a >= .018 for a,b in zip(starts, starts[1:])))

    def test_measured_reuse_counts_one_write_and_distinct_queries(self):
        rows = [dict(arm="hybrid_model_ack", query_index=i, memory_instance_id="I", memory_id="B",
                     question_id=f"Q{i}", total_tokens=10, known_total_tokens=10,
                     semantic_correct=True, abstention=False, question_type="synthetic-factual") for i in range(20)]
        writes = {"I": dict(total_tokens=100, known_total_tokens=100)}
        protocol = dict(bootstrap_resamples=100, bootstrap_seed=1)
        result = measured_reuse(rows, writes, protocol)
        self.assertEqual([r["amortized_tokens_per_query"]["estimate"] for r in result], [110,30,20,15])
        rows[-1]["question_id"] = rows[0]["question_id"]
        with self.assertRaisesRegex(ValueError, "distinct"):
            measured_reuse(rows, writes, protocol)

    def test_reuse_missing_usage_is_a_lower_bound_not_an_exact_cost(self):
        rows = [dict(arm="hybrid_model_ack", query_index=i, memory_instance_id="I", memory_id="B",
                     question_id=f"Q{i}", total_tokens=10, known_total_tokens=10,
                     semantic_correct=True, abstention=False, question_type="synthetic-factual") for i in range(20)]
        rows[0].update(total_tokens=None, known_total_tokens=3)
        result = measured_reuse(rows, {"I": dict(total_tokens=100, known_total_tokens=100)},
                                dict(bootstrap_resamples=100, bootstrap_seed=1))
        self.assertIsNone(result[0]["amortized_tokens_per_query"])
        self.assertEqual(result[0]["known_tokens_per_query_lower_bound"]["estimate"], 103)

    def test_scoring_resume_preserves_completed_and_partial_human_reviews(self):
        row = dict(judge_key="K", question_id="Q", query="Where?", gold_answer="A", response="B")
        reviewed = {**row, "decision": False, "reviewer": "reviewer-1", "notes": "Verified against gold"}
        pending = {**row, "judge_key": "P", "decision": None, "reviewer": "reviewer-2", "notes": "Needs another review"}
        restored = restore_adjudications([dict(row), {**row,"judge_key":"P"}], [reviewed,pending])
        self.assertIs(restored[0]["decision"], False)
        self.assertEqual(restored[1]["notes"], pending["notes"])

    def test_changed_response_cannot_inherit_a_human_judgment(self):
        row = dict(judge_key="K", question_id="Q", query="Where?", gold_answer="A", response="B")
        with self.assertRaisesRegex(ValueError, "changed"):
            restore_adjudications([{**row,"response":"C"}], [{**row,"decision":True}])

if __name__ == "__main__":
    unittest.main()
