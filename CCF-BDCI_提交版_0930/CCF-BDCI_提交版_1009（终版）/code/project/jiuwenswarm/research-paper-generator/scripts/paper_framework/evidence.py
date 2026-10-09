"""Resolve evidence consistently across framework, content, and quality handoffs."""

from pathlib import Path


def evidence_path(record: dict, project: Path | None = None) -> Path:
    """Prefer an explicit project-relative snapshot; never fall back if it is lost.

    resolved_path is retained for old callers and legacy manifests. New consumers
    supply the current project root so moving the project does not change evidence.
    """
    if "project_path" in record:
        relative = record["project_path"]
        if not isinstance(relative, str) or not relative.strip():
            raise ValueError("Evidence project_path must be a non-empty relative path")
        if Path(relative).is_absolute() or Path(relative).drive or ".." in Path(relative).parts:
            raise ValueError(f"Evidence path is outside its project: {relative}")
        if project is not None:
            root = project.resolve()
            path = (root / relative).resolve()
            if not path.is_relative_to(root):
                raise ValueError(f"Evidence path is outside its project: {relative}")
            return path
    recorded = record.get("resolved_path")
    if not isinstance(recorded, str) or not recorded.strip():
        raise ValueError("Evidence has no usable path")
    return Path(recorded)
