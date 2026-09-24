# CCF BDCI比赛实施计划

## 比赛要求总结

### 核心任务
开发基于JiuwenSwarm的Agent系统，自动生成Agent相关的科研短论文（Short Paper）

### 关键要求
1. **必须修改JiuwenSwarm源码**（否则无效）
2. 使用ICLR 2027模板
3. 提交Stanford Agentic Reviewer评测
4. 建议主题：Agent上下文工程设计、Agent记忆引擎设计、Agent自演进

### 评分标准（100分）
- 论文质量：60分（Stanford Agentic Reviewer 40分 + 论文评测Agent 20分）
- Agent系统能力：15分
- 资源消耗：10分
- openJiuwen贡献：15分

### 参考标杆：FARS系统
- Ideation（构思）：文献调研、问题挖掘、假设生成
- Planning（规划）：实验方案设计、框架搭建
- Experiment（实验）：代码编写、实验执行、结果收集
- Writing（写作）：论文撰写
- 效果：100篇论文，平均分5.05分（高于ICLR 2026人类投稿的4.21分）

## 整体策略

### 研究主题选择：Agent记忆引擎的多层次协同设计

**选题理由：**
1. 记忆是Agent系统的核心能力，具有重要研究价值
2. JiuwenSwarm已有记忆相关模块（memory_rail, project_memory等），可以进行深度改进
3. 易于设计对比实验和消融实验来验证效果
4. 可以结合JiuwenSwarm的多智能体协作特性，研究分布式记忆共享

**研究创新点：**
1. **多层次记忆架构**：短期工作记忆 + 中期任务记忆 + 长期项目记忆
2. **记忆检索优化**：基于语义相似度和时间衰减的混合检索策略
3. **团队记忆共享**：在多Agent协作中的记忆同步和冲突解决机制
4. **记忆压缩与总结**：自动识别重要信息并进行层次化压缩

## 实施计划

### 阶段1：环境搭建与代码理解（预计1天）

**目标：**
- 搭建JiuwenSwarm开发环境
- 深入理解现有记忆系统的实现
- 确定需要修改的源码模块

**任务清单：**
1. 安装和配置JiuwenSwarm开发环境
   - 使用uv创建虚拟环境
   - 安装依赖
   - 配置模型API（使用DeepSeek或其他可用模型）
2. 分析现有记忆系统源码
   - `jiuwenswarm/agents/harness/common/memory/` 目录
   - `jiuwenswarm/agents/harness/common/rails/project_memory_rail.py`
   - `jiuwenswarm/agents/harness/common/tools/memory_tools.py`
3. 设计记忆系统改进方案
   - 确定新增的记忆层次结构
   - 设计记忆检索算法
   - 规划团队记忆共享机制

### 阶段2：JiuwenSwarm源码修改（预计2-3天）

**目标：实现增强的记忆引擎**

**核心修改内容：**

1. **新增多层次记忆模块** (`jiuwenswarm/agents/harness/common/memory/multi_level_memory.py`)
   - WorkingMemory：存储当前对话上下文
   - TaskMemory：存储任务执行历史
   - ProjectMemory：存储长期项目知识
   - 实现记忆层级之间的升级和降级机制

2. **改进记忆检索算法** (`jiuwenswarm/agents/harness/common/memory/retrieval_engine.py`)
   - 实现混合检索策略（语义相似度 + 时间衰减 + 访问频率）
   - 支持向量化检索（使用embedding）
   - 实现记忆重要性评分机制

3. **新增团队记忆共享Rail** (`jiuwenswarm/agents/harness/team/rails/team_memory_sync_rail.py`)
   - 实现多Agent间的记忆同步
   - 处理记忆冲突和合并
   - 支持记忆权限控制

4. **记忆压缩工具** (`jiuwenswarm/agents/harness/common/tools/memory_compression_tool.py`)
   - 自动识别冗余信息
   - 生成层次化摘要
   - 实现增量压缩

