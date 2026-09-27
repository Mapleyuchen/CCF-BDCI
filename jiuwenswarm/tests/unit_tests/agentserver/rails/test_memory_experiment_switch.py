"""The code Agent experiment changes only its selected memory Rail."""

from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from jiuwenswarm.agents.harness.common.memory.experiment_config import (
    code_memory_experiment_group,
)
from jiuwenswarm.agents.harness.common.rails import EnhancedMemoryRail, ProjectMemoryRail
from jiuwenswarm.agents.swarm import registry
from jiuwenswarm.agents.swarm.config_specs import build_member_capability_specs
from jiuwenswarm.agents.swarm.context import SwarmBuildContext
from jiuwenswarm.agents.swarm.providers.builtin_rails import (
    _build_enhanced_memory_rail,
)
with patch("jiuwenswarm.common.config.get_config", return_value={}):
    from jiuwenswarm.server.runtime.agent_adapter.interface_code import (
        JiuwenSwarmCodeAdapter,
    )


def _config(group: str) -> dict:
    return {
        "modes": {"code": {"memory": {"enabled": True, "experiment_group": group}}},
        "models": {"default": {"model_client_config": {"model_name": "same-model"}}},
    }


class MemoryExperimentSwitchTest(unittest.TestCase):
    def test_defaults_to_baseline_and_rejects_unknown_group(self):
        self.assertEqual(code_memory_experiment_group({}), "baseline")
        with self.assertRaisesRegex(ValueError, "experiment_group"):
            code_memory_experiment_group(_config("typo"))

    def test_code_team_specs_change_only_memory_rail(self):
        for mode in ("code.team", "team.plan.code"):
            for role in ("leader", "teammate"):
                with self.subTest(mode=mode, role=role):
                    baseline = _config("baseline")
                    enhanced = deepcopy(baseline)
                    enhanced["modes"]["code"]["memory"]["experiment_group"] = "enhanced"
                    base_rails, base_tools = build_member_capability_specs(baseline, mode, role)
                    enhanced_rails, enhanced_tools = build_member_capability_specs(
                        enhanced, mode, role
                    )
                    self.assertEqual(base_tools, enhanced_tools)
                    self.assertEqual(len(base_rails), len(enhanced_rails))
                    changed = [
                        (before, after)
                        for before, after in zip(base_rails, enhanced_rails)
                        if before != after
                    ]
                    self.assertEqual(len(changed), 1)
                    self.assertEqual(changed[0][0].type, registry.CODE_PROJECT_MEMORY)
                    self.assertEqual(changed[0][1].type, registry.ENHANCED_MEMORY)
                    self.assertEqual(changed[0][1].params, {})

    def test_single_code_adapter_constructs_selected_rail(self):
        adapter = JiuwenSwarmCodeAdapter.__new__(JiuwenSwarmCodeAdapter)
        adapter._project_dir = "project"
        adapter._workspace_dir = "workspace"
        adapter._instance_overrides = {}
        adapter._config_cache = {}
        adapter._resolve_runtime_language = lambda: "en"

        baseline = adapter._build_project_memory_rail(_config("baseline"))
        enhanced = adapter._build_project_memory_rail(_config("enhanced"))
        self.assertIsInstance(baseline, ProjectMemoryRail)
        self.assertIsInstance(enhanced, EnhancedMemoryRail)
        self.assertEqual(baseline._workspace_path, enhanced._workspace_path)

    def test_team_enhanced_provider_uses_code_project_directory(self):
        rail = _build_enhanced_memory_rail(
            {}, SwarmBuildContext(project_dir="project")
        )
        self.assertEqual(rail._workspace_path, "project")

    def test_single_code_adapter_passes_same_config_to_memory_builder(self):
        adapter = JiuwenSwarmCodeAdapter.__new__(JiuwenSwarmCodeAdapter)
        adapter._permission_interrupt_rail_infos = lambda _config: []
        adapter._instantiate_rails = lambda infos, _config: infos
        config = _config("enhanced")

        infos = adapter._build_agent_rails({}, config)

        memory_infos = [info for info in infos if info.attr_name == "_project_memory_rail"]
        self.assertEqual(len(memory_infos), 1)
        self.assertIs(memory_infos[0].params["config_base"], config)


class MemoryExperimentSwitchAsyncTest(unittest.IsolatedAsyncioTestCase):
    async def test_single_code_adapter_replaces_existing_rail(self):
        adapter = JiuwenSwarmCodeAdapter.__new__(JiuwenSwarmCodeAdapter)
        old_rail = ProjectMemoryRail(workspace="project")
        new_rail = EnhancedMemoryRail(workspace="project")
        adapter._project_memory_rail = old_rail
        adapter._subagent_rail = object()
        adapter._coding_memory_rail = object()
        adapter._instance = SimpleNamespace(
            register_rail=AsyncMock(), unregister_rail=AsyncMock()
        )
        adapter._active_code_config = lambda: _config("enhanced")
        adapter._build_project_memory_rail = lambda: new_rail
        adapter._sync_personal_context_rail = AsyncMock()

        await adapter._update_rails_for_mode("code")

        adapter._instance.unregister_rail.assert_awaited_once_with(old_rail)
        adapter._instance.register_rail.assert_awaited_once_with(new_rail)
        self.assertIs(adapter._project_memory_rail, new_rail)
