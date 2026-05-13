"""Agent resource documentation checks."""

from __future__ import annotations

import json
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
