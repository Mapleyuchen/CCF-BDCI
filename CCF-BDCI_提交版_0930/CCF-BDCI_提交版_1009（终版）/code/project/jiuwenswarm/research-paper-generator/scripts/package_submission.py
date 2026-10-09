#!/usr/bin/env python3
"""Prepare a new contest bundle from a completed paper run and a curated prior bundle.

The template supplies the contest layout and the previously reviewed source allowlist.
Source bytes are refreshed from this checkout; credentials and runtime caches are excluded.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_tree(source, target):
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.aux", "*.log", "*.out", "*.blg", "*.synctex.gz"))


def package(root, template, run, output, additional_runs=()):
    root, template, run, output = (Path(p).resolve() for p in (root, template, run, output))
    if output.exists() or output.is_relative_to(template) or output.is_relative_to(run):
        raise ValueError("Choose a new submission directory outside the template and run")
    paper = run / "paper"
    report = json.loads((paper / "content_report.json").read_text(encoding="utf-8"))
    if report.get("status") != "completed" or not report.get("mechanical_checks_passed"):
        raise ValueError("A compiled paper with passing mechanical checks is required")
    from paper_illustration.pipeline import load_bundle
    illustrations = load_bundle(paper / "illustrations/manifest.json")
    if not (paper / "paper.pdf").read_bytes().startswith(b"%PDF-"):
        raise ValueError("Missing final PDF")
    export = json.loads((template / "evidence/source_export.json").read_text(encoding="utf-8"))
    paths = {item["repository_path"] for item in export["files"]}
    module = root / "jiuwenswarm/research-paper-generator"
    # Add new application files even before they are staged in Git.
    legacy = {"generate_paper.py", "run_baseline_experiments.py", "run_enhanced_experiments.py", "compare_results.py"}
    for path in module.rglob("*"):
        if path.is_file() and not any(p in {"__pycache__", ".git"} for p in path.parts) and path.suffix not in {".pyc", ".aux", ".log", ".out", ".blg"} and path.name not in legacy:
            paths.add(path.relative_to(root).as_posix())
    # Resolve and inspect every source before creating the new bundle.
    secret = re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
    dummy = b"sk-" + b"livekeyvalue1234567890"
    selected = []
    for relative in sorted(paths):
        source = (root / relative).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise ValueError("Curated source is missing or outside checkout: " + relative)
        if source.name in {"config_setup.py", ".env", "config.yaml"}:
            raise ValueError("Private configuration cannot be exported: " + relative)
        matches = [m.group() for m in secret.finditer(source.read_bytes())]
        if any(m != dummy or not relative.endswith("/tests/test_submission.py") for m in matches):
            raise ValueError("Potential credential in source: " + relative)
        selected.append((relative, source))
    output.mkdir(parents=True)
    for directory in ("code", "contributions"):
        (output / directory).mkdir()
    # Keep the portable wrapper, environment and reviewed historical patches.
    for path in (template / "code").iterdir():
        if path.is_file():
            shutil.copy2(path, output / "code" / path.name)
    for path in (template / "contributions").iterdir():
        if path.is_file():
            shutil.copy2(path, output / "contributions" / path.name)
    exported = []
    for relative, source in selected:
        target = output / "code/project" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        exported.append({"repository_path": relative, "sha256": sha256(target)})
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip())
    write_json(output / "evidence/source_export.json", {**{k: v for k, v in export.items() if k != "files"},
        "source_commit": commit, "working_tree_changes_included": dirty,
        "export_mode": "Curated current source copied byte-for-byte; see SHA256SUMS and source hashes", "files": exported})
    (output / "paper").mkdir()
    shutil.copy2(paper / "paper.pdf", output / "paper/paper.pdf")
    copy_tree(paper, output / "paper/source")
    copy_tree(run / "framework", output / "evidence/framework")
    copy_tree(paper / "illustrations", output / "evidence/illustration_run")
    earlier_calls = []
    for earlier in additional_runs:
        earlier = Path(earlier).resolve()
        if earlier == run or not (earlier / "illustrations/manifest.json").is_file():
            raise ValueError("Additional run must be a different recorded illustration attempt")
        copy_tree(earlier / "illustrations", output / "evidence/prior_attempts" / earlier.name)
        old = json.loads((earlier / "illustrations/manifest.json").read_text(encoding="utf-8"))
        earlier_calls.extend(c for c in old.get("calls", []) if not c.get("reused_from_previous_run"))
    writing = output / "evidence/writing_run"
    writing.mkdir()
    for path in paper.iterdir():
        if path.suffix == ".json":
            shutil.copy2(path, writing / path.name)
    upstream_calls = []
    upstream = report.get("upstream_generation_report")
    if upstream:
        source_report = Path(upstream["path"])
        if sha256(source_report) != upstream["sha256"]:
            raise ValueError("Upstream writing report changed")
        shutil.copy2(source_report, writing / "upstream_content_report.json")
        upstream_calls = json.loads(source_report.read_text(encoding="utf-8")).get("calls", [])
    if report.get("content_input_path"):
        edits = Path(report["content_input_path"]).parent / "edits.json"
        if edits.is_file():
            shutil.copy2(edits, writing / "local_prose_edits.json")
    if (template / "evidence/arxiv-cache").is_dir():
        copy_tree(template / "evidence/arxiv-cache", output / "evidence/arxiv-cache")
    # Review tokens belong to an exact PDF; never carry the previous token forward.
    (output / "Agentic Reviewer").mkdir()
    (output / "Agentic Reviewer/PaperReview-AccessToken.txt").write_text("", encoding="utf-8")
    write_json(output / "evidence/package_status.json", {
        "schema_version": 1, "prepared_date": datetime.now().date().isoformat(), "team_name": None,
        "source_commit": commit, "working_tree_changes_included": dirty,
        "paper_sha256": sha256(output / "paper/paper.pdf"), "reviewed_pdf_sha256": None,
        "upstream_pr_url": None, "human_review_completed": False,
        "note": "New candidate; team identity, matching reviewer token, upstream PR and academic human review remain required.",
        "author": {"name": "Yuan Junsong", "email": "2287884254@qq.com", "github": "GoldstreamCitadel"}})
    main = (output / "code/main.py").read_text(encoding="utf-8")
    main = main.replace("'--output', output / 'paper', *extra)",
        "'--illustration-manifest', BUNDLE / 'evidence/illustration_run/manifest.json', '--output', output / 'paper', *extra)")
    main = main.replace("if args.generate_methodology:\n                extra += ['--generate-methodology']",
        "if args.generate_methodology:\n                extra += ['--generate-illustrations']\n            else:\n                extra += ['--illustration-manifest', BUNDLE / 'evidence/illustration_run/manifest.json']")
    main = main.replace("parser.add_argument('--generate-methodology', action=", "parser.add_argument('--generate-methodology', '--generate-illustrations', action=")
    (output / "code/main.py").write_text(main, encoding="utf-8")
    (output / "code/run_guide.md").write_text("""# 提交包运行指南

