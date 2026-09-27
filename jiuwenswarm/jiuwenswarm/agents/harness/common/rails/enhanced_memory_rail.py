# coding: utf-8
# Copyright (c) CCF BDCI 2026 Team. All rights reserved.
"""EnhancedMemoryRail -- Multi-Level Memory Integration Rail

This rail integrates the enhanced multi-level memory system into JiuwenSwarm's
agent lifecycle.

Current behavior:
- Store completed user/assistant exchanges in L1 working memory
- Retrieve across the memory layers with hybrid ranking
- Inject retrieved content before the next model call

L2/L3 routing, disk persistence, and team synchronization require separate
integration work; they are not enabled by this rail yet.

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
from openjiuwen.core.foundation.llm.schema.message import UserMessage
from openjiuwen.harness.rails.base import DeepAgentRail
from openjiuwen.harness.prompts import PromptSection

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

    Store completed exchanges and inject relevant context before model calls.

    Usage:
        rail = EnhancedMemoryRail(
            workspace="/path/to/workspace",
            enable_hybrid_retrieval=True,
            enable_team_sync=False
        )
        await agent.register_rail(rail)
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
        max_context_chars: int | None = None,
    ) -> None:
        """Initialize the enhanced memory rail.

        Args:
            workspace: Working directory path
            enable_hybrid_retrieval: Use hybrid retrieval engine (default: True)
            enable_team_sync: Enable team memory synchronization (default: False)
            retrieval_weights: Custom weights for retrieval scoring
            max_context_items: Maximum memory items to inject per call (default: 10)
            max_context_chars: Optional full prompt-section character cap.
        """
        super().__init__()
        self._workspace_path: str = workspace
        self._enable_hybrid_retrieval = enable_hybrid_retrieval
        self._enable_team_sync = enable_team_sync
        self._max_context_items = max_context_items
        if max_context_chars is not None and max_context_chars <= 0:
            raise ValueError("max_context_chars must be positive")
        self._max_context_chars = max_context_chars

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

        # MultiLevelMemory currently has no storage_dir or disk persistence API.
        self._memory = MultiLevelMemory()
        logger.info("[EnhancedMemoryRail] Multi-level memory system initialized")

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

    async def before_model_call(self, ctx: AgentCallbackContext) -> None:
        """Inject relevant memories into system prompt before each model call."""
        if self._memory is None or self._system_prompt_builder is None:
            return

        try:
            # Replace the previous section on every model call, including calls
            # where there is no usable query or matching memory.
            self._system_prompt_builder.remove_section(self.SECTION_NAME)
            user_message = self._latest_user_message(ctx)

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
            if not memory_context:
                return

            # Inject into system prompt
            self._system_prompt_builder.add_section(
                PromptSection(
                    name=self.SECTION_NAME,
                    content={"cn": memory_context, "en": memory_context},
                    priority=self.SECTION_PRIORITY,
                )
            )

            logger.debug(
                f"[EnhancedMemoryRail] Injected {len(relevant_memories)} memories "
                f"into system prompt"
            )

        except Exception as e:
            logger.error(f"[EnhancedMemoryRail] Error in before_model_call: {e}")

    async def after_model_call(self, ctx: AgentCallbackContext) -> None:
        """Store important information from model response."""
        if self._memory is None:
            return

        try:
            user_message = self._latest_user_message(ctx)
            response = getattr(getattr(ctx, "inputs", None), "response", None)
            assistant_response = self._message_text(response)

            if not user_message or not assistant_response:
                return

            # Create memory entry
            memory_content = f"User: {user_message}\nAssistant: {assistant_response}"

            # Determine importance (simple heuristic)
            importance = self._calculate_importance(user_message, assistant_response)

            # Store in appropriate layer
            self._memory.store(
                content=memory_content,
                layer="working",
                importance=importance,
                type="conversation",
                user_query=user_message,
            )

            logger.debug(
                f"[EnhancedMemoryRail] Stored memory with importance={importance:.2f}"
            )

        except Exception as e:
            logger.error(f"[EnhancedMemoryRail] Error in after_model_call: {e}")

    def _retrieve_relevant_memories(self, query: str, limit: int):
        """Retrieve relevant memories using hybrid retrieval."""
        if self._memory is None:
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
                return [mem for mem, _score in results]
            else:
                # Recent-memory fallback when hybrid retrieval is disabled.
                return self._memory.get_all_memories()[-limit:][::-1]
        except Exception as e:
            logger.error(f"[EnhancedMemoryRail] Retrieval error: {e}")
            return []

    def _build_memory_context(self, memories) -> str:
        """Build formatted memory context for system prompt."""
        if not memories:
            return ""

        lines = [
            "# Relevant Context from Memory\n",
            "The following information from previous interactions may be relevant:\n",
        ]

        for i, memory in enumerate(memories, 1):
            content = memory.content if hasattr(memory, 'content') else str(memory)
            # Truncate very long memories
            if len(content) > 500:
                content = content[:500] + "..."
            candidate = f"\n## Memory {i}:\n{content}"
            if self._max_context_chars is not None and len(
                "\n".join(lines + [candidate])
            ) > self._max_context_chars:
                continue
            lines.append(candidate)

        if len(lines) == 2:
            return ""
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

    @staticmethod
    def _message_text(message: object) -> str:
        """Extract plain text without turning an entire message object into text."""
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return "\n".join(
                part if isinstance(part, str) else str(part.get("text", ""))
                for part in content
                if isinstance(part, str) or (isinstance(part, dict) and part.get("type") == "text")
            ).strip()
        return ""

    @classmethod
    def _latest_user_message(cls, ctx: AgentCallbackContext) -> str:
        inputs = getattr(ctx, "inputs", None)
        messages = getattr(inputs, "messages", None) or []
        for message in reversed(messages):
            if isinstance(message, UserMessage) or getattr(message, "role", None) == "user":
                return cls._message_text(message)
        return ""

    def uninit(self, agent: "DeepAgent") -> None:
        """Remove this rail's prompt section when it is unregistered."""
        if self._system_prompt_builder is not None:
            self._system_prompt_builder.remove_section(self.SECTION_NAME)


__all__ = ["EnhancedMemoryRail"]
