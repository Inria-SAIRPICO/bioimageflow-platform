"""Helpers for tests that exercise installed bioimageflow-common-tools."""

from __future__ import annotations

import os

import pytest
from packaging.version import InvalidVersion, Version

PACKAGE_NAME = "bioimageflow_common_tools"
COMMON_TOOLS_MARK = pytest.mark.common_tools
COMMON_TOOLS_FAILURE_REASON = (
    f"{PACKAGE_NAME} certification tests require an installed tool store. "
    "Set BIOIMAGEFLOW_TOOL_STORE to a fixture store, or BIOIMAGEFLOW_HOME to "
    "a home containing tool_packages/bioimageflow_common_tools."
)


def latest_common_tools_version() -> str:
    """Return the newest installed common-tools version, or fail certification."""
    try:
        __import__("bioimageflow.paths")
    except ImportError:
        _fail_common_tools("Could not import bioimageflow.paths.")
    from bioimageflow.paths import get_tool_store_path

    package_dir = get_tool_store_path() / PACKAGE_NAME
    if not package_dir.exists():
        _fail_common_tools(f"Package directory does not exist: {package_dir}.")

    versions = sorted(
        (path.name for path in package_dir.iterdir() if path.is_dir()),
        key=_version_key,
    )
    if not versions:
        _fail_common_tools(f"No installed versions were found in {package_dir}.")
    return versions[-1]


def load_common_tools_class(class_name: str) -> tuple[type, str]:
    """Load a class from the newest installed common-tools package."""
    try:
        __import__("bioimageflow.tool_loader")
    except ImportError:
        _fail_common_tools("Could not import bioimageflow.tool_loader.")
    from bioimageflow.tool_loader import load_versioned_package

    version = latest_common_tools_version()
    try:
        module = load_versioned_package(PACKAGE_NAME, version)
    except Exception as exc:
        pytest.fail(
            f"{COMMON_TOOLS_FAILURE_REASON} Load failed for {version}: {exc}",
            pytrace=False,
        )

    cls = getattr(module, class_name, None)
    if cls is None:
        pytest.fail(
            f"{COMMON_TOOLS_FAILURE_REASON} {class_name} is missing from {version}.",
            pytrace=False,
        )
    return cls, version


def _version_key(version: str) -> Version:
    try:
        return Version(version)
    except InvalidVersion:
        return Version("0")


def _fail_common_tools(detail: str) -> None:
    configured_store = os.environ.get("BIOIMAGEFLOW_TOOL_STORE")
    configured_home = os.environ.get("BIOIMAGEFLOW_HOME")
    configured_detail = ""
    if configured_store:
        configured_detail = f" Checked BIOIMAGEFLOW_TOOL_STORE={configured_store}."
    elif configured_home:
        configured_detail = f" Checked BIOIMAGEFLOW_HOME={configured_home}."
    pytest.fail(
        f"{COMMON_TOOLS_FAILURE_REASON} {detail}{configured_detail}",
        pytrace=False,
    )
