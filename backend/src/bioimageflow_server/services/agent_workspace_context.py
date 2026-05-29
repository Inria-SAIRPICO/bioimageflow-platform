"""Agent-facing workspace context files and source reference setup."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


PLATFORM_SOURCE_DIR = "platform-source"


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

This checkout is a reference copy for agents. Do not edit files here to change
BioImageFlow behavior or workflows. The running app uses the installed source,
not this clone. Make workflow changes through the local API described in the
workspace root `AGENTS.md`.
""",
        encoding="utf-8",
    )


def _write_read_only_note(meta_dir: Path, source_path: Path, *, cloned: bool) -> None:
    status = "available" if cloned else "unavailable"
    (meta_dir / "platform-source.README.md").write_text(
        f"""# BioImageFlow Platform Source Reference

Status: `{status}`

Expected location: `{PLATFORM_SOURCE_DIR}/`

This source tree is for agent context only. It is a read-only reference copy of
BioImageFlow platform docs and implementation. Editing files here will not change
the running application and may confuse future agents.

Use it to inspect docs, API models, routers, frontend stores, and implementation
patterns. Make workflow changes through the local BioImageFlow API described in
the workspace root `AGENTS.md`.
""",
        encoding="utf-8",
    )


def agent_workspace_instructions(*, source_path: Path | None = None) -> str:
    source_status = (
        "read-only platform docs and implementation reference"
        if source_path is not None
        else "optional read-only platform docs and implementation reference"
    )
    return f"""# BioImageFlow Agent Instructions

BioImageFlow is a local app for designing and running bioimage analysis
workflows. A workflow is a graph: nodes run tools, and edges connect outputs
from one node to inputs on another.

Your job is to edit the live workflow draft through the local HTTP API, validate
the graph, and execute it when asked. Workflow editing is API-first through
`api_base_url` from `.bioimageflow/agent-state.json`.

## What To Read

- `.bioimageflow/agent-state.json`: runtime pointers only. Read
  `api_base_url` and `active_workflow_id` from here; do not treat this file as
  workflow data.
- Live draft from `GET /workflow-drafts/$WF`: editable source of truth.
- `workflow.json`: saved/exported artifact. Do not edit it to change the open
  workflow.
- `.bioimageflow/platform-source/`: {source_status}.
  Treat every file under it as read-only; editing it will not change the
  running app or workflow.
- `current_draft_revision` and `active_draft_path`, if present in state: useful
  diagnostics only. Fresh-read the draft before every write.

## First-Run Checklist

1. Set `API` from `api_base_url` and `WF` from `active_workflow_id`.
2. Health check: `curl -sS "$API/health"`.
3. Read the live draft: `GET $API/workflow-drafts/$WF`.
4. Save the returned `draft_revision` and full `graph`.
5. Inspect tools before creating or connecting nodes: `GET $API/tools`.
6. Edit the graph object: mutate `nodes`, `edges`, `published_inputs`, and
   `published_outputs` deliberately.
7. Validate without saving: `PUT $API/graph` with
   `{{"graph": graph, "workflow_name": WF}}`.
8. Write the draft with `PUT $API/workflow-drafts/$WF`:
   `{{"graph": graph, "expected_revision": draft_revision, "updated_by": "agent", "validate": true}}`
9. Expect the open canvas to update automatically when the user has no local
   conflict. If the user has local edits, BioImageFlow will ask them which
   version to keep.
10. Execute the latest draft graph: `POST $API/execution/run` with
   `{{"graph": graph, "workflow_name": WF}}`.
11. Check or stop execution: `GET $API/execution/status`,
    `POST $API/execution/stop`.

## API URL And Sandbox

The backend port is dynamic. Always read `api_base_url` from
`.bioimageflow/agent-state.json`. Do not guess or hardcode ports such as 8008,
and do not switch to another port unless the state file changes.

Recommended setup:

```sh
STATE=.bioimageflow/agent-state.json
API=$(jq -r .api_base_url "$STATE")
WF=$(jq -r .active_workflow_id "$STATE")
curl -sS "$API/health"
```

Sandboxed agents may be blocked from reaching localhost or 127.0.0.1 even when
BioImageFlow is running. If the health check fails with a permission, sandbox,
or connection error, request permission to run the same curl command outside the sandbox.
Do not edit `workflow.json` or the read-only platform source as a fallback.

## Draft Write Rule

`PUT /workflow-drafts/{{workflow_id}}` is full-graph replacement, not patch.
Always send the complete graph and preserve unchanged `nodes`, `edges`,
`published_inputs`, and `published_outputs`.

On `409 draft_revision_conflict`: re-read the draft, reapply your intended
change to the new graph, then retry with the new `draft_revision`.

On `423 workflow_locked`: execution is running. Check status, stop or wait, then
write after the lock clears.

## Frontend Sync

After a successful draft write, connected frontends receive a draft-change
event. A clean canvas usually updates automatically. If the user has local
canvas edits, the UI offers three choices: apply agent changes, keep the canvas,
or save the agent version as a copy. Do not try to resolve that conflict by
editing `workflow.json`.

Save, run, and export are blocked while that conflict is unresolved. Export
prompts the user that the workflow will be saved first, then exports the saved
workflow.

## Graph Edits

- Create node: add an entry to `graph.nodes` with `id`, `name`, `tool_name`,
  `position`, and `parameters`. Use `GET /tools` for valid tool names and
  parameter names.
- Edit node: change `name`, `parameters`, `enabled`, `resources`, or
  `output_templates`.
- Connect nodes: add an edge to `graph.edges`. Use `column_ref` for named
  output-to-input connections; use `positional` for ordered upstream inputs.
- Replace a connection: remove the old edge for that target input, then add the
  new edge.
- Enable or disable node: set `enabled` to `true` or `false`, then save the
  full draft. Disabled nodes are skipped in future executions; this does not
  stop an already running execution.
- Execute selected nodes: send the full graph to `POST /execution/run` with
  `nodes` set to the node ids to run, for example
  `{{"graph": graph, "workflow_name": WF, "nodes": ["node_id"]}}`.
- Stop current execution: `POST $API/execution/stop`, then poll
  `GET $API/execution/status` until it is idle.
- Delete node: remove the node and every edge where it is source or target.

## More Detail

- Expanded docs may be available in `.bioimageflow/platform-source/docs/agents/`.
"""
