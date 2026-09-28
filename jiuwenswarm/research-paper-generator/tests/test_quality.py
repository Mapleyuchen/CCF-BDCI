"""Quality-gate checks against framework drafts and a hand-filled project."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / "scripts"))

from paper_framework.project import generate_project
from paper_quality.checker import check_project


PROSE = (
    "This section states the research question, the method, and the limits of the current evidence. "
    "It does not claim a leaderboard result. Measurements stay in the cited result files."
)


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.brief = json.loads((MODULE / "examples/brief.json").read_text(encoding="utf-8"))
        self.literature = json.loads((MODULE / "examples/literature.json").read_text(encoding="utf-8"))

    def write(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def generate(self, literature=None, name="paper"):
        return generate_project(self.write("brief.json", self.brief), self.root / name,
                                self.write("literature.json", literature) if literature is not None else None)

    def ids(self, report, check_id, passed=None):
        items = [item for item in report["checks"] if item["id"] == check_id]
        if passed is not None:
            items = [item for item in items if item["passed"] is passed]
        return items

    def test_skeleton_is_not_ready(self):
        self.generate()
        report = check_project(self.root / "paper")
        self.assertFalse(report["ready_for_submission"])
        self.assertTrue(self.ids(report, "completeness_placeholder", False))
        self.assertTrue(self.ids(report, "format_draft_banner", False))
        self.assertTrue(self.ids(report, "format_compile", False))
        self.assertTrue(self.ids(report, "format_anonymous", True))
        self.assertGreater(report["summary"]["errors"], 0)
        self.assertTrue((self.root / "paper/quality_report.json").is_file())

    def test_literature_skeleton_still_has_draft_citations(self):
        self.generate(self.literature, name="cited")
        report = check_project(self.root / "cited")
        self.assertTrue(self.ids(report, "completeness_draft_bibliography", False))
        self.assertTrue(self.ids(report, "format_bibliography_order", True))

    def ready_draft(self):
        self.brief.pop("methods", None)
        self.brief.pop("experiments", None)
        self.generate()
        project = self.root / "paper"
        for path in (project / "sections").glob("*.tex"):
            path.write_text(PROSE + "\n", encoding="utf-8")
        paper = project / "paper.tex"
        paper.write_text(paper.read_text(encoding="utf-8").replace(
            r"\lhead{Research paper framework -- draft}", ""), encoding="utf-8")
        report = project / "compile_report.json"
        pdf = project / "paper.pdf"
        report.write_text(json.dumps({"success": True, "warnings": []}), encoding="utf-8")
        (project / "paper.log").write_text("Output written on paper.pdf (6 pages, 1000 bytes).\n", encoding="utf-8")
        pdf.write_bytes(b"%PDF-1.4\n")
        stamp = time.time() + 30
        os.utime(report, (stamp, stamp))
        os.utime(pdf, (stamp, stamp))
        return project

    def test_filled_anonymous_draft_can_pass(self):
        project = self.ready_draft()
        report = check_project(project)
        self.assertTrue(report["ready_for_submission"], [item for item in report["checks"] if not item["passed"]])
        self.assertEqual(report["summary"]["errors"], 0)

    def test_source_edited_after_compile_is_stale(self):
        project = self.ready_draft()
        section = project / "sections/introduction.tex"
        later = time.time() + 120
        os.utime(section, (later, later))
        report = check_project(project)
        self.assertTrue(self.ids(report, "format_compile_stale", False))

    def test_section_omitted_from_paper_tex_fails(self):
        project = self.ready_draft()
        paper = project / "paper.tex"
        paper.write_text(paper.read_text(encoding="utf-8").replace(r"\input{sections/discussion.tex}", ""),
                         encoding="utf-8")
        stamp = time.time() + 30
        os.utime(project / "compile_report.json", (stamp, stamp))
        os.utime(project / "paper.pdf", (stamp, stamp))
        report = check_project(project)
        self.assertTrue(self.ids(report, "completeness_section_input", False))

    def test_assigned_citation_must_be_used_and_defined(self):
        self.brief["methods"][0]["citation_ids"] = ["memgpt"]
        self.generate(self.literature, name="cited-method")
        project = self.root / "cited-method"
        report = check_project(project)
        self.assertTrue(self.ids(report, "completeness_assigned_citation", False))
        self.assertTrue(self.ids(report, "completeness_citation_used", False))
        key = json.loads((project / "citation_map.json").read_text())["by_source_id"]["memgpt"]
        method = project / "sections/method.tex"
        method.write_text(PROSE + f" Memory systems include \\citep{{{key},not_a_key}}.\n", encoding="utf-8")
        report = check_project(project)
        self.assertFalse(self.ids(report, "completeness_assigned_citation", False))
        self.assertTrue(self.ids(report, "completeness_citation_unknown", False))

    def test_result_numbers_must_come_from_the_evidence_file(self):
        self.write("actual.json", {"accuracy": 0.25})
        self.brief["experiments"][0].update(status="completed", result_path="actual.json")
        self.generate(name="measured")
        results = self.root / "measured/sections/results.tex"
        results.write_text(PROSE + " The measured accuracy is 0.25.\n", encoding="utf-8")
        report = check_project(self.root / "measured")
        self.assertTrue(self.ids(report, "completeness_result_numbers", True))
        results.write_text(PROSE + " The measured accuracy is 90\\%.\n", encoding="utf-8")
        report = check_project(self.root / "measured")
        self.assertTrue(self.ids(report, "completeness_result_numbers", False))

    def test_planned_experiment_cannot_claim_a_gain(self):
        self.generate(name="planned")
        results = self.root / "planned/sections/results.tex"
        results.write_text(PROSE + " Accuracy improved by 20\\%.\n", encoding="utf-8")
        report = check_project(self.root / "planned")
        self.assertTrue(self.ids(report, "completeness_planned_result", False))

    def test_camera_ready_flag_blocks_anonymous_submission(self):
        self.generate()
        paper = self.root / "paper/paper.tex"
        paper.write_text(paper.read_text(encoding="utf-8") + "\n\\iclrfinalcopy\n", encoding="utf-8")
        report = check_project(self.root / "paper")
        self.assertTrue(self.ids(report, "format_anonymous", False))

    def test_missing_figure_and_changed_evidence_are_errors(self):
        evidence = self.write("actual.json", {"accuracy": 0.25})
        self.brief["experiments"][0].update(status="completed", result_path="actual.json")
        self.generate()
        evidence.write_text('{"accuracy": 0.9}', encoding="utf-8")
        method = self.root / "paper/sections/method.tex"
        method.write_text(method.read_text(encoding="utf-8") + "\n\\includegraphics{figures/missing.png}\n",
                          encoding="utf-8")
        report = check_project(self.root / "paper")
        self.assertTrue(self.ids(report, "completeness_evidence_hash", False))
        self.assertTrue(self.ids(report, "format_figures", False))
        self.assertEqual(self.ids(report, "format_figures", False)[0]["severity"], "error")

    def test_chinese_prose_and_writing_stubs_fail_grammar(self):
        self.brief.pop("methods")
        self.brief.pop("experiments")
        self.generate()
        section = self.root / "paper/sections/introduction.tex"
        section.write_text(PROSE + " TODO 这里还没写完。\n", encoding="utf-8")
        report = check_project(self.root / "paper")
        self.assertTrue(self.ids(report, "grammar_cjk", False))
        self.assertTrue(self.ids(report, "grammar_stub", False))

    def test_missing_project_is_a_usage_error(self):
        with self.assertRaisesRegex(ValueError, "paper.tex"):
            check_project(self.root / "missing")

    def test_cli_exits_nonzero_until_the_draft_is_ready(self):
        self.generate()
        script = MODULE / "scripts/check_quality.py"
        failed = subprocess.run([sys.executable, str(script), str(self.root / "paper")],
                                capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
        self.assertIn("Not ready for submission", failed.stderr)
        self.assertIn("completeness_placeholder", failed.stdout)


if __name__ == "__main__":
    unittest.main()
