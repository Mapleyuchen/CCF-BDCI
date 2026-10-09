"""
Memory Compression Tool for Multi-Level Memory System

Implements automatic memory compression and summarization to:
- Identify redundant information
- Generate hierarchical summaries
- Support incremental compression
- Reduce storage overhead while preserving essential information

Author: CCF BDCI 2026 Team
Date: 2026-09-23
License: MIT
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from jiuwenswarm.agents.harness.common.memory.multi_level_memory import MemoryItem


@dataclass
class CompressionResult:
    """Result of memory compression operation"""
    original_count: int
    compressed_count: int
    compression_ratio: float
    summaries: List[str]
    removed_keys: List[str]


class MemoryCompressionTool:
    """
    Tool for compressing and summarizing memory content

    Uses clustering and summarization to reduce redundancy
    while maintaining information quality.
    """

    def __init__(self,
                 similarity_threshold: float = 0.7,
                 min_cluster_size: int = 2):
        """
        Initialize compression tool

        Args:
            similarity_threshold: Minimum similarity to cluster memories
            min_cluster_size: Minimum items required to form cluster
        """
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size

        # Statistics
        self.compression_count = 0
        self.total_items_compressed = 0
        self.total_summaries_generated = 0

    def compress_memories(self,
                         memories: List[Tuple[str, MemoryItem]]) -> CompressionResult:
        """
        Compress a list of memory items

        Args:
            memories: List of (key, MemoryItem) tuples

        Returns:
            CompressionResult with statistics
        """
        if not memories:
            return CompressionResult(0, 0, 1.0, [], [])

        original_count = len(memories)

        # Step 1: Cluster similar memories
        clusters = self._cluster_memories(memories)

        # Step 2: Generate summaries for each cluster
        summaries = []
        removed_keys = []
        compressed_memories = []

        for cluster in clusters:
            if len(cluster) >= self.min_cluster_size:
                # Generate summary for cluster
                summary = self._summarize_cluster(cluster)
                summaries.append(summary)

                # Mark items for removal (keep first, remove rest)
                for i, (key, _) in enumerate(cluster):
                    if i > 0:  # Keep first item, remove others
                        removed_keys.append(key)
                    else:
                        compressed_memories.append((key, cluster[i][1]))
            else:
                # Keep small clusters as-is
                compressed_memories.extend(cluster)

        compressed_count = len(compressed_memories)
        compression_ratio = compressed_count / original_count if original_count > 0 else 1.0

        # Update statistics
        self.compression_count += 1
        self.total_items_compressed += (original_count - compressed_count)
        self.total_summaries_generated += len(summaries)

        return CompressionResult(
            original_count=original_count,
            compressed_count=compressed_count,
            compression_ratio=compression_ratio,
            summaries=summaries,
            removed_keys=removed_keys
        )

    def _cluster_memories(self,
                         memories: List[Tuple[str, MemoryItem]]) -> List[List[Tuple[str, MemoryItem]]]:
        """
        Cluster similar memories using simple similarity-based grouping

        Returns:
            List of clusters, where each cluster is a list of (key, MemoryItem)
        """
        clusters = []
        used = set()

        for i, (key1, item1) in enumerate(memories):
            if key1 in used:
                continue

            cluster = [(key1, item1)]
            used.add(key1)

            # Find similar items
            for j, (key2, item2) in enumerate(memories):
                if i != j and key2 not in used:
                    similarity = self._calculate_similarity(
                        item1.content,
                        item2.content
                    )

                    if similarity >= self.similarity_threshold:
                        cluster.append((key2, item2))
                        used.add(key2)

            clusters.append(cluster)

        return clusters

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate Jaccard similarity between two texts

        Returns:
            Similarity score between 0.0 and 1.0
        """
        tokens1 = set(self._tokenize(text1.lower()))
        tokens2 = set(self._tokenize(text2.lower()))

        if not tokens1 or not tokens2:
            return 0.0

        intersection = tokens1 & tokens2
        union = tokens1 | tokens2

        return len(intersection) / len(union) if union else 0.0

    def _summarize_cluster(self, cluster: List[Tuple[str, MemoryItem]]) -> str:
        """
        Generate summary for a cluster of similar memories

        Simple implementation: extract common keywords and create summary
        """
        # Extract all content
        contents = [item.content for _, item in cluster]

        # Count word frequencies
        word_freq = defaultdict(int)
        for content in contents:
            tokens = self._tokenize(content.lower())
            for token in set(tokens):  # Count unique words per content
                word_freq[token] += 1

        # Get most common words
        common_words = sorted(
            word_freq.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        # Create summary
        keywords = [word for word, _ in common_words]
        summary = (
            f"Cluster of {len(cluster)} similar memories "
            f"about: {', '.join(keywords)}"
        )

        return summary

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenize text into words"""
        tokens = re.findall(r'\w+', text)
        return [t for t in tokens if len(t) > 2]  # Filter short tokens

    def generate_hierarchical_summary(self,
                                     memories: List[MemoryItem],
                                     levels: int = 2) -> List[str]:
        """
        Generate multi-level hierarchical summary

        Args:
            memories: List of memory items
            levels: Number of summary levels (1-3)

        Returns:
            List of summaries at different abstraction levels
        """
        if not memories:
            return []

        summaries = []

        # Level 1: Category-based summary
        categories = defaultdict(list)
        for item in memories:
            layer = item.layer
            categories[layer].append(item)

        level1_summary = []
        for layer, items in categories.items():
            level1_summary.append(
                f"{layer.capitalize()} layer: {len(items)} memories"
            )
        summaries.append(" | ".join(level1_summary))

        if levels >= 2:
            # Level 2: Content-based summary
            all_content = " ".join(m.content for m in memories)
            tokens = self._tokenize(all_content.lower())
            word_freq = defaultdict(int)
            for token in tokens:
                word_freq[token] += 1

            top_keywords = sorted(
                word_freq.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]

            level2_summary = "Key topics: " + ", ".join(
                word for word, _ in top_keywords
            )
            summaries.append(level2_summary)

        if levels >= 3:
            # Level 3: Statistical summary
            avg_importance = sum(m.importance for m in memories) / len(memories)
            avg_access = sum(m.access_count for m in memories) / len(memories)

            level3_summary = (
                f"Statistics: {len(memories)} total memories, "
                f"avg importance {avg_importance:.2f}, "
                f"avg access count {avg_access:.1f}"
            )
            summaries.append(level3_summary)

        return summaries

    def identify_redundancy(self,
                           memories: List[Tuple[str, MemoryItem]]) -> List[List[str]]:
        """
        Identify groups of redundant memories

        Returns:
            List of redundancy groups (each group is list of keys)
        """
        clusters = self._cluster_memories(memories)

        redundancy_groups = []
        for cluster in clusters:
            if len(cluster) >= self.min_cluster_size:
                keys = [key for key, _ in cluster]
                redundancy_groups.append(keys)

        return redundancy_groups

    def get_statistics(self) -> Dict:
        """Get compression tool statistics"""
        return {
            'compression_count': self.compression_count,
            'total_items_compressed': self.total_items_compressed,
            'total_summaries_generated': self.total_summaries_generated,
            'similarity_threshold': self.similarity_threshold,
            'min_cluster_size': self.min_cluster_size
        }
