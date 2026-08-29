from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import bioimageflow
import pytest

from bioimageflow_server.models.execution_preflight import ExecutionPreflightRequest
from bioimageflow_server.services.execution_preflight import (
    DistributedPreflightService,
    PreparedRunAcceptance,
    PreparedSubmissionTokenManager,
    PreparedTokenConflict,
    preflight_binding,
)


class _Intent:
    def __init__(self) -> None:
        self.closed = False
        self.calls = 0

    def submit(self) -> object:
        self.calls += 1
        return SimpleNamespace(id="run_" + "1" * 32)

    def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_token_consumes_exact_intent_once_and_checks_binding() -> None:
    manager = PreparedSubmissionTokenManager()
    intent = _Intent()
    token, _ = await manager.issue(intent, binding="expected", lifetime=60)
    with pytest.raises(PreparedTokenConflict):
        await manager.consume(token, binding="different")
    assert intent.closed and intent.calls == 0

    intent = _Intent()
    token, _ = await manager.issue(intent, binding="expected", lifetime=60)
    handle = await manager.consume(token, binding="expected")
    assert handle.id == "run_" + "1" * 32
    assert intent.closed and intent.calls == 1


@pytest.mark.anyio
async def test_preflight_resolves_paths_then_directly_submits(monkeypatch: pytest.MonkeyPatch) -> None:
    path_item = SimpleNamespace(
        scoped_node_path="preprocessing/files",
        input_name="path",
        value_shape="path",
    )
    path_plan = SimpleNamespace(
        inputs=(path_item,),
        to_dict=lambda: {
            "schema": "bioimageflow.remote_node_path_plan.v1",
            "allocates_resources": False,
            "reads_local_files": False,
            "inputs": [
                {
                    "scoped_node_path": "preprocessing/files",
                    "input_name": "path",
                    "value_shape": "path",
                    "nullable": False,
                    "path_picker": "folder",
                    "current_paths": [],
                    "cluster_compatible": True,
                }
            ],
        },
    )
    monkeypatch.setattr(bioimageflow, "inspect_remote_node_paths", lambda _workflow: path_plan)
    captured: dict[str, Any] = {}

    class _Cluster:
        def submit(self, workflow: object, **kwargs: Any) -> object:
            captured.update(kwargs)
            return SimpleNamespace(id="run_" + "2" * 32, status="prepared")

    profile = SimpleNamespace(
        id="cluster",
        revision=1,
        cluster=_Cluster(),
        workflow_storage_path=Path("/tmp/results"),
    )
    service = DistributedPreflightService(
        workflows=SimpleNamespace(resolve_workflow=lambda *_args: object()),
        profiles=SimpleNamespace(resolve_target=lambda *_args: profile),
        uploads=SimpleNamespace(resolve_upload=lambda value: Path("/authorized") / value),
        tokens=PreparedSubmissionTokenManager(),
    )
    request = ExecutionPreflightRequest(
        workflow_id="demo",
        draft_revision=3,
        target_id="cluster",
        profile_revision=1,
    )
    unresolved = await service.preflight(request)
    assert unresolved.kind == "resolution_required"

    ready_request = request.model_copy(
        update={
            "node_path_choices": {
                "preprocessing/files": {"path": {"source": "upload", "value": "dataset"}}
            }
        }
    )
    ready = await service.preflight(ready_request)
    assert ready.kind == "ready"
    accepted = await service.tokens.consume(
        ready.token,
        binding=preflight_binding(ready_request),
    )
    assert isinstance(accepted, PreparedRunAcceptance)
    assert accepted.handle.id == "run_" + "2" * 32
    override = captured["node_input_overrides"]["preprocessing/files"]["path"]
    assert override.path == Path("/authorized/dataset")
    assert "inputs" not in captured


@pytest.mark.anyio
@pytest.mark.parametrize(
    "value",
    [
        "relative",
        "//cluster/path",
        "/cluster//path",
        "/cluster/./path",
        "/cluster/../path",
        "/cluster/path/",
        "/cluster/path\x00suffix",
        "/cluster/path\nsuffix",
        "/cluster/path\rsuffix",
    ],
)
async def test_cluster_path_must_be_exact_normalized_absolute_posix(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    item = SimpleNamespace(scoped_node_path="files", input_name="path", value_shape="path")
    plan = SimpleNamespace(inputs=(item,), to_dict=lambda: {"inputs": []})
    monkeypatch.setattr(bioimageflow, "inspect_remote_node_paths", lambda _workflow: plan)
    profile = SimpleNamespace(
        id="cluster",
        revision=1,
        cluster=object(),
        workflow_storage_path=None,
    )
    service = DistributedPreflightService(
        workflows=SimpleNamespace(resolve_workflow=lambda *_args: object()),
        profiles=SimpleNamespace(resolve_target=lambda *_args: profile),
        uploads=SimpleNamespace(resolve_upload=Path),
        tokens=PreparedSubmissionTokenManager(),
    )
    request = ExecutionPreflightRequest(
        workflow_id="demo",
        draft_revision=0,
        target_id="cluster",
        profile_revision=1,
        node_path_choices={"files": {"path": {"source": "cluster", "value": value}}},
    )
    with pytest.raises(ValueError, match="normalized absolute POSIX"):
        await service.preflight(request)


def test_cluster_path_decoder_returns_exact_path() -> None:
    service = DistributedPreflightService(
        workflows=SimpleNamespace(),
        profiles=SimpleNamespace(),
        uploads=SimpleNamespace(),
        tokens=PreparedSubmissionTokenManager(),
    )

    decoded = service._decode_value(
        {"source": "cluster", "value": "/shared/project/input.tif"}
    )

    assert decoded == Path("/shared/project/input.tif")
    assert isinstance(decoded, Path)
