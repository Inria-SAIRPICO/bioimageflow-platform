"""Tests for platform latest-output mode policy."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bioimageflow.storage import OutputViewCapability

from bioimageflow_server.models.settings import Settings
from bioimageflow_server.services import output_views


def _capability(mode: str, supported: bool) -> OutputViewCapability:
    return OutputViewCapability(
        mode=mode,
        supported=supported,
        code="ok" if supported else "permission_denied",
    )


def _capabilities(*, symlink: bool = True) -> dict[str, OutputViewCapability]:
    return {
        "pointer": _capability("pointer", True),
        "symlink": _capability("symlink", symlink),
        "copy": _capability("copy", True),
    }


def test_auto_uses_symlinks_when_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(output_views, "probe_latest_output_modes", lambda _path: _capabilities())

    resolved = output_views.resolve_latest_output_mode(Path("/outputs"), "auto")

    assert resolved.effective == "symlink"
    assert resolved.warning is None


def test_auto_falls_back_to_pointer_without_copying(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        output_views,
        "probe_latest_output_modes",
        lambda _path: _capabilities(symlink=False),
    )

    resolved = output_views.resolve_latest_output_mode(Path("/outputs"), "auto")

    assert resolved.effective == "pointer"
    assert "permissions" in (resolved.warning or "")


def test_runtime_symlink_failure_falls_back_to_pointer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(output_views, "probe_latest_output_modes", lambda _path: _capabilities())
    workflow = MagicMock()
    workflow.export_outputs.side_effect = [OSError("links denied"), [Path("pointer")]]
    settings = Settings(deployment_mode="desktop", latest_output_mode="symlink")

    resolved = output_views.materialize_latest_outputs(
        workflow,
        settings,
        storage_path=Path("/outputs"),
    )

    assert resolved.effective == "pointer"
    assert workflow.export_outputs.call_args_list[0].kwargs == {
        "mode": "symlink",
        "scope": "latest",
    }
    assert workflow.export_outputs.call_args_list[1].kwargs == {
        "mode": "pointer",
        "scope": "latest",
    }


def test_copy_failure_does_not_fall_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(output_views, "probe_latest_output_modes", lambda _path: _capabilities())
    workflow = MagicMock()
    workflow.export_outputs.side_effect = OSError("disk full")
    settings = Settings(deployment_mode="desktop", latest_output_mode="copy")

    with pytest.raises(OSError, match="disk full"):
        output_views.materialize_latest_outputs(
            workflow,
            settings,
            storage_path=Path("/outputs"),
        )

    workflow.export_outputs.assert_called_once_with(mode="copy", scope="latest")
