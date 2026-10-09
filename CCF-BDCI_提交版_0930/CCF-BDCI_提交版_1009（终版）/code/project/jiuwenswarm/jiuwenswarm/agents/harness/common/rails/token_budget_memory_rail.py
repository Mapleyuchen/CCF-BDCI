"""Read-only single-layer memory Rail for controlled token-budget comparisons."""

from __future__ import annotations

from openjiuwen.harness.rails.base import DeepAgentRail
from openjiuwen.harness.prompts import PromptSection

from jiuwenswarm.agents.harness.common.memory.controlled_retrieval import FrozenMemoryIndex, PinnedTokenizer
from jiuwenswarm.agents.harness.common.prompt.priority_registry import SystemPromptPriority
from .enhanced_memory_rail import EnhancedMemoryRail


class TokenBudgetMemoryRail(DeepAgentRail):
    """Use one immutable bank, wrapper and packing rule for all selectors.

    Source history can be ingested directly without a model ACK. Formal answers
    never mutate the bank. The caller explicitly sets query text and timestamp;
    no reference answer or evidence labels are accepted by this Rail.
    """

    SECTION_NAME = "token_budget_memory"

    def __init__(self, index: FrozenMemoryIndex, tokenizer: PinnedTokenizer, *,
                 strategy: str, budget_tokens: int, reference_time: float):
        super().__init__()
        self.index, self.tokenizer = index, tokenizer
        self.strategy, self.budget_tokens = strategy, budget_tokens
        self.reference_time = reference_time
        self.query_override: str | None = None
        self.trace: dict | None = None
        self._builder = None

    def init(self, agent):
        self._builder = agent.system_prompt_builder

    async def before_model_call(self, ctx):
        if self._builder is None:
            raise RuntimeError("TokenBudgetMemoryRail has not been initialized")
        query = self.query_override or EnhancedMemoryRail._latest_user_message(ctx)
        ranking = self.index.rank(query, self.strategy, self.reference_time)
        self.trace = self.index.pack(ranking, self.tokenizer, self.budget_tokens)
        self._builder.remove_section(self.SECTION_NAME)
        self._builder.add_section(PromptSection(
            name=self.SECTION_NAME, content={"en": self.trace["context"], "cn": self.trace["context"]},
            priority=SystemPromptPriority.PROJECT_MEMORY,
        ))
        rendered = self._builder.get_section(self.SECTION_NAME).render("en")
        # PromptSection may add its own heading. Account for the actual render.
        if self.tokenizer.count(rendered) > self.budget_tokens:
            raise RuntimeError("Rendered Rail exceeds the memory token cap")
        self.trace["rendered_context"] = rendered
        self.trace["memory_tokens"] = self.tokenizer.count(rendered)

    async def after_model_call(self, ctx):
        """Intentionally read-only, including successful and failed questions."""

    def uninit(self, agent):
        if self._builder is not None:
            self._builder.remove_section(self.SECTION_NAME)
