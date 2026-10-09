# coding: utf-8
# Copyright (c) CCF BDCI 2026. All rights reserved.
"""
Team Memory Sync Rail for JiuwenSwarm
团队记忆同步Rail：支持多Agent间的记忆共享和同步

创新点：
1. 多Agent记忆共享机制
2. 记忆冲突检测和解决
3. 记忆权限控制
4. 增量同步优化性能
"""

from __future__ import annotations
import time
import json
from typing import TYPE_CHECKING, Dict, List, Optional, Any, Set
from pathlib import Path

from openjiuwen.core.single_agent.rail.base import AgentCallbackContext
from openjiuwen.harness.rails.base import DeepAgentRail

from jiuwenswarm.common.utils import logger

if TYPE_CHECKING:
    from openjiuwen.harness.deep_agent import DeepAgent


class TeamMemoryStore:
    """团队记忆存储

    管理团队共享的记忆数据
    """

    def __init__(self, team_id: str, storage_path: Optional[Path] = None):
        self.team_id = team_id
        self.storage_path = storage_path or (
            Path.home() / ".jiuwenswarm" / "memory" / "team" / team_id
        )
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.memories: Dict[str, Any] = {}  # memory_id -> memory_data
        self.member_contributions: Dict[str, List[str]] = {}  # agent_id -> [memory_ids]
        self.last_sync_time: Dict[str, float] = {}  # agent_id -> timestamp

        self.load()

    def add_memory(self, agent_id: str, memory_id: str, memory_data: Dict) -> bool:
        """添加记忆"""
        try:
            # 添加元数据
            memory_data["contributor"] = agent_id
            memory_data["created_at"] = time.time()
            memory_data["memory_id"] = memory_id

            self.memories[memory_id] = memory_data

            # 记录贡献者
            if agent_id not in self.member_contributions:
                self.member_contributions[agent_id] = []
            self.member_contributions[agent_id].append(memory_id)

            self.save()
            return True

        except Exception as e:
            logger.error(f"[TeamMemoryStore] Failed to add memory: {e}")
            return False

    def get_memories(self, agent_id: Optional[str] = None,
                    since: Optional[float] = None) -> List[Dict]:
        """获取记忆

        Args:
            agent_id: 指定Agent ID，返回该Agent可访问的记忆
            since: 时间戳，返回该时间之后的记忆（增量同步）
        """
        result = []

        for memory_id, memory_data in self.memories.items():
            # 时间过滤
            if since and memory_data.get("created_at", 0) <= since:
                continue

            # 权限检查（这里简化处理，实际可以更复杂）
            if agent_id and not self._check_permission(agent_id, memory_data):
                continue

            result.append(memory_data)

        return result

    def _check_permission(self, agent_id: str, memory_data: Dict) -> bool:
        """检查访问权限"""
        # 简化实现：所有团队成员都可以访问
        # 未来可以支持更细粒度的权限控制
        return True

    def update_sync_time(self, agent_id: str):
        """更新同步时间"""
        self.last_sync_time[agent_id] = time.time()

    def get_last_sync_time(self, agent_id: str) -> float:
        """获取上次同步时间"""
        return self.last_sync_time.get(agent_id, 0.0)

    def detect_conflicts(self, memory_id: str, new_data: Dict) -> Optional[Dict]:
        """检测记忆冲突

        Returns:
            如果有冲突，返回冲突信息；否则返回None
        """
        if memory_id not in self.memories:
            return None

        existing = self.memories[memory_id]

        # 检查内容是否不同
        if existing.get("content") != new_data.get("content"):
            return {
                "memory_id": memory_id,
                "existing_contributor": existing.get("contributor"),
                "new_contributor": new_data.get("contributor"),
                "existing_content": existing.get("content"),
                "new_content": new_data.get("content"),
                "conflict_type": "content_mismatch"
            }

        return None

    def resolve_conflict(self, conflict: Dict, strategy: str = "keep_latest") -> bool:
        """解决记忆冲突

        Args:
            conflict: 冲突信息
            strategy: 解决策略
                - "keep_latest": 保留最新的
                - "keep_existing": 保留现有的
                - "merge": 合并（简单拼接）
        """
        memory_id = conflict["memory_id"]

        try:
            if strategy == "keep_latest":
                # 保留新的（已经在add_memory中处理）
                pass

            elif strategy == "keep_existing":
                # 不做任何操作
                pass

            elif strategy == "merge":
                # 合并内容
                existing = self.memories[memory_id]
                new_content = conflict["new_content"]
                merged_content = f"{existing['content']}\n[Updated]: {new_content}"
                existing["content"] = merged_content
                existing["updated_at"] = time.time()
                self.save()

            return True

        except Exception as e:
            logger.error(f"[TeamMemoryStore] Failed to resolve conflict: {e}")
            return False

    def save(self):
        """持久化到磁盘"""
        data = {
            "team_id": self.team_id,
            "memories": self.memories,
            "member_contributions": self.member_contributions,
            "last_sync_time": self.last_sync_time,
            "saved_at": time.time()
        }

        save_file = self.storage_path / "team_memory.json"
        with open(save_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self):
        """从磁盘加载"""
        save_file = self.storage_path / "team_memory.json"
        if save_file.exists():
            try:
                with open(save_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self.memories = data.get("memories", {})
                self.member_contributions = data.get("member_contributions", {})
                self.last_sync_time = data.get("last_sync_time", {})

            except Exception as e:
                logger.error(f"[TeamMemoryStore] Failed to load: {e}")

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            "team_id": self.team_id,
            "total_memories": len(self.memories),
            "active_members": len(self.member_contributions),
            "storage_path": str(self.storage_path)
        }


