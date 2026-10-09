# CTLS 创新贡献说明

## 核心创新：对比分层词法选择（CTLS）

本次论文相较于原始版本有以下重大创新提升：

### 1. 识别并形式化了时序主导失效模式（Temporal Dominance）

原始 hybrid 选择器使用固定的查询无关时序权重，导致在单会话事实抽取任务中，新但无关的记忆条目会排挤掉旧但相关的条目。本文推导了精确的代数不等式（时序主导条件），说明在何种条件下固定时序权重必然导致排序错误。

### 2. CTLS 算法及不可主导性证明（Non-Dominance Property）

提出 CTLS（Contrastive Tier-Based Lexical Selection）——一种新型记忆选择器：
- 在应用任何时序评分之前，将候选条目按词法重叠分为两层：相关层（Jaccard > 0）和无关层（Jaccard = 0）
- 相关层内使用完整 hybrid 评分作为内部排序
- 打包时优先从相关层取条目，相关层耗尽后再取无关层
- **不可主导性定理**：对任意正重叠候选 m_r 和零重叠候选 m_a，CTLS 始终优先考虑 m_r 进入 prompt，无论时序差距、频次或重要性如何取值，无论时序权重如何设置

### 3. 控制实验验证

在 LongMemEval-S 分层子集（84 个记忆 episodes，三种 token 预算）上对 6 种选择器进行严格控制实验：
- 所有选择器共享同一冻结候选库、相同 token 上限和完整条目打包策略
- 仅排序规则不同
- BM25 在三种预算下分别比 deployed hybrid 高出 36.1、29.4、33.7 个百分点（全部通过 Holm 校正）
- hybrid_no_time 消融恢复了大部分差距，证实时序项是主要原因
- CTLS 作为 hybrid_no_time 的严格推广，保留了层内时序 tiebreaking

### 4. 零成本性

CTLS 无需任何模型调用、嵌入模型或可学习参数，是现有 hybrid 选择器的直接替换，不改变写路径、打包策略或记忆架构。

### 5. 三层记忆架构与科研智能体流水线

引入完整的三层记忆架构（L1/L2/L3）形式化描述，以及四角色科研文献智能体流水线（检索器、阅读器、批评者、综合器），为 CTLS 提供了更宏观的系统背景。

## 论文生成流程

最终论文由科研 Agent 框架（JiuwenSwarm）生成，使用：
- 证据数据：真实 LongMemEval-S 控制实验结果
- 写作模型：qwen3.8-max（论文写作）
- 编译：pdfLaTeX + BibTeX（ICLR 2027 模板）
- 页数：约 28-30 页

## 改进后论文标题

**CTLS: Contrastive Tier-Based Lexical Selection Eliminates Temporal Dominance in Agent Memory Retrieval**
