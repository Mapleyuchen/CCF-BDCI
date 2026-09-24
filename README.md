# CCF BDCI 2026 - 基于JiuwenSwarm的Agent科研论文自动生成系统

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![JiuwenSwarm](https://img.shields.io/badge/JiuwenSwarm-enhanced-green.svg)](https://github.com/openJiuwen-ai/jiuwenswarm)

## 📖 项目简介

本项目为CCF BDCI 2026比赛开发，实现了基于JiuwenSwarm框架的**多层次Agent记忆引擎增强系统**，并集成**科研论文自动生成**功能。

**研究主题**：Multi-Level Memory Architecture for Intelligent Agents: A Hybrid Retrieval Approach

## 🌟 核心创新

### 1. 三层记忆架构
- **L1 Working Memory**：短期对话上下文（20条，1小时TTL）
- **L2 Task Memory**：任务执行历史（100条，7天TTL）
- **L3 Project Memory**：长期知识存储（无限容量，持久化）

### 2. 混合检索引擎
结合4种检索信号：
- 语义相似度（Jaccard/Embedding）
- 时间衰减（指数函数）
- 访问频率（对数归一化）
- 重要性评分（用户设定）

### 3. 团队记忆同步
- 增量同步机制
- 冲突检测与解决
- 访问权限控制

### 4. 端到端自动化
从文献调研到论文成稿的全流程自动化：
- 文献自动检索（arXiv API）
- 实验自动执行（基线+增强系统）
- 结果自动分析（对比+消融实验）
- 论文自动生成（ICLR格式）

## 📊 性能提升

| 任务类型 | 指标 | Baseline | Enhanced | 提升 |
|---------|------|----------|----------|------|
| 单轮对话 | F1-Score | 89.0% | 93.0% | **+4.5%** |
| 多步骤 | 完成率 | 90.0% | 100.0% | **+11.1%** |
| 多步骤 | 连贯性 | 72.9% | 88.3% | **+21.1%** |
| 跨会话 | 保留率 | 75.0% | 87.0% | **+16.0%** |
| 跨会话 | 一致性 | 62.0% | 83.0% | **+33.9%** |

**平均性能提升：11.82%** | **最大提升：33.9%**

## 🚀 快速开始

### 环境要求
- Python 3.11+
- Git
- LaTeX（用于编译论文）

### 安装

```bash
# 1. 克隆项目
git clone https://github.com/Mapleyuchen/CCF-BDCI.git
cd CCF-BDCI

# 2. 安装JiuwenSwarm
cd jiuwenswarm
pip install -e .

# 3. 配置API密钥
# 编辑 ~/.jiuwenswarm/config/config.yaml
# 配置你的LLM API密钥（支持OpenAI、Anthropic、DeepSeek等）
```

### 验证安装

```bash
# 测试核心模块
python -c "from jiuwenswarm.agents.harness.common.memory.multi_level_memory import MultiLevelMemory; print('✅ 成功')"
python -c "from jiuwenswarm.agents.harness.common.memory.retrieval_engine import HybridRetrievalEngine; print('✅ 成功')"
python -c "from jiuwenswarm.agents.harness.common.rails.enhanced_memory_rail import EnhancedMemoryRail; print('✅ 成功')"
```

## 📁 项目结构

```
CCF-BDCI/
├── README.md                           # 本文件
├── COLLABORATOR_GUIDE.md               # 协作者指南 ⭐
├── PLAN.md                             # 实施计划
├── STAGE2_COMPLETION_REPORT.md         # 第二阶段报告
├── PROJECT_STATUS_AND_NEXT_STEPS.md    # 项目状态
│
├── jiuwenswarm/                        # 主项目目录
│   ├── jiuwenswarm/                    # 核心改进模块
│   │   ├── agents/harness/common/
│   │   │   ├── memory/
│   │   │   │   ├── multi_level_memory.py          # 多层次记忆 ⭐
│   │   │   │   └── retrieval_engine.py            # 混合检索 ⭐
│   │   │   ├── rails/
│   │   │   │   ├── enhanced_memory_rail.py        # 增强Rail ⭐
│   │   │   │   └── __init__.py
│   │   │   └── tools/
│   │   │       └── memory_compression_tool.py     # 记忆压缩 ⭐
│   │   └── agents/harness/team/rails/
│   │       └── team_memory_sync_rail.py           # 团队同步 ⭐
│   │
│   ├── research-paper-generator/       # 论文生成Skill
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       ├── literature_search.py
│   │       ├── run_baseline_experiments.py
│   │       ├── run_enhanced_experiments.py
│   │       ├── compare_results.py
│   │       └── generate_paper.py
│   │
│   ├── experiments/                    # 实验数据
│   │   ├── baseline/results.json
│   │   ├── enhanced/results.json
│   │   └── comparison/comparison.json
│   │
│   ├── paper/                          # 论文输出
│   │   ├── paper.pdf                   # 最终论文
│   │   └── paper.tex
│   │
│   └── docs/                           # 技术文档
│       ├── architecture.md
│       ├── module_call.md
│       ├── innovation.md
│       └── INTEGRATION_GUIDE.md        # 集成指南 ⭐
│
└── iclr-2027-style-files/              # 论文模板
```

## 💻 使用示例

### 1. 启用增强记忆系统

**方式一：配置文件**
```yaml
# config.yaml
agent:
  rails:
    - type: swarm.enhanced_memory
      params:
        workspace: ~/.jiuwenswarm/memory
        enable_hybrid_retrieval: true
        max_context_items: 10
```

**方式二：代码集成**
```python
from jiuwenswarm.agents.harness.common.rails.enhanced_memory_rail import EnhancedMemoryRail

memory_rail = EnhancedMemoryRail(
    workspace="/path/to/workspace",
    enable_hybrid_retrieval=True
)
agent.register_rail(memory_rail)
```

### 2. 运行完整实验流程

```bash
cd jiuwenswarm

# 1. 基线实验
python research-paper-generator/scripts/run_baseline_experiments.py \
  --output-dir experiments/baseline

# 2. 增强系统实验
python research-paper-generator/scripts/run_enhanced_experiments.py \
  --output-dir experiments/enhanced

# 3. 对比分析
python research-paper-generator/scripts/compare_results.py \
  --baseline experiments/baseline/results.json \
  --enhanced experiments/enhanced/results.json

# 4. 生成论文
python research-paper-generator/scripts/generate_paper.py \
  --comparison experiments/comparison/comparison.json
```

### 3. 编译论文

```bash
cd paper
pdflatex paper.tex
bibtex paper
pdflatex paper.tex
pdflatex paper.tex
```

## 📚 文档

- **[协作者指南](COLLABORATOR_GUIDE.md)** - 团队协作工作流、任务分配
- **[集成指南](jiuwenswarm/docs/INTEGRATION_GUIDE.md)** - 详细的集成说明
- **[模块调用说明](jiuwenswarm/docs/module_call.md)** - API使用文档
- **[系统架构](jiuwenswarm/docs/architecture.md)** - 架构设计文档
- **[创新点详解](jiuwenswarm/docs/innovation.md)** - 技术创新说明

## 🎯 项目状态

### 完成度：100%

- ✅ **第一阶段**（核心实现）：多层次记忆系统、混合检索引擎、团队同步、记忆压缩
- ✅ **第二阶段**（实验验证）：4类任务实验、对比分析、论文撰写
- ✅ **第三阶段**（Agent自动化）：EnhancedMemoryRail集成、系统注册、端到端验证

### 代码统计

```
总代码量: ~2800行

核心模块:
├── multi_level_memory.py           450行
├── retrieval_engine.py             400行
├── team_memory_sync_rail.py        350行
├── memory_compression_tool.py      300行
├── enhanced_memory_rail.py         280行
└── research-paper-generator/       800行

文档: 8个MD文件
测试: 290行
```

## 🤝 如何贡献

我们欢迎任何形式的贡献！详见 **[协作者指南](COLLABORATOR_GUIDE.md)**

### 贡献流程
1. Fork 本项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'feat: Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 👥 团队

- **项目维护者**：[@Mapleyuchen](https://github.com/Mapleyuchen)
- **学校**：同济大学
- **比赛**：CCF BDCI 2026

## 🙏 致谢

- [openJiuwen](https://github.com/openJiuwen-ai/jiuwenswarm) - 提供优秀的多智能体框架
- CCF BDCI 组委会 - 组织精彩的比赛
- 开源社区 - 持续的支持和贡献

## 📞 联系我们

- **GitHub Issues**: [https://github.com/Mapleyuchen/CCF-BDCI/issues](https://github.com/Mapleyuchen/CCF-BDCI/issues)
- **邮箱**: [待填写]

## 🔗 相关链接

- [JiuwenSwarm 官方文档](https://openjiuwen.com/zh/jiuwenswarm)
- [ICLR 2027 论文格式](https://iclr.cc/Conferences/2027/AuthorGuide)
- [CCF BDCI 官网](https://www.datafountain.cn/competitions)

---

**⭐ 如果这个项目对你有帮助，欢迎 Star！**

**最后更新**: 2026年9月24日
