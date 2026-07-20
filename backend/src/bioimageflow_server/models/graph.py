"""Canonical recursive workflow graph models.

The platform persists this document directly.  Translation to the BioImageFlow
library format is deliberately mechanical: GUI-only node metadata is removed,
while definition metadata, interfaces, nodes, edges, and configuration retain
the same recursive shape at every depth.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    field_validator,
    model_validator,
)


class WireModel(BaseModel):
    """Strict base for every persisted/API workflow wire record."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
        json_schema_mode_override="validation",
    )


class SerializedConstant(WireModel):
    """Typed constant envelope shared with the BioImageFlow library."""

    type_: Literal["none", "bool", "int", "float", "list", "tuple", "str"] = Field(
        serialization_alias="__type__",
        validation_alias=AliasChoices("__type__", "type_"),
    )
    value: Any

    @model_validator(mode="after")
    def validate_payload(self) -> SerializedConstant:
        value = self.value
        valid = {
            "none": value is None,
            "bool": isinstance(value, bool),
            "int": isinstance(value, int) and not isinstance(value, bool),
            "float": isinstance(value, (int, float)) and not isinstance(value, bool),
            "list": isinstance(value, list),
            "tuple": isinstance(value, list),
            "str": isinstance(value, str),
        }[self.type_]
        if not valid:
            raise ValueError(f"Invalid payload for serialized constant type {self.type_!r}")
        return self


class FieldInputPort(WireModel):
    kind: Literal["field"]
    name: str = Field(min_length=1)


class PositionalInputPort(WireModel):
    kind: Literal["positional"]
    index: int = Field(ge=0)


class WorkflowInputPort(WireModel):
    kind: Literal["workflow"]
    id: str = Field(min_length=1)


InputTargetPort = Annotated[
    FieldInputPort | PositionalInputPort | WorkflowInputPort,
    Discriminator("kind"),
]


class WorkflowInputTarget(WireModel):
    node: str = Field(min_length=1)
    port: InputTargetPort


