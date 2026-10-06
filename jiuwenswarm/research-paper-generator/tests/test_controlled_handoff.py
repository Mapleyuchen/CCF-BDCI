"""Completed module-2 evidence must remain correctly scoped and portable."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / "scripts"))
from audit_framework import audit_project
from paper_framework.project import generate_project
from paper_framework.materials import verify_materials
from paper_content.project import fill_project
from paper_content.prose import render_paragraph
from paper_quality.checker import check_project
from prepare_controlled_brief import curate, REPORT
from test_content import experiment, PROSE


class ControlledHandoffTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "asset.tex"
        self.source.write_text("Upstream source for manual integration.", encoding="utf-8")
        (self.root / "run.json").write_text(json.dumps(experiment()), encoding="utf-8")
        self.brief = {"schema_version": 1, "title": "Portable Controlled Study", "research_question": "What does memory cost?",
            "experiments": [{"id": "trial", "title": "Measured Comparison", "status": "completed", "result_path": "run.json"}],
            "supporting_materials": [{"id": "source", "title": "Upstream prose", "kind": "prose", "path": "asset.tex",
                "purpose": "Review and adapt this prose.", "placement": "handoff", "experiment_ids": ["trial"]}]}

    def generate(self):
        source = self.root / "brief.json"
        source.write_text(json.dumps(self.brief), encoding="utf-8")
        generate_project(source, self.root / "framework")
        return json.loads((self.root / "framework/outline.json").read_text(encoding="utf-8"))

    def content(self, outline):
        sections = []
        for section in outline["sections"]:
            children = []
            for child in section["subsections"]:
                text = PROSE + (" Accuracy was [[metric:trial.baseline.accuracy]]." if child.get("evidence_ids") else "")
                children.append({"id": child["id"], "paragraphs": [text]})
            sections.append({"id": section["id"], "paragraphs": [PROSE], "subsections": children})
        path = self.root / "content.json"
        path.write_text(json.dumps({"sections": sections}), encoding="utf-8")
        return path

    def test_moved_framework_and_filled_paper_preserve_materials(self):
        outline = self.generate()
        moved = self.root / "moved"
        (self.root / "framework").rename(moved)
        self.source.rename(self.root / "unavailable.tex")
        verify_materials(outline, moved)
        report = fill_project(moved, self.root / "paper", content_json=self.content(outline))
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["calls"], [])
        paper = self.root / "paper"
        filled = json.loads((paper / "outline.json").read_text(encoding="utf-8"))
        verify_materials(filled, paper)
        self.assertEqual((moved / "supporting/source.tex").read_bytes(), (paper / "supporting/source.tex").read_bytes())
        self.assertNotIn("Upstream source", (paper / "sections/results.tex").read_text(encoding="utf-8"))
        request = json.loads((paper / "generation_request.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads(request[1]["content"])["supporting_materials"][0]["project_path"], "supporting/source.tex")

    def test_tampered_material_blocks_content_and_fails_quality(self):
        outline = self.generate()
        (self.root / "framework/supporting/source.tex").write_text("Changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Supporting material changed"):
            fill_project(self.root / "framework", self.root / "paper", content_json=self.content(outline))
        self.assertFalse((self.root / "paper").exists())
        report = check_project(self.root / "framework")
        self.assertTrue(any(c["id"] == "completeness_supporting_materials" and not c["passed"] for c in report["checks"]))

    def test_supporting_path_cannot_escape_or_fall_back(self):
        outline = self.generate()
        outline["supporting_materials"][0]["project_path"] = "../asset.tex"
        with self.assertRaisesRegex(ValueError, "outside"):
            verify_materials(outline, self.root / "framework")
        outline["supporting_materials"][0]["project_path"] = "supporting/missing.tex"
        with self.assertRaisesRegex(ValueError, "changed or missing"):
            verify_materials(outline, self.root / "framework")

    def test_declared_hash_or_invalid_material_link_fails_before_output(self):
        original = deepcopy(self.brief)
        for mutate in (
            lambda b: b["supporting_materials"][0].update(sha256="0" * 64),
            lambda b: b["supporting_materials"][0].update(experiment_ids=["missing"]),
            lambda b: b["experiments"][0].update(result_sha256="0" * 64),
        ):
            self.brief = deepcopy(original)
            mutate(self.brief)
            with self.assertRaises(ValueError):
                self.generate()
            self.assertFalse((self.root / "framework").exists())

    def test_real_curated_handoff_covers_all_budgets_and_keeps_human_review_open(self):
        curated = self.root / "curated.json"
        brief = curate(MODULE / "examples/memory-eval-v2.brief.json", REPORT, curated)
        framework = self.root / "complete"
        generate_project(curated, framework, MODULE / "examples/memory-research.literature.json")
        report = audit_project(framework)
        self.assertEqual(len(report["primary_results"]), 7)
        self.assertEqual(len(report["supplementary_results"]), 15)
        self.assertEqual(report["metric_count"], 357)
        primary = report["primary_results"][:3]
        self.assertEqual([r["context_tokens"] for r in primary], [512, 1024, 2048])
        self.assertTrue(all(r["accuracy_gain_pp"] < 0 for r in primary))
        self.assertTrue(all(r["group_labels"] == {"baseline": "bm25", "enhanced": "hybrid"} for r in primary))
        self.assertEqual(report["review_queues"][0]["missing_decision"], 0)
        self.assertTrue(report["scientific_review_required"])
        self.assertNotIn("writing_profile", brief)
        outline_path = framework / "outline.json"
        outline = json.loads(outline_path.read_text(encoding="utf-8"))
        outline["research_plan"]["experiments"][0]["protocol"]["budget"]["values"] = [600]
        outline_path.write_text(json.dumps(outline), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Declared protocol differs"):
            audit_project(framework)
        self.assertEqual(json.loads((framework / "framework_audit.json").read_text())["status"], "failed")

    def test_real_arm_names_with_digits_are_allowed_without_weakening_numeric_checks(self):
        citations = {"entries": [], "by_source_id": {}}
        self.assertIn("BM25", render_paragraph("BM25 is a measured comparator.", {}, citations, ["bm25"]))
        for text in ("BM250 is better.", "BM25 accuracy is 99.9%."):
            with self.assertRaisesRegex(ValueError, "Numeric prose"):
                render_paragraph(text, {}, citations, ["bm25"])


if __name__ == "__main__":
    unittest.main()
