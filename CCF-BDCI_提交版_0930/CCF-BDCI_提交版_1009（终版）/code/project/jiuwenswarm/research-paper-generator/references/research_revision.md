# 测试反馈后的研究修订接口（第 3 部分）

本轮完成研究问题、章节规划、实验协议字段和证据交接。截图指出的基线公平性、组件混淆、成本摊销与统计局限仍需新实验回答；这份计划不表示问题已经解决，也不保证评审得分提高。

## 生成可交接框架

在仓库根目录执行，不需要模型服务或 API Key：

```powershell
python jiuwenswarm/research-paper-generator/scripts/generate_framework.py --brief jiuwenswarm/research-paper-generator/examples/memory-revision.brief.json --literature jiuwenswarm/research-paper-generator/examples/memory-research.literature.json --output output/memory-revision-framework
```

输出目录必须不存在。主要查看 `RESEARCH_HANDOFF.md`、`research_plan.json` 和 `outline.json`。主章节仍为八章，引言增加三个研究问题子章节，实验设置按实验任务组织，结果章节目前只保留两个初步实验的待复核入口。引用沿用已有文献 ID 与去重规则，没有新增未经核对的文献。

这份修订说明使用通用正文流程，未启用 `writing_profile: research`。当前研究版的自动公式、诊断和附录专用于旧 L1 实验，不应把它们直接套到尚未实现的新协议上。旧 `memory-research.brief.json` 和已交付正文保持原样，仍可离线复现。

## 本轮的任务与边界

| 任务 | 当前交付 | 后续负责人 |
| --- | --- | --- |
| 研究问题与章节 | 质量、组件归因、生命周期成本三个问题及实验关联 | 第 3 部分已实现 |
| Token 匹配和更强基线 | `fair_baselines` 协议、固定变量和证据清单 | 第 2 部分实现并运行 |
| 单因素消融 | `selection_ablation`、`representation_ablation`、`construction_ablation` | 第 2 部分实现并运行 |
| 多查询摊销 | `memory_reuse`，一次构建对应多个不同查询 | 第 2 部分实现并运行 |
| 重复运行与评分复核 | `protocol_replication`，需固定数据/评分器版本和统计单位 | 第 2 部分实施，第 5 部分复核 |
| 新证据进入正文 | 保留协议和未解决问题的写作输入及文件交接 | 第 4 部分接入新结果格式后写正文 |
| 实验有效性与论断支持 | 文件存在和哈希只记录来源，不自动作学术判断 | 第 2 / 4 / 5 部分共同复核 |

先落实公平比较和消融，再扩大样本；扩大有混淆的原实验不能替代控制变量。BM25 等候选基线只是计划，不表示仓库已经实现。

## 新增可选字段（继续使用 schema_version: 1）

顶层 `research_questions` 每项为 `id/title/question`；`review_concerns` 每项为 `id/title/description/experiment_ids`。ID 规则与已有方法和实验一致。实验 ID、研究问题 ID 的引用必须存在；未知引用和重复 ID 会在生成输出前报错。

实验可增加：

| 字段 | 类型与含义 |
| --- | --- |
| `purpose` | `pilot`、`comparison`、`ablation`、`amortization`、`replication`，默认 `comparison` |
| `research_question_ids` | 关联的研究问题 ID 数组 |
| `protocol` | 下表中的设计元数据；缺字段会列为待补，不自动补造 |
| `evidence_requirements` | 交付后还需逐项复核的原始记录和分析材料，字符串数组 |
| `limitations` | 该实验的解释边界，字符串数组 |

`protocol` 是声明的协议，不能证明运行器实际遵守。只接受下列键，拼错字段会报错：

