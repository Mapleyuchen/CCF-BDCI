# 论文框架、内容填充与质量检查（第 3 / 4 / 5 部分）

2026-10-01 接口联调与离线复现结果见 [联调报告](INTEGRATION_REPORT.md)。新增证据快照随项目交接，以及 `write_paper.py --content-json` 单命令离线入口。

当前研究版入口与配置见 [API 调用说明](references/api_workflow.md) 和 [SKILL](SKILL.md)。默认使用 DashScope `qwen3.8-max` 完成规划、初稿、审阅、修订，使用百炼 `qwen-image-3.0-pro` 生成 Methodology 图；arXiv 元数据检索不需要 Key。研究版增加方法公式、Wilson 区间、逐题诊断、写入/查询成本拆分和可审计附录。以下框架输入与内容 JSON 约定继续适用。

其中第 3 部分在没有其他模块、模型服务或 API Key 的情况下，可以生成 ICLR 论文骨架、结构化大纲和引用映射。使用 Python 3.11+ 标准库；生成 PDF 另需 PATH 中有 `pdflatex` 和 `bibtex`。第 4 部分的模型写作与额外依赖见下文。

**框架生成器是规则规划器，不调用 LLM，不生成论文正文、实验数字或研究结论。** 主章节使用科研论文常见结构，方法与实验子章节根据输入生成。后续主 Agent 可以先组织研究说明，再调用本模块。尚未实现自主研究构思或主 Agent 的工具注册。

## 立即运行

在仓库根目录执行：

```powershell
python jiuwenswarm/research-paper-generator/scripts/generate_framework.py --brief jiuwenswarm/research-paper-generator/examples/brief.json --literature jiuwenswarm/research-paper-generator/examples/literature.json --output output/paper-framework-demo --compile
```

不传 `--literature` 也能生成骨架；不传 `--compile` 就完全不需要 LaTeX。输出目录必须尚不存在，避免覆盖第 4 位同学填好的内容。重新生成时选择新目录；修改正文后使用下面的命令重新编译：

```powershell
python jiuwenswarm/research-paper-generator/scripts/compile_framework.py output/paper-framework-demo
```

CLI 输入与输出路径相对当前工作目录；模板默认路径相对模块自身定位，不依赖启动目录。可用 `--template-dir` 指向另一份兼容的样式目录。

`examples/literature.json` 取自仓库已有书目，仅用于演示接入，没有联网核验元数据。它不表示该文献支持示例课题的任何结论。公开发布前应回到原文核对。

## 输入约定（版本 1）

研究说明 `--brief` 为 JSON 对象，字段如下：

| 字段 | 必填 | 内容 |
| --- | --- | --- |
| `schema_version` | 是 | 整数 `1` |
| `title` | 是 | 论文标题，普通文本 |
| `research_question` | 是 | 研究问题；保留在大纲，供写作者使用 |
| `anonymous` | 否 | 默认 `true`；`false` 显示传入作者，页面仍标注 draft |
| `authors` | 否 | 作者姓名字符串数组；非匿名时必填 |
| `methods` | 否 | 方法对象数组；每项有 `id`、`title`，可选 `description`、`citation_ids` |
| `experiments` | 否 | 实验对象数组；每项有 `id`、`title`，可选 `status`、`metrics`、`result_path` |

方法、实验的 `id` 在各自数组内唯一，使用小写字母开头及小写字母、数字、下划线、短横线。它们生成稳定的章节标签。`citation_ids` 是文献的显式 `id` 或规范 ID，例如 `arxiv:2310.08560`、`doi:10.xxxx/xxx`；引用不存在的 ID 会报错。

`status` 默认 `planned`。计划实验仅产生实验设置子章节，并列出待补数据。`completed` 必须附上存在的 `result_path`，其路径**相对原始 brief 文件所在目录**解析。模块记录 SHA-256，并将当时的原始文件复制到 `evidence/raw/`；复制后再次核对哈希。结果子章节标记为“待证据复核”，不会根据文件存在生成结论。

新证据记录的 `project_path` 相对当前论文工程解析，跨目录、跨电脑交接时以此为准。`original_path`、原始 `input_path` 只用于来源追踪；`resolved_path` 为生成时的快照绝对路径，保留给旧调用方。第 4、5 部分优先读取项目内快照，快照缺失或被修改时拒绝使用，不回退到旧电脑上的文件。生成后原始实验文件的后续变化不会改变这份已规划的证据；要采用新结果，应重新生成框架。旧的绝对路径工程仍可在原路径有效时读取，交接前建议重新生成。

