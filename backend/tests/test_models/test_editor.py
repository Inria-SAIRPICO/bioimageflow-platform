from __future__ import annotations

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.editor import (
    EditorOpenMethod,
    EditorOpenRequest,
    EditorOpenResponse,
    EditorStatus,
)


def test_editor_open_request_rejects_empty_path() -> None:
    with pytest.raises(ValidationError):
        EditorOpenRequest(path="  ")


def test_editor_open_request_rejects_empty_focus_path() -> None:
    with pytest.raises(ValidationError):
        EditorOpenRequest(path="/tmp", focus_path="  ")


def test_editor_open_method_values() -> None:
    assert EditorOpenMethod.EXTERNAL == "external"
    assert EditorOpenMethod.EMBEDDED == "embedded"
    assert EditorOpenMethod.CLIPBOARD == "clipboard"


def test_editor_status_allows_nullable_url_and_version() -> None:
    status = EditorStatus(available=False, url=None, version=None)
    assert status.model_dump() == {
        "available": False,
        "url": None,
        "version": None,
        "control_available": False,
        "launch_attempted": False,
        "error_code": None,
        "error_detail": None,
    }


def test_editor_open_response_serializes_enum_value() -> None:
    response = EditorOpenResponse(
        opened=True,
        method=EditorOpenMethod.EMBEDDED,
        url="http://127.0.0.1:32344",
        path="/tmp/tool.py",
    )
    assert response.model_dump(mode="json")["method"] == "embedded"
