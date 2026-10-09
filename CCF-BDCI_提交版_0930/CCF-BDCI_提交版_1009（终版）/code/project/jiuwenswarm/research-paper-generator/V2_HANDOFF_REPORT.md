# 第 3 部分：v2 实测结果对接报告

日期：2026-10-06。输入基于同学 2 提交 `b0937c4` 的 `experiments/results/memory_eval_v2/report/EXPERIMENT_HANDOFF.md`、配对导出及汇总。原始实验文件和同学 2 的交接 brief 保留；本轮新增面向论文的 `examples/memory-eval-v2.paper-brief.json`。

## 已完成

- 补接 512 Token 主比较，512 / 1024 / 2048 三个预算下的 hybrid versus BM25 结果在大纲中相邻排列。
- 每个正文结果章节只声明其文件实际包含的两个组，避免一个配对文件被写成五组基线实验。全部其余对照仍作为补充证据交付。
- 保留 `protocol_replication` 的 ID 兼容性，标题改为同一批问题上的预算敏感性，明确它不是独立复现实验或已完成人工评分复核。
- 主证据按导出清单的 SHA-256 固定；配套图表、实验段落、统计、补充原始记录、人工复核队列一并复制，形成可以移动目录的交接包。
- 写作请求传入实际组名、配对差值/校正检验、区间方法和材料索引。修复 `BM25` 等真实组名中的数字被正文校验误判为捏造数值的问题；任意百分数仍必须使用指标 token。
- 第 4 部分填充时继续携带材料；第 5 部分检查材料哈希。缺失或被修改的快照不会回退读取原机器文件。

## 本地已生成

仓库根目录下 `output/memory-eval-v2-framework-20261006/` 包含：

| 文件 | 用途 |
| --- | --- |
| `outline.json`、`sections/*.tex` | 八个主章节、三个研究问题、七个设置/结果子章节；正文尚待第 4 部分填写 |
| `research_plan.json`、`RESEARCH_HANDOFF.md` | 已完成实验与研究问题/评审意见的关联；评审问题仍为 `needs_scientific_review` |
| `evidence/raw/` | 七项正文配对结果的原始快照 |
| `supporting/`、`MATERIALS.md` | 32 份材料，含 15 项补充配对结果、五幅上游 PDF 图和复核材料；标注正文/附录/交接用途 |
| `framework_audit.json` | 数据重算及声明协议与实际文件范围的核对结果 |
| `metric_catalog.json` | 七项正文对照对应的 357 个可用指标 token |
| `writing_request.json` | 无需模型调用即可检查的正文写作请求，包含章节 ID、引用映射和已知限制 |
| `citation_map.json`、`references.bib` | 沿用已交付文献，保持稳定引用键 |

`supporting/` 中的表格、段落和图表按材料索引交接，不会自动执行或拼接到主 TeX。机器指标仅来自正文选定配对的重算；补充汇总里的其他数字需由第 4 部分进一步接入，不能仅根据文件名就写入正文。

## 重现

直接使用本轮准备好的 brief：

```powershell
python jiuwenswarm/research-paper-generator/scripts/generate_framework.py --brief jiuwenswarm/research-paper-generator/examples/memory-eval-v2.paper-brief.json --literature jiuwenswarm/research-paper-generator/examples/memory-research.literature.json --output output/v2-framework-new
python jiuwenswarm/research-paper-generator/scripts/audit_framework.py output/v2-framework-new
```

两条命令均不访问模型服务。第二条重新读取原始回答和评分标签，复算正文与补充配对统计，核对预算、组名、重复数、数据集哈希和 memory 聚类样本量，并列出尚无人工决定的复核队列。

若同学 2 交付新的导出清单，重新整理到新文件再生成框架：

```powershell
python jiuwenswarm/research-paper-generator/scripts/prepare_controlled_brief.py --output output/v2-inputs/next-paper-brief.json
```

整理器验证导出清单中的全部文件哈希，不覆盖已有 brief。默认输入为仓库中当前同学 2 的 brief 和 report；可用 `--source`、`--report` 替换。跨 Windows 盘符时来源路径使用绝对路径，框架生成后统一转为项目内快照。

`write_paper.py` 默认优先使用 `memory-eval-v2.paper-brief.json`。旧 `memory-research.content.json` 只能搭配显式指定的旧 `memory-research.brief.json`；章节和证据 ID 不匹配时不能混用。若更新默认输入，应先审查新生成 brief，再替换默认文件。

## 新增材料接口

`supporting_materials` 每项需要 `id/title/path/kind/purpose`。`path` 相对输入 brief 解析；`kind` 可为 `figure/table/prose/statistics/review_queue/documentation/supplementary_evidence`。`placement` 为 `main/appendix/handoff`，默认 `handoff`；`experiment_ids` 为已有实验 ID 数组；可提供 `sha256` 固定上游交付版本。

实验对象新增可选 `result_sha256`。指定时必须与结果文件一致，避免导出清单已固定后输入被无声更换。两种哈希都只证明字节一致性，不证明学术正确。

## 实际核对与结论边界

本轮已重算 **7 项正文对照 + 15 项补充对照**。三个主预算的 hybrid 减 BM25 准确率差分别约为 **−36.1、−29.4、−33.7 个百分点**，与队友交接一致。写作应保留这些负结果；不能继续沿用旧字符预算 pilot 的优越性叙述。

全量回归 **101 项通过**，其中本轮新增 6 项，覆盖真实交接、缺失/篡改材料、跨目录移动、声明协议冲突、评分任务仍开放以及含数字的真实组名。已有正文/引用/LaTeX 测试一并通过。本轮实际框架生成和审计也通过，没有发起新实验、付费写作或图像调用。

需要明确区分：

- 三个预算共享同一批问题；配对导出彼此也有重叠，不能累加成独立样本量。
- 500 段历史的结果是检索覆盖，不是 500 题的回答准确率。
- 当前复用配对文件给出二十次查询后的端点；完整一/五/十/二十次查询曲线在配套汇总和图中，尚未自动转换成正文指标。
- 配对导出携带回答、评分来源和构建记录，但其中引用的完整 gzip prompt/ranking 工件未包含在本交接包。审计没有独立重放模型、重新判断语义标签或打开这些外部工件。
- 239 条模型分歧已由人员5填写布尔 decision：34 条正确，205 条不正确。它们是 966 条盲审队列的子集，不能相加。队列里其余抽样回答仍为空。模型一致也不等于人工复核，主结果没有按这些决定重算。

第 3 部分的框架、证据关联、引用管理与材料交接已完成。第 4 部分继续按新大纲撰写正文、整合主图及附录；第 2 / 5 部分完成人工评分复核和科学有效性核查。新稿完成后才可重新提交评审平台，本轮没有新的 Reviewer 分数。
