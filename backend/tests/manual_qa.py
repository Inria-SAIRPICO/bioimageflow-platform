"""Prepare deterministic fixtures for maintainer-led manual QA sessions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from PIL import Image

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowSaveBody
from bioimageflow_server.services.custom_tools import CustomToolService
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService


MARKER_NAME = ".bioimageflow-manual-qa.json"
MARKER_SCHEMA = "bioimageflow-platform-manual-qa/v1"
RESULTS_BUNDLE_SCHEMA = "bioimageflow-results-bundle/v1"


QA_NUMBERS_SOURCE = '''\
"""Deterministic source tool for BioImageFlow manual QA."""

from typing import Any

import pandas as pd
from bioimageflow import DataFrameTool
from bioimageflow_core import IOModel


class QaNumberOutputs(IOModel):
    number: int
    label: str


class QaNumbers(DataFrameTool):
    display_name = "QA Numbers"
    documentation = "Create three deterministic rows for manual QA."
    accepts_upstream = False
    Outputs = QaNumberOutputs

    def transform(self, df: Any, arguments: Any) -> Any:
        return pd.DataFrame({"number": [1, 2, 3], "label": ["one", "two", "three"]})
'''


QA_INCREMENT_SOURCE = '''\
"""Deterministic transform tool for BioImageFlow manual QA."""

from typing import Any

from bioimageflow import DataFrameTool
from bioimageflow_core import IOModel


class QaIncrementOutputs(IOModel):
    number_plus_one: int


class QaIncrement(DataFrameTool):
    display_name = "QA Increment"
    documentation = "Add one to the number column in the connected DataFrame."
    Outputs = QaIncrementOutputs

    def transform(self, df: Any, arguments: Any) -> Any:
        result = df.copy()
        result["number_plus_one"] = result["number"] + 1
        return result
'''


QA_FAIL_SOURCE = '''\
"""Controlled failure tool for BioImageFlow manual QA."""

from typing import Any

from bioimageflow import DataFrameTool
from bioimageflow_core import IOModel


class QaFailOutputs(IOModel):
    number: int


class QaFail(DataFrameTool):
    display_name = "QA Controlled Failure"
    documentation = "Raise a controlled error after receiving the connected DataFrame."
    Outputs = QaFailOutputs

    def transform(self, df: Any, arguments: Any) -> Any:
        raise RuntimeError("Intentional manual QA failure")
'''


PYTHON_WORKFLOW_SOURCE = '''\
"""Trusted Python-authoring fixture for manual QA."""

from bioimageflow import Workflow


def build_workflow():
    return Workflow(
        name="qa_python_built",
        display_name="QA Python Built",
        engine="direct",
        execution="parallel",
    )
'''


def _empty_graph(name: str, display_name: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "name": name,
        "display_name": display_name,
        "nodes": [],
        "edges": [],
        "interface": {"inputs": [], "outputs": []},
        "config": {"engine": "direct", "execution": "parallel"},
    }


def _tool_node(
    node_id: str,
    tool_name: str,
    x: float,
    y: float,
    *,
    tool_module: str | None = None,
    tool_package: str | None = None,
    tool_package_version: str | None = None,
) -> dict[str, object]:
    node: dict[str, object] = {
        "type": "tool",
        "id": node_id,
        "name": tool_name,
        "tool_name": tool_name,
        "position": [x, y],
        "parameters": {},
    }
    if tool_module is not None:
        node.update(
            {
                "tool_module": tool_module,
                "tool_class": tool_name,
                "tool_package": tool_package,
                "tool_package_version": tool_package_version,
            }
        )
    return node


def _dataframe_edge(
    edge_id: str,
    source_node: str,
    target_node: str,
    *,
    target_position: int | None = None,
    target_input: str | None = None,
) -> dict[str, object]:
    edge: dict[str, object] = {
        "type": "dataframe",
        "id": edge_id,
        "source_node": source_node,
        "target_node": target_node,
    }
    if target_position is not None:
        edge["target_position"] = target_position
    if target_input is not None:
        edge["target_input"] = target_input
    return edge


def _reference_graph() -> GraphState:
    graph = _empty_graph("qa_reference", "QA Reference Workflow")
    graph["nodes"] = [
        _tool_node("numbers", "QaNumbers", 80, 120),
        _tool_node("increment", "QaIncrement", 380, 120),
    ]
    graph["edges"] = [
        _dataframe_edge(
            "numbers-to-increment",
            "numbers",
            "increment",
            target_position=0,
        )
    ]
    graph["interface"] = {
        "inputs": [],
        "outputs": [
            {
                "id": "incremented-output",
                "name": "Incremented number",
                "schema": {"type": "int"},
                "source": {"node": "increment", "column": "number_plus_one"},
            }
        ],
    }
    return GraphState.model_validate(graph)


def _child_graph() -> GraphState:
    graph = _empty_graph("qa_child", "QA Nested Child")
    graph["nodes"] = [_tool_node("increment", "QaIncrement", 180, 120)]
    graph["interface"] = {
        "inputs": [
            {
                "id": "numbers-dataframe-input",
                "name": "Numbers DataFrame",
                "kind": "dataframe",
                "schema": {"type": "DataFrame"},
                "targets": [
                    {
                        "node": "increment",
                        "port": {"kind": "positional", "index": 0},
                    }
                ],
            }
        ],
        "outputs": [
            {
                "id": "number-output",
                "name": "Incremented number",
                "schema": {"type": "int"},
                "source": {"node": "increment", "column": "number_plus_one"},
            }
        ],
    }
    return GraphState.model_validate(graph)


def _parent_graph(child: GraphState, artifact_hash: str) -> GraphState:
    graph = _empty_graph("qa_parent", "QA Nested Parent")
    graph["nodes"] = [
        _tool_node("numbers", "QaNumbers", 80, 120),
        {
            "type": "workflow",
            "id": "child",
            "name": "Nested Child",
            "workflow": child.model_dump(mode="json", by_alias=True),
            "bindings": {},
            "source": {
                "kind": "workspace",
                "workflow_id": "QA/Nested Child",
                "artifact_hash": artifact_hash,
            },
            "position": [400, 120],
        },
    ]
    graph["edges"] = [
        _dataframe_edge(
            "numbers-to-child",
            "numbers",
            "child",
            target_input="numbers-dataframe-input",
        )
    ]
    graph["interface"] = {
        "inputs": [],
        "outputs": [
            {
                "id": "parent-output",
                "name": "Nested result",
                "schema": {"type": "int"},
                "source": {"node": "child", "column": "number-output"},
            }
        ],
    }
    return GraphState.model_validate(graph)


def _failing_graph() -> GraphState:
    graph = _empty_graph("qa_failing", "QA Controlled Failure")
    graph["nodes"] = [
        _tool_node("numbers", "QaNumbers", 80, 120),
        _tool_node("failure", "QaFail", 380, 120),
    ]
    graph["edges"] = [
        _dataframe_edge(
            "numbers-to-failure",
            "numbers",
            "failure",
            target_position=0,
        )
    ]
    return GraphState.model_validate(graph)


def _write_inputs(root: Path) -> None:
    inputs = root / "inputs"
    inputs.mkdir(parents=True)
    image = Image.new("L", (32, 32))
    image.putdata([(x * 7 + y * 3) % 256 for y in range(32) for x in range(32)])
    image.save(inputs / "qa-gradient.tif")
    with (inputs / "qa-table.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["image", "condition", "replicate"])
        writer.writerow([str(inputs / "qa-gradient.tif"), "control", 1])
        writer.writerow([str(inputs / "qa-gradient.tif"), "treated", 2])


def _write_local_package(root: Path) -> None:
    destination = root / "packages" / "qa-manual-tools.zip"
    destination.parent.mkdir(parents=True)
    pyproject = '''\
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "qa-manual-tools"
version = "1.0.0"
description = "Dependency-free BioImageFlow manual QA tools"
requires-python = ">=3.12"
dependencies = []

[tool.setuptools]
packages = ["qa_manual_tools"]
'''
    package_source = QA_NUMBERS_SOURCE.replace("QaNumbers", "QaPackagedNumbers").replace(
        "QA Numbers", "QA Packaged Numbers"
    )
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("pyproject.toml", pyproject)
        archive.writestr("qa_manual_tools/__init__.py", package_source)


def _create_workflow(
    store: WorkflowStoreService,
    workflow_id: str,
    display_name: str,
    graph: GraphState,
    description: str,
) -> None:
    store.create_workflow(
        WorkflowCreate(
            name=workflow_id,
            display_name=display_name,
            description=description,
        )
    )
    store.save_workflow(workflow_id, WorkflowSaveBody(graph=graph))


def _write_workflows(root: Path) -> WorkflowStoreService:
    registry = ToolRegistryService()
    store = WorkflowStoreService(root / "workspace" / "workflows", registry)

    reference_id = "QA/Reference Workflow"
    _create_workflow(
        store,
        reference_id,
        "QA Reference Workflow",
        GraphState.model_validate(_empty_graph("qa_reference", "QA Reference Workflow")),
        "Deterministic two-step workflow for manual QA.",
    )
    custom_tools = CustomToolService(store.workflow_dir(reference_id), registry)
    tool_sources = {
        "qa_numbers.py": QA_NUMBERS_SOURCE,
        "qa_increment.py": QA_INCREMENT_SOURCE,
        "qa_fail.py": QA_FAIL_SOURCE,
    }
    custom_tools.root.mkdir(parents=True, exist_ok=True)
    for filename, source in tool_sources.items():
        (custom_tools.root / filename).write_text(source, encoding="utf-8")
    registry.register_custom_tools_directory(custom_tools.root)
    store.save_workflow(reference_id, WorkflowSaveBody(graph=_reference_graph()))

    child = _child_graph()
    _create_workflow(
        store,
        "QA/Nested Child",
        "QA Nested Child",
        child,
        "Reusable child with one stable input and output.",
    )
    child_hash = store.get_workflow("QA/Nested Child").artifact_hash
    _create_workflow(
        store,
        "QA/Nested Parent",
        "QA Nested Parent",
        _parent_graph(child, child_hash),
        "Parent containing a saved nested-workflow snapshot.",
    )
    _create_workflow(
        store,
        "QA/Controlled Failure",
        "QA Controlled Failure",
        _failing_graph(),
        "Always fails in QaFail for error, retry, and logging checks.",
    )
    _create_workflow(
        store,
        "QA/Python Authoring",
        "QA Python Authoring",
        GraphState.model_validate(_empty_graph("qa_python_authoring", "QA Python Authoring")),
        "Contains trusted workflow.py for Build from Python source.",
    )
    (store.workflow_dir("QA/Python Authoring") / "workflow.py").write_text(
        PYTHON_WORKFLOW_SOURCE,
        encoding="utf-8",
    )
    _create_workflow(
        store,
        "qa_import_collision",
        "QA Import Collision",
        GraphState.model_validate(_empty_graph("qa_import_collision", "QA Import Collision")),
        "Existing root workflow used to trigger import rename handling.",
    )

    return store


def _write_archives(root: Path, store: WorkflowStoreService) -> None:
    imports = root / "imports"
    imports.mkdir(parents=True)
    for workflow_id, filename in (
        ("qa_import_collision", "qa_import_collision.bioimageflow.zip"),
        ("QA/Nested Parent", "qa-nested-parent.bioimageflow.zip"),
    ):
        _, payload = store.export_workflow_archive(workflow_id)
        (imports / filename).write_bytes(payload)

    (imports / "corrupt-workflow.bioimageflow.zip").write_bytes(
        b"This is intentionally not a ZIP archive.\n"
    )

    workflow_payload = (imports / "qa_import_collision.bioimageflow.zip").read_bytes()
    workflow_member = "workflow/qa_import_collision.bioimageflow.zip"
    run_id = "run_manual_qa_fixture"
    manifest = {
        "schema": RESULTS_BUNDLE_SCHEMA,
        "kind": "workflow-with-results",
        "workflow_id": "qa_import_collision",
        "workflow": {
            "archive": workflow_member,
            "sha256": hashlib.sha256(workflow_payload).hexdigest(),
        },
        "results": {
            "kind": "latest-successful-run",
            "run_id": run_id,
            "path": f"results/runs/{run_id}",
        },
    }
    with zipfile.ZipFile(
        imports / "qa-workflow-and-results.zip",
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            "bioimageflow-results-bundle.json",
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )
        archive.writestr(workflow_member, workflow_payload)
        archive.writestr(
            f"results/runs/{run_id}/README.txt",
            "Deterministic manual QA result-bundle fixture.\n",
        )


def _source_revision() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _checksums(root: Path) -> dict[str, str]:
    excluded_roots = {"evidence"}
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or relative.name == MARKER_NAME:
            continue
        if relative.parts and relative.parts[0] in excluded_roots:
            continue
        result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _remove_generated_bytecode(root: Path) -> None:
    for cache_dir in root.rglob("__pycache__"):
        if cache_dir.is_dir():
            shutil.rmtree(cache_dir)


def _marker_payload(root: Path) -> dict[str, object]:
    return {
        "schema": MARKER_SCHEMA,
        "source_revision": _source_revision(),
        "workspace": "workspace",
        "inputs": ["inputs/qa-gradient.tif", "inputs/qa-table.csv"],
        "imports": [
            "imports/qa_import_collision.bioimageflow.zip",
            "imports/qa-nested-parent.bioimageflow.zip",
            "imports/corrupt-workflow.bioimageflow.zip",
            "imports/qa-workflow-and-results.zip",
        ],
        "workflows": [
            "QA/Reference Workflow",
            "QA/Nested Child",
            "QA/Nested Parent",
            "QA/Controlled Failure",
            "QA/Python Authoring",
            "qa_import_collision",
        ],
        "checksums": _checksums(root),
    }


def _resolved_root(raw_root: str) -> Path:
    root = Path(raw_root).expanduser()
    if not root.is_absolute():
        raise ValueError("--root must be an absolute path")
    return root.resolve(strict=False)


def _validate_safe_root(root: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    home = Path.home().resolve()
    filesystem_root = Path(root.anchor)
    if root in {filesystem_root, home, repo_root}:
        raise ValueError("QA root must not be the filesystem root, home, or repository root")
    if repo_root.is_relative_to(root) or root.is_relative_to(repo_root):
        raise ValueError("QA root must not overlap the repository")
    if home.is_relative_to(root):
        raise ValueError("QA root must not contain the home directory")


def _read_marker(root: Path) -> dict[str, object]:
    marker = root / MARKER_NAME
    if not marker.is_file() or marker.is_symlink():
        raise ValueError(f"Not a generated manual-QA root: {root}")
    payload = json.loads(marker.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != MARKER_SCHEMA:
        raise ValueError(f"Unsupported manual-QA marker in {root}")
    return payload


def verify(root: Path) -> dict[str, object]:
    _validate_safe_root(root)
    payload = _read_marker(root)
    expected = payload.get("checksums")
    if not isinstance(expected, dict):
        raise ValueError("Manual-QA marker has no checksum map")
    actual = _checksums(root)
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        added = sorted(set(actual) - set(expected))
        changed = sorted(
            name for name in set(actual) & set(expected) if actual[name] != expected[name]
        )
        raise ValueError(
            "Manual-QA fixtures were modified "
            f"(missing={missing}, added={added}, changed={changed})"
        )
    return payload


def prepare(root: Path) -> tuple[dict[str, object], bool]:
    _validate_safe_root(root)
    if root.exists() and any(root.iterdir()):
        return verify(root), False
    root.mkdir(parents=True, exist_ok=True)
    try:
        _write_inputs(root)
        _write_local_package(root)
        store = _write_workflows(root)
        _write_archives(root, store)
        _remove_generated_bytecode(root)
        (root / "evidence").mkdir()
        (root / "exports").mkdir()
        payload = _marker_payload(root)
        (root / MARKER_NAME).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        verify(root)
        return payload, True
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


def clean(root: Path) -> None:
    _validate_safe_root(root)
    _read_marker(root)
    shutil.rmtree(root)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare deterministic BioImageFlow manual-QA fixtures."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "verify", "clean"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--root", required=True, help="Absolute QA root path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        root = _resolved_root(args.root)
        if args.command == "prepare":
            payload, created = prepare(root)
            state = "created" if created else "already prepared"
            print(f"Manual QA root {state}: {root}")
            print(f"Source revision: {payload['source_revision']}")
            print(f"Workspace: {root / str(payload['workspace'])}")
            print(f"Inputs: {root / 'inputs'}")
            print(f"Imports: {root / 'imports'}")
            print(f"Export destination: {root / 'exports'}")
            print(f"Evidence: {root / 'evidence'}")
        elif args.command == "verify":
            payload = verify(root)
            print(f"Manual QA fixtures verified: {root}")
            print(f"Source revision: {payload['source_revision']}")
        else:
            clean(root)
            print(f"Manual QA root removed: {root}")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"manual-qa: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
