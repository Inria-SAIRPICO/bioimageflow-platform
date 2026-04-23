"""Graph validation orchestration.

Thin wrapper that turns a ``GraphState`` into a ``ValidationResult`` by
delegating to the library:

* :meth:`bioimageflow.Workflow.validate` for domain-level checks
  (cycle, type compatibility, missing required inputs, constant
  Pydantic validation, sub-workflow recursion).
* :meth:`bioimageflow.Workflow.plan` for per-node cache status —
  signature hashes are produced by the same code path as execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.validation import (
    GraphValidationError,
    NodeStatus,
    ValidationResult,
)
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.graph_translator import (
    lib_validation_error_to_graph_error,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService


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
    sig_hash: str,
) -> Literal["unexecuted", "out_of_date"]:
    """Decide ``out_of_date`` vs ``unexecuted`` based on cache presence.

    Returns ``"unexecuted"`` when no storage path is configured or the
    node directory is empty, ``"out_of_date"`` when the directory has
    prior cache entries but no current hit.
    """
    if storage_path is None:
        return "unexecuted"
    from bioimageflow.storage import get_node_dir

    node_dir = get_node_dir(storage_path, node_id)
    if node_dir.exists() and any(node_dir.iterdir()):
        return "out_of_date"
    return "unexecuted"


def validate_graph(
    graph: GraphState,
    registry: ToolRegistryService,
    storage_path: Path | None = None,
    dev_mode: bool = True,
) -> ValidationResult:
    """Run full validation on ``graph``.

    Errors and node statuses come from the library. The platform only
    adds structural errors (duplicate IDs, unknown edge endpoints,
    unresolved tools), which the translator surfaces.
    """
    build = build_workflow(graph, registry, storage_path=storage_path)
    errors: list[GraphValidationError] = list(build.errors)

    node_statuses: dict[str, NodeStatus] = {}
    for nid in build.disabled_node_ids:
        node_statuses[nid] = NodeStatus(node_id=nid, status="disabled", cached=False)

    has_cycle = False
    if build.workflow is not None:
        lib_errors = build.workflow.validate(dev_mode=dev_mode)
        for err in lib_errors:
            if err.kind == "cycle":
                has_cycle = True
            errors.append(
                lib_validation_error_to_graph_error(err, build.edge_id_by_key)
            )

        # Skip plan() on cyclic graphs — the library returns all-skipped
        # entries in that case, which would wrongly flatten every node's
        # status. Fall back to the disk-based heuristic below.
        if not has_cycle:
            plans = build.workflow.plan(dev_mode=dev_mode)
            for nid, node_plan in plans.items():
                # Already classified as explicitly disabled.
                if nid in node_statuses:
                    continue
                # Treat nodes that fail to build (plan has no entry for them)
                # as ``unexecuted``; handled by the fill-in loop below.
                if node_plan.skipped:
                    # Skipped-but-not-disabled means downstream of a
                    # disabled node. Preserve the prior platform behavior
                    # of reporting these as ``unexecuted`` rather than
                    # ``disabled`` (which is reserved for explicit
                    # ``NodeState.enabled=False``).
                    node_statuses[nid] = NodeStatus(
                        node_id=nid, status="unexecuted", cached=False,
                    )
                    continue
                if node_plan.cached:
                    node_statuses[nid] = NodeStatus(
                        node_id=nid, status="executed", cached=True,
                    )
                else:
                    status = _status_from_disk(storage_path, nid, node_plan.sig_hash)
                    node_statuses[nid] = NodeStatus(
                        node_id=nid, status=status, cached=False,
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
                    lib_validation_error_to_graph_error(err, {})
                )

    status_label = _status_from_disk(storage_path, node_id, "")
    return ValidationResult(
        valid=not errors,
        node_statuses={
            node_id: NodeStatus(
                node_id=node_id, status=status_label, cached=False,
            )
        },
        errors=errors,
    )
