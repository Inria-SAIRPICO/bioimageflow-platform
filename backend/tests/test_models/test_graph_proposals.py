"""Tests for graph proposal operation models."""

from pydantic import TypeAdapter

from bioimageflow_server.models.graph import GraphState, NodeState
from bioimageflow_server.models.graph_proposals import (
    AddNodeOperation,
    ConnectOperation,
    DisconnectOperation,
    GraphProposalOperation,
    ReplaceGraphOperation,
    UpdateParametersOperation,
)


def test_operation_discriminator_dispatches_all_supported_operations() -> None:
    adapter = TypeAdapter(GraphProposalOperation)

    add_node = adapter.validate_python(
        {
            "type": "add_node",
            "node": {
                "id": "n1",
                "name": "Node",
                "tool_name": "Tool",
                "position": [0, 0],
                "parameters": {},
            },
        }
    )
    connect = adapter.validate_python(
        {
            "type": "connect",
            "edge": {
                "type": "positional",
                "id": "e1",
                "source_node": "n1",
                "target_node": "n2",
                "positional_index": 0,
            },
        }
    )
    disconnect = adapter.validate_python({"type": "disconnect", "edge_id": "e1"})
    update = adapter.validate_python(
        {"type": "update_parameters", "node_id": "n1", "parameters": {"k": "v"}}
    )
    replace = adapter.validate_python(
        {"type": "replace_graph", "graph": {"nodes": [], "edges": []}}
    )

    assert isinstance(add_node, AddNodeOperation)
    assert isinstance(connect, ConnectOperation)
    assert isinstance(disconnect, DisconnectOperation)
    assert isinstance(update, UpdateParametersOperation)
    assert isinstance(replace, ReplaceGraphOperation)


def test_proposal_operations_roundtrip() -> None:
    operations: list[GraphProposalOperation] = [
        AddNodeOperation(
            node=NodeState(
                id="n1",
                name="Node",
                tool_name="Tool",
                position=(0, 0),
                parameters={},
            )
        ),
        UpdateParametersOperation(node_id="n1", parameters={"threshold": 0.5}),
        ReplaceGraphOperation(graph=GraphState(nodes=[], edges=[])),
    ]

    adapter = TypeAdapter(list[GraphProposalOperation])
    dumped = adapter.dump_python(operations, mode="json")
    restored = adapter.validate_python(dumped)

    assert restored == operations
