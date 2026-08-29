from __future__ import annotations

import json
from pathlib import Path

from bioimageflow_server.models.execution_runtime import ExecutionSnapshot
from bioimageflow_server.services.execution_registry import ExecutionRegistry


def test_migration_preserves_local_v1_and_erases_legacy_distributed_bytes(
    tmp_path: Path,
) -> None:
    registry = ExecutionRegistry(tmp_path)
    registry.root.mkdir(parents=True)
    local = ExecutionSnapshot(
        execution_id="run_" + "1" * 32,
        workflow_id="local",
        backend="direct",
        target_id="local",
        target_snapshot={"name": "Local", "mode": "local"},
        state="succeeded",
    ).model_dump(mode="json")
    local["schema_version"] = 1
    local_path = registry.root / f"{local['execution_id']}.json"
    local_path.write_text(json.dumps(local), encoding="utf-8")

    legacy_id = "run_" + "2" * 32
    legacy_path = registry.root / f"{legacy_id}.json"
    legacy_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "execution_id": legacy_id,
                "workflow_id": "remote",
                "backend": "submitted_remote",
                "target_id": "legacy",
                "state": "failed",
                "target_snapshot": {"transport": {"password": "must-disappear"}},
            }
        ),
        encoding="utf-8",
    )
    retry_dir = registry.root / "retry_plans"
    retry_dir.mkdir()
    retry = retry_dir / "legacy.json"
    retry.write_text(
        json.dumps({"plan": {"parent_run_id": legacy_id}}),
        encoding="utf-8",
    )

    assert registry.migrate() == (1, 1)
    assert registry.get(local["execution_id"]).backend == "direct"
    assert json.loads(local_path.read_text(encoding="utf-8"))["schema_version"] == 2
    assert not legacy_path.exists()
    assert not retry.exists()
    assert "must-disappear" not in "".join(
        path.read_text(encoding="utf-8")
        for path in registry.root.rglob("*.json")
    )