这允许第 2 位同学继续使用自己的结果格式。第 3 部分只约定实验描述和文件关联，不要求对方先改实验脚本。输入给正文的实验结果由第 4 位同学解析。

### 文献输入

`--literature` 是 JSON 数组，兼容当前 `scripts/literature_search.py` 的输出。每条需要 `title`、非空 `authors` 字符串数组，以及 `year` 或 ISO 日期 `published` 的前四位。可选 `id`、`arxiv_id`、`doi`、`url`、`journal`。`abstract`、`pdf_url` 等额外字段可保留在上游输入中，不会用于生成书目。

引用管理按 DOI、去除版本号的 arXiv ID，或规范化后的“标题 + 作者 + 年份”去重。同一身份的元数据冲突会报错，交给上游核对；不做模糊去重。引用键以规范身份的哈希生成，同一元数据改变输入顺序不会改变键。后续新增 DOI 等更强身份信息可能改变引用键，应重新交付引用映射。

未提供年份、作者等必填信息时明确报错，不用假作者、假年份或示例文献补齐。无文献时传空数组或省略文件。

正文标题、子章节标题和书目使用适合英文论文的文本；默认 pdfLaTeX 工程不配置 CJK 字体。中文研究说明可放在 `research_question`、`description` 中，它们保留在 JSON，不直接排入 PDF。元数据不支持原始 LaTeX 命令，特殊字符会转义。

## 输出与协作交接

```text
<output>/
  paper.tex                 主文件及章节装配
  sections/*.tex            8 个主章节的可填写文件
  outline.json              每节目标、状态、子章节、候选引用与证据关联
  citation_map.json         规范元数据、原始 ID -> 引用键、去重来源索引
  references.bib            从输入生成的 BibTeX
  brief.input.json          研究说明快照（结果相对路径仍以原始 brief 为基准）
  evidence/raw/*.json        已完成实验的原始快照，随框架一起交接
  manifest.json             输入/样式哈希、draft 状态和待补信息
  HANDOFF.md                内容填充注意事项
  *.sty / *.bst             仓库现有 ICLR 样式依赖
  paper.pdf                 仅在编译成功后生成
  compile_report.json       编译命令、错误与警告
```

`outline.json` 的 `sections` 按论文顺序排列：`abstract`、`introduction`、`related_work`、`method`、`experiments`、`results`、`discussion`、`conclusion`。每节有 `id/title/file/goal/status/citation_keys/subsections`。子章节有 `id/title/goal/status/citation_keys`，结果子章节另外有 `evidence_ids`，引用顶层 `evidence` 数组中的记录。

第 4 位同学按 `file` 填写章节，不必更改主文件装配逻辑；摘要文件只填写摘要正文。用 `citation_map.json` 中的键写 `\citep{ref_...}` 或 `\citet{ref_...}`，不要自行重建引用键。Related Work 默认列出全部传入文献作为候选，并不代表已判定相关性或证据支持。

为验证完整书目链路，骨架使用 `\nocite{*}` 展示候选书目，并有可见草稿提示。正文完成后应移除 `\nocite{*}`、Draft bibliography 段落及各章节占位文字，改用真实逐条引用。

## 第 4 部分：根据实测数据填充内容

`scripts/fill_content.py` 接收第 3 部分生成的目录，在**新目录**里填充八个章节、结果表、PNG/SVG/PDF 图和 BibTeX，保留原骨架及已有人工编辑。模型只返回英文段落 JSON；章节结构、LaTeX、引用键、实验数值和图表由程序生成。开启 `--compile` 后串联编译和第 5 部分检查，检查失败返回非零退出码。

### Conda 环境与模型配置

只运行论文流程需要 Python 3.11、Matplotlib、PyYAML 和 python-dotenv；不需要 Torch、CUDA、模型权重或完整 JiuwenSwarm 服务。PDF 编译仍使用系统的 `pdflatex` / `bibtex`。

```powershell
conda env create -f jiuwenswarm/research-paper-generator/environment.yml
conda activate ccf-bdci
```

如果还要运行真实 DeepAgent 对照实验，在同一环境、仓库根目录执行 `python -m pip install -e ./jiuwenswarm` 安装完整项目。当前本机已安装这部分依赖，并验证没有安装 Torch/CUDA；`environment.yml` 保留的是论文流程所需的最小依赖集。

