"""Offline regression checks for handoff integrity and honest evidence handling."""

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / "scripts"))

from paper_framework.citations import bibliography, build_citations
from paper_framework.compiler import compile_project
from paper_framework.project import generate_project


class FrameworkTests(unittest.TestCase):
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

    def generate(self, literature=None):
        return generate_project(self.write("brief.json", self.brief), self.root / "paper",
                                self.write("literature.json", literature) if literature is not None else None)

    def outline(self):
        return json.loads((self.root / "paper/outline.json").read_text(encoding="utf-8"))

    def test_no_dependencies_required_for_minimal_draft(self):
        self.brief.pop("methods")
        self.brief.pop("experiments")
        manifest = self.generate()
        self.assertFalse(manifest["ready_for_submission"])
        self.assertEqual(len(self.outline()["sections"]), 8)
        self.assertNotIn(r"\bibliography{", (self.root / "paper/paper.tex").read_text())
        self.assertTrue((self.root / "paper/iclr2027_conference.sty").is_file())

    def test_planned_experiment_does_not_become_a_result(self):
        self.generate()
        outline = self.outline()
        sections = {s["id"]: s for s in outline["sections"]}
        self.assertEqual(len(sections["experiments"]["subsections"]), 1)
        self.assertEqual(sections["results"]["subsections"], [])
        self.assertEqual(outline["evidence"], [])

    def test_completed_evidence_is_hashed_but_not_claimed_as_verified(self):
        evidence = self.write("actual.json", {"accuracy": 0.25})
        self.brief["experiments"][0].update(status="completed", result_path="actual.json")
        self.generate()
        record = self.outline()["evidence"][0]
        self.assertEqual(record["sha256"], hashlib.sha256(evidence.read_bytes()).hexdigest())
        self.assertEqual(record["validation"], "file_exists_and_hashed_only")
        tex = (self.root / "paper/sections/results.tex").read_text()
        self.assertNotIn("0.25", tex)
        self.assertIn("Context Budget Comparison", tex)

    def test_missing_completed_evidence_fails_before_output(self):
        self.brief["experiments"][0].update(status="completed", result_path="missing.json")
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.generate()
        self.assertFalse((self.root / "paper").exists())

    def test_unknown_citation_fails_before_output(self):
        self.brief["methods"][0]["citation_ids"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "Unknown citation"):
            self.generate(self.literature)
        self.assertFalse((self.root / "paper").exists())

    def test_citation_handoff_resolves_explicit_id(self):
        self.brief["methods"][0]["citation_ids"] = ["memgpt"]
        self.generate(self.literature)
        mapping = json.loads((self.root / "paper/citation_map.json").read_text())
        key = mapping["by_source_id"]["memgpt"]
        methods = next(s for s in self.outline()["sections"] if s["id"] == "method")
        self.assertEqual(methods["subsections"][0]["citation_keys"], [key])
        self.assertIn("{" + key + ",", (self.root / "paper/references.bib").read_text())

    def test_versioned_arxiv_duplicates_have_stable_keys(self):
        duplicate = copy.deepcopy(self.literature[0])
        duplicate.update(id="duplicate", arxiv_id="https://arxiv.org/abs/2310.08560v2")
        a = build_citations(self.literature + [duplicate])
        b = build_citations([duplicate] + self.literature)
        self.assertEqual(len(a["entries"]), 1)
        self.assertEqual(a["by_source_id"], b["by_source_id"])
        self.assertEqual(a["by_source_id"]["memgpt"], a["by_source_id"]["duplicate"])

    def test_doi_dedup_and_metadata_fallback(self):
        item = {"id": "a", "title": "Test", "authors": ["Test Author"], "year": 2025,
                "doi": "https://doi.org/10.1234/ABC"}
        other = dict(item, id="b", doi="doi:10.1234/abc")
        result = build_citations([item, other])
        self.assertEqual(len(result["entries"]), 1)
        self.assertEqual(result["entries"][0]["doi"], "10.1234/abc")
        item.pop("doi")
        other.pop("doi")
        self.assertEqual(len(build_citations([item, other])["entries"]), 1)

    def test_incomplete_or_conflicting_metadata_is_not_invented(self):
        bad = dict(self.literature[0], authors=[])
        with self.assertRaisesRegex(ValueError, "authors"):
            build_citations([bad])
        bad = dict(self.literature[0], title="Different paper")
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            build_citations(self.literature + [bad])

    def test_plain_text_is_escaped_and_template_markers_are_not_reexpanded(self):
        self.brief["title"] = r"A & B_50% \input{secret} @@SECTIONS@@"
        self.generate()
        tex = (self.root / "paper/paper.tex").read_text()
        self.assertIn(r"A \& B\_50\% \textbackslash{}input\{secret\} @@SECTIONS@@", tex)
        self.assertEqual(tex.count(r"\input{sections/introduction.tex}"), 1)
        item = dict(self.literature[0], title="A {B} & C_50%")
        self.assertIn(r"A \{B\} \& C\_50\%", bibliography(build_citations([item])))

    def test_existing_work_is_never_overwritten(self):
        self.generate()
        section = self.root / "paper/sections/introduction.tex"
        section.write_text("Manual work", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.generate()
        self.assertEqual(section.read_text(), "Manual work")

    def test_missing_style_fails_before_output(self):
        with self.assertRaisesRegex(ValueError, "Missing template"):
            generate_project(self.write("brief.json", self.brief), self.root / "paper",
                             template_dir=self.root / "missing")
        self.assertFalse((self.root / "paper").exists())

    def test_cli_paths_work_outside_repository(self):
        result = subprocess.run([sys.executable, str(MODULE / "scripts/generate_framework.py"),
                                 "--brief", str(MODULE / "examples/brief.json"), "--output", "draft"],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "draft/paper.tex").is_file())

    def test_missing_latex_has_clear_error(self):
        self.generate()
        with patch("paper_framework.compiler.shutil.which", return_value=None):
            with self.assertRaisesRegex(ValueError, "pdflatex"):
                compile_project(self.root / "paper")

    def test_compile_failure_is_reported_not_masked_by_an_old_pdf(self):
        self.generate()
        (self.root / "paper/paper.pdf").write_bytes(b"old result")
        failed = subprocess.CompletedProcess([], 1, "LaTeX error", "")
        with patch("paper_framework.compiler.shutil.which", return_value="tool"), \
             patch("paper_framework.compiler.subprocess.run", return_value=failed):
            with self.assertRaisesRegex(ValueError, "Compilation failed"):
                compile_project(self.root / "paper")
        report = json.loads((self.root / "paper/compile_report.json").read_text())
        self.assertFalse(report["success"])
        self.assertIn("LaTeX error", report["commands"][0]["output_tail"])

    def test_compiler_waits_for_stable_references_and_bounds_retries(self):
        self.generate()
        project = self.root / "paper"
        for stable_after in (4, 99):
            calls = []

            def simulate(command, **kwargs):
                calls.append(command)
                (project / "paper.aux").write_text("", encoding="utf-8")
                (project / "paper.pdf").write_bytes(b"%PDF-test")
                (project / "paper.log").write_text(
                    "LaTeX Warning: Label(s) may have changed. Rerun to get cross-references right."
                    if len(calls) < stable_after else "Output written on paper.pdf (1 page).", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("paper_framework.compiler.shutil.which", return_value="tool"), \
                    patch("paper_framework.compiler.subprocess.run", side_effect=simulate):
                if stable_after == 4:
                    compile_project(project)
                    self.assertEqual(len(calls), 4)
                else:
                    with self.assertRaisesRegex(ValueError, "did not stabilize"):
                        compile_project(project)
                    self.assertEqual(len(calls), 5)
                    report = json.loads((project / "compile_report.json").read_text())
                    self.assertFalse(report["success"])

    @unittest.skipUnless(shutil.which("pdflatex") and shutil.which("bibtex"), "LaTeX tools not installed")
    def test_real_bibtex_and_citation_survive_content_handoff(self):
        self.generate(self.literature)
        key = build_citations(self.literature)["by_source_id"]["memgpt"]
        section = self.root / "paper/sections/related_work.tex"
        section.write_text(r"\section{Related Work}" + "\nCitation plumbing check: \\citep{" + key + "}.\n",
                           encoding="utf-8")
        pdf = compile_project(self.root / "paper")
        self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
        report = json.loads((self.root / "paper/compile_report.json").read_text())
        self.assertTrue(report["success"])
        self.assertEqual(len(report["commands"]), 4)
        self.assertNotIn("undefined", " ".join(report["warnings"]))

    @unittest.skipUnless(shutil.which("pdflatex"), "LaTeX tools not installed")
    def test_real_empty_bibliography_and_unresolved_citation_detection(self):
        self.brief.update(anonymous=False, authors=["Alice Example", "Bob Example"])
        self.generate()
        compile_project(self.root / "paper")
        report = json.loads((self.root / "paper/compile_report.json").read_text())
        self.assertEqual(len(report["commands"]), 3)
        section = self.root / "paper/sections/introduction.tex"
        section.write_text(r"\section{Introduction} Missing: \citep{not_in_library}.", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Unresolved citations"):
            compile_project(self.root / "paper")
        report = json.loads((self.root / "paper/compile_report.json").read_text())
        self.assertFalse(report["success"])


if __name__ == "__main__":
    unittest.main()
