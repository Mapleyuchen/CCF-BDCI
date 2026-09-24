---
name: research-paper-generator
description: |
  自动化科研论文生成系统：从文献调研到论文撰写的全流程自动化。
  参考FARS系统架构，实现Ideation（构思）、Planning（规划）、Experiment（实验）、Writing（写作）四大模块。
  触发词：生成论文、写论文、research paper、generate paper、自动科研、scientific research
---

# 科研论文自动生成系统

> **执行前必读**：本Skill实现了从研究构思到论文成稿的端到端自动化流程。严格按照四大阶段顺序执行。

## 系统概览

本系统参考FARS（Fully Automated Research System）架构，实现科研论文自动生成：

```
用户研究主题 
  ↓
[Ideation] 文献调研 + 问题挖掘 + 假设生成
  ↓
[Planning] 实验方案设计 + 基线确定 + 指标规划
  ↓
[Experiment] 代码实现 + 实验执行 + 数据收集
  ↓
[Writing] 论文撰写 + 图表生成 + 格式化
  ↓
输出：ICLR格式PDF论文
```

## 一、Ideation阶段（构思）

**目标**：完成文献调研，识别研究gap，生成研究假设

### 1.1 文献检索

**任务**：
1. 使用arXiv API检索相关文献
2. 关键词：Agent memory, multi-level memory, memory architecture
3. 时间范围：最近2-3年的论文
4. 数量：至少20篇相关论文

**执行**：
```python
python scripts/literature_search.py \
  --query "agent memory architecture" \
  --max-results 20 \
  --output references/literature.json
```

### 1.2 文献分析

**任务**：
1. 阅读摘要和引言，提取关键信息
2. 识别现有方法的局限性
3. 发现研究空白

**关键问题**：
- 现有Agent记忆系统有什么问题？
- 多层次记忆架构是否被充分研究？
- 团队协作中的记忆共享如何处理？

### 1.3 研究假设生成

基于文献分析，生成研究假设：

**核心假设**：
1. 多层次记忆架构（工作/任务/项目三层）能显著提升Agent的记忆管理效率
2. 混合检索策略（语义+时间+频率）比单一检索策略性能更优
3. 团队记忆共享机制能改善多Agent协作效果

**预期贡献**：
- 提出创新的多层次记忆架构
- 设计高效的混合检索算法
- 实现团队记忆同步机制
- 在JiuwenSwarm上验证效果

## 二、Planning阶段（规划）

**目标**：设计实验方案，确定评估指标和基线系统

### 2.1 实验设计

**对比实验**：

| 实验组 | 描述 | 配置 |
|-------|------|------|
| 基线系统 | 原始JiuwenSwarm记忆系统 | 使用ProjectMemoryRail |
| 改进系统 | 多层次记忆引擎 | 使用MultiLevelMemory + HybridRetrieval |

**测试任务**：
1. **单轮对话任务**：测试短期记忆（工作记忆）
   - 任务：连续5轮对话，每轮引用前序信息
   - 评估：记忆检索准确率

2. **多轮复杂任务**：测试中期记忆（任务记忆）
   - 任务：完成一个需要10步的复杂任务
   - 评估：任务完成质量、步骤连贯性

3. **跨会话项目任务**：测试长期记忆（项目记忆）
   - 任务：在3个不同会话中完成同一项目
   - 评估：知识保留率、信息一致性

4. **多Agent协作任务**：测试团队记忆共享
   - 任务：3个Agent协同完成研究任务
   - 评估：信息共享效率、协作质量

### 2.2 评估指标

**定量指标**：
- **记忆检索准确率**：Precision, Recall, F1-Score
- **响应时间**：平均响应延迟（秒）
- **Token消耗**：每个任务的Token使用量
- **任务完成率**：成功完成任务的比例

**定性指标**：
- **回答质量**：人工评分（1-5分）
- **信息连贯性**：上下文关联程度
- **知识保留**：跨会话信息保持度

### 2.3 消融实验

验证各组件的有效性：

| 实验 | 移除组件 | 目的 |
|-----|---------|------|
| Ablation-1 | 移除任务记忆层 | 验证多层次架构的必要性 |
| Ablation-2 | 使用单一检索策略 | 验证混合检索的优势 |
| Ablation-3 | 禁用团队记忆共享 | 验证协作改进效果 |

## 三、Experiment阶段（实验）

**目标**：执行实验，收集数据，分析结果

### 3.1 实验执行

**环境配置**：
```bash
# 1. 安装JiuwenSwarm（已完成）
# 2. 配置API密钥
python config_setup.py

# 3. 运行基线实验
python scripts/run_baseline_experiments.py \
  --output-dir experiments/baseline

# 4. 运行改进系统实验
python scripts/run_enhanced_experiments.py \
  --output-dir experiments/enhanced

# 5. 运行消融实验
python scripts/run_ablation_experiments.py \
  --output-dir experiments/ablation
```

### 3.2 数据收集

**记录内容**：
- 每个任务的执行日志
- 记忆检索的详细记录（查询、结果、耗时）
- Token消耗统计
- 错误和异常情况

**数据格式**：
```json
{
  "experiment_id": "baseline_task1_run1",
  "system": "baseline",
  "task_type": "single_turn",
  "metrics": {
    "accuracy": 0.85,
    "response_time": 1.2,
    "token_count": 1500
  },
  "details": {...}
}
```

### 3.3 结果分析

使用统计分析方法：
- 计算平均值和标准差
- 进行显著性检验（t-test）
- 生成对比图表

## 四、Writing阶段（写作）

