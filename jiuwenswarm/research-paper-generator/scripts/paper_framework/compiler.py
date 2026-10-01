"""Compile a generated draft with BibTeX and retain actionable diagnostics."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path


def compile_project(project: Path, timeout: int = 120) -> Path:
    project = project.resolve()
    if not (project / "paper.tex").is_file():
        raise ValueError(f"Missing paper.tex in {project}")
    latex = shutil.which("pdflatex")
    if not latex:
        raise ValueError("pdflatex is not installed or is not on PATH")
    bibtex = shutil.which("bibtex")
    report = {"success": False, "commands": [], "warnings": []}
    report_path = project / "compile_report.json"

    def run(command):
        try:
            result = subprocess.run(command, cwd=project, capture_output=True,
                                    text=True, encoding="utf-8", errors="replace", timeout=timeout)
        except (subprocess.TimeoutExpired, OSError) as error:
            report["commands"].append({"command": command, "error": str(error)})
            raise ValueError(f"Compilation could not finish; see {report_path}") from error
        report["commands"].append({"command": command, "returncode": result.returncode,
                                   "output_tail": (result.stdout + result.stderr)[-6000:]})
        if result.returncode:
            raise ValueError(f"Compilation failed ({Path(command[0]).name}); see {report_path}")

    try:
        command = [latex, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "paper.tex"]
        run(command)
        auxiliary = (project / "paper.aux").read_text(encoding="utf-8", errors="replace")
        if r"\bibdata{" in auxiliary:
            if not bibtex:
                raise ValueError("This draft needs bibtex, which is not on PATH")
            run([bibtex, "paper"])
        run(command)
        run(command)
        for extra_pass in range(3):
            log = (project / "paper.log").read_text(encoding="utf-8", errors="replace")
            report["warnings"] = [line for line in log.splitlines() if "Warning" in line or "Overfull" in line]
            needs_rerun = re.search(
                r"Label\(s\) may have changed|Rerun to get (?:cross-references|/PageLabels)|rerunfilecheck Warning: File", log)
            if not needs_rerun:
                break
            if extra_pass == 2:
                raise ValueError(f"Cross-references did not stabilize after five LaTeX passes; see {report_path}")
            run(command)
        if re.search(r"(?:Citation|Reference).*undefined|There were undefined (?:references|citations)", log):
            raise ValueError(f"Unresolved citations or references; see {report_path}")
        if not (project / "paper.pdf").is_file():
            raise ValueError("Compilation did not produce paper.pdf")
        report["success"] = True
        return project / "paper.pdf"
    except ValueError as error:
        report["error"] = str(error)
        raise
    finally:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
