"""Translate a GUI ``GraphState`` into a :class:`bioimageflow.Workflow`.

Thin adapter over :func:`graph_state_to_lib_dict` +
:meth:`bioimageflow.Workflow.from_dict`. The platform is not responsible
for graph semantics -- cycle detection, type compatibility, missing
required inputs, and signature hashing all live in the library. See
:mod:`graph_translator` for the wire-format translation.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.validation import GraphValidationError
from bioimageflow_server.services.graph_translator import (
    graph_state_to_lib_dict,
    lib_validation_error_to_graph_error,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService


class BuildOutput(NamedTuple):
    """Return type of :func:`build_workflow`."""

    workflow: Any
    errors: list[GraphValidationError]
    disabled_node_ids: set[str]


def build_workflow(
    graph: GraphState,
    registry: ToolRegistryService,
    storage_path: Path | None = None,
    on_progress: Callable[[Any], None] | None = None,
) -> BuildOutput:
    """Translate ``graph`` into a library :class:`Workflow`.

    Returns a ``(workflow, errors, disabled_node_ids)`` tuple. The
    workflow is always non-None (``validate_only=True, partial=True``).
    """
    from bioimageflow.workflow import Workflow

    translation = graph_state_to_lib_dict(
        graph, registry, storage_path=storage_path,
    )
    errors: list[GraphValidationError] = list(translation.errors)

    result = Workflow.from_dict(
        translation.lib_dict,
        validate_only=True,
        partial=True,
        storage_path_override=storage_path,
        on_progress=on_progress,
        use_wetlands=False,
        auto_install=False,
    )
    assert isinstance(result, tuple)
    workflow, lib_errors = result

    errors.extend(lib_validation_error_to_graph_error(e) for e in lib_errors)
    disabled = {n.id for n in graph.nodes if not n.enabled}

    return BuildOutput(workflow, errors, disabled)
