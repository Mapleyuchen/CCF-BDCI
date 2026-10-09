"""Planning metadata and evidence gaps, never an assessment of scientific validity."""

from __future__ import annotations

from copy import deepcopy

from .citations import required_text


PROTOCOL_FIELDS = {
    "budget": {"unit", "values", "scope", "tokenizer", "packing"},
    "dataset": {"name", "split", "version", "adaptation", "sample_size"},
    "scoring": {"method", "version", "review"},
    "statistics": {"unit", "method"},
    "reuse": {"queries_per_memory", "construction_cost_policy"},
}
LIST_FIELDS = {"baselines", "controlled_variables", "changed_variables"}
REQUIRED_FIELDS = (
    "budget.unit", "budget.values", "budget.scope", "budget.packing",
    "dataset.name", "dataset.split", "dataset.version", "dataset.adaptation", "dataset.sample_size",
    "baselines", "controlled_variables", "changed_variables", "repeats",
    "scoring.method", "scoring.version", "scoring.review", "statistics.unit", "statistics.method",
)
PURPOSES = {"pilot", "comparison", "ablation", "amortization", "replication"}


def texts(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array of strings")
    result = [required_text(item, label) for item in value]
    if len(result) != len(set(result)):
        raise ValueError(f"{label} must not contain duplicates")
    return result


def _positive_integer(value, label):
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer")


def _positive_integers(value, label):
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a nonempty array of positive integers")
    for item in value:
        _positive_integer(item, label)
    if len(set(value)) != len(value):
        raise ValueError(f"{label} must not contain duplicates")


def _protocol(value, purpose):
    if not isinstance(value, dict):
        raise ValueError("experiment.protocol must be an object")
    unknown = set(value) - (set(PROTOCOL_FIELDS) | LIST_FIELDS | {"repeats"})
    if unknown:
        raise ValueError(f"Unknown protocol fields: {sorted(unknown)}")
    result = deepcopy(value)
    for key, item in result.items():
        label = f"protocol.{key}"
        if key in LIST_FIELDS:
            result[key] = texts(item, label)
        elif key == "repeats":
            _positive_integer(item, label)
        else:
            if not isinstance(item, dict) or set(item) - PROTOCOL_FIELDS[key]:
                raise ValueError(f"{label} must be an object with fields {sorted(PROTOCOL_FIELDS[key])}")
            for field, field_value in item.items():
                field_label = f"{label}.{field}"
                if field in {"values", "queries_per_memory"}:
                    _positive_integers(field_value, field_label)
                elif field == "sample_size":
                    _positive_integer(field_value, field_label)
                else:
                    item[field] = required_text(field_value, field_label)
    budget = result.get("budget", {})
    if "unit" in budget and budget["unit"] not in {"tokens", "characters"}:
        raise ValueError("protocol.budget.unit must be tokens or characters")
    controls, changed = (result.get(key, []) for key in ("controlled_variables", "changed_variables"))
    if set(controls) & set(changed):
        raise ValueError("A variable cannot be both controlled and changed")
    if purpose == "ablation" and len(changed) > 1:
        raise ValueError("An ablation plan must change one variable; split multi-factor studies into separate experiments")
    return result


def _missing(protocol, purpose):
    required = list(REQUIRED_FIELDS)
    if protocol.get("budget", {}).get("unit") == "tokens":
        required.append("budget.tokenizer")
    if purpose == "amortization":
        required += ["reuse.queries_per_memory", "reuse.construction_cost_policy"]
    missing = []
    for path in required:
        value = protocol
        for part in path.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if not value:
            missing.append(path)
    return missing


def build_research_plan(questions, concerns, experiments):
    """Inputs have stable IDs validated by the outline planner. Missing design stays visible."""
    question_ids = {q["id"] for q in questions}
    for question in questions:
        question["question"] = required_text(question.get("question"), "research_questions.question")
    plans = []
    for experiment in experiments:
        eid = experiment["id"]
        refs = texts(experiment.get("research_question_ids", []), f"{eid}.research_question_ids")
        if set(refs) - question_ids:
            raise ValueError(f"Unknown research question IDs in experiment {eid}: {sorted(set(refs) - question_ids)}")
        purpose = experiment.get("purpose", "comparison")
        if not isinstance(purpose, str) or purpose not in PURPOSES:
            raise ValueError(f"experiment.purpose must be one of {sorted(PURPOSES)}")
        protocol = _protocol(experiment.get("protocol", {}), purpose)
        state = "awaiting_evidence" if experiment.get("status", "planned") == "planned" else "evidence_needs_review"
        plans.append({
            "id": eid, "title": experiment["title"], "purpose": purpose,
            "status": experiment.get("status", "planned"), "evidence_status": state,
            "research_question_ids": refs, "protocol": protocol,
            "metrics": experiment.get("metrics", []),
            "evidence_requirements": texts(experiment.get("evidence_requirements", []), f"{eid}.evidence_requirements"),
            "limitations": texts(experiment.get("limitations", []), f"{eid}.limitations"),
            "missing_protocol_fields": _missing(protocol, purpose),
            "evidence_ids": [eid] if state == "evidence_needs_review" else [],
        })
    by_id = {e["id"]: e for e in plans}
    for question in questions:
        linked = [e for e in plans if question["id"] in e["research_question_ids"]]
        question["experiment_ids"] = [e["id"] for e in linked]
        question["awaiting_evidence"] = [e["id"] for e in linked if e["status"] == "planned"]
        question["evidence_to_review"] = [e["id"] for e in linked if e["status"] == "completed"]
    for concern in concerns:
        concern["description"] = required_text(concern.get("description"), "review_concerns.description")
        refs = texts(concern.get("experiment_ids", []), "review_concerns.experiment_ids")
        if set(refs) - set(by_id):
            raise ValueError(f"Unknown experiment IDs in review concern {concern['id']}: {sorted(set(refs) - set(by_id))}")
        concern["experiment_ids"] = refs
        concern["awaiting_evidence"] = [eid for eid in refs if by_id[eid]["status"] == "planned"]
        concern["evidence_to_review"] = [eid for eid in refs if by_id[eid]["status"] == "completed"]
        # A mapping, a completed flag or a file hash cannot resolve a scientific criticism.
        concern["status"] = "unmapped" if not refs else "awaiting_evidence" if concern["awaiting_evidence"] else "needs_scientific_review"
    return {"schema_version": 1, "kind": "research_revision_plan", "scientific_review_required": True,
            "policy": "Protocols are declared plans, not verified execution. Files and mappings do not establish claim support or resolve reviewer concerns.",
            "research_questions": questions, "experiments": plans, "review_concerns": concerns}


def handoff_markdown(plan):
    lines = ["# 研究修订交接", "", "此文件由研究说明生成。协议字段描述计划或声明，尚未核对实际执行；文件存在和哈希匹配不代表科学结论成立。", "",
             "## 研究问题", ""]
    for question in plan["research_questions"]:
        lines += [f"- {question['id']} — {question['question']}",
                  "  关联实验：" + (", ".join(question["experiment_ids"]) or "尚未关联")]
    lines += ["", "## 实验交接（第 2 部分）", ""]
    for item in plan["experiments"]:
        lines += [f"### {item['id']} — {item['title']}", "",
                  f"状态：{item['evidence_status']}；用途：{item['purpose']}。", "",
                  "协议待补字段：" + (", ".join(item["missing_protocol_fields"]) or "无；仍需核对实际执行") + "。", "",
                  "指标：" + (", ".join(item["metrics"]) or "待约定") + "。", ""]
        lines += ["- 待交付并复核：" + text for text in item["evidence_requirements"]]
        lines += ["- 解释边界：" + text for text in item["limitations"]]
        lines.append("")
    lines += ["## 评审问题到实验的映射", ""]
    for concern in plan["review_concerns"]:
        lines += [f"- {concern['id']} — {concern['title']}：{concern['status']}。",
                  "  " + concern["description"],
                  "  关联实验：" + (", ".join(concern["experiment_ids"]) or "尚未关联")]
    lines += ["", "## 正文与复核交接（第 4 / 5 部分）", "",
              "- 完整协议见 research_plan.json；outline.json 的 research_plan 与其内容一致。",
              "- planned 实验只进入实验设置，不生成结果子章节、数值或结论。待实施协议必须使用将来时。",
              "- completed 只代表已交付文件；必须按实验 ID 核对原始记录、协议、统计单位和引用支持。",
              "- 初步观察不能用于证明新的公平性、消融、重复运行或多查询结论。",
              "- 修改章节后旧 content.json 不能直接复用；应按新 outline 的 ID 与顺序重新交付正文。",
              "- 新实验格式需要第 2 / 4 部分共同接入；规划器不会执行实验或自动计算新指标。", ""]
    return "\n".join(lines)
