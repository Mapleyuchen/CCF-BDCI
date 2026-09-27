# 公开记忆基准：LongMemEval-S 的 20 轮改编实验

本实验使用 [LongMemEval 作者仓库](https://github.com/xiaowu0162/LongMemEval)发布的
[LongMemEval-S cleaned 数据](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned)。
原始数据文件位于本地 `data/public/longmemeval_s_cleaned.json`，已被 Git 忽略。
来源 SHA-256 为 `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`。
数据集标记为 MIT；论文引用为 Wu 等人的 *LongMemEval*（ICLR 2025）。

这个切片**不是 LongMemEval 官方成绩**。原始 500 道问题中的多轮历史被改成
每题独立的 20 条事实，目的是测试本项目单层记忆 Rail 在同一事实输入下的检索和问答。
`prepare_longmemeval_slice.py` 从原始 S 数据中选出 `single-session-user` 类型，要求
唯一标注答案轮次、答案文本出现在该轮中而不出现在问题中，以及至少 19 条不含答案的
干扰轮次。符合条件的 22 题按原始 question ID 排序取前 20；每题用固定种子从同一
原始历史采样 19 条干扰轮次，再打乱事实顺序。问题、答案和轮次内容来自原数据，
增加的日期、角色和事实 ID 用来保留上下文并追踪证据。

改编数据：[`data/longmemeval_s_turn20_v1.json`](data/longmemeval_s_turn20_v1.json)。
重建命令（需要先下载作者发布的原始 S 文件）：

```powershell
.\.venv\Scripts\python.exe experiments\prepare_longmemeval_slice.py
```

## 配对运行

在 `jiuwenswarm/` 目录执行。先跑无网络自检；它使用假模型，只检查 Agent、Rail、
上下文和记录链路，**不可用作模型成绩**：

```powershell
.\.venv\Scripts\python.exe experiments\longmemeval_turn20_ab.py --self-test --max-cases 3 --output experiments\results\longmemeval_s_turn20_self_test.json
```

正式运行使用本地忽略的配置文件和 `.env`，其中的模型为 `qwen-plus`、温度为 0。
`--max-cases 0` 跑全部 20 道独立问题；`--context-chars` 同时控制两组记忆片段预算。

```powershell
.\.venv\Scripts\python.exe experiments\longmemeval_turn20_ab.py --config .\jiuwenswarm\resources\config.yaml --env-file .env --max-cases 0 --context-chars 600 --output experiments\results\longmemeval_s_turn20_live.json
.\.venv\Scripts\python.exe experiments\longmemeval_turn20_ab.py --config .\jiuwenswarm\resources\config.yaml --env-file .env --max-cases 0 --context-chars 2400 --output experiments\results\longmemeval_s_turn20_live_2400.json
```

每题两组获得相同的 20 条事实、问题、模型设置和字符预算。基线将事实写入隔离的
`JIUWENSWARM.md`，增强组通过 20 次前置对话写入 `EnhancedMemoryRail` 的进程内
L1；正式提问使用新会话，且各题重新创建 Agent。两组运行顺序逐题交替。使用
openjiuwen `DeepAgent` 与本仓库的真实 Rail；关闭工具和任务循环，只评估记忆问答。

结果 JSON 的 `records` 保存原始回答、标准答案、注入片段、完整证据是否进入上下文、
模型 Token、正式提问耗时及错误；`runs` 保存增强组每条事实写入的模型调用、Token
和耗时。`resource_totals` 把写入 Token 计入增强组的总开销。

当前自动正确性判定为标准答案字符串包含检查；它适合初筛，但正式论文应逐题人工复核
原始回答与标准答案，或采用单独定义的语义评判。证据召回要求完整目标事实出现在模型
收到的记忆片段。两个预算共享同一批 20 题，不能合并成 40 个独立样本。基线的文件
路径和标题也消耗字符预算，因此结果会受 Rail 提示格式影响。增强组额外进行 20 次
模型写入，其成本必须与准确率一起报告。

## 当前实测

600 字符、20 题：基线回答准确率及完整证据召回均为 0/20；增强组均为 13/20。
两组有效题目均为 20，且正式提问历史隔离、记忆注入检查通过。增强组另外用了
400 次模型写入调用，写入与提问合计 101669 Token；基线提问合计 4686 Token。
这说明 600 字符条件下基线大量证据被截断，不足以单独说明更宽预算下的优势。

2400 字符、同一批 20 题：基线答对 12/20、完整证据召回 11/20；增强组答对
19/20、完整证据召回 19/20。基线有一题虽然未获得完整事实文本，截断后的片段仍
包含了正确答案，因此准确率比完整证据召回高一题。增强组与基线准确率相差 7 题，
但增强组也有一题未取回证据并回答 `UNKNOWN`。两个预算的原始回答均已逐题检查；
自动判定未见明显错分，正式论文仍应写明字符串评分规则。

2400 字符条件下，基线提问使用 16877 Token；增强组提问使用 14638 Token，
加上 400 次写入调用的 249398 Token，总计 264036 Token。按每题摊销分别约为
844 与 13202 Token。基线平均提问耗时约 717 ms；增强组平均提问耗时约 601 ms，
但计入写入后每题约 7133 ms。增强组的准确率收益伴随明显的写入成本。

汇总和图表用以下命令从原始 JSON 重建，输出位于 `results/figures/`：

```powershell
.\.venv\Scripts\python.exe experiments\report_longmemeval_turn20.py
```

论文图可使用 `longmemeval_turn20_budget.svg`；精确数值见
`longmemeval_turn20_budget_summary.json`。20 题样本量仍小，且每个预算仅运行一轮；
不应对两个预算间的差异做显著性声明。下一步若要发表更强的结论，需要增加公开题目
和重复运行，或加入团队协作场景；这些尚未包含在当前单层 L1 实验中。
