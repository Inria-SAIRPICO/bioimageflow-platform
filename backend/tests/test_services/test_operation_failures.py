"""Managed-environment operation failure rendering tests."""

from types import SimpleNamespace

from bioimageflow_server.services.operation_failures import (
    normalize_operation_text,
    operation_failure_detail,
)


def test_normalize_operation_text_repairs_windows_utf8_mojibake() -> None:
    value = 'Error: Ã— expected a version specifier\n â•­â”€ python = "==3.12.*"'

    assert normalize_operation_text(value) == (
        'Error: × expected a version specifier\n ╭─ python = "==3.12.*"'
    )


def test_normalize_operation_text_preserves_ordinary_unicode() -> None:
    assert normalize_operation_text("Échec à l’étape de résolution") == (
        "Échec à l’étape de résolution"
    )


def test_operation_failure_detail_repairs_windows_stderr_tail() -> None:
    failure = SimpleNamespace(
        message="Provisioning failed",
        stage="conda_install",
        step_id="pixi-install",
        command="pixi install",
        returncode=1,
        stderr_tail=(
            "Error: Ã— expected a version specifier",
            ' â”‚ python = "==3.12.*"',
        ),
        stdout_tail=(),
        cleanup_error=None,
    )
    error = RuntimeError("provisioning failed")
    error.failure = failure  # type: ignore[attr-defined]

    detail = operation_failure_detail(error)

    assert detail is not None
    assert "Error: × expected a version specifier" in detail
    assert ' │ python = "==3.12.*"' in detail
    assert "Ã" not in detail
    assert "â”" not in detail
