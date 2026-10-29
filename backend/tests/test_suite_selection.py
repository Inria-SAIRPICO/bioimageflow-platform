from types import SimpleNamespace
from typing import Any

import pytest

from tests.suite_selection import select_test_suite


def test_feature_suites_partition_collection_without_losing_tests() -> None:
    local: Any = SimpleNamespace(get_closest_marker=lambda _: None)
    remote: Any = SimpleNamespace(get_closest_marker=lambda _: pytest.mark.distributed)
    items = [local, remote]

    assert select_test_suite(items, "local") == ([local], [remote])
    assert select_test_suite(items, "distributed") == ([remote], [local])
    assert select_test_suite(items, "all") == (items, [])


def test_unknown_feature_suite_fails_instead_of_running_everything() -> None:
    with pytest.raises(pytest.UsageError, match="Unknown test suite"):
        select_test_suite([], "typo")
