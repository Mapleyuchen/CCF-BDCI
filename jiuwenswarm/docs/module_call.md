# 模块调用说明

## 概述

本文档详细说明了增强记忆系统各模块的调用方式和集成方法。

## 1. 多层次记忆系统调用

### 1.1 基本使用

```python
from jiuwenswarm.agents.harness.common.memory.multi_level_memory import MultiLevelMemory

# 创建多层次记忆系统
memory_system = MultiLevelMemory()

# 添加记忆（自动选择层级）
memory_system.add_memory(
    content="用户询问了关于Agent记忆系统的问题",
    importance=0.8,  # 重要性评分
    tags=["query", "memory_system"],
    metadata={"session_id": "session_001"}
)

# 指定层级添加
memory_system.add_memory(
    content="完成了文档生成任务",
    importance=0.9,
    memory_type="task",  # 明确指定为任务记忆
    task_id="task_001"
)

# 检索记忆
results = memory_system.retrieve_memories(
    query="Agent记忆",
    importance_threshold=0.5,
    memory_types=["working", "task", "project"],
    limit=10
)

# 打印检索结果
for memory in results:
    print(f"内容: {memory.content}")
    print(f"重要性: {memory.importance}")
    print(f"类型: {memory.memory_type}")
```

### 1.2 记忆升级

```python
# 将重要的工作记忆升级到任务记忆
working_memory_item = memory_system.working_memory.get_all()[0]
memory_system.promote_memory(
    item=working_memory_item,
    target_level="task",
    task_id="task_001"
)

# 将关键任务记忆升级到项目记忆
task_memory_item = memory_system.task_memory.get_all()[0]
memory_system.promote_memory(
    item=task_memory_item,
    target_level="project"
)
```

### 1.3 持久化

```python
# 保存所有记忆
memory_system.save_all()

# 加载记忆
memory_system.load_all()

# 获取统计信息
stats = memory_system.get_statistics()
print(f"工作记忆: {stats['working_memory']['count']} 条")
print(f"任务记忆: {stats['task_memory']['count']} 条")
print(f"项目记忆: {stats['project_memory']['count']} 条")
```

## 2. 混合检索引擎调用

### 2.1 基本检索

```python
from jiuwenswarm.agents.harness.common.memory.retrieval_engine import (
    HybridRetrievalEngine,
    RetrievalConfig
)

# 创建配置
config = RetrievalConfig(
    semantic_weight=0.4,
    temporal_weight=0.3,
    frequency_weight=0.2,
    importance_weight=0.1,
    top_k=10
)

# 创建检索引擎
engine = HybridRetrievalEngine(config)

# 执行检索
memories = memory_system.working_memory.get_all()
results = engine.retrieve(
    query="Agent记忆管理",
    memories=memories
)

# 处理结果
for score, memory in results:
    print(f"分数: {score:.4f}, 内容: {memory.content[:50]}...")
```

### 2.2 动态调整权重

```python
# 调整检索权重
engine.update_config(
    semantic_weight=0.5,  # 提高语义相似度权重
    temporal_weight=0.2   # 降低时间衰减权重
)

# 重新检索
results = engine.retrieve(query="...", memories=memories)
```

### 2.3 缓存管理

```python
# 清空缓存
engine.clear_cache()

# 获取统计信息
stats = engine.get_statistics()
print(f"缓存大小: {stats['cache']['size']}")
print(f"使用向量检索: {stats['use_vector']}")
```

## 3. 团队记忆同步调用

### 3.1 注册Rail到Agent

```python
from jiuwenswarm.agents.harness.team.rails.team_memory_sync_rail import TeamMemorySyncRail

# 创建团队记忆同步Rail
team_sync_rail = TeamMemorySyncRail(
    team_id="research_team_01",
    agent_id="agent_001",
    sync_strategy="incremental",  # 增量同步
    conflict_resolution="keep_latest"  # 冲突解决策略
)

# 注册到DeepAgent
agent.register_rail(team_sync_rail)
```

### 3.2 手动同步

```python
# 从团队存储同步
team_sync_rail._sync_from_team(incremental=True)

# 同步到团队存储
team_sync_rail._sync_to_team()

# 添加本地记忆（待同步）
team_sync_rail.add_local_memory(
    memory_id="mem_001",
    memory_data={
        "content": "团队发现了新的优化方法",
        "importance": 0.9
    }
)
```

