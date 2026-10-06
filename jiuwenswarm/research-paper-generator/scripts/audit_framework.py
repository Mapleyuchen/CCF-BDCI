#!/usr/bin/env python3
"""Recompute framework evidence and export a writer handoff without model calls."""

import argparse
import json
from pathlib import Path

from paper_framework.evidence import evidence_path
from paper_framework.materials import verify_materials
from paper_content.evidence import load_evidence, metric_catalog, normalize_result, read_json, sha256
from paper_content.prose import build_messages


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def audit_project(project):
    project = project.resolve()
    outline = read_json(project / "outline.json")
    report = {"schema_version": 1, "kind": "framework_evidence_handoff_audit", "status": "running",
              "outline_sha256": sha256(project / "outline.json"), "scientific_review_required": True,
              "note": "Validates records and handoff consistency, not human adjudication or publication readiness.",
              "primary_results": [], "supplementary_results": [], "review_queues": []}
    try:
        verify_materials(outline, project)
        results = load_evidence(outline, project)
        brief = read_json(project / "brief.input.json")
        citations = read_json(project / "citation_map.json")
        declared = {e["id"]: e for e in outline.get("research_plan", {}).get("experiments", [])}
        for result in results:
            if result["kind"] == "controlled_memory_eval_live" and result["id"] in declared:
                protocol = declared[result["id"]]["protocol"]
                checks = {
                    "budget": protocol.get("budget", {}).get("values") == [result["context_tokens"]]
                              and protocol.get("budget", {}).get("unit") == "tokens",
                    "arms": set(protocol.get("baselines", [])) == set(result["group_labels"].values()),
                    "repeats": protocol.get("repeats") == result["repeats"],
                    "dataset": protocol.get("dataset", {}).get("version") == result["dataset_sha256"],
                    "sample_size": all(protocol.get("dataset", {}).get("sample_size") == g["memory_clusters"]
                                       for g in result["groups"].values()),
                }
                failed = [key for key, passed in checks.items() if not passed]
                if failed:
                    raise ValueError(f"Declared protocol differs from linked evidence for {result['id']}: {', '.join(failed)}")
            report["primary_results"].append({key: result[key] for key in (
                "id", "title", "kind", "group_labels", "context_tokens", "unique_questions", "paired_observations",
                "repeats", "accuracy_gain_pp", "accuracy_difference_ci_low_pp", "accuracy_difference_ci_high_pp", "paired_p_holm") if key in result})
        for item in outline.get("supporting_materials", []):
            path = evidence_path(item, project)
            if item["kind"] == "supplementary_evidence":
                result = normalize_result(path, item["id"], item["title"])
                report["supplementary_results"].append({"id": item["id"], "source_sha256": result["source_sha256"],
                                                         "status": "records_recomputed", "group_labels": result["group_labels"]})
            elif item["kind"] == "review_queue":
                rows = read_json(path)
                if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                    raise ValueError(f"Review queue must be an array of objects: {item['id']}")
                report["review_queues"].append({"id": item["id"], "items": len(rows),
                    "missing_decision": sum(not row.get("decision") for row in rows),
                    "note": "Queues may overlap. Filled decisions still require reviewer/provenance verification."})
        metrics = metric_catalog(results)
        write(project / "metric_catalog.json", metrics)
        write(project / "writing_request.json", build_messages(outline, brief, citations, metrics, results, brief.get("source_notes", {})))
        report.update(status="passed", material_count=len(outline.get("supporting_materials", [])), metric_count=len(metrics))
    except (OSError, ValueError, KeyError, TypeError) as error:
        report.update(status="failed", error=str(error))
        write(project / "framework_audit.json", report)
        raise ValueError(str(error)) from error
    write(project / "framework_audit.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    try:
        report = audit_project(args.project)
        print(f"Passed: {len(report['primary_results'])} primary comparisons, {len(report['supplementary_results'])} supplementary comparisons, {report['metric_count']} metric tokens. Human review remains required.")
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Framework audit failed: {error}\n")


if __name__ == "__main__":
    main()