class WorkflowInput(WireModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: Literal["field", "dataframe"]
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    default: SerializedConstant | None = None
    targets: list[WorkflowInputTarget]

    @model_validator(mode="after")
    def validate_target_kinds(self) -> WorkflowInput:
        for target in self.targets:
            if self.kind == "field" and not isinstance(
                target.port, (FieldInputPort, WorkflowInputPort)
            ):
                raise ValueError("Field workflow inputs cannot target positional ports")
            if self.kind == "dataframe" and not isinstance(
                target.port, (PositionalInputPort, WorkflowInputPort)
            ):
                raise ValueError("DataFrame workflow inputs cannot target field ports")
        return self


class WorkflowOutputSource(WireModel):
    node: str = Field(min_length=1)
    column: str = Field(min_length=1)


class WorkflowOutput(WireModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    source: WorkflowOutputSource


class WorkflowInterface(WireModel):
    inputs: list[WorkflowInput]
    outputs: list[WorkflowOutput]

    @model_validator(mode="after")
    def validate_identity(self) -> WorkflowInterface:
        for label, ports in (("input", self.inputs), ("output", self.outputs)):
            ids = [port.id for port in ports]
            names = [port.name for port in ports]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Workflow {label} IDs must be unique")
            if len(names) != len(set(names)):
                raise ValueError(f"Workflow {label} names must be unique")
        if {port.id for port in self.inputs} & {port.id for port in self.outputs}:
            raise ValueError("Workflow input and output IDs must be globally unique")
        return self


class OutputViewConfig(WireModel):
    mode: Literal["none", "symlink", "copy", "hardlink"] = "none"
    scope: Literal["latest", "runs", "both"] = "latest"


class WorkflowConfig(WireModel):
    storage_path: str = "./bif_data"
    engine: Literal["direct", "wetlands"] = "wetlands"
    execution: Literal["parallel", "sequential"] = "parallel"
    output_view: OutputViewConfig | None = None


class WorkspaceWorkflowSource(WireModel):
    kind: Literal["workspace"]
    workflow_id: str = Field(min_length=1)
    artifact_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ToolNodeState(WireModel):
    """Editable platform state for one processing tool invocation."""

    type: Literal["tool"]
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    position: tuple[float, float]
    parameters: dict[str, Any]
    resources: dict[str, Any] = Field(default_factory=dict)
    output_templates: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    collapsed: bool = False
    tool_module: str | None = None
    tool_class: str | None = None
    tool_package: str | None = None
    tool_package_version: str | None = None
    source_module: str | None = None


class WorkflowNodeState(WireModel):
    """An embedded, independently editable workflow snapshot."""

    type: Literal["workflow"]
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    workflow: GraphState
    bindings: dict[str, SerializedConstant]
    source: WorkspaceWorkflowSource | None = None
    position: tuple[float, float]
    resources: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    collapsed: bool = False

    @model_validator(mode="after")
    def validate_bindings(self) -> WorkflowNodeState:
        inputs = {port.id: port for port in self.workflow.interface.inputs}
        unknown = sorted(set(self.bindings) - set(inputs))
        if unknown:
            raise ValueError(f"Bindings reference unknown workflow input IDs: {unknown}")
        dataframe = sorted(
            port_id for port_id in self.bindings if inputs[port_id].kind == "dataframe"
        )
        if dataframe:
            raise ValueError(f"DataFrame workflow inputs cannot have constants: {dataframe}")
        return self


NodeState = Annotated[ToolNodeState | WorkflowNodeState, Discriminator("type")]


class ColumnEdge(WireModel):
    type: Literal["column"]
    id: str = Field(min_length=1)
    source_node: str = Field(min_length=1)
    target_node: str = Field(min_length=1)
    source_output: str = Field(min_length=1)
    target_input: str = Field(min_length=1)


class DataFrameEdge(WireModel):
    type: Literal["dataframe"]
    id: str = Field(min_length=1)
    source_node: str = Field(min_length=1)
    target_node: str = Field(min_length=1)
    target_position: int | None = Field(default=None, ge=0)
    target_input: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_target(self) -> DataFrameEdge:
        if (self.target_position is None) == (self.target_input is None):
            raise ValueError(
                "DataFrame edges require exactly one of target_position or target_input"
            )
        return self


Edge = Annotated[ColumnEdge | DataFrameEdge, Discriminator("type")]


class GraphState(WireModel):
    """One self-contained workflow definition at any editor depth."""

    schema_version: Literal[1]
    name: str = Field(min_length=1)
    display_name: str
    nodes: list[NodeState]
    edges: list[Edge]
    interface: WorkflowInterface
    config: WorkflowConfig

    @field_validator("name")
    @classmethod
    def validate_definition_name(cls, value: str) -> str:
        if "/" in value:
            raise ValueError("Workflow definition names cannot contain '/'")
        return value

    @model_validator(mode="after")
    def validate_graph_integrity(self) -> GraphState:
        node_by_id = {node.id: node for node in self.nodes}
        if len(node_by_id) != len(self.nodes):
            raise ValueError("Workflow node IDs must be unique")
        edge_ids = [edge.id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("Workflow edge IDs must be unique")

        connected_inputs: set[tuple[str, str]] = set()
        for edge in self.edges:
            source = node_by_id.get(edge.source_node)
            target = node_by_id.get(edge.target_node)
            if source is None or target is None:
                raise ValueError(f"Edge {edge.id!r} references an unknown node")
            if isinstance(source, WorkflowNodeState):
                outputs = {port.id for port in source.workflow.interface.outputs}
                if isinstance(edge, ColumnEdge) and edge.source_output not in outputs:
                    raise ValueError(
                        f"Edge {edge.id!r} references an unknown workflow output ID"
                    )
            if isinstance(target, WorkflowNodeState):
                inputs = {port.id: port for port in target.workflow.interface.inputs}
                target_id = edge.target_input
                if target_id is None or target_id not in inputs:
                    raise ValueError(
                        f"Edge {edge.id!r} references an unknown workflow input ID"
                    )
                expected = "field" if isinstance(edge, ColumnEdge) else "dataframe"
                if inputs[target_id].kind != expected:
                    raise ValueError(f"Edge {edge.id!r} has the wrong workflow input kind")
                key = (target.id, target_id)
                if key in connected_inputs:
                    raise ValueError(f"Workflow input {target_id!r} has multiple incoming edges")
                if target_id in target.bindings:
                    raise ValueError(
                        f"Workflow input {target_id!r} cannot have both an edge and a binding"
                    )
                connected_inputs.add(key)
            elif isinstance(edge, DataFrameEdge) and edge.target_position is None:
                raise ValueError("Tool DataFrame edges must use target_position")

        for port in self.interface.inputs:
            for target in port.targets:
                node = node_by_id.get(target.node)
                if node is None:
                    raise ValueError(
                        f"Workflow input {port.id!r} targets unknown node {target.node!r}"
                    )
                if isinstance(target.port, WorkflowInputPort):
                    if not isinstance(node, WorkflowNodeState):
                        raise ValueError("Workflow target ports require a workflow node")
                    child_inputs = {item.id: item for item in node.workflow.interface.inputs}
                    child = child_inputs.get(target.port.id)
                    if child is None or child.kind != port.kind:
                        raise ValueError(
                            f"Workflow input {port.id!r} targets an incompatible child port"
                        )
                elif isinstance(node, WorkflowNodeState):
                    raise ValueError("Workflow nodes must be targeted through stable port IDs")

        for port in self.interface.outputs:
            source = node_by_id.get(port.source.node)
            if source is None:
                raise ValueError(
                    f"Workflow output {port.id!r} references unknown node {port.source.node!r}"
                )
            if isinstance(source, WorkflowNodeState):
                outputs = {item.id for item in source.workflow.interface.outputs}
                if port.source.column not in outputs:
                    raise ValueError(
                        f"Workflow output {port.id!r} references unknown child output ID"
                    )
        return self


# Resolve GraphState -> WorkflowNodeState -> GraphState before OpenAPI generation.
GraphState.model_rebuild()
WorkflowNodeState.model_rebuild()


class GraphValidationRequest(WireModel):
    """Request to validate a graph in an optional workspace context."""

    graph: GraphState
    workflow_name: str | None = None


class NodeOutputSchemaResponse(WireModel):
    """Response for ``POST /graph/nodes/{node_id}/output_schema``."""

    resolved: bool
    columns: dict[str, Any]
