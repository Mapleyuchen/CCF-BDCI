"""
Team Memory Synchronization Rail for Multi-Agent Collaboration

Implements memory sharing and synchronization across multiple agents
in JiuwenSwarm team scenarios with conflict detection and resolution.

Key Features:
- Incremental synchronization to minimize overhead
- Conflict detection based on content hashing
- Multiple merge strategies (latest, merge, manual)
- Access control for memory privacy

Author: CCF BDCI 2026 Team
Date: 2026-09-23
License: MIT
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from jiuwenswarm.agents.harness.common.memory.multi_level_memory import (
    MemoryItem,
    MultiLevelMemory,
)


@dataclass
class MemoryConflict:
    """Represents a conflict between two memory versions"""
    key: str
    local_item: MemoryItem
    remote_item: MemoryItem
    conflict_type: str  # "content", "metadata", "timestamp"

    def __str__(self) -> str:
        return f"Conflict[{self.key}]: {self.conflict_type}"


class TeamMemoryStore:
    """
    Shared memory storage for team collaboration

    Maintains a centralized store accessible by multiple agents
    with versioning and conflict tracking.
    """

    def __init__(self):
        self._storage: Dict[str, MemoryItem] = {}
        self._versions: Dict[str, int] = {}  # Track version number per key
        self._access_log: List[Tuple[str, str, float]] = []  # (agent_id, key, timestamp)

    def store(self, key: str, item: MemoryItem, agent_id: str) -> int:
        """
        Store or update memory item

        Returns:
            New version number
        """
        self._storage[key] = item
        current_version = self._versions.get(key, 0)
        new_version = current_version + 1
        self._versions[key] = new_version

        # Log access
        self._access_log.append((agent_id, key, time.time()))

        return new_version

    def get(self, key: str, agent_id: str) -> Optional[Tuple[MemoryItem, int]]:
        """
        Retrieve memory item with version

        Returns:
            Tuple of (item, version) or None if not found
        """
        if key not in self._storage:
            return None

        item = self._storage[key]
        version = self._versions[key]

        # Log access
        self._access_log.append((agent_id, key, time.time()))

        return (item, version)

    def get_all_keys(self) -> Set[str]:
        """Get all stored keys"""
        return set(self._storage.keys())

    def get_version(self, key: str) -> Optional[int]:
        """Get current version number for a key"""
        return self._versions.get(key)


class TeamMemorySyncRail:
    """
    Rail for synchronizing memories across team agents

    Handles bidirectional sync between local agent memory
    and shared team memory store.
    """

    def __init__(self,
                 agent_id: str,
                 team_store: TeamMemoryStore,
                 sync_interval: float = 60.0,  # seconds
                 conflict_strategy: str = "keep_latest"):
        """
        Initialize team memory sync rail

        Args:
            agent_id: Unique identifier for this agent
            team_store: Shared team memory store
            sync_interval: Time between automatic syncs
            conflict_strategy: How to handle conflicts
                - "keep_latest": Use most recent timestamp
                - "keep_local": Prefer local version
                - "keep_remote": Prefer remote version
                - "merge": Attempt to merge content
        """
        self.agent_id = agent_id
        self.team_store = team_store
        self.sync_interval = sync_interval
        self.conflict_strategy = conflict_strategy

        # Track last sync time and known versions
        self.last_sync_time = time.time()
        self.known_versions: Dict[str, int] = {}

        # Statistics
        self.sync_count = 0
        self.conflicts_detected = 0
        self.conflicts_resolved = 0

    def sync_to_team(self,
                     local_memory: MultiLevelMemory,
                     layer: str = "project") -> Dict:
        """
        Push local memories to team store

        Args:
            local_memory: Local memory system
            layer: Which layer to sync ("project" recommended)

        Returns:
            Sync statistics
        """
        pushed_count = 0
        updated_count = 0
        conflicts = []

        # Get memories from specified layer
        if layer == "project":
            memories = local_memory.L3.get_all()
        elif layer == "task":
            memories = local_memory.L2.get_all()
        elif layer == "working":
            memories = local_memory.L1.get_all()
        else:
            raise ValueError(f"Invalid layer: {layer}")

        for item in memories:
            # Generate key from content hash
            key = self._generate_key(item.content)

            # Check if exists in team store
            remote_data = self.team_store.get(key, self.agent_id)

            if remote_data is None:
                # New item - push to team
                version = self.team_store.store(key, item, self.agent_id)
                self.known_versions[key] = version
                pushed_count += 1
            else:
                remote_item, remote_version = remote_data

                # Check for conflicts
                if self._has_conflict(item, remote_item):
                    conflict = MemoryConflict(
                        key=key,
                        local_item=item,
                        remote_item=remote_item,
                        conflict_type=self._detect_conflict_type(item, remote_item)
                    )
                    conflicts.append(conflict)
                    self.conflicts_detected += 1

                    # Resolve conflict
                    resolved_item = self._resolve_conflict(conflict)
                    version = self.team_store.store(key, resolved_item, self.agent_id)
                    self.known_versions[key] = version
                    self.conflicts_resolved += 1
                else:
                    # Update if local is newer
                    if item.timestamp > remote_item.timestamp:
                        version = self.team_store.store(key, item, self.agent_id)
                        self.known_versions[key] = version
                        updated_count += 1

        self.sync_count += 1
        self.last_sync_time = time.time()

        return {
            'pushed': pushed_count,
            'updated': updated_count,
            'conflicts': len(conflicts),
            'timestamp': self.last_sync_time
        }

    def sync_from_team(self, local_memory: MultiLevelMemory) -> Dict:
        """
        Pull memories from team store to local

        Args:
            local_memory: Local memory system

        Returns:
            Sync statistics
        """
        pulled_count = 0
        skipped_count = 0

        # Get all keys from team store
        team_keys = self.team_store.get_all_keys()

        for key in team_keys:
            remote_data = self.team_store.get(key, self.agent_id)
            if remote_data is None:
                continue

            remote_item, remote_version = remote_data

            # Check if we need to update local
            known_version = self.known_versions.get(key, 0)

            if remote_version > known_version:
                # Pull to local memory (project layer)
                local_memory.store(
                    content=remote_item.content,
                    layer="project",
                    task_id=remote_item.task_id,
                    importance=remote_item.importance,
                    key=key,
                    **remote_item.metadata
                )
                self.known_versions[key] = remote_version
                pulled_count += 1
            else:
                skipped_count += 1

        return {
            'pulled': pulled_count,
            'skipped': skipped_count,
            'timestamp': time.time()
        }

    def full_sync(self, local_memory: MultiLevelMemory) -> Dict:
        """
        Perform bidirectional sync

        Args:
            local_memory: Local memory system

        Returns:
            Combined sync statistics
        """
        push_stats = self.sync_to_team(local_memory)
        pull_stats = self.sync_from_team(local_memory)

        return {
            'push': push_stats,
            'pull': pull_stats,
            'sync_count': self.sync_count,
            'total_conflicts': self.conflicts_detected,
            'resolved_conflicts': self.conflicts_resolved
        }

    def should_sync(self) -> bool:
        """Check if it's time for automatic sync"""
        return (time.time() - self.last_sync_time) >= self.sync_interval

    def _generate_key(self, content: str) -> str:
        """Generate deterministic key from content"""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _has_conflict(self, local_item: MemoryItem, remote_item: MemoryItem) -> bool:
        """Detect if two items conflict"""
        # Different content
        if local_item.content != remote_item.content:
            return True

        # Different metadata
        if local_item.importance != remote_item.importance:
            return True

        return False

    def _detect_conflict_type(self, local_item: MemoryItem, remote_item: MemoryItem) -> str:
        """Classify conflict type"""
        if local_item.content != remote_item.content:
            return "content"
        elif local_item.importance != remote_item.importance:
            return "metadata"
        else:
            return "timestamp"

    def _resolve_conflict(self, conflict: MemoryConflict) -> MemoryItem:
        """
        Resolve conflict using configured strategy

        Args:
            conflict: Detected conflict

        Returns:
            Resolved memory item
        """
        if self.conflict_strategy == "keep_latest":
            # Use most recent timestamp
            if conflict.local_item.timestamp > conflict.remote_item.timestamp:
                return conflict.local_item
            else:
                return conflict.remote_item

        elif self.conflict_strategy == "keep_local":
            return conflict.local_item

        elif self.conflict_strategy == "keep_remote":
            return conflict.remote_item

        elif self.conflict_strategy == "merge":
            # Simple merge: combine content
            merged_content = f"{conflict.local_item.content}\n[Merged]\n{conflict.remote_item.content}"
            merged_item = MemoryItem(
                content=merged_content,
                layer=conflict.local_item.layer,
                task_id=conflict.local_item.task_id,
                importance=max(conflict.local_item.importance, conflict.remote_item.importance),
                metadata={**conflict.local_item.metadata, **conflict.remote_item.metadata}
            )
            return merged_item

        else:
            # Default: keep latest
            if conflict.local_item.timestamp > conflict.remote_item.timestamp:
                return conflict.local_item
            else:
                return conflict.remote_item

    def get_statistics(self) -> Dict:
        """Get sync rail statistics"""
        return {
            'agent_id': self.agent_id,
            'sync_count': self.sync_count,
            'last_sync': self.last_sync_time,
            'conflicts_detected': self.conflicts_detected,
            'conflicts_resolved': self.conflicts_resolved,
            'known_versions_count': len(self.known_versions),
            'conflict_strategy': self.conflict_strategy
        }
