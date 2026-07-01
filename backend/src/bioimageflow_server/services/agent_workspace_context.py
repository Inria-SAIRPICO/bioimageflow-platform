"""Agent-facing workspace context files and source reference setup."""

from __future__ import annotations

import shutil
import subprocess
from importlib import resources
from pathlib import Path


PLATFORM_SOURCE_DIR = "platform-source"
AGENT_INSTRUCTIONS_TEMPLATE = "agent_workspace_instructions.md"


def source_checkout_root() -> Path | None:
    """Return the BioImageFlow source checkout root when running from git."""
    root = Path(__file__).resolve().parents[4]
    return root if (root / ".git").exists() else None


def ensure_agent_workspace_context(
    workspace_path: Path,
    *,
    source_root: Path | None = None,
) -> None:
    """Create root agent instructions and a read-only source reference.

    The source reference is for agent context only. The running platform never
    imports from it, and editing it cannot affect the application.
    """
    workspace_path.mkdir(parents=True, exist_ok=True)
    meta_dir = workspace_path / ".bioimageflow"
    meta_dir.mkdir(parents=True, exist_ok=True)
    _remove_generated_hidden_instructions(meta_dir)
    source_path = ensure_platform_source_reference(
        meta_dir,
        source_root=source_root,
    )
    (workspace_path / "AGENTS.md").write_text(
        agent_workspace_instructions(
            source_path=source_path if source_path.exists() else None,
        ),
        encoding="utf-8",
    )


def ensure_platform_source_reference(
    meta_dir: Path,
    *,
    source_root: Path | None = None,
) -> Path:
    """Best-effort clone of the platform source into ``.bioimageflow``."""
    target = meta_dir / PLATFORM_SOURCE_DIR
    if target.exists():
        _sanitize_source_reference(target)
        _sync_agent_docs(target, source_root=source_root)
        _write_read_only_note(meta_dir, target, cloned=True)
        return target

    source = source_root if source_root is not None else source_checkout_root()
    if source is not None and (source / ".git").exists():
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", "--no-tags", str(source), str(target)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=60,
            )
        except Exception:  # noqa: BLE001 - source reference must never block startup
            pass

    if target.exists():
        _sanitize_source_reference(target)
        _sync_agent_docs(target, source_root=source)
    _write_read_only_note(meta_dir, target, cloned=target.exists())
    return target


def _remove_generated_hidden_instructions(meta_dir: Path) -> None:
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = meta_dir / name
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if content.startswith("# BioImageFlow Agent Instructions"):
            path.unlink()


def _sync_agent_docs(source_path: Path, *, source_root: Path | None) -> None:
    if source_root is None:
        return
    docs_source = source_root / "docs" / "agents"
    if not docs_source.is_dir():
        return
    docs_target = source_path / "docs" / "agents"
    docs_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(docs_source, docs_target, dirs_exist_ok=True)


def _sanitize_source_reference(source_path: Path) -> None:
    nested_meta = source_path / ".bioimageflow"
    if nested_meta.is_symlink() or nested_meta.is_file():
        nested_meta.unlink(missing_ok=True)
    elif nested_meta.is_dir():
        shutil.rmtree(nested_meta)
    (source_path / "READ_ONLY_AGENT_NOTE.md").write_text(
        """# Read-Only Agent Context

This checkout is a reference copy for agents. Do not edit files here to change BioImageFlow behavior or workflows.
The running app uses the installed source, not this clone.
Make workflow changes through the BioImageFlow MCP tools described in the workspace root `AGENTS.md`.
""",
        encoding="utf-8",
    )


def _write_read_only_note(meta_dir: Path, source_path: Path, *, cloned: bool) -> None:
    status = "available" if cloned else "unavailable"
    (meta_dir / "platform-source.README.md").write_text(
        f"""# BioImageFlow Platform Source Reference

Status: `{status}`

Expected location: `{PLATFORM_SOURCE_DIR}/`

This source tree is for agent context only. It is a read-only reference copy of BioImageFlow platform docs and implementation. Editing files here will not change the running application and may confuse future agents.

Use it to inspect docs, models, frontend stores, and implementation patterns. Make workflow changes through the BioImageFlow MCP tools described in the workspace root `AGENTS.md`.
""",
        encoding="utf-8",
    )


def agent_workspace_instructions(*, source_path: Path | None = None) -> str:
    source_status = (
        "read-only platform docs and implementation reference"
        if source_path is not None
        else "optional read-only platform docs and implementation reference"
    )
    template = (
        resources.files("bioimageflow_server.data")
        .joinpath(AGENT_INSTRUCTIONS_TEMPLATE)
        .read_text(encoding="utf-8")
    )
    return template.replace("{{SOURCE_STATUS}}", source_status)
