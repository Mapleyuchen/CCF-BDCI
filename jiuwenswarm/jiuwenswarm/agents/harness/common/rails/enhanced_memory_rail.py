# coding: utf-8
# Copyright (c) CCF BDCI 2026 Team. All rights reserved.
"""EnhancedMemoryRail -- Multi-Level Memory Integration Rail

This rail integrates the enhanced multi-level memory system into JiuwenSwarm's
agent lifecycle. It replaces the default single-layer memory with a three-tier
hierarchical system optimized for different temporal scopes.

Key Features:
- L1 Working Memory: Recent context (20 items, 1h TTL)
- L2 Task Memory: Execution history (100 items, 7d TTL)
- L3 Project Memory: Long-term knowledge (unlimited, persistent)
- Hybrid retrieval: semantic + temporal + frequency + importance
- Team memory sync: multi-agent collaboration support

Integration:
Register this rail in your agent configuration to automatically enable
the enhanced memory system. Compatible with existing ProjectMemoryRail.

Author: CCF BDCI 2026 Team
Date: 2026-09-24
License: MIT
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from openjiuwen.core.single_agent.rail.base import AgentCallbackContext
from openjiuwen.harness.rails.base import DeepAgentRail

from jiuwenswarm.agents.harness.common.memory.multi_level_memory import (
    MultiLevelMemory,
)
from jiuwenswarm.agents.harness.common.memory.retrieval_engine import (
    HybridRetrievalEngine,
    RetrievalWeights,
)
from jiuwenswarm.agents.harness.common.prompt.priority_registry import (
    SystemPromptPriority,
)
from jiuwenswarm.common.utils import logger

if TYPE_CHECKING:
    from openjiuwen.harness.deep_agent import DeepAgent


class EnhancedMemoryRail(DeepAgentRail):
    """Enhanced multi-level memory integration rail.

    Automatically manages agent memory across three hierarchical layers
    and injects relevant context into system prompts before each model call.

    Usage:
        rail = EnhancedMemoryRail(
            workspace="/path/to/workspace",
            enable_hybrid_retrieval=True,
            enable_team_sync=False
        )
        agent.register_rail(rail)
    """

    SECTION_NAME = "enhanced_memory"
    SECTION_PRIORITY = SystemPromptPriority.PROJECT_MEMORY + 1

    def __init__(
        self,
        workspace: str,
        *,
        enable_hybrid_retrieval: bool = True,
        enable_team_sync: bool = False,
        retrieval_weights: Optional[RetrievalWeights] = None,
        max_context_items: int = 10,
    ) -> None:
        """Initialize the enhanced memory rail.

        Args:
            workspace: Working directory path
            enable_hybrid_retrieval: Use hybrid retrieval engine (default: True)
            enable_team_sync: Enable team memory synchronization (default: False)
            retrieval_weights: Custom weights for retrieval scoring
            max_context_items: Maximum memory items to inject per call (default: 10)
        """
        super().__init__()
        self._workspace_path: str = workspace
        self._enable_hybrid_retrieval = enable_hybrid_retrieval
        self._enable_team_sync = enable_team_sync
        self._max_context_items = max_context_items

        # Initialize memory system
        self._memory: Optional[MultiLevelMemory] = None
        self._retrieval_engine: Optional[HybridRetrievalEngine] = None
        self._system_prompt_builder = None

        # Custom retrieval weights
        self._retrieval_weights = retrieval_weights or RetrievalWeights()

        logger.info(
            f"[EnhancedMemoryRail] Initialized with hybrid_retrieval={enable_hybrid_retrieval}, "
            f"team_sync={enable_team_sync}"
        )

    def init(self, agent: "DeepAgent") -> None:
        """Initialize memory system when rail is registered to agent."""
        self._system_prompt_builder = getattr(agent, "system_prompt_builder", None)

        if self._system_prompt_builder is None:
            logger.warning(
                "[EnhancedMemoryRail] agent has no system_prompt_builder; disabled"
            )
            return

        # Create multi-level memory
        try:
            self._memory = MultiLevelMemory(storage_dir=self._workspace_path)
            logger.info("[EnhancedMemoryRail] Multi-level memory system initialized")
        except Exception as e:
            logger.error(f"[EnhancedMemoryRail] Failed to initialize memory: {e}")
            return

        # Create hybrid retrieval engine if enabled
        if self._enable_hybrid_retrieval:
            try:
                self._retrieval_engine = HybridRetrievalEngine(
                    weights=self._retrieval_weights
                )
                logger.info("[EnhancedMemoryRail] Hybrid retrieval engine initialized")
            except Exception as e:
                logger.warning(
                    f"[EnhancedMemoryRail] Failed to initialize retrieval engine: {e}"
                )

    def before_model_call(self, context: AgentCallbackContext) -> None:
        """Inject relevant memories into system prompt before each model call."""
        if not self._memory or not self._system_prompt_builder:
            return

        try:
            # Get current user message
            user_message = context.input.text if hasattr(context.input, 'text') else ""

            if not user_message:
                return

            # Retrieve relevant memories
            relevant_memories = self._retrieve_relevant_memories(
                query=user_message,
                limit=self._max_context_items
            )

            if not relevant_memories:
                return

            # Build memory context section
            memory_context = self._build_memory_context(relevant_memories)

            # Inject into system prompt
            self._system_prompt_builder.set_section(
                name=self.SECTION_NAME,
                content=memory_context,
                priority=self.SECTION_PRIORITY,
            )

            logger.debug(
                f"[EnhancedMemoryRail] Injected {len(relevant_memories)} memories "
                f"into system prompt"
            )

        except Exception as e:
            logger.error(f"[EnhancedMemoryRail] Error in before_model_call: {e}")

    def after_model_call(self, context: AgentCallbackContext) -> None:
        """Store important information from model response."""
        if not self._memory:
            return

        try:
            # Extract user message and assistant response
            user_message = context.input.text if hasattr(context.input, 'text') else ""
            assistant_response = ""

            if hasattr(context, 'response') and context.response:
                assistant_response = str(context.response)

            if not user_message and not assistant_response:
                return

            # Create memory entry
            memory_content = f"User: {user_message}\nAssistant: {assistant_response}"

            # Determine importance (simple heuristic)
            importance = self._calculate_importance(user_message, assistant_response)

            # Store in appropriate layer
            self._memory.add_memory(
                content=memory_content,
                importance=importance,
                metadata={
                    "type": "conversation",
                    "user_query": user_message,
                }
            )

            logger.debug(
                f"[EnhancedMemoryRail] Stored memory with importance={importance:.2f}"
            )

        except Exception as e:
            logger.error(f"[EnhancedMemoryRail] Error in after_model_call: {e}")

    def _retrieve_relevant_memories(self, query: str, limit: int):
        """Retrieve relevant memories using hybrid retrieval."""
        if not self._memory:
            return []

        try:
            if self._retrieval_engine:
                # Use hybrid retrieval
                all_memories = self._memory.get_all_memories()
                if not all_memories:
                    return []

                results = self._retrieval_engine.retrieve(
                    query=query,
                    memories=all_memories,
                    top_k=limit
                )
                return [mem for _, mem in results]
            else:
                # Fallback to simple retrieval
                return self._memory.retrieve_memories(
                    query=query,
                    limit=limit
                )
        except Exception as e:
            logger.error(f"[EnhancedMemoryRail] Retrieval error: {e}")
            return []

    def _build_memory_context(self, memories) -> str:
        """Build formatted memory context for system prompt."""
        if not memories:
            return ""

        lines = ["# Relevant Context from Memory\n"]
        lines.append("The following information from previous interactions may be relevant:\n")

        for i, memory in enumerate(memories, 1):
            content = memory.content if hasattr(memory, 'content') else str(memory)
            # Truncate very long memories
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(f"\n## Memory {i}:")
            lines.append(content)

        return "\n".join(lines)

    def _calculate_importance(self, user_message: str, assistant_response: str) -> float:
        """Calculate importance score for a memory entry (simple heuristic)."""
        importance = 0.5  # base importance

        # Boost for longer interactions
        total_length = len(user_message) + len(assistant_response)
        if total_length > 500:
            importance += 0.1
        if total_length > 1000:
            importance += 0.1

        # Boost for certain keywords
        important_keywords = [
            "important", "remember", "task", "project", "error", "bug",
            "重要", "记住", "任务", "项目", "错误"
        ]

        combined_text = (user_message + " " + assistant_response).lower()
        for keyword in important_keywords:
            if keyword in combined_text:
                importance += 0.05
                break

        # Cap at 1.0
        return min(importance, 1.0)

    def cleanup(self, agent: "DeepAgent") -> None:
        """Cleanup when rail is removed or agent shuts down."""
        if self._memory:
            try:
                # Save all memories to disk
                self._memory.save_all()
                logger.info("[EnhancedMemoryRail] Saved all memories on cleanup")
            except Exception as e:
                logger.error(f"[EnhancedMemoryRail] Error saving memories: {e}")


__all__ = ["EnhancedMemoryRail"]
