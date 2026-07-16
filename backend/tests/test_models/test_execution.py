"""Tests for the execution Pydantic models."""

import json

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.execution import (
    ExecutionContext,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    ProgressInfo,
)
from bioimageflow_server.models.validation import NodeStatus


class TestExecutionRequest:
    def test_full(self) -> None:
        er = ExecutionRequest(
            graph={"nodes": [], "edges": []},
            nodes=["n1", "n2"],
            workflow_name="wf_a",
            draft_revision=7,
        )
        assert er.graph == {"nodes": [], "edges": []}
        assert er.nodes == ["n1", "n2"]
        assert er.workflow_name == "wf_a"
        assert er.draft_revision == 7

    def test_selective_none(self) -> None:
        er = ExecutionRequest(graph={"nodes": []}, workflow_name="wf_a")
        assert er.nodes is None


class TestExecutionContext:
    def test_roundtrip(self) -> None:
        context = ExecutionContext(
            execution_id="exec-123",
            workflow_id="wf_a",
            draft_revision=7,
        )

        assert ExecutionContext.model_validate(context.model_dump()) == context

    def test_is_immutable(self) -> None:
        context = ExecutionContext(
            execution_id="exec-123",
            workflow_id="wf_a",
            draft_revision=7,
        )

        with pytest.raises(ValidationError):
            context.draft_revision = 8


class TestProgressInfo:
    def test_construction(self) -> None:
        p = ProgressInfo(node_id="n1", row=5, total_rows=100)
        assert p.node_id == "n1"
        assert p.row == 5
        assert p.total_rows == 100


class TestExecutionResult:
    def test_success(self) -> None:
        er = ExecutionResult(success=True)
        assert er.success is True
        assert er.errors == []
        assert er.node_statuses == {}

    def test_failure(self) -> None:
        ns = NodeStatus(node_id="n1", status="failed", cached=False, error="boom")
        er = ExecutionResult(
            success=False,
            errors=[{"node_id": "n1", "message": "boom"}],
            node_statuses={"n1": ns},
        )
        assert er.success is False
        assert len(er.errors) == 1
        assert er.node_statuses["n1"].status == "failed"


class TestExecutionStatus:
    def test_running(self) -> None:
        p = ProgressInfo(node_id="n1", row=3, total_rows=10)
        es = ExecutionStatus(state="running", progress=p)
        assert es.state == "running"
        assert es.last_result is None
        assert es.progress is not None
        assert es.progress.row == 3

    def test_idle(self) -> None:
        result = ExecutionResult(success=True)
        es = ExecutionStatus(state="idle", last_result=result)
        assert es.state == "idle"
        assert es.last_result is not None
        assert es.last_result.success is True

    def test_invalid_state(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionStatus.model_validate({"state": "paused"})

    def test_roundtrip(self) -> None:
        p = ProgressInfo(node_id="n1", row=1, total_rows=5)
        es = ExecutionStatus(state="running", progress=p)
        dumped = json.loads(es.model_dump_json())
        es2 = ExecutionStatus.model_validate(dumped)
        assert es2.state == "running"
        assert es2.progress is not None
        assert es2.progress.node_id == "n1"

    def test_retains_execution_identity_while_idle(self) -> None:
        es = ExecutionStatus(
            state="idle",
            execution_id="exec-123",
            workflow_id="wf_a",
            draft_revision=7,
        )

        assert es.model_dump() | {} == {
            "state": "idle",
            "last_result": None,
            "progress": None,
            "node_statuses": {},
            "execution_id": "exec-123",
            "workflow_id": "wf_a",
            "draft_revision": 7,
        }
