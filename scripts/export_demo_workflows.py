#!/usr/bin/env python3
"""Generate deterministic platform demo templates from BioImageFlow examples."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))
for package_root in sorted((ROOT / "bioimageflow" / "packages").iterdir()):
    if package_root.is_dir() and str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))

from bioimageflow import Workflow  # noqa: E402
from bioimageflow_server.models.workflow import (  # noqa: E402
    BundledTemplateProvenance,
    WorkflowDocument,
    WorkspaceWorkflowMetadata,
)
from bioimageflow_server.services.graph_translator import (  # noqa: E402
    lib_dict_to_graph_state,
)
from bioimageflow_server.services.workflow_artifacts import artifact_hash  # noqa: E402


BUNDLE_VERSION = 1
OUTPUT_DIR = (
    ROOT
    / "backend"
    / "src"
    / "bioimageflow_server"
    / "data"
    / "demo_workflows"
    / f"v{BUNDLE_VERSION}"
)


@dataclass(frozen=True)
class DemoDefinition:
    template_id: str
    workflow_id: str
    directory: str
    source: str
    description: str


DEFINITIONS = (
    DemoDefinition(
        template_id="fish-analysis",
        workflow_id="Demo/Fish Analysis",
        directory="fish-analysis",
        source="example_workflows/fish_analysis/workflow.py",
        description="Analyze FISH marker spots per segmented nucleus.",
    ),
    DemoDefinition(
        template_id="parameters-space-exploration",
        workflow_id="Demo/Parameters Space Exploration",
        directory="parameters-space-exploration",
        source="example_workflows/parameter_space_exploration/workflow.py",
        description="Explore a grid of ATLAS spot-detection parameters.",
    ),
)

PACKAGE_REQUIREMENTS = {
    "bioimageflow_common_tools": ("bioimageflow_common_tools", "bioimageflow-common-tools"),
    "bioimageflow_segmentation_tools": (
        "bioimageflow_segmentation_tools",
        "bioimageflow-segmentation-tools",
    ),
    "bioimageflow_spot_tools": ("bioimageflow_spot_tools", "bioimageflow-spot-tools"),
}


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _source_filename(record: dict[str, Any], used: set[str]) -> str:
    candidate = Path(str(record.get("filename") or f"{record['id']}.py")).name
    if not candidate.endswith(".py"):
        candidate = f"{candidate}.py"
    if candidate not in used:
        used.add(candidate)
        return candidate
    candidate = f"{Path(candidate).stem}_{record['id']}.py"
    used.add(candidate)
    return candidate


def _materialize_custom_tools(
    graph_data: dict[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, bytes]:
    filenames: dict[str, str] = {}
    files: dict[str, bytes] = {}
    used: set[str] = set()
    for record in records:
        if "files" in record:
            raise ValueError("Bundled demo exporter does not support directory source bundles")
        source_id = str(record["id"])
        filename = _source_filename(record, used)
        filenames[source_id] = filename
        files[filename] = str(record["source"]).encode("utf-8")

    def visit(definition: dict[str, Any]) -> None:
        for node in definition.get("nodes", []):
            if node.get("type") == "workflow":
                visit(node["workflow"])
                continue
            source_id = node.get("source_module")
            if source_id not in filenames:
                continue
            node["source_module"] = None
            node["tool_module"] = f"tools.{Path(filenames[source_id]).stem}"

    visit(graph_data)
    return files


def _annotate_package_requirements(graph_data: dict[str, Any]) -> None:
    versions = {
        module: str(
            tomllib.loads(
                (
                    ROOT
                    / "bioimageflow"
                    / "packages"
                    / directory
                    / "pyproject.toml"
                ).read_text(encoding="utf-8")
            )["project"]["version"]
        )
        for module, (_, directory) in PACKAGE_REQUIREMENTS.items()
    }

    def visit(definition: dict[str, Any]) -> None:
        for node in definition.get("nodes", []):
            if node.get("type") == "workflow":
                visit(node["workflow"])
                continue
            if node.get("source_module"):
                continue
            module_name = str(node.get("tool_module") or "")
            package_module = module_name.split(".", 1)[0]
            requirement = PACKAGE_REQUIREMENTS.get(package_module)
            if requirement is None:
                continue
            node["tool_package"] = requirement[0]
            node["tool_package_version"] = versions[package_module]

    visit(graph_data)


def _render_definition(definition: DemoDefinition) -> dict[str, bytes]:
    source_path = ROOT / "bioimageflow" / definition.source
    workflow = Workflow.from_python(source_path)
    exported = workflow.to_dict(include_custom_tools=True)
    if set(exported) != {"archive_version", "workflow", "custom_sources"}:
        raise ValueError(f"Expected a portable workflow envelope from {source_path}")

    library_graph = json.loads(json.dumps(exported["workflow"]))
    tool_files = _materialize_custom_tools(library_graph, exported["custom_sources"])
    _annotate_package_requirements(library_graph)
    graph = lib_dict_to_graph_state(library_graph)
    graph = graph.model_copy(
        update={
            "config": graph.config.model_copy(update={"storage_path": "./bif_data"}),
        }
    )
    document = WorkflowDocument(
        graph=graph,
        metadata=WorkspaceWorkflowMetadata(
            description=definition.description,
            storage_path="./bif_data",
            bundled_template=BundledTemplateProvenance(
                id=definition.template_id,
                version=BUNDLE_VERSION,
            ),
        ),
        owned_source_ids=[],
        artifact_hash=artifact_hash(graph, []),
    )
    rendered = {
        "workflow.json": _json_bytes(
            document.model_dump(mode="json", by_alias=True, exclude_none=True)
        )
    }
    rendered.update({f"tools/{name}": content for name, content in tool_files.items()})
    return rendered


def _render_bundle() -> dict[str, bytes]:
    manifest = {
        "bundle_version": BUNDLE_VERSION,
        "workflows": [
            {
                "id": definition.template_id,
                "version": BUNDLE_VERSION,
                "workflow_id": definition.workflow_id,
                "directory": definition.directory,
                "source": definition.source,
            }
            for definition in DEFINITIONS
        ],
    }
    rendered = {"manifest.json": _json_bytes(manifest)}
    for definition in DEFINITIONS:
        for relative, content in _render_definition(definition).items():
            rendered[f"{definition.directory}/{relative}"] = content
    return rendered


def _existing_files() -> dict[str, bytes]:
    if not OUTPUT_DIR.exists():
        return {}
    return {
        path.relative_to(OUTPUT_DIR).as_posix(): path.read_bytes()
        for path in sorted(OUTPUT_DIR.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when committed templates differ from the Python examples.",
    )
    args = parser.parse_args()
    rendered = _render_bundle()
    existing = _existing_files()
    if args.check:
        if existing == rendered:
            return 0
        changed = sorted(set(existing) | set(rendered))
        print("Bundled demo templates are out of date:", file=sys.stderr)
        for path in changed:
            if existing.get(path) != rendered.get(path):
                print(f"  {path}", file=sys.stderr)
        return 1

    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=OUTPUT_DIR.parent) as temporary:
        staging = Path(temporary) / OUTPUT_DIR.name
        for relative, content in rendered.items():
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)
        staging.rename(OUTPUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
