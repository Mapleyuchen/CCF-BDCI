# coding: utf-8
# Copyright (c) CCF BDCI 2026. All rights reserved.
"""
Memory Compression Tool for JiuwenSwarm
记忆压缩工具：自动识别冗余信息并进行层次化压缩

创新点：
1. 智能识别冗余和重复信息
2. 层次化摘要生成
3. 增量压缩策略
4. 保留关键信息
"""

from typing import List, Dict, Any, Optional, Tuple
import hashlib
import re
from collections import Counter


class MemoryCompressor:
    """记忆压缩器

    功能：
    1. 识别相似和重复的记忆
    2. 生成摘要
    3. 合并冗余信息
    """

    def __init__(self, similarity_threshold: float = 0.8):
        """
        Args:
            similarity_threshold: 相似度阈值，超过此值视为重复
        """
        self.similarity_threshold = similarity_threshold

    def compress_memories(self, memories: List[Dict]) -> Tuple[List[Dict], Dict]:
        """压缩记忆列表

        Args:
            memories: 记忆列表，每个记忆应包含 "content" 字段

        Returns:
            (compressed_memories, stats) 压缩后的记忆和统计信息
        """
        if not memories:
            return [], {"original_count": 0, "compressed_count": 0, "compression_ratio": 0}

        # 1. 识别重复记忆
        duplicates = self._find_duplicates(memories)

        # 2. 识别相似记忆
        similar_groups = self._find_similar_groups(memories)

        # 3. 压缩处理
        compressed = []
        removed_indices = set()

        # 移除完全重复的
        for indices in duplicates.values():
            # 保留第一个，移除其他
            for idx in indices[1:]:
                removed_indices.add(idx)

        # 合并相似的
        for group in similar_groups:
            if len(group) > 1:
                # 生成摘要
                summary = self._generate_summary([memories[i] for i in group])
                compressed.append({
                    "content": summary,
                    "compressed_from": len(group),
                    "original_indices": group,
                    "type": "compressed"
                })
                # 标记这些记忆已处理
                removed_indices.update(group)

        # 添加未被压缩的记忆
        for i, memory in enumerate(memories):
            if i not in removed_indices:
                compressed.append(memory)

        # 统计信息
        stats = {
            "original_count": len(memories),
            "compressed_count": len(compressed),
            "compression_ratio": len(compressed) / len(memories) if memories else 0,
            "duplicates_removed": len(removed_indices),
            "groups_merged": len(similar_groups)
        }

        return compressed, stats

    def _find_duplicates(self, memories: List[Dict]) -> Dict[str, List[int]]:
        """识别完全重复的记忆

        Returns:
            {content_hash: [indices]} 内容哈希到索引列表的映射
        """
        hash_to_indices = {}

        for i, memory in enumerate(memories):
            content = memory.get("content", "")
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

            if content_hash not in hash_to_indices:
                hash_to_indices[content_hash] = []
            hash_to_indices[content_hash].append(i)

        # 只返回有重复的
        duplicates = {h: indices for h, indices in hash_to_indices.items()
                     if len(indices) > 1}

        return duplicates

    def _find_similar_groups(self, memories: List[Dict]) -> List[List[int]]:
        """识别相似的记忆组

        使用简单的文本相似度算法
        """
        groups = []
        processed = set()

        for i, mem1 in enumerate(memories):
            if i in processed:
                continue

            group = [i]
            content1 = mem1.get("content", "")

            for j, mem2 in enumerate(memories[i+1:], start=i+1):
                if j in processed:
                    continue

                content2 = mem2.get("content", "")
                similarity = self._calculate_similarity(content1, content2)

                if similarity >= self.similarity_threshold:
                    group.append(j)
                    processed.add(j)

            if len(group) > 1:
                groups.append(group)
                processed.add(i)

        return groups

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度（Jaccard相似度）"""
        if not text1 or not text2:
            return 0.0

        # 分词
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        # Jaccard相似度
        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _generate_summary(self, memories: List[Dict]) -> str:
        """生成一组记忆的摘要

        策略：
        1. 提取关键词
        2. 保留最重要的信息
        3. 生成简洁的总结
        """
        contents = [m.get("content", "") for m in memories]

        # 提取所有词汇
        all_words = []
        for content in contents:
            words = content.split()
            all_words.extend(words)

        # 词频统计
        word_freq = Counter(all_words)

        # 提取高频关键词（前5个）
        top_keywords = [word for word, freq in word_freq.most_common(5)]

        # 生成摘要：保留包含关键词最多的句子
        best_sentence = ""
        max_keyword_count = 0

        for content in contents:
            sentences = re.split(r'[。！？\.!?]', content)
            for sentence in sentences:
                keyword_count = sum(1 for kw in top_keywords if kw in sentence)
                if keyword_count > max_keyword_count:
                    max_keyword_count = keyword_count
                    best_sentence = sentence

        # 构建摘要
        summary = f"[摘要] {best_sentence.strip()}"
        if len(contents) > 1:
            summary += f" (合并了{len(contents)}条相似记忆)"

        return summary

    def compress_to_levels(self, memories: List[Dict],
                          levels: int = 3) -> List[List[Dict]]:
        """分层压缩记忆

        Args:
            memories: 原始记忆列表
            levels: 压缩层级数

        Returns:
            每层的压缩结果 [level1, level2, level3]
        """
        result = [memories]

        current_memories = memories
        for level in range(1, levels):
            # 逐层压缩
            compressed, stats = self.compress_memories(current_memories)

            # 如果压缩率太低，停止
            if stats["compression_ratio"] > 0.9:
                break

            result.append(compressed)
            current_memories = compressed

        return result


class IncrementalCompressor:
    """增量压缩器

    支持在新增记忆时进行增量压缩，避免每次都全量压缩
    """

    def __init__(self, base_compressor: Optional[MemoryCompressor] = None):
        self.compressor = base_compressor or MemoryCompressor()
        self.last_compressed_count = 0
        self.compression_buffer: List[Dict] = []

    def add_memory(self, memory: Dict):
        """添加新记忆到缓冲区"""
        self.compression_buffer.append(memory)

    def should_compress(self, threshold: int = 10) -> bool:
        """判断是否应该执行压缩

        当缓冲区记忆数量超过阈值时触发压缩
        """
        return len(self.compression_buffer) >= threshold

    def compress_incremental(self) -> Tuple[List[Dict], Dict]:
        """执行增量压缩"""
        if not self.compression_buffer:
            return [], {"compressed": 0}

        compressed, stats = self.compressor.compress_memories(self.compression_buffer)

        # 清空缓冲区
        self.compression_buffer = []
        self.last_compressed_count = len(compressed)

        return compressed, stats

    def get_buffer_size(self) -> int:
        """获取缓冲区大小"""
        return len(self.compression_buffer)


def demonstrate_compression():
    """演示记忆压缩功能"""
    print("=== Memory Compression Demo ===\n")

    # 示例记忆
    memories = [
        {"content": "Agent使用多层次记忆架构来管理信息", "importance": 0.8},
        {"content": "Agent使用多层次记忆架构来管理信息", "importance": 0.8},  # 重复
        {"content": "多层次记忆架构帮助Agent更好地管理信息", "importance": 0.7},  # 相似
        {"content": "记忆系统包括工作记忆、任务记忆和项目记忆三层", "importance": 0.9},
        {"content": "工作记忆存储短期上下文信息", "importance": 0.6},
        {"content": "任务记忆保存任务执行历史", "importance": 0.7},
        {"content": "项目记忆用于长期知识存储", "importance": 0.8},
        {"content": "短期上下文信息保存在工作记忆中", "importance": 0.6},  # 相似
    ]

    compressor = MemoryCompressor(similarity_threshold=0.6)

    print(f"原始记忆数量: {len(memories)}\n")

    compressed, stats = compressor.compress_memories(memories)

    print(f"压缩后记忆数量: {len(compressed)}")
    print(f"压缩率: {stats['compression_ratio']:.2%}")
    print(f"移除重复: {stats['duplicates_removed']} 条")
    print(f"合并分组: {stats['groups_merged']} 组\n")

    print("压缩后的记忆:")
    for i, mem in enumerate(compressed, 1):
        content = mem.get("content", "")
        if len(content) > 60:
            content = content[:60] + "..."
        print(f"{i}. {content}")
        if mem.get("type") == "compressed":
            print(f"   (合并自 {mem['compressed_from']} 条记忆)")


if __name__ == "__main__":
    demonstrate_compression()


__all__ = [
    "MemoryCompressor",
    "IncrementalCompressor"
]
