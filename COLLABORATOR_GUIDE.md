# CCF BDCI 2026 项目协作者指南

## 📋 项目概述

**项目名称**：基于JiuwenSwarm的Agent科研论文自动生成系统

**研究主题**：Multi-Level Memory Architecture for Intelligent Agents: A Hybrid Retrieval Approach

**项目目标**：为CCF BDCI 2026比赛开发增强的多层次Agent记忆系统，并自动生成高质量科研论文

**GitHub仓库**：https://github.com/Mapleyuchen/CCF-BDCI.git

---

## 🎯 项目当前状态

### 完成度：100%

| 阶段 | 任务 | 状态 | 负责人 |
|-----|------|------|--------|
| 第一阶段 | 核心源码实现 | ✅ 完成 | - |
| 第二阶段 | 实验验证 | ✅ 完成 | - |
| 第三阶段 | Agent自动化集成 | ✅ 完成 | - |

### 核心成果

- **源码**：~2800行生产级Python代码
- **论文**：完整的ICLR 2027格式论文（5页）
- **实验数据**：4类任务的完整对比实验
- **文档**：完善的技术文档和使用指南

---

## 📁 项目目录结构

```
CCF-BDCI/
├── README.md                          # 项目说明
├── COLLABORATOR_GUIDE.md              # 本文件 - 协作者指南
├── PROJECT_STATUS_AND_NEXT_STEPS.md   # 项目状态和下一步计划
├── PLAN.md                            # 实施计划
├── STAGE2_COMPLETION_REPORT.md        # 第二阶段完成报告
│
├── jiuwenswarm/                       # JiuwenSwarm源码和改进
│   ├── PROJECT_SUMMARY.md             # 项目总结
│   ├── STAGE3_COMPLETION_REPORT.md    # 第三阶段完成报告
│   ├── framework_contribution.md      # 框架贡献说明
│   ├── resource_report.md             # 资源消耗报告
│   ├── 提交说明.md                     # 比赛提交说明
│   │
│   ├── jiuwenswarm/                   # 核心改进模块
│   │   ├── agents/harness/common/
│   │   │   ├── memory/
│   │   │   │   ├── multi_level_memory.py          # 多层次记忆系统 ⭐
│   │   │   │   └── retrieval_engine.py            # 混合检索引擎 ⭐
│   │   │   ├── rails/
│   │   │   │   ├── enhanced_memory_rail.py        # 增强记忆Rail ⭐
│   │   │   │   └── __init__.py                    # Rail注册
│   │   │   └── tools/
│   │   │       └── memory_compression_tool.py     # 记忆压缩工具 ⭐
│   │   ├── agents/harness/team/rails/
│   │   │   └── team_memory_sync_rail.py           # 团队记忆同步 ⭐
│   │   └── agents/swarm/providers/
│   │       └── builtin_rails.py                   # Rail系统注册
│   │
│   ├── research-paper-generator/      # 论文自动生成Skill
│   │   ├── SKILL.md                   # Skill定义
│   │   └── scripts/                   # 自动化脚本
│   │       ├── literature_search.py
│   │       ├── run_baseline_experiments.py
│   │       ├── run_enhanced_experiments.py
│   │       ├── compare_results.py
│   │       └── generate_paper.py
│   │
│   ├── experiments/                   # 实验数据
│   │   ├── baseline/results.json
│   │   ├── enhanced/results.json
│   │   └── comparison/
│   │       ├── comparison.json
│   │       └── results_table.tex
│   │
│   ├── paper/                         # 论文输出
│   │   ├── paper.pdf                  # 最终论文PDF
│   │   ├── paper.tex                  # LaTeX源文件
│   │   └── references.bib             # 参考文献
│   │
│   ├── docs/                          # 技术文档
│   │   ├── architecture.md            # 系统架构
│   │   ├── module_call.md             # 模块调用说明
│   │   ├── innovation.md              # 创新点详解
│   │   ├── IMPLEMENTATION_SUMMARY.md  # 实现总结
│   │   ├── IMPLEMENTATION_REPORT.md   # 实现报告
│   │   └── INTEGRATION_GUIDE.md       # 集成指南
│   │
│   └── tests/                         # 测试代码
│       └── test_multi_level_memory.py
│
└── iclr-2027-style-files/             # ICLR论文模板
    └── iclr2027/
```

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/Mapleyuchen/CCF-BDCI.git
cd CCF-BDCI
```

### 2. 环境配置

**环境要求：**
- Python 3.11+
- Git
- LaTeX（用于编译论文）

**安装JiuwenSwarm：**
```bash
cd jiuwenswarm
pip install -e .

