"""Helpers for tests that exercise installed bioimageflow-common-tools."""

from __future__ import annotations

import os

import pytest
from packaging.version import InvalidVersion, Version

PACKAGE_NAME = "bioimageflow_common_tools"
COMMON_TOOLS_MARK = pytest.mark.common_tools
COMMON_TOOLS_SKIP_REASON = (
    f"{PACKAGE_NAME} certification tests require an installed tool store. "
    "Set BIOIMAGEFLOW_TOOL_STORE to a fixture store, or BIOIMAGEFLOW_HOME to "
    "a home containing tool_packages/bioimageflow_common_tools."
)


def latest_common_tools_version() -> str:
    """Return the newest installed common-tools version, or skip the test."""
    try:
        __import__("bioimageflow.paths")
    except ImportError:
        _skip_common_tools()
    from bioimageflow.paths import get_tool_store_path

    package_dir = get_tool_store_path() / PACKAGE_NAME
    if not package_dir.exists():
        _skip_common_tools()

    versions = sorted(
        (path.name for path in package_dir.iterdir() if path.is_dir()),
        key=_version_key,
    )
    if not versions:
        _skip_common_tools()
    return versions[-1]


def load_common_tools_class(class_name: str) -> tuple[type, str]:
    """Load a class from the newest installed common-tools package."""
    try:
        __import__("bioimageflow.tool_loader")
    except ImportError:
        _skip_common_tools()
    from bioimageflow.tool_loader import load_versioned_package

    version = latest_common_tools_version()
    try:
        module = load_versioned_package(PACKAGE_NAME, version)
    except Exception as exc:
        pytest.skip(f"{COMMON_TOOLS_SKIP_REASON} Load failed for {version}: {exc}")

    cls = getattr(module, class_name, None)
    if cls is None:
        pytest.skip(f"{COMMON_TOOLS_SKIP_REASON} {class_name} is missing from {version}.")
    return cls, version


def maybe_load_common_tools_class(class_name: str) -> tuple[type, str] | None:
    """Load a common-tools class, returning None for optional registrations."""
    try:
        return load_common_tools_class(class_name)
    except pytest.skip.Exception:
        return None


def _version_key(version: str) -> Version:
    try:
        return Version(version)
    except InvalidVersion:
        return Version("0")


def _skip_common_tools() -> None:
    configured_store = os.environ.get("BIOIMAGEFLOW_TOOL_STORE")
    configured_home = os.environ.get("BIOIMAGEFLOW_HOME")
    detail = ""
    if configured_store:
        detail = f" Checked BIOIMAGEFLOW_TOOL_STORE={configured_store}."
    elif configured_home:
        detail = f" Checked BIOIMAGEFLOW_HOME={configured_home}."
    pytest.skip(f"{COMMON_TOOLS_SKIP_REASON}{detail}")
