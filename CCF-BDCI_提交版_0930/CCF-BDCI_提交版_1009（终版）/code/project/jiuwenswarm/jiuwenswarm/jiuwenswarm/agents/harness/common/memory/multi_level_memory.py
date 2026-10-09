# coding: utf-8
# Copyright (c) CCF BDCI 2026. All rights reserved.
"""
Multi-Level Memory Engine for JiuwenSwarm
多层次记忆引擎：实现工作记忆、任务记忆和项目记忆的协同管理

创新点：
1. 三层记忆架构：短期工作记忆 + 中期任务记忆 + 长期项目记忆
2. 智能记忆升级降级机制
3. 记忆重要性评分
4. 自动过期和压缩
"""

from __future__ import annotations
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timedelta
import hashlib


@dataclass
class MemoryItem:
    """记忆项基础数据结构"""
    content: str
    timestamp: float
    importance: float  # 0-1，重要性分数
    access_count: int  # 访问次数
    last_access: float  # 最后访问时间
    memory_type: str  # "working", "task", "project"
    tags: List[str]  # 标签
    metadata: Dict[str, Any]  # 额外元数据

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "MemoryItem":
        return cls(**data)


class WorkingMemory:
    """工作记忆：存储当前对话的短期上下文

    特点：
    - 容量有限（默认最多20条）
    - 快速访问
    - 自动过期（默认1小时）
    """

    def __init__(self, max_size: int = 20, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.memories: List[MemoryItem] = []

    def add(self, content: str, importance: float = 0.5, tags: List[str] = None,
            metadata: Dict = None) -> MemoryItem:
        """添加工作记忆"""
        now = time.time()
        item = MemoryItem(
            content=content,
            timestamp=now,
            importance=importance,
            access_count=0,
            last_access=now,
            memory_type="working",
            tags=tags or [],
            metadata=metadata or {}
        )

        self.memories.append(item)
        self._cleanup()
        return item

    def _cleanup(self):
        """清理过期和超容量的记忆"""
        now = time.time()

        # 移除过期记忆
        self.memories = [m for m in self.memories
                        if now - m.timestamp < self.ttl_seconds]

        # 如果超过容量，移除最旧的低重要性记忆
        if len(self.memories) > self.max_size:
            self.memories.sort(key=lambda x: (x.importance, x.timestamp))
            self.memories = self.memories[-(self.max_size):]

    def get_all(self) -> List[MemoryItem]:
        """获取所有有效的工作记忆"""
        self._cleanup()
        return self.memories.copy()

    def to_dict(self) -> Dict:
        return {
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "memories": [m.to_dict() for m in self.memories]
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WorkingMemory":
        wm = cls(max_size=data["max_size"], ttl_seconds=data["ttl_seconds"])
        wm.memories = [MemoryItem.from_dict(m) for m in data["memories"]]
        return wm


class TaskMemory:
    """任务记忆：存储任务执行历史和经验

    特点：
    - 按任务组织
    - 中等容量（默认最多100条）
    - 保留7天
    """

    def __init__(self, max_size: int = 100, ttl_days: int = 7):
        self.max_size = max_size
        self.ttl_seconds = ttl_days * 86400
        self.memories: Dict[str, List[MemoryItem]] = {}  # task_id -> memories

    def add(self, task_id: str, content: str, importance: float = 0.7,
            tags: List[str] = None, metadata: Dict = None) -> MemoryItem:
        """添加任务记忆"""
        now = time.time()
        item = MemoryItem(
            content=content,
            timestamp=now,
            importance=importance,
            access_count=0,
            last_access=now,
            memory_type="task",
            tags=tags or [],
            metadata=metadata or {"task_id": task_id}
        )

        if task_id not in self.memories:
            self.memories[task_id] = []

        self.memories[task_id].append(item)
        self._cleanup()
        return item

    def _cleanup(self):
        """清理过期记忆"""
        now = time.time()

        # 清理每个任务的过期记忆
        for task_id in list(self.memories.keys()):
            self.memories[task_id] = [
                m for m in self.memories[task_id]
                if now - m.timestamp < self.ttl_seconds
            ]

            # 移除空任务
            if not self.memories[task_id]:
                del self.memories[task_id]

        # 如果总数超过容量，移除最旧的任务
        total = sum(len(mems) for mems in self.memories.values())
        if total > self.max_size:
            all_mems = []
            for task_id, mems in self.memories.items():
                for m in mems:
                    all_mems.append((task_id, m))

            all_mems.sort(key=lambda x: x[1].timestamp)
            to_remove = total - self.max_size

            for task_id, mem in all_mems[:to_remove]:
                self.memories[task_id].remove(mem)
                if not self.memories[task_id]:
                    del self.memories[task_id]

    def get_by_task(self, task_id: str) -> List[MemoryItem]:
        """获取指定任务的记忆"""
        return self.memories.get(task_id, []).copy()

    def get_all(self) -> List[MemoryItem]:
        """获取所有任务记忆"""
        self._cleanup()
        all_mems = []
        for mems in self.memories.values():
            all_mems.extend(mems)
        return all_mems

    def to_dict(self) -> Dict:
        return {
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "memories": {
                task_id: [m.to_dict() for m in mems]
                for task_id, mems in self.memories.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TaskMemory":
        tm = cls(max_size=data["max_size"],
                ttl_days=data["ttl_seconds"] // 86400)
        tm.memories = {
            task_id: [MemoryItem.from_dict(m) for m in mems]
            for task_id, mems in data["memories"].items()
        }
        return tm


class ProjectMemory:
    """项目记忆：存储长期项目知识

    特点：
    - 持久化存储
    - 大容量
    - 高重要性记忆
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.home() / ".jiuwenswarm" / "memory" / "project"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.memories: List[MemoryItem] = []
        self.load()

    def add(self, content: str, importance: float = 0.9,
            tags: List[str] = None, metadata: Dict = None) -> MemoryItem:
        """添加项目记忆"""
        now = time.time()
        item = MemoryItem(
            content=content,
            timestamp=now,
            importance=importance,
            access_count=0,
            last_access=now,
            memory_type="project",
            tags=tags or [],
            metadata=metadata or {}
        )

        self.memories.append(item)
        self.save()
        return item

    def get_all(self) -> List[MemoryItem]:
        """获取所有项目记忆"""
        return self.memories.copy()

    def save(self):
        """持久化到磁盘"""
        data = {
            "memories": [m.to_dict() for m in self.memories],
            "saved_at": time.time()
        }

        save_file = self.storage_path / "project_memory.json"
        with open(save_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self):
        """从磁盘加载"""
        save_file = self.storage_path / "project_memory.json"
        if save_file.exists():
            try:
                with open(save_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.memories = [MemoryItem.from_dict(m)
                               for m in data.get("memories", [])]
            except Exception as e:
                print(f"Failed to load project memory: {e}")
                self.memories = []


class MultiLevelMemory:
    """多层次记忆系统：协调三层记忆的管理

    核心功能：
    1. 统一的记忆添加接口
    2. 智能记忆升级（工作 -> 任务 -> 项目）
    3. 跨层记忆检索
    4. 记忆重要性评估
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.working_memory = WorkingMemory()
        self.task_memory = TaskMemory()
        self.project_memory = ProjectMemory(storage_path)

        # 升级阈值
        self.working_to_task_threshold = 0.7
        self.task_to_project_threshold = 0.85

    def add_memory(self, content: str, importance: float = 0.5,
                   memory_type: str = "auto", task_id: Optional[str] = None,
                   tags: List[str] = None, metadata: Dict = None) -> MemoryItem:
        """智能添加记忆

        Args:
            content: 记忆内容
            importance: 重要性（0-1）
            memory_type: "auto", "working", "task", "project"
            task_id: 任务ID（用于任务记忆）
            tags: 标签列表
            metadata: 元数据
        """

        # 自动选择记忆层级
        if memory_type == "auto":
            if importance >= self.task_to_project_threshold:
                memory_type = "project"
            elif importance >= self.working_to_task_threshold:
                memory_type = "task"
            else:
                memory_type = "working"

        # 添加到对应层级
        if memory_type == "project":
            return self.project_memory.add(content, importance, tags, metadata)
        elif memory_type == "task" and task_id:
            return self.task_memory.add(task_id, content, importance, tags, metadata)
        else:
            return self.working_memory.add(content, importance, tags, metadata)

    def promote_memory(self, item: MemoryItem, target_level: str,
                      task_id: Optional[str] = None):
        """升级记忆到更高层级

        Args:
            item: 要升级的记忆项
            target_level: 目标层级 "task" 或 "project"
            task_id: 任务ID（升级到task时需要）
        """
        if target_level == "task" and item.memory_type == "working":
            if task_id:
                self.task_memory.add(
                    task_id, item.content, item.importance,
                    item.tags, item.metadata
                )
        elif target_level == "project" and item.memory_type in ["working", "task"]:
            self.project_memory.add(
                item.content, item.importance,
                item.tags, item.metadata
            )

    def retrieve_memories(self, query: str = None, importance_threshold: float = 0.0,
                         memory_types: List[str] = None,
                         limit: int = 10) -> List[MemoryItem]:
        """跨层检索记忆

        Args:
            query: 查询文本（暂时使用简单匹配，后续可改为语义检索）
            importance_threshold: 重要性阈值
            memory_types: 要检索的记忆类型列表
            limit: 返回数量限制

        Returns:
            按相关性排序的记忆列表
        """
        memory_types = memory_types or ["working", "task", "project"]

        all_memories = []

        if "working" in memory_types:
            all_memories.extend(self.working_memory.get_all())
        if "task" in memory_types:
            all_memories.extend(self.task_memory.get_all())
        if "project" in memory_types:
            all_memories.extend(self.project_memory.get_all())

        # 过滤重要性
        filtered = [m for m in all_memories if m.importance >= importance_threshold]

        # 简单的文本匹配（后续可升级为语义检索）
        if query:
            scored = []
            query_lower = query.lower()
            for mem in filtered:
                content_lower = mem.content.lower()
                if query_lower in content_lower:
                    # 计算相关性分数
                    score = self._calculate_relevance_score(mem, query)
                    scored.append((score, mem))

            scored.sort(reverse=True, key=lambda x: x[0])
            result = [mem for score, mem in scored[:limit]]
        else:
            # 按重要性和时间排序
            filtered.sort(key=lambda x: (x.importance, x.timestamp), reverse=True)
            result = filtered[:limit]

        # 更新访问统计
        now = time.time()
        for mem in result:
            mem.access_count += 1
            mem.last_access = now

        return result

    def _calculate_relevance_score(self, memory: MemoryItem, query: str) -> float:
        """计算记忆与查询的相关性分数

        综合考虑：
        1. 文本匹配程度
        2. 重要性
        3. 时间衰减
        4. 访问频率
        """
        now = time.time()

        # 文本匹配分数（简单实现）
        query_lower = query.lower()
        content_lower = memory.content.lower()
        match_score = query_lower.count(content_lower) / len(query_lower) if query_lower else 0

        # 重要性权重
        importance_score = memory.importance

        # 时间衰减（指数衰减，半衰期为7天）
        days_old = (now - memory.timestamp) / 86400
        time_decay = 0.5 ** (days_old / 7)

        # 访问频率加成
        access_boost = min(memory.access_count * 0.1, 0.5)

        # 综合分数
        score = (match_score * 0.4 +
                importance_score * 0.3 +
                time_decay * 0.2 +
                access_boost * 0.1)

        return score

    def get_statistics(self) -> Dict:
        """获取记忆系统统计信息"""
        return {
            "working_memory": {
                "count": len(self.working_memory.get_all()),
                "max_size": self.working_memory.max_size
            },
            "task_memory": {
                "count": len(self.task_memory.get_all()),
                "tasks": len(self.task_memory.memories),
                "max_size": self.task_memory.max_size
            },
            "project_memory": {
                "count": len(self.project_memory.get_all())
            }
        }

    def save_all(self):
        """保存所有记忆"""
        self.project_memory.save()

        # 保存工作记忆和任务记忆到临时存储
        temp_path = Path.home() / ".jiuwenswarm" / "memory" / "temp"
        temp_path.mkdir(parents=True, exist_ok=True)

        with open(temp_path / "working_memory.json", "w", encoding="utf-8") as f:
            json.dump(self.working_memory.to_dict(), f, ensure_ascii=False, indent=2)

        with open(temp_path / "task_memory.json", "w", encoding="utf-8") as f:
            json.dump(self.task_memory.to_dict(), f, ensure_ascii=False, indent=2)

    def load_all(self):
        """加载所有记忆"""
        self.project_memory.load()

        temp_path = Path.home() / ".jiuwenswarm" / "memory" / "temp"

        # 加载工作记忆
        wm_file = temp_path / "working_memory.json"
        if wm_file.exists():
            try:
                with open(wm_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.working_memory = WorkingMemory.from_dict(data)
            except Exception as e:
                print(f"Failed to load working memory: {e}")

        # 加载任务记忆
        tm_file = temp_path / "task_memory.json"
        if tm_file.exists():
            try:
                with open(tm_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.task_memory = TaskMemory.from_dict(data)
            except Exception as e:
                print(f"Failed to load task memory: {e}")


__all__ = [
    "MemoryItem",
    "WorkingMemory",
    "TaskMemory",
    "ProjectMemory",
    "MultiLevelMemory"
]
