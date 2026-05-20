"""Agent resource documentation checks."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".agents/skills/bioimageflow-platform/SKILL.md",
    ".agents/skills/bioimageflow-tool-authoring/SKILL.md",
    ".agents/skills/bioimageflow-workflow-editing/SKILL.md",
    ".agents/skills/bioimageflow-execution-debugging/SKILL.md",
    ".agents/resources/rest-cookbook.md",
    ".agents/resources/frontend-state-map.md",
    ".agents/resources/openapi.snapshot.json",
]

AGENTS_REQUIRED_PHRASES = [
    "backend drafts are authoritative for agents and execution snapshots",
    "use draft apis for current workflow state",
    "create tools under workflow-local `tools/`",
    "validate after graph/tool changes",
    "never edit saved workflow json manually unless explicitly requested",
]

SKILL_FILES = [
    ".agents/skills/bioimageflow-platform/SKILL.md",
    ".agents/skills/bioimageflow-tool-authoring/SKILL.md",
    ".agents/skills/bioimageflow-workflow-editing/SKILL.md",
    ".agents/skills/bioimageflow-execution-debugging/SKILL.md",
]

DOC_RESOURCE_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".agents/resources/rest-cookbook.md",
    ".agents/resources/frontend-state-map.md",
    *SKILL_FILES,
]


def test_agent_resource_files_exist() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]

    assert missing == []


def test_agent_root_instructions_contain_required_policies() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8").lower()

    missing = [phrase for phrase in AGENTS_REQUIRED_PHRASES if phrase not in agents]

    assert missing == []


def test_agent_resources_are_parseable_and_actionable() -> None:
    snapshot = json.loads((ROOT / ".agents/resources/openapi.snapshot.json").read_text())
    paths = snapshot.get("paths", {})

    assert snapshot.get("openapi")
    assert "/api/v1/workflows/{name}" in paths
    assert "/api/v1/graph" in paths
    assert "/api/v1/execution/status" in paths

    rest_cookbook = (ROOT / ".agents/resources/rest-cookbook.md").read_text(encoding="utf-8")
    state_map = (ROOT / ".agents/resources/frontend-state-map.md").read_text(encoding="utf-8")

    assert "Draft workflow state" in rest_cookbook
    assert "MCP tool inventory" in rest_cookbook
    assert "Workflow stores" in state_map


def test_agent_skills_have_yaml_frontmatter() -> None:
    missing_frontmatter = []

    for path in SKILL_FILES:
        text = (ROOT / path).read_text(encoding="utf-8")
        if not re.match(r"^---\nname: .+\ndescription: .+\n---\n", text):
            missing_frontmatter.append(path)

    assert missing_frontmatter == []


def test_agent_docs_describe_workspace_and_platform_source_boundaries() -> None:
    docs = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in DOC_RESOURCE_FILES).lower()

    required = [
        "agents must never edit platform source",
        "workflow-root workspace",
        "platform reference is a copy",
        "read-only reference",
    ]
    missing = [phrase for phrase in required if phrase not in docs]

    assert missing == []


def test_agent_entry_points_each_describe_workspace_and_platform_source_boundaries() -> None:
    required = [
        "agents must never edit platform source",
        "workflow-root workspace",
        "platform reference",
        "read-only reference",
    ]
    failures: dict[str, list[str]] = {}

    for path in ["AGENTS.md", "CLAUDE.md", "GEMINI.md"]:
        text = (ROOT / path).read_text(encoding="utf-8").lower()
        missing = [phrase for phrase in required if phrase not in text]
        if missing:
            failures[path] = missing

    assert failures == {}


def test_rest_cookbook_lists_agent_bridge_safety_endpoints() -> None:
    cookbook = (ROOT / ".agents/resources/rest-cookbook.md").read_text(encoding="utf-8")
    required = [
        "GET /api/v1/agent-bridge/context",
        "PUT /api/v1/agent-bridge/workflows/{workflow_name}/tools",
        "POST /api/v1/agent-bridge/package-install-requests",
        "POST /api/v1/openhands/approvals/{approval_id}/approve",
        "POST /api/v1/openhands/undo",
    ]
    missing = [phrase for phrase in required if phrase not in cookbook]

    assert missing == []


def test_agent_docs_include_novice_files_atlas_connected_components_scenario() -> None:
    docs = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in DOC_RESOURCE_FILES).lower()

    required = [
        "files > atlas > connected components",
        "draft id",
        "revision",
        "undo",
        "package install approval",
        "execution permission",
    ]
    missing = [phrase for phrase in required if phrase not in docs]

    assert missing == []
