"""Self-audit contracts for the backend local-platform campaign selection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.campaign_scope import (
    ALLOWED_EXCLUSION_REASONS,
    MANIFEST_PATH,
    audit_backend_collection,
    load_backend_exclusions,
)


class _Item:
    def __init__(self, nodeid: str, *reasons: str) -> None:
        self.nodeid = nodeid
        self._markers = [
            pytest.mark.campaign_excluded(reason=reason).mark for reason in reasons
        ]

    def iter_markers(self, name: str) -> list[Any]:
        assert name == "campaign_excluded"
        return self._markers


def _write_manifest(path: Path, entries: list[dict[str, str]]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "suites": {
                    "backend": {
                        "runner": "pytest",
                        "root": "backend",
                        "excluded": entries,
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_checked_in_backend_manifest_is_exact_and_reasoned() -> None:
    exclusions = load_backend_exclusions(MANIFEST_PATH)

    assert len(exclusions) == 110
    assert set(exclusions.values()) == ALLOWED_EXCLUSION_REASONS


def test_manifest_loader_rejects_duplicate_nodeids(tmp_path: Path) -> None:
    path = tmp_path / "scope.json"
    entry = {"nodeid": "tests/test_example.py::test_case", "reason": "parsl"}
    _write_manifest(path, [entry, entry])

    with pytest.raises(ValueError, match="duplicate backend nodeids"):
        load_backend_exclusions(path)


def test_collection_audit_returns_exact_partition() -> None:
    selected_item = _Item("tests/test_local.py::test_local")
    excluded_item = _Item("tests/test_remote.py::test_remote", "managed-remote")

    selected, excluded = audit_backend_collection(
        [selected_item, excluded_item],
        {excluded_item.nodeid: "managed-remote"},
    )

    assert selected == [selected_item]
    assert excluded == [excluded_item]


@pytest.mark.parametrize(
    ("items", "manifest", "message"),
    [
        (
            [_Item("tests/test_local.py::test_local")],
            {"tests/test_missing.py::test_missing": "parsl"},
            "manifest nodeids missing from collection",
        ),
        (
            [
                _Item("tests/test_local.py::test_local"),
                _Item("tests/test_remote.py::test_remote", "managed-remote"),
            ],
            {},
            "marked nodeids missing from manifest",
        ),
        (
            [
                _Item("tests/test_local.py::test_local"),
                _Item("tests/test_remote.py::test_remote"),
            ],
            {"tests/test_remote.py::test_remote": "managed-remote"},
            "missing campaign_excluded markers",
        ),
        (
            [
                _Item("tests/test_local.py::test_local"),
                _Item("tests/test_remote.py::test_remote", "distributed-engine"),
            ],
            {"tests/test_remote.py::test_remote": "managed-remote"},
            "reason drift",
        ),
        (
            [_Item("tests/test_remote.py::test_remote", "managed-remote")],
            {"tests/test_remote.py::test_remote": "managed-remote"},
            "zero tests",
        ),
        (
            [
                _Item("tests/test_local.py::test_local"),
                _Item("tests/test_remote.py::test_remote", "parsl", "parsl"),
            ],
            {"tests/test_remote.py::test_remote": "parsl"},
            "expected one campaign_excluded marker",
        ),
    ],
)
def test_collection_audit_rejects_scope_drift(
    items: list[Any], manifest: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        audit_backend_collection(items, manifest)
