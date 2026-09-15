"""Typed contracts for registered local napari environments."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from bioimageflow_server.models.graph import PackageRequirement, ViewerSpec
from bioimageflow_server.models.results import ResultArtifactIdentity


DEFAULT_MANAGED_PYTHON = "==3.12.*"
DEFAULT_MANAGED_NAPARI = "0.9.1"
DEFAULT_MANAGED_QT = "PyQt6"
LEGACY_MANAGED_NAPARI = "0.6.6"
LEGACY_MANAGED_QT = "PyQt5"
MANAGED_CHANNELS = ["conda-forge"]
_RESERVED_MANAGED_DISTRIBUTIONS = {
    "bioimageflow",
    "bioimageflow-server",
    "napari",
    "pyqt5",
    "pyqt6",
    "pyside2",
    "pyside6",
    "python",
    "wetlands",
}


def _validated_python_constraint(value: str) -> str:
    normalized = value.strip()
    try:
        constraint = SpecifierSet(normalized)
    except InvalidSpecifier as exc:
        raise ValueError("python must be a valid version constraint") from exc
    if (
        not normalized
        or not constraint.contains("3.12.0")
        or not constraint.contains("3.12.99")
        or constraint.contains("3.11.99")
        or constraint.contains("3.13.0")
    ):
        raise ValueError("managed napari recipes must select only Python 3.12")
    return normalized


def _validated_napari_version(value: str) -> str:
    normalized = value.strip()
    try:
        Version(normalized)
    except InvalidVersion as exc:
        raise ValueError("napari must be an exact valid version") from exc
    return normalized


def _normalized_requested_packages(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        try:
            requirement = Requirement(raw.strip())
        except InvalidRequirement as exc:
            raise ValueError(f"invalid requested PyPI requirement: {raw!r}") from exc
        name = canonicalize_name(requirement.name)
        if requirement.url is not None:
            raise ValueError("managed requirements must resolve from PyPI, not direct URLs")
        if requirement.marker is not None:
            raise ValueError("managed requirements do not support environment markers")
        if name in _RESERVED_MANAGED_DISTRIBUTIONS:
            raise ValueError(f"{requirement.name} is controlled by the managed recipe")
        if name in seen:
            raise ValueError(f"duplicate requested distribution: {requirement.name}")
        seen.add(name)
        normalized.append(str(requirement))
    return normalized


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
    preset: Literal["default", "legacy", "advanced"] | None = None
    python: str | None = None
    napari: str | None = None
    qt: Literal["PyQt5", "PyQt6"] | None = None
    requested_packages: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)

    @field_validator("python")
    @classmethod
    def _validate_python(cls, value: str | None) -> str | None:
        return _validated_python_constraint(value) if value is not None else None

    @field_validator("napari")
    @classmethod
    def _validate_napari(cls, value: str | None) -> str | None:
        return _validated_napari_version(value) if value is not None else None

    @field_validator("requested_packages")
    @classmethod
    def _validate_requested_packages(cls, value: list[str]) -> list[str]:
        return _normalized_requested_packages(value)

    @model_validator(mode="after")
    def _validate_source_shape(self) -> "NapariManagedRecipe":
        if self.source == "adopted":
            if any(
                value is not None
                for value in (self.preset, self.python, self.napari, self.qt)
            ) or self.requested_packages or self.channels:
                raise ValueError("adopted environments cannot claim a managed recipe")
            return self
        if None in (self.preset, self.python, self.napari, self.qt):
            raise ValueError("managed recipes require preset, Python, napari, and Qt")
        if self.channels != MANAGED_CHANNELS:
            raise ValueError("managed recipes use the conda-forge channel")
        return self


class NapariEnvironmentOperationError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    detail: str


class NapariEnvironmentOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    environment_id: UUID
    kind: Literal["create", "copy", "retry", "remove"]
    state: Literal[
        "pending",
        "resolving",
        "installing",
        "validating",
        "removing",
        "completed",
        "failed",
        "cancelled",
    ]
    progress: int = Field(ge=0, le=100)
    message: str
    error: NapariEnvironmentOperationError | None = None
    wetlands_operation_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NapariManagedMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wetlands_name: str
    installation_generation: UUID | None
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


class NapariManagedRecipeSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset: Literal["default", "legacy", "advanced"] = "default"
    python: str | None = None
    napari: str | None = None
    qt: Literal["PyQt5", "PyQt6"] | None = None
    requested_packages: list[str] = Field(default_factory=list)

    @field_validator("python")
    @classmethod
    def _validate_python(cls, value: str | None) -> str | None:
        return _validated_python_constraint(value) if value is not None else None

    @field_validator("napari")
    @classmethod
    def _validate_napari(cls, value: str | None) -> str | None:
        return _validated_napari_version(value) if value is not None else None

    @field_validator("requested_packages")
    @classmethod
    def _validate_requested_packages(cls, value: list[str]) -> list[str]:
        return _normalized_requested_packages(value)

    @model_validator(mode="after")
    def _validate_preset_fields(self) -> "NapariManagedRecipeSelection":
        if self.preset != "advanced" and any(
            value is not None for value in (self.python, self.napari, self.qt)
        ):
            raise ValueError("preset recipes do not accept advanced version overrides")
        if self.preset == "advanced" and (self.napari is None or self.qt is None):
            raise ValueError("advanced recipes require an exact napari version and Qt choice")
        return self

    def resolved(self) -> NapariManagedRecipe:
        if self.preset == "default":
            napari = DEFAULT_MANAGED_NAPARI
            qt = DEFAULT_MANAGED_QT
        elif self.preset == "legacy":
            napari = LEGACY_MANAGED_NAPARI
            qt = LEGACY_MANAGED_QT
        else:
            assert self.napari is not None and self.qt is not None
            napari = self.napari
            qt = self.qt
        return NapariManagedRecipe(
            source="managed",
            preset=self.preset,
            python=self.python or DEFAULT_MANAGED_PYTHON,
            napari=napari,
            qt=qt,
            requested_packages=self.requested_packages,
            channels=MANAGED_CHANNELS,
        )


class NapariManagedEnvironmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    recipe: NapariManagedRecipeSelection = Field(default_factory=NapariManagedRecipeSelection)
    expected_revision: int = Field(ge=0)

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


class NapariManagedEnvironmentCopy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    python: str | None = None
    napari: str | None = None
    qt: Literal["PyQt5", "PyQt6"] | None = None
    requested_packages: list[str] | None = None
    expected_revision: int = Field(ge=0)

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

    @field_validator("python")
    @classmethod
    def _validate_python(cls, value: str | None) -> str | None:
        return _validated_python_constraint(value) if value is not None else None

    @field_validator("napari")
    @classmethod
    def _validate_napari(cls, value: str | None) -> str | None:
        return _validated_napari_version(value) if value is not None else None

    @field_validator("requested_packages")
    @classmethod
    def _validate_requested_packages(cls, value: list[str] | None) -> list[str] | None:
        return _normalized_requested_packages(value) if value is not None else None


class NapariManagedRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)


class NapariManagedRemoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)


class NapariManagedOperationMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=0)
    environment: NapariEnvironment | None
    operation: NapariEnvironmentOperation


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
    operations: list[NapariEnvironmentOperation] = Field(default_factory=list)


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
