# 系统架构设计文档

## 概述

本文档详细描述了基于JiuwenSwarm的多层次Agent记忆引擎增强系统的架构设计。

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     JiuwenSwarm Agent                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │          Multi-Level Memory System                  │    │
│  │                                                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │    │
│  │  │   Working    │  │    Task      │  │ Project  │ │    │
│  │  │   Memory     │  │   Memory     │  │  Memory  │ │    │
│  │  │  (L1 Cache)  │  │  (L2 Cache)  │  │  (L3 DB) │ │    │
│  │  │              │  │              │  │          │ │    │
│  │  │  Max: 20     │  │  Max: 100    │  │ Unlimited│ │    │
│  │  │  TTL: 1h     │  │  TTL: 7d     │  │Persistent│ │    │
│  │  └──────────────┘  └──────────────┘  └──────────┘ │    │
│  │            │              │                │        │    │
│  │            └──────────────┴────────────────┘        │    │
│  │                          │                          │    │
│  │            ┌─────────────▼─────────────┐            │    │
│  │            │  Hybrid Retrieval Engine  │            │    │
│  │            │                           │            │    │
│  │            │  • Semantic Similarity    │            │    │
│  │            │  • Temporal Decay         │            │    │
│  │            │  • Access Frequency       │            │    │
│  │            │  • Importance Score       │            │    │
│  │            └───────────────────────────┘            │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │        Team Memory Synchronization                  │    │
│  │                                                      │    │
│  │    Agent A ←→ Team Store ←→ Agent B                │    │
│  │                    ↕                                 │    │
│  │                 Agent C                              │    │
│  │                                                      │    │
│  │  Features:                                          │    │
│  │  • Incremental Sync                                 │    │
│  │  • Conflict Detection                               │    │
│  │  • Resolution Strategies                            │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Memory Compression Tool                      │    │
│  │                                                      │    │
│  │  • Duplicate Detection                              │    │
│  │  • Similarity Grouping                              │    │
│  │  • Summary Generation                               │    │
│  │  • Hierarchical Compression                         │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 核心组件详解

### 1. 多层次记忆系统 (Multi-Level Memory System)

#### 1.1 工作记忆 (Working Memory - L1)
**目的**: 存储当前对话的短期上下文

**特性**:
- 容量: 20条记忆
- TTL: 1小时
- 存储: 内存（快速访问）
- 策略: LRU淘汰

**数据结构**:
```python
class WorkingMemory:
    memories: List[MemoryItem]  # 记忆列表
    max_size: int = 20           # 最大容量
    ttl_seconds: int = 3600      # 过期时间
```

**使用场景**:
- 多轮对话上下文
- 临时变量存储
- 快速信息访问

#### 1.2 任务记忆 (Task Memory - L2)
**目的**: 存储任务执行历史和经验

**特性**:
- 容量: 100条记忆
- TTL: 7天
- 存储: 按任务ID组织
- 策略: 基于时间和重要性淘汰

**数据结构**:
```python
class TaskMemory:
    memories: Dict[str, List[MemoryItem]]  # task_id -> memories
    max_size: int = 100
    ttl_seconds: int = 7 * 86400
```

**使用场景**:
- 多步骤任务执行
- 任务经验积累
- 错误恢复

#### 1.3 项目记忆 (Project Memory - L3)
**目的**: 存储长期项目知识

**特性**:
- 容量: 无限制
- TTL: 永久（手动清理）
- 存储: 磁盘持久化
- 策略: 按重要性组织

**数据结构**:
```python
class ProjectMemory:
    memories: List[MemoryItem]
    storage_path: Path  # 持久化路径
```

**使用场景**:
- 跨会话知识保留
- 项目文档和规范
- 领域专业知识

### 2. 混合检索引擎 (Hybrid Retrieval Engine)

#### 2.1 检索评分公式

```
Score(m, q) = w_s × S_semantic(m, q) 
            + w_t × S_temporal(m)
            + w_f × S_frequency(m)
            + w_i × S_importance(m)
```

其中:
- w_s, w_t, w_f, w_i 是权重，满足 Σw = 1
- 默认权重: w_s=0.4, w_t=0.3, w_f=0.2, w_i=0.1

#### 2.2 各维度评分算法

**语义相似度 (Semantic Similarity)**:
```python
# 基于Jaccard系数
S_semantic = |query_words ∩ memory_words| / |query_words|

# 可升级为向量相似度
S_semantic = cosine_similarity(embedding(query), embedding(memory))
```

**时间衰减 (Temporal Decay)**:
```python
# 指数衰减
S_temporal = 0.5 ^ (days_old / halflife)

# 默认半衰期: 7天
```

**访问频率 (Access Frequency)**:
```python
# 对数归一化
S_frequency = log(1 + access_count) / log(101)
```

**重要性评分 (Importance Score)**:
```python
# 直接使用预设重要性值
S_importance = memory.importance  # ∈ [0, 1]
```

#### 2.3 缓存机制

**目的**: 减少重复检索开销

**实现**:
```python
class RetrievalCache:
    cache: Dict[str, Tuple[float, Any]]  # query_hash -> (timestamp, result)
    ttl_seconds: int = 300  # 5分钟缓存
```

**策略**:
- 基于查询哈希缓存
- TTL过期自动清理
- 支持手动清空

### 3. 团队记忆同步 (Team Memory Synchronization)

#### 3.1 同步协议

