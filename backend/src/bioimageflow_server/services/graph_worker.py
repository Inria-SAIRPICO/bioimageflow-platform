"""Bounded worker boundary for graph compilation and validation."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from anyio import to_thread

ResultT = TypeVar("ResultT")


async def run_graph_work(operation: Callable[[], ResultT]) -> ResultT:
    """Run blocking graph work under AnyIO's bounded thread limiter."""

    return await to_thread.run_sync(operation)
