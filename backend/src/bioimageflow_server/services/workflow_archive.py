"""Narrow adapter for BioImageFlow workflow archive I/O."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

from bioimageflow.workflow import Workflow as BioImageFlowWorkflow


def safe_workflow_export_stem(workflow_id: str) -> str:
    """Return a readable collision-resistant filename stem for one workflow ID."""

    if "/" not in workflow_id:
        return workflow_id
    digest = hashlib.sha256(workflow_id.encode("utf-8")).hexdigest()[:8]
    readable = workflow_id.replace("/", "--")
    readable_bytes = readable.encode("utf-8")
    if len(readable_bytes) > 120:
        readable = readable_bytes[:120].decode("utf-8", errors="ignore").rstrip(" -_")
    return f"{readable}-{digest}"


@contextmanager
def _workflow_import_scope(root: Path):
    root_str = str(root)
    sys.path.insert(0, root_str)
    previous_tools_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "tools" or name.startswith("tools.")
    }
    for name in list(previous_tools_modules):
        sys.modules.pop(name, None)
    try:
        yield
    finally:
        sys.path = [entry for entry in sys.path if entry != root_str]
        for name in [n for n in sys.modules if n == "tools" or n.startswith("tools.")]:
            sys.modules.pop(name, None)
        sys.modules.update(previous_tools_modules)


class BioImageFlowWorkflowArchiveAdapter:
    """Delegate workflow archive reads/writes to the BioImageFlow library."""

    def export_archive(
        self,
        workflow_data: dict[str, Any],
        archive_path: Path,
        *,
        storage_path: Path,
    ) -> None:
        """Export one accepted graph-plus-source snapshot through the library."""

        result = BioImageFlowWorkflow.from_dict(
            workflow_data,
            storage_path=storage_path,
        )
        workflow = cast(Any, result)
        workflow.export(archive_path)

    def read_archive(
        self,
        archive_path: Path,
        *,
        extract_to: Path | None = None,
        storage_path: Path,
    ) -> dict[str, Any]:
        """Read portable bytes without importing or installing tool packages."""

        del extract_to, storage_path
        with zipfile.ZipFile(archive_path) as archive:
            entries = [item for item in archive.infolist() if item.filename == "workflow.json"]
            if len(entries) != 1:
                raise ValueError("Workflow archive must contain exactly one workflow.json")
            document = json.loads(archive.read(entries[0]))
        if not isinstance(document, dict):
            raise ValueError("Workflow archive document must be an object")
        BioImageFlowWorkflow.inspect_viewing_requirements(document)
        return document

    def inspect_viewing_requirements(self, archive_path: Path) -> dict[str, Any]:
        return BioImageFlowWorkflow.inspect_viewing_requirements(archive_path).to_dict()
