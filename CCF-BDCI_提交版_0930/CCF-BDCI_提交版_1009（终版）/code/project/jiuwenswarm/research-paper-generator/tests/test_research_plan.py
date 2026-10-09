"""Revision planning must preserve evidence boundaries and the content handoff."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / "scripts"))

from paper_content.project import fill_project
from paper_content.prose import build_messages, validate_content
from paper_framework.citations import build_citations
from paper_framework.planner import plan_outline
from paper_framework.project import generate_project
from test_content import experiment, PROSE


class ResearchPlanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.brief = {
            "schema_version": 1, "title": "Controlled Memory Evaluation", "research_question": "What does memory buy?",
            "research_questions": [{"id": "quality", "title": "Answer Quality", "question": "Does matched retrieval help?"}],
            "experiments": [{"id": "fair", "title": "Matched Retrieval", "status": "planned",
                             "research_question_ids": ["quality"], "purpose": "comparison",
                             "protocol": {"budget": {"unit": "tokens", "values": [512]}, "repeats": 3},
                             "evidence_requirements": ["Rendered prompts and per-query usage"]}],
            "review_concerns": [{"id": "fairness", "title": "Fair Baselines", "description": "Match representation and budgets.",
                                 "experiment_ids": ["fair"]}],
        }
        self.citations = build_citations([])

    def plan(self):
        return plan_outline(self.brief, self.citations, self.root)

    def generate(self):
        source = self.root / "brief.json"
        source.write_text(json.dumps(self.brief), encoding="utf-8")
        return generate_project(source, self.root / "framework")

    def test_plan_exposes_missing_protocol_without_inventing_results(self):
        outline = self.plan()
        plan = outline["research_plan"]
        sections = {s["id"]: s for s in outline["sections"]}
        self.assertEqual(outline["evidence"], [])
        self.assertEqual(sections["results"]["subsections"], [])
        self.assertEqual(sections["introduction"]["subsections"][0]["id"], "rq_quality")
        self.assertEqual(sections["experiments"]["subsections"][0]["protocol"]["budget"]["unit"], "tokens")
        self.assertIn("budget.tokenizer", plan["experiments"][0]["missing_protocol_fields"])
        self.assertIn("scoring.version", plan["experiments"][0]["missing_protocol_fields"])
        self.assertEqual(plan["review_concerns"][0]["status"], "awaiting_evidence")

    def test_unknown_links_and_duplicate_ids_fail_before_writing(self):
        original = deepcopy(self.brief)
        for mutate in (
            lambda b: b["experiments"][0].update(research_question_ids=["missing"]),
            lambda b: b["review_concerns"][0].update(experiment_ids=["missing"]),
            lambda b: b["research_questions"].append(deepcopy(b["research_questions"][0])),
        ):
            self.brief = deepcopy(original)
            mutate(self.brief)
            with self.assertRaises(ValueError):
                self.generate()
            self.assertFalse((self.root / "framework").exists())

    def test_invalid_protocols_are_not_silently_accepted(self):
        invalid = [
            {"repeat": 3}, {"repeats": True}, {"repeats": 0}, {"repeats": 1.5},
            {"budget": {"unit": "bytes"}}, {"budget": {"values": [0]}},
            {"budget": {"values": [True]}}, {"budget": {"values": [512, 512]}},
            {"budget": {"tokeniser": "typo"}}, {"baselines": "prefix"},
            {"controlled_variables": ["representation"], "changed_variables": ["representation"]},
            {"dataset": {"sample_size": -1}}, {"reuse": {"queries_per_memory": []}},
        ]
        for protocol in invalid:
            with self.subTest(protocol=protocol):
                self.brief["experiments"][0]["protocol"] = protocol
                with self.assertRaises(ValueError):
                    self.plan()

    def test_ablation_rejects_conflated_variables_and_reuse_lists_required_inputs(self):
        item = self.brief["experiments"][0]
        item.update(purpose="ablation", protocol={"changed_variables": ["representation", "selector"]})
        with self.assertRaisesRegex(ValueError, "one variable"):
            self.plan()
        item.update(purpose="amortization", protocol={})
        missing = self.plan()["research_plan"]["experiments"][0]["missing_protocol_fields"]
        self.assertIn("reuse.queries_per_memory", missing)
        self.assertIn("reuse.construction_cost_policy", missing)

    def test_planned_result_file_cannot_silently_become_evidence(self):
        (self.root / "run.json").write_text("{}", encoding="utf-8")
        self.brief["experiments"][0]["result_path"] = "run.json"
        with self.assertRaisesRegex(ValueError, "Planned experiment"):
            self.generate()
        self.assertFalse((self.root / "framework").exists())

    def test_file_and_complete_protocol_do_not_resolve_a_review_concern(self):
        (self.root / "run.json").write_text("{}", encoding="utf-8")
        self.brief["experiments"][0].update(status="completed", result_path="run.json")
        outline = self.plan()
        self.assertEqual(outline["evidence"][0]["validation"], "file_exists_and_hashed_only")
        self.assertEqual(outline["research_plan"]["review_concerns"][0]["status"], "needs_scientific_review")
        self.assertTrue(outline["research_plan"]["scientific_review_required"])

    def test_unmapped_question_and_review_concern_remain_visible(self):
        self.brief["experiments"] = []
        self.brief["review_concerns"][0]["experiment_ids"] = []
        outline = self.plan()
        self.assertEqual(outline["research_plan"]["review_concerns"][0]["status"], "unmapped")
        self.assertTrue(any("no linked experiment" in w for w in outline["warnings"]))

    def test_legacy_brief_has_unchanged_structure_and_no_new_requirements(self):
        for key in ("research_questions", "review_concerns"):
            self.brief.pop(key)
        self.brief["experiments"] = [{"id": "old", "title": "Original Trial"}]
        outline = self.plan()
        self.assertNotIn("research_plan", outline)
        self.assertEqual(outline["planner"], "deterministic_rules_v1")
        self.assertEqual(outline["sections"][1]["subsections"], [])
        self.assertEqual(len(outline["sections"][4]["subsections"]), 1)

    def test_revision_example_keeps_only_pilot_results_and_stable_citations(self):
        brief = json.loads((MODULE / "examples/memory-revision.brief.json").read_text(encoding="utf-8"))
        literature = json.loads((MODULE / "examples/memory-research.literature.json").read_text(encoding="utf-8"))
        citations = build_citations(literature)
        outline = plan_outline(brief, citations, MODULE / "examples")
        self.assertEqual([e["id"] for e in outline["evidence"]], ["public_small", "public_large"])
        self.assertEqual(len(outline["research_plan"]["experiments"]), 8)
        self.assertEqual(len(outline["sections"][5]["subsections"]), 2)
        self.assertTrue(all(c["status"] == "awaiting_evidence" for c in outline["research_plan"]["review_concerns"]))
        self.assertTrue(all(e["purpose"] == "pilot" for e in outline["research_plan"]["experiments"] if e["evidence_ids"]))
        self.assertEqual(citations["by_source_id"], build_citations(list(reversed(literature)))["by_source_id"])

    def test_content_receives_and_preserves_the_plan_with_mixed_evidence(self):
        (self.root / "pilot.json").write_text(json.dumps(experiment()), encoding="utf-8")
        self.brief["experiments"].append({"id": "pilot", "title": "Pilot Observation", "purpose": "pilot",
                                          "status": "completed", "result_path": "pilot.json"})
        self.generate()
        framework = self.root / "framework"
        outline = json.loads((framework / "outline.json").read_text(encoding="utf-8"))
        content = {"sections": []}
        for section in outline["sections"]:
            children = []
            for child in section["subsections"]:
                paragraph = PROSE
                if child.get("evidence_ids"):
                    paragraph += " Observed accuracy was [[metric:pilot.baseline.accuracy]]."
                children.append({"id": child["id"], "paragraphs": [paragraph]})
            content["sections"].append({"id": section["id"], "paragraphs": [PROSE], "subsections": children})
        source = self.root / "content.json"
        source.write_text(json.dumps(content), encoding="utf-8")
        report = fill_project(framework, self.root / "paper", content_json=source)
        self.assertEqual(report["calls"], [])
        self.assertEqual(report["status"], "completed")
        for filename in ("research_plan.json", "RESEARCH_HANDOFF.md"):
            self.assertEqual((framework / filename).read_bytes(), (self.root / "paper" / filename).read_bytes())
        request = json.loads((self.root / "paper/generation_request.json").read_text(encoding="utf-8"))
        payload = json.loads(request[1]["content"])
        self.assertEqual(payload["research_plan"], outline["research_plan"])
        self.assertIn("Planned experiments have NOT run", request[0]["content"])
        self.assertFalse(any(key.startswith("fair.") for key in payload["metric_tokens"]))
        content["sections"][5]["paragraphs"] = [PROSE + " Accuracy was [[metric:fair.baseline.accuracy]]."]
        with self.assertRaisesRegex(ValueError, "Unknown measurement token"):
            validate_content(content, outline, {}, self.citations)


if __name__ == "__main__":
    unittest.main()
