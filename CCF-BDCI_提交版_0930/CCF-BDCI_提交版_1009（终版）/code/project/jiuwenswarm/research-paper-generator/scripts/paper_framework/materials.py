"""Portable supporting assets, kept separate from machine-readable result evidence."""

import hashlib
from pathlib import Path
import shutil

from .citations import required_text
from .evidence import evidence_path
from .research import texts


KINDS = {"figure", "table", "prose", "statistics", "review_queue", "documentation", "supplementary_evidence"}


def plan_materials(items, base_dir, experiment_ids):
    planned = []
    for item in items:
        kind = item.get("kind")
        if not isinstance(kind, str) or kind not in KINDS:
            raise ValueError(f"Supporting material kind must be one of {sorted(KINDS)}")
        source = required_text(item.get("path"), "supporting_materials.path")
        path = (base_dir / source).resolve()
        if not path.is_file():
            raise ValueError(f"Supporting material does not exist: {source}")
        refs = texts(item.get("experiment_ids", []), "supporting_materials.experiment_ids")
        if set(refs) - experiment_ids:
            raise ValueError(f"Unknown experiment IDs in supporting material {item['id']}")
        placement = item.get("placement", "handoff")
        if placement not in ("main", "appendix", "handoff"):
            raise ValueError("Supporting material placement must be main, appendix or handoff")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if "sha256" in item and item["sha256"] != digest:
            raise ValueError(f"Supporting material changed: {item['id']}")
        planned.append({"id": item["id"], "title": item["title"], "kind": kind,
                        "input_path": source, "resolved_path": str(path), "sha256": digest,
                        "experiment_ids": refs, "placement": placement,
                        "purpose": required_text(item.get("purpose"), "supporting_materials.purpose"),
                        "validation": "file_exists_and_hashed_only", "human_review_required": True})
    return planned


def verify_materials(outline, project):
    for item in outline.get("supporting_materials", []):
        path = evidence_path(item, project)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Supporting material changed or missing: {item['id']}")


def copy_materials(outline, staged, final, source_project=None):
    for item in outline.get("supporting_materials", []):
        source = evidence_path(item, source_project)
        relative = f"supporting/{item['id']}{source.suffix.lower()}"
        target = staged / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Supporting material changed during copy: {item['id']}")
        item.setdefault("original_path", str(source))
        item.update(project_path=relative, resolved_path=str(final / relative))


def materials_markdown(outline):
    lines = ["# 配套材料与版面安排", "", "这些材料已按哈希复制，仍需核对内容、引用和版面。正文填充不会自动执行或拼接其中的 LaTeX。",
             "统计汇总、补充对照和人工评分队列不自动变成正文指标或已完成的人工复核。", ""]
    for item in outline.get("supporting_materials", []):
        lines += [f"- [{item['title']}]({item['project_path']}) — {item['kind']} / {item['placement']}",
                  "  " + item["purpose"], "  关联实验：" + (", ".join(item["experiment_ids"]) or "整篇论文")]
    return "\n".join(lines) + "\n"
