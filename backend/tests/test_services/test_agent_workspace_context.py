from __future__ import annotations

from pathlib import Path

from bioimageflow_server.services import agent_workspace_context as context


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
    assert "local app for designing and running bioimage analysis workflows" in normalized_instructions
    assert (
        "Your job is to edit the live workflow draft through the local HTTP API"
        in normalized_instructions
    )
    assert "First-Run Checklist" in instructions
    assert ".bioimageflow/platform-source/" in instructions
    assert "read-only" in instructions
    assert "API-first through `api_base_url`" in normalized_instructions
    assert "Do not guess or hardcode ports such as 8008" in instructions
    assert "Sandboxed agents may be blocked from reaching localhost" in instructions
    assert "request permission to run the same curl command outside the sandbox" in instructions
    assert "bioimageflow-agent" not in instructions
    assert "full-graph replacement, not patch" in instructions
    assert "Enable or disable node" in instructions
    assert "Execute selected nodes" in instructions
    assert "/Users/" not in instructions
    assert not (workspace / ".bioimageflow" / "AGENTS.md").exists()
    source_clone = workspace / ".bioimageflow" / "platform-source"
    assert (source_clone / "README.md").exists()
    assert not (source_clone / ".bioimageflow").exists()
    assert "Do not edit files here" in (source_clone / "READ_ONLY_AGENT_NOTE.md").read_text()
    assert (source_clone / "docs" / "agents" / "README.md").read_text() == "agent docs"

    note = (workspace / ".bioimageflow" / "platform-source.README.md").read_text()
    assert "read-only reference" in note
    assert "Editing files here will not change" in note


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
