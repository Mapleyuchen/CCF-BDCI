"""Check a contest submission directory. This does not zip the bundle or call a reviewer."""

from __future__ import annotations

import json
import re
from pathlib import Path

REQUIRED_FILES = (
    "paper/paper.pdf",
    "AgenticReviewer/PaperReview-AccessToken.txt",
    "docs/architecture.md",
    "docs/module_call.md",
    "docs/innovation.md",
    "framework_contribution.md",
    "resource_report.md",
    "提交说明.md",
)
TOKEN_STUBS = ("todo", "xxx", "placeholder", "changeme", "your token", "your_token", "access token")
SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?:api[_-]?key|secret|password|access[_-]?token)\s*[:=]\s*['\"]?([A-Za-z0-9_./+\-]{16,})"
)
SECRET_KEY = re.compile(r"\bsk-[A-Za-z0-9]{16,}\b")
SECRET_FILENAMES = {"config.yaml", ".env", "credentials.json", "id_rsa", "id_ed25519"}
PLACEHOLDER_SECRET = ("example", "your", "changeme", "placeholder", "todo", "xxx", "<", "none", "null")


def check_submission(bundle: Path) -> dict:
    """Write submission_report.json beside the bundle and return it."""
    bundle = bundle.resolve()
    if not bundle.is_dir():
        raise ValueError(f"Submission directory does not exist: {bundle}")
    checks: list[dict] = []
    _check_required(bundle, checks)
    _check_token(bundle, checks)
    _check_contribution(bundle, checks)
    _check_resources(bundle, checks)
    _check_pdf(bundle, checks)
    _check_secrets(bundle, checks)
    report = {
        "schema_version": 1,
        "artifact_kind": "submission_quality_report",
        "ready_for_submission": not any(item["severity"] == "error" and not item["passed"] for item in checks),
        "summary": {
            "passed": sum(item["passed"] for item in checks),
            "errors": sum(item["severity"] == "error" and not item["passed"] for item in checks),
            "warnings": sum(item["severity"] == "warning" and not item["passed"] for item in checks),
        },
        "checks": checks,
    }
    destination = bundle.parent / "submission_report.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _add(checks, *, check_id, severity, passed, message, target=None):
    item = {"id": check_id, "category": "submission", "severity": severity, "passed": passed, "message": message}
    if target:
        item["target"] = target
    checks.append(item)


def _check_required(bundle: Path, checks: list[dict]):
    missing = [relative for relative in REQUIRED_FILES if not (bundle / relative).is_file()]
    if not (bundle / "code").is_dir():
        missing.append("code/")
    _add(checks, check_id="submission_files", severity="error", passed=not missing,
         message="Required contest files are present." if not missing
         else "Missing submission files: " + ", ".join(missing))


def _check_token(bundle: Path, checks: list[dict]):
    path = bundle / "AgenticReviewer/PaperReview-AccessToken.txt"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    stub = len(text) < 8 or any(marker in text.lower() for marker in TOKEN_STUBS)
    _add(checks, check_id="submission_token", severity="error", passed=not stub, target=str(path.name),
         message="Access token file is non-empty and not a placeholder." if not stub
         else "PaperReview-AccessToken.txt is empty or still a placeholder. It must match paper/paper.pdf.")


def _check_contribution(bundle: Path, checks: list[dict]):
    path = bundle / "framework_contribution.md"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    linked = "http://" in text or "https://" in text
    _add(checks, check_id="submission_contribution", severity="error", passed=linked,
         message="framework_contribution.md contains a PR or patch link." if linked
         else "framework_contribution.md needs an http(s) link to the PR or patch.")


def _check_resources(bundle: Path, checks: list[dict]):
    path = bundle / "resource_report.md"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    traced = bool(re.search(r"token|时长|运行|latency|hour", text, re.IGNORECASE))
    _add(checks, check_id="submission_resources", severity="error", passed=traced,
         message="resource_report.md records token use or runtime." if traced
         else "resource_report.md should record token consumption and runtime.")


def _check_pdf(bundle: Path, checks: list[dict]):
    path = bundle / "paper/paper.pdf"
    if not path.is_file():
        return
    header = path.read_bytes()[:5]
    _add(checks, check_id="submission_pdf", severity="error", passed=header == b"%PDF-",
         message="paper/paper.pdf has a PDF header." if header == b"%PDF-"
         else "paper/paper.pdf is not a PDF file.")


def _check_secrets(bundle: Path, checks: list[dict]):
    found = []
    for path in bundle.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = str(path.relative_to(bundle)).replace("\\", "/")
        if path.name in SECRET_FILENAMES:
            found.append(relative)
            continue
        if path.suffix.lower() not in {".py", ".yaml", ".yml", ".json", ".env", ".md", ".txt", ".toml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SECRET_KEY.search(text):
            found.append(relative)
            continue
        for match in SECRET_ASSIGNMENT.finditer(text):
            value = match.group(1).lower()
            if not any(marker in value for marker in PLACEHOLDER_SECRET):
                found.append(relative)
                break
    _add(checks, check_id="submission_secrets", severity="error", passed=not found,
         message="No config secrets or credential files were found." if not found
         else "Remove secrets before packing: " + ", ".join(sorted(set(found))))
