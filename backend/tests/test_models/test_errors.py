"""Tests for the ErrorResponse model."""

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.errors import ErrorResponse


class TestErrorResponse:
    def test_required_fields(self) -> None:
        resp = ErrorResponse(error="not_found", detail="Resource not found")
        assert resp.error == "not_found"
        assert resp.detail == "Resource not found"

    def test_field_defaults_to_none(self) -> None:
        resp = ErrorResponse(error="server_error", detail="Something went wrong")
        assert resp.field is None

    def test_field_can_be_set(self) -> None:
        resp = ErrorResponse(error="validation_error", detail="Invalid value", field="name")
        assert resp.field == "name"

    def test_serialization(self) -> None:
        resp = ErrorResponse(error="not_found", detail="Not found")
        data = resp.model_dump()
        assert data == {"error": "not_found", "detail": "Not found", "field": None}

    def test_serialization_with_field(self) -> None:
        resp = ErrorResponse(error="validation_error", detail="Required", field="email")
        data = resp.model_dump()
        assert data == {"error": "validation_error", "detail": "Required", "field": "email"}

    def test_json_serialization(self) -> None:
        resp = ErrorResponse(error="bad_request", detail="Bad request")
        json_str = resp.model_dump_json()
        assert '"error":"bad_request"' in json_str.replace(" ", "")

    def test_short_snake_case_codes(self) -> None:
        """The error field is a short snake_case code (spec §2.4.1b)."""
        for code in ("graph_locked", "execution_running", "path_traversal", "file_too_large"):
            resp = ErrorResponse(error=code, detail="Some human-readable message")
            assert resp.error == code

    def test_rejects_extra_fields(self) -> None:
        """Extra fields are forbidden to keep the wire format strict."""
        with pytest.raises(ValidationError):
            ErrorResponse(  # type: ignore[call-arg]
                error="bad_request",
                detail="Bad request",
                extra_unknown="should-be-rejected",
            )

    def test_rejects_missing_error(self) -> None:
        with pytest.raises(ValidationError):
            ErrorResponse(detail="missing error")  # type: ignore[call-arg]

    def test_rejects_missing_detail(self) -> None:
        with pytest.raises(ValidationError):
            ErrorResponse(error="bad_request")  # type: ignore[call-arg]

    def test_round_trip(self) -> None:
        resp = ErrorResponse(error="graph_locked", detail="Locked", field="parameters")
        revived = ErrorResponse.model_validate(resp.model_dump())
        assert revived == resp
