"""Regression tests for strict external common-tools certification helpers."""

import builtins
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.common_tools import latest_common_tools_version, load_common_tools_class


def _configure_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    version: str = "0.1.5",
) -> None:
    tool_store = tmp_path / "tool-packages"
    (tool_store / "bioimageflow_common_tools" / version).mkdir(parents=True)
    monkeypatch.setenv("BIOIMAGEFLOW_TOOL_STORE", str(tool_store))


def test_missing_common_tools_store_fails_certification(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("BIOIMAGEFLOW_TOOL_STORE", str(tmp_path / "missing-store"))

    with pytest.raises(pytest.fail.Exception, match="Package directory does not exist"):
        latest_common_tools_version()


@pytest.mark.parametrize("module_name", ["bioimageflow.paths", "bioimageflow.tool_loader"])
def test_missing_bioimageflow_import_fails_certification(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
) -> None:
    real_import = builtins.__import__

    def fail_selected_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == module_name:
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    with monkeypatch.context() as import_patch:
        import_patch.setattr(builtins, "__import__", fail_selected_import)
        with pytest.raises(pytest.fail.Exception, match=f"Could not import {module_name}"):
            if module_name == "bioimageflow.paths":
                latest_common_tools_version()
            else:
                load_common_tools_class("Files")


def test_common_tools_load_error_fails_certification(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import bioimageflow.tool_loader as tool_loader

    _configure_version(monkeypatch, tmp_path)

    def fail_load(_package: str, _version: str) -> None:
        raise RuntimeError("broken package")

    monkeypatch.setattr(tool_loader, "load_versioned_package", fail_load)

    with pytest.raises(pytest.fail.Exception, match="Load failed for 0.1.5"):
        load_common_tools_class("Files")


def test_missing_common_tools_class_fails_certification(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import bioimageflow.tool_loader as tool_loader

    _configure_version(monkeypatch, tmp_path)
    monkeypatch.setattr(
        tool_loader,
        "load_versioned_package",
        lambda _package, _version: SimpleNamespace(),
    )

    with pytest.raises(pytest.fail.Exception, match="Files is missing from 0.1.5"):
        load_common_tools_class("Files")
