"""Regression checks for the real Agent path with a deterministic local model."""

from argparse import Namespace
import asyncio
from pathlib import Path
import unittest

from agent_memory_ab import answer_is_correct, complete_fact_ids, experiment_workspace, load_qa_dataset, run_experiment
from memory_rail_benchmark import load_dataset


HERE = Path(__file__).parent


class AgentMemoryABTest(unittest.TestCase):
    def test_first_five_questions_reuse_component_pilot(self):
        component = load_dataset(HERE / "data" / "memory_retrieval_v1.json")
        agent = load_qa_dataset(HERE / "data" / "memory_agent_qa_v2.json")
        self.assertEqual(agent["facts"], component["facts"])
        self.assertEqual(len(agent["questions"]), 20)
        for old, new in zip(component["questions"], agent["questions"][:5]):
            self.assertEqual(
                {key: new[key] for key in ("id", "query", "relevant_ids")}, old
            )

    def test_answer_match_uses_token_boundaries(self):
        self.assertTrue(answer_is_correct("The limit is 120 requests.", ["120"]))
        self.assertFalse(answer_is_correct("The limit is 1200 requests.", ["120"]))

    def test_truncated_fact_marker_is_not_complete_evidence(self):
        facts = [{"id": "F04", "text": "The Delta project deploys to the Frankfurt region."}]
        self.assertEqual(complete_fact_ids("<FACT:F04> The Delta project deploys to the", facts), set())
        self.assertEqual(complete_fact_ids("<FACT:F04> The Delta project deploys to the Frankfurt region.", facts), {"F04"})

    def test_one_paired_question_runs_real_agent_callbacks(self):
        with experiment_workspace(HERE / "results", "agent-ab-test-") as directory:
            args = Namespace(
                dataset=HERE / "data" / "memory_agent_qa_v2.json",
                output=Path(directory) / "result.json",
                config=Path(directory) / "no-config.yaml",
                context_chars=600, top_k=10, max_cases=1, repeats=1,
                fact_order_seed=None, self_test=True,
            )
            report = asyncio.run(run_experiment(args))
        self.assertEqual(report["kind"], "deterministic_self_test")
        self.assertEqual(report["summary"]["paired"]["n"], 1)
        self.assertEqual(report["summary"]["paired"]["unique_questions"], 1)
        self.assertEqual(report["runs"][1]["seed_model_calls"], 20)
        self.assertEqual(report["summary"]["resource_totals"]["baseline"]["all_tokens"], 23)
        self.assertEqual(report["summary"]["resource_totals"]["enhanced"]["all_tokens"], 483)
        for row in report["records"]:
            self.assertEqual(row["status"], "ok")
            self.assertTrue(row["history_isolated"])
            self.assertTrue(row["memory_in_model_prompt"])
            self.assertLessEqual(row["memory_chars"], 600)
            self.assertEqual(row["input_tokens"], 20)

    def test_fact_order_is_shared_within_each_pair_and_changes_by_repeat(self):
        with experiment_workspace(HERE / "results", "agent-ab-test-") as directory:
            report = asyncio.run(run_experiment(Namespace(
                dataset=HERE / "data" / "memory_agent_qa_v2.json",
                output=Path(directory) / "result.json",
                config=Path(directory) / "no-config.yaml",
                context_chars=600, top_k=10, max_cases=1, repeats=2,
                fact_order_seed=2026, self_test=True,
            )))
        orders = {}
        for run in report["runs"]:
            orders.setdefault(run["repeat"], []).append(run["fact_order"])
        self.assertEqual(orders[0][0], orders[0][1])
        self.assertEqual(orders[1][0], orders[1][1])
        self.assertNotEqual(orders[0][0], orders[1][0])
        self.assertEqual(report["summary"]["paired"]["unique_questions"], 1)


if __name__ == "__main__":
    unittest.main()
