"""Immutable public identities for retained workflow results."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResultArtifactIdentity(BaseModel):
    """Exact library run/node/record identity captured for a table source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1)
    node_key: str = Field(min_length=1)
    result_key: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
