from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import bioimageflow
import pytest

from bioimageflow_server.models.execution_preflight import ExecutionPreflightRequest
from bioimageflow_server.services.execution_preflight import (
    DistributedPreflightService,
    PreparedSubmissionTokenManager,
    PreparedTokenConflict,
    preflight_binding,
)


class _Prepared:
    expired = False

    def __init__(self) -> None:
        self.closed = False
        self.submit_calls: list[object] = []
        self.manifest = SimpleNamespace(to_dict=lambda: {"bundle_digest": "digest"})

    def submit(self, transport: object) -> object:
        self.submit_calls.append(transport)
        return SimpleNamespace(id="run_remote", status="prepared")

    def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_token_consumes_exact_prepared_object_once_and_checks_binding() -> None:
    manager = PreparedSubmissionTokenManager()
    prepared = _Prepared()
    token, _ = await manager.issue(
        prepared,
        transport="ssh",
        binding="expected",
        lifetime=60,
    )

    with pytest.raises(PreparedTokenConflict):
        await manager.consume(token, binding="different")
    assert prepared.closed
    assert prepared.submit_calls == []

    prepared = _Prepared()
    token, _ = await manager.issue(
        prepared,
        transport="ssh",
        binding="expected",
        lifetime=60,
    )
    handle = await manager.consume(token, binding="expected")
    assert handle.id == "run_remote"
    assert prepared.submit_calls == ["ssh"]
    assert prepared.closed


@pytest.mark.anyio
async def test_remote_preflight_requires_choices_then_prepares_manifest(monkeypatch) -> None:
    prepared = _Prepared()
    captured: dict[str, Any] = {}
    path_item = SimpleNamespace(
        scoped_node_path="preprocessing/files",
        input_name="path",
        value_shape="path",
    )
    path_plan = SimpleNamespace(
        inputs=(path_item,),
        to_dict=lambda: {"inputs": [{"scoped_node_path": "preprocessing/files"}]},
    )

    class _Plan:
        def to_dict(self) -> dict[str, Any]:
            return {"nodes": []}

    monkeypatch.setattr(bioimageflow, "plan_distributed_execution", lambda *a, **k: _Plan(), raising=False)
    monkeypatch.setattr(bioimageflow, "inspect_remote_node_paths", lambda workflow: path_plan, raising=False)

    def prepare(*args: Any, **kwargs: Any) -> _Prepared:
        captured.update(kwargs)
        return prepared

    monkeypatch.setattr(bioimageflow, "prepare_remote_submission", prepare, raising=False)
    monkeypatch.setattr(
        bioimageflow,
        "LocalUpload",
        lambda path: SimpleNamespace(path=path),
        raising=False,
    )
    profile = SimpleNamespace(
        id="cluster",
        revision=1,
        mode="submitted_remote",
        transport="ssh",
        planning_arguments=lambda: {"executor_bindings": {}},
        submission_arguments=lambda: {
            "parsl_config": "config",
            "executor_bindings": {},
            "launch": "launch",
        },
    )
    service = DistributedPreflightService(
        workflows=SimpleNamespace(resolve_workflow=lambda workflow_id, revision: object()),
        profiles=SimpleNamespace(resolve_target=lambda target_id: profile),
        uploads=SimpleNamespace(resolve_upload=lambda value: Path("/authorized") / value),
        tokens=PreparedSubmissionTokenManager(),
    )
    unresolved_request = ExecutionPreflightRequest(
        workflow_id="demo",
        draft_revision=3,
        target_id="cluster",
    )
    unresolved = await service.preflight(unresolved_request)
    assert unresolved.kind == "resolution_required"

    ready_request = unresolved_request.model_copy(
        update={
            "node_path_choices": {
                "preprocessing/files": {
                    "path": {"source": "upload", "value": "dataset"}
                }
            }
        }
    )
    ready = await service.preflight(ready_request)
    assert ready.kind == "ready"
    assert ready.manifest == {"bundle_digest": "digest"}
    override = captured["node_input_overrides"]["preprocessing/files"]["path"]
    assert override.path == Path("/authorized/dataset")

    handle = await service.tokens.consume(ready.token, binding=preflight_binding(ready_request))
    assert handle.id == "run_remote"
    assert prepared.submit_calls == ["ssh"]
