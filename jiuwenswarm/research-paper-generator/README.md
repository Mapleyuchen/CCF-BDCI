# 第 3 部分：论文框架生成

本模块在没有其他模块、模型服务或 API Key 的情况下，可以生成 ICLR 论文骨架、结构化大纲和引用映射。使用 Python 3.11+ 标准库；生成 PDF 另需 PATH 中有 `pdflatex` 和 `bibtex`。

**当前为规则规划器，不调用 LLM，不生成论文正文、实验数字或研究结论。** 主章节使用科研论文常见结构，方法与实验子章节根据输入生成。后续主 Agent 可以先组织研究说明，再调用本模块。尚未实现自主研究构思或主 Agent 的工具注册。

## 立即运行

在仓库根目录 `E:\rollup\CCF` 执行：

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

`status` 默认 `planned`。计划实验仅产生实验设置子章节，并列出待补数据。`completed` 必须附上存在的 `result_path`，其路径**相对原始 brief 文件所在目录**解析。模块记录结果文件路径和 SHA-256，生成“待证据复核”的结果子章节；不会读取数值生成结论，也不会把文件存在当作实验有效的证明。

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
  manifest.json             输入/样式哈希、draft 状态和待补信息
  HANDOFF.md                内容填充注意事项
  *.sty / *.bst             仓库现有 ICLR 样式依赖
  paper.pdf                 仅在编译成功后生成
  compile_report.json       编译命令、错误与警告
```

`outline.json` 的 `sections` 按论文顺序排列：`abstract`、`introduction`、`related_work`、`method`、`experiments`、`results`、`discussion`、`conclusion`。每节有 `id/title/file/goal/status/citation_keys/subsections`。子章节有 `id/title/goal/status/citation_keys`，结果子章节另外有 `evidence_ids`，引用顶层 `evidence` 数组中的记录。

第 4 位同学按 `file` 填写章节，不必更改主文件装配逻辑；摘要文件只填写摘要正文。用 `citation_map.json` 中的键写 `\citep{ref_...}` 或 `\citet{ref_...}`，不要自行重建引用键。Related Work 默认列出全部传入文献作为候选，并不代表已判定相关性或证据支持。

为验证完整书目链路，骨架使用 `\nocite{*}` 展示候选书目，并有可见草稿提示。正文完成后应移除 `\nocite{*}`、Draft bibliography 段落及各章节占位文字，改用真实逐条引用。

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

真实编译使用 `pdflatex -> bibtex（有书目时）-> pdflatex -> pdflatex`，关闭 shell escape；命令错误和未解析引用会导致非零退出码。编译通过仅表示工程有效，不表示论文内容已完成。