Python 3.11，依赖见 code/requirements.txt；PDF 另需 pdflatex、bibtex。无需 Torch、CUDA 或 Codex。
在提交目录执行，输出目录必须是提交包外的新目录：

```powershell
python code/main.py replay --output ../paper-replay-new
python code/main.py live --generate-illustrations --output ../paper-live-new
python code/main.py test
python code/main.py verify
```

replay 使用保存正文及完整图包，零 API 调用。live 使用 DASHSCOPE_API_KEY；可加 --env-file 指定包外私有文件。
live --generate-illustrations 使用 fast 默认：一次研究理解与逐图设计，每图一个并行生图任务，一次正文生成；不开启模型审阅或重绘。
不带生成参数的 live 复用本包图示。底层 image 模式仍是固定提示词调试入口，不是配图 Agent。
详情：code/project/jiuwenswarm/research-paper-generator/references/illustration_agent.md。
更改包内材料后运行 python code/main.py manifest 更新文件哈希。
实验记录沿用原研究，没有新增目标任务实验；本轮 API 消耗是论文与配图生成消耗。
verify 对缺失队伍信息、新论文 Reviewer Token、上游 PR 和人工复核如实报缺。
""", encoding="utf-8")
    docs = output / "docs"
    docs.mkdir()
    (docs / "architecture.md").write_text("""# 系统架构

研究 brief + 文献 + 已完成实验记录 -> 证据快照 -> 配图 Agent -> 一次论文写作 -> 确定性图表与 LaTeX -> PDF 检查。
配图 Agent：一次完成研究分析与源材料关联的节点/连线/布局/提示词设计 -> 代码校验 -> 阿里云并行生图。默认无模型复审和重绘。
新增模块均在 research-paper-generator 内；没有修改 JiuwenSwarm 核心调度或记忆设计。
当前 research profile 仍有记忆研究专用统计和公式，不能宣称论文系统已适配任意课题。
""", encoding="utf-8")
    (docs / "module_call.md").write_text("""# 模块调用

