"""Adapt public library output planning without duplicating its resolver."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bioimageflow_server.models.output_planning import OutputPlanningReport


def public_planning_errors(error: BaseException) -> list[Any]:
    """Find typed planning failures, including parallel failure groups."""
    from bioimageflow.output_planning import OutputPlanningError

    found: list[Any] = []
    seen: set[int] = set()

    def visit(current: BaseException) -> None:
        if id(current) in seen:
            return
        seen.add(id(current))
        if isinstance(current, OutputPlanningError):
            found.append(current)
        if isinstance(current, BaseExceptionGroup):
            for nested in current.exceptions:
                visit(nested)
        if current.__cause__ is not None:
            visit(current.__cause__)
        elif current.__context__ is not None:
            visit(current.__context__)

    visit(error)
    return found


def planning_report(
    payload: Mapping[str, Any],
    *,
    correction_available: bool = False,
    unavailable_reason: str | None = None,
) -> OutputPlanningReport:
    return OutputPlanningReport.model_validate({
        **payload,
        "correction_available": correction_available,
        "correction_unavailable_reason": unavailable_reason,
    })


def explanation_only(report: OutputPlanningReport) -> OutputPlanningReport:
    """Retained diagnostics never promise that ephemeral input evidence survives."""
    return report.model_copy(update={
        "correction_available": False,
        "correction_unavailable_reason": (
            "Edit the output template in the workflow and run again. "
            "The original execution's correction inputs are no longer retained."
        ),
    })
