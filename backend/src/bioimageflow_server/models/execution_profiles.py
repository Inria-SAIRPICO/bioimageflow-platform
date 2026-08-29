"""Strict API and persistence models for managed remote clusters."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProfileValue(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class ExecutionProfileCreate(ProfileValue):
    """Trusted desktop configuration-script selection."""

    name: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    config_path: str = Field(min_length=1)

    @field_validator("name", "config_path")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must be non-empty")
        return normalized


class DistributedExecutionProfile(ExecutionProfileCreate):
    schema_: Literal["bioimageflow.platform.execution-profile.v2"] = Field(
        default="bioimageflow.platform.execution-profile.v2", alias="schema"
    )
    id: str = Field(pattern=r"^profile_[0-9a-f]{32}$")
    revision: int = Field(ge=1)
    config_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    cluster_host: str = Field(min_length=1)
    cluster_root: str = Field(min_length=1)


class ExecutionProfilePatch(ProfileValue):
    expected_revision: int = Field(ge=1)
    profile: ExecutionProfileCreate


class ExecutionProfileList(ProfileValue):
    editable: bool
    profiles: list[DistributedExecutionProfile]


class CapabilityStatusValue(ProfileValue):
    supported: bool
    reason: str | None = None


class ExecutionCapabilitiesValue(ProfileValue):
    schema_: Literal["bioimageflow.execution_capabilities.v1"] = Field(alias="schema")
    capabilities: dict[str, CapabilityStatusValue]


class ClusterDiagnosticValue(ProfileValue):
    schema_: Literal["bioimageflow.cluster_diagnostic.v1"] = Field(alias="schema")
    phase: str
    category: str
    message: str
    allocation_state: Literal[
        "none", "orchestrator-submitted", "workers-possible", "unknown"
    ]
    retry_safety: Literal["safe", "same-attempt-only", "unsafe", "not-applicable"]
    next_action: str
    identities: dict[str, str] = Field(default_factory=dict)


class ClusterEnvironmentDescription(ProfileValue):
    kind: str | None = None


class ParslConfigurationDescription(ProfileValue):
    source_kind: str | None = None
    factory: str | None = None


class SchedulerJobDescription(ProfileValue):
    scheduler: str | None = None
    queue: str | None = None
    project: str | None = None
    walltime_seconds: int | None = Field(default=None, ge=1)
    cpu: int | None = Field(default=None, ge=1)


class SetupScriptDescription(ProfileValue):
    source_kind: str | None = None
    digest: str | None = None
    cluster_path: str | None = None


class SanitizedClusterDescription(ProfileValue):
    schema_: Literal["bioimageflow.remote_cluster.v1"] = Field(alias="schema")
    host: str
    root: str
    results_root: str | None = None
    configured: bool
    environment: ClusterEnvironmentDescription | None = None
    parsl: ParslConfigurationDescription | None = None
    orchestrator: SchedulerJobDescription | None = None
    setup: SetupScriptDescription | None = None


class ClusterConnectionValue(ProfileValue):
    schema_: Literal["bioimageflow.cluster_connection_report.v1"] = Field(alias="schema")
    reachable: bool
    gateway_available: bool
    bootstrap_required: bool
    gateway_version: str | None = None
    protocol_versions: list[int] = Field(default_factory=list)
    diagnostics: list[ClusterDiagnosticValue] = Field(default_factory=list)


class ExecutionProfileDescription(ProfileValue):
    profile_id: str
    profile_revision: int
    config_digest: str
    cluster_host: str
    cluster_root: str
    configured: bool
    cluster: SanitizedClusterDescription
    capabilities: ExecutionCapabilitiesValue
    connection: ClusterConnectionValue | None = None
    diagnostics: list[ClusterDiagnosticValue] = Field(default_factory=list)


class ExecutionTargetValue(ProfileValue):
    id: str
    name: str
    kind: Literal["local", "profile"]
    mode: Literal["local", "managed_remote"]
    available: bool
    disabled_reason: str | None = None
    profile_revision: int | None = None


class ExecutionTargetsValue(ProfileValue):
    capabilities: ExecutionCapabilitiesValue
    targets: list[ExecutionTargetValue]