| 字段 | 内容 |
| --- | --- |
| `budget.unit` | `tokens` 或 `characters` |
| `budget.values` | 不重复的正整数数组；计划中的预算不是实测数据 |
| `budget.scope` | 预算包含哪些内容，是否计入包装和元数据 |
| `budget.tokenizer` | Token 预算需明确 tokenizer 名称及版本；未提供会列为缺失 |
| `budget.packing` | 装入、截断、跳过和溢出规则 |
| `dataset.name/split/version/adaptation` | 数据集、划分、固定版本/哈希、相对原协议的变更 |
| `dataset.sample_size` | 正整数；在实验负责人确定规模后填写 |
| `baselines` | 基线及实现约定，字符串数组 |
| `controlled_variables/changed_variables` | 固定/改变的变量名称数组，名称不能同时出现在两边 |
| `repeats` | 正整数，布尔值不视为整数；这是计划重复次数 |
| `scoring.method/version/review` | 评分方式、实现版本、争议样本复核方式 |
| `statistics.unit/method` | 独立/聚类单位、配对与区间方法；不能将重复查询直接算作独立样本 |
| `reuse.queries_per_memory` | 摊销实验必需，不重复的正整数数组 |
| `reuse.construction_cost_policy` | 摊销实验必需，规定写入只计一次、失败和重试如何计费等 |

字符串必须非空。尚未确定的字段请省略，生成器会在 `missing_protocol_fields` 和交接文档中列出；不要用“待定”冒充已确定的 tokenizer、版本或样本量。一般比较允许多个变化因素，但 `ablation` 若声明多个变化变量会报错，应拆成独立实验。变量名称匹配仅检查字面一致，不能判定语义上是否真正控制变量。

示例提出的预算 `512/1024/2048` tokens、`3` 次重复以及 `1/5/10/20` 个复用查询均为可调整的设计初稿，不是实际运行结果。tokenizer、数据版本、样本量和评分器版本故意留空，需与实验负责人确认后补齐。示例沿用旧实验的模型说明，但新实验必须另行固定实际模型版本和解码设置。

## 结果状态与评审问题

- `planned` → `awaiting_evidence`：只生成设置，不生成结果子章节；非空 `result_path` 与该状态冲突，会报错。
- `completed` → `evidence_needs_review`：必须已有结果文件，框架创建快照并哈希；文件内容是否符合设计仍需复核。
- 评审问题没有关联实验 → `unmapped`；有关联且包含计划实验 → `awaiting_evidence`；关联实验全部交付 → `needs_scientific_review`。

不存在自动 `resolved` 或“科学审查通过”状态。即使协议字段全部填写，或 `completed` 的文件只是空对象，框架也不会据此宣称评审意见解决。现有两份实验标记为 `pilot`，且评审问题只关联新实验，以免旧结果被用于证明尚未运行的新设计。

规划器仍允许任意原始结果文件结构，由第 4 部分的证据解析器验证。当前正文解析器只支持已有两组实验格式，不能直接理解任意多基线、标准评测器或共享记忆的多查询输出。新实验交付前，第 2 / 4 部分必须约定并接入解析、指标和图表，不能把新数据伪装成旧格式。

## 给队友的具体交接

第 2 部分：按 `research_plan.json` 确定尚缺的协议项，实现并实跑实验，交付逐题、逐次、逐记忆实例记录。共享记忆摊销需记录 `memory_instance_id`，总成本按一次构建加全部查询计算，再除以查询数；失败和重试不能丢弃。更改为 `completed` 并填写相对 brief 的 `result_path` 后，重新生成新目录中的框架。

第 4 部分：按新 `outline.json` 组织正文。写作请求已经携带完整 `research_plan`；未执行协议使用将来时，初步结果与新增实验分开论述。旧 `memory-research.content.json` 的子章节 ID 不匹配修订框架，不能直接复用。填充时两份研究交接文件会随论文工程复制，指标仍只能从已有实测记录产生。

第 5 部分：核对原始记录是否遵守声明的协议，复核评分、排除规则、相关样本的统计处理和论断范围。现有机械质量检查通过不意味着研究设计或公平性通过，也不能代替标准评测协议对齐核查。

## 验证

```powershell
python -m unittest discover -s jiuwenswarm/research-paper-generator/tests -v
```

新增回归覆盖协议类型与矛盾、未知关联、单因素消融、摊销缺项、未执行实验不生成结果、已有文件不自动解决评审问题、旧输入兼容，以及第 3 → 第 4 部分的协议传递和交接文件保留。它们验证工程行为，不验证新实验结论。