code/main.py -> write_paper.py -> generate_project -> paper_illustration.pipeline.run_illustrations -> fill_project -> compile_project/check_project。
配图理解与正文复用 JsonModel 的阿里云兼容 Chat 接口；实际生图复用 generate_methodology.py 的异步原生接口。
paper/illustrations 和 evidence/illustration_run 含完整设计、提示词、PNG、实际审阅状态和哈希。正文通过 [[figure:ID]] 与图对应。
文本调用、图像任务和原研究实验分别记账；输入、阶段或图像哈希变化会阻止缓存复用。
""", encoding="utf-8")
    (docs / "innovation.md").write_text("""# 本轮工程改进

从固定方法图提示词升级为研究内容驱动的逐图设计；图的目的、机制、布局、精确标签、边关系和排除内容均显式保存。
单次规划代替多个审阅 Agent，简洁无环图与明确提示词降低重绘需要；多图并行以缩短等待，实际耗时与 Token 可追溯。深度模型审阅仅显式选择时启用。
通过图引用约束让正文解释配图；图包可独立携带和离线校验复现。没有添加实验分数或以生图绘制实测图表。
这些是论文生成系统的工程能力，不主张新记忆算法或新增实验证据。
""", encoding="utf-8")
    current_calls = earlier_calls + [c for c in illustrations["calls"] + report["calls"] + upstream_calls if not c.get("reused_from_previous_run")]
    usage = sum((c.get("usage") or {}).get("total_tokens") or 0 for c in current_calls)
    image_task_files = list((paper / "illustrations").glob("*.provenance.json"))
    for earlier in additional_runs:
        image_task_files.extend((Path(earlier).resolve() / "illustrations").glob("*.provenance.json"))
    image_tasks = {json.loads(path.read_text(encoding="utf-8")).get("task_id", sha256(path)) for path in image_task_files}
    selection_note = ("最终插图复用了已有图像；未采用的新图和具体选择原因见图包 artifact_selection，没有为此继续重绘。"
                      if illustrations.get("artifact_selection") else "")
    write_json(output / "evidence/resource_usage.json", {
        "text_calls": len(current_calls), "reported_text_tokens": usage,
        "recorded_image_tasks": len(image_tasks), "image_task_ids": sorted(image_tasks),
        "illustration_wall_seconds": illustrations.get("elapsed_seconds"),
        "offline_render_seconds": report.get("elapsed_seconds"),
        "artifact_selection": illustrations.get("artifact_selection"),
        "text_call_records": current_calls,
        "note": "Returned usage only; earlier reviewed-mode development runs excluded unless explicitly supplied. Reused image origins are retained and are not new billing."})
    (output / "resource_report.md").write_text(
        f"# 资源记录\n\n本轮保存的非缓存文本/视觉响应共 {len(current_calls)} 次（含随包失败尝试），返回 usage 合计 {usage:,} Token。"
        f"图像任务记录 {len(image_tasks)} 份。逐次耗时、任务 ID、usage 见 evidence/illustration_run 和 evidence/writing_run。"
        "若发生未返回 usage 的传输重试，此合计不代表完整账单，以服务商记录为准。\n\n"
        + selection_note + "图像来源记录可能包含复用的历史任务，不等于本轮新计费任务数；未随包保存的开发试错不计入上述合计。\n\n"
        "研究实验沿用既有 qwen-plus 记录；本次没有重新运行或新增该研究实验。环境不需要本地模型权重。\n", encoding="utf-8")
    (output / "framework_contribution.md").write_text(
        f"# 框架贡献说明\n\n源码基于 https://github.com/Mapleyuchen/CCF-BDCI/commit/{commit}；"
        f"是否含工作区改动：{dirty}。精确导出文件与哈希见 evidence/source_export.json。\n\n"
        "新增贡献为论文应用层的研究驱动配图 Agent、图文引用、低调用量并行生成与可恢复 API 编排。"
        "历史贡献 patch 在 contributions/。尚未提供真实上游 PR，仓库提交链接不等于上游 PR。\n", encoding="utf-8")
    (output / "提交说明.md").write_text("""# 提交候选版本

paper/paper.pdf 是本版本论文；paper/source 是完整源工程；code 是可运行代码；evidence 保存生成过程与来源；docs 是架构说明。
本次改进对象是自动论文生成系统的配图设计，不是追加记忆研究实验。先阅读 code/run_guide.md，可离线复现，也可用自己的阿里云 Key 在线生成。
旧版本单独保留。本文件夹不含 API Key。正式上传前仍需填写赛事队伍名、取得对应本 PDF 的 Reviewer Token、补充真实上游 PR，并完成学术人工复核。
""", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("bundle_check", output / "code/bundle_check.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    checker.write_manifest(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--additional-runs", type=Path, nargs="*", default=[], help="Earlier failed attempts to retain and include in resource accounting")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    try:
        print(package(root, args.template, args.run, args.output, args.additional_runs))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, str(error) + "\n")


if __name__ == "__main__":
    main()