# 或使用国内镜像加速
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**配置API密钥：**
```bash
# 编辑配置文件
nano ~/.jiuwenswarm/config/config.yaml

# 配置示例（使用DeepSeek）
model_name: deepseek-v4-flash
api_base: https://api.deepseek.com
api_key: sk-your-api-key
model_provider: OpenAI
```

### 3. 验证安装

```bash
# 测试多层次记忆系统
python -c "from jiuwenswarm.agents.harness.common.memory.multi_level_memory import MultiLevelMemory; print('✅ 多层次记忆系统加载成功')"

# 测试混合检索引擎
python -c "from jiuwenswarm.agents.harness.common.memory.retrieval_engine import HybridRetrievalEngine; print('✅ 混合检索引擎加载成功')"

# 测试EnhancedMemoryRail
python -c "from jiuwenswarm.agents.harness.common.rails.enhanced_memory_rail import EnhancedMemoryRail; print('✅ EnhancedMemoryRail加载成功')"
```

---

## 👥 协作工作流

### Git工作流

**主分支：**
- `main` - 稳定版本，已完成的工作
- `dev` - 开发分支，新功能开发

**创建功能分支：**
```bash
# 从main创建新分支
git checkout main
git pull origin main
git checkout -b feature/your-feature-name

# 开发完成后
git add .
git commit -m "feat: 描述你的改动"
git push origin feature/your-feature-name

# 然后创建Pull Request
```

**提交信息规范：**
- `feat:` - 新功能
- `fix:` - Bug修复
- `docs:` - 文档更新
- `refactor:` - 代码重构
- `test:` - 测试相关
- `chore:` - 构建/工具链更新

### 代码审查

**审查要点：**
1. 代码质量：是否符合PEP 8规范
2. 功能完整性：是否实现了预期功能
3. 测试覆盖：是否有相应的单元测试
4. 文档完善：是否更新了相关文档
5. 性能影响：是否影响系统性能

**审查流程：**
1. 提交PR后，至少需要1人审查
2. 审查通过后方可合并到dev分支
3. 定期将dev合并到main

---

## 💼 任务分工建议

### 角色1：实验验证工程师
**职责：**
- 运行和验证实验结果
- 收集性能数据
- 进行消融实验
- 生成实验报告

**相关文件：**
- `research-paper-generator/scripts/run_*.py`
- `experiments/`

### 角色2：论文优化专家
**职责：**
- 优化论文写作
- 扩充参考文献
- 改进图表展示
- 提交Stanford Agentic Reviewer

**相关文件：**
- `paper/paper.tex`
- `paper/references.bib`

### 角色3：系统集成开发者
**职责：**
- 完善EnhancedMemoryRail
- 优化检索算法
- 添加新功能
- 编写单元测试

**相关文件：**
- `jiuwenswarm/agents/harness/common/memory/*.py`
- `jiuwenswarm/agents/harness/common/rails/enhanced_memory_rail.py`
- `tests/`

### 角色4：文档维护者
**职责：**
- 更新技术文档
- 编写使用指南
- 准备演示材料
- 整理提交材料

**相关文件：**
- `docs/*.md`
- `README.md`
- `COLLABORATOR_GUIDE.md`

---

## 📝 待完成任务清单

### 高优先级（P0）

- [ ] **提交Stanford Agentic Reviewer**
  - 上传paper.pdf
  - 获取Access Token
  - 目标分数：5.0+
  - 负责人：【待分配】
  - 截止日期：【待定】

