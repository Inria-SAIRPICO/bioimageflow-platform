"""Managed-cluster path resolution and short-lived direct-submit intents."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from bioimageflow_server.models.execution_preflight import (
    ExecutionPreflightRequest,
    ReadyPreflight,
    RemotePathLeaf,
    ResolutionRequiredPreflight,
)


class PreparedTokenError(RuntimeError):
    pass


class PreparedTokenExpired(PreparedTokenError):
    pass


class PreparedTokenConflict(PreparedTokenError):
    pass


class DistributedProfile(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def revision(self) -> int: ...

    @property
    def cluster(self) -> Any: ...

    @property
    def workflow_storage_path(self) -> str | Path | None: ...


class ExecutionProfileResolver(Protocol):
    def resolve_target(
        self,
        target_id: str,
        workflow_id: str,
        profile_revision: int,
    ) -> DistributedProfile: ...


class PreflightWorkflowResolver(Protocol):
    def resolve_workflow(
        self,
        workflow_id: str,
        draft_revision: int,
        storage_path: str | Path | None = None,
    ) -> Any: ...


class UploadPathResolver(Protocol):
    def resolve_upload(self, value: str) -> Path: ...


@dataclass(frozen=True)
class PreparedRunAcceptance:
    handle: Any | None
    profile: DistributedProfile
    request: ExecutionPreflightRequest
    uncertainty: Any | None = None


class ManagedSubmitIntent:
    """One exact in-process intent consumed by a direct ``RemoteCluster.submit``."""

    expired = False

    def __init__(
        self,
        *,
        workflow: Any,
        profile: DistributedProfile,
        request: ExecutionPreflightRequest,
        inputs: Mapping[str, Any],
        overrides: Mapping[str, Mapping[str, Any]],
    ) -> None:
        self._workflow = workflow
        self._profile = profile
        self._request = request.model_copy(deep=True)
        self._inputs = dict(inputs)
        self._overrides = {path: dict(values) for path, values in overrides.items()}
        self._closed = False
        self._submitted = False

    def submit(self, _transport: object = None) -> PreparedRunAcceptance:
        if self._closed or self._submitted:
            raise RuntimeError("Managed submit intent was already consumed")
        self._submitted = True
        try:
            handle = self._profile.cluster.submit(
                self._workflow,
                inputs=self._inputs or None,
                targets=self._request.requested_nodes,
                node_input_overrides=self._overrides or None,
            )
        except Exception as exc:
            cluster_api = importlib.import_module("bioimageflow.cluster")

            if isinstance(exc, cluster_api.RemoteSubmissionUncertainError):
                return PreparedRunAcceptance(None, self._profile, self._request, exc)
            raise
        return PreparedRunAcceptance(handle, self._profile, self._request)

    def close(self) -> None:
        self._closed = True


@dataclass
class _PreparedEntry:
    prepared: Any
    binding: str
    expires_at: float


class PreparedSubmissionTokenManager:
    def __init__(self) -> None:
        self._entries: dict[str, _PreparedEntry] = {}
        self._lock = asyncio.Lock()

    async def issue(
        self,
        prepared: Any,
        *,
        transport: Any = None,
        binding: str,
        lifetime: float,
    ) -> tuple[str, float]:
        del transport
        expires_at = time.time() + lifetime
        token = uuid4().hex
        async with self._lock:
            self._entries[token] = _PreparedEntry(prepared, binding, expires_at)
        return token, expires_at

    async def consume(self, token: str, *, binding: str) -> Any:
        async with self._lock:
            entry = self._entries.pop(token, None)
        if entry is None:
            raise PreparedTokenError("Managed submit token is unknown or already consumed")
        if entry.binding != binding:
            entry.prepared.close()
            raise PreparedTokenConflict("Managed submit token does not match this invocation")
        if time.time() >= entry.expires_at:
            entry.prepared.close()
            raise PreparedTokenExpired("Managed submit token expired")
        try:
            # Direct submit intentionally has a small crash window before the returned
            # durable run ID can be persisted. The public API owns all later recovery.
            return await asyncio.to_thread(entry.prepared.submit)
        finally:
            entry.prepared.close()

    async def abandon(self, token: str) -> None:
        async with self._lock:
            entry = self._entries.pop(token, None)
        if entry is not None:
            entry.prepared.close()

    async def reap_expired(self) -> int:
        now = time.time()
        async with self._lock:
            expired = [token for token, entry in self._entries.items() if entry.expires_at <= now]
            entries = [self._entries.pop(token) for token in expired]
        for entry in entries:
            entry.prepared.close()
        return len(entries)

    async def close(self) -> None:
        async with self._lock:
            entries = list(self._entries.values())
            self._entries.clear()
        for entry in entries:
            entry.prepared.close()


def invocation_binding(
    *,
    workflow_id: str,
    draft_revision: int,
    target_id: str,
    requested_nodes: list[str] | None = None,
) -> str:
    payload = {
        "workflow_id": workflow_id,
        "draft_revision": draft_revision,
        "target_id": target_id,
        "requested_nodes": requested_nodes,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def preflight_binding(request: ExecutionPreflightRequest) -> str:
    return invocation_binding(
        workflow_id=request.workflow_id,
        draft_revision=request.draft_revision,
        target_id=request.target_id,
        requested_nodes=request.requested_nodes,
    )


class DistributedPreflightService:
    """Resolve explicit local-upload/cluster-path choices without remote allocation."""

    def __init__(
        self,
        *,
        workflows: PreflightWorkflowResolver,
        profiles: ExecutionProfileResolver,
        uploads: UploadPathResolver,
        tokens: PreparedSubmissionTokenManager,
        preparation_lifetime: float = 900,
    ) -> None:
        self._workflows = workflows
        self._profiles = profiles
        self._uploads = uploads
        self.tokens = tokens
        self._preparation_lifetime = preparation_lifetime

    async def preflight(
        self,
        request: ExecutionPreflightRequest,
    ) -> ResolutionRequiredPreflight | ReadyPreflight:
        profile = await asyncio.to_thread(
            self._profiles.resolve_target,
            request.target_id,
            request.workflow_id,
            request.profile_revision,
        )
        workflow = await asyncio.to_thread(
            self._workflows.resolve_workflow,
            request.workflow_id,
            request.draft_revision,
            profile.workflow_storage_path,
        )
        import bioimageflow

        path_plan = await asyncio.to_thread(bioimageflow.inspect_remote_node_paths, workflow)
        unresolved = [
            {"scoped_node_path": item.scoped_node_path, "input_name": item.input_name}
            for item in path_plan.inputs
            if item.scoped_node_path not in request.node_path_choices
            or item.input_name not in request.node_path_choices[item.scoped_node_path]
        ]
        if unresolved:
            return ResolutionRequiredPreflight(
                remote_node_paths=path_plan.to_dict(),
                unresolved=unresolved,
            )
        overrides = self._decode_overrides(path_plan, request.node_path_choices)
        inputs = {key: self._decode_value(value) for key, value in request.root_inputs.items()}
        intent = ManagedSubmitIntent(
            workflow=workflow,
            profile=profile,
            request=request,
            inputs=inputs,
            overrides=overrides,
        )
        token, expires_at = await self.tokens.issue(
            intent,
            binding=preflight_binding(request),
            lifetime=self._preparation_lifetime,
        )
        return ReadyPreflight(
            token=token,
            expires_at=expires_at,
            resolved_inputs=len(request.root_inputs) + len(path_plan.inputs),
        )

    def _decode_overrides(
        self,
        path_plan: Any,
        choices: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        expected = {(item.scoped_node_path, item.input_name) for item in path_plan.inputs}
        supplied = {
            (scoped_node_path, input_name)
            for scoped_node_path, fields in choices.items()
            for input_name in fields
        }
        if supplied != expected:
            raise ValueError("Remote node path choices do not exactly match discovery")
        result: dict[str, dict[str, Any]] = {}
        for item in path_plan.inputs:
            decoded = self._decode_value(choices[item.scoped_node_path][item.input_name])
            if item.value_shape == "tuple" and isinstance(decoded, list):
                decoded = tuple(decoded)
            result.setdefault(item.scoped_node_path, {})[item.input_name] = decoded
        return result

    def _decode_value(self, raw: Any) -> Any:
        if isinstance(raw, list):
            return [self._decode_value(item) for item in raw]
        if not isinstance(raw, dict) or "source" not in raw:
            return raw
        leaf = RemotePathLeaf.model_validate(raw)
        if leaf.source == "none":
            return None
        if leaf.source == "cluster":
            value = Path(leaf.value or "")
            if not value.is_absolute():
                raise ValueError("Cluster paths must be absolute")
            return value
        cluster_api = importlib.import_module("bioimageflow.cluster")

        return cluster_api.LocalUpload(self._uploads.resolve_upload(leaf.value or ""))
