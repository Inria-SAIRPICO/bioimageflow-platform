"""Narrow adapter for BioImageFlow workflow archive I/O."""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

from bioimageflow.workflow import Workflow as BioImageFlowWorkflow


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

    def export_archive(self, workflow_path: Path, archive_path: Path) -> None:
        raw = json.loads(workflow_path.read_text(encoding="utf-8"))
        library = raw.get("workflow", raw) if isinstance(raw, dict) else raw
        if not isinstance(library, dict):
            raise ValueError("Workflow file did not contain a library workflow object")
        with _workflow_import_scope(workflow_path.parent):
            result = BioImageFlowWorkflow.from_dict(library)
            workflow = cast(Any, result)
        workflow.export(archive_path)

    def read_archive(
        self,
        archive_path: Path,
        *,
        extract_to: Path | None = None,
    ) -> dict[str, Any]:
        if extract_to is None:
            workflow = BioImageFlowWorkflow.load(archive_path)
        else:
            workflow = BioImageFlowWorkflow.import_archive(archive_path, extract_to)
        return workflow.to_dict(include_custom_tools=False)
