"""Fill a new copy of a framework, preserving the original handoff and evidence."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import time

from paper_framework.citations import bibliography
from paper_framework.compiler import compile_project
from paper_framework.evidence import evidence_path
from paper_quality.checker import check_project
from .evidence import load_evidence, metric_catalog, read_json, sha256
from .figures import figure_tex, make_figures, table_tex
from .prose import build_messages, validate_content


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Framework file is outside its project: {relative}")
    return path


def fill_project(framework: Path, output: Path, *, model=None, content_json: Path | None = None,
                 related_work: Path | None = None, compile_pdf=False, methodology_image: Path | None = None,
                 resume_from: Path | None = None, illustration_manifest: Path | None = None,
                 writing_mode="fast") -> dict:
    started = time.monotonic()
    if writing_mode not in {"fast", "reviewed"} or (resume_from and writing_mode != "reviewed"):
        raise ValueError("Choose fast or reviewed writing; editorial resume requires reviewed mode")
    framework, output = framework.resolve(), output.resolve()
    if output.exists() or output.is_relative_to(framework):
        raise ValueError("Choose a new output directory outside the source framework; existing work is never overwritten")
    outline = read_json(framework / "outline.json")
    brief = read_json(framework / "brief.input.json")
    research = brief.get("writing_profile") == "research"
    if research and brief.get("method_specification", {}).get("implementation") != "jiuwenswarm_l1_v1":
        raise ValueError("Research assets require the audited jiuwenswarm_l1_v1 method specification")
    citations = read_json(framework / "citation_map.json")
    results = load_evidence(outline, framework)
    metrics = metric_catalog(results)
    illustrations = None
    if illustration_manifest:
        if methodology_image:
            raise ValueError("Choose an illustration manifest or a legacy methodology image")
        from paper_illustration.pipeline import load_bundle, build_context
        illustrations = load_bundle(illustration_manifest)
        identity = read_json(illustration_manifest.parent / "input.json")
        if identity["context"] != build_context(framework):
            raise ValueError("Illustrations do not match the current research brief and evidence")
    # Persist the exact displayed precision as well as full measurements for the quality checker.
    for item in metrics.values():
        item["display_value"] = float(item["text"].split()[0].rstrip("%")) if item["value"] is not None else None
    source_notes = brief.get("source_notes", {})
    if not isinstance(source_notes, dict):
        raise ValueError("brief.source_notes must map source IDs to reviewed source summaries")
    for key, value in source_notes.items():
        if key not in citations["by_source_id"] or not isinstance(value, str):
            raise ValueError(f"Source note must reference a known literature ID: {key}")
    override = read_json(related_work) if related_work else None
    if override is not None and (not isinstance(override, dict) or not isinstance(override.get("paragraphs"), list)):
        raise ValueError("Related Work handoff must be an object with a paragraphs array")
    if content_json is None and model is None:
        raise ValueError("A configured model or --content-json is required")
    files = ["paper.tex", "outline.json", "brief.input.json", "citation_map.json", "manifest.json",
             "iclr2027_conference.sty", "iclr2027_conference.bst", "natbib.sty", "fancyhdr.sty"]
    files += [section["file"] for section in outline["sections"]]
    files += [name for name in ("HANDOFF.md", "research_plan.json", "RESEARCH_HANDOFF.md")
              if (framework / name).is_file()]
    for relative in files:
        if not inside(framework, relative).is_file():
            raise ValueError(f"Missing framework file: {relative}")
        inside(output, relative)
    output.mkdir(parents=True)
    report = {"schema_version": 1, "status": "running", "human_review_required": True,
              "source_framework": str(framework), "source_outline_sha256": sha256(framework / "outline.json"),
              "calls": [], "validation_errors": [], "figures": [],
              "writing_mode": "offline" if content_json else writing_mode}
    try:
        for relative in files:
            target = inside(output, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(inside(framework, relative), target)
        (output / "evidence").mkdir()
        for entry in outline["evidence"]:
            target = output / "evidence" / (entry["id"] + ".json")
            source = evidence_path(entry, framework)
            shutil.copy2(source, target)
            if sha256(target) != entry["sha256"]:
                raise ValueError("Evidence changed during copy")
            entry.setdefault("original_path", str(source))
            entry["resolved_path"] = str(target)
            entry["input_path"] = "evidence/" + target.name
            entry["project_path"] = "evidence/" + target.name
            entry["validation"] = "live_records_recomputed; human_review_required"
        normalized = output / "evidence" / "normalized_results.json"
        write_json(normalized, {"schema_version": 1, "results": results, "metrics": metrics,
                                "display_policy": "Percentages to one decimal; average tokens and milliseconds to two decimals."})
        outline["evidence"].append({"id": "content_normalized", "input_path": "evidence/normalized_results.json",
                                    "project_path": "evidence/normalized_results.json",
                                    "resolved_path": str(normalized), "sha256": sha256(normalized),
                                    "validation": "derived_from_hashed_live_records"})
        write_json(output / "outline.json", outline)
        if illustrations:
            from paper_illustration.pipeline import copy_bundle
            copy_bundle(illustration_manifest, output / "illustrations")
            report["illustration_manifest_sha256"] = sha256(output / "illustrations/manifest.json")
        messages = build_messages(outline, brief, citations, metrics, results, source_notes, illustrations)
        write_json(output / "generation_request.json", messages)
        if content_json:
            content = read_json(content_json)
            report["content_input_sha256"] = sha256(content_json)
            report["content_input_path"] = str(content_json.resolve())
            prior_report = content_json.parent / "content_report.json"
            if prior_report.is_file():
                report["upstream_generation_report"] = {"path": str(prior_report.resolve()),
                                                        "sha256": sha256(prior_report)}
        elif research and writing_mode == "reviewed":
            from .editorial import draft_and_review
            content = draft_and_review(model, messages, output, resume_from)
        else:
            print("Writing manuscript in one pass (no model review)...", flush=True)
            original_request = dict(model.config["request"])
            model.config["request"].pop("thinking_budget", None)
            model.config["request"].pop("reasoning_effort", None)
            model.config["request"].update(enable_thinking=False, max_tokens=14000)
            try:
                content = model.complete(messages)
            finally:
                model.config["request"] = original_request
        allowed_names = [r["model_name"] for r in results]
        # A bounded repair call corrects schema/tokens, not measured data.
        for attempt in range(2):
            if override is not None and isinstance(content.get("sections"), list):
                for section in content["sections"]:
                    if isinstance(section, dict) and section.get("id") == "related_work":
                        section["paragraphs"] = deepcopy(override["paragraphs"])
            write_json(output / f"content_attempt_{attempt + 1}.json", content)
            try:
                rendered = validate_content(content, outline, metrics, citations, allowed_names, illustrations)
                break
            except ValueError as error:
                report["validation_errors"].append(str(error))
                if content_json or attempt == 1:
                    raise
                messages += [{"role": "assistant", "content": json.dumps(content)},
                             {"role": "user", "content": "Correct the complete JSON, keeping all evidence unchanged. Validation error: " + str(error)}]
                content = model.complete(messages)
        write_json(output / "content.json", content)
        for result in results:
            rendered["results"] += table_tex(result, metrics)
            if not research:
                rendered["results"] += figure_tex(result)
        if research:
            from .research_assets import attach_research_assets, FORMALIZATION
            method_tex, diagnostic_tex, files = attach_research_assets(results, output, methodology_image,
                                                                       include_methodology=not illustrations)
            rendered["method"] = rendered["method"].replace(r"\subsection", method_tex + r"\subsection", 1)
            rendered["method"] += "\n\\FloatBarrier\n" + FORMALIZATION + "\n\\FloatBarrier\n"
            rendered["results"] += diagnostic_tex + "\n\\FloatBarrier\n"
            report["figures"] = files
            if not illustrations:
                report["methodology_image_sha256"] = sha256(output / "figures/methodology.png")
            report["editorial_checks"] = {
                "prose_words": len(re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", " ".join(
                    p for s in content['sections'] for b in [s] + s['subsections'] for p in b['paragraphs']))),
                "reference_count": len(citations['entries']), "method_equations": 3,
                "question_level_appendix": True, "research_validity_requires_human_review": True,
            }
        else:
            report["figures"] = make_figures(results, output / "figures")
        if illustrations:
            from paper_framework.citations import latex_text
            seen_sections = set()
            (output / "figures").mkdir(exist_ok=True)
            for figure in illustrations["figures"]:
                name = figure["id"] + ".png"
                shutil.copy2(output / "illustrations" / figure["image"], output / "figures" / name)
                report["figures"].append(name)
                tex = ("\n\\begin{figure}[htbp]\n\\centering\n"
                       + r"\includegraphics[width=\linewidth,height=0.32\textheight,keepaspectratio]{figures/" + name + "}\n"
                       + r"\caption{" + latex_text(figure["caption"]) + "}\n"
                       + r"\label{fig:" + figure["id"] + "}\\end{figure}\n")
                section = figure["section"]
                if section not in seen_sections and r"\subsection" in rendered[section]:
                    rendered[section] = rendered[section].replace(r"\subsection", tex + r"\subsection", 1)
                elif section == "method" and r"\subsection{Budget and cost formalization}" in rendered[section]:
                    rendered[section] = rendered[section].replace(r"\subsection{Budget and cost formalization}",
                        tex + r"\subsection{Budget and cost formalization}", 1)
                else:
                    rendered[section] += tex
                seen_sections.add(section)
        for section in outline["sections"]:
            inside(output, section["file"]).write_text(rendered[section["id"]], encoding="utf-8")
            section["status"] = "generated_needs_human_review"
        write_json(output / "outline.json", outline)
        paper = (output / "paper.tex").read_text(encoding="utf-8")
        paper = paper.replace(r"\lhead{Research paper framework -- draft}", r"\lhead{Research manuscript}")
        paper = re.sub(r"\\paragraph\{Draft bibliography\.\}[^\n]*\n", "", paper)
        paper = paper.replace(r"\nocite{*}", "")
        if research:
            paper = paper.replace(r"\begin{document}", "\\usepackage{placeins}\n\\begin{document}")
            paper = paper.replace(r"\bibliography{references}",
                                  r"{\small\setlength{\bibsep}{3pt}\bibliography{references}}")
            paper = paper.replace(r"\end{document}", "\\input{appendix.tex}\n\\end{document}")
        # Avoid vertically stretched float-only pages while keeping ICLR margins/style.
        layout = ("\\hypersetup{hidelinks}\n\\raggedbottom\n"
                  "\\renewcommand{\\topfraction}{0.95}\n\\renewcommand{\\textfraction}{0.05}\n"
                  "\\renewcommand{\\floatpagefraction}{0.8}\n"
                  "\\makeatletter\n\\setlength{\\@fptop}{0pt}\n"
                  "\\setlength{\\@fpsep}{14pt}\n\\setlength{\\@fpbot}{0pt plus 1fil}\n\\makeatother\n")
        paper = paper.replace(r"\begin{document}", layout + r"\begin{document}")
        (output / "paper.tex").write_text(paper, encoding="utf-8")
        (output / "references.bib").write_text(bibliography(citations), encoding="utf-8")
        manifest = read_json(output / "manifest.json")
        manifest.update(artifact_kind="paper_content_draft", ready_for_submission=False,
                        human_review_required=True, content_generator=("reviewed_research_v2" if writing_mode == "reviewed" else "one_pass_research_v3") if research else "evidence_grounded_v1")
        write_json(output / "manifest.json", manifest)
        if compile_pdf:
            compile_project(output)
        quality = check_project(output)
        report["quality"] = quality["summary"]
        report["mechanical_checks_passed"] = quality["ready_for_submission"]
        report["status"] = "completed" if not compile_pdf or quality["ready_for_submission"] else "quality_failed"
        return report
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        if model is not None:
            report["calls"] = model.calls
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report["new_text_calls"] = sum(not c.get("reused_from_previous_run") for c in report["calls"])
        report["new_text_tokens"] = sum((c.get("usage") or {}).get("total_tokens") or 0 for c in report["calls"] if not c.get("reused_from_previous_run"))
        write_json(output / "content_report.json", report)
