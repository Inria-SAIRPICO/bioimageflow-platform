"""Strict manifest validation for the local-platform pytest campaign."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

import pytest


ALLOWED_EXCLUSION_REASONS = frozenset(
    {"parallel-scheduling", "parsl", "managed-remote", "distributed-engine"}
)
MANIFEST_PATH = Path(__file__).parents[2] / "tests" / "campaign-local-scope.json"


def load_backend_exclusions(path: Path = MANIFEST_PATH) -> dict[str, str]:
    """Load the exact backend pytest exclusion map and reject malformed manifests."""

    try:
        document: Any = json.loads(path.read_text(encoding="utf-8"))
        if document.get("schema_version") != 1:
            raise ValueError("schema_version must be 1")
        suite = document["suites"]["backend"]
        if suite.get("runner") != "pytest" or suite.get("root") != "backend":
            raise ValueError("backend suite must declare pytest with root 'backend'")
        entries = suite["excluded"]
        if not isinstance(entries, list):
            raise ValueError("backend excluded must be a list")
    except (AttributeError, KeyError, OSError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot load campaign manifest {path}: {error}") from error

    nodeids: list[str] = []
    exclusions: dict[str, str] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"nodeid", "reason"}:
            raise ValueError(
                f"backend excluded entry {index} must contain only nodeid and reason"
            )
        nodeid = entry["nodeid"]
        reason = entry["reason"]
        if not isinstance(nodeid, str) or not nodeid:
            raise ValueError(f"backend excluded entry {index} has an invalid nodeid")
        if reason not in ALLOWED_EXCLUSION_REASONS:
            raise ValueError(
                f"backend excluded entry {nodeid!r} has invalid reason {reason!r}"
            )
        nodeids.append(nodeid)
        exclusions[nodeid] = reason

    duplicates = sorted(nodeid for nodeid, count in Counter(nodeids).items() if count > 1)
    if duplicates:
        raise ValueError(f"campaign manifest has duplicate backend nodeids: {duplicates}")
    return exclusions


def audit_backend_collection(
    items: list[pytest.Item], manifest: dict[str, str]
) -> tuple[list[pytest.Item], list[pytest.Item]]:
    """Validate collected markers exactly, returning selected and excluded items."""

    errors: list[str] = []
    collected_ids = [item.nodeid for item in items]
    duplicate_collected = sorted(
        nodeid for nodeid, count in Counter(collected_ids).items() if count > 1
    )
    if duplicate_collected:
        errors.append(f"duplicate collected nodeids: {duplicate_collected}")

    marked: dict[str, str] = {}
    excluded: list[pytest.Item] = []
    for item in items:
        markers = list(item.iter_markers("campaign_excluded"))
        if not markers:
            continue
        if len(markers) != 1:
            errors.append(f"{item.nodeid}: expected one campaign_excluded marker")
            continue
        marker = markers[0]
        if marker.args or set(marker.kwargs) != {"reason"}:
            errors.append(
                f"{item.nodeid}: campaign_excluded requires only reason=<allowed reason>"
            )
            continue
        reason = marker.kwargs["reason"]
        if reason not in ALLOWED_EXCLUSION_REASONS:
            errors.append(f"{item.nodeid}: invalid exclusion reason {reason!r}")
            continue
        marked[item.nodeid] = reason
        excluded.append(item)

    collected = set(collected_ids)
    missing = sorted(set(manifest) - collected)
    unmanifested = sorted(set(marked) - set(manifest))
    unmarked = sorted(set(manifest) & collected - set(marked))
    drift = sorted(
        f"{nodeid}: marker={marked[nodeid]!r}, manifest={manifest[nodeid]!r}"
        for nodeid in set(marked) & set(manifest)
        if marked[nodeid] != manifest[nodeid]
    )
    if missing:
        errors.append(f"manifest nodeids missing from collection: {missing}")
    if unmanifested:
        errors.append(f"marked nodeids missing from manifest: {unmanifested}")
    if unmarked:
        errors.append(f"manifest nodeids missing campaign_excluded markers: {unmarked}")
    if drift:
        errors.append(f"campaign exclusion reason drift: {drift}")

    selected = [item for item in items if item.nodeid not in marked]
    if not selected:
        errors.append("campaign selection contains zero tests")
    if errors:
        raise ValueError("invalid backend local campaign scope:\n- " + "\n- ".join(errors))
    return selected, excluded