**增量同步**:
```
1. Agent请求同步，提供last_sync_time
2. TeamStore返回自last_sync_time后的新记忆
3. Agent本地合并
4. Agent上传本地新记忆
5. 更新同步时间戳
```

**全量同步**:
```
1. Agent请求全部记忆
2. TeamStore返回完整记忆集
3. Agent本地替换
```

#### 3.2 冲突检测与解决

**冲突类型**:
- 内容不一致: 同一memory_id的内容不同
- 时间冲突: 本地和远程更新时间不一致

**解决策略**:
1. **keep_latest**: 保留最新的
2. **keep_existing**: 保留现有的
3. **merge**: 合并内容（拼接）

**实现**:
```python
def resolve_conflict(conflict, strategy):
    if strategy == "keep_latest":
        # 用新内容覆盖
        pass
    elif strategy == "merge":
        # 合并内容
        merged = existing + "\n[Updated]: " + new
```

#### 3.3 权限控制

**访问控制**:
- 团队成员可读所有记忆
- 只能修改自己贡献的记忆
- Leader可管理全部记忆

### 4. 记忆压缩工具 (Memory Compression Tool)

#### 4.1 压缩流程

```
1. 识别重复记忆（基于内容哈希）
2. 识别相似记忆（Jaccard相似度>阈值）
3. 分组相似记忆
4. 生成摘要
5. 替换原记忆
```

#### 4.2 摘要生成算法

```python
def generate_summary(memories):
    # 1. 提取高频关键词
    keywords = extract_top_keywords(memories, top_k=5)
    
    # 2. 选择包含最多关键词的句子
    best_sentence = select_best_sentence(memories, keywords)
    
    # 3. 生成摘要
    summary = f"[摘要] {best_sentence} (合并了{len(memories)}条)"
    
    return summary
```

#### 4.3 增量压缩

**目的**: 避免频繁全量压缩

**实现**:
```python
class IncrementalCompressor:
    buffer: List[MemoryItem]  # 缓冲区
    threshold: int = 10        # 触发阈值
    
    def should_compress():
        return len(buffer) >= threshold
```

## 数据流图

### 记忆添加流程

```
User Input
    ↓
[判断重要性]
    ↓
重要性 < 0.7? ────Yes───→ WorkingMemory (L1)
    │
    No
    ↓
重要性 < 0.85? ───Yes───→ TaskMemory (L2)
    │
    No
    ↓
ProjectMemory (L3)
```

### 记忆检索流程

```
Query
    ↓
[检查缓存] ───Hit───→ 返回缓存结果
    │
    Miss
    ↓
[收集候选记忆]
    │
    ├─ WorkingMemory.get_all()
    ├─ TaskMemory.get_all()
    └─ ProjectMemory.get_all()
    ↓
[混合检索评分]
    │
    ├─ 计算语义相似度
    ├─ 计算时间衰减
    ├─ 计算访问频率
    └─ 计算重要性
    ↓
[排序并返回Top-K]
    ↓
[更新访问统计]
    ↓
[缓存结果]
    ↓
返回检索结果
```

### 团队同步流程

```
Agent A (修改记忆)
    ↓
[本地记忆更新]
    ↓
[触发同步]
    ↓
[连接TeamStore]
    ↓
[检测冲突] ───有冲突───→ [解决冲突]
    │                        ↓
    无冲突               [应用解决策略]
    ↓                        ↓
[上传记忆] ←─────────────┘
    ↓
[更新同步时间]
    ↓
通知其他Agent
    ↓
Agent B, C (拉取更新)
```

## 性能优化

### 1. 缓存策略
- 检索结果缓存（5分钟TTL）
- Embedding缓存（永久）
- 查询哈希去重

### 2. 索引优化
- 按时间戳索引
- 按重要性索引
- 按任务ID索引

### 3. 并发控制
- 读写锁分离
- 异步持久化
- 批量操作

## 可扩展性

### 1. 向量检索升级路径
```python
# 当前: 文本匹配
S_semantic = jaccard_similarity(query, memory)

# 升级: 向量检索
embeddings = embed_model.encode([query] + memories)
S_semantic = cosine_similarity(embeddings[0], embeddings[1:])
```

### 2. 分布式存储支持
```python
# 当前: 本地文件系统
storage = LocalFileStorage(path)

# 升级: 分布式数据库
storage = DistributedStorage(
    backend="redis",  # 或 "mongodb", "postgresql"
    cluster_config={...}
)
```

### 3. 自适应权重学习
```python
# 当前: 固定权重
weights = {"semantic": 0.4, "temporal": 0.3, ...}

# 升级: 学习权重
weights = learn_weights(
    training_data=query_result_pairs,
    method="gradient_descent"
)
```

## 安全性考虑

### 1. 数据隔离
- 用户级别隔离
- 团队级别隔离
- 项目级别隔离

### 2. 访问控制
- 读权限控制
- 写权限控制
- 删除权限控制

### 3. 数据加密
- 敏感信息加密存储
- 传输层加密
- 密钥管理

## 监控与日志

### 1. 性能监控
- 检索延迟
- 缓存命中率
- 同步频率

### 2. 质量监控
- 检索准确率
- 压缩率
- 冲突频率

### 3. 日志记录
- 操作日志
- 错误日志
- 审计日志

---

**文档版本**: v1.0  
**更新日期**: 2026年9月21日  
**作者**: CCF BDCI团队
