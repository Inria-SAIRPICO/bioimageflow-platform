#!/usr/bin/env python3
"""Verify the campaign obligation dashboard against its source inventories."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "docs/developer/platform-test-dashboard.md"
INVENTORIES = (
    ROOT / "docs/developer/coverage-gui.md",
    ROOT / "docs/developer/coverage-workflows.md",
    ROOT / "docs/developer/coverage-runtime.md",
)
DIMENSIONS = ("S", "R", "F", "P", "B")
VALID_STATES = frozenset("VGIBUN")
ID_PATTERN = re.compile(r"(?:GUI|WF|RT)-(?:SHL|EDT|AUT|LIF|REC|SRC|EXE|RES|XCT)-\d{3}")
CELL_PATTERN = re.compile(r"^(?P<state>[VGIBU])$|^N \((?P<reason>[^()]+)\)$")
CONTRACT_PATTERN = re.compile(r"(?:^|; )([SRFPB])=([VGIBUN])(?: \(([^()]+)\))?(?:: (.+?))?(?=; [SRFPB]=|$)")


class VerificationError(Exception):
    """Raised for a dashboard integrity failure."""


def markdown_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_inventory(path: Path) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        cells = markdown_cells(line) if line.startswith("|") else []
        if not cells or not ID_PATTERN.fullmatch(cells[0]):
            continue
        feature_id = cells[0]
        if feature_id in rows:
            raise VerificationError(f"duplicate inventory ID {feature_id} at {path}:{line_number}")
        if len(cells) != 6:
            raise VerificationError(
                f"inventory row {feature_id} at {path}:{line_number} has {len(cells)} columns, expected 6"
            )
        contracts: dict[str, tuple[str, str | None]] = {}
        matches = list(CONTRACT_PATTERN.finditer(cells[-1]))
        if len(matches) != len(DIMENSIONS):
            raise VerificationError(
                f"inventory row {feature_id} at {path}:{line_number} must define S/R/F/P/B contracts"
            )
        for match in matches:
            dimension, state, reason, contract = match.groups()
            if dimension in contracts or state not in VALID_STATES:
                raise VerificationError(f"invalid contract token for {feature_id} dimension {dimension}")
            if state == "N":
                if not reason or contract:
                    raise VerificationError(f"{feature_id} {dimension}=N needs only a concise parenthesized reason")
                contracts[dimension] = (state, reason)
            else:
                if reason or not contract:
                    raise VerificationError(f"{feature_id} {dimension}={state} needs a concrete or delegated contract")
                contracts[dimension] = (state, contract)
        if set(contracts) != set(DIMENSIONS):
            raise VerificationError(f"inventory row {feature_id} has incomplete or duplicate dimensions")
        rows[feature_id] = {
            "path": path,
            "line": line_number,
            "text": line,
            "contracts": contracts,
        }
    return rows


def expected_status(states: list[str]) -> str:
    applicable = [state for state in states if state != "N"]
    if applicable and all(state == "V" for state in applicable):
        return "verified"
    if "B" in applicable:
        return "blocked"
    if "I" in applicable or "V" in applicable:
        return "in-progress"
    if applicable and all(state == "U" for state in applicable):
        return "unassessed"
    return "gap"


def parse_dashboard(inventory_rows: dict[str, dict[str, object]]) -> tuple[list[dict[str, object]], str]:
    text = DASHBOARD.read_text()
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), 1):
        cells = markdown_cells(line) if line.startswith("|") else []
        if not cells or not ID_PATTERN.fullmatch(cells[0]):
            continue
        feature_id = cells[0]
        if feature_id in seen:
            raise VerificationError(f"duplicate dashboard ID {feature_id} at {DASHBOARD}:{line_number}")
        seen.add(feature_id)
        if len(cells) != 12:
            raise VerificationError(
                f"dashboard row {feature_id} at {DASHBOARD}:{line_number} has {len(cells)} columns, expected 12"
            )
        if cells[4] not in {"yes", "no"}:
            raise VerificationError(f"dashboard row {feature_id} has invalid Primary GUI value {cells[4]!r}")
        states: list[str] = []
        for dimension, value in zip(DIMENSIONS, cells[5:10], strict=True):
            match = CELL_PATTERN.fullmatch(value)
            if not match:
                raise VerificationError(f"dashboard row {feature_id} has invalid {dimension} cell {value!r}")
            state = match.group("state") or "N"
            states.append(state)
            source_state, source_detail = inventory_rows[feature_id]["contracts"][dimension]  # type: ignore[index]
            if state != source_state:
                raise VerificationError(
                    f"{feature_id} {dimension} disagrees: dashboard {state}, inventory {source_state}"
                )
            if state == "N" and match.group("reason") != source_detail:
                raise VerificationError(f"{feature_id} {dimension}=N reason differs between dashboard and inventory")
            if state == "B":
                source_text = str(inventory_rows[feature_id]["text"])
                if "Unavailable prerequisite:" not in source_text or "Recovery:" not in source_text:
                    raise VerificationError(
                        f"{feature_id} {dimension}=B requires an actual unavailable prerequisite and recovery step"
                    )
        status = expected_status(states)
        if cells[10] != status:
            raise VerificationError(
                f"dashboard row {feature_id} status is {cells[10]!r}, expected {status!r}"
            )
        if not cells[11]:
            raise VerificationError(f"dashboard row {feature_id} has no evidence revision")
        rows.append({"id": feature_id, "primary": cells[4] == "yes", "states": states})
    return rows, text


def summary_counts(rows: list[dict[str, object]], primary_only: bool) -> Counter[str]:
    return Counter(
        state
        for row in rows
        if not primary_only or row["primary"]
        for state in row["states"]  # type: ignore[union-attr]
    )


def verify_summary(text: str, label: str, counts: Counter[str], row_count: int | None = None) -> None:
    applicable = sum(counts[state] for state in "VGIBU")
    pattern = re.compile(
        rf"- {label}: \*\*(\d+) V \+ (\d+) G \+ (\d+) I \+ (\d+) B \+ (\d+) U = (\d+) applicable obligations\*\*, so \*\*(\d+) / (\d+) are verified \(([0-9]+\.[0-9])%\)\*\*"
    )
    match = pattern.search(text)
    if not match:
        raise VerificationError(f"missing or malformed {label} summary")
    reported = tuple(map(int, match.groups()[:8]))
    expected = (
        counts["V"], counts["G"], counts["I"], counts["B"], counts["U"],
        applicable, counts["V"], applicable,
    )
    if reported != expected:
        raise VerificationError(f"{label} summary {reported} does not match recomputed {expected}")
    reported_percent = match.group(9)
    expected_percent = f"{100 * counts['V'] / applicable:.1f}"
    if reported_percent != expected_percent:
        raise VerificationError(
            f"{label} percentage {reported_percent}% does not match recomputed {expected_percent}%"
        )
    if row_count is not None:
        reconciliation = re.search(
            r"- Inventory reconciliation: (\d+) feature rows, (\d+) scenario decisions, including (\d+) justified `N` decisions\.",
            text,
        )
        expected_reconciliation = (row_count, row_count * len(DIMENSIONS), counts["N"])
        if not reconciliation or tuple(map(int, reconciliation.groups())) != expected_reconciliation:
            raise VerificationError(
                f"inventory reconciliation does not match recomputed {expected_reconciliation}"
            )


def main() -> int:
    try:
        inventory_rows: dict[str, dict[str, object]] = {}
        for path in INVENTORIES:
            for feature_id, row in parse_inventory(path).items():
                if feature_id in inventory_rows:
                    raise VerificationError(f"duplicate inventory ID {feature_id} across source files")
                inventory_rows[feature_id] = row
        dashboard_rows, dashboard_text = parse_dashboard(inventory_rows)
        dashboard_ids = {str(row["id"]) for row in dashboard_rows}
        inventory_ids = set(inventory_rows)
        if dashboard_ids != inventory_ids:
            raise VerificationError(
                f"inventory/dashboard ID mismatch; inventory-only={sorted(inventory_ids - dashboard_ids)}, "
                f"dashboard-only={sorted(dashboard_ids - inventory_ids)}"
            )
        overall = summary_counts(dashboard_rows, primary_only=False)
        primary = summary_counts(dashboard_rows, primary_only=True)
        verify_summary(dashboard_text, "Overall", overall, row_count=len(dashboard_rows))
        verify_summary(dashboard_text, "Primary GUI", primary)
    except (KeyError, VerificationError) as error:
        print(f"dashboard verification failed: {error}", file=sys.stderr)
        return 1
    print(
        "dashboard verification passed: "
        f"{len(dashboard_rows)} rows, {sum(overall[state] for state in 'VGIBU')} applicable, "
        f"{overall['V']} verified; {sum(primary[state] for state in 'VGIBU')} primary, "
        f"{primary['V']} verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