当前配置 `examples/dashscope-research.yaml` 使用百炼北京地域的文本兼容接口、`qwen3.8-max` 和环境变量 `DASHSCOPE_API_KEY`。`examples/dashscope.yaml` 保留为基础版及实验配置。使用其他地域时同时调整地址、密钥和模型。支持 `--env-file` 显式加载本机凭据；不会将模型配置或密钥复制到论文目录。模型服务调用会产生费用。

完整演示使用仓库已提交的两份真实 LongMemEval 改编实验记录，无需重新运行记忆实验：

```powershell
python jiuwenswarm/research-paper-generator/scripts/write_paper.py --output output/memory-paper-run --compile
```

命令依次执行框架生成、DashScope 规划/正文/审阅/修订、图表和书目生成、LaTeX 编译、质量检查。输入默认采用 `examples/memory-research.brief.json` 和 `memory-research.literature.json`；可通过 `--brief`、`--literature`、`--config` 替换。`--output` 必须是尚不存在的目录。默认配图来自仓库已审阅资产；加 `--generate-methodology` 才会新调用图像 API，或用 `--methodology-image` 接入自己检查过的 PNG。

**队友已经交付正文时，可用一条命令离线复现完整论文，无需 Key 或模型配置：**

```powershell
python jiuwenswarm/research-paper-generator/scripts/write_paper.py --content-json jiuwenswarm/research-paper-generator/examples/memory-research.content.json --output output/memory-paper-offline --compile
```

该命令仍会生成新框架、校验原始实验、重算指标、生成图表与 BibTeX、编译并检查 PDF，但不调用文本或图像 API。`--content-json` 与 `--config` 互斥，也不能同时指定 `--model`、`--env-file`、`--generate-methodology`、`--resume-from`；可搭配经过审阅的 `--methodology-image`、`--related-work`。正文必须与传入 brief 的章节 ID 和文献映射匹配。

可用 `--model qwen-turbo` 单独切换写作模型，不改变实验文件中的模型身份。若服务返回 `AllocationQuota.FreeTierOnly`，表示该模型的免费额度耗尽且账户禁止付费调用，需要调整百炼额度设置或选择账号下仍可用的模型。

本机实跑时 `qwen-plus` 受上述额度限制；`qwen3.8-flash` 已完成一次调用生成正文并通过后续编译和检查。可在仓库根目录复跑（输出目录需换新）：

```powershell
conda activate ccf-bdci
python jiuwenswarm/research-paper-generator/scripts/write_paper.py --model qwen3.8-flash --output output/next-paper --compile
```

单独接入第 3 部分已有骨架：

```powershell
python jiuwenswarm/research-paper-generator/scripts/fill_content.py output/my-framework --config jiuwenswarm/research-paper-generator/examples/dashscope.yaml --output output/my-filled-paper --compile
```

### 数据与正文约定

- 支持 `live_model_experiment` 和 `adapted_longmemeval_live` 两种现有实验格式，必须包含 `settings`、`records`、`runs` 和数据集 SHA-256。旧模拟实验、`--self-test` 结果、只有汇总而没有逐题记录的文件会被拒绝。
- 核对规划时的文件哈希，按 `(repeat, question_id)` 匹配两组；剔除任一组出错、历史未隔离或没有确认记忆注入的配对。准确率和证据召回从逐题记录重算，不信任旧 `summary`。完整事实是否召回仍以实验运行器的记录为依据，并非重新审阅事实文本或模型回答。
- Token 计入查询和记忆写入，保留全部已记录尝试的成本，按有效配对数摊销。缺少 usage 时显示 `not reported`，不填零。重复题数与独立题数分别记录，不自动生成显著性声明。
- 研究说明可增加 `writing_notes` 字符串数组及 `source_notes` 对象。后者将文献 ID 映射到经复核的来源摘要，让模型有依据描述 Related Work。仅有题名/作者时不能推断论文发现。
- 模型返回 `{"sections": [{"id": "abstract", "paragraphs": ["..."], "subsections": []}, ...]}`。章节和子章节 ID 必须与大纲完全一致。
- 实验数字必须使用 `[[metric:public_small.baseline.accuracy]]` 等已知指标标记，引用使用 `[[cite:longmemeval]]` 或已有引用键。程序解析并转义，拒绝未知指标、未知文献、手写数字、LaTeX 指令和占位文字。可修复的格式错误最多请求模型重写一次；HTTP 暂时错误最多重试两次。

接入另一位同学已经写好的 Related Work 时，加 `--related-work reviewed-related-work.json`。格式为 `{"paragraphs": ["Reviewed English prose with [[cite:longmemeval]]."]}`；这些段落将原样进入校验和渲染，模型不会改写。文献 ID 需存在于第 3 部分交付的引用映射。

