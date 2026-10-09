# 框架贡献说明

提交基于修改后的 JiuwenSwarm 源码，源仓库版本为 `e0fa45cfa18d6a71a6bcd90c4a22592fc1e4adbb`。框架源码与上游 LICENSE、第三方声明一并保留。

## 已实现的修改

| 贡献 | 源码入口 | 证据 |
| --- | --- | --- |
| 增强记忆 Rail 接入与实验校验 | `agents/harness/common/rails/enhanced_memory_rail.py` 及 memory 目录 | DeepAgent 生命周期回调、配对实验和上下文注入检查 |
| 实验可追溯性 | `experiments/agent_memory_ab.py`、`longmemeval_turn20_ab.py` | 原始回答、注入片段、写入和查询 Token、时延 |
| ICLR 框架与引用交接 | `research-paper-generator/scripts/paper_framework/` | 章节规划、引用去重、文件哈希 |
| 内容填充与检查 | `research-paper-generator/scripts/paper_content/`、`paper_quality/` | 模型正文、数值标记、图表、书目与机械检查 |

入口均相对 `code/project/jiuwenswarm/`。随包 `contributions/` 保存九份相关提交 patch，供代码审阅；它们是本仓库提交快照，不是已被上游合并的证明。

## 可核查的提交与 Patch

- [实验模块提交](https://github.com/Mapleyuchen/CCF-BDCI/commit/16761e3) 与 [patch](https://github.com/Mapleyuchen/CCF-BDCI/commit/16761e3.patch)。
- [论文框架提交](https://github.com/Mapleyuchen/CCF-BDCI/commit/886a3e4) 与 [patch](https://github.com/Mapleyuchen/CCF-BDCI/commit/886a3e4.patch)。
- [质量检查提交](https://github.com/Mapleyuchen/CCF-BDCI/commit/74e5820) 与 [patch](https://github.com/Mapleyuchen/CCF-BDCI/commit/74e5820.patch)。
- [内容填充提交](https://github.com/Mapleyuchen/CCF-BDCI/commit/c92aa710aed3678867e535d68cd4274b826adc0c) 与 [patch](https://github.com/Mapleyuchen/CCF-BDCI/commit/c92aa710aed3678867e535d68cd4274b826adc0c.patch)。

## 上游贡献状态

尚未提供真实上游 PR 链接，不能声称已经提交或合并。请在正式递交前补充 PR 的 URL、目标仓库、标题、分支及状态，并同步 `evidence/package_status.json` 的 `upstream_pr_url`。代码 patch 已备齐，可用于后续 PR 审阅。


本轮提交：[改进研究论文与百炼图像流程](https://github.com/Mapleyuchen/CCF-BDCI/commit/c92aa710aed3678867e535d68cd4274b826adc0c)，作者 Yuan Junsong <2287884254@qq.com>，GitHub 账号 GoldstreamCitadel。新增代码、论文和对应 patch 已同步。该链接是本仓库提交，不冒充上游 PR。
