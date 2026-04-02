"""Tests for the validation Pydantic models."""

import json

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.validation import (
    GraphValidationError,
    NodeStatus,
    ValidationResult,
)


class TestNodeStatus:
    def test_minimal(self) -> None:
        ns = NodeStatus(node_id="n1", status="unexecuted", cached=False)
        assert ns.node_id == "n1"
        assert ns.status == "unexecuted"
        assert ns.cached is False
        assert ns.error is None
        assert ns.traceback is None

    def test_failed_with_error(self) -> None:
        ns = NodeStatus(
            node_id="n2",
            status="failed",
            cached=False,
            error="Division by zero",
            traceback="Traceback ...",
        )
        assert ns.error == "Division by zero"
        assert ns.traceback == "Traceback ..."

    def test_all_statuses(self) -> None:
        for s in ("unexecuted", "executed", "out_of_date", "disabled", "running", "failed"):
            ns = NodeStatus(node_id="n", status=s, cached=False)
            assert ns.status == s

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            NodeStatus(node_id="n", status="unknown", cached=False)


class TestGraphValidationError:
    def test_all_fields(self) -> None:
        err = GraphValidationError(
            type="cycle_detected",
            detail="Cycle found",
            node="n1",
            edge_id="e1",
            field="param",
        )
        assert err.type == "cycle_detected"
        assert err.detail == "Cycle found"
        assert err.node == "n1"
        assert err.edge_id == "e1"
        assert err.field == "param"

    def test_all_types(self) -> None:
        types = (
            "cycle_detected",
            "type_incompatible",
            "parameter_invalid",
            "missing_tool",
            "missing_connection",
            "missing_package",
            "invalid_node_id",
            "invalid_edge_id",
        )
        for t in types:
            err = GraphValidationError(type=t, detail="d")
            assert err.type == t

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            GraphValidationError(type="bad_type", detail="d")


class TestValidationResult:
    def test_valid(self) -> None:
        vr = ValidationResult(valid=True)
        assert vr.valid is True
        assert vr.node_statuses == {}
        assert vr.errors == []

    def test_invalid_with_errors(self) -> None:
        ns = NodeStatus(node_id="n1", status="failed", cached=False, error="err")
        err = GraphValidationError(type="cycle_detected", detail="cycle")
        vr = ValidationResult(
            valid=False,
            node_statuses={"n1": ns},
            errors=[err],
        )
        assert vr.valid is False
        assert len(vr.errors) == 1
        assert "n1" in vr.node_statuses

    def test_defaults(self) -> None:
        vr = ValidationResult(valid=True)
        assert vr.node_statuses == {}
        assert vr.errors == []

    def test_roundtrip(self) -> None:
        ns = NodeStatus(node_id="n1", status="executed", cached=True)
        vr = ValidationResult(valid=True, node_statuses={"n1": ns})
        dumped = json.loads(vr.model_dump_json())
        vr2 = ValidationResult.model_validate(dumped)
        assert vr2.valid is True
        assert vr2.node_statuses["n1"].status == "executed"
