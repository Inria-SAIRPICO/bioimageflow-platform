"""Canonical graph builders shared by tests outside the graph-model suite."""

from typing import Any

from bioimageflow_server.models.graph import GraphState


def graph_state(**changes: Any) -> GraphState:
    """Build a complete recursive workflow document with concise test overrides."""

    document: dict[str, Any] = {
        "schema_version": 1,
        "name": "test_workflow",
        "display_name": "Test workflow",
        "nodes": [],
        "edges": [],
        "interface": {"inputs": [], "outputs": []},
        "config": {},
    }
    document.update(changes)
    return GraphState.model_validate(document)


def graph_document(**changes: Any) -> dict[str, Any]:
    """Return the JSON form accepted by graph API endpoints."""

    return graph_state(**changes).model_dump(mode="json", by_alias=True)


def graph_payload(**changes: Any) -> dict[str, Any]:
    """Build a complete raw payload, including intentionally invalid fixtures."""

    document: dict[str, Any] = {
        "schema_version": 1,
        "name": "test_workflow",
        "display_name": "Test workflow",
        "nodes": [],
        "edges": [],
        "interface": {"inputs": [], "outputs": []},
        "config": {},
    }
    document.update(changes)
    return document