5. **新增Rail到harness系统**
   - 修改 `jiuwenswarm/agents/swarm/providers/builtin_rails.py` 或创建新的provider
   - 注册新的记忆相关Rails

### 阶段3：开发论文自动生成Skill（预计3-4天）

**目标：创建一个完整的科研论文自动生成系统**

**Skill结构：**
```
research-paper-generator/
├── SKILL.md                    # Skill定义
├── scripts/
│   ├── literature_search.py    # 文献检索
│   ├── experiment_runner.py    # 实验执行
│   └── paper_writer.py         # 论文撰写
├── references/
│   ├── paper_template.tex      # ICLR模板
│   └── research_guidelines.md  # 研究规范
└── tools/
    ├── arxiv_search_tool.py    # arXiv检索工具
    └── latex_generator_tool.py # LaTeX生成工具
```

**SKILL.md核心内容：**

参考FARS的四大模块，实现：

1. **Ideation阶段**
   - 使用语义搜索检索相关文献（arXiv, Google Scholar）
   - 分析现有研究的gap和痛点
   - 生成研究假设和问题

2. **Planning阶段**
   - 设计对比实验方案（基线 vs 改进方法）
   - 规划消融实验（验证各组件的有效性）
   - 确定评估指标和数据集

3. **Experiment阶段**
   - 在JiuwenSwarm上执行实验
   - 收集性能数据（记忆检索准确率、响应时间、Token消耗等）
   - 对比基线系统和改进系统

4. **Writing阶段**
   - 按ICLR模板结构生成论文各章节
   - 生成实验图表和表格
   - 格式化参考文献

### 阶段4：实验执行与数据收集（预计2-3天）

**实验设计：**

**基线系统：** 原始JiuwenSwarm记忆系统

**改进系统：** 增强的多层次记忆引擎

**评估任务：**
1. **单轮对话任务**：测试短期记忆性能
2. **多轮复杂任务**：测试中期任务记忆
3. **跨会话项目任务**：测试长期项目记忆
4. **多Agent协作任务**：测试团队记忆共享

**评估指标：**
- 记忆检索准确率（Precision, Recall, F1）
- 响应时间
- Token消耗
- 任务完成质量（人工评估）

**数据收集：**
- 记录每个实验的详细日志
- 统计Token消耗和运行时间
- 保存实验结果用于论文撰写

### 阶段5：论文生成与优化（预计2-3天）

**论文结构（ICLR格式）：**

1. **Abstract**
   - 研究问题：Agent记忆引擎的局限性
   - 提出方法：多层次协同记忆架构
   - 主要结果：性能提升指标

2. **Introduction**
   - 背景：Agent系统中记忆的重要性
   - 现有问题：单层记忆、检索效率低、团队协作难
   - 贡献：多层次记忆、优化检索、团队共享

3. **Related Work**
   - Agent记忆系统综述
   - 多Agent协作中的记忆机制
   - 知识管理和检索方法

4. **Method**
   - 多层次记忆架构设计
   - 混合检索算法
   - 团队记忆共享机制
   - 记忆压缩策略

5. **Experiments**
   - 实验设置
   - 基线系统介绍
   - 评估指标说明
   - 实验结果与分析

6. **Results and Discussion**
   - 定量结果（表格和图表）
   - 消融实验分析
   - 案例研究
   - 局限性讨论

7. **Conclusion**
   - 主要贡献总结
   - Future Work

8. **References**
   - 相关文献列表

**生成流程：**
1. 使用research-paper-generator Skill自动生成初稿
2. 基于实验数据填充结果章节
3. 生成图表和表格
4. 优化语言表达和逻辑流畅性
5. 编译LaTeX生成PDF

### 阶段6：提交准备（预计1-2天）

**提交内容清单：**

