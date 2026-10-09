"""Contest bundle checks stay separate from the paper-project checker."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / "scripts"))

from paper_quality.submission import check_submission


class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bundle = Path(self.temp.name) / "team"
        self._write_complete()

    def _write_complete(self):
        files = {
            "paper/paper.pdf": b"%PDF-1.4\n",
            "AgenticReviewer/PaperReview-AccessToken.txt": b"review-token-123456\n",
            "docs/architecture.md": b"architecture\n",
            "docs/module_call.md": b"modules\n",
            "docs/innovation.md": b"innovation\n",
            "framework_contribution.md": b"PR: https://github.com/openJiuwen/jiuwenswarm/pull/1\n",
            "resource_report.md": b"tokens: 1000\nruntime: 2 hours\n",
            "提交说明.md": b"layout\n",
            "code/README.md": b"agent\n",
        }
        for relative, content in files.items():
            path = self.bundle / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    def test_complete_bundle_passes(self):
        report = check_submission(self.bundle)
        self.assertTrue(report["ready_for_submission"], [item for item in report["checks"] if not item["passed"]])
        self.assertTrue((self.bundle.parent / "submission_report.json").is_file())

    def test_placeholder_token_and_missing_link_fail(self):
        (self.bundle / "AgenticReviewer/PaperReview-AccessToken.txt").write_text("TODO\n", encoding="utf-8")
        (self.bundle / "framework_contribution.md").write_text("No link yet.\n", encoding="utf-8")
        report = check_submission(self.bundle)
        failed = {item["id"] for item in report["checks"] if not item["passed"]}
        self.assertIn("submission_token", failed)
        self.assertIn("submission_contribution", failed)

    def test_real_secret_fails_and_example_value_does_not(self):
        settings = self.bundle / "code/settings.py"
        settings.write_text('API_KEY = "your-api-key-here-example"\n', encoding="utf-8")
        report = check_submission(self.bundle)
        self.assertTrue(report["ready_for_submission"], [item for item in report["checks"] if not item["passed"]])
        settings.write_text('API_KEY = "sk-livekeyvalue1234567890"\n', encoding="utf-8")
        report = check_submission(self.bundle)
        self.assertTrue(any(item["id"] == "submission_secrets" and not item["passed"] for item in report["checks"]))
        settings.write_text('API_KEY = "your-api-key-here-example"\n', encoding="utf-8")
        (self.bundle / "code/config.yaml").write_text("model: example\n", encoding="utf-8")
        report = check_submission(self.bundle)
        self.assertTrue(any(item["id"] == "submission_secrets" and not item["passed"] for item in report["checks"]))

    def test_cli_rejects_a_missing_bundle(self):
        script = MODULE / "scripts/check_submission.py"
        result = subprocess.run([sys.executable, str(script), str(self.bundle / "missing")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not exist", result.stderr)


if __name__ == "__main__":
    unittest.main()
