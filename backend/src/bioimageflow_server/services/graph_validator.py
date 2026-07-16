"""Request-local graph validation and cache-status projection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.validation import (
    GraphValidationError,
    NodeStatus,
    NodeStatusValue,
    ValidationResult,
)
from bioimageflow_server.services.graph_builder import BuildOutput
from bioimageflow_server.services.graph_compiler import GraphCompiler
from bioimageflow_server.services.graph_worker import run_graph_work
from bioimageflow_server.services.graph_translator import (
    lib_validation_error_to_graph_error,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService

if TYPE_CHECKING:
    from bioimageflow_server.models.settings import Settings


_PLAN_STATUS_MAP: dict[str, tuple[NodeStatusValue, bool]] = {
    "cached": ("executed", True),
    "out_of_date": ("out_of_date", False),
    "prior_selection_miss": ("out_of_date", False),
    "unexecuted": ("unexecuted", False),
    "skipped": ("unexecuted", False),
    "pending_upstream": ("unexecuted", False),
}


@dataclass(frozen=True)
class GraphValidationOutput:
    """A compiled request graph and the validation derived from it."""

    compilation: BuildOutput
    validation: ValidationResult


def _error_key(error: GraphValidationError) -> tuple[Any, ...]:
    return (
        error.type,
        error.detail,
        error.node,
        error.edge_id,
        error.field,
    )


def _append_unique_error(
    errors: list[GraphValidationError],
    seen: set[tuple[Any, ...]],
    error: GraphValidationError,
) -> None:
    key = _error_key(error)
    if key not in seen:
        errors.append(error)
        seen.add(key)


def _validation_from_compilation(
    graph: GraphState,
    compilation: BuildOutput,
    *,
    dev_mode: bool,
) -> ValidationResult:
    """Derive validation and statuses from one request-local compilation."""
    from bioimageflow import CycleInWorkflowError

    errors: list[GraphValidationError] = []
    seen_errors: set[tuple[Any, ...]] = set()
    for error in compilation.errors:
        _append_unique_error(errors, seen_errors, error)

    workflow = compilation.workflow
    if workflow is not None:
        for library_error in [*workflow.errors, *workflow.validate(dev_mode=dev_mode)]:
            _append_unique_error(
                errors,
                seen_errors,
                lib_validation_error_to_graph_error(library_error),
            )

    node_statuses = {
        node_id: NodeStatus(
            node_id=node_id,
            status="disabled",
            cached=False,
        )
        for node_id in compilation.disabled_node_ids
    }

    has_cycle = any(error.type == "cycle_detected" for error in errors)
    if workflow is not None and not has_cycle:
        try:
            plans = workflow.plan(dev_mode=dev_mode)
        except CycleInWorkflowError:
            plans = {}
        for node_id, node_plan in plans.items():
            if node_id in node_statuses:
                continue
            status, cached = _PLAN_STATUS_MAP.get(
                str(node_plan.status.value),
                ("unexecuted", False),
            )
            node_statuses[node_id] = NodeStatus(
                node_id=node_id,
                status=status,
                cached=cached,
                result_key=getattr(node_plan, "final_result_key", None),
                record_id=getattr(node_plan, "selected_record_id", None),
            )

    for node in graph.nodes:
        node_statuses.setdefault(
            node.id,
            NodeStatus(node_id=node.id, status="unexecuted", cached=False),
        )

    return ValidationResult(
        valid=not errors,
        node_statuses=node_statuses,
        errors=errors,
    )


class GraphValidationService:
    """Compile and validate complete graph snapshots without shared sessions."""

    def __init__(
        self,
        registry: ToolRegistryService,
        *,
        compiler: GraphCompiler | None = None,
    ) -> None:
        self._compiler = compiler or GraphCompiler(registry)

    def validate_with_compilation(
        self,
        graph: GraphState,
        *,
        storage_path: Path | None = None,
        dev_mode: bool = True,
        settings: Settings | None = None,
        on_progress: Callable[[Any], None] | None = None,
    ) -> GraphValidationOutput:
        compilation = self._compiler.compile(
            graph,
            storage_path=storage_path,
            on_progress=on_progress,
            settings=settings,
        )
        validation = _validation_from_compilation(
            graph,
            compilation,
            dev_mode=dev_mode,
        )
        return GraphValidationOutput(
            compilation=compilation,
            validation=validation,
        )

    def validate(
        self,
        graph: GraphState,
        *,
        storage_path: Path | None = None,
        dev_mode: bool = True,
        settings: Settings | None = None,
        on_progress: Callable[[Any], None] | None = None,
    ) -> ValidationResult:
        return self.validate_with_compilation(
            graph,
            storage_path=storage_path,
            dev_mode=dev_mode,
            settings=settings,
            on_progress=on_progress,
        ).validation

    async def validate_with_compilation_async(
        self,
        graph: GraphState,
        *,
        storage_path: Path | None = None,
        dev_mode: bool = True,
        settings: Settings | None = None,
        on_progress: Callable[[Any], None] | None = None,
    ) -> GraphValidationOutput:
        """Compile and validate without occupying the application event loop."""

        graph = graph.model_copy(deep=True)
        return await run_graph_work(
            partial(
                self.validate_with_compilation,
                graph,
                storage_path=storage_path,
                dev_mode=dev_mode,
                settings=settings,
                on_progress=on_progress,
            )
        )

    async def validate_async(
        self,
        graph: GraphState,
        *,
        storage_path: Path | None = None,
        dev_mode: bool = True,
        settings: Settings | None = None,
        on_progress: Callable[[Any], None] | None = None,
    ) -> ValidationResult:
        """Validate without occupying the application event loop."""

        graph = graph.model_copy(deep=True)
        return await run_graph_work(
            partial(
                self.validate,
                graph,
                storage_path=storage_path,
                dev_mode=dev_mode,
                settings=settings,
                on_progress=on_progress,
            )
        )


def validate_graph(
    graph: GraphState,
    registry: ToolRegistryService,
    *,
    storage_path: Path | None = None,
    dev_mode: bool = True,
    settings: Settings | None = None,
) -> ValidationResult:
    """Validate one complete graph snapshot in its explicit storage context."""
    return GraphValidationService(registry).validate(
        graph,
        storage_path=storage_path,
        dev_mode=dev_mode,
        settings=settings,
    )
