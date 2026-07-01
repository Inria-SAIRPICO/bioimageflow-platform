from __future__ import annotations

from pathlib import Path

from bioimageflow_server.services import agent_workspace_context as context


FORBIDDEN_AGENT_CONTEXT_PHRASES = [
    "Operation REST second",
    "Raw full-DAG",
    "REST fallback",
    "MCP is a protocol",
    "curl",
    "human_diagnostic_rest",
    "workflow-draft-operations",
    "workflow-drafts",
    "execution/run",
]


def test_ensure_agent_workspace_context_writes_root_instructions_and_readonly_note(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".git").mkdir()
    (source / "docs" / "agents").mkdir(parents=True)
    (source / "docs" / "agents" / "README.md").write_text("agent docs")
    workspace = tmp_path / "workspace"
    (workspace / ".bioimageflow").mkdir(parents=True)
    (workspace / ".bioimageflow" / "AGENTS.md").write_text(
        "# BioImageFlow Agent Instructions for Codex\nold"
    )

    def fake_run(args, **kwargs):  # noqa: ANN001, ANN202
        target = Path(args[-1])
        target.mkdir(parents=True)
        (target / "README.md").write_text("source clone")
        (target / ".bioimageflow").symlink_to(tmp_path / "global-meta")

    monkeypatch.setattr(context.subprocess, "run", fake_run)

    context.ensure_agent_workspace_context(workspace, source_root=source)

    instructions = (workspace / "AGENTS.md").read_text()
    normalized_instructions = " ".join(instructions.split())
    assert "Use BioImageFlow MCP tools for workflow inspection" in normalized_instructions
    assert "MCP Tool Reference" in instructions
    assert "get_bioimageflow_capabilities" in instructions
    assert "get_workflow_draft" in instructions
    assert "describe_workflow" in instructions
    assert "describe_bioimageflow_tool" in instructions
    assert "apply_workflow_operations" in instructions
    assert "get_execution_status" in instructions
    assert ".bioimageflow/platform-source/" in instructions
    assert "read-only" in instructions
    assert "BIOIMAGEFLOW_AGENT_STATE" in instructions
    assert "bioimageflow-agent" not in instructions
    assert "batch" in normalized_instructions
    assert "Workflow-local tool authoring" in instructions
    assert "tool_reload" in instructions
    assert "/Users/" not in instructions
    for phrase in FORBIDDEN_AGENT_CONTEXT_PHRASES:
        assert phrase not in instructions
    assert not (workspace / ".bioimageflow" / "AGENTS.md").exists()
    source_clone = workspace / ".bioimageflow" / "platform-source"
    assert (source_clone / "README.md").exists()
    assert not (source_clone / ".bioimageflow").exists()
    assert "Do not edit files here" in (source_clone / "READ_ONLY_AGENT_NOTE.md").read_text()
    assert (source_clone / "docs" / "agents" / "README.md").read_text() == "agent docs"

    note = (workspace / ".bioimageflow" / "platform-source.README.md").read_text()
    assert "read-only reference" in note
    assert "Editing files here will not change" in note


def test_agent_workspace_instructions_are_loaded_from_markdown_template() -> None:
    source = Path(context.__file__).read_text(encoding="utf-8")
    template = (
        Path(context.__file__).parents[1] / "data" / context.AGENT_INSTRUCTIONS_TEMPLATE
    ).read_text(encoding="utf-8")

    assert "{{SOURCE_STATUS}}" in template
    assert "## MCP Tool Reference" in template
    assert "## MCP Tool Reference" not in source
    assert "{{SOURCE_STATUS}}" not in context.agent_workspace_instructions()


def test_source_reference_failure_is_non_fatal(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".git").mkdir()
    meta = tmp_path / ".bioimageflow"
    meta.mkdir()

    def fail_run(args, **kwargs):  # noqa: ANN001, ANN202
        raise RuntimeError("clone failed")

    monkeypatch.setattr(context.subprocess, "run", fail_run)

    target = context.ensure_platform_source_reference(meta, source_root=source)

    assert target == meta / "platform-source"
    assert not target.exists()
    note = (meta / "platform-source.README.md").read_text()
    assert "Status: `unavailable`" in note


def test_user_hidden_agent_doc_is_preserved(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".git").mkdir()
    workspace = tmp_path / "workspace"
    hidden = workspace / ".bioimageflow" / "AGENTS.md"
    hidden.parent.mkdir(parents=True)
    hidden.write_text("# Custom User Instructions\nkeep me")

    def fake_run(args, **kwargs):  # noqa: ANN001, ANN202
        Path(args[-1]).mkdir(parents=True)

    monkeypatch.setattr(context.subprocess, "run", fake_run)

    context.ensure_agent_workspace_context(workspace, source_root=source)

    assert hidden.read_text() == "# Custom User Instructions\nkeep me"


def test_agent_docs_include_mcp_client_setup() -> None:
    docs_root = Path(__file__).parents[3] / "docs" / "agents"
    readme = (docs_root / "README.md").read_text(encoding="utf-8")
    assert "bioimageflow-mcp" in readme
    assert "BIOIMAGEFLOW_AGENT_STATE" in readme
    for name in ("README.md", "api-reference.md", "workflow-editing.md"):
        content = (docs_root / name).read_text(encoding="utf-8")
        assert "get_bioimageflow_capabilities" in content
        assert "get_workflow_draft" in content
        assert "apply_workflow_operations" in content
        if name != "workflow-editing.md":
            assert "get_execution_status" in content
        for phrase in FORBIDDEN_AGENT_CONTEXT_PHRASES:
            assert phrase not in content


def test_agent_docs_include_workflow_local_tool_authoring() -> None:
    docs_root = Path(__file__).parents[3] / "docs" / "agents"
    workflow_editing = (docs_root / "workflow-editing.md").read_text(encoding="utf-8")
    readme = (docs_root / "README.md").read_text(encoding="utf-8")

    for content in (workflow_editing, readme):
        assert "workflow-local tool" in content
        assert "describe_bioimageflow_tool" in content
        assert ".bioimageflow/platform-source/" in content
