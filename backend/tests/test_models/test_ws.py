"""Tests for WebSocket message Pydantic models."""

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from bioimageflow_server.models.ws import (
    AckMessage,
    ClientMessage,
    EnvironmentStatusMessage,
    ErrorMessage,
    ExecutionCompleteMessage,
    LogMessage,
    NodeStateMessage,
    PackageInstallMessage,
    ProgressMessage,
    ServerMessage,
    SubscribeLogsMessage,
    SystemErrorMessage,
    ToolReloadMessage,
    ToolRemovedMessage,
)


class TestProgressMessage:
    def test_construction(self) -> None:
        msg = ProgressMessage(
            node_id="n1",
            status="running",
            row=5,
            total_rows=10,
            timestamp=123.456,
        )
        assert msg.type == "progress"
        assert msg.node_id == "n1"
        assert msg.status == "running"
        assert msg.row == 5
        assert msg.total_rows == 10
        assert msg.timestamp == 123.456

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            ProgressMessage(
                node_id="n1",
                status="running",
                row=1,
                total_rows=10,
                timestamp=0.0,
                bogus="x",
            )


class TestNodeStateMessage:
    def test_all_statuses(self) -> None:
        for status in (
            "unexecuted",
            "executed",
            "out_of_date",
            "disabled",
            "running",
            "failed",
        ):
            msg = NodeStateMessage(node_id="n1", status=status, cached=False)
            assert msg.status == status

    def test_invalid_status(self) -> None:
        with pytest.raises(ValidationError):
            NodeStateMessage(node_id="n1", status="bogus", cached=False)

    def test_defaults(self) -> None:
        msg = NodeStateMessage(node_id="n1", status="running", cached=False)
        assert msg.error is None
        assert msg.traceback is None
        assert msg.type == "node_state"

    def test_with_error(self) -> None:
        msg = NodeStateMessage(
            node_id="n1",
            status="failed",
            cached=False,
            error="bad",
            traceback="tb",
        )
        assert msg.error == "bad"
        assert msg.traceback == "tb"


class TestLogMessage:
    def test_without_node_id(self) -> None:
        msg = LogMessage(level="INFO", message="hello", timestamp=1.0)
        assert msg.type == "log"
        assert msg.node_id is None

    def test_with_node_id(self) -> None:
        msg = LogMessage(
            level="WARNING",
            message="watch out",
            node_id="segmenter_1",
            timestamp=2.0,
        )
        assert msg.node_id == "segmenter_1"


class TestExecutionCompleteMessage:
    def test_success(self) -> None:
        msg = ExecutionCompleteMessage(success=True, node_statuses={})
        assert msg.type == "execution_complete"
        assert msg.success is True
        assert msg.errors == []

    def test_failure_with_errors(self) -> None:
        msg = ExecutionCompleteMessage(
            success=False,
            errors=[{"node_id": "n1", "error": "boom"}],
            node_statuses={"n1": {"status": "failed", "cached": False}},
        )
        assert msg.success is False
        assert len(msg.errors) == 1
        assert msg.node_statuses["n1"]["status"] == "failed"


class TestToolReloadMessage:
    def test_construction(self) -> None:
        msg = ToolReloadMessage(
            tool_name="my_tool",
            tool_metadata={"name": "my_tool", "display_name": "MT"},
        )
        assert msg.type == "tool_reload"
        assert msg.tool_name == "my_tool"
        assert msg.tool_metadata["display_name"] == "MT"


class TestToolRemovedMessage:
    def test_construction(self) -> None:
        msg = ToolRemovedMessage(tool_name="GaussianSmooth")
        assert msg.type == "tool_removed"
        assert msg.tool_name == "GaussianSmooth"

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            ToolRemovedMessage(tool_name="GaussianSmooth", bogus="x")


class TestSystemErrorMessage:
    def test_construction(self) -> None:
        msg = SystemErrorMessage(
            code="tool_reload_failed",
            detail="syntax error in foo.py",
            timestamp=1.0,
        )
        assert msg.type == "system_error"
        assert msg.code == "tool_reload_failed"
        assert msg.detail == "syntax error in foo.py"
        assert msg.timestamp == 1.0

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            SystemErrorMessage(
                code="c", detail="d", timestamp=0.0, bogus="x"
            )


class TestPackageInstallMessage:
    def test_statuses(self) -> None:
        for status in ("installing", "complete", "failed"):
            msg = PackageInstallMessage(package_name="pkg", status=status)
            assert msg.status == status

    def test_invalid_status(self) -> None:
        with pytest.raises(ValidationError):
            PackageInstallMessage(package_name="pkg", status="bogus")

    def test_with_detail(self) -> None:
        msg = PackageInstallMessage(
            package_name="pkg", status="failed", detail="network"
        )
        assert msg.detail == "network"


class TestEnvironmentStatusMessage:
    def test_statuses(self) -> None:
        for status in ("stopped", "creating", "running"):
            msg = EnvironmentStatusMessage(env_name="napari", status=status)
            assert msg.status == status

    def test_invalid_status(self) -> None:
        with pytest.raises(ValidationError):
            EnvironmentStatusMessage(env_name="napari", status="bogus")


class TestAckMessage:
    def test_construction(self) -> None:
        msg = AckMessage(ref="abc-123")
        assert msg.type == "ack"
        assert msg.ref == "abc-123"


