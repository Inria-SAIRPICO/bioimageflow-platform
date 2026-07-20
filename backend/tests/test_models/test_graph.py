"""Tests for the strict recursive workflow graph models."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.graph import GraphState


def _tool(node_id: str) -> dict[str, object]:
    return {
        "type": "tool",
        "id": node_id,
        "name": node_id.title(),
        "tool_name": "Generate",
        "position": [0, 0],
        "parameters": {},
    }


def _graph(name: str = "workflow") -> dict[str, object]:
    return {
        "schema_version": 1,
        "name": name,
        "display_name": name.title(),
        "nodes": [_tool("generate")],
        "edges": [],
        "interface": {"inputs": [], "outputs": []},
        "config": {
            "storage_path": "./bif_data",
            "engine": "direct",
            "execution": "parallel",
        },
    }


def test_recursive_discriminated_graph_round_trip() -> None:
    child = _graph("child")
    child["interface"] = {
        "inputs": [
            {
                "id": "input-value",
                "name": "value",
                "kind": "field",
                "targets": [
                    {
                        "node": "generate",
                        "port": {"kind": "field", "name": "value"},
                    }
                ],
            }
        ],
        "outputs": [
            {
                "id": "output-value",
                "name": "value",
                "source": {"node": "generate", "column": "value"},
            }
        ],
    }
    parent = _graph("parent")
    parent["nodes"] = [
        {
            "type": "workflow",
            "id": "child-node",
            "name": "Child",
            "workflow": child,
            "bindings": {
                "input-value": {"__type__": "int", "value": 7},
            },
            "position": [100, 100],
            "source": {
                "kind": "workspace",
                "workflow_id": "saved/child",
                "artifact_hash": "sha256:" + "a" * 64,
            },
        }
    ]
    parsed = GraphState.model_validate(parent)

    assert parsed.nodes[0].type == "workflow"
    assert parsed.model_dump(mode="json", by_alias=True)["nodes"][0]["bindings"] == {
        "input-value": {"__type__": "int", "value": 7}
    }
    assert GraphState.model_validate_json(parsed.model_dump_json(by_alias=True)) == parsed


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("unexpected",), True),
        (("nodes", 0, "unexpected"), True),
        (("nodes", 0, "type"), "unknown"),
        (("edges",), [{"type": "unknown", "id": "e"}]),
    ],
)
def test_unknown_fields_and_discriminators_are_rejected(
    path: tuple[str | int, ...], value: object
) -> None:
    payload = _graph()
    cursor: object = payload
    for part in path[:-1]:
        cursor = cursor[part]  # type: ignore[index]
    cursor[path[-1]] = value  # type: ignore[index]
    with pytest.raises(ValidationError):
        GraphState.model_validate(payload)


@pytest.mark.parametrize("missing", ["name", "display_name", "interface", "config"])
def test_definition_fields_are_required(missing: str) -> None:
    payload = _graph()
    payload.pop(missing)
    with pytest.raises(ValidationError):
        GraphState.model_validate(payload)


def test_binding_requires_known_field_input_and_typed_envelope() -> None:
    payload = _graph("parent")
    child = _graph("child")
    child["interface"] = {
        "inputs": [
            {"id": "table", "name": "table", "kind": "dataframe", "targets": []}
        ],
        "outputs": [],
    }
    payload["nodes"] = [
        {
            "type": "workflow",
            "id": "child",
            "name": "Child",
            "workflow": child,
            "bindings": {"table": {"__type__": "str", "value": "invalid"}},
            "position": [0, 0],
        }
    ]
    with pytest.raises(ValidationError, match="DataFrame workflow inputs cannot have constants"):
        GraphState.model_validate(payload)

    payload["nodes"][0]["bindings"] = {  # type: ignore[index]
        "missing": {"__type__": "str", "value": "invalid"}
    }
    with pytest.raises(ValidationError, match="unknown workflow input IDs"):
        GraphState.model_validate(payload)


def test_workflow_edge_uses_stable_port_id_and_excludes_a_binding() -> None:
    payload = _graph("parent")
    child = _graph("child")
    child["interface"] = {
        "inputs": [{"id": "input-value", "name": "Value", "kind": "field", "targets": []}],
        "outputs": [],
    }
    payload["nodes"] = [
        _tool("source"),
        {
            "type": "workflow",
            "id": "child",
            "name": "Child",
            "workflow": child,
            "bindings": {},
            "position": [0, 0],
        },
    ]
    payload["edges"] = [
        {
            "type": "column",
            "id": "edge-value",
            "source_node": "source",
            "source_output": "value",
            "target_node": "child",
            "target_input": "input-value",
        }
    ]
    parsed = GraphState.model_validate(payload)
    renamed = copy.deepcopy(payload)
    renamed["nodes"][1]["workflow"]["interface"]["inputs"][0]["name"] = "Renamed"  # type: ignore[index]
    assert GraphState.model_validate(renamed).edges == parsed.edges

    renamed["nodes"][1]["bindings"] = {  # type: ignore[index]
        "input-value": {"__type__": "int", "value": 1}
    }
    with pytest.raises(ValidationError, match="both an edge and a binding"):
        GraphState.model_validate(renamed)