### 3.3 获取团队统计

```python
stats = team_sync_rail.get_team_statistics()
print(f"团队ID: {stats['team_id']}")
print(f"总记忆数: {stats['total_memories']}")
print(f"活跃成员: {stats['active_members']}")
```

## 4. 记忆压缩工具调用

### 4.1 基本压缩

```python
from jiuwenswarm.agents.harness.common.tools.memory_compression_tool import (
    MemoryCompressor
)

# 创建压缩器
compressor = MemoryCompressor(similarity_threshold=0.8)

# 压缩记忆
memories = [
    {"content": "Agent使用多层次记忆架构", "importance": 0.8},
    {"content": "Agent使用多层次记忆架构", "importance": 0.8},  # 重复
    {"content": "多层次记忆架构很有用", "importance": 0.7},  # 相似
]

compressed, stats = compressor.compress_memories(memories)

print(f"原始: {stats['original_count']} 条")
print(f"压缩后: {stats['compressed_count']} 条")
print(f"压缩率: {stats['compression_ratio']:.2%}")
```

### 4.2 分层压缩

```python
# 生成多层压缩
levels = compressor.compress_to_levels(memories, levels=3)

for i, level in enumerate(levels):
    print(f"层级 {i}: {len(level)} 条记忆")
```

### 4.3 增量压缩

```python
from jiuwenswarm.agents.harness.common.tools.memory_compression_tool import (
    IncrementalCompressor
)

# 创建增量压缩器
inc_compressor = IncrementalCompressor()

# 添加记忆到缓冲区
inc_compressor.add_memory({"content": "...", "importance": 0.8})
inc_compressor.add_memory({"content": "...", "importance": 0.7})

# 检查是否需要压缩
if inc_compressor.should_compress(threshold=10):
    compressed, stats = inc_compressor.compress_incremental()
```

## 5. 集成到JiuwenSwarm

### 5.1 在Skill中使用

```python
# 在Skill的SKILL.md中
"""
执行步骤：
1. 初始化多层次记忆系统
2. 执行任务并记录重要信息
3. 使用混合检索查找相关记忆
4. 基于记忆生成回答
"""

# 在Skill的脚本中
from jiuwenswarm.agents.harness.common.memory.multi_level_memory import MultiLevelMemory

def execute_skill():
    # 初始化记忆系统
    memory = MultiLevelMemory()
    
    # 执行任务
    task_result = perform_task()
    
    # 记录重要信息
    memory.add_memory(
        content=f"任务执行结果: {task_result}",
        importance=0.85,
        memory_type="task",
        task_id=current_task_id
    )
    
    # 检索相关记忆
    relevant_memories = memory.retrieve_memories(
        query="任务执行",
        importance_threshold=0.7
    )
    
    return format_response(relevant_memories)
```

### 5.2 在Agent中使用

```python
from openjiuwen.harness.deep_agent import DeepAgent
from jiuwenswarm.agents.harness.common.memory.multi_level_memory import MultiLevelMemory

class EnhancedAgent(DeepAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 初始化多层次记忆
        self.memory = MultiLevelMemory()
        
    async def process_message(self, message: str):
        # 检索相关记忆
        relevant_memories = self.memory.retrieve_memories(
            query=message,
            limit=5
        )
        
        # 构建上下文
        context = self._build_context(relevant_memories)
        
        # 生成回复
        response = await self.generate_response(message, context)
        
        # 记录交互
        self.memory.add_memory(
            content=f"Q: {message}\nA: {response}",
            importance=0.6
        )
        
        return response
```

### 5.3 配置文件集成

```yaml
# config.yaml
memory:
  multi_level:
    enabled: true
    working_memory:
      max_size: 20
      ttl_seconds: 3600
    task_memory:
      max_size: 100
      ttl_days: 7
    project_memory:
      storage_path: ~/.jiuwenswarm/memory/project
  
  retrieval:
    semantic_weight: 0.4
    temporal_weight: 0.3
    frequency_weight: 0.2
    importance_weight: 0.1
    cache_enabled: true
    cache_ttl_seconds: 300
  
  team_sync:
    enabled: true
    sync_strategy: incremental
    conflict_resolution: keep_latest
```

