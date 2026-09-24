# coding: utf-8
# Copyright (c) CCF BDCI 2026. All rights reserved.
"""
Hybrid Retrieval Engine for Multi-Level Memory
混合检索引擎：结合语义相似度、时间衰减和访问频率的智能检索

创新点：
1. 多维度混合检索策略
2. 动态权重调整
3. 缓存机制提高性能
4. 支持向量化语义检索（可选）
"""

from __future__ import annotations
import time
import hashlib
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
import math

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


@dataclass
class RetrievalConfig:
    """检索配置"""
    # 权重配置
    semantic_weight: float = 0.4  # 语义相似度权重
    temporal_weight: float = 0.3  # 时间衰减权重
    frequency_weight: float = 0.2  # 访问频率权重
    importance_weight: float = 0.1  # 重要性权重

    # 时间衰减配置
    time_decay_halflife_days: float = 7.0  # 半衰期（天）

    # 检索参数
    top_k: int = 10  # 返回top-k结果
    min_score: float = 0.1  # 最小分数阈值

    # 缓存配置
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300  # 缓存有效期5分钟


class RetrievalCache:
    """检索结果缓存"""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Tuple[float, Any]] = {}  # query_hash -> (timestamp, result)

    def get(self, query: str) -> Optional[Any]:
        """获取缓存结果"""
        query_hash = self._hash_query(query)
        if query_hash in self.cache:
            timestamp, result = self.cache[query_hash]
            if time.time() - timestamp < self.ttl_seconds:
                return result
            else:
                del self.cache[query_hash]
        return None

    def put(self, query: str, result: Any):
        """存入缓存"""
        query_hash = self._hash_query(query)
        self.cache[query_hash] = (time.time(), result)

    def clear(self):
        """清空缓存"""
        self.cache.clear()

    def _hash_query(self, query: str) -> str:
        """计算查询的哈希值"""
        return hashlib.md5(query.encode('utf-8')).hexdigest()


