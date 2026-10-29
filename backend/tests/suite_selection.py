"""Keep local and optional distributed feature tests disjoint."""

from typing import TypeVar

import pytest

Item = TypeVar("Item", bound=pytest.Item)


def select_test_suite(items: list[Item], suite: str) -> tuple[list[Item], list[Item]]:
    if suite not in {"local", "distributed", "all"}:
        raise pytest.UsageError(f"Unknown test suite: {suite}")
    selected: list[Item] = []
    deselected: list[Item] = []
    for item in items:
        distributed = item.get_closest_marker("distributed") is not None
        included = suite == "all" or distributed == (suite == "distributed")
        (selected if included else deselected).append(item)
    return selected, deselected
