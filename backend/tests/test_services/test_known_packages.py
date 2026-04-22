"""Tests for KnownPackagesService and the bundled default list."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import pytest

from bioimageflow_server.services.known_packages import KnownPackagesService


# ---------------------------------------------------------------------------
# Task 1 — bundled default ships with the backend
# ---------------------------------------------------------------------------


def test_bundled_default_ships_with_backend():
    bundled = resources.files("bioimageflow_server.data").joinpath(
        "default_known_packages.txt"
    )
    text = bundled.read_text(encoding="utf-8")
    non_comment_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert "bioimageflow_common_tools" in non_comment_lines


# ---------------------------------------------------------------------------
# Task 2 — KnownPackagesService
# ---------------------------------------------------------------------------


@pytest.fixture
def bundled_fixture(tmp_path: Path) -> Path:
    bundled = tmp_path / "bundled.txt"
    bundled.write_text(
        "# bundled default\nbioimageflow_core\nbundled_extra\n",
        encoding="utf-8",
    )
    return bundled


def test_list_uses_bundled_when_user_absent(tmp_path: Path, bundled_fixture: Path):
    user_path = tmp_path / "user.txt"  # does not exist
    svc = KnownPackagesService(user_path=user_path, bundled_path=bundled_fixture)
    assert svc.list_known_packages() == ["bioimageflow_core", "bundled_extra"]


def test_list_uses_user_file_when_present(tmp_path: Path, bundled_fixture: Path):
    user_path = tmp_path / "user.txt"
    user_path.write_text(
        "# custom user list\nfoo_pkg\nbar_pkg\n",
        encoding="utf-8",
    )
    svc = KnownPackagesService(user_path=user_path, bundled_path=bundled_fixture)
    # User file completely replaces bundled (spec §2.5)
    assert svc.list_known_packages() == ["foo_pkg", "bar_pkg"]


def test_list_strips_comments_and_blanks(tmp_path: Path, bundled_fixture: Path):
    user_path = tmp_path / "user.txt"
    user_path.write_text(
        "# leading comment\n"
        "\n"
        "pkg_a\n"
        "  \n"
        "pkg_b  # trailing comment\n"
        "# between comment\n"
        "pkg_c\n",
        encoding="utf-8",
    )
    svc = KnownPackagesService(user_path=user_path, bundled_path=bundled_fixture)
    assert svc.list_known_packages() == ["pkg_a", "pkg_b", "pkg_c"]


def test_list_returns_empty_and_warns_when_both_unreadable(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    user_path = tmp_path / "missing_user.txt"
    bundled_path = tmp_path / "missing_bundled.txt"
    svc = KnownPackagesService(user_path=user_path, bundled_path=bundled_path)
    with caplog.at_level("WARNING"):
        result = svc.list_known_packages()
    assert result == []
    assert any("known_packages" in rec.message.lower() for rec in caplog.records)


def test_default_constructor_resolves_bundled_resource():
    svc = KnownPackagesService.default()
    names = svc.list_known_packages()
    # Either user has overridden the file (unknown contents) or we get the bundled default.
    # On a clean test env the user file should not exist; tolerate the override case too.
    assert isinstance(names, list)
    assert all(isinstance(n, str) for n in names)
