"""Application settings models."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from bioimageflow_server.models.napari_environments import (
    NapariEnvironment,
    NapariEnvironmentOperation,
    NapariFilenameRule,
)


_DEFAULT_MAX_UPLOAD_SIZE = 2 * 1024**3  # 2 GB (v1 §2.4.10)


class OMEROInstance(BaseModel):
    """OMERO server connection configuration."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    host: str
    port: int = Field(default=4064, ge=1, le=65535)
    username: str

    @field_validator("name", mode="before")
    @classmethod
    def _trim_optional_name(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("host", "username", mode="before")
    @classmethod
    def _trim_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("host", "username")
    @classmethod
    def _require_non_empty_text(cls, value: str) -> str:
        if not value:
            raise ValueError("OMERO host and username must be non-empty")
        return value

    def effective_name(self) -> str:
        """Return the display name used for uniqueness checks."""
        return self.name or f"{self.host}:{self.username}"


class OMEROInstancePatch(OMEROInstance):
    """API-facing OMERO instance patch with transient password input."""

    password: str | None = None


class OMEROInstanceResponse(OMEROInstance):
    """API-facing OMERO instance response with non-secret password state."""

    password_stored: bool


class Settings(BaseModel):
    """Application settings from GET/PATCH /settings.

    The model rejects unknown fields (``extra="forbid"``) so typos in PATCH
    bodies surface as 422s rather than being silently dropped. ``dev_mode``
    is permissive at the model layer; the GUI router rejects ``dev_mode=False``.
    """

    model_config = ConfigDict(extra="forbid")

    deployment_mode: Literal["desktop", "webapp"]
    external_editor: str | None = None
    fiji_path: str | None = None
    napari_registry_revision: int = Field(default=0, ge=0)
    napari_environments: list[NapariEnvironment] = Field(default_factory=list)
    napari_default_environment_id: UUID | None = None
    napari_filename_rules: list[NapariFilenameRule] = Field(default_factory=list)
    napari_environment_operations: list[NapariEnvironmentOperation] = Field(default_factory=list)
    omero_instances: list[OMEROInstance] = []
    tool_store_path: str = "~/.bioimageflow/tool_packages/"
    update_mode: Literal["auto", "manual"] | str = "auto"
    new_workflow_execution: Literal["sequential", "parallel"] = "sequential"
    default_execution_target_id: str = "local"
    node_data_page_size: Literal[25, 50, 100, 250, 500] = 250
    keyboard_shortcuts: dict[str, str] = {}
    dev_mode: bool = True
    enable_unsafe_webapp_features: bool = False
    datasets_root: str | None = None
    max_upload_size: int = _DEFAULT_MAX_UPLOAD_SIZE
    workspace_path: str | None = None
    workspaces_root: str | None = None

    @field_validator("fiji_path", mode="before")
    @classmethod
    def _normalize_fiji_path(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("default_execution_target_id", mode="before")
    @classmethod
    def _normalize_default_target(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("default_execution_target_id must be non-empty")
        return value

    @model_validator(mode="after")
    def _validate_unique_omero_instance_names(self) -> "Settings":
        seen: set[str] = set()
        for instance in self.omero_instances:
            effective_name = instance.effective_name()
            if effective_name in seen:
                raise ValueError("OMERO instance names must be unique")
            seen.add(effective_name)
        return self

    @model_validator(mode="after")
    def _validate_napari_registry(self) -> "Settings":
        ids = [environment.id for environment in self.napari_environments]
        if len(ids) != len(set(ids)):
            raise ValueError("napari environment IDs must be unique")
        names = [environment.name.casefold() for environment in self.napari_environments]
        if len(names) != len(set(names)):
            raise ValueError("napari environment names must be unique ignoring case")
        roots = [environment.root.casefold() for environment in self.napari_environments]
        if len(roots) != len(set(roots)):
            raise ValueError("napari environment roots must be unique")
        orders = [environment.registration_order for environment in self.napari_environments]
        if len(orders) != len(set(orders)):
            raise ValueError("napari environment registration orders must be unique")
        known = set(ids)
        if self.napari_default_environment_id is not None:
            if self.napari_default_environment_id not in known:
                raise ValueError("napari default environment must be registered")
        rule_ids = [rule.id for rule in self.napari_filename_rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("napari filename rule IDs must be unique")
        if any(rule.environment_id not in known for rule in self.napari_filename_rules):
            raise ValueError("napari filename rules must reference registered environments")
        patterns = [rule.pattern.casefold() for rule in self.napari_filename_rules]
        if len(patterns) != len(set(patterns)):
            raise ValueError("napari filename rule patterns must be unique ignoring case")
        operation_ids = [operation.id for operation in self.napari_environment_operations]
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("napari environment operation IDs must be unique")
        active_by_environment: set[UUID] = set()
        for operation in self.napari_environment_operations:
            if operation.state in {"completed", "failed", "cancelled"}:
                continue
            if operation.environment_id in active_by_environment:
                raise ValueError("napari environments allow only one active mutation")
            active_by_environment.add(operation.environment_id)
            if operation.environment_id not in known:
                raise ValueError("active napari operations must reference registered environments")
        return self