- [ ] **验证实验可复现性**
  - 在新环境中运行所有实验脚本
  - 确认结果一致性
  - 记录任何问题
  - 负责人：【待分配】

- [ ] **准备比赛提交材料**
  - 按照提交说明.md组织文件
  - 打包成zip文件
  - 检查完整性
  - 负责人：【待分配】

### 中优先级（P1）

- [ ] **扩充参考文献**
  - 当前：21篇
  - 目标：25-30篇
  - 覆盖Agent记忆、多智能体、检索算法等领域
  - 负责人：【待分配】

- [ ] **优化论文写作**
  - 改进Abstract
  - 完善Related Work
  - 增强Discussion
  - 负责人：【待分配】

- [ ] **添加更多实验**
  - 消融实验
  - 不同参数设置对比
  - 更多baseline对比
  - 负责人：【待分配】

### 低优先级（P2）

- [ ] **准备PR到openJiuwen**
  - 编写贡献说明
  - 准备代码示例
  - 编写CONTRIBUTING.md
  - 负责人：【待分配】

- [ ] **制作演示视频**
  - 系统功能演示
  - 实验过程展示
  - 结果分析讲解
  - 负责人：【待分配】

- [ ] **编写技术博客**
  - 设计思路
  - 实现细节
  - 经验总结
  - 负责人：【待分配】

---

## 🔧 开发指南

### 代码规范

**Python代码风格：**
- 遵循PEP 8规范
- 使用类型注解
- 函数和类需要docstring
- 复杂逻辑需要注释

**示例：**
```python
from typing import List, Optional

def retrieve_memories(
    query: str,
    limit: int = 10,
    importance_threshold: float = 0.5
) -> List[MemoryItem]:
    """检索相关记忆。
    
    Args:
        query: 查询文本
        limit: 返回结果数量上限
        importance_threshold: 重要性阈值
        
    Returns:
        记忆项列表，按相关性排序
        
    Raises:
        ValueError: 如果参数无效
    """
    # 实现...
```

### 测试规范

**单元测试：**
- 使用pytest框架
- 测试文件命名：`test_*.py`
- 测试函数命名：`test_*`
- 覆盖率目标：80%+

**示例：**
```python
import pytest
from jiuwenswarm.agents.harness.common.memory.multi_level_memory import MultiLevelMemory

def test_add_memory():
    """测试添加记忆功能"""
    memory = MultiLevelMemory()
    memory.add_memory("test content", importance=0.8)
    
    stats = memory.get_statistics()
    assert stats['working_memory']['count'] == 1

def test_retrieve_memories():
    """测试检索记忆功能"""
    memory = MultiLevelMemory()
    memory.add_memory("agent memory system", importance=0.8)
    
    results = memory.retrieve_memories("agent", limit=5)
    assert len(results) > 0
```

### 文档规范

**Markdown格式：**
- 使用标题层级（# ## ### ####）
- 代码块使用```标记语言
- 重要信息使用**加粗**或`代码样式`
- 使用表格组织结构化信息

**文档更新：**
- 添加新功能时更新相关文档
- 修改API时更新module_call.md
- 重大变更时更新CHANGELOG.md

---

## 🐛 问题排查

### 常见问题

**问题1：导入模块失败**
```bash
# 错误：ModuleNotFoundError: No module named 'jiuwenswarm'

# 解决：重新安装
cd jiuwenswarm
pip install -e .
```

**问题2：API密钥配置错误**
```bash
# 错误：Authentication failed

# 解决：检查配置文件
cat ~/.jiuwenswarm/config/config.yaml
# 确认api_key正确
```

**问题3：实验脚本运行失败**
```bash
# 错误：FileNotFoundError

# 解决：确认在正确目录
cd jiuwenswarm
python research-paper-generator/scripts/run_baseline_experiments.py
```

**问题4：LaTeX编译失败**
```bash
# 错误：pdflatex: command not found

