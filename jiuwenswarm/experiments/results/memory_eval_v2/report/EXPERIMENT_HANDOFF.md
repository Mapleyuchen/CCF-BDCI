# 同学2实验交接：正式结果

## 已验证

- QA记录：6516；各suite：{'full': 4536, 'micro': 540, 'reuse': 1440}。
- 全量检索记录：9000；500段历史，拒答题不进入证据召回分母。
- Solver调用尝试：8196；失败尝试：0；已知tokens：7783743；usage未知尝试：0。
- 评分模型分歧：239 / 966个复核回答。这 239 条已由人员5填写 decision/reviewer/notes（34 条判为正确，205 条判为不正确）。其余抽样回答仍未复核。主结果仍使用预先指定的主评分，没有按人工决定重算。

## 主比较：hybrid 减 BM25

- 512 tokens：准确率差-36.1个百分点，95%区间[-46.0, -25.8]，Holm p=0.0021。
- 1024 tokens：准确率差-29.4个百分点，95%区间[-40.1, -18.3]，Holm p=0.0022。
- 2048 tokens：准确率差-33.7个百分点，95%区间[-44.0, -23.0]，Holm p=0.0021。

## 使用方式

- `summary.json`为全部统计依据；`paper_exports/`自包含配对原始回答、实际评分标签和写入日志。
- `experimental_methods.tex`和`experimental_results.tex`可由同学3/4纳入论文；图表为真实运行记录生成，需由论文负责人安排版面。
- `fair_baselines.pdf`、`memory_reuse.pdf`及`results_table.tex`供正文/附录使用；表格覆盖全部组，正文优先主比较，避免塞入全量长表。
- `category_accuracy.pdf`按任务类别呈现1,024 Token下的结果；置信区间和类别样本数见`summary.json`。
- 生成器使用`examples/memory-eval-v2.brief.json`及general renderer，不能套用旧L1字符预算 research profile。

## 提交前仍要完成

- 239 条模型分歧已复核，记录在 `model_disagreement_review.json`。966 条队列里其余抽样回答的 decision 仍为空。
- `judge_sensitivity.json`只替换已复核回答，未复核标签保持主评分；该范围不是人工正确率或完整第二模型评分。已填写的人工决定尚未替换主评分。
- 将旧pilot的因果和优越性主张替换为新版公平比较，保留负结果及适用边界。
- 论文负责人更新稿件、检查图表和引用并重新提交Reviewer；本实验未产生新的Reviewer评分，不能保证分数。

## 适用边界

- Question-answer evaluation uses a deterministic stratified subset; retrieval evaluation covers all 500 histories.
- Original complete histories, questions, dates and gold answers are retained; histories are split losslessly into bounded turn segments.
- A frozen read-only single-layer bank is evaluated; the legacy 20-item EnhancedMemoryRail capacity is not asserted to support full histories.
- Token caps use the pinned public Qwen3-8B BPE; service-reported input/output tokens are logged separately and may differ.
- The original LongMemEval evaluation prompts are pinned; qwen3-max-2026-01-23 replaces its recommended GPT-4o judge.
- This is a LongMemEval-S subset with disclosed deviations, not an official leaderboard score.
- Synthetic reuse banks share templates; eight entity/value variants do not establish generality on independent natural memory workloads.
- Representation and model-ACK controls use the adapted 20-item workload; they are mechanism controls, not full-history benchmark results.
- Representation ablation keeps the selector algorithm fixed; changed exchange formatting can affect both lexical features and token packing, so it does not isolate packing alone.
- Construction control canonicalizes identical source facts after real ACK writes; it measures acquisition overhead, not learned summarization quality.
- Three temperature-zero calls measure operational repeatability, not variation across model families.
- Blinded primary/secondary judge audit requires human adjudication before final paper submission.
- The hybrid selector is an existing lexical/time heuristic; no new retrieval algorithm is claimed.
- This evaluates a memory question-answering component, not the quality of automatically generated research papers; a new manuscript and reviewer evaluation are required to measure any paper-score change.