class TestErrorMessage:
    def test_with_ref(self) -> None:
        msg = ErrorMessage(ref="r1", code="invalid_payload", detail="bad json")
        assert msg.type == "error"
        assert msg.ref == "r1"
        assert msg.code == "invalid_payload"

    def test_without_ref(self) -> None:
        msg = ErrorMessage(code="unknown", detail="???")
        assert msg.ref is None


class TestSubscribeLogsMessage:
    def test_minimal(self) -> None:
        msg = SubscribeLogsMessage()
        assert msg.type == "subscribe_logs"
        assert msg.message_id is None
        assert msg.node_id is None
        assert msg.level is None

    def test_full(self) -> None:
        msg = SubscribeLogsMessage(
            message_id="m1", node_id="n1", level="WARNING"
        )
        assert msg.message_id == "m1"
        assert msg.node_id == "n1"
        assert msg.level == "WARNING"


class TestServerMessageUnion:
    _adapter = TypeAdapter(ServerMessage)

    def test_dispatch_progress(self) -> None:
        parsed = self._adapter.validate_python(
            {
                "type": "progress",
                "node_id": "n1",
                "status": "running",
                "row": 1,
                "total_rows": 10,
                "timestamp": 0.0,
            }
        )
        assert isinstance(parsed, ProgressMessage)

    def test_dispatch_node_state(self) -> None:
        parsed = self._adapter.validate_python(
            {
                "type": "node_state",
                "node_id": "n1",
                "status": "executed",
                "cached": True,
            }
        )
        assert isinstance(parsed, NodeStateMessage)

    def test_dispatch_log(self) -> None:
        parsed = self._adapter.validate_python(
            {"type": "log", "level": "INFO", "message": "hi", "timestamp": 0.0}
        )
        assert isinstance(parsed, LogMessage)

    def test_dispatch_execution_complete(self) -> None:
        parsed = self._adapter.validate_python(
            {
                "type": "execution_complete",
                "success": True,
                "node_statuses": {},
            }
        )
        assert isinstance(parsed, ExecutionCompleteMessage)

    def test_dispatch_tool_reload(self) -> None:
        parsed = self._adapter.validate_python(
            {
                "type": "tool_reload",
                "tool_name": "x",
                "tool_metadata": {},
            }
        )
        assert isinstance(parsed, ToolReloadMessage)

    def test_dispatch_tool_removed(self) -> None:
        parsed = self._adapter.validate_python(
            {"type": "tool_removed", "tool_name": "x"}
        )
        assert isinstance(parsed, ToolRemovedMessage)

    def test_dispatch_system_error(self) -> None:
        parsed = self._adapter.validate_python(
            {
                "type": "system_error",
                "code": "tool_reload_failed",
                "detail": "boom",
                "timestamp": 0.0,
            }
        )
        assert isinstance(parsed, SystemErrorMessage)

    def test_dispatch_package_install(self) -> None:
        parsed = self._adapter.validate_python(
            {
                "type": "package_install",
                "package_name": "pkg",
                "status": "installing",
            }
        )
        assert isinstance(parsed, PackageInstallMessage)

    def test_dispatch_environment_status(self) -> None:
        parsed = self._adapter.validate_python(
            {
                "type": "environment_status",
                "env_name": "napari",
                "status": "running",
            }
        )
        assert isinstance(parsed, EnvironmentStatusMessage)

    def test_dispatch_ack(self) -> None:
        parsed = self._adapter.validate_python({"type": "ack", "ref": "r1"})
        assert isinstance(parsed, AckMessage)

    def test_dispatch_error(self) -> None:
        parsed = self._adapter.validate_python(
            {"type": "error", "code": "c", "detail": "d"}
        )
        assert isinstance(parsed, ErrorMessage)

    def test_rejects_unknown_type(self) -> None:
        with pytest.raises(ValidationError):
            self._adapter.validate_python({"type": "bogus"})


class TestClientMessageUnion:
    _adapter = TypeAdapter(ClientMessage)

    def test_subscribe_logs(self) -> None:
        parsed = self._adapter.validate_python({"type": "subscribe_logs"})
        assert isinstance(parsed, SubscribeLogsMessage)

    def test_rejects_unknown(self) -> None:
        with pytest.raises(ValidationError):
            self._adapter.validate_python({"type": "bogus"})


class TestJsonRoundTrip:
    @pytest.mark.parametrize(
        "message",
        [
            ProgressMessage(
                node_id="n", status="running", row=1, total_rows=5, timestamp=0.0
            ),
            NodeStateMessage(node_id="n", status="executed", cached=True),
            LogMessage(level="INFO", message="m", timestamp=1.0),
            ExecutionCompleteMessage(
                success=True, node_statuses={"n": {"status": "executed"}}
            ),
            ToolReloadMessage(tool_name="t", tool_metadata={"x": 1}),
            ToolRemovedMessage(tool_name="t"),
            SystemErrorMessage(code="c", detail="d", timestamp=1.0),
            PackageInstallMessage(package_name="p", status="complete"),
            EnvironmentStatusMessage(env_name="e", status="running"),
            AckMessage(ref="r"),
            ErrorMessage(code="c", detail="d"),
            SubscribeLogsMessage(message_id="m", node_id="n", level="INFO"),
        ],
    )
    def test_roundtrip(self, message) -> None:
        dumped = message.model_dump()
        reparsed = type(message).model_validate(dumped)
        assert reparsed == message
        json_str = json.dumps(dumped)
        loaded = json.loads(json_str)
        reparsed_json = type(message).model_validate(loaded)
        assert reparsed_json == message
