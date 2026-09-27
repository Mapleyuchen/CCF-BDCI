# JiuwenSwarm 记忆组件实验（第一版）

`memory_rail_benchmark.py` 对比当前仓库中的 `ProjectMemoryRail` 与
`MultiLevelMemory + HybridRetrievalEngine`。两组接收同一批事实，使用相同的
最终上下文字符预算。基线由 `ProjectMemoryRail.before_model_call` 实际读取
`JIUWENSWARM.md` 并生成提示词片段；增强组由真实分层记忆与混合检索引擎排序。

该实验测量目标事实进入模型上下文的比例（`mean_recall`）、上下文长度和检索耗时。
它**没有调用大模型**，因此不代表最终回答准确率、Token 消耗或 Agent 任务完成率。
两组的耗时范围也不同：基线包括文件发现和提示词片段生成，增强组只包括内存
检索和片段拼接；`median_latency_ms` 仅用于排查运行性能，不能据此宣称提速。
当前固定任务集只有 5 个问题，且事实顺序固定；命中率仅用于流程自检。
重复次数用于观察运行时耗时；同一固定任务的重复运行不构成独立样本，不能据此
声称统计显著性。论文中的其他实验数值仍需真实 Agent 运行记录支持。

## 运行

先按照项目 `docs/zh/Quickstart.md` 安装依赖。在 `jiuwenswarm/` 目录运行：

```powershell
.\.venv\Scripts\python.exe experiments\memory_rail_benchmark.py `
  --dataset experiments\data\memory_retrieval_v1.json `
  --output experiments\results\memory_rail_benchmark.json `
  --context-chars 600 --top-k 10 --repeats 3
```

输出保留逐题的查询、标准事实 ID、上下文正文、命中情况、延迟，以及数据集
SHA-256，便于复核。`results/` 是运行产物，不应手工填写数字。

## 下一步

真实 DeepAgent 的双组问答实验已接入，详见 [AGENT_MEMORY_AB.md](AGENT_MEMORY_AB.md)。
公开来源的独立问答实验见 [LONGMEMEVAL_TURN20.md](LONGMEMEVAL_TURN20.md)。
它记录原始回答、模型配置、Token、错误、会话 ID 与实际注入的记忆，并完成
跨会话提问。下一步需要逐题人工复核公开数据的回答，并在论文中明确这是改编基准；
当前增强 Rail 只验证
进程内 L1 记忆，尚未验证跨重启持久化或团队记忆同步。
