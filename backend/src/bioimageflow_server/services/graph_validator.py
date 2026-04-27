"""Graph validation orchestration.

Thin wrapper that turns a ``GraphState`` into a ``ValidationResult`` by
delegating to :class:`SessionManager` and its underlying
:class:`WorkflowSession`:

* The session manager translates ``GraphState`` to the library dict
  and catches structural errors (duplicate IDs, missing tools, dangling
  edges).
* :meth:`WorkflowSession.validate` for domain-level checks (cycle,
  type compatibility, missing required inputs, constant Pydantic
  validation, sub-workflow recursion).
* :meth:`WorkflowSession.plan` for per-node cache status — signature
  hashes are produced by the same code path as execution.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.validation import (
    GraphValidationError,
    NodeStatus,
    ValidationResult,
)
from bioimageflow_server.services.graph_translator import (
    lib_validation_error_to_graph_error,
)
from bioimageflow_server.services.session_manager import SessionManager
from bioimageflow_server.services.tool_registry import ToolRegistryService

logger = logging.getLogger(__name__)


def _is_binding_shape(value: Any) -> bool:
    """Return True if *value* looks like a serialised ``ColumnRef`` binding.

    Binding shape is ``{"node_id": ..., "output": ...}``. PATCH endpoints
    reject this because parameter-only patches must carry constants only.
    """
    if not isinstance(value, dict):
        return False
    return "node_id" in value and "output" in value


def _status_from_disk(
    storage_path: Path | None,
    node_id: str,
) -> Literal["unexecuted", "out_of_date"]:
    """Decide ``out_of_date`` vs ``unexecuted`` based on cache presence.

    Used only by :func:`validate_parameters` (the PATCH handler) which
    has no workflow context to call ``plan()``.  For full-graph
    validation, :func:`validate_graph` uses ``NodePlanStatus`` directly.
    """
    if storage_path is None:
        return "unexecuted"
    from bioimageflow.storage import get_node_dir

    node_dir = get_node_dir(storage_path, node_id)
    if node_dir.exists() and any(node_dir.iterdir()):
        return "out_of_date"
    return "unexecuted"


# Map library NodePlanStatus string values to the platform's status labels.
_PLAN_STATUS_MAP: dict[str, tuple[str, bool]] = {
    "cached": ("executed", True),
    "out_of_date": ("out_of_date", False),
    "unexecuted": ("unexecuted", False),
    # Skipped-but-not-disabled means downstream of a disabled node.
    # Preserve the prior platform behavior of reporting these as
    # ``unexecuted`` rather than ``disabled`` (which is reserved for
    # explicit ``NodeState.enabled=False``).
    "skipped": ("unexecuted", False),
}


def validate_graph(
    graph: GraphState,
    registry: ToolRegistryService,
    session_manager: SessionManager,
    storage_path: Path | None = None,
    dev_mode: bool = True,
) -> ValidationResult:
    """Run full validation on ``graph`` via the session manager.

    Loads the graph into the session (replacing any prior session),
    then reads errors and plan from the cached session. Structural
    errors from the translator are merged with domain-level errors
    from the library.
    """
    from bioimageflow import CycleInWorkflowError

    translation_errors = session_manager.load(
        graph, registry, storage_path=storage_path,
    )
    errors: list[GraphValidationError] = list(translation_errors)
    disabled_node_ids = session_manager.disabled_node_ids

    node_statuses: dict[str, NodeStatus] = {}
    for nid in disabled_node_ids:
        node_statuses[nid] = NodeStatus(node_id=nid, status="disabled", cached=False)

    session = session_manager.session
    if session is not None:
        # Use to_workflow() from the session (cached across non-structural
        # edits), then call validate/plan directly with dev_mode — the
        # session's own validate()/plan() don't accept dev_mode.
        wf = session.to_workflow()

        # Merge build-time errors from Workflow.errors (captured during
        # from_dict) and domain-level errors from validate().
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
            errors.append(
                lib_validation_error_to_graph_error(err)
            )

        # plan() raises CycleInWorkflowError on cyclic graphs; skip it
        # when validate() already reported a cycle.
        if not has_cycle:
            try:
                plans = wf.plan(dev_mode=dev_mode)
            except CycleInWorkflowError:
                # Defensive: validate() should have caught this, but
                # guard against race / edge cases.
                plans = {}

            for nid, node_plan in plans.items():
                if nid in node_statuses:
                    continue
                status_str = str(node_plan.status.value)
                status_label, cached = _PLAN_STATUS_MAP.get(
                    status_str, ("unexecuted", False),
                )
                node_statuses[nid] = NodeStatus(
                    node_id=nid, status=status_label, cached=cached,
                )

    # Fill in ``unexecuted`` for nodes that failed to build or for any
    # node not covered above (e.g., cyclic graphs).
    for node in graph.nodes:
        if node.id in node_statuses:
            continue
        node_statuses[node.id] = NodeStatus(
            node_id=node.id, status="unexecuted", cached=False,
        )

    return ValidationResult(
        valid=not errors,
        node_statuses=node_statuses,
        errors=errors,
    )


def validate_parameters(
    node_id: str,
    tool_name: str,
    parameters: dict[str, Any],
    registry: ToolRegistryService,
    storage_path: Path | None = None,
    dev_mode: bool = True,
) -> ValidationResult:
    """Validate a single node's parameters in isolation (PATCH handler).

    Uses :func:`bioimageflow.validation.validate_parameters` for the
    per-field Pydantic checks. Cache status is computed conservatively
    from disk presence only — the upstream context needed for a
    signature hash is not available in a PATCH request.
    """
    from bioimageflow.validation import validate_parameters as lib_validate_parameters

    errors: list[GraphValidationError] = []

    # Reject binding-shaped values (constants only for PATCH).
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
