"""Public, bounded output-file planning diagnostics and correction checks."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from bioimageflow_server.models.workflow import validate_workflow_id


class _OutputPlanningModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class FileGroupSchema(_OutputPlanningModel):
    kind: Literal["per_row", "once", "by"]
    keys: list[str] = Field(default_factory=list)


class OutputFileDeclaration(_OutputPlanningModel):
    output_role: Literal["exact", "base", "reference"]
    file_group: FileGroupSchema | None = None
    description: str = ""


class OutputPlanningField(_OutputPlanningModel):
    field: str
    template: str
    kind: Literal["exact"]
    group: FileGroupSchema
    description: str


class TemplateExpansionPart(_OutputPlanningModel):
    kind: Literal["literal", "token"]
    text: str
    value: str


class OutputPlanningMember(_OutputPlanningModel):
    field: str
    row_position: int | None
    row_index: str | None
    group_index: int
    group_key: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    parts: list[TemplateExpansionPart] = Field(default_factory=list)


class OutputPlanningConflict(_OutputPlanningModel):
    path: str
    members: list[OutputPlanningMember]
    total_members: int = Field(ge=1)


class OutputPlanningReport(_OutputPlanningModel):
    code: Literal["output_path_collision", "output_group_destination_mismatch"]
    node_id: str
    detail: str
    fields: list[OutputPlanningField]
    conflicts: list[OutputPlanningConflict]
    total_conflicts: int = Field(ge=1)
    total_owners: int = Field(ge=1)
    suggested_templates: dict[str, str] = Field(default_factory=dict)
    correction_available: bool = False
    correction_unavailable_reason: str | None = None


class OutputTemplateCheckRequest(_OutputPlanningModel):
    execution_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    draft_revision: int = Field(ge=0)
    node_id: str = Field(min_length=1)
    templates: dict[str, str] = Field(min_length=1, max_length=64)

    @field_validator("workflow_id")
    @classmethod
    def validate_workflow_name(cls, value: str) -> str:
        return validate_workflow_id(value)

    @field_validator("templates")
    @classmethod
    def validate_templates(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not name or not pattern or len(pattern) > 32768 for name, pattern in value.items()):
            raise ValueError("Output templates must have nonempty fields and bounded patterns")
        return value


class OutputTemplateCheckResponse(_OutputPlanningModel):
    valid: bool
    reports: list[OutputPlanningReport] = Field(default_factory=list)
