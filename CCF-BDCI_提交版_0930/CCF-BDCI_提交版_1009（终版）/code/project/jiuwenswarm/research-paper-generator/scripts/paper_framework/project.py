"""Render an isolated, portable LaTeX draft and its handoff manifests."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

from .citations import bibliography, build_citations, latex_text
from .planner import plan_outline
from .research import handoff_markdown
from .materials import copy_materials, materials_markdown

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_TEMPLATE = ROOT / "iclr-2027-style-files" / "iclr2027"
STYLE_FILES = ("iclr2027_conference.sty", "iclr2027_conference.bst", "fancyhdr.sty", "natbib.sty")
MAIN_TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "paper.tex.template"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value: object):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _section_tex(section: dict) -> str:
    abstract = section["id"] == "abstract"
    lines = ["% Draft placeholder. Replace with reviewed content; see outline.json."]
    if not abstract:
        lines += [f"\\section{{{latex_text(section['title'])}}}", f"\\label{{sec:{section['id']}}}"]
    lines.append(r"\textit{[To be written. See the section plan in outline.json.]}")
    if section["citation_keys"]:
        lines.append("% Candidate citation keys (not verified claim support): " + ", ".join(section["citation_keys"]))
    for child in section["subsections"]:
        lines += [f"\\subsection{{{latex_text(child['title'])}}}", f"\\label{{sec:{child['id']}}}",
                  r"\textit{[To be written after reviewing the specified inputs.]}"]
        if child["citation_keys"]:
            lines.append("% Candidate citation keys: " + ", ".join(child["citation_keys"]))
    return "\n".join(lines) + "\n"


def generate_project(brief_path: Path, output: Path, literature_path: Path | None = None,
                     template_dir: Path = DEFAULT_TEMPLATE) -> dict:
    """Validate all inputs before writing; never replace an existing directory."""
    brief_path, output, template_dir = brief_path.resolve(), output.resolve(), template_dir.resolve()
    if output.exists():
        raise ValueError(f"Output already exists; choose a new directory to preserve edits: {output}")
    brief = load_json(brief_path)
    citations = build_citations(load_json(literature_path) if literature_path else [])
    outline = plan_outline(brief, citations, brief_path.parent)
    for name in STYLE_FILES:
        if not (template_dir / name).is_file():
            raise ValueError(f"Missing template dependency: {template_dir / name}")
    tex = MAIN_TEMPLATE.read_text(encoding="utf-8")
    sections = "\n".join(f"\\input{{{s['file']}}}" for s in outline["sections"] if s["id"] != "abstract")
    bib = (r"\paragraph{Draft bibliography.} Candidate sources supplied for planning; claim-level citations remain to be reviewed."
           "\n% Remove nocite when real claim-level citations have been inserted.\n"
           "\\nocite{*}\n\\bibliographystyle{iclr2027_conference}\n\\bibliography{references}") if citations["entries"] else "% No literature supplied. Add bibliography after citation handoff."
    replacements = {
        "TITLE": latex_text(outline["title"]),
        "AUTHORS": "Anonymous Authors" if outline["anonymous"] else " \\And ".join(latex_text(a) for a in outline["authors"]),
        # This remains a draft, not a claim of acceptance at ICLR.
        "AUTHOR_MODE": "" if outline["anonymous"] else r"\iclrfinalcopy",
        "SECTIONS": sections, "BIBLIOGRAPHY": bib,
    }
    tex = re.sub(r"@@([A-Z_]+)@@", lambda match: replacements[match[1]], tex)
    source_paths = {"brief": brief_path}
    if literature_path:
        source_paths["literature"] = literature_path.resolve()
    manifest = {
        "schema_version": 1, "artifact_kind": "paper_framework_draft", "ready_for_submission": False,
        "evidence_path_policy": "project_relative_snapshot_v1",
        "inputs": {key: {"filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                   for key, path in source_paths.items()},
        "style_sha256": {name: hashlib.sha256((template_dir / name).read_bytes()).hexdigest() for name in STYLE_FILES},
        "warnings": outline["warnings"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # Temporary staging is in the output's parent, so rename stays on one volume.
    with tempfile.TemporaryDirectory(prefix=".framework-", dir=output.parent) as temporary:
        staged = Path(temporary) / "project"
        (staged / "sections").mkdir(parents=True)
        copy_materials(outline, staged, output)
        for entry in outline["evidence"]:
            source = Path(entry["resolved_path"])
            relative = f"evidence/raw/{entry['id']}.json"
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if hashlib.sha256(target.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError(f"Evidence changed during snapshot: {entry['id']}")
            entry.update(original_path=str(source), project_path=relative,
                         resolved_path=str(output / relative))
        for section in outline["sections"]:
            (staged / section["file"]).write_text(_section_tex(section), encoding="utf-8")
        (staged / "paper.tex").write_text(tex, encoding="utf-8")
        (staged / "references.bib").write_text(bibliography(citations), encoding="utf-8")
        _write_json(staged / "outline.json", outline)
        if outline.get("supporting_materials"):
            (staged / "MATERIALS.md").write_text(materials_markdown(outline), encoding="utf-8")
            manifest["supporting_materials"] = {"index": "MATERIALS.md", "count": len(outline["supporting_materials"])}
        if "research_plan" in outline:
            _write_json(staged / "research_plan.json", outline["research_plan"])
            (staged / "RESEARCH_HANDOFF.md").write_text(handoff_markdown(outline["research_plan"]), encoding="utf-8")
            manifest["research_plan"] = {"path": "research_plan.json", "scientific_review_required": True}
        _write_json(staged / "citation_map.json", citations)
        _write_json(staged / "manifest.json", manifest)
        _write_json(staged / "brief.input.json", brief)
        for name in STYLE_FILES:
            shutil.copyfile(template_dir / name, staged / name)
        (staged / "HANDOFF.md").write_text(
            "# Paper framework draft\n\n"
            "Fill sections/*.tex using outline.json. Do not edit measured results into the planner.\n"
            "Result hashes record provenance, not scientific validity. Read project_path relative to this project.\n"
            "Evidence snapshots travel with the framework. original_path and input_path are source provenance only.\n"
            "If present, read research_plan.json and RESEARCH_HANDOFF.md for planned protocols and unresolved review concerns.\n"
            "If present, MATERIALS.md maps reviewed experiment assets and pending human-review queues to sections.\n"
            "Use citation_map.json to select citation keys; verify each source and claim before citing it.\n"
            "Remove draft placeholders, the Draft bibliography paragraph, and \\nocite{*} before final review.\n"
            "Keep paper.tex and sections/*.tex changes: regeneration requires a new output directory.\n"
            "The skeleton uses the repository's ICLR style; check current submission requirements separately.\n",
            encoding="utf-8",
        )
        staged.rename(output)
    return manifest
