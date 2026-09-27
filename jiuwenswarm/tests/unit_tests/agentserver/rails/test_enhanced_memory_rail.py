"""Exercise the EnhancedMemoryRail against openjiuwen's real callback API."""

from types import SimpleNamespace
import unittest
from uuid import uuid4

from openjiuwen.core.foundation.llm.schema.message import AssistantMessage, UserMessage
from openjiuwen.core.single_agent.agent_callback_manager import AgentCallbackManager
from openjiuwen.core.single_agent.rail.base import (
    AgentCallbackContext,
    AgentCallbackEvent,
    ModelCallInputs,
)
from openjiuwen.harness.prompts import SystemPromptBuilder
from openjiuwen.harness.schema import deep_agent_spec as das

from jiuwenswarm.agents.harness.common.rails.enhanced_memory_rail import EnhancedMemoryRail
from jiuwenswarm.agents.swarm.registry import ENHANCED_MEMORY, register_swarm_providers


class EnhancedMemoryRailTest(unittest.IsolatedAsyncioTestCase):
    def test_context_character_budget(self):
        rail = EnhancedMemoryRail(workspace="unused", max_context_chars=240)
        context = rail._build_memory_context([
            SimpleNamespace(content="A" * 500),
            SimpleNamespace(content="<FACT:F01> PostgreSQL"),
        ])
        self.assertLessEqual(len(context), 240)
        self.assertIn("<FACT:F01>", context)

    def test_swarm_provider_is_registered(self):
        register_swarm_providers()
        self.assertIn(ENHANCED_MEMORY, das._RAIL_PROVIDER_REGISTRY)

    async def test_registered_rail_stores_and_injects_memory(self):
        builder = SystemPromptBuilder(language="en")
        manager = AgentCallbackManager(f"enhanced-memory-test-{uuid4()}")
        agent = SimpleNamespace(system_prompt_builder=builder, agent_callback_manager=manager)
        rail = EnhancedMemoryRail(workspace="unused")
        rail.init(agent)

        await manager.register_rail(rail, agent)
        try:
            self.assertTrue(manager.has_hooks(AgentCallbackEvent.BEFORE_MODEL_CALL))
            self.assertTrue(manager.has_hooks(AgentCallbackEvent.AFTER_MODEL_CALL))

            first = AgentCallbackContext(
                agent=agent,
                inputs=ModelCallInputs(
                    messages=[UserMessage(content="Remember: the Atlas database is PostgreSQL.")],
                    response=AssistantMessage(content="I will remember that Atlas uses PostgreSQL."),
                ),
            )
            await first.fire(AgentCallbackEvent.AFTER_MODEL_CALL)
            self.assertEqual(rail._memory.get_statistics()["total_stores"], 1)

            follow_up = AgentCallbackContext(
                agent=agent,
                inputs=ModelCallInputs(messages=[UserMessage(content="Which database does Atlas use?")]),
            )
            await follow_up.fire(AgentCallbackEvent.BEFORE_MODEL_CALL)
            section = builder.get_section(rail.SECTION_NAME)
            self.assertIsNotNone(section)
            self.assertIn("PostgreSQL", section.render("en"))

            empty = AgentCallbackContext(agent=agent, inputs=ModelCallInputs())
            await empty.fire(AgentCallbackEvent.BEFORE_MODEL_CALL)
            self.assertIsNone(builder.get_section(rail.SECTION_NAME))
        finally:
            await manager.unregister_rail(rail, agent)
            rail.uninit(agent)
