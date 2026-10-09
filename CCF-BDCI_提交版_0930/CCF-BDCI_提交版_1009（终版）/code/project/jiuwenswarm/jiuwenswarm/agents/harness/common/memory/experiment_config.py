"""Select the code Agent's memory Rail for the controlled experiment."""

from __future__ import annotations

from typing import Any


def code_memory_experiment_group(config: dict[str, Any]) -> str:
    """Read ``modes.code.memory.experiment_group`` (default: baseline).

    Reject unknown groups so an experiment cannot silently run the wrong Rail.
    """
    modes = config.get("modes") or {}
    code = modes.get("code") or {}
    memory = code.get("memory") or {}
    group = memory.get("experiment_group", "baseline")
    if group not in ("baseline", "enhanced"):
        raise ValueError(
            "modes.code.memory.experiment_group must be 'baseline' or 'enhanced'"
        )
    return group
