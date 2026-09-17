"""Strict local output-favorite contracts."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Discriminator, Field, model_validator


class PersistentOutputPreferenceKey(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["persistent"] = "persistent"
    workspace_id: UUID
    workflow_id: str = Field(min_length=1)
    identity_generation: int = Field(ge=0)
    node_path: tuple[str, ...] = Field(min_length=1)
    output_key: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_path(self) -> "PersistentOutputPreferenceKey":
        if any(not part or "/" in part for part in self.node_path):
            raise ValueError("node_path contains an invalid structural node ID")
        return self


class SessionOutputPreferenceKey(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["session"] = "session"
    workspace_id: UUID
    session_id: str = Field(min_length=1)
    node_path: tuple[str, ...] = Field(min_length=1)
    output_key: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_path(self) -> "SessionOutputPreferenceKey":
        if any(not part or "/" in part for part in self.node_path):
            raise ValueError("node_path contains an invalid structural node ID")
        return self


OutputPreferenceKey = Annotated[
    PersistentOutputPreferenceKey | SessionOutputPreferenceKey,
    Discriminator("kind"),
]


class ViewerFavorite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: OutputPreferenceKey
    environment_id: UUID


class ViewerPreferencesSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferences_version: Literal[1] = 1
    revision: int = Field(ge=0)
    favorites: list[ViewerFavorite] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_keys(self) -> "ViewerPreferencesSnapshot":
        keys = [favorite.key for favorite in self.favorites]
        if len(keys) != len(set(keys)):
            raise ValueError("viewer favorite keys must be unique")
        return self


class ViewerFavoriteSetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: OutputPreferenceKey
    environment_id: UUID
    expected_revision: int = Field(ge=0)


class ViewerFavoriteUnsetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: OutputPreferenceKey
    expected_environment_id: UUID
    expected_revision: int = Field(ge=0)


class ViewerFavoriteToggleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: OutputPreferenceKey
    environment_id: UUID
    expected_revision: int = Field(ge=0)
