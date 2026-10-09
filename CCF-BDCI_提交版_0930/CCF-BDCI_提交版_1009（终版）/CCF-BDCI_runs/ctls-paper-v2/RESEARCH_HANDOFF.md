# 研究修订交接

此文件由研究说明生成。协议字段描述计划或声明，尚未核对实际执行；文件存在和哈希匹配不代表科学结论成立。

## 研究问题

- quality — How does CTLS answer accuracy compare against hybrid and BM25 across all three token budgets on the stratified LongMemEval-S subset?
  关联实验：fair_baselines_512, fair_baselines, protocol_replication
- attribution — Does the tier partition eliminate the temporal dominance condition by construction, and does removing decay entirely (hybrid_no_time) serve as an ablation upper bound?
  关联实验：fair_baselines_512, fair_baselines
- lifecycle — How does write-plus-query cost change when a single constructed memory bank serves multiple distinct queries, and does CTLS change that cost?
  关联实验：memory_reuse

## 实验交接（第 2 部分）

### fair_baselines_512 — CTLS versus Hybrid and BM25 at 512 Tokens

状态：evidence_needs_review；用途：comparison。

协议待补字段：无；仍需核对实际执行。

指标：semantic answer accuracy, evidence-session recall, annotated-turn recall (any fragment), complete annotated-turn coverage, write-plus-query tokens, query latency including scheduling。

- 解释边界：CTLS is evaluated on the same frozen bank as hybrid and BM25; no new model calls are required.
- 解释边界：The non-dominance property holds by construction; empirical results measure whether tier-0 candidates are consistently more useful than tier-1 candidates.
- 解释边界：Three temperature-zero calls measure operational repeatability, not variation across model families.
- 解释边界：Blinded primary/secondary judge audit requires human adjudication before final paper submission.
- 解释边界：A frozen read-only single-layer bank is evaluated; the legacy 20-item L1 capacity is not asserted to support full histories.
- 解释边界：This is a LongMemEval-S subset with disclosed deviations, not an official leaderboard score.

### fair_baselines — Primary CTLS versus Hybrid and BM25 at 1024 Tokens

状态：evidence_needs_review；用途：comparison。

协议待补字段：无；仍需核对实际执行。

指标：semantic answer accuracy, evidence-session recall, annotated-turn recall (any fragment), complete annotated-turn coverage, write-plus-query tokens, query latency including scheduling。

- 解释边界：CTLS non-dominance is a structural property of the scoring rule, not a measured empirical claim.
- 解释边界：hybrid_no_time provides a conservative ablation upper bound for CTLS on queries with mixed tier membership.
- 解释边界：Blinded judge audit remains incomplete; results use the primary predeclared judge.
- 解释边界：This is a LongMemEval-S subset with disclosed deviations, not an official leaderboard score.

### protocol_replication — CTLS Robustness at 2048 Tokens

状态：evidence_needs_review；用途：comparison。

协议待补字段：scoring.review。

指标：semantic answer accuracy, evidence-session recall, complete annotated-turn coverage, write-plus-query tokens。

- 解释边界：At 2048 tokens, nearly all tier-0 items fit within the budget, reducing the practical impact of tier partition; this budget tests whether CTLS retains the gain when budget is not a binding constraint.
- 解释边界：protocol_replication is the same 84-question subset at a higher budget, not an independent cohort.

### memory_reuse — Measured Memory Reuse on Synthetic Banks

状态：evidence_needs_review；用途：amortization。

协议待补字段：scoring.review。

指标：semantic answer accuracy, required fact-item recall, write-plus-query tokens, query latency including scheduling。

- 解释边界：Synthetic banks share templates; eight entity/value variants do not establish generality on natural workloads.
- 解释边界：The linked pair provides the endpoint after twenty queries; other prefix lengths are in supporting materials.
- 解释边界：CTLS selector substitution does not change construction cost; reuse amortization is identical to the baseline write path.

## 评审问题到实验的映射


## 正文与复核交接（第 4 / 5 部分）

- 完整协议见 research_plan.json；outline.json 的 research_plan 与其内容一致。
- planned 实验只进入实验设置，不生成结果子章节、数值或结论。待实施协议必须使用将来时。
- completed 只代表已交付文件；必须按实验 ID 核对原始记录、协议、统计单位和引用支持。
- 初步观察不能用于证明新的公平性、消融、重复运行或多查询结论。
- 修改章节后旧 content.json 不能直接复用；应按新 outline 的 ID 与顺序重新交付正文。
- 新实验格式需要第 2 / 4 部分共同接入；规划器不会执行实验或自动计算新指标。
