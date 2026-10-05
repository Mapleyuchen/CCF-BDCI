"""Deterministic, evidence-aware outline planning; no model calls required."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .citations import required_text
from .research import build_research_plan


def _objects(value: object, label: str) -> list[dict]:
    if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
        raise ValueError(f"{label} must be an array of objects")
    seen = set()
    normalized = []
    for item in value:
        item_id = required_text(item.get("id"), f"{label}.id")
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", item_id) or item_id in seen:
            raise ValueError(f"Invalid or duplicate {label} ID: {item_id}")
        seen.add(item_id)
        title = required_text(item.get("title"), f"{label}.title")
        normalized.append(dict(item, id=item_id, title=title))
    return normalized


def plan_outline(brief: object, citations: dict, base_dir: Path) -> dict:
    if not isinstance(brief, dict) or type(brief.get("schema_version")) is not int or brief["schema_version"] != 1:
        raise ValueError("Brief must be an object with schema_version: 1")
    title = required_text(brief.get("title"), "brief.title")
    question = required_text(brief.get("research_question"), "brief.research_question")
    methods = _objects(brief.get("methods", []), "methods")
    experiments = _objects(brief.get("experiments", []), "experiments")
    has_research_plan = any(key in brief for key in ("research_questions", "review_concerns")) or any(
        any(key in experiment for key in ("protocol", "purpose", "research_question_ids", "evidence_requirements", "limitations"))
        for experiment in experiments)
    authors = brief.get("authors", [])
    if not isinstance(authors, list):
        raise ValueError("authors must be an array of strings")
    authors = [required_text(a, "author") for a in authors]
    anonymous = brief.get("anonymous", True)
    if not isinstance(anonymous, bool) or (not anonymous and not authors):
        raise ValueError("anonymous must be boolean; non-anonymous drafts require authors")
    warnings = []
    if not citations["entries"]:
        warnings.append("No literature supplied; related work and citations need input.")
    sections = []

    def section(section_id, heading, goal):
        value = {"id": section_id, "title": heading, "file": f"sections/{section_id}.tex",
                 "goal": goal, "status": "needs_content", "citation_keys": [], "subsections": []}
        sections.append(value)
        return value

    section("abstract", "Abstract", "Summarize the question, method, supported results, and limitations after content is complete.")
    section("introduction", "Introduction", question)
    related = section("related_work", "Related Work", "Compare supplied sources; verify each claim against its cited source.")
    related["citation_keys"] = [e["cite_key"] for e in citations["entries"]]
    method_section = section("method", "Method", "Describe the implemented approach and distinguish it from proposed extensions.")
    for method in methods:
        refs = method.get("citation_ids", [])
        if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
            raise ValueError("methods.citation_ids must be an array of strings")
        unknown = [ref for ref in refs if ref not in citations["by_source_id"]]
        if unknown:
            raise ValueError(f"Unknown citation IDs in method {method['id']}: {unknown}")
        method_section["subsections"].append({
            "id": f"method_{method['id']}", "title": method["title"],
            "goal": required_text(method.get("description", method["title"]), "method.description"),
            "status": "needs_content", "citation_keys": sorted({citations["by_source_id"][ref] for ref in refs}),
        })
    if not methods:
        warnings.append("No method specification supplied; Method remains a placeholder.")
    setup = section("experiments", "Experimental Setup", "Specify datasets, baselines, budgets, metrics, scoring rules, and reproducibility.")
    results = section("results", "Results and Analysis", "Report only traceable measurements; include costs and negative outcomes.")
    evidence = []
    for experiment in experiments:
        status = experiment.get("status", "planned")
        if status not in ("planned", "completed"):
            raise ValueError("experiment.status must be planned or completed")
        metrics = experiment.get("metrics", [])
        if not isinstance(metrics, list):
            raise ValueError("experiment.metrics must be an array of strings")
        metrics = [required_text(m, "metric") for m in metrics]
        setup["subsections"].append({
            "id": f"setup_{experiment['id']}", "title": experiment["title"],
            "goal": "Describe the protocol and these metrics: " + (", ".join(metrics) or "not supplied"),
            "status": status, "citation_keys": [],
        })
        if status == "planned":
            if experiment.get("result_path"):
                raise ValueError(f"Planned experiment {experiment['id']} must not supply result_path; mark completed only after execution")
            warnings.append(f"Experiment {experiment['id']} is planned; no result subsection generated.")
            continue
        source = required_text(experiment.get("result_path"), "completed experiment.result_path")
        path = (base_dir / source).resolve()
        if not path.is_file():
            raise ValueError(f"Result file does not exist: {source}")
        evidence.append({"id": experiment["id"], "input_path": source, "resolved_path": str(path),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "validation": "file_exists_and_hashed_only"})
        results["subsections"].append({
            "id": f"result_{experiment['id']}", "title": experiment["title"],
            "goal": "Read the referenced result file; check validity before stating findings.",
            "status": "needs_evidence_review", "evidence_ids": [experiment["id"]], "citation_keys": [],
        })
    if not evidence:
        warnings.append("No completed experiment evidence supplied; result claims must remain empty.")
    section("discussion", "Discussion and Limitations", "Explain scope, confounders, missing evaluations, and resource tradeoffs.")
    section("conclusion", "Conclusion", "Answer the research question using only reviewed results.")
    outline = {"schema_version": 1, "planner": "deterministic_rules_v1", "title": title,
            "research_question": question, "anonymous": anonymous, "authors": authors,
            "sections": sections, "evidence": evidence, "warnings": warnings,
            "citation_policy": "Candidates only; presence does not establish support for any claim."}
    if has_research_plan:
        plan = build_research_plan(_objects(brief.get("research_questions", []), "research_questions"),
                                   _objects(brief.get("review_concerns", []), "review_concerns"), experiments)
        outline["research_plan"] = plan
        outline["planner"] = "deterministic_rules_v2"
        by_section = {item["id"]: item for item in sections}
        for item in plan["research_questions"]:
            by_section["introduction"]["subsections"].append({
                "id": "rq_" + item["id"], "title": item["title"], "goal": item["question"],
                "status": "needs_content", "citation_keys": [], "experiment_ids": item["experiment_ids"],
            })
            if not item["experiment_ids"]:
                warnings.append(f"Research question {item['id']} has no linked experiment.")
        for child, experiment in zip(setup["subsections"], plan["experiments"]):
            child.update(protocol=experiment["protocol"], research_question_ids=experiment["research_question_ids"],
                         evidence_requirements=experiment["evidence_requirements"], purpose=experiment["purpose"])
            child["goal"] += (". Protocol fields are declared metadata; verify them against actual execution. "
                              + ("This experiment has not run. Describe only a future protocol; no findings."
                                 if experiment["status"] == "planned" else "Evidence is supplied but needs scientific review."))
            if experiment["missing_protocol_fields"]:
                warnings.append(f"Experiment {experiment['id']} protocol needs: " + ", ".join(experiment["missing_protocol_fields"]))
        for concern in plan["review_concerns"]:
            warnings.append(f"Review concern {concern['id']}: {concern['status']}.")
        by_section["discussion"]["goal"] += " Address these unresolved review concerns: " + "; ".join(
            item["description"] for item in plan["review_concerns"])
    return outline
