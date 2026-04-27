"""Cache parity tests.

Lock the invariant that ``validate_graph``'s per-node ``cached`` flag
matches what the engine would observe when it runs the same signature
hash lookup. Before the library-adoption refactor, the validator
recomputed signature hashes with a *different* resolved-params shape
from the execution engine — so validation could report ``cached=True``
while execution recomputed (or vice versa). Now both paths go through
``Workflow.plan()`` / ``compute()`` which share a single hash
implementation. These tests guard against regressions.
"""
# pyright: reportInvalidTypeForm=false
# Rationale: library factory types like ``ImagePath(semantics={...})`` return
# ``Annotated[Path, spec]`` at runtime; pyright can't evaluate them statically.

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from bioimageflow.cache import cache_save
from bioimageflow.storage import get_node_dir
from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import IOModel, ProcessingTool
from bioimageflow_core.types import ImagePath, Semantic

from bioimageflow_server.models.graph import (
    ColumnRefEdge,
    GraphState,
    NodeState,
)
from bioimageflow_server.models.tools import ToolMetadata
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.graph_validator import validate_graph
from bioimageflow_server.services.session_manager import SessionManager
from bioimageflow_server.services.tool_registry import ToolRegistryService


class _SourceInputs(IOModel):
    input_image: ImagePath(semantics={Semantic.INTENSITY})
    diameter: float = 30.0


class _SourceOutputs(IOModel):
    mask: ImagePath(semantics={Semantic.LABEL})


class SourceTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = _SourceInputs
    Outputs = _SourceOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class _MidInputs(IOModel):
    mask_input: ImagePath(semantics={Semantic.LABEL})
    scale: float = 1.0


class _MidOutputs(IOModel):
    result: ImagePath(semantics={Semantic.LABEL})


class MidTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = _MidInputs
    Outputs = _MidOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


@pytest.fixture
def registry() -> ToolRegistryService:
    reg = ToolRegistryService()
    for name, cls in [("SourceTool", SourceTool), ("MidTool", MidTool)]:
        reg.register_tool(
            name,
            ToolMetadata(
                name=name, display_name=name,
                package="test-pkg", package_version="1.0.0",
                tool_type="ProcessingTool",
            ),
            tool_class=cls,
        )
    return reg


@pytest.fixture(autouse=True)
def _clear_active_workflow() -> Any:
    from bioimageflow.node import set_active_workflow

    set_active_workflow(None)
    yield
    set_active_workflow(None)


@pytest.fixture
def session_manager() -> SessionManager:
    return SessionManager()


def _seed_cache(storage_path: Path, registry: ToolRegistryService,
                graph: GraphState, dev_mode: bool) -> None:
    """Populate the cache for every node using ``plan()``'s sig hash."""
    workflow, _errors, _disabled = build_workflow(graph, registry, storage_path=storage_path)
    plans = workflow.plan(dev_mode=dev_mode)
    for nid, node_plan in plans.items():
        if node_plan.skipped or not node_plan.sig_hash:
            continue
        node_dir = get_node_dir(storage_path, nid)
        cache_save(node_dir, node_plan.sig_hash, pd.DataFrame({"x": [1]}))


def _chain_graph() -> GraphState:
    return GraphState(
        nodes=[
            NodeState(id="src", name="src", tool_name="SourceTool",
                      position=(0, 0),
                      parameters={"input_image": "/a", "diameter": 30.0}),
            NodeState(id="mid", name="mid", tool_name="MidTool",
                      position=(0, 0),
                      parameters={"scale": 2.0}),
        ],
        edges=[
            ColumnRefEdge(id="e1", source_node="src", target_node="mid",
                          source_output="mask", target_input="mask_input"),
        ],
    )


@pytest.mark.parametrize("dev_mode", [True, False])
def test_empty_cache_reports_unexecuted(
    registry: ToolRegistryService, session_manager: SessionManager, tmp_path: Path, dev_mode: bool,
) -> None:
    graph = _chain_graph()
    result = validate_graph(graph, registry, session_manager, storage_path=tmp_path, dev_mode=dev_mode)
    assert result.valid is True
    for nid in ("src", "mid"):
        status = result.node_statuses[nid]
        assert status.status == "unexecuted"
        assert status.cached is False


@pytest.mark.parametrize("dev_mode", [True, False])
def test_seeded_cache_reports_executed(
    registry: ToolRegistryService, session_manager: SessionManager, tmp_path: Path, dev_mode: bool,
) -> None:
    """After seeding the cache via the engine's own hash, every node
    must be reported as ``executed``/``cached=True`` by the validator."""
    graph = _chain_graph()
    _seed_cache(tmp_path, registry, graph, dev_mode)

    result = validate_graph(graph, registry, session_manager, storage_path=tmp_path, dev_mode=dev_mode)
    for nid in ("src", "mid"):
        status = result.node_statuses[nid]
        assert status.status == "executed", f"{nid}: {status}"
        assert status.cached is True, f"{nid}: {status}"


@pytest.mark.parametrize("dev_mode", [True, False])
def test_constant_change_invalidates_downstream(
    registry: ToolRegistryService, session_manager: SessionManager, tmp_path: Path, dev_mode: bool,
) -> None:
    """Changing a constant on ``src`` must flip both ``src`` and ``mid``
    off ``cached``; an unchanged chain stays fully cached."""
    graph = _chain_graph()
    _seed_cache(tmp_path, registry, graph, dev_mode)

    # Mutate the upstream node's constant.
    modified = GraphState(
        nodes=[
            NodeState(id="src", name="src", tool_name="SourceTool",
                      position=(0, 0),
                      parameters={"input_image": "/a", "diameter": 99.0}),
            NodeState(id="mid", name="mid", tool_name="MidTool",
                      position=(0, 0),
                      parameters={"scale": 2.0}),
        ],
        edges=graph.edges,
    )

    result = validate_graph(modified, registry, session_manager, storage_path=tmp_path, dev_mode=dev_mode)
    assert result.node_statuses["src"].cached is False
    assert result.node_statuses["mid"].cached is False
    # ``src`` previously had a hash dir on disk → out_of_date.
    assert result.node_statuses["src"].status in {"out_of_date", "unexecuted"}


@pytest.mark.parametrize("dev_mode", [True, False])
def test_unrelated_node_stays_cached(
    registry: ToolRegistryService, session_manager: SessionManager, tmp_path: Path, dev_mode: bool,
) -> None:
    """Changing a downstream node must NOT invalidate its upstream."""
    graph = _chain_graph()
    _seed_cache(tmp_path, registry, graph, dev_mode)

    modified = GraphState(
        nodes=[
            NodeState(id="src", name="src", tool_name="SourceTool",
                      position=(0, 0),
                      parameters={"input_image": "/a", "diameter": 30.0}),
            NodeState(id="mid", name="mid", tool_name="MidTool",
                      position=(0, 0),
                      parameters={"scale": 99.0}),
        ],
        edges=graph.edges,
    )

    result = validate_graph(modified, registry, session_manager, storage_path=tmp_path, dev_mode=dev_mode)
    assert result.node_statuses["src"].status == "executed"
    assert result.node_statuses["src"].cached is True
    assert result.node_statuses["mid"].cached is False
