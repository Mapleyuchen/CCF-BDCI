# 同学2：修订版实验交接

本版针对评审指出的预算不公平、因素混杂、写入成本未摊销、小样本及字符串评分问题。旧 `longmemeval_turn20_ab.py` 和原结果保留为 pilot；不把旧的 600/2400 字符结果当作公平检索实验。

## 运行

在 `jiuwenswarm` 目录，用已有 `.venv`，模型凭据只从本地 `.env` / `config.yaml` 读取。不要提交它们。

```powershell
.\.venv\Scripts\python.exe -m pip install -r experiments\requirements-v2.txt
.\.venv\Scripts\python.exe experiments\fetch_memory_eval_dependencies.py
.\.venv\Scripts\python.exe experiments\prepare_memory_eval.py
.\.venv\Scripts\python.exe experiments\test_memory_eval_v2.py
.\.venv\Scripts\python.exe experiments\run_memory_eval.py --self-test --suite micro --max-episodes 2 --repeats 1 --budgets 512 --output experiments/results/memory_eval_v2_smoke
# 正式运行，会产生模型调用费用；重复执行相同命令只续跑尚未完成的 trial。
.\.venv\Scripts\python.exe experiments\run_memory_eval.py
.\.venv\Scripts\python.exe experiments\run_memory_eval.py --offline-retrieval --output experiments/results/memory_eval_v2_retrieval_final
.\.venv\Scripts\python.exe experiments\score_memory_eval.py
.\.venv\Scripts\python.exe experiments\report_memory_eval.py --retrieval-run experiments/results/memory_eval_v2_retrieval_final
```

以上依赖版本来自本次实测的 Python 3.13.12 环境；项目和 openJiuwen 的基础安装按现有项目说明完成。正式运行的 `environment.json` 记录实验关键依赖版本，`code_snapshot/` 保存冻结的执行源码，`supplementary_code_snapshot/` 保存评分和报告源码。

`--self-test` 仅验证调用路径，报告程序拒绝把它当成效果数据。协议、代码、运行参数变更后须换输出目录，不能混合续跑。模型重试逐次记录，失败仍进入分母；无法获得的 usage 保留为 unknown。写入失败会停止运行，要求检查原因，不能悄悄删掉失败样本。

固定快照有每分钟调用上限；实际调用间隔至少0.65秒，429触发后全局冷却60秒。query wall clock包含排队时间，`calls.jsonl` 的 `queue_wait_ms` 与服务调用延迟分开，不用排队速度宣称方法更快。生成时可用 `score_memory_eval_stream.py` 对已落盘答案做主模型评分；它只在所有solver完成后使用同型号副评分，避免共享模型限额被两进程叠加。限流及分词修复期间的预检目录保留，未并入正式数据。

## 冻结的设计

- 数据：完整 LongMemEval-S cleaned 的 500 段历史，源文件 SHA-256 固定；不依据答案长度或运行效果筛选。QA 在运行前选定六类各12道非拒答题及12道拒答题，共84道。宏平均反映这个均衡抽样，不能冒充原500题自然分布的准确率。
- 完整历史：保留全部 user/assistant 原文、日期、问题及答案。按 turn 切成至多256个固定 Qwen3 BPE token 的片段，Unicode 无损拼接。答案及 `has_answer` 不进入候选内容或排序器。
- 公平基线：prefix、recency、Jaccard、BM25、现有 hybrid、仅去掉时间项的 hybrid。相同原始候选、元数据、包装、固定问题时间和整体条目装箱规则；512/1024/2048 token 上限包含整个记忆 section。没有给 prefix 额外文件路径开销；所有方法都跳过放不下的整体条目，不字符截断。BM25 使用 k1=1.2、b=0.75、正 idf。
- 执行：真实 `openjiuwen` DeepAgent + `TokenBudgetMemoryRail`，无工具、单次回答迭代。新会话 ID 隔离每个问题；模型只看到选择后的记忆。只读 bank 防止访问计数、写回和上题回答污染下一题。
- 模型：solver 固定 `qwen-plus-2025-12-01`，temperature=0，max_tokens=384，关闭 thinking。评分固定 `qwen3-max-2026-01-23`；原候选 qwen-max 因账户权限不可用，在正式运行前改为可用快照。记录实际返回的模型名。公开 Qwen3-8B tokenizer 是预算约定，并不宣称与服务端计费 tokenizer 完全相同；实际计费 usage 另存。
- 重复：主实验84×6×3预算×3次=4536个实际回答；micro20×3组×3预算×3次=540；reuse8个bank×20道不同问题×3组×3次=1440。合计6516个回答，加1680次真实 ACK 写入，正常情况下共8196次模型调用；评分费用另计。
- 全量检索：500×6×3=9000条检索记录。30道拒答没有正证据，排除在检索指标外；保留在 QA 准确率中。

## 三个控制实验