## 6. 性能优化建议

### 6.1 批量操作

```python
# 批量添加记忆
memories_to_add = [
    {"content": "...", "importance": 0.8},
    {"content": "...", "importance": 0.7},
    # ...
]

for mem_data in memories_to_add:
    memory_system.add_memory(**mem_data)

# 批量压缩后添加
compressed, _ = compressor.compress_memories(memories_to_add)
for mem in compressed:
    memory_system.add_memory(**mem)
```

### 6.2 异步操作

```python
import asyncio

async def async_retrieve(memory_system, queries):
    tasks = [
        asyncio.to_thread(
            memory_system.retrieve_memories,
            query=q
        )
        for q in queries
    ]
    results = await asyncio.gather(*tasks)
    return results

# 使用
queries = ["查询1", "查询2", "查询3"]
results = asyncio.run(async_retrieve(memory_system, queries))
```

### 6.3 定期维护

```python
import schedule
import time

def maintenance_job():
    # 清理过期记忆
    memory_system.working_memory._cleanup()
    memory_system.task_memory._cleanup()
    
    # 压缩冗余记忆
    all_memories = memory_system.working_memory.get_all()
    compressed, _ = compressor.compress_memories(all_memories)
    
    # 保存到磁盘
    memory_system.save_all()
    
    print("维护完成")

# 每小时执行一次
schedule.every().hour.do(maintenance_job)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## 7. 故障排查

### 7.1 常见问题

**问题1**: 记忆检索为空
```python
# 检查记忆数量
stats = memory_system.get_statistics()
print(stats)

# 降低重要性阈值
results = memory_system.retrieve_memories(
    query="...",
    importance_threshold=0.0  # 降低阈值
)
```

**问题2**: 同步冲突频繁
```python
# 更改冲突解决策略
team_sync_rail.conflict_resolution = "merge"  # 改为合并策略

# 增加同步间隔
team_sync_rail.sync_interval = 600  # 10分钟
```

**问题3**: 内存占用过高
```python
# 减少各层容量
memory_system.working_memory.max_size = 10  # 从20减到10
memory_system.task_memory.max_size = 50     # 从100减到50

# 定期压缩
compressor.compress_memories(memory_system.working_memory.get_all())
```

### 7.2 调试模式

```python
import logging

# 启用详细日志
logging.basicConfig(level=logging.DEBUG)

# 记忆系统会输出详细操作日志
memory_system.add_memory(content="测试", importance=0.5)
# DEBUG: Adding memory to working layer
# DEBUG: Current working memory size: 1/20
```

## 8. API参考

### 8.1 MultiLevelMemory

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|--------|------|
| `add_memory()` | content, importance, memory_type, task_id, tags, metadata | MemoryItem | 添加记忆 |
| `retrieve_memories()` | query, importance_threshold, memory_types, limit | List[MemoryItem] | 检索记忆 |
| `promote_memory()` | item, target_level, task_id | None | 升级记忆 |
| `get_statistics()` | - | Dict | 获取统计信息 |
| `save_all()` | - | None | 保存所有记忆 |
| `load_all()` | - | None | 加载所有记忆 |

### 8.2 HybridRetrievalEngine

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|--------|------|
| `retrieve()` | query, memories, memory_accessor | List[Tuple[float, Any]] | 执行检索 |
| `update_config()` | **kwargs | None | 更新配置 |
| `clear_cache()` | - | None | 清空缓存 |
| `get_statistics()` | - | Dict | 获取统计信息 |

### 8.3 TeamMemorySyncRail

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|--------|------|
| `add_local_memory()` | memory_id, memory_data | None | 添加本地记忆 |
| `get_team_statistics()` | - | Dict | 获取团队统计 |

### 8.4 MemoryCompressor

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|--------|------|
| `compress_memories()` | memories | Tuple[List[Dict], Dict] | 压缩记忆 |
| `compress_to_levels()` | memories, levels | List[List[Dict]] | 分层压缩 |

---

**文档版本**: v1.0  
**更新日期**: 2026年9月21日
