from __future__ import annotations

import json
from pathlib import Path

import pytest

from bioimageflow_server.services import editor_workspace
from bioimageflow_server.services.editor_workspace import ensure_editor_workspace


def test_ensure_editor_workspace_writes_multi_root_configuration(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    tool_store = tmp_path / "tool_packages"
    workspace.mkdir()
    tool_store.mkdir()

    result = ensure_editor_workspace(workspace, tool_store)

    assert result == workspace / ".bioimageflow" / "BioImageFlow.code-workspace"
    assert json.loads(result.read_text(encoding="utf-8")) == {
        "folders": [
            {"name": "Workspace", "path": str(workspace)},
            {"name": "Installed Tool Packages", "path": str(tool_store)},
        ],
        "settings": {
            "terminal.integrated.cwd": str(workspace),
            "files.readonlyInclude": {f"{tool_store.as_posix()}/**": True},
        },
    }


def test_ensure_editor_workspace_does_not_replace_unchanged_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    tool_store = tmp_path / "tool_packages"
    workspace.mkdir()
    tool_store.mkdir()
    result = ensure_editor_workspace(workspace, tool_store)
    replacements: list[tuple[str, Path]] = []
    monkeypatch.setattr(
        editor_workspace.os,
        "replace",
        lambda source, target: replacements.append((source, target)),
    )

    assert ensure_editor_workspace(workspace, tool_store) == result
    assert replacements == []


def test_ensure_editor_workspace_keeps_previous_file_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    first_store = tmp_path / "tool_packages_a"
    second_store = tmp_path / "tool_packages_b"
    workspace.mkdir()
    first_store.mkdir()
    second_store.mkdir()
    result = ensure_editor_workspace(workspace, first_store)
    previous = result.read_text(encoding="utf-8")

    def fail_replace(_source: str, _target: Path) -> None:
        raise OSError("read-only filesystem")

    monkeypatch.setattr(editor_workspace.os, "replace", fail_replace)

    with pytest.raises(OSError, match="read-only filesystem"):
        ensure_editor_workspace(workspace, second_store)

    assert result.read_text(encoding="utf-8") == previous
    assert list(result.parent.glob(".*.tmp")) == []


@pytest.mark.parametrize("missing", ["workspace", "tool_store"])
def test_ensure_editor_workspace_requires_existing_roots(tmp_path: Path, missing: str) -> None:
    workspace = tmp_path / "workspace"
    tool_store = tmp_path / "tool_packages"
    if missing != "workspace":
        workspace.mkdir()
    if missing != "tool_store":
        tool_store.mkdir()

    with pytest.raises(FileNotFoundError):
        ensure_editor_workspace(workspace, tool_store)
