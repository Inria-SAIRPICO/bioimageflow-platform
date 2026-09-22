"""Render structured managed-environment failure detail from Wetlands errors."""

from __future__ import annotations

MAX_TAIL_LINES = 20
_WINDOWS_UTF8_MOJIBAKE_MARKERS = ("Ã", "Â", "â", "ð", "�")


def normalize_operation_text(value: str) -> str:
    """Repair UTF-8 subprocess output decoded as Windows-1252.

    Wetlands 2.4 captures provisioning subprocesses in text mode without an
    explicit encoding. On Windows that can decode Pixi's UTF-8 diagnostics
    with the active ANSI code page before the platform receives them. Only
    accept the reversible repair when it reduces characteristic mojibake, so
    ordinary localized output is preserved.
    """

    if not any(marker in value for marker in _WINDOWS_UTF8_MOJIBAKE_MARKERS):
        return value
    try:
        repaired = value.encode("cp1252").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return value
    original_score = sum(value.count(marker) for marker in _WINDOWS_UTF8_MOJIBAKE_MARKERS)
    repaired_score = sum(
        repaired.count(marker) for marker in _WINDOWS_UTF8_MOJIBAKE_MARKERS
    )
    return repaired if repaired_score < original_score else value


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
    parts = [
        normalize_operation_text(str(getattr(failure, "message", "") or type(exc).__name__))
    ]
    stage, step_id = getattr(failure, "stage", None), getattr(failure, "step_id", None)
    if stage or step_id:
        parts.append(f"step: {stage or '?'}/{step_id or '?'}")
    command = getattr(failure, "command", None)
    if command:
        parts.append(f"command: {normalize_operation_text(str(command))}")
    returncode = getattr(failure, "returncode", None)
    if returncode is not None:
        parts.append(f"exit code: {returncode}")
    for label in ("stderr", "stdout"):
        tail = getattr(failure, f"{label}_tail", ()) or ()
        if tail:
            lines = "\n".join(
                normalize_operation_text(str(line)) for line in tail[-MAX_TAIL_LINES:]
            )
            parts.append(f"{label} (last {min(len(tail), MAX_TAIL_LINES)} lines):\n{lines}")
    cleanup = getattr(failure, "cleanup_error", None)
    if cleanup:
        parts.append(f"cleanup: {normalize_operation_text(str(cleanup))}")
    return "\n".join(parts)
