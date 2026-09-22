from __future__ import annotations

from types import SimpleNamespace

import pytest

from bioimageflow_server.services.environment_logging import (
    environment_log_entry,
    log_environment_operation_event,
)


def _event(**changes: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "kind": SimpleNamespace(value="output"),
        "state": SimpleNamespace(value="running"),
        "timestamp": 42.5,
        "message": "fallback message",
        "line": "pixi line",
        "stream": "stderr",
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_output_uses_the_exact_pixi_line_and_event_timestamp() -> None:
    entry = environment_log_entry(_event())

    assert entry is not None
    assert entry.level == "INFO"
    assert entry.message == "pixi line"
    assert entry.timestamp == 42.5


@pytest.mark.parametrize(
    ("kind", "state", "expected_level"),
    [
        ("cleanup", "running", "INFO"),
        ("cancellation_requested", "running", "WARNING"),
        ("state", "failed", "ERROR"),
    ],
)
def test_every_operation_kind_gets_an_appropriate_level(
    kind: str, state: str, expected_level: str
) -> None:
    entry = environment_log_entry(
        _event(
            kind=SimpleNamespace(value=kind),
            state=SimpleNamespace(value=state),
            line=None,
            message=f"{kind} message",
        )
    )

    assert entry is not None
    assert entry.level == expected_level
    assert entry.message == f"{kind} message"


def test_streamed_environment_logger_includes_owner_and_repairs_mojibake(
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = _event(line="Downloading package â”‚ 1/2")

    with caplog.at_level("INFO", logger="bioimageflow.environment"):
        log_environment_operation_event(event, owner="Environment atlas")

    assert caplog.messages == ["Environment atlas: Downloading package │ 1/2"]
