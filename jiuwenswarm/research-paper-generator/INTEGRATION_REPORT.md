# 第 3 / 4 / 5 部分接口联调（2026-10-01）

本轮基于 `3a603b0` 及其之前的队友提交，检查论文框架与新加入的文献、内容和质量模块的实际衔接。使用仓库保存的正文与实验数据，不重新调用模型或声称进行了新实验。

## 新模块与交接关系

| 部分 | 已有入口 | 与框架的接口 |
| --- | --- | --- |
| 文献检索 | `literature_search.py` | arXiv 元数据数组；研究 brief 使用的显式文献别名必须保留 |
| 实验 | `experiments/` 中逐题结果 | `completed` 实验关联原始 `records` / `runs` JSON，内容模块重算配对指标 |
| 框架 | `generate_framework.py` | `outline.json`、`citation_map.json`、章节文件、证据快照 |
| 内容 | `fill_content.py` / `paper_content/` | 按大纲 ID 填充章节，通过指标与引用标记生成正文、表格和图 |
| 质量 | `check_quality.py` / `check_submission.py` | 核对工程文件、哈希、引用、编译结果与提交包材料 |

`write_paper.py` 已经串联框架与内容流程。现有科研版还提供规划、草稿、审阅、修订阶段、方法图和逐题附录。普通研究规划与特定 `jiuwenswarm_l1_v1` 的固定公式/配图仍需区分。

## 本轮修复

1. **证据交接依赖原电脑路径。** 原框架只保存实验文件的绝对路径；内容模块与质量模块也直接读取此路径。回归测试通过移动框架、隐藏原始实验文件复现失败。现在框架保存逐字节证据快照与 SHA-256，使用项目相对的 `project_path`；第 4、5 部分采用同一解析函数。缺失或修改快照仍然失败，不回退到其他证据。
2. **完整入口缺少离线模式。** 原 `write_paper.py` 总是加载模型配置，保存正文只能通过分开的命令重排。现在 `--content-json` 可从研究说明到 PDF 一次运行，且明确拒绝与付费图像生成或在线恢复参数混用。
3. **长论文交叉引用未稳定就报告成功。** 原固定编译轮数在真实研究版中留下 `Label(s) may have changed`。现在根据日志最多追加两轮，超过五轮 LaTeX 仍不稳定则失败，不无限重试。

## 离线复现

仓库根目录执行，输出必须是新目录：

```powershell
python jiuwenswarm/research-paper-generator/scripts/write_paper.py --content-json jiuwenswarm/research-paper-generator/examples/memory-research.content.json --output output/pdf/integration-20261001 --compile
```

输入为 `memory-research.brief.json`、`memory-research.literature.json`、`memory-research.content.json`、两份 LongMemEval 改编逐题记录，以及已有方法图。此次运行文本和图像模型调用均为零。

| 记录 | 记忆片段字符预算 | 有效配对题数 | 基线答对 | 增强组答对 |
| --- | ---: | ---: | ---: | ---: |
| `public_small` | 600 | 20 | 0 | 13 |
| `public_large` | 2400 | 20 | 12 | 19 |

两行共享同一批问题，不能计作四十道独立问题；这些是对旧实验文件的重算，不是新实验成绩。

生成工程位于 `output/pdf/integration-20261001/paper/`：PDF 共 11 页，质量报告为 75 项通过、0 错误、0 警告。全部页面已渲染检查，未发现文字/图表越界、重叠或未解析引用。编译日志仅保留关闭 shell escape 时的 epstopdf 提示；交叉引用已稳定。

运行回归检查：

```powershell
python -m unittest discover -s jiuwenswarm/research-paper-generator/tests -v
```

本机 69 项测试全部通过。覆盖既有模块、目录迁移、源文件后续变化与快照隔离、快照篡改/丢失、旧格式兼容、离线不加载凭据及编译引用收敛。

## 当前边界

- 本轮完成工程交接与离线复现，未注册主对话 Agent 工具，也未增加自动选题或新实验。
- 研究版公式和方法图对应当前 L1 实现；不能直接推广为其他方法的模板内容。
- 机械检查不等于学术评审，仍保留 `human_review_required: true`。提交包还需要真实团队信息、对应论文的 Reviewer Token 与框架贡献材料。
- 本轮更改留在工作区；线上模型流程没有重新付费验证。
