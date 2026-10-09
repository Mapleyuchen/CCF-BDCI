"""Content handoff, evidence integrity and real LaTeX integration checks."""

from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / "scripts"))

from paper_content.evidence import load_evidence, metric_catalog, normalize_result
from paper_content.model import JsonModel, load_model_config
from paper_content.project import fill_project
from paper_content.prose import render_paragraph, validate_content
from paper_framework.project import generate_project

PROSE = ("This controlled comparison examines retrieval within a shared context budget while preserving the same questions "
         "and accounting for the additional memory writing cost. The evidence supports a limited descriptive comparison.")


def experiment():
    records = []
    for group in ("baseline", "enhanced"):
        for q in range(2):
            records.append({"group": group, "repeat": 0, "question_id": f"q{q}",
                            "query": f"Question {q}", "answers": [f"Answer {q}"], "status": "ok",
                            "correct": group == "enhanced" or q == 0, "evidence_recall": float(group == "enhanced" or q == 0),
                            "history_isolated": True, "memory_in_model_prompt": True,
                            "total_tokens": 10, "latency_ms": 1.234, "seed_latency_ms": 10})
    return {"kind": "live_model_experiment", "dataset_sha256": "a" * 64,
            "settings": {"model_name": "test-model", "context_chars": 600}, "records": records,
            "runs": [{"group": g, "repeat": 0, "seed_total_tokens": 100 if g == "enhanced" else 0,
                      "seed_model_calls": 2 if g == "enhanced" else 0,
                      "seed_latency_ms": 10 if g == "enhanced" else 0} for g in ("baseline", "enhanced")],
            "summary": {"baseline": {"accuracy": 0.999}}}


class ContentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = experiment()
        self.result = self.write("run.json", self.data)
        self.brief = {"schema_version": 1, "title": "An Evidence-Based Memory Study", "research_question": "What does retrieval cost?",
                      "methods": [{"id": "selection", "title": "Memory Selection", "description": "Rank stored facts."}],
                      "experiments": [{"id": "trial", "title": "Paired Trial", "status": "completed", "result_path": "run.json"}]}
        generate_project(self.write("brief.json", self.brief), self.root / "framework")
        self.outline = json.loads((self.root / "framework/outline.json").read_text())
        self.citations = {"entries": [], "by_source_id": {}}
        self.results = load_evidence(self.outline)
        self.metrics = metric_catalog(self.results)
        self.content = {"sections": []}
        for section in self.outline["sections"]:
            children = []
            for child in section["subsections"]:
                text = PROSE
                if child.get("evidence_ids"):
                    text += " Accuracy was [[metric:trial.baseline.accuracy]] and [[metric:trial.enhanced.accuracy]]."
                children.append({"id": child["id"], "paragraphs": [text]})
            self.content["sections"].append({"id": section["id"], "paragraphs": [PROSE], "subsections": children})

    def write(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_recomputes_scores_and_counts_write_cost_once(self):
        result = self.results[0]
        self.assertEqual(result["groups"]["baseline"]["accuracy"], .5)
        self.assertEqual(result["groups"]["enhanced"]["tokens_per_question"], 60)
        self.assertAlmostEqual(result["groups"]["enhanced"]["end_to_end_latency_ms"], 6.234)
        self.assertEqual(result["accuracy_gain_pp"], 50)

    def test_missing_usage_remains_unknown(self):
        self.data["records"][0]["total_tokens"] = None
        result = normalize_result(self.write("missing.json", self.data), "trial", "Trial")
        self.assertIsNone(result["groups"]["baseline"]["tokens_per_question"])

    def test_excludes_both_arms_of_invalid_pair_and_keeps_cost(self):
        self.data["records"][0]["history_isolated"] = False
        result = normalize_result(self.write("invalid.json", self.data), "trial", "Trial")
        self.assertEqual(result["paired_observations"], 1)
        self.assertEqual(result["groups"]["enhanced"]["excluded_records"], 1)
        self.assertEqual(result["groups"]["enhanced"]["tokens_per_question"], 120)

    def test_rejects_fake_legacy_duplicate_or_nonfinite_results(self):
        for kind in ("adapted_longmemeval_self_test", "self_test", "legacy"):
            invalid = dict(self.data, kind=kind)
            with self.assertRaisesRegex(ValueError, "live"):
                normalize_result(self.write("bad.json", invalid), "trial", "Trial")
        self.data["records"].append(self.data["records"][0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            normalize_result(self.write("bad.json", self.data), "trial", "Trial")
        self.data["records"].pop()
        self.data["records"][0]["latency_ms"] = float("nan")
        with self.assertRaisesRegex(ValueError, "measurement"):
            normalize_result(self.write("bad.json", self.data), "trial", "Trial")

    def test_hash_change_fails_before_creating_output(self):
        snapshot = self.root / "framework" / self.outline["evidence"][0]["project_path"]
        snapshot.write_text("{}")
        with self.assertRaisesRegex(ValueError, "changed"):
            fill_project(self.root / "framework", self.root / "filled", content_json=self.write("content.json", self.content))
        self.assertFalse((self.root / "filled").exists())

    def test_unknown_metrics_citations_raw_numbers_and_latex_rejected(self):
        for text in ("Gain [[metric:invented.accuracy]]", "See [[cite:fake-paper]]", "Accuracy was 99.9%.", r"\input{secret}"):
            with self.assertRaises(ValueError):
                render_paragraph(text, self.metrics, self.citations)
        rendered = render_paragraph("Accuracy [[metric:trial.baseline.accuracy]] & cost.", self.metrics, self.citations)
        self.assertIn(r"50.0\%", rendered)
        self.assertIn(r"\&", rendered)
        redundant = render_paragraph("Accuracy [[metric:trial.baseline.accuracy]]%.", self.metrics, self.citations)
        self.assertEqual(redundant.count(r"\%"), 1)
        gain = render_paragraph("Gain [[metric:trial.accuracy_gain_pp]] percentage points.", self.metrics, self.citations)
        self.assertEqual(gain.count("percentage points"), 1)
        self.assertIn("50 percentage points", gain)

    def test_missing_section_or_unlinked_result_rejected(self):
        content = deepcopy(self.content)
        content["sections"].pop()
        with self.assertRaisesRegex(ValueError, "eight"):
            validate_content(content, self.outline, self.metrics, self.citations)
        content = deepcopy(self.content)
        content["sections"][5]["subsections"][0]["paragraphs"] = [PROSE]
        with self.assertRaisesRegex(ValueError, "reference its evidence"):
            validate_content(content, self.outline, self.metrics, self.citations)

    def test_citation_aliases_resolve_and_required_citations_are_checked(self):
        citations = {"entries": [{"cite_key": "ref_abc"}], "by_source_id": {"source": "ref_abc"}}
        self.assertIn(r"\citep{ref_abc}", render_paragraph("See [[cite:source]].", self.metrics, citations))
        outline = deepcopy(self.outline)
        outline["sections"][3]["subsections"][0]["citation_keys"] = ["ref_abc"]
        with self.assertRaisesRegex(ValueError, "assigned citation"):
            validate_content(self.content, outline, self.metrics, citations)

    def test_existing_output_and_path_escape_are_rejected(self):
        content_path = self.write("content.json", self.content)
        with self.assertRaisesRegex(ValueError, "never overwritten"):
            fill_project(self.root / "framework", self.root / "framework", content_json=content_path)
        self.outline["sections"][0]["file"] = "../escaped.tex"
        self.write("framework/outline.json", self.outline)
        with self.assertRaisesRegex(ValueError, "outside"):
            fill_project(self.root / "framework", self.root / "filled", content_json=content_path)

    @unittest.skipUnless(shutil.which("pdflatex") and shutil.which("bibtex"), "LaTeX not installed")
    def test_content_handoff_compiles_with_generated_figures_and_evidence(self):
        original = (self.root / "framework/sections/abstract.tex").read_bytes()
        report = fill_project(self.root / "framework", self.root / "filled",
                              content_json=self.write("content.json", self.content), compile_pdf=True)
        self.assertEqual(report["status"], "completed", report)
        self.assertEqual(report["quality"]["errors"], 0)
        self.assertTrue(report["human_review_required"])
        self.assertEqual(original, (self.root / "framework/sections/abstract.tex").read_bytes())
        self.assertTrue((self.root / "filled/figures/trial.svg").is_file())
        self.assertTrue((self.root / "filled/paper.pdf").read_bytes().startswith(b"%PDF-"))
        self.assertEqual((self.root / "filled/evidence/trial.json").read_bytes(), self.result.read_bytes())

    def test_model_config_uses_existing_environment_without_saving_secrets(self):
        path = self.root / "model.yaml"
        path.write_text('models:\n  defaults:\n    - is_default: true\n      model_client_config:\n'
                        '        api_base: https://example.test/v1\n        api_key: ${PAPER_TEST_KEY}\n'
                        '        model_name: example-model\n        client_provider: OpenAI\n')
        with patch.dict(os.environ, {"PAPER_TEST_KEY": "private-unit-test-value"}):
            config = load_model_config(path)
        self.assertEqual(config["client"]["api_key"], "private-unit-test-value")
        self.assertNotIn("private-unit-test-value", path.read_text())

    def test_reviewed_related_work_is_preserved_and_failed_drafts_are_retained(self):
        reviewed = "This reviewed literature discussion is supplied by the collaborating author and must remain intact. " + PROSE
        output = self.root / "filled"
        report = fill_project(self.root / "framework", output, content_json=self.write("content.json", self.content),
                              related_work=self.write("related.json", {"paragraphs": [reviewed]}))
        saved = json.loads((output / "content.json").read_text())
        self.assertEqual(saved["sections"][2]["paragraphs"], [reviewed])
        self.assertFalse(report["mechanical_checks_passed"])  # PDF has not been compiled.
        self.content["sections"][0]["paragraphs"] = [PROSE + " Invalid [[metric:invented]]."]
        with self.assertRaisesRegex(ValueError, "Unknown measurement"):
            fill_project(self.root / "framework", self.root / "failed",
                         content_json=self.write("bad_content.json", self.content))
        failed = json.loads((self.root / "failed/content_report.json").read_text())
        self.assertEqual(failed["status"], "failed")
        self.assertTrue((self.root / "failed/content_attempt_1.json").is_file())

    def test_api_success_records_usage_without_credentials(self):
        import io
        response = {"model": "example", "usage": {"total_tokens": 42},
                    "choices": [{"finish_reason": "stop", "message": {"content": '{"sections": []}'}}]}
        model = JsonModel({"client": {"api_base": "https://example.test/v1", "api_key": "private-value",
                                      "model_name": "example", "timeout": 1}, "request": {}})
        with patch("paper_content.model.urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as send:
            self.assertEqual(model.complete([]), {"sections": []})
        request = send.call_args.args[0]
        self.assertEqual(request.headers["Authorization"], "Bearer private-value")
        self.assertEqual(model.calls[0]["usage"]["total_tokens"], 42)
        self.assertNotIn("private-value", json.dumps(model.calls))

    def test_api_failure_does_not_echo_credentials(self):
        from urllib.error import HTTPError
        model = JsonModel({"client": {"api_base": "https://example.test/v1", "api_key": "private-value",
                                      "model_name": "example", "timeout": 1}, "request": {}})
        error = HTTPError("https://example.test", 401, "private-value", {}, None)
        with patch("paper_content.model.urlopen", side_effect=error):
            with self.assertRaisesRegex(ValueError, "HTTP 401") as raised:
                model.complete([])
        self.assertNotIn("private-value", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
