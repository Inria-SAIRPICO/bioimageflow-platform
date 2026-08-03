"""Public BioImageFlow planning and immutable prepared-submission boundary."""

from __future__ import annotations

import asyncio
import hashlib
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
    id: str
    revision: int
    mode: str
    transport: Any | None

    def planning_arguments(self) -> Mapping[str, Any]: ...

    def submission_arguments(self) -> Mapping[str, Any]: ...


class ExecutionProfileResolver(Protocol):
    def resolve_target(self, target_id: str) -> DistributedProfile: ...


class PreflightWorkflowResolver(Protocol):
    def resolve_workflow(self, workflow_id: str, draft_revision: int) -> Any: ...


class UploadPathResolver(Protocol):
    """Authorize a desktop-local path or managed dataset reference."""

    def resolve_upload(self, value: str) -> Path: ...


@dataclass
class _PreparedEntry:
    prepared: Any
    transport: Any
    binding: str
    expires_at: float


class PreparedSubmissionTokenManager:
    """Own live process-local preparations and consume each exact object once."""

    def __init__(self) -> None:
        self._entries: dict[str, _PreparedEntry] = {}
        self._lock = asyncio.Lock()

    async def issue(
        self,
        prepared: Any,
        *,
        transport: Any,
        binding: str,
        lifetime: float,
    ) -> tuple[str, float]:
        expires_at = time.time() + lifetime
        token = uuid4().hex
        async with self._lock:
            self._entries[token] = _PreparedEntry(prepared, transport, binding, expires_at)
        return token, expires_at

    async def consume(self, token: str, *, binding: str) -> Any:
        async with self._lock:
            entry = self._entries.pop(token, None)
        if entry is None:
            raise PreparedTokenError("Prepared submission token is unknown or already consumed")
        if entry.binding != binding:
            entry.prepared.close()
            raise PreparedTokenConflict("Prepared submission token does not match this invocation")
        if time.time() >= entry.expires_at or getattr(entry.prepared, "expired", False):
            entry.prepared.close()
            raise PreparedTokenExpired("Prepared submission token expired")
        try:
            return await asyncio.to_thread(entry.prepared.submit, entry.transport)
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
        workflow = await asyncio.to_thread(
            self._workflows.resolve_workflow,
            request.workflow_id,
            request.draft_revision,
        )
        profile = await asyncio.to_thread(self._profiles.resolve_target, request.target_id)
        import bioimageflow

        inspect_remote_node_paths = getattr(bioimageflow, "inspect_remote_node_paths")
        plan_distributed_execution = getattr(bioimageflow, "plan_distributed_execution")

        planning_arguments = dict(profile.planning_arguments())
        planning_arguments["node_routes"] = request.node_routes or planning_arguments.get("node_routes")
        plan = await asyncio.to_thread(
            plan_distributed_execution,
            workflow,
            targets=request.requested_nodes,
            **planning_arguments,
        )
        plan_payload = plan.to_dict()
        if profile.mode != "submitted_remote":
            # Attached/submitted-local acceptance is performed by the runtime/profile layer.
            return ReadyPreflight(
                distributed_plan=plan_payload,
                manifest=None,
            )

        path_plan = await asyncio.to_thread(inspect_remote_node_paths, workflow)
        unresolved = [
            {
                "scoped_node_path": item.scoped_node_path,
                "input_name": item.input_name,
            }
            for item in path_plan.inputs
            if item.scoped_node_path not in request.node_path_choices
            or item.input_name not in request.node_path_choices[item.scoped_node_path]
        ]
        if unresolved:
            return ResolutionRequiredPreflight(
                distributed_plan=plan_payload,
                remote_node_paths=path_plan.to_dict(),
                unresolved=unresolved,
            )

        overrides = self._decode_overrides(path_plan, request.node_path_choices)
        prepare_remote_submission = getattr(bioimageflow, "prepare_remote_submission")

        prepared = await asyncio.to_thread(
            prepare_remote_submission,
            workflow,
            inputs=request.root_inputs,
            targets=request.requested_nodes,
            node_input_overrides=overrides,
            lifetime=self._preparation_lifetime,
            **dict(profile.submission_arguments()),
        )
        token, expires_at = await self.tokens.issue(
            prepared,
            transport=profile.transport,
            binding=preflight_binding(request),
            lifetime=self._preparation_lifetime,
        )
        return ReadyPreflight(
            token=token,
            expires_at=expires_at,
            distributed_plan=plan_payload,
            manifest=prepared.manifest.to_dict(),
        )

    def _decode_overrides(self, path_plan: Any, choices: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        expected = {
            (item.scoped_node_path, item.input_name)
            for item in path_plan.inputs
        }
        supplied = {
            (scoped_node_path, input_name)
            for scoped_node_path, fields in choices.items()
            for input_name in fields
        }
        if supplied != expected:
            raise ValueError("Remote node path choices do not exactly match discovery")
        result: dict[str, dict[str, Any]] = {}
        for item in path_plan.inputs:
            raw = choices[item.scoped_node_path][item.input_name]
            decoded = self._decode_value(raw)
            if item.value_shape == "tuple" and isinstance(decoded, list):
                decoded = tuple(decoded)
            result.setdefault(item.scoped_node_path, {})[item.input_name] = decoded
        return result

    def _decode_value(self, raw: Any) -> Any:
        if isinstance(raw, list):
            return [self._decode_value(item) for item in raw]
        leaf = RemotePathLeaf.model_validate(raw)
        if leaf.source == "none":
            return None
        if leaf.source == "cluster":
            return Path(leaf.value or "")
        import bioimageflow

        local_upload = getattr(bioimageflow, "LocalUpload")
        return local_upload(self._uploads.resolve_upload(leaf.value or ""))
