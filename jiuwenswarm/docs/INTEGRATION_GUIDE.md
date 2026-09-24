# 增强记忆系统集成指南

## 概述

本指南详细说明如何将增强的多层次记忆系统集成到JiuwenSwarm Agent中。

## 快速开始

### 方式一：通过配置文件（推荐）

编辑 `~/.jiuwenswarm/config/config.yaml`:

```yaml
agent:
  workspace: ~/.jiuwenswarm/workspace
  
  # 启用增强记忆Rail
  rails:
    - type: swarm.enhanced_memory
      params:
        workspace: ~/.jiuwenswarm/memory
        enable_hybrid_retrieval: true
        enable_team_sync: false
        max_context_items: 10
```

### 方式二：代码集成

```python
from openjiuwen.harness.deep_agent import DeepAgent
from jiuwenswarm.agents.harness.common.rails.enhanced_memory_rail import (
    EnhancedMemoryRail
)

# 创建Agent
agent = DeepAgent(
    model="gpt-4",
    workspace="/path/to/workspace"
)

# 注册增强记忆Rail
memory_rail = EnhancedMemoryRail(
    workspace=agent.workspace,
    enable_hybrid_retrieval=True,
    enable_team_sync=False,
    max_context_items=10
)

agent.register_rail(memory_rail)
```

## 配置参数

### EnhancedMemoryRail参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `workspace` | str | 必需 | 工作目录路径 |
| `enable_hybrid_retrieval` | bool | True | 启用混合检索引擎 |
| `enable_team_sync` | bool | False | 启用团队记忆同步 |
| `retrieval_weights` | RetrievalWeights | None | 自定义检索权重 |
| `max_context_items` | int | 10 | 每次注入的最大记忆数 |

### 自定义检索权重

```python
from jiuwenswarm.agents.harness.common.memory.retrieval_engine import (
    RetrievalWeights
)

# 自定义权重
custom_weights = RetrievalWeights(
    semantic=0.5,    # 语义相似度权重
    temporal=0.2,    # 时间衰减权重
    frequency=0.2,   # 访问频率权重
    importance=0.1   # 重要性权重
)

memory_rail = EnhancedMemoryRail(
    workspace=workspace,
    retrieval_weights=custom_weights
)
```

## 工作原理

### 1. 记忆存储（after_model_call）

每次模型调用后，Rail会自动：

1. 提取用户消息和助手回复
2. 计算重要性分数
3. 存储到适当的记忆层
4. 持久化到磁盘

### 2. 记忆检索（before_model_call）

每次模型调用前，Rail会自动：

1. 分析当前用户查询
2. 使用混合检索算法查找相关记忆
3. 格式化为上下文
4. 注入到系统提示

### 3. 记忆层级

- **L1 Working Memory**: 最近20条，1小时TTL
- **L2 Task Memory**: 最近100条，7天TTL
- **L3 Project Memory**: 无限容量，持久化

## 与现有系统的关系

### 与ProjectMemoryRail共存

两个Rail可以同时使用：

```yaml
rails:
  # 静态项目文档
  - type: project_memory
    params:
      workspace: ~/.jiuwenswarm/workspace
  
  # 动态对话记忆
  - type: swarm.enhanced_memory
    params:
      workspace: ~/.jiuwenswarm/memory
```

