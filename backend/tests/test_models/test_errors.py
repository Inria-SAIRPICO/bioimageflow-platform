"""Tests for the ErrorResponse model."""

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
