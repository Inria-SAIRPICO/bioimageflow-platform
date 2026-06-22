"""Graph validation orchestration.

Thin wrapper that turns a ``GraphState`` into a ``ValidationResult`` by
delegating to :class:`SessionManager` and its underlying
:class:`WorkflowSession`:

* The session manager translates ``GraphState`` to the library dict
  and catches structural errors (duplicate IDs, missing tools, dangling
  edges).
* ``Workflow.validate`` for domain-level checks (cycle, type
  compatibility, missing required inputs, constant Pydantic validation,
  sub-workflow recursion).
* ``Workflow.plan`` for per-node cache status — signature hashes are
  produced by the same code path as execution.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from bioimageflow_server.models.settings import Settings

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.validation import (
    GraphValidationError,
    NodeStatus,
    NodeStatusValue,
    ValidationResult,
)
from bioimageflow_server.services.graph_translator import (
    lib_validation_error_to_graph_error,
)
from bioimageflow_server.services.session_manager import SessionManager
from bioimageflow_server.services.tool_registry import ToolRegistryService

logger = logging.getLogger(__name__)


# Map library NodePlanStatus string values to the platform's status labels.
_PLAN_STATUS_MAP: dict[str, tuple[NodeStatusValue, bool]] = {
    "cached": ("executed", True),
    "out_of_date": ("out_of_date", False),
    "prior_selection_miss": ("out_of_date", False),
    "unexecuted": ("unexecuted", False),
    # Skipped-but-not-disabled means downstream of a disabled node.
    # Preserve the prior platform behavior of reporting these as
    # ``unexecuted`` rather than ``disabled`` (which is reserved for
    # explicit ``NodeState.enabled=False``).
    "skipped": ("unexecuted", False),
    "pending_upstream": ("unexecuted", False),
}


def _build_validation_result(
    session_manager: SessionManager,
    all_node_ids: Iterable[str],
    dev_mode: bool,
) -> ValidationResult:
    """Shared validation logic used by both full-graph and PATCH paths.

    Reads errors, plan, and disabled-node state from the session manager
    and its underlying :class:`WorkflowSession`.
    """
    from bioimageflow import CycleInWorkflowError

    errors: list[GraphValidationError] = list(session_manager.translation_errors)

    node_statuses: dict[str, NodeStatus] = {}
    for nid in session_manager.disabled_node_ids:
        node_statuses[nid] = NodeStatus(node_id=nid, status="disabled", cached=False)

    session = session_manager.session
    if session is not None:
        wf = session.to_workflow()

        # Merge build-time errors and domain-level errors; deduplicate.
        lib_errors = list(wf.errors) + list(wf.validate(dev_mode=dev_mode))
        has_cycle = False
        seen_keys: set[tuple] = set()
        for err in lib_errors:
            key = (err.path, err.node, err.field, err.kind, err.message, err.edge_id)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if err.kind == "cycle":
                has_cycle = True
            errors.append(lib_validation_error_to_graph_error(err))

        if not has_cycle:
            try:
                plans = wf.plan(dev_mode=dev_mode)
            except CycleInWorkflowError:
                plans = {}
            for nid, node_plan in plans.items():
                if nid in node_statuses:
                    continue
                status_str = str(node_plan.status.value)
                status_label, cached = _PLAN_STATUS_MAP.get(
                    status_str, ("unexecuted", False),
                )
                node_statuses[nid] = NodeStatus(
                    node_id=nid,
                    status=status_label,
                    cached=cached,
                    result_key=getattr(node_plan, "final_result_key", None),
                    record_id=getattr(node_plan, "selected_record_id", None),
                )

    # Fill in ``unexecuted`` for nodes not covered above.
    for nid in all_node_ids:
        if nid in node_statuses:
            continue
        node_statuses[nid] = NodeStatus(
            node_id=nid, status="unexecuted", cached=False,
        )

    return ValidationResult(
        valid=not errors,
        node_statuses=node_statuses,
        errors=errors,
    )


def validate_graph(
    graph: GraphState,
    registry: ToolRegistryService,
    session_manager: SessionManager,
    storage_path: Path | None = None,
    dev_mode: bool = True,
    settings: "Settings | None" = None,
) -> ValidationResult:
    """Run full validation on ``graph`` via the session manager.

    Loads the graph into the session (replacing any prior session),
    then reads errors and plan from the cached session.
    """
    session_manager.load(
        graph, registry, storage_path=storage_path, settings=settings
    )
    return _build_validation_result(
        session_manager,
        all_node_ids=[n.id for n in graph.nodes],
        dev_mode=dev_mode,
    )


def patch_session_constants(
    node_id: str,
    parameters: dict[str, Any],
    session_manager: SessionManager,
    dev_mode: bool = True,
) -> ValidationResult:
    """Apply constant edits via the session and return full validation.

    Uses :meth:`WorkflowSession.set_constant` for each field — a
    non-structural edit that does NOT trigger tool re-resolution.
    """
    session = session_manager.session
    if session is None:
        raise RuntimeError("No active session")

    for field_name, value in parameters.items():
        session.set_constant(node_id, field_name, value)

    return _build_validation_result(
        session_manager,
        all_node_ids=list(session.nodes.keys()),
        dev_mode=dev_mode,
    )


def _is_binding_shape(value: Any) -> bool:
    """Return True if *value* looks like a serialised ``ColumnRef`` binding."""
    if not isinstance(value, dict):
        return False
    return "node_id" in value and "output" in value


def _status_from_disk(
    storage_path: Path | None,
    node_id: str,
) -> Literal["unexecuted", "out_of_date"]:
    """Return a conservative status for PATCH fallback validation.

    Used only by :func:`validate_parameters` (the PATCH fallback) which
    has no workflow context to call ``plan()``. The clean library API no
    longer exposes cache directory helpers, so this fallback does not
    inspect storage internals.
    """
    return "unexecuted"


def validate_parameters(
    node_id: str,
    tool_name: str,
    parameters: dict[str, Any],
    registry: ToolRegistryService,
    storage_path: Path | None = None,
    dev_mode: bool = True,
) -> ValidationResult:
    """Validate a single node's parameters in isolation (PATCH fallback).

    Used when no session is loaded. Uses
    :func:`bioimageflow.validation.validate_parameters` for per-field
    Pydantic checks. Cache status is computed conservatively from disk
    presence only.
    """
    from bioimageflow.validation import validate_parameters as lib_validate_parameters

    errors: list[GraphValidationError] = []

    binding_rejected = False
    for field_name, value in parameters.items():
        if _is_binding_shape(value):
            binding_rejected = True
            errors.append(
                GraphValidationError(
                    type="parameter_invalid",
                    detail=(
                        "PATCH accepts constant parameters only; use PUT /graph "
                        "to modify connections"
                    ),
                    node=node_id,
                    field=field_name,
                )
            )

    metadata = registry.get_tool(tool_name)
    if metadata is None:
        errors.append(
            GraphValidationError(
                type="missing_tool",
                detail=f"Tool '{tool_name}' not found in registry",
                node=node_id,
            )
        )
    elif not binding_rejected:
        tool_class = registry.get_tool_class(tool_name)
        if tool_class is not None:
            for err in lib_validate_parameters(tool_class, parameters, node=node_id):
                errors.append(
                    lib_validation_error_to_graph_error(err)
                )

    status_label = _status_from_disk(storage_path, node_id)
    return ValidationResult(
        valid=not errors,
        node_statuses={
            node_id: NodeStatus(
                node_id=node_id, status=status_label, cached=False,
            )
        },
        errors=errors,
    )