**区别：**
- **ProjectMemoryRail**: 加载静态文档（JIUWENSWARM.md, rules/*.md）
- **EnhancedMemoryRail**: 管理动态对话历史和任务经验

### 优先级

EnhancedMemoryRail的优先级略高：
```python
SECTION_PRIORITY = SystemPromptPriority.PROJECT_MEMORY + 1
```

这确保动态记忆在静态文档之后注入。

## 使用场景

### 场景1：长对话上下文管理

```python
# Agent自动记住之前的对话
user: "请帮我分析这个数据集"
assistant: "好的，我会分析..."

# 几轮对话后
user: "刚才那个数据集的结论是什么？"
# EnhancedMemoryRail自动检索相关记忆并回答
```

### 场景2：跨会话任务连续性

```python
# 第一个会话
user: "我正在做一个机器学习项目"
assistant: "了解，请告诉我更多细节..."

# 第二个会话（几天后）
user: "继续我的机器学习项目"
# L3 Project Memory保留了项目信息
assistant: "好的，您之前提到的机器学习项目..."
```

### 场景3：团队协作记忆共享

```yaml
# 启用团队同步
rails:
  - type: swarm.enhanced_memory
    params:
      enable_team_sync: true
      team_id: "research_team_01"
```

```python
# Agent A的发现会同步到Agent B
# 支持多Agent协作场景
```

## 性能优化

### 1. 缓存设置

混合检索引擎自动缓存结果（5分钟TTL）：

```python
# 缓存会自动管理，无需手动配置
# 相同查询在5分钟内会复用缓存结果
```

### 2. 批量操作

```python
# Rail自动批量处理记忆
# 减少磁盘I/O次数
```

### 3. 异步持久化

```python
# cleanup时统一保存
# 避免每次都写磁盘
```

## 故障排查

### 问题1：记忆未注入

**检查：**
```python
# 确认Rail已注册
agent.rails  # 应该包含EnhancedMemoryRail

# 查看日志
# [EnhancedMemoryRail] Injected N memories into system prompt
```

**解决：**
- 确认`enable_hybrid_retrieval=True`
- 检查`max_context_items`设置
- 验证记忆系统已初始化

### 问题2：检索结果不相关

**调整权重：**
```python
# 提高语义相似度权重
custom_weights = RetrievalWeights(
    semantic=0.6,    # 提高
    temporal=0.2,
    frequency=0.1,
    importance=0.1
)
```

### 问题3：内存占用过高

**减少容量：**
```python
# 修改 multi_level_memory.py
DEFAULT_WORKING_CAPACITY = 10  # 从20减少
DEFAULT_TASK_CAPACITY = 50     # 从100减少
```

## 监控和日志

### 启用详细日志

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 查看Rail操作
# [EnhancedMemoryRail] Initialized with...
# [EnhancedMemoryRail] Injected N memories...
# [EnhancedMemoryRail] Stored memory with importance=...
```

### 查看统计信息

```python
# 通过内存系统查询
from jiuwenswarm.agents.harness.common.memory.multi_level_memory import MultiLevelMemory

memory = MultiLevelMemory()
stats = memory.get_statistics()

print(f"工作记忆: {stats['working_memory']['count']}")
print(f"任务记忆: {stats['task_memory']['count']}")
print(f"项目记忆: {stats['project_memory']['count']}")
```

## 最佳实践

### 1. 合理设置max_context_items

```python
# 根据模型上下文窗口调整
max_context_items=5   # 较小模型（如gpt-3.5）
max_context_items=10  # 中等模型（如gpt-4）
max_context_items=20  # 大模型（如claude-opus）
```

### 2. 定期维护记忆

```python
# 可选：定期清理过期记忆
# Rail的cleanup方法会自动保存
# 但可以添加额外的维护逻辑
```

### 3. 团队协作场景

```python
# 为每个团队使用独立的team_id
rails:
  - type: swarm.enhanced_memory
    params:
      enable_team_sync: true
      team_id: "team_research"  # 研究团队
      
  - type: swarm.enhanced_memory
    params:
      enable_team_sync: true
      team_id: "team_development"  # 开发团队
```

## API参考

### EnhancedMemoryRail

```python
class EnhancedMemoryRail(DeepAgentRail):
    def __init__(
        self,
        workspace: str,
        *,
        enable_hybrid_retrieval: bool = True,
        enable_team_sync: bool = False,
        retrieval_weights: Optional[RetrievalWeights] = None,
        max_context_items: int = 10,
    ) -> None:
        """初始化增强记忆Rail"""
    
    def init(self, agent: "DeepAgent") -> None:
        """Rail注册时初始化"""
    
    def before_model_call(self, context: AgentCallbackContext) -> None:
        """模型调用前注入记忆"""
    
    def after_model_call(self, context: AgentCallbackContext) -> None:
        """模型调用后存储记忆"""
    
    def cleanup(self, agent: "DeepAgent") -> None:
        """清理时保存记忆"""
```

## 示例项目

完整示例见：
- `research-paper-generator/` - 论文生成Skill
- `experiments/` - 实验脚本和结果

---

**文档版本**: v1.0  
**更新日期**: 2026年9月24日  
**作者**: CCF BDCI 2026 Team
