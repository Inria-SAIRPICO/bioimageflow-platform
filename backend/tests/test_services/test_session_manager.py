"""Tests for :mod:`bioimageflow_server.services.session_manager`."""
# pyright: reportInvalidTypeForm=false
# Rationale: library factory types like ``ImagePath(semantics={...})`` return
# ``Annotated[Path, spec]`` at runtime; pyright can't evaluate them statically.

from pathlib import Path
from typing import Any

import pytest

from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import IOModel, ProcessingTool
from bioimageflow_core.types import ImagePath, Semantic

from bioimageflow_server.models.graph import (
    ColumnRefEdge,
    GraphState,
    NodeState,
)
from bioimageflow_server.models.tools import ToolMetadata
from bioimageflow_server.services.session_manager import SessionManager
from bioimageflow_server.services.tool_registry import ToolRegistryService


# ---- Mock tool classes (module-level so from_dict can re-import) -----------


class _ProcInputs(IOModel):
    input_image: ImagePath(semantics={Semantic.INTENSITY})
    diameter: float = 30.0


class _ProcOutputs(IOModel):
    mask: ImagePath(semantics={Semantic.LABEL})


class MockProcessingTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = _ProcInputs
    Outputs = _ProcOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class _CompatInputs(IOModel):
    mask_input: ImagePath(semantics={Semantic.LABEL})


class _CompatOutputs(IOModel):
    result: ImagePath(semantics={Semantic.LABEL})


class CompatTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = _CompatInputs
    Outputs = _CompatOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


_TOOL_CLASSES: dict[str, type] = {
    "MockProcessingTool": MockProcessingTool,
    "CompatTool": CompatTool,
}


def _meta(name: str) -> ToolMetadata:
    return ToolMetadata(
        name=name,
        display_name=name,
        package="test-package",
        package_version="1.0.0",
        tool_type="ProcessingTool",
    )


@pytest.fixture
def registry() -> ToolRegistryService:
    reg = ToolRegistryService()
    for name, cls in _TOOL_CLASSES.items():
        reg.register_tool(name, _meta(name), tool_class=cls)
    return reg


@pytest.fixture(autouse=True)
def _clear_active_workflow() -> Any:
    from bioimageflow.node import set_active_workflow

    set_active_workflow(None)
    yield
    set_active_workflow(None)


# ---- SessionManager skeleton tests -----------------------------------------


class TestSessionManagerLifecycle:
    def test_initial_state_is_empty(self) -> None:
        sm = SessionManager()
        assert sm.session is None
        assert sm.translation_errors == []
        assert sm.disabled_node_ids == set()

    def test_load_creates_session(
        self, registry: ToolRegistryService, tmp_path: Path,
    ) -> None:
        graph = GraphState(
            nodes=[
                NodeState(
                    id="n1", name="n1", tool_name="MockProcessingTool",
                    position=(0, 0), parameters={"input_image": "/a"},
                ),
            ],
            edges=[],
        )
        sm = SessionManager()
        errors = sm.load(graph, registry, storage_path=tmp_path)
        assert sm.session is not None
        assert errors == []

    def test_load_returns_translation_errors(
        self, registry: ToolRegistryService, tmp_path: Path,
    ) -> None:
        graph = GraphState(
            nodes=[
                NodeState(
                    id="n1", name="n1", tool_name="NoSuchTool",
                    position=(0, 0), parameters={},
                ),
            ],
            edges=[],
        )
        sm = SessionManager()
        errors = sm.load(graph, registry, storage_path=tmp_path)
        assert len(errors) > 0
        assert any(e.type == "missing_tool" for e in errors)

    def test_load_replaces_existing_session(
        self, registry: ToolRegistryService, tmp_path: Path,
    ) -> None:
        sm = SessionManager()
        g1 = GraphState(
            nodes=[
                NodeState(
                    id="n1", name="n1", tool_name="MockProcessingTool",
                    position=(0, 0), parameters={"input_image": "/a"},
                ),
            ],
            edges=[],
        )
        sm.load(g1, registry, storage_path=tmp_path)
        first_session = sm.session

        g2 = GraphState(
            nodes=[
                NodeState(
                    id="n2", name="n2", tool_name="MockProcessingTool",
                    position=(0, 0), parameters={"input_image": "/b"},
                ),
            ],
            edges=[],
        )
        sm.load(g2, registry, storage_path=tmp_path)
        assert sm.session is not first_session

    def test_clear_drops_session(
        self, registry: ToolRegistryService, tmp_path: Path,
    ) -> None:
        graph = GraphState(
            nodes=[
                NodeState(
                    id="n1", name="n1", tool_name="MockProcessingTool",
                    position=(0, 0), parameters={"input_image": "/a"},
                ),
            ],
            edges=[],
        )
        sm = SessionManager()
        sm.load(graph, registry, storage_path=tmp_path)
        assert sm.session is not None
        sm.clear()
        assert sm.session is None

    def test_disabled_nodes_tracked(
        self, registry: ToolRegistryService, tmp_path: Path,
    ) -> None:
        graph = GraphState(
            nodes=[
                NodeState(
                    id="n1", name="n1", tool_name="MockProcessingTool",
                    position=(0, 0), parameters={"input_image": "/a"},
                    enabled=False,
                ),
            ],
            edges=[],
        )
        sm = SessionManager()
        sm.load(graph, registry, storage_path=tmp_path)
        assert "n1" in sm.disabled_node_ids