1. **选择**：完整公共历史上固定其他因素，只改排序器；时间消融仅减去现有加权时间贡献，不重分配其余权重。
2. **表示**：已有20条事实的 micro 工作负载上，只将 raw 改为确定性的 `User: Remember... / Assistant: ACK` 包装，metadata 不变，无额外模型写入。
3. **构建**：真实 `EnhancedMemoryRail` 经前置对话写入20条事实并验证保留；读阶段统一还原为同一份 canonical 原始事实，丢弃 ACK 内容、动态重要性等变化。raw/direct 与 raw/model-ACK 的最终模型输入须逐字相同。该实验衡量写入路径开销，不能当作学习式记忆提炼质量实验。

**关键边界**：完整历史评估使用冻结的单层 bank，绕开旧 Rail 的 L1=20容量。不能据此声称现有生产 `EnhancedMemoryRail` 支持所有长历史、更不能声称评估了 L2/L3 或团队同步。原 hybrid 的 semantic 实际是 Jaccard 词汇重合，并非 embedding 检索。

## 写一次，问多次

reuse 使用8个实体/值不同的合成记忆 bank，每个bank20道不同的问题、固定打乱顺序。每个 repeat 的 bank 只构建一次。实际测量同一序列前1/5/10/20道问答：

`每题总成本 = (该 bank 的一次写入 tokens + 前 k 道实际问答 tokens) / k`

保留 `memory_instance_id` 和 `query_index`，禁止把孤立的一问成本乘20冒充实测。报告直接写入、model-ACK、BM25直接写入；置信区间以8个bank聚类，不能把480次回答说成480个独立项目。这些bank共享模板，外推到真实长期使用必须谨慎。

## 评分与统计

原 LongMemEval 评分 prompt 固定 Git commit 和源码 SHA；保留 temporal off-by-one、update、preference、abstention 的原任务判定规则。仅 AST 加载评分函数，严格解析 yes/no，按问题/答案而非组名盲评。字符串匹配只作诊断。相同问题及相同回答可复用评分，重复 solver 回答始终实际调用。

对字符串/主评分分歧及固定 hash 的10%样本，用另一固定模型复核。`scoring/blinded_adjudication_queue.json` 留出人类 decision/reviewer/notes；二模型一致不代表人工审查完成。主要结果仍使用预先指定的主评分，不能挑对某组有利的判定。

重复运行先在每个 memory 内平均，按任务类别分层、以 memory 聚类 bootstrap 10000次，seed=20261007。比较用配对 cluster sign-flip 检验，并对全部预设 full/micro 比较做 Holm 校正；主比较为 hybrid vs BM25。区间和检验不能支持“提出新算法”或跨模型普遍优势。

完整历史的证据指标是“选中的片段是否命中标注 evidence session”，并不等价于完整答案事实进入上下文；章节和图注必须写清。query latency 不包括原始历史切分和预先构建索引；ranking/index日志单独保存，不能把 query latency 写成全流程端到端速度。

报告另提供标注 evidence turn 的任意片段命中率、原文字符覆盖比例、完整 turn 覆盖率；这些标注只在事后核验时使用，不进入候选库或检索排序。通过 gzip 提示词工件的 SHA、原始候选库 SHA、所选 ID、实际模型记忆文本和 Token 数逐一核验。时间戳使用公开历史的会话时间，参考时钟固定为问题日期；这是一种按原时间线回放的评估，不把批量导入的当下时间当作所有历史的创建时间。

## 交给同学3/4/5

- `results/memory_eval_v2/report/summary.json`：验证后的统计、CIs、配对差值和校正p值。
- `report/paper_exports/`：每个对照的自包含原始回答、评分来源、构建费用和真实组名；内容模块新增 `controlled_memory_eval_live` 适配器，重新验证回答与语义评分、按memory重算CI。预算字段为 `context_tokens`，不会冒充字符数。
- `report/results_table.tex`、`fair_baselines.{pdf,svg,png}`、`memory_reuse.{pdf,svg,png}`：实测图表。优先选择主要比较及关键消融，避免短论文堆满全部表格。
- `report/retrieval_summary.json`：全500题的检索覆盖；不能称为500题回答准确率。
- `report/full500_retrieval.{pdf,svg,png}`、`evaluation_protocol.{pdf,svg,png}`：公开完整历史的检索图和新版实验设计图；替换与本协议不符的旧多层/字符预算配图。
- `report/experimental_methods.tex`、`experimental_results.tex`、`EXPERIMENT_HANDOFF.md`：同学3/4/5可直接核查并整合的实验段落与真实结论。
- `finalize_memory_eval_handoff.py` 只接受全部既定suite、预算、3次重复及二模型评分已完成的运行；生成 `memory-eval-v2.brief.json` 后，一键 `write_paper.py` 默认使用新版证据。显式 `--brief examples/memory-research.brief.json` 可重放旧稿，不能把新稿当作已完成的Reviewer评测。
- `calls/trials/constructions/index_builds/labels/judge_calls.jsonl` 和 `artifacts/`：完整可追溯证据。`.work` 是临时 Agent 目录，不用提交。

最终提交前必须人工审查评分分歧，核实图表与结果一致，将旧 pilot 的“增强明显更好”替换成新的公平对照结论。实验改进能加强证据，算法新颖性、写作及评审最终分数仍需团队处理，不保证分数必然提高。
