"""Check completeness, ICLR format, and surface writing issues of a framework draft.

The report records what can be decided from the project files. It does not
judge whether an experiment result is scientifically valid.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from paper_framework.evidence import evidence_path

REQUIRED_SECTIONS = (
    "abstract",
    "introduction",
    "related_work",
    "method",
    "experiments",
    "results",
    "discussion",
    "conclusion",
)
SECTION_PLACEHOLDERS = (
    "Draft placeholder",
    "[To be written",
    "TBD",
    "to be done",
    "fill in",
    "[...]",
    "待写",
    "待补充",
)
DRAFT_BIBLIOGRAPHY = "Draft bibliography"
NOCITE = r"\nocite{*}"
DRAFT_BANNER = r"Research paper framework -- draft"
CJK = re.compile(r"[\u4e00-\u9fff]")
TOKEN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
REPEATED_WORD = re.compile(r"\b([A-Za-z]{3,})\s+\1\b", re.IGNORECASE)
STUB_WORDS = re.compile(r"\b(?:TODO|FIXME|TBD|TK|lorem ipsum|xxx+)\b", re.IGNORECASE)
LEAK_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\\thanks\b", re.IGNORECASE)
LEAK_GITHUB = re.compile(r"(?<![\w.])github\.com/[\w.-]+", re.IGNORECASE)
SMART_QUOTES = re.compile("[“”‘’]")
INCLUDE_GRAPHICS = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}")
PAGE_COUNT = re.compile(r"Output written on paper\.pdf \((\d+) page")
CITE_COMMAND = re.compile(r"\\cite[a-zA-Z]*\s*\{([^{}]+)\}")
BIB_ENTRY = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,(.*?)(?=\n@|\Z)", re.S)
CLAIM_NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:\\%|%)|(?<![\w.])(\d+\.\d+)(?!\w)")
PLANNED_CLAIM = re.compile(
    r"(?:improved|improvement|increase[sd]?|gain)\s+by\s+\d|(?:\+\s*)?\d+(?:\.\d+)?\s*(?:\\%|%)",
    re.IGNORECASE,
)
MIN_WORDS = 20
MAX_PDF_BYTES = 10 * 1024 * 1024
SOURCE_CLOCK_SKEW = 0.05


def check_project(project: Path) -> dict:
    """Write quality_report.json and return it. Findings do not raise."""
    project = project.resolve()
    paper = project / "paper.tex"
    if not project.is_dir() or not paper.is_file():
        raise ValueError(f"Not a paper project (missing paper.tex): {project}")
    checks: list[dict] = []
    outline = _load_json(project / "outline.json", checks, "outline.json")
    citation_map = _load_json(project / "citation_map.json", checks, "citation_map.json")
    paper_tex = paper.read_text(encoding="utf-8")
    section_text = _section_text(project, outline, checks)
    _check_completeness(project, paper_tex, outline, section_text, citation_map, checks)
    _check_format(project, paper_tex, outline, citation_map, checks)
    _check_typography(project, checks)
    _check_grammar(section_text, checks)
    report = {
        "schema_version": 1,
        "artifact_kind": "paper_quality_report",
        "ready_for_submission": not any(item["severity"] == "error" and not item["passed"] for item in checks),
        "summary": _summary(checks),
        "checks": checks,
    }
    (project / "quality_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _summary(checks: list[dict]) -> dict:
    failed = [item for item in checks if not item["passed"]]
    return {
        "passed": sum(item["passed"] for item in checks),
        "errors": sum(item["severity"] == "error" for item in failed),
        "warnings": sum(item["severity"] == "warning" for item in failed),
        "info": sum(item["severity"] == "info" for item in failed),
    }


def _add(checks, *, check_id, category, severity, passed, message, target=None):
    item = {"id": check_id, "category": category, "severity": severity, "passed": passed, "message": message}
    if target:
        item["target"] = target
    checks.append(item)


def _load_json(path: Path, checks: list[dict], label: str):
    if not path.is_file():
        _add(checks, check_id="completeness_manifest", category="completeness", severity="error",
             passed=False, message=f"Missing {label}. Generate the framework before review.", target=label)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        _add(checks, check_id="completeness_manifest", category="completeness", severity="error",
             passed=False, message=f"{label} is not valid JSON: {error}", target=label)
        return None


def _section_text(project: Path, outline, checks: list[dict]) -> dict[str, str]:
    found = {}
    expected = {section["id"]: section["file"] for section in (outline or {}).get("sections", [])
                if isinstance(section, dict) and "id" in section and "file" in section}
    for section_id in REQUIRED_SECTIONS:
        relative = expected.get(section_id, f"sections/{section_id}.tex")
        path = project / relative
        if path.is_file():
            found[section_id] = path.read_text(encoding="utf-8")
        else:
            _add(checks, check_id="completeness_section_missing", category="completeness", severity="error",
                 passed=False, message=f"Missing section file {relative}.", target=relative)
    if outline and isinstance(outline.get("sections"), list):
        ids = [section.get("id") for section in outline["sections"] if isinstance(section, dict)]
        _add(checks, check_id="completeness_section_order", category="completeness",
             severity="error", passed=ids == list(REQUIRED_SECTIONS),
             message="outline.json sections follow the eight-section ICLR order." if ids == list(REQUIRED_SECTIONS)
             else f"outline.json section order is {ids}; expected {list(REQUIRED_SECTIONS)}.")
    return found


def _check_completeness(project, paper_tex, outline, section_text, citation_map, checks):
    for section_id, text in section_text.items():
        hit = next((marker for marker in SECTION_PLACEHOLDERS if marker in text), None)
        target = f"sections/{section_id}.tex"
        if hit:
            _add(checks, check_id="completeness_placeholder", category="completeness", severity="error",
                 passed=False, message=f"Section still contains draft marker {hit!r}.", target=target)
        else:
            _add(checks, check_id="completeness_placeholder", category="completeness", severity="error",
                 passed=True, message="Section has no draft placeholder.", target=target)
    draft_bib = DRAFT_BIBLIOGRAPHY in paper_tex
    nocite = NOCITE in paper_tex
    _add(checks, check_id="completeness_draft_bibliography", category="completeness", severity="error",
         passed=not draft_bib and not nocite,
         message="Draft bibliography and \\nocite{*} are removed." if not draft_bib and not nocite
         else "Remove the draft bibliography paragraph and \\nocite{*} after real citations are inserted.",
         target="paper.tex")
    if not isinstance(outline, dict):
        return
    for record in outline.get("evidence") or []:
        if not isinstance(record, dict):
            continue
        evidence_id = str(record.get("id", "unknown"))
        recorded = record.get("project_path", record.get("resolved_path"))
        expected_hash = record.get("sha256")
        try:
            path = evidence_path(record, project)
        except (ValueError, OSError):
            path = None
        if path is None or not path.is_file():
            _add(checks, check_id="completeness_evidence_missing", category="completeness", severity="error",
                 passed=False, message=f"Result file for {evidence_id} is not at the recorded path.",
                 target=str(recorded))
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        matched = actual == expected_hash
        _add(checks, check_id="completeness_evidence_hash", category="completeness", severity="error",
             passed=matched, target=str(path),
             message="Result file matches the hash recorded at planning time." if matched
             else "Result file changed after planning. Regenerate the outline or review the new file before citing numbers.")
    _check_inputs(paper_tex, outline, checks)
    _check_subsections(outline, section_text, checks)
    _check_citations(project, outline, section_text, citation_map, checks)
    _check_result_claims(project, outline, section_text, checks)


def _check_inputs(paper_tex, outline, checks):
    if not isinstance(outline, dict):
        return
    active = _uncommented(paper_tex)
    missing = []
    for section in outline.get("sections") or []:
        if not isinstance(section, dict) or "file" not in section:
            continue
        command = "\\input{" + section["file"] + "}"
        if command not in active.replace(" ", ""):
            missing.append(section["file"])
    _add(checks, check_id="completeness_section_input", category="completeness", severity="error",
         passed=not missing, target="paper.tex",
         message="paper.tex inputs every outline section." if not missing
         else "paper.tex does not input: " + ", ".join(missing))


def _check_subsections(outline, section_text, checks):
    if not isinstance(outline, dict):
        return
    missing = []
    for section in outline.get("sections") or []:
        if not isinstance(section, dict):
            continue
        text = _uncommented(section_text.get(section.get("id"), ""))
        for child in section.get("subsections") or []:
            if not isinstance(child, dict) or "id" not in child:
                continue
            label = "\\label{sec:" + child["id"] + "}"
            title = child.get("title") or ""
            if label not in text and (not title or title not in text):
                missing.append(child["id"])
    _add(checks, check_id="completeness_subsection", category="completeness", severity="error",
         passed=not missing, target="sections",
         message="Every planned subsection still appears in its section file." if not missing
         else "Subsection labels or titles were removed: " + ", ".join(missing))


def _check_citations(project, outline, section_text, citation_map, checks):
    bib_path = project / "references.bib"
    bib_text = bib_path.read_text(encoding="utf-8") if bib_path.is_file() else ""
    bib_entries = _bibliography_entries(bib_text)
    cited = _citation_keys(section_text)
    unknown = sorted(key for key in cited if key not in bib_entries)
    _add(checks, check_id="completeness_citation_unknown", category="completeness", severity="error",
         passed=not unknown, target="references.bib",
         message="Every citation key exists in references.bib." if not unknown
         else "Citation keys missing from references.bib: " + ", ".join(unknown))
    incomplete = [key for key, fields in bib_entries.items() if not {"author", "title", "year"} <= fields]
    _add(checks, check_id="completeness_bib_fields", category="completeness", severity="error",
         passed=not incomplete, target="references.bib",
         message="Bibliography entries include author, title, and year." if not incomplete
         else "Bibliography entries missing author, title, or year: " + ", ".join(incomplete))
    entries = (citation_map or {}).get("entries") if isinstance(citation_map, dict) else None
    cited_somewhere = bool(cited)
    if entries and not cited_somewhere:
        _add(checks, check_id="completeness_citation_used", category="completeness", severity="error",
             passed=False, message="Literature was supplied, but no section contains a \\\\cite command.",
             target="sections")
    elif entries:
        _add(checks, check_id="completeness_citation_used", category="completeness", severity="error",
             passed=True, message="At least one supplied source is cited in the section files.")
    required = _required_citation_keys(outline)
    if not required:
        _add(checks, check_id="completeness_assigned_citation", category="completeness", severity="error",
             passed=True, message="The brief did not assign a citation key to a method section.")
    else:
        absent = sorted({key for key, target in required
                         if key not in _citation_keys({target: section_text.get(target, "")})})
        _add(checks, check_id="completeness_assigned_citation", category="completeness", severity="error",
             passed=not absent, target="sections",
             message="Method citation keys requested by the brief appear in that section." if not absent
             else "Assigned citation keys are not used in their section: " + ", ".join(absent))
    weak = [key for key, fields in bib_entries.items() if "doi" not in fields and "eprint" not in fields]
    if weak:
        _add(checks, check_id="completeness_citation_identity", category="completeness", severity="warning",
             passed=False, target="references.bib",
             message="Bibliography entries have neither a DOI nor an arXiv id: " + ", ".join(weak))


def _check_result_claims(project, outline, section_text, checks):
    if not isinstance(outline, dict):
        return
    results = _uncommented(section_text.get("results", ""))
    evidence = [record for record in outline.get("evidence") or [] if isinstance(record, dict)]
    planned = [child for section in outline.get("sections") or [] if isinstance(section, dict)
               for child in section.get("subsections") or []
               if isinstance(child, dict) and child.get("status") == "planned"]
    if planned and not evidence and PLANNED_CLAIM.search(results):
        _add(checks, check_id="completeness_planned_result", category="completeness", severity="error",
             passed=False, target="sections/results.tex",
             message="Results state a measured gain, but every experiment is still planned.")
        return
    if not evidence or any(marker in section_text.get("results", "") for marker in SECTION_PLACEHOLDERS):
        return
    allowed = set()
    for record in evidence:
        try:
            path = evidence_path(record, project)
        except (ValueError, OSError):
            continue
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == record.get("sha256"):
            allowed.update(_numbers_in_file(path))
    claims = _claim_numbers(results)
    if not claims:
        _add(checks, check_id="completeness_result_numbers", category="completeness", severity="warning",
             passed=False, target="sections/results.tex",
             message="A completed result file exists, but the results section states no decimal or percentage.")
        return
    unsupported = [claim for claim in claims if not _number_supported(claim, allowed)]
    _add(checks, check_id="completeness_result_numbers", category="completeness", severity="error",
         passed=not unsupported, target="sections/results.tex",
         message="Measured numbers in Results match the completed result files." if not unsupported
         else "Results mention numbers that are not in the completed result files: " + ", ".join(unsupported))


def _required_citation_keys(outline):
    if not isinstance(outline, dict):
        return []
    required = []
    for section in outline.get("sections") or []:
        if not isinstance(section, dict):
            continue
        # Related Work lists every supplied source as a candidate, not as a required citation.
        if section.get("id") != "related_work":
            for key in section.get("citation_keys") or []:
                required.append((key, section["id"]))
        for child in section.get("subsections") or []:
            if isinstance(child, dict):
                for key in child.get("citation_keys") or []:
                    required.append((key, section["id"]))
    return required


def _citation_keys(section_text: dict[str, str]) -> set[str]:
    keys = set()
    for text in section_text.values():
        for group in CITE_COMMAND.findall(_uncommented(text)):
            keys.update(part.strip() for part in group.split(",") if part.strip())
    return keys


def _bibliography_entries(bib_text: str) -> dict[str, set[str]]:
    entries = {}
    for match in BIB_ENTRY.finditer(bib_text):
        fields = {name.lower() for name in re.findall(r"(?m)^\s*(\w+)\s*=", match.group(2))}
        entries[match.group(1)] = fields
    return entries


def _claim_numbers(text: str) -> list[str]:
    found = []
    for percent, decimal in CLAIM_NUMBER.findall(text):
        found.append(percent or decimal)
    return found


def _numbers_in_file(path: Path) -> set[float]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    values = set()
    try:
        _collect_numbers(json.loads(raw), values)
    except json.JSONDecodeError:
        values.update(float(match) for match in re.findall(r"\d+(?:\.\d+)?", raw))
    return values


def _collect_numbers(value, found: set[float]):
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        found.add(float(value))
    elif isinstance(value, dict):
        for item in value.values():
            _collect_numbers(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect_numbers(item, found)


def _number_supported(claim: str, values: set[float]) -> bool:
    number = float(claim)
    return any(abs(number - value) < 1e-6 or abs(number - value * 100) < 0.2 for value in values)


def _check_format(project, paper_tex, outline, citation_map, checks):
    active = _uncommented(paper_tex)
    uses_style = bool(re.search(r"\\usepackage(?:\[[^\]]*\])?\{[^}]*iclr2027_conference", active))
    _add(checks, check_id="format_iclr_style", category="format", severity="error", passed=uses_style,
         message="paper.tex loads iclr2027_conference." if uses_style else "paper.tex does not load iclr2027_conference.",
         target="paper.tex")
    for name in ("iclr2027_conference.sty", "iclr2027_conference.bst", "natbib.sty"):
        exists = (project / name).is_file()
        _add(checks, check_id="format_style_file", category="format", severity="error", passed=exists,
             message=f"{name} is present." if exists else f"Missing style file {name}.", target=name)
    anonymous = bool(outline.get("anonymous")) if isinstance(outline, dict) else True
    final_copy = bool(re.search(r"\\iclrfinalcopy\b", active))
    if anonymous:
        author_ok = bool(re.search(r"\\author\{[^}]*Anonymous", active))
        _add(checks, check_id="format_anonymous", category="format", severity="error",
             passed=author_ok and not final_copy, target="paper.tex",
             message="Anonymous submission keeps Anonymous authors and leaves \\iclrfinalcopy unset."
             if author_ok and not final_copy else
             "Anonymous brief still shows a camera-ready author block or \\iclrfinalcopy.")
    else:
        _add(checks, check_id="format_anonymous", category="format", severity="warning",
             passed=final_copy, target="paper.tex",
             message="Non-anonymous draft enables \\iclrfinalcopy." if final_copy
             else "Brief is not anonymous, but \\iclrfinalcopy is not enabled.")
    if anonymous:
        _check_anonymity_leaks(project, checks)
    banner = DRAFT_BANNER in active
    _add(checks, check_id="format_draft_banner", category="format", severity="error", passed=not banner,
         message="Draft running header is removed." if not banner
         else "Remove the draft running header before submission.", target="paper.tex")
    _check_bibliography_order(active, citation_map, checks)
    _check_compile(project, checks)
    _check_figures(project, checks)


def _check_bibliography_order(active, citation_map, checks):
    entries = (citation_map or {}).get("entries") if isinstance(citation_map, dict) else None
    style_at = active.find(r"\bibliographystyle{")
    bib_at = active.find(r"\bibliography{")
    if not entries:
        _add(checks, check_id="format_bibliography_order", category="format", severity="error", passed=True,
             message="No literature entries were supplied, so bibliography order is not required.")
        return
    ordered = style_at != -1 and bib_at != -1 and style_at < bib_at
    _add(checks, check_id="format_bibliography_order", category="format", severity="error", passed=ordered,
         message="\\bibliographystyle appears before \\bibliography." if ordered
         else "Literature was supplied, but bibliography commands are missing or in the wrong order.",
         target="paper.tex")


def _check_compile(project: Path, checks: list[dict]):
    report_path = project / "compile_report.json"
    if not report_path.is_file():
        _add(checks, check_id="format_compile", category="format", severity="error", passed=False,
             message="No compile_report.json. Run compile_framework.py before submission.", target="compile_report.json")
        return
    try:
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        _add(checks, check_id="format_compile", category="format", severity="error", passed=False,
             message=f"compile_report.json is not valid JSON: {error}", target="compile_report.json")
        return
    success = bool(report.get("success")) and (project / "paper.pdf").is_file()
    warning_text = " ".join(report.get("warnings") or [])
    unresolved = "undefined" in warning_text.lower()
    compiled = success and not unresolved
    _add(checks, check_id="format_compile", category="format", severity="error", passed=compiled,
         message="Compilation succeeded without undefined citations." if compiled
         else "Compilation failed, paper.pdf is missing, or citations are undefined.",
         target="compile_report.json")
    stale = _newer_source(project, report_path) if compiled else None
    if compiled:
        _add(checks, check_id="format_compile_stale", category="format", severity="error",
             passed=stale is None, target=str(stale.relative_to(project)) if stale else "compile_report.json",
             message="Compilation is newer than paper.tex, section files, and references.bib." if stale is None
             else f"{stale.name} changed after the last successful compilation. Compile again before review.")
    pdf = project / "paper.pdf"
    if pdf.is_file():
        size_ok = pdf.stat().st_size <= MAX_PDF_BYTES
        _add(checks, check_id="format_pdf_size", category="format", severity="error", passed=size_ok,
             message="paper.pdf is within 10MB." if size_ok else "paper.pdf exceeds 10MB.", target="paper.pdf")
    log = project / "paper.log"
    if not log.is_file():
        _add(checks, check_id="format_page_count", category="format", severity="info", passed=True,
             message="Page count was not checked. Contest rules do not limit paper length.", target="paper.log")
        return
    match = PAGE_COUNT.search(log.read_text(encoding="utf-8", errors="replace"))
    pages = match.group(1) if match else "unknown"
    _add(checks, check_id="format_page_count", category="format", severity="info", passed=True,
         message=f"pdflatex reports {pages} pages, including the bibliography. Contest rules do not limit length.",
         target="paper.log")


def _newer_source(project: Path, report_path: Path):
    outputs = [report_path]
    pdf = project / "paper.pdf"
    if pdf.is_file():
        outputs.append(pdf)
    output_time = min(path.stat().st_mtime for path in outputs)
    newest = None
    for path in [project / "paper.tex", project / "references.bib", *sorted((project / "sections").glob("*.tex"))]:
        if not path.is_file():
            continue
        if path.stat().st_mtime > output_time + SOURCE_CLOCK_SKEW and (newest is None or path.stat().st_mtime > newest.stat().st_mtime):
            newest = path
    return newest


def _check_figures(project: Path, checks: list[dict]):
    targets = []
    for path in [project / "paper.tex", *sorted((project / "sections").glob("*.tex"))]:
        if not path.is_file():
            continue
        targets.extend(INCLUDE_GRAPHICS.findall(_uncommented(path.read_text(encoding="utf-8"))))
    if not targets:
        _add(checks, check_id="format_figures", category="format", severity="warning", passed=False,
             message="No \\includegraphics found. Add the method or result figures before final submission.")
        return
    missing = [item for item in targets if not (project / item).is_file()]
    _add(checks, check_id="format_figures", category="format", severity="error", passed=not missing,
         message="Every \\includegraphics target exists." if not missing
         else "Missing figure files: " + ", ".join(missing), target="sections")
    unlabeled = []
    for path in [project / "paper.tex", *sorted((project / "sections").glob("*.tex"))]:
        if not path.is_file():
            continue
        active = _uncommented(path.read_text(encoding="utf-8"))
        if INCLUDE_GRAPHICS.search(active) and (r"\caption" not in active or r"\label" not in active):
            unlabeled.append(str(path.relative_to(project)))
    _add(checks, check_id="format_figure_caption", category="format", severity="error",
         passed=not unlabeled, target="sections",
         message="Every figure has a caption and a label." if not unlabeled
         else "Figures are missing a caption or label in: " + ", ".join(unlabeled))


def _check_anonymity_leaks(project: Path, checks: list[dict]):
    leaks = []
    tex_files = [project / "paper.tex", *sorted((project / "sections").glob("*.tex"))]
    bib = project / "references.bib"
    for path in tex_files + ([bib] if bib.is_file() else []):
        if not path.is_file():
            continue
        active = _uncommented(path.read_text(encoding="utf-8", errors="replace"))
        github = path.suffix == ".tex" and LEAK_GITHUB.search(active)
        if LEAK_EMAIL.search(active) or github:
            leaks.append(str(path.relative_to(project)))
    _add(checks, check_id="format_anonymity_leak", category="format", severity="error",
         passed=not leaks, target="paper.tex",
         message="Anonymous draft has no email, GitHub profile, or \\thanks." if not leaks
         else "Anonymous draft contains an identity leak in: " + ", ".join(leaks))


def _check_typography(project: Path, checks: list[dict]):
    problems = []
    for path in [project / "paper.tex", project / "references.bib", *sorted((project / "sections").glob("*.tex"))]:
        if not path.is_file():
            continue
        active = _uncommented(path.read_text(encoding="utf-8", errors="replace"))
        relative = str(path.relative_to(project))
        if CJK.search(active) or SMART_QUOTES.search(active):
            problems.append(relative + " has Chinese or smart quotes")
        if active.replace(r"\$", "").count("$") % 2:
            problems.append(relative + " has an unmatched $")
    _add(checks, check_id="format_typography", category="format", severity="error",
         passed=not problems, target="paper.tex",
         message="Paper sources have no CJK text, smart quotes, or unmatched math delimiters." if not problems
         else "; ".join(problems))


def _check_grammar(section_text: dict[str, str], checks: list[dict]):
    for section_id, text in section_text.items():
        target = f"sections/{section_id}.tex"
        if any(marker in text for marker in SECTION_PLACEHOLDERS):
            continue
        source = _uncommented(text)
        visible = _visible_prose(source)
        if CJK.search(source):
            _add(checks, check_id="grammar_cjk", category="grammar", severity="error", passed=False,
                 message="Section contains Chinese characters. The pdfLaTeX draft has no CJK fonts.", target=target)
        else:
            _add(checks, check_id="grammar_cjk", category="grammar", severity="error", passed=True,
                 message="Section has no CJK characters.", target=target)
        stub = STUB_WORDS.search(visible)
        _add(checks, check_id="grammar_stub", category="grammar", severity="error", passed=stub is None,
             message="No TODO, FIXME, lorem ipsum, or XXX marker." if stub is None
             else f"Remove writing stub {stub.group(0)!r}.", target=target)
        words = TOKEN.findall(visible)
        long_enough = len(words) >= MIN_WORDS
        _add(checks, check_id="grammar_length", category="grammar", severity="warning", passed=long_enough,
             message=f"Section has {len(words)} words." if long_enough
             else f"Section has only {len(words)} words, below {MIN_WORDS}.", target=target)
        repeat = REPEATED_WORD.search(visible)
        _add(checks, check_id="grammar_repeated_word", category="grammar", severity="warning", passed=repeat is None,
             message="No immediate repeated word." if repeat is None
             else f"Repeated word {repeat.group(1)!r}.", target=target)
        balanced = source.count("{") == source.count("}")
        _add(checks, check_id="grammar_braces", category="grammar", severity="error", passed=balanced,
             message="Braces are balanced." if balanced else "Unbalanced braces.", target=target)


def _uncommented(tex: str) -> str:
    kept = []
    for line in tex.splitlines():
        if line.lstrip().startswith("%"):
            continue
        kept.append(line.split("%", 1)[0])
    return "\n".join(kept)


def _visible_prose(tex: str) -> str:
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", " ", tex)
    return text.replace("{", " ").replace("}", " ")
