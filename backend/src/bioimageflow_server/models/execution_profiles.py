"""Strict persisted models for named distributed execution profiles."""

from __future__ import annotations

import importlib
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, field_validator, model_validator


class ProfileValue(BaseModel):
    """Strict base for profile values that cross the API boundary."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )


def _bioimageflow() -> Any:
    """Load the public root module while 0.4 type metadata is being published."""
    return importlib.import_module("bioimageflow")


class ParslConfigRefValue(ProfileValue):
    factory: str
    kwargs: dict[str, Any] = Field(default_factory=dict)
    secret_refs: dict[str, str] | None = None

    @model_validator(mode="after")
    def validate_library_value(self) -> ParslConfigRefValue:
        self.to_library()
        return self

    def to_library(self):
        return _bioimageflow().ParslConfigRef.from_dict(self.model_dump(mode="json"))


class WorkerSlotCapacityValue(ProfileValue):
    schema_: Literal["bioimageflow.parsl.worker_slot_capacity.v1"] = Field(
        default="bioimageflow.parsl.worker_slot_capacity.v1", alias="schema"
    )
    cpu: int = Field(ge=1)
    gpu: int = Field(default=0, ge=0)
    memory_bytes: int | None = Field(default=None, ge=1)
    gpu_memory_bytes: int | None = Field(default=None, ge=1)


class ExecutorCapabilitiesValue(ProfileValue):
    schema_: Literal["bioimageflow.parsl.executor_capabilities.v1"] = Field(
        default="bioimageflow.parsl.executor_capabilities.v1", alias="schema"
    )
    storage_modes: list[Literal["shared_fs", "staged"]]
    tool_origin_modes: list[
        Literal[
            "installed_module",
            "versioned_module",
            "shared_module",
            "source_file",
            "archive_module",
        ]
    ]
    slot: WorkerSlotCapacityValue


class WorkerEnvironmentAttestationValue(ProfileValue):
    schema_: Literal["bioimageflow.parsl.worker_environment_attestation.v1"] = Field(
        default="bioimageflow.parsl.worker_environment_attestation.v1", alias="schema"
    )
    name: str
    dependency_hash: str
    allow_flexible_versions: bool
    core_requirement: str


class ExecutorBindingValue(ProfileValue):
    schema_: Literal["bioimageflow.parsl.executor_binding.v1"] = Field(
        default="bioimageflow.parsl.executor_binding.v1", alias="schema"
    )
    label: str
    environments: list[WorkerEnvironmentAttestationValue]
    capabilities: ExecutorCapabilitiesValue

    @model_validator(mode="after")
    def validate_library_value(self) -> ExecutorBindingValue:
        self.to_library()
        return self

    def to_library(self):
        return _bioimageflow().ExecutorBinding.from_dict(self.model_dump(mode="json"))


class ParslTaskPolicyValue(ProfileValue):
    schema_: Literal["bioimageflow.parsl.task_policy.v1"] = Field(
        default="bioimageflow.parsl.task_policy.v1", alias="schema"
    )
    row_chunk_size: int = Field(default=1, ge=1)
    max_in_flight: int = Field(default=32, ge=1)

    @model_validator(mode="after")
    def validate_library_value(self) -> ParslTaskPolicyValue:
        self.to_library()
        return self

    def to_library(self):
        return _bioimageflow().ParslTaskPolicy.from_dict(self.model_dump(mode="json"))


class LocalLaunchValue(ProfileValue):
    backend: Literal["local"] = "local"
    work_dir: str | None = None
    hard_cancel_after: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_library_value(self) -> LocalLaunchValue:
        self.to_library()
        return self

    def to_library(self):
        return _bioimageflow().OrchestratorLaunchConfig.from_dict(self.model_dump(mode="json"))


class PSIJLaunchValue(ProfileValue):
    backend: Literal["psij"] = "psij"
    executor: Literal["slurm", "pbs", "lsf"]
    walltime_seconds: float = Field(gt=0)
    queue: str | None = None
    project: str | None = None
    cpu_cores: int = Field(default=1, ge=1)
    work_dir: str | None = None
    hard_cancel_after: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_library_value(self) -> PSIJLaunchValue:
        self.to_library()
        return self

    def to_library(self):
        return _bioimageflow().PSIJLaunchConfig.from_dict(self.model_dump(mode="json"))


LaunchValue = Annotated[LocalLaunchValue | PSIJLaunchValue, Discriminator("backend")]


class SSHSubmissionTransportValue(ProfileValue):
    host: str
    staging_root: str
    remote_executable: str
    connect_timeout: float = Field(default=15.0, gt=0)

    @model_validator(mode="after")
    def validate_library_value(self) -> SSHSubmissionTransportValue:
        self.to_library()
        return self

    def to_library(self):
        return _bioimageflow().SSHSubmissionTransport.from_dict(self.model_dump(mode="json"))


class InlinePreLaunchValue(ProfileValue):
    kind: Literal["inline"] = "inline"
    text: str = Field(repr=False)

    def to_library(self):
        return _bioimageflow().PreLaunchScript.from_text(self.text)


class LocalFilePreLaunchValue(ProfileValue):
    kind: Literal["local_file"] = "local_file"
    path: str = Field(repr=False)

    def to_library(self):
        return _bioimageflow().PreLaunchScript.from_local_file(Path(self.path))


class ClusterFilePreLaunchValue(ProfileValue):
    kind: Literal["cluster_file"] = "cluster_file"
    path: str
    expected_digest: str | None = None

    def to_library(self):
        return _bioimageflow().PreLaunchScript.from_cluster_file(
            PurePosixPath(self.path), expected_digest=self.expected_digest
        )


PreLaunchValue = Annotated[
    InlinePreLaunchValue | LocalFilePreLaunchValue | ClusterFilePreLaunchValue,
    Discriminator("kind"),
]


class ExecutionProfileFields(ProfileValue):
    name: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    mode: Literal["attached", "submitted_local", "submitted_remote"]
    parsl_config: ParslConfigRefValue
    executor_bindings: dict[str, ExecutorBindingValue]
    environment_routes: dict[str, str] = Field(default_factory=dict)
    shared_runtime_root: str | None = None
    task_policy: ParslTaskPolicyValue = Field(default_factory=ParslTaskPolicyValue)
    launch: LaunchValue | None = None
    transport: SSHSubmissionTransportValue | None = None
    remote_workflow_root: str | None = None
    pre_launch: PreLaunchValue | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must be non-empty")
        return value

    @model_validator(mode="after")
    def validate_mode_contract(self) -> ExecutionProfileFields:
        if not self.executor_bindings:
            raise ValueError("executor_bindings must not be empty")
        for label, binding in self.executor_bindings.items():
            if label != binding.label:
                raise ValueError("executor binding keys must match their labels")
        unknown_routes = sorted(set(self.environment_routes.values()) - set(self.executor_bindings))
        if unknown_routes:
            raise ValueError(f"environment_routes reference unknown executors: {unknown_routes}")

        if self.mode == "attached":
            if any(
                value is not None
                for value in (
                    self.launch,
                    self.transport,
                    self.remote_workflow_root,
                    self.pre_launch,
                )
            ):
                raise ValueError("attached profiles cannot define launch, transport, or pre-launch")
        elif self.mode == "submitted_local":
            if not isinstance(self.launch, LocalLaunchValue):
                raise ValueError("submitted_local profiles require a local launch")
            if any(
                value is not None
                for value in (self.transport, self.remote_workflow_root, self.pre_launch)
            ):
                raise ValueError("submitted_local profiles cannot define remote fields")
        else:
            if not isinstance(self.launch, PSIJLaunchValue):
                raise ValueError("submitted_remote profiles require a PSI/J launch")
            if self.transport is None or self.remote_workflow_root is None:
                raise ValueError(
                    "submitted_remote profiles require transport and remote_workflow_root"
                )
            root = PurePosixPath(self.remote_workflow_root)
            if not root.is_absolute() or str(root) != self.remote_workflow_root:
                raise ValueError("remote_workflow_root must be a normalized absolute POSIX path")
            if self.pre_launch is not None:
                self.pre_launch.to_library()
        return self

    def library_bindings(self):
        return {label: value.to_library() for label, value in self.executor_bindings.items()}


class ExecutionProfileCreate(ExecutionProfileFields):
    pass


class DistributedExecutionProfile(ExecutionProfileFields):
    schema_: Literal["bioimageflow.platform.execution-profile.v1"] = Field(
        default="bioimageflow.platform.execution-profile.v1", alias="schema"
    )
    id: str = Field(pattern=r"^profile_[0-9a-f]{32}$")
    revision: int = Field(ge=1)


class ExecutionProfilePatch(ProfileValue):
    expected_revision: int = Field(ge=1)
    profile: ExecutionProfileCreate


class ExecutionProfileList(ProfileValue):
    editable: bool
    profiles: list[DistributedExecutionProfile]


class ExecutionProfileTestResult(ProfileValue):
    profile_id: str
    profile_revision: int
    mode: Literal["attached", "submitted_local", "submitted_remote"]
    report: dict[str, Any]


class CapabilityStatusValue(ProfileValue):
    supported: bool
    reason: str | None = None


class ExecutionCapabilitiesValue(ProfileValue):
    schema_: Literal["bioimageflow.execution_capabilities.v1"] = Field(alias="schema")
    capabilities: dict[str, CapabilityStatusValue]


class ExecutionTargetValue(ProfileValue):
    id: str
    name: str
    kind: Literal["local", "profile"]
    mode: Literal["local", "attached", "submitted_local", "submitted_remote"]
    available: bool
    disabled_reason: str | None = None
    profile_revision: int | None = None


class ExecutionTargetsValue(ProfileValue):
    capabilities: ExecutionCapabilitiesValue
    targets: list[ExecutionTargetValue]
