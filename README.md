# CCF BDCI 2026：JiuwenSwarm 记忆实验与论文生成

项目包含记忆增强 Rail、真实 Agent 对照实验，以及从证据、文献到 ICLR PDF 的论文流水线。

最新研究版论文：[paper_memory_research_20260930.pdf](paper_memory_research_20260930.pdf)。本版使用 DashScope `qwen3.8-max` 规划、撰写、审阅和修订，方法图使用百炼 `qwen-image-3.0-pro`；实验图表由原始记录计算。旧版 [paper_memory_study_20260930.pdf](paper_memory_study_20260930.pdf) 和 [paper_iclr2027.pdf](paper_iclr2027.pdf) 单独保留。

## 当前已完成的流程

| 模块 | 实际能力 |
| --- | --- |
| 文献 | arXiv HTTPS API、字段查询/ID 查询、三秒限流、Atom 缓存与来源记录；当前研究引用六篇真实来源 |
| 实验 | openJiuwen DeepAgent 的文件记忆与 L1 检索记忆配对比较，检查历史隔离及实际提示词注入 |
| 框架 | 规则规划八章节、ICLR 样式、文献去重与稳定引用键、输入哈希 |
| 内容 | 四阶段模型写作、已知数值/引用标记、方法图、公式、成本图、逐题诊断与附录 |
| 检查 | LaTeX/BibTeX 编译、文件与引用完整性、数值来源、格式检查；仍需人工学术审阅 |

这是一条可直接运行的 CLI 流水线，尚未注册为主聊天 Agent 的工具。既有 L2/L3 与团队同步代码不等于已经完成对应实验。

## 真实实验范围

论文依据两份已保存的 `qwen-plus` 结果。每个预算使用同一组二十道 LongMemEval 改编问题，单次运行；不是官方基准成绩，也不是组件消融。

| 记忆字符预算 | 文件基线准确率 | 检索 L1 准确率 | 基线总 Token | 检索总 Token（含写入） |
| --- | --- | --- | --- | --- |
| 600 | 0/20 | 13/20 | 4,686 | 101,669 |
| 2400 | 12/20 | 19/20 | 16,877 | 264,036 |

检索组的写入开销很高；两组的格式和构建方式也不同，不能把差异完全归因于排序算法。Wilson 区间只提供描述性不确定性，不能代替重复实验或显著性检验。旧演示脚本的固定提升百分比不作为本项目的实测结论。

## 本机运行

```powershell
conda env create -f jiuwenswarm/research-paper-generator/environment.yml
conda activate ccf-bdci
python jiuwenswarm/research-paper-generator/scripts/write_paper.py --output output/my-research-paper --compile
```

已有环境时直接激活。设置 `DASHSCOPE_API_KEY`，并安装系统 LaTeX（`pdflatex`、`bibtex`）。论文流程无需 Torch、CUDA 或本地模型权重；默认使用已保存的方法图。重新出图和论文的完整入口：

```powershell
python jiuwenswarm/research-paper-generator/scripts/write_paper.py --generate-methodology --output output/my-paper-with-new-image --compile
```

默认配置：[dashscope-research.yaml](jiuwenswarm/research-paper-generator/examples/dashscope-research.yaml)。只引用环境变量，不含密钥。arXiv 无需 Key。详见 [API/环境/恢复说明](jiuwenswarm/research-paper-generator/references/api_workflow.md)、[输入与输出约定](jiuwenswarm/research-paper-generator/README.md)、[项目 SKILL](jiuwenswarm/research-paper-generator/SKILL.md)。

```powershell
python -m unittest discover -s jiuwenswarm/research-paper-generator/tests -v
```

完整 Agent 实验另需 `python -m pip install -e ./jiuwenswarm`；参考 [实验协议](jiuwenswarm/experiments/LONGMEMEVAL_TURN20.md)。更换写作模型不会重跑实验。

提交材料保留真实模型调用、实验记录、源代码和哈希。正式参赛还需队伍名称、针对最终 PDF 的 Reviewer Token、上游贡献 PR 和人工复核；本地机械检查通过不代表这些材料已经齐全。
