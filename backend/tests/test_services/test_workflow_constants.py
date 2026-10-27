"""Platform JSON constants retain types across public library compilation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, get_type_hints

from bioimageflow import deserialize_constant, serialize_constant
from bioimageflow_core.type_descriptors import encode_annotation
from platform_test_tools.workflow_parameters import WorkflowParameterTool
from pydantic import ValidationError
import pytest

from bioimageflow_server.models.graph import GraphState, SerializedConstant
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.graph_translator import (
    graph_state_to_lib_dict,
    lib_dict_to_graph_state,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService


def _constant(kind: str, value: Any) -> dict[str, Any]:
    return {"__type__": kind, "value": value}


def _graph(bindings: dict[str, Any], defaults: dict[str, Any] | None = None) -> GraphState:
    child = {
        "schema_version": 2,
        "name": "child",
        "display_name": "Child",
        "nodes": [{
            "type": "tool", "id": "parameters", "name": "Parameters",
            "tool_name": "WorkflowParameterTool", "parameters": {}, "position": [0, 0],
        }],
        "edges": [],
        "interface": {"inputs": [
            {
                "id": name, "name": name, "kind": "field",
                "schema": {"type_spec": encode_annotation(annotation)},
                "targets": [{"node": "parameters", "port": {"kind": "field", "name": name}}],
                **({"default": defaults[name]} if defaults and name in defaults else {}),
            }
            for name, annotation in get_type_hints(WorkflowParameterTool.Inputs).items()
        ], "outputs": []},
        "config": {"engine": "direct", "execution": "parallel"},
    }
    parent = {
        **child, "name": "parent", "display_name": "Parent",
        "nodes": [{
            "type": "workflow", "id": "nested", "name": "Nested", "workflow": child,
            "bindings": bindings, "position": [0, 0],
        }],
        "interface": {"inputs": [], "outputs": []},
    }
    # Browser JSON has already erased the distinction between 1.0 and 1.
    return GraphState.model_validate_json(json.dumps(parent))


def _registry() -> ToolRegistryService:
    registry = ToolRegistryService()
    registry.register_tool(
        WorkflowParameterTool.__name__,
        registry.metadata_for_class(WorkflowParameterTool),
        tool_class=WorkflowParameterTool,
    )
    return registry


@pytest.mark.parametrize("kind", ["list", "tuple"])
def test_legacy_sequence_literals_translate_without_rewriting(kind: str) -> None:
    literal = {"__type__": "float", "value": "literal", "note": "data"}
    payload = _constant(kind, [1, None, True, [2, "three"], literal])
    value = SerializedConstant.model_validate_json(json.dumps(payload))

    assert value.model_dump(mode="json", by_alias=True) == payload
    decoded = deserialize_constant(value.to_library_dict())
    expected = [1, None, True, [2, "three"], literal]
    assert decoded == (tuple(expected) if kind == "tuple" else expected)


def test_typed_sequences_normalize_floats_recursively_and_preserve_maps() -> None:
    payload = _constant("list", [
        _constant("float", 1),
        _constant("tuple", [_constant("bool", True), _constant("none", None)]),
        _constant("dict", [{
            "key": _constant("str", "amount"), "value": _constant("float", 2),
        }]),
        _constant("path", "image.tiff"),
        "legacy sibling",
    ])
    value = SerializedConstant.model_validate_json(json.dumps(payload))
    decoded = deserialize_constant(value.to_library_dict())

    assert decoded == [1.0, (True, None), {"amount": 2.0}, Path("image.tiff"), "legacy sibling"]
    assert type(decoded[0]) is float
    assert type(decoded[2]["amount"]) is float
    assert value.model_dump(mode="json", by_alias=True) == payload


@pytest.mark.parametrize("malformed", [
    _constant("float", True),
    _constant("bool", 1),
    _constant("tuple", "items"),
    _constant("unknown", None),
    _constant("dict", [{"key": _constant("str", "a"), "value": _constant("int", 1), "extra": 1}]),
    _constant("dict", [{"key": _constant("str", "a"), "value": _constant("int", 1)}] * 2),
    {"__type__": [], "value": None},
])
def test_malformed_reserved_sequence_envelopes_are_rejected(malformed: Any) -> None:
    with pytest.raises(ValidationError):
        SerializedConstant.model_validate(_constant("list", [malformed]))


def test_json_binding_compilation_and_library_round_trip(tmp_path: Path) -> None:
    bindings = {
        "amount": _constant("float", 1),
        "values": _constant("list", [
            _constant("float", 2), _constant("tuple", [_constant("none", None), _constant("bool", True)]),
        ]),
        "coordinates": _constant("tuple", [_constant("float", 3), _constant("int", 4)]),
        "path": _constant("str", "image.tiff"),
        "optional": _constant("none", None),
        "enabled": _constant("bool", True),
    }
    graph = _graph(bindings)
    registry = _registry()
    translated = graph_state_to_lib_dict(graph, registry)
    assert translated.errors == []
    expected = {
        "amount": 1.0, "values": [2.0, (None, True)], "coordinates": (3.0, 4),
        "path": "image.tiff", "optional": None, "enabled": True,
    }
    normalized = translated.lib_dict["nodes"][0]["bindings"]
    assert {key: deserialize_constant(value) for key, value in normalized.items()} == expected
    assert type(deserialize_constant(normalized["amount"])) is float

    workflow, errors, _ = build_workflow(graph, registry, storage_path=tmp_path)
    assert errors == []
    assert workflow is not None
    exported = workflow.to_dict()
    restored = lib_dict_to_graph_state(json.loads(json.dumps(exported)))
    retranslated = graph_state_to_lib_dict(restored, registry)
    assert retranslated.errors == []
    assert retranslated.lib_dict["nodes"][0]["bindings"] == normalized


def test_interface_defaults_and_removed_bindings_compile_distinctly(tmp_path: Path) -> None:
    defaults = {"amount": _constant("float", 1), "values": _constant("list", [True, None])}
    graph = _graph({"optional": _constant("none", None)}, defaults)
    registry = _registry()
    workflow, errors, _ = build_workflow(graph, registry, storage_path=tmp_path)
    assert errors == []
    assert workflow is not None
    exported = workflow.to_dict()["nodes"][0]
    declared = {port["id"]: port for port in exported["workflow"]["interface"]["inputs"]}
    assert declared["amount"]["default"] == serialize_constant(1.0)
    assert declared["values"]["default"] == serialize_constant([True, None])
    # The library materializes interface defaults into invocation bindings.
    assert exported["bindings"] == {
        "optional": serialize_constant(None),
        "amount": serialize_constant(1.0),
        "values": serialize_constant([True, None]),
    }

    # Reset removes the override; it must not turn the declaration into null.
    reset, errors, _ = build_workflow(_graph({}, defaults), registry, storage_path=tmp_path / "reset")
    assert errors == []
    assert reset is not None
    assert reset.to_dict()["nodes"][0]["bindings"] == {
        "amount": serialize_constant(1.0),
        "values": serialize_constant([True, None]),
    }
