"""Typed contracts for registered local napari environments."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from bioimageflow_server.models.graph import PackageRequirement, ViewerSpec
from bioimageflow_server.models.results import ResultArtifactIdentity


class InstalledDistribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str


class NapariEnvironmentInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    python_version: str
    napari_version: str | None = None
    qt_distribution: str | None = None
    qt_version: str | None = None
    bridge_distribution: str | None = None
    bridge_version: str | None = None
    distributions: list[InstalledDistribution]
    fingerprint: str
    probed_at: datetime


class NapariLaunchContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["interpreter", "conda-run", "wetlands-managed"]
    argv_prefix: list[str] = Field(default_factory=list)
    conda_executable: str | None = None


class NapariManagedRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["adopted", "managed"]
    python: str | None = None
    napari: str | None = None
    qt: str | None = None
    requested_packages: list[str] = Field(default_factory=list)


class NapariManagedMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wetlands_name: str
    installation_generation: UUID
    recipe: NapariManagedRecipe


class NapariEnvironment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    registration_order: int = Field(ge=0)
    name: str
    ownership: Literal["external", "managed"]
    kind: Literal["conda", "venv"]
    root: str
    interpreter: str
    interpreter_identity: str
    interpreter_fingerprint: str
    launch: NapariLaunchContext
    managed: NapariManagedMetadata | None = None
    inventory: NapariEnvironmentInventory | None = None
    state: Literal[
        "setup_needed",
        "creating",
        "ready",
        "failed",
        "cancelled",
        "removing",
        "missing",
        "replaced",
        "drifted",
        "probe_failed",
    ] = "ready"
    last_error: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("name")
    @classmethod
    def _require_name(cls, value: str) -> str:
        if not value:
            raise ValueError("environment name must be non-empty")
        return value

    @model_validator(mode="after")
    def _validate_ownership_metadata(self) -> "NapariEnvironment":
        if self.ownership == "managed" and self.managed is None:
            raise ValueError("managed environments require managed metadata")
        if self.ownership == "external" and self.managed is not None:
            raise ValueError("external environments cannot carry managed metadata")
        return self


class NapariFilenameRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    pattern: str
    environment_id: UUID
    enabled: bool = True
    reader_id: str | None = None

    @field_validator("pattern", mode="before")
    @classmethod
    def _normalize_pattern(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("pattern")
    @classmethod
    def _validate_pattern_shape(cls, value: str) -> str:
        if not value or "/" in value or "\\" in value or "**" in value:
            raise ValueError("filename rule pattern is empty or unsupported")
        index = 0
        while index < len(value):
            if value[index] == "]":
                raise ValueError("filename rule pattern contains an unmatched ]")
            if value[index] != "[":
                index += 1
                continue
            closing = value.find("]", index + 1)
            if closing < 0 or closing == index + 1:
                raise ValueError("filename rule pattern contains a malformed character class")
            content = value[index + 1 : closing]
            if content == "!" or "[" in content:
                raise ValueError("filename rule pattern contains a malformed character class")
            index = closing + 1
        return value

    @field_validator("reader_id", mode="before")
    @classmethod
    def _normalize_reader(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class NapariEnvironmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    path: str
    expected_revision: int = Field(ge=0)


class NapariEnvironmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    path: str | None = None
    expected_revision: int = Field(ge=0)


class NapariEnvironmentList(BaseModel):
    revision: int = Field(ge=0)
    environments: list[NapariEnvironment] = Field(default_factory=list)
    default_environment_id: UUID | None
    filename_rules: list[NapariFilenameRule] = Field(default_factory=list)


class NapariDefaultEnvironmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment_id: UUID | None
    expected_revision: int = Field(ge=0)


class NapariFilenameRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    mode: Literal["extension", "pattern"] = "extension"
    environment_id: UUID
    enabled: bool = True
    reader_id: str | None = None
    expected_revision: int = Field(ge=0)


class NapariFilenameRulesReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: list[NapariFilenameRule] = Field(default_factory=list)
    expected_revision: int = Field(ge=0)


class NapariProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)


class NapariEnvironmentMutation(BaseModel):
    revision: int = Field(ge=0)
    environment: NapariEnvironment


class NapariFilenameRuleMutation(BaseModel):
    revision: int = Field(ge=0)
    rule: NapariFilenameRule


class NapariFilenamePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str


class NapariFilenamePreview(BaseModel):
    filename: str
    matching_rule_ids: list[UUID]
    winner_rule_id: UUID | None


class NapariResolveRequest(BaseModel):
    """Resolve one captured output artifact against local environments."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(min_length=1)
    identity_generation: int = Field(ge=0)
    node_path: tuple[str, ...] = Field(min_length=1)
    output_key: str = Field(min_length=1)
    result_identity: ResultArtifactIdentity
    row: int = Field(ge=0)


class NapariCompatibilityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "missing_distribution",
        "version_out_of_range",
        "napari_version_out_of_range",
        "missing_napari",
        "inventory_missing",
        "inventory_stale",
        "probe_failed",
        "unavailable",
    ]
    distribution: str | None = None
    required_version: str | None = None
    installed_version: str | None = None
    detail: str


class NapariEnvironmentCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment_id: UUID
    name: str
    status: Literal["compatible", "incompatible", "unknown", "unavailable"]
    label: str
    reason: str
    issues: list[NapariCompatibilityIssue] = Field(default_factory=list)
    missing_recommended_packages: list[PackageRequirement] = Field(default_factory=list)
    preference: Literal["favorite", "filename_rule", "global_default", "other"]


class NapariResolveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_identity: ResultArtifactIdentity
    workflow_id: str
    identity_generation: int
    node_path: tuple[str, ...]
    output_key: str
    filename: str
    viewer: ViewerSpec | None = None
    reader_id: str | None = None
    candidates: list[NapariEnvironmentCandidate]
    effective_environment_id: UUID | None = None
    effective_reason: str
