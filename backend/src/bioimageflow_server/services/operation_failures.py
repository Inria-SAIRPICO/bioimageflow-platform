"""Render structured managed-environment failure detail from Wetlands errors."""

from __future__ import annotations

MAX_TAIL_LINES = 20


def operation_failure_detail(exc: BaseException) -> str | None:
    """Return a readable detail for a Wetlands operation error, or None.

    Wetlands raises errors that carry a structured ``failure`` payload (failing
    step, command, exit code, redacted stdout/stderr tails). ``str(exc)`` alone
    drops all of it, so any code path that reports a managed-environment failure
    should prefer this rendering. Access is duck-typed: platform code does not
    import Wetlands' error classes, and non-Wetlands exceptions return ``None``
    so callers fall back to their own summary.
    """
    failure = getattr(exc, "failure", None)
    if failure is None:
        return None
    parts = [str(getattr(failure, "message", "") or type(exc).__name__)]
    stage, step_id = getattr(failure, "stage", None), getattr(failure, "step_id", None)
    if stage or step_id:
        parts.append(f"step: {stage or '?'}/{step_id or '?'}")
    command = getattr(failure, "command", None)
    if command:
        parts.append(f"command: {command}")
    returncode = getattr(failure, "returncode", None)
    if returncode is not None:
        parts.append(f"exit code: {returncode}")
    for label in ("stderr", "stdout"):
        tail = getattr(failure, f"{label}_tail", ()) or ()
        if tail:
            lines = "\n".join(tail[-MAX_TAIL_LINES:])
            parts.append(f"{label} (last {min(len(tail), MAX_TAIL_LINES)} lines):\n{lines}")
    cleanup = getattr(failure, "cleanup_error", None)
    if cleanup:
        parts.append(f"cleanup: {cleanup}")
    return "\n".join(parts)