class TestSetConstant:
    """Verify keystroke-rate constant edits via set_constant."""

    def test_set_constant_does_not_re_resolve_tools(
        self, registry: ToolRegistryService, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The load-bearing contract: after the initial to_workflow() build,
        a set_constant + validate/plan cycle must NOT trigger any tool
        class resolution."""
        from bioimageflow_server.services.graph_validator import (
            patch_session_constants,
        )

        graph = GraphState(
            nodes=[
                NodeState(
                    id="n1", name="n1", tool_name="MockProcessingTool",
                    position=(0, 0), parameters={"input_image": "/a"},
                ),
            ],
            edges=[],
        )
        sm = SessionManager()
        sm.load(graph, registry, storage_path=tmp_path)

        # Force the initial workflow build so the cache is warm.
        sm.session.to_workflow()

        # Spy on tool resolution.
        from bioimageflow import workflow as wf_mod

        calls: list[tuple] = []
        original = wf_mod.Workflow._resolve_tool_instance

        def tracking(self_wf, *args, **kwargs):  # type: ignore[no-untyped-def]
            calls.append((args, kwargs))
            return original(self_wf, *args, **kwargs)

        monkeypatch.setattr(
            wf_mod.Workflow, "_resolve_tool_instance", tracking,
        )

        # Apply a constant edit through the session.
        result = patch_session_constants(
            "n1", {"diameter": 42.0}, sm, dev_mode=True,
        )
        assert result.valid is True
        assert calls == [], (
            "set_constant + validate should NOT trigger tool resolution; "
            f"got {len(calls)} calls"
        )

    def test_set_constant_updates_session_state(
        self, registry: ToolRegistryService, tmp_path: Path,
    ) -> None:
        graph = GraphState(
            nodes=[
                NodeState(
                    id="n1", name="n1", tool_name="MockProcessingTool",
                    position=(0, 0), parameters={"input_image": "/a"},
                ),
            ],
            edges=[],
        )
        sm = SessionManager()
        sm.load(graph, registry, storage_path=tmp_path)
        sm.session.set_constant("n1", "diameter", 99.5)
        node_data = sm.session.nodes["n1"]
        assert node_data["constants"]["diameter"]["value"] == 99.5


class TestSessionHydration:
    """Verify the session round-trips the graph through the translator."""

    def test_session_to_workflow_produces_valid_workflow(
        self, registry: ToolRegistryService, tmp_path: Path,
    ) -> None:
        graph = GraphState(
            nodes=[
                NodeState(
                    id="n1", name="n1", tool_name="MockProcessingTool",
                    position=(0, 0), parameters={"input_image": "/a"},
                ),
            ],
            edges=[],
        )
        sm = SessionManager()
        sm.load(graph, registry, storage_path=tmp_path)
        session = sm.session
        wf = session.to_workflow()
        assert "n1" in wf.nodes

    def test_session_validates_consistently_with_build_workflow(
        self, registry: ToolRegistryService, tmp_path: Path,
    ) -> None:
        """Session's validate() should find the same error kinds as the
        existing build_workflow + wf.validate() path."""
        from bioimageflow_server.services.graph_builder import build_workflow

        graph = GraphState(
            nodes=[
                NodeState(
                    id="src", name="src", tool_name="MockProcessingTool",
                    position=(0, 0), parameters={"input_image": "/a"},
                ),
                NodeState(
                    id="dst", name="dst", tool_name="CompatTool",
                    position=(0, 0), parameters={},
                ),
            ],
            edges=[
                ColumnRefEdge(
                    id="e1", source_node="src", target_node="dst",
                    source_output="mask", target_input="mask_input",
                ),
            ],
        )

        # Existing path
        build = build_workflow(graph, registry, storage_path=tmp_path)
        ref_errors = set()
        if build.workflow is not None:
            for e in build.workflow.validate():
                ref_errors.add(e.kind)

        # Session path
        sm = SessionManager()
        sm.load(graph, registry, storage_path=tmp_path)
        session_errors = {e.kind for e in sm.session.validate()}

        assert session_errors == ref_errors

    def test_session_plan_matches_build_workflow_plan(
        self, registry: ToolRegistryService, tmp_path: Path,
    ) -> None:
        graph = GraphState(
            nodes=[
                NodeState(
                    id="n1", name="n1", tool_name="MockProcessingTool",
                    position=(0, 0), parameters={"input_image": "/a"},
                ),
            ],
            edges=[],
        )
        sm = SessionManager()
        sm.load(graph, registry, storage_path=tmp_path)
        plan = sm.session.plan()
        assert "n1" in plan

    def test_two_node_connected_graph_round_trips(
        self, registry: ToolRegistryService, tmp_path: Path,
    ) -> None:
        graph = GraphState(
            nodes=[
                NodeState(
                    id="src", name="src", tool_name="MockProcessingTool",
                    position=(0, 0), parameters={"input_image": "/a"},
                ),
                NodeState(
                    id="dst", name="dst", tool_name="CompatTool",
                    position=(0, 0), parameters={},
                ),
            ],
            edges=[
                ColumnRefEdge(
                    id="e1", source_node="src", target_node="dst",
                    source_output="mask", target_input="mask_input",
                ),
            ],
        )
        sm = SessionManager()
        sm.load(graph, registry, storage_path=tmp_path)
        wf = sm.session.to_workflow()
        assert "src" in wf.nodes
        assert "dst" in wf.nodes