**目标**：按ICLR模板撰写完整论文

### 4.1 论文结构

**ICLR 2027格式**：
```latex
\documentclass{article}
\usepackage{iclr2027_conference,times}

\title{Multi-Level Memory Architecture for Intelligent Agents: 
       A Hybrid Retrieval Approach}

\author{Anonymous Submission}

\begin{document}
\maketitle

\begin{abstract}
% 150-200词摘要
\end{abstract}

\section{Introduction}
% 问题背景、现有局限、本文贡献

\section{Related Work}
% 文献综述

\section{Method}
% 多层次记忆架构、混合检索算法、团队记忆同步

\section{Experiments}
% 实验设置、基线系统、评估指标

\section{Results}
% 实验结果、对比分析、消融实验

\section{Discussion}
% 结果讨论、局限性、未来工作

\section{Conclusion}
% 总结

\bibliography{references}
\end{document}
```

### 4.2 各章节写作要点

**Abstract（摘要）**：
- 问题陈述：Agent记忆管理的挑战
- 方法概述：多层次记忆架构
- 主要结果：性能提升X%
- 结论：有效性验证

**Introduction（引言）**：
- 背景：AI Agent系统的发展
- 动机：记忆管理的重要性
- 问题：现有方法的局限
  1. 单层记忆结构效率低
  2. 检索策略不够智能
  3. 多Agent协作缺乏记忆共享
- 贡献：
  1. 提出多层次记忆架构
  2. 设计混合检索算法
  3. 实现团队记忆同步
  4. 在JiuwenSwarm上验证

**Method（方法）**：
详细描述：
1. 系统架构图
2. 多层次记忆设计
   - WorkingMemory：短期上下文
   - TaskMemory：任务历史
   - ProjectMemory：长期知识
3. 混合检索算法
   - 语义相似度计算
   - 时间衰减函数
   - 访问频率加权
4. 团队记忆同步机制
   - 同步协议
   - 冲突解决策略

**Experiments（实验）**：
1. 实验设置
2. 基线系统介绍
3. 评估指标说明
4. 实现细节

**Results（结果）**：
1. 主要结果表格
2. 对比图表
3. 消融实验分析
4. 案例研究

### 4.3 图表生成

**必需图表**：
1. 系统架构图（Figure 1）
2. 性能对比柱状图（Figure 2）
3. 时间衰减曲线（Figure 3）
4. 消融实验结果（Table 1）
5. 详细指标对比（Table 2）

**生成工具**：
```python
python scripts/generate_figures.py \
  --data experiments/results.json \
  --output paper/figures/
```

### 4.4 编译与检查

```bash
# 编译LaTeX
cd paper
pdflatex paper.tex
bibtex paper
pdflatex paper.tex
pdflatex paper.tex

# 检查
# - 页数限制：初稿≤9页（不含参考文献）
# - 图表质量：清晰、专业
# - 参考文献：格式统一、引用正确
# - 语言：学术规范、无语法错误
```

## 五、质量检查清单

**内容完整性**：
- [ ] 摘要准确概括全文
- [ ] 引言清晰阐述问题和贡献
- [ ] 相关工作充分综述
- [ ] 方法描述详细、可复现
- [ ] 实验设计合理、充分
- [ ] 结果分析深入、有洞察
- [ ] 讨论客观、全面
- [ ] 结论简洁、有力

**实验严谨性**：
- [ ] 基线系统选择合理
- [ ] 评估指标全面
- [ ] 实验重复次数足够（≥3次）
- [ ] 统计显著性检验
- [ ] 消融实验验证各组件

**写作质量**：
- [ ] 逻辑流畅
- [ ] 语言专业
- [ ] 格式规范
- [ ] 图表清晰
- [ ] 引用准确

## 六、输出交付

**最终产物**：
1. **paper.pdf**：完整论文PDF
2. **source/**：LaTeX源文件
3. **figures/**：所有图表
4. **data/**：实验数据
5. **code/**：实验代码
6. **supplementary.pdf**：补充材料（可选）

**提交检查**：
- [ ] PDF文件正常打开
- [ ] 文件大小合理（<10MB）
- [ ] 页数符合要求
- [ ] 格式符合ICLR模板
- [ ] 作者信息已匿名（初稿）

## 七、使用示例

```text
用户: 请为我生成一篇关于Agent记忆引擎的研究论文

系统: 好的，我将执行科研论文自动生成流程。

[阶段1: Ideation]
- 正在检索相关文献...
- 已找到23篇相关论文
- 分析研究gap...
- 生成研究假设...

[阶段2: Planning]
- 设计实验方案...
- 确定评估指标...
- 规划消融实验...

[阶段3: Experiment]
- 运行基线实验...
- 运行改进系统实验...
- 收集数据并分析...

[阶段4: Writing]
- 撰写各章节...
- 生成图表...
- 编译LaTeX...
- 生成PDF...

✓ 论文生成完成！
输出文件: paper/paper.pdf
```

## 八、注意事项

1. **时间估算**：完整流程需要2-4小时（取决于实验规模）
2. **资源消耗**：预计消耗5000万-1亿Token
3. **人工介入**：关键决策点建议人工确认
4. **质量保证**：生成后需人工review和优化
5. **数据真实性**：确保实验数据真实可靠

## 九、故障排查

**常见问题**：
1. 文献检索失败 → 检查网络连接
2. 实验执行错误 → 查看日志文件
3. LaTeX编译失败 → 检查语法和包依赖
4. 图表生成失败 → 验证数据格式

**联系支持**：
如遇到问题，请查看日志文件：`logs/paper_generation.log`
