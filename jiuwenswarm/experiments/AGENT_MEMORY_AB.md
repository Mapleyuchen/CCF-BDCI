# 记忆 Rail 的 Agent 对照实验

运行器：[agent_memory_ab.py](agent_memory_ab.py)。它使用真实的 openjiuwen `DeepAgent`、JiuwenSwarm 的 `ProjectMemoryRail` / `EnhancedMemoryRail` 和同一个模型配置。为了单独测记忆，它关闭工具调用与任务循环；这是 **Agent 记忆问答实验**，不是整套论文生成流程或 Code Team 实验。

## 数据和控制条件

数据集 [memory_agent_qa_v2.json](data/memory_agent_qa_v2.json) 有 20 条事实、20 道带标准答案的问题。前 5 道题与组件自检集的问题相同。默认取全部；`--max-cases 5` 只跑首 5 题。

- 两组每次运行使用同一份事实、问题、系统提示、模型条目、工具配置（无工具）、最多 1 次模型调用和 600 字符的完整记忆片段上限。
- 基线组把事实写入隔离工作区的 `JIUWENSWARM.md`。增强组逐条向 Agent 发送“记住这条事实”的前置对话，检查 20 条事实确实进入其 L1 记忆。两组均隔离用户级和管理员级记忆文件。
- 每次正式提问使用新的 `conversation_id`。运行器检查模型收到的用户消息只有本题，避免旧对话直接泄漏答案。增强组每题前恢复前置对话结束时的记忆快照，防止上一题的回答影响下一题。
- 正式提问的上下文字符预算相同，但两种 Rail 的格式不同：基线会包含文件路径等元数据。结果记录实际字符数，解释差异时应考虑格式开销。

## 运行

在 `jiuwenswarm/` 目录的 PowerShell 中，先用无网络自检确认完整 Agent 回调链可用：

```powershell
.\.venv\Scripts\python.exe experiments\agent_memory_ab.py --self-test --max-cases 5 --output experiments\results\agent_memory_ab_self_test.json
```

`--self-test` 用确定性假模型：只要正确事实 ID 出现在模型上下文，就返回预设答案。它只用于验证流程；其准确率、Token 和耗时**不能写入论文结果**。

真实模型需先在 JiuwenSwarm 的 `config.yaml` 中配置可用的默认模型。Python 代码里的 `OpenAI(base_url=..., api_key=...)` 是调用示例，不是 YAML 配置文件；其中的 `base_url` 对应这里的 `api_base`。如果服务提供 OpenAI 兼容接口，可用下面的最小配置（把地址换成实际地址）：

```yaml
models:
  default:
    model_client_config:
      client_provider: OpenAI
      api_base: https://your-endpoint/v1
      api_key: ${API_KEY}
      model_name: ${MODEL_NAME}
    model_config_obj:
      temperature: 0
modes:
  code:
    memory:
      enabled: true
```

若使用上面的最小示例，需在本机设置 `API_KEY` 和 `MODEL_NAME` 环境变量；两者为空时无法进行真实模型实验。密钥不应提交到仓库，运行器也不会把密钥写入结果。准备好配置文件后，先跑 5 题：

仓库现有 `jiuwenswarm/resources/config.yaml.example` 可复制为同目录的 `config.yaml`。若凭据保存在本机 `.env` 文件，给运行器加 `--env-file .env`；它会在读取 YAML 前加载变量，且不会将 `.env` 内容写入结果。当前本机 DashScope 配置在 YAML 中固定 `qwen-plus` 和接口地址，用 `DASHSCOPE_API_KEY` 环境变量提供密钥；`api_key` 字段引用 `${DASHSCOPE_API_KEY}`。

```powershell
.\.venv\Scripts\python.exe experiments\agent_memory_ab.py --config .\jiuwenswarm\resources\config.yaml --env-file .env --max-cases 5 --output experiments\results\agent_memory_ab_pilot.json
```

检查 5 题的原始记录、记忆片段、`history_isolated`、`memory_in_model_prompt` 和错误后，再跑完整 20 题；每次重复重建 Agent 并重新写入事实，两组顺序交替：

```powershell
.\.venv\Scripts\python.exe experiments\agent_memory_ab.py --config .\jiuwenswarm\resources\config.yaml --env-file .env --repeats 3 --output experiments\results\agent_memory_ab_live.json
```

如需其他预算，使用 `--context-chars`；两组会同时使用该值。`--top-k` 只控制增强 Rail 的最多候选条数，默认 10。实际模型、温度等参数来自同一份配置文件。运行器在内存中仅切换 `modes.code.memory.experiment_group`，不会修改用户配置。

## 结果解释

JSON 的 `records` 保存每题原始回答、标准答案、Rail 类型、记忆片段及命中事实、答题正误、模型 Token、提问耗时和错误。`runs` 单独记录增强组前置对话的模型调用、Token 与耗时，避免把写入成本漏掉。`summary` 给出两组均值和同题配对差值。Token 使用量若模型服务没有返回，会记为 `null`。

`observed_ids` 只表示提示里出现了事实编号；若文件在事实正文中途被截断，这不代表事实完整进入上下文。新运行记录的 `complete_fact_ids` 和 `evidence_recall` 要求完整事实文本出现。已有运行记录的该指标可以用下面的汇总脚本从保存的 `memory_context` 重新计算，原始 JSON 不会被改写：

```powershell
.\.venv\Scripts\python.exe experiments\report_agent_memory_ab.py
```

脚本核对四个预算（300/600/1200/2400 字符）的数据集哈希、模型、题目配对、历史隔离与提示注入，生成 `experiments/results/figures/memory_ab_budget_summary.json`、PNG 和 SVG。图中每个预算取 20 题的一轮真实模型运行；Token 指标把增强组的 20 次事实写入调用摊到这 20 道题。600 字符另外有三轮固定顺序和三轮随机事实顺序实验：

```powershell
.\.venv\Scripts\python.exe experiments\agent_memory_ab.py --config .\jiuwenswarm\resources\config.yaml --env-file .env --context-chars 600 --fact-order-seed 2026 --repeats 3 --output experiments\results\agent_memory_ab_600_shuffled_repeat3.json
```

`--fact-order-seed` 让每轮事实顺序不同，但该轮两组顺序完全相同。三轮仍是 20 道独立问题的重复观察，不能当成 60 道独立题计算显著性。

## 当前实测概览

使用同一个 `qwen-plus`、温度 0、20 道合成问题，每个预算各跑一轮时，基线在 300/600/1200/2400 字符下分别答对 0/3/14/20 题，增强组均答对 20/20。600 字符固定顺序重复三轮的基线均为 3/20；每轮重新打乱事实顺序时为 3/20、3/20、4/20，增强组均为 20/20。原始记录和图表位于 `experiments/results/`。

预算增加到 2400 字符后，两组准确率相同；这说明当前合成任务上的优势集中在受限上下文检索。增强组每轮还需 20 次模型调用写入事实，论文比较成本时应使用图中的“包含写入成本的每题 Token”。300 字符的基线结果尤其受文件路径与提示片段格式开销影响。以上是当前实现的阶段性证据，尚不足以证明真实论文生成任务或多层记忆能力的提升。

当前增强 Rail 仅把前置对话写入进程内 L1 记忆，容量 20 条；本实验不评估跨重启持久化、L2/L3 写入或团队同步。20 道题共享 20 个事实，因此重复运行和题目变体不能视为完全独立的研究样本。论文前仍需扩充项目/任务来源，并复核自动答案判定。