# 解决：安装LaTeX
# Windows: 安装MiKTeX或TeX Live
# Linux: sudo apt-get install texlive-full
# macOS: brew install --cask mactex
```

### 获取帮助

**文档资源：**
- 项目文档：`docs/` 目录
- 集成指南：`docs/INTEGRATION_GUIDE.md`
- 模块调用：`docs/module_call.md`

**联系方式：**
- GitHub Issues：https://github.com/Mapleyuchen/CCF-BDCI/issues
- 项目维护者：【待填写】
- 邮箱：【待填写】

---

## 📊 性能基准

### 实验结果（当前）

| 任务类型 | 指标 | Baseline | Enhanced | 提升 |
|---------|------|----------|----------|------|
| 单轮对话 | Precision | 95.0% | 97.0% | +2.1% |
| 单轮对话 | Recall | 85.0% | 90.0% | +5.9% |
| 单轮对话 | F1-Score | 89.0% | 93.0% | +4.5% |
| 多步骤 | 完成率 | 90.0% | 100.0% | +11.1% |
| 多步骤 | 连贯性 | 72.9% | 88.3% | +21.1% |
| 跨会话 | 保留率 | 75.0% | 87.0% | +16.0% |
| 跨会话 | 一致性 | 62.0% | 83.0% | +33.9% |
| 团队协作 | 共享效率 | - | 88.0% | - |

**平均性能提升：** 11.82%  
**最大提升：** 33.9%（跨会话一致性）

### 性能优化建议

如果你的实验结果明显偏低，检查：
1. API模型是否是高性能模型（如GPT-4, Claude-Opus）
2. 检索权重配置是否合理
3. 记忆层容量是否足够
4. 是否启用了混合检索

---

## 🎓 学习资源

### JiuwenSwarm相关
- [官方文档](https://openjiuwen.com/zh/jiuwenswarm)
- [GitHub仓库](https://github.com/openJiuwen-ai/jiuwenswarm)
- [Skill Hub](https://swarmskills.openjiuwen.com/)

### Agent记忆系统
- MemGPT论文：[arXiv:2310.08560](https://arxiv.org/abs/2310.08560)
- MemoryBank论文：[arXiv:2305.10250](https://arxiv.org/abs/2305.10250)
- LangChain Memory：[Documentation](https://python.langchain.com/docs/modules/memory/)

### 学术写作
- ICLR投稿指南
- LaTeX使用教程
- 学术英语写作

---

## 📅 项目时间线

### 已完成（2026年9月）

- **9月21日**：第一阶段完成（核心实现）
- **9月23日**：第二阶段完成（实验验证）
- **9月24日**：第三阶段完成（Agent自动化）
- **9月24日**：创建GitHub仓库和协作文档

### 待完成（根据比赛时间调整）

- **Week 1**：实验验证和论文优化
- **Week 2**：提交Stanford Reviewer，准备比赛材料
- **Week 3**：最终检查和提交
- **Week 4+**：准备PR和技术分享

---

## 🤝 贡献指南

### 如何贡献

1. **Fork项目**
2. **创建功能分支** (`git checkout -b feature/AmazingFeature`)
3. **提交更改** (`git commit -m 'Add some AmazingFeature'`)
4. **推送到分支** (`git push origin feature/AmazingFeature`)
5. **开启Pull Request**

### 贡献类型

- 🐛 Bug修复
- ✨ 新功能
- 📝 文档改进
- 🎨 代码优化
- ✅ 测试增强
- 🔧 配置改进

### 贡献者名单

感谢所有贡献者！

- 【项目发起人】
- 【贡献者1】
- 【贡献者2】
- ...

---

## 📜 许可证

本项目遵循 MIT License。

---

## 📞 联系我们

**项目维护者：**
- GitHub: [@Mapleyuchen](https://github.com/Mapleyuchen)
- 邮箱：【待填写】

**团队信息：**
- 团队名称：【待填写】
- 学校：同济大学
- 比赛：CCF BDCI 2026

---

## 🎉 致谢

感谢：
- openJiuwen社区提供的JiuwenSwarm框架
- CCF BDCI组委会组织的精彩比赛
- 所有参考文献的作者
- 开源社区的支持

---

**最后更新：** 2026年9月24日  
**文档版本：** v1.0  
**维护者：** 项目团队

**祝协作愉快！** 🚀
