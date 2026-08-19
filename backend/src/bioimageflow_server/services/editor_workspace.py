"""Managed multi-root workspace for the embedded code editor."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


EDITOR_WORKSPACE_RELATIVE_PATH = Path(".bioimageflow") / "BioImageFlow.code-workspace"


def ensure_editor_workspace(workspace_path: Path, tool_store_path: Path) -> Path:
    """Write the managed VS Code workspace and return its absolute path."""
    workspace = workspace_path.expanduser().resolve(strict=False)
    tool_store = tool_store_path.expanduser().resolve(strict=False)
    if not workspace.is_dir():
        raise FileNotFoundError(f"BioImageFlow workspace does not exist: {workspace}")
    if not tool_store.is_dir():
        raise FileNotFoundError(f"BioImageFlow tool store does not exist: {tool_store}")
    if workspace == tool_store:
        raise ValueError("BioImageFlow workspace and tool store must be different directories")

    target = workspace / EDITOR_WORKSPACE_RELATIVE_PATH
    payload = {
        "folders": [
            {"name": "Workspace", "path": str(workspace)},
            {"name": "Installed Tool Packages", "path": str(tool_store)},
        ],
        "settings": {
            "terminal.integrated.cwd": str(workspace),
            "files.readonlyInclude": {
                f"{tool_store.as_posix().rstrip('/')}/**": True,
            },
        },
    }
    content = json.dumps(payload, indent=2) + "\n"
    if target.is_file() and target.read_text(encoding="utf-8") == content:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temporary_name, target)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return target