class HybridRetrievalEngine:
    """混合检索引擎

    结合多种检索策略：
    1. 语义相似度：基于文本匹配或向量相似度
    2. 时间衰减：越新的记忆权重越高
    3. 访问频率：经常访问的记忆权重越高
    4. 重要性：高重要性记忆优先
    """

    def __init__(self, config: Optional[RetrievalConfig] = None):
        self.config = config or RetrievalConfig()
        self.cache = RetrievalCache(self.config.cache_ttl_seconds)

        # 向量化相似度计算（可选）
        self.use_vector = False
        self.embeddings_cache: Dict[str, Any] = {}

    def retrieve(self, query: str, memories: List[Any],
                memory_accessor: Optional[Dict] = None) -> List[Tuple[float, Any]]:
        """执行混合检索

        Args:
            query: 查询文本
            memories: 记忆列表（MemoryItem对象）
            memory_accessor: 记忆属性访问器，格式:
                {
                    "content": lambda m: m.content,
                    "timestamp": lambda m: m.timestamp,
                    "access_count": lambda m: m.access_count,
                    "importance": lambda m: m.importance
                }

        Returns:
            [(score, memory), ...] 按分数降序排列
        """
        # 检查缓存
        if self.config.cache_enabled:
            cached = self.cache.get(query)
            if cached is not None:
                return cached

        # 默认访问器（假设是MemoryItem对象）
        if memory_accessor is None:
            memory_accessor = {
                "content": lambda m: m.content,
                "timestamp": lambda m: m.timestamp,
                "access_count": lambda m: m.access_count,
                "importance": lambda m: m.importance
            }

        scored_memories = []
        now = time.time()

        for memory in memories:
            # 计算各维度分数
            semantic_score = self._calculate_semantic_score(
                query, memory_accessor["content"](memory)
            )
            temporal_score = self._calculate_temporal_score(
                now, memory_accessor["timestamp"](memory)
            )
            frequency_score = self._calculate_frequency_score(
                memory_accessor["access_count"](memory)
            )
            importance_score = memory_accessor["importance"](memory)

            # 加权综合分数
            total_score = (
                semantic_score * self.config.semantic_weight +
                temporal_score * self.config.temporal_weight +
                frequency_score * self.config.frequency_weight +
                importance_score * self.config.importance_weight
            )

            if total_score >= self.config.min_score:
                scored_memories.append((total_score, memory))

        # 排序并取top-k
        scored_memories.sort(reverse=True, key=lambda x: x[0])
        result = scored_memories[:self.config.top_k]

        # 缓存结果
        if self.config.cache_enabled:
            self.cache.put(query, result)

        return result

    def _calculate_semantic_score(self, query: str, content: str) -> float:
        """计算语义相似度分数

        当前实现：基于简单的文本匹配
        未来可以升级为：向量相似度计算（使用embedding模型）
        """
        if not query or not content:
            return 0.0

        query_lower = query.lower()
        content_lower = content.lower()

        # 方法1：完全包含
        if query_lower in content_lower:
            return 1.0

        # 方法2：词汇重叠度
        query_words = set(query_lower.split())
        content_words = set(content_lower.split())

        if not query_words:
            return 0.0

        overlap = len(query_words & content_words)
        score = overlap / len(query_words)

        return score

    def _calculate_temporal_score(self, now: float, timestamp: float) -> float:
        """计算时间衰减分数

        使用指数衰减：score = 0.5 ^ (days_old / halflife)
        """
        days_old = (now - timestamp) / 86400.0
        halflife = self.config.time_decay_halflife_days

        if days_old < 0:
            days_old = 0

        # 指数衰减
        score = 0.5 ** (days_old / halflife)

        return score

    def _calculate_frequency_score(self, access_count: int) -> float:
        """计算访问频率分数

        使用对数增长避免过度奖励高频访问：score = log(1 + access_count) / log(101)
        """
        if access_count < 0:
            access_count = 0

        # 对数归一化到[0, 1]
        score = math.log(1 + access_count) / math.log(101)  # log(101) ≈ 2

        return min(score, 1.0)

    def update_config(self, **kwargs):
        """动态更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()

    def get_statistics(self) -> Dict[str, Any]:
        """获取检索引擎统计信息"""
        return {
            "config": {
                "semantic_weight": self.config.semantic_weight,
                "temporal_weight": self.config.temporal_weight,
                "frequency_weight": self.config.frequency_weight,
                "importance_weight": self.config.importance_weight,
            },
            "cache": {
                "enabled": self.config.cache_enabled,
                "size": len(self.cache.cache),
                "ttl_seconds": self.cache.ttl_seconds
            },
            "use_vector": self.use_vector
        }


class SemanticRetriever:
    """语义检索器（可选，需要embedding模型）

    支持向量化语义检索，提供更精确的相似度计算
    """

    def __init__(self, embedding_model: Optional[Any] = None):
        self.embedding_model = embedding_model
        self.embeddings_cache: Dict[str, Any] = {}

    def encode(self, text: str) -> Optional[Any]:
        """将文本编码为向量"""
        if self.embedding_model is None:
            return None

        # 检查缓存
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        if text_hash in self.embeddings_cache:
            return self.embeddings_cache[text_hash]

        try:
            # 调用embedding模型
            embedding = self.embedding_model.encode(text)
            self.embeddings_cache[text_hash] = embedding
            return embedding
        except Exception as e:
            print(f"Encoding failed: {e}")
            return None

    def calculate_similarity(self, query_embedding: Any,
                           memory_embedding: Any) -> float:
        """计算向量相似度（余弦相似度）"""
        if query_embedding is None or memory_embedding is None:
            return 0.0

        if not HAS_NUMPY:
            return 0.0

        try:
            # 余弦相似度
            query_vec = np.array(query_embedding)
            memory_vec = np.array(memory_embedding)

            dot_product = np.dot(query_vec, memory_vec)
            norm_query = np.linalg.norm(query_vec)
            norm_memory = np.linalg.norm(memory_vec)

            if norm_query == 0 or norm_memory == 0:
                return 0.0

            similarity = dot_product / (norm_query * norm_memory)

            # 归一化到[0, 1]
            return (similarity + 1) / 2

        except Exception as e:
            print(f"Similarity calculation failed: {e}")
            return 0.0

    def retrieve_by_vector(self, query: str, memories: List[Any],
                          content_accessor) -> List[Tuple[float, Any]]:
        """基于向量相似度检索"""
        query_embedding = self.encode(query)
        if query_embedding is None:
            return []

        scored_memories = []

        for memory in memories:
            content = content_accessor(memory)
            memory_embedding = self.encode(content)

            if memory_embedding is not None:
                similarity = self.calculate_similarity(query_embedding, memory_embedding)
                scored_memories.append((similarity, memory))

        scored_memories.sort(reverse=True, key=lambda x: x[0])
        return scored_memories


__all__ = [
    "RetrievalConfig",
    "HybridRetrievalEngine",
    "SemanticRetriever",
    "RetrievalCache"
]