### 输出与复核

`write_paper.py` 输出 `framework/` 和 `paper/`；`fill_content.py` 直接输出论文目录。论文目录除第 3 部分文件外还有：

| 文件 | 用途 |
| --- | --- |
| `sections/*.tex` | 已填充的正文、数据表和图引用 |
| `figures/*.{png,svg,pdf}` | 从相同标准化数据生成的可导出图 |
| `evidence/*.json` | 原始结果快照、重算指标、显示精度与哈希 |
| `content.json` / `content_attempt_*.json` | 结构化正文与校验前的模型输出 |
| `generation_request.json` | 发给写作模型的研究说明和结构化证据；不含模型凭据 |
| `content_report.json` | 成功/失败状态、校验错误、模型调用耗时和 Token |
| `paper.pdf` / `compile_report.json` | 开启编译后的论文和诊断 |
| `quality_report.json` | 第 5 部分机械检查结果 |

输出失败时保留报告及已收到的正文；修改保存的 JSON 后，可离线重新渲染到另一目录，无需重复付费：

```powershell
python jiuwenswarm/research-paper-generator/scripts/fill_content.py output/memory-paper-run/framework --content-json output/memory-paper-run/paper/content.json --output output/reviewed-paper --compile
```

若尚未产生 `content.json`，可选择 `content_attempt_1.json` 等已保存文件。内容默认标记 `human_review_required: true`。机械检查通过不代表论断、引用支持关系或实验设计已经通过学术审查。示例论文只描述小样本 L1 记忆问答；不是 LongMemEval 官方成绩，也不声称完成 L2/L3、跨重启持久化或团队实验。

这条命令行流水线尚未注册为主 Agent 工具。`SKILL.md` 已更新为真实 API 与证据流程；旧 `generate_paper.py` 和模拟实验脚本不应作为新论文的数据/写作入口。

## 第 5 部分：质量检查

`scripts/check_quality.py` 读取第 3 部分的输出目录，检查完整性、ICLR 版式和能从文件判断的写作问题。它不调用模型，也不判断实验结果是否成立。下面这些情况退出码为 1：占位文字、草稿页眉、`\nocite{*}`、缺失章节、`paper.tex` 没有 `\input` 某一节、对不上的结果文件哈希、未编译、编译之后又改了源文件、未解析引用、文献表里没有的引用键、brief 指定了引用却没写进对应章节、计划中的实验写出了提升百分比、Results 里的小数或百分数在结果文件中找不到、中文正文和 TODO。没有图只记警告。赛题不限制篇幅，页数只记在报告里，不作为失败。

```powershell
python jiuwenswarm/research-paper-generator/scripts/check_quality.py output/paper-framework-demo
```

报告写在该目录的 `quality_report.json`。`ready_for_submission` 为 true 只表示这些机械检查通过。人员 4 填完正文后应再跑一次。

提交目录用另一条命令检查，报告写在该目录的上一级，避免把报告打进 zip：

```powershell
python jiuwenswarm/research-paper-generator/scripts/check_submission.py 团队名称
```

它核对赛题要求的 `paper/paper.pdf`、Access Token、三份技术文档、框架贡献链接、资源报告和 `code/`，并拒绝 `config.yaml`、`.env` 和看起来像真实密钥的赋值。Token 是否真评过这篇 PDF，仍要人工到 Stanford Agentic Reviewer 核对。

模块不会改写原来的 `paper/`、根目录论文或已有实验结果。旧 `scripts/generate_paper.py` 仍是早期固定内容脚本，包含写死的实验数字和示例书目；第 3 部分应使用新的 `generate_framework.py`。

## 验证

```powershell
python -m unittest discover -s jiuwenswarm/research-paper-generator/tests -v
```

离线测试覆盖缺失数据、证据路径与哈希、引用键与去重、元数据冲突、LaTeX 文本转义、跨工作目录运行、拒绝覆盖和编译失败。检测到 LaTeX 时还会执行实际编译测试，检查正文引用交接、无书目和非匿名模式、未知引用拦截；未安装时跳过这两项。

真实编译使用 `pdflatex -> bibtex（有书目时）-> pdflatex -> pdflatex`，关闭 shell escape。若长论文仍提示交叉引用变化，最多再运行两轮 LaTeX；引用持续不稳定、命令错误或未解析引用均返回非零退出码。编译通过仅表示工程有效，不表示论文内容已完成。
