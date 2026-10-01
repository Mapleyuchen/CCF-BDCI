"""Cross-directory handoff checks for modules 3, 4 and 5 and offline orchestration."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / "scripts"))

import write_paper
from paper_content.evidence import load_evidence
from paper_content.project import fill_project
from paper_framework.project import generate_project
from paper_quality.checker import check_project
from test_content import experiment, PROSE


class HandoffTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "run.json"
        self.source.write_text(json.dumps(experiment()), encoding="utf-8")
        self.brief = self.root / "brief.json"
        self.brief.write_text(json.dumps({
            "schema_version": 1, "title": "Portable Memory Study", "research_question": "What does retrieval cost?",
            "experiments": [{"id": "trial", "title": "Paired Trial", "status": "completed", "result_path": "run.json"}],
        }), encoding="utf-8")
        self.framework = self.root / "framework"
        generate_project(self.brief, self.framework)
        self.outline = json.loads((self.framework / "outline.json").read_text(encoding="utf-8"))
        content = {"sections": []}
        for section in self.outline["sections"]:
            children = []
            for child in section["subsections"]:
                text = PROSE
                if child.get("evidence_ids"):
                    text += " Accuracy was [[metric:trial.baseline.accuracy]]."
                children.append({"id": child["id"], "paragraphs": [text]})
            content["sections"].append({"id": section["id"], "paragraphs": [PROSE], "subsections": children})
        self.content = self.root / "content.json"
        self.content.write_text(json.dumps(content), encoding="utf-8")

    def test_framework_contains_a_byte_identical_evidence_snapshot(self):
        entry = self.outline["evidence"][0]
        self.assertIn("project_path", entry)
        self.assertEqual((self.framework / entry["project_path"]).read_bytes(), self.source.read_bytes())

    def test_moved_framework_fills_without_the_original_experiment(self):
        moved = self.root / "teammate-framework"
        self.framework.rename(moved)
        self.source.rename(self.root / "source-unavailable.json")
        report = fill_project(moved, self.root / "paper", content_json=self.content)
        self.assertEqual(report["calls"], [])
        self.assertEqual(report["status"], "completed")
        self.assertEqual(json.loads((self.root / "paper/evidence/trial.json").read_text())["kind"], "live_model_experiment")

    def test_moved_paper_quality_reads_local_evidence_and_derived_numbers(self):
        fill_project(self.framework, self.root / "paper", content_json=self.content)
        moved = self.root / "teammate-paper"
        (self.root / "paper").rename(moved)
        self.source.rename(self.root / "source-unavailable.json")
        quality = check_project(moved)
        failed_evidence = [c for c in quality["checks"] if not c["passed"] and c["id"] in {
            "completeness_evidence_missing", "completeness_evidence_hash", "completeness_result_numbers"}]
        self.assertEqual(failed_evidence, [])

    def test_snapshot_tampering_does_not_fall_back_to_the_original(self):
        entry = self.outline["evidence"][0]
        self.assertIn("project_path", entry)
        (self.framework / entry["project_path"]).write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed or missing"):
            fill_project(self.framework, self.root / "failed", content_json=self.content)
        self.assertFalse((self.root / "failed").exists())

    def test_missing_snapshot_does_not_fall_back_to_the_original(self):
        entry = self.outline["evidence"][0]
        snapshot = self.framework / entry["project_path"]
        snapshot.rename(snapshot.with_suffix(".unavailable"))
        with self.assertRaisesRegex(ValueError, "changed or missing"):
            fill_project(self.framework, self.root / "failed", content_json=self.content)

    def test_later_source_changes_do_not_rewrite_the_planned_evidence(self):
        self.source.write_text("{}", encoding="utf-8")
        result = load_evidence(self.outline, self.framework)[0]
        self.assertEqual(result["paired_observations"], 2)
        self.assertEqual(result["groups"]["baseline"]["accuracy"], 0.5)

    def test_portable_evidence_cannot_escape_the_project(self):
        self.outline["evidence"][0]["project_path"] = "../run.json"
        (self.framework / "outline.json").write_text(json.dumps(self.outline), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "outside"):
            fill_project(self.framework, self.root / "failed", content_json=self.content)
        quality = check_project(self.framework)
        self.assertTrue(any(c["id"] == "completeness_evidence_missing" and not c["passed"] for c in quality["checks"]))

    def test_legacy_absolute_evidence_remains_readable(self):
        entry = self.outline["evidence"][0]
        entry.pop("project_path", None)
        entry["resolved_path"] = str(self.source)
        self.assertEqual(load_evidence(self.outline)[0]["paired_observations"], 2)

    def test_one_command_offline_path_does_not_load_model_credentials(self):
        literature = self.root / "literature.json"
        literature.write_text("[]", encoding="utf-8")
        argv = ["write_paper.py", "--brief", str(self.brief), "--literature", str(literature),
                "--content-json", str(self.content), "--output", str(self.root / "offline")]
        with patch.object(sys, "argv", argv), patch.object(write_paper, "load_model_config", side_effect=AssertionError("No credentials")), \
                patch.object(write_paper, "JsonModel", side_effect=AssertionError("No model calls")):
            write_paper.main()
        report = json.loads((self.root / "offline/paper/content_report.json").read_text())
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["calls"], [])

    def test_offline_mode_rejects_paid_image_generation_before_creating_output(self):
        output = self.root / "invalid-offline"
        argv = ["write_paper.py", "--content-json", str(self.content), "--generate-methodology", "--output", str(output)]
        with patch.object(sys, "argv", argv), patch.object(write_paper, "load_model_config", side_effect=AssertionError("No credentials")):
            with self.assertRaises(SystemExit) as stopped:
                write_paper.main()
        self.assertEqual(stopped.exception.code, 2)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