```
团队名称.zip
└── 团队名称/
    ├── paper/
    │   └── paper.pdf                          # 论文PDF
    ├── AgenticReviewer/
    │   └── PaperReview-AccessToken.txt        # 评测Token
    ├── code/
    │   ├── jiuwenswarm/                       # 修改后的源码
    │   ├── skills/
    │   │   └── research-paper-generator/      # 论文生成Skill
    │   ├── experiments/                       # 实验脚本
    │   └── README.md                          # 代码说明
    ├── docs/
    │   ├── architecture.md                    # 架构设计
    │   ├── module_call.md                     # 模块调用说明
    │   └── innovation.md                      # 创新点
    ├── framework_contribution.md              # 框架贡献说明
    ├── resource_report.md                     # 资源统计
    └── 提交说明.md
```

**关键任务：**
1. 整理修改的源码，添加详细注释
2. 编写技术文档
3. 准备PR或patch文件给openJiuwen仓库
4. 提交论文到Stanford Agentic Reviewer获取Token
5. 生成资源报告（Token消耗、运行时长统计）
6. 按目录结构打包提交

## 技术栈

- **开发语言**：Python 3.11+
- **核心框架**：JiuwenSwarm
- **LLM模型**：DeepSeek-V4-Flash（或其他高性价比模型）
- **文献检索**：arXiv API, Semantic Scholar API
- **论文生成**：LaTeX (ICLR 2027模板)
- **向量检索**：可选使用FAISS或ChromaDB
- **实验记录**：JSON格式日志

## 资源预算

根据FARS的数据（100篇论文消耗114亿Token，约10.4万美元），单篇论文约1.14亿Token。

**我们的预算策略：**
- 目标：生成1篇高质量论文
- 预计Token消耗：5000万-1亿（包括实验和论文生成）
- 成本预估：500-1000美元（使用DeepSeek等低成本模型可降至50-100美元）

**优化策略：**
1. 使用高性价比模型（DeepSeek, Qwen等）
2. 实验阶段使用较小的测试集
3. 缓存中间结果避免重复调用
4. 人工介入关键决策减少试错

## 风险与应对

### 风险1：实验效果不明显
**应对：**
- 设计更有针对性的评估任务
- 调整改进方案，增强对比度
- 进行更多消融实验证明各组件的价值

### 风险2：论文评分不理想
**应对：**
- 参考ICLR高分论文的写作风格
- 确保实验设计严谨、结果可信
- 多次迭代优化论文质量

### 风险3：时间不足
**应对：**
- 优先完成核心功能
- 简化部分实验设计
- 并行处理多个任务

### 风险4：源码修改冲突
**应对：**
- 基于最新版本的JiuwenSwarm开发
- 遵循项目的代码规范
- 充分测试避免破坏现有功能

## 成功标准

### 最低标准（确保有效提交）
- ✅ 修改了JiuwenSwarm源码
- ✅ 生成符合ICLR格式的论文PDF
- ✅ 获得Stanford Agentic Reviewer评分
- ✅ 完整的提交包

### 理想标准（争取高分）
- ✅ Stanford Agentic Reviewer评分 > 5.0
- ✅ 实验结果有明显提升（>10%）
- ✅ 代码质量高，贡献有价值
- ✅ 资源消耗合理（Token < 1亿）
- ✅ 技术文档完善

## 下一步行动

1. **立即开始**：搭建开发环境，配置JiuwenSwarm
2. **第1天**：深入分析现有记忆系统源码，确定修改方案
3. **第2-4天**：实现核心的记忆引擎改进
4. **第5-7天**：开发论文自动生成Skill
5. **第8-10天**：执行实验并收集数据
6. **第11-13天**：生成和优化论文
7. **第14天**：准备提交材料

## 总结

这个计划的核心优势：
1. **主题明确**：聚焦记忆引擎，与JiuwenSwarm契合度高
2. **可实现性强**：基于现有代码改进，风险可控
3. **实验可验证**：设计了清晰的对比实验和评估指标
4. **符合要求**：满足所有比赛要求，包括源码修改和ICLR格式
5. **创新性适中**：既有理论创新，又有工程实现

目标：产出一篇Stanford Agentic Reviewer评分5.0+的高质量论文，在比赛中获得优异成绩！