class TeamMemorySyncRail(DeepAgentRail):
    """团队记忆同步Rail

    功能：
    1. 在团队任务开始前同步团队记忆到各Agent
    2. 在任务执行过程中收集新产生的记忆
    3. 在任务结束后将记忆同步回团队存储
    4. 处理记忆冲突
    """

    def __init__(self, team_id: str, agent_id: str,
                 sync_strategy: str = "incremental",
                 conflict_resolution: str = "keep_latest"):
        """
        Args:
            team_id: 团队ID
            agent_id: 当前Agent的ID
            sync_strategy: 同步策略 "full" 或 "incremental"
            conflict_resolution: 冲突解决策略
        """
        super().__init__()
        self.team_id = team_id
        self.agent_id = agent_id
        self.sync_strategy = sync_strategy
        self.conflict_resolution = conflict_resolution

        self.team_store = TeamMemoryStore(team_id)
        self.local_memories: List[Dict] = []  # 本地新增的记忆
        self.synced_memory_ids: Set[str] = set()  # 已同步的记忆ID

    def init(self, agent: "DeepAgent") -> None:
        """初始化时同步团队记忆"""
        logger.info(
            f"[TeamMemorySyncRail] Initializing for team={self.team_id}, agent={self.agent_id}"
        )

        # 执行初始同步
        self._sync_from_team()

    def uninit(self, agent: "DeepAgent") -> None:
        """卸载时同步本地记忆到团队"""
        logger.info(
            f"[TeamMemorySyncRail] Uninitializing, syncing local memories to team"
        )

        self._sync_to_team()

    async def before_model_call(self, ctx: AgentCallbackContext) -> None:
        """模型调用前：确保有最新的团队记忆"""
        if self.sync_strategy == "incremental":
            # 增量同步：只获取上次同步后的新记忆
            self._sync_from_team(incremental=True)

    async def after_model_call(self, ctx: AgentCallbackContext) -> None:
        """模型调用后：收集新产生的记忆"""
        # 这里可以从context中提取新的记忆
        # 实际实现需要与memory系统集成
        pass

    def _sync_from_team(self, incremental: bool = False):
        """从团队存储同步记忆到本地

        Args:
            incremental: 是否增量同步
        """
        try:
            if incremental:
                # 增量同步：只获取上次同步后的记忆
                last_sync = self.team_store.get_last_sync_time(self.agent_id)
                new_memories = self.team_store.get_memories(
                    agent_id=self.agent_id,
                    since=last_sync
                )
                logger.info(
                    f"[TeamMemorySyncRail] Incremental sync: {len(new_memories)} new memories"
                )
            else:
                # 全量同步
                new_memories = self.team_store.get_memories(agent_id=self.agent_id)
                logger.info(
                    f"[TeamMemorySyncRail] Full sync: {len(new_memories)} memories"
                )

            # 记录已同步的记忆ID
            for mem in new_memories:
                self.synced_memory_ids.add(mem["memory_id"])

            # 更新同步时间
            self.team_store.update_sync_time(self.agent_id)

        except Exception as e:
            logger.error(f"[TeamMemorySyncRail] Sync from team failed: {e}")

    def _sync_to_team(self):
        """将本地记忆同步到团队存储"""
        try:
            synced_count = 0
            conflict_count = 0

            for memory in self.local_memories:
                memory_id = memory.get("memory_id")
                if not memory_id:
                    continue

                # 检测冲突
                conflict = self.team_store.detect_conflicts(memory_id, memory)

                if conflict:
                    logger.warning(
                        f"[TeamMemorySyncRail] Conflict detected for memory {memory_id}"
                    )
                    # 解决冲突
                    self.team_store.resolve_conflict(conflict, self.conflict_resolution)
                    conflict_count += 1

                # 添加到团队存储
                success = self.team_store.add_memory(self.agent_id, memory_id, memory)
                if success:
                    synced_count += 1

            logger.info(
                f"[TeamMemorySyncRail] Synced {synced_count} memories, "
                f"resolved {conflict_count} conflicts"
            )

        except Exception as e:
            logger.error(f"[TeamMemorySyncRail] Sync to team failed: {e}")

    def add_local_memory(self, memory_id: str, memory_data: Dict):
        """添加本地记忆（待同步）"""
        memory_data["memory_id"] = memory_id
        self.local_memories.append(memory_data)

    def get_team_statistics(self) -> Dict:
        """获取团队记忆统计"""
        return self.team_store.get_statistics()


__all__ = [
    "TeamMemoryStore",
    "TeamMemorySyncRail"
]
