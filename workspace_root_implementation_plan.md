# Workspace Root and Workflow Tree Implementation Plan

## Goal

Implement one per-user workspace folder named `workspace`, with all workflows
saved below `workspace/workflows/` and optionally organized in folders. The GUI
must expose a workflow tree with folder create/delete/rename controls and
drag-and-drop movement of workflows.

Desktop users can change their own workspace path in Settings. Webapp users cannot; only the admin configures the workspaces root, and each authenticated user receives a workspace at:

```text
<workspaces_root>/<user_id>/workspace/
```

VS Code must always open the user's workspace folder as the editor project. When a user clicks "Open tool script" for a tool, the editor opens the workspace project and focuses the tool file inside it, instead of opening a tool folder as the project.

This plan includes specs, README, docs, implementation, and tests. It assumes parallel worker agents in dedicated git worktrees, each reviewed by a separate review agent before integration, commit, and merge to `main`.

## Current Repo Facts

- Workflow CRUD is centralized in `backend/src/bioimageflow_server/routers/workflows.py`.
- Workflow persistence is in `backend/src/bioimageflow_server/services/workflow_store.py`.
- Current layout is `root_dir/<workflow_name>/workflow.json` plus `root_dir/<workflow_name>/tools/`.
- `WorkflowInfo`, `WorkflowCreate`, and `WorkflowUpdate` expose flat workflow names and per-workflow `storage_path` in `backend/src/bioimageflow_server/models/workflow.py`.
- `create_app()` currently defaults `workflow_root` to `Path("./workflows")`.
- Runtime workflow storage resolution flows through `backend/src/bioimageflow_server/services/workflow_context.py`.
- Custom tools are currently tied to a workflow via `workflow_store.workflow_tools_dir(name)`.
- The Workflows panel is a flat list in `frontend/src/components/panels/WorkflowsPanel.vue`.
- Workflow drag from the panel already exists for sub-workflow creation using `application/bioimageflow-workflow`.
- Tool "Open tool script" is in `frontend/src/components/panels/ToolsPanel.vue`; it currently opens the parent folder of the tool source path.
- Editor backend logic is in `backend/src/bioimageflow_server/services/editor.py` and currently accepts a single `path`.

## Target Layout

Each user has exactly one workspace directory:

```text
workspace/
  workflows/
    segmentation/
      nuclei.workflow.json
      quantification/
        intensity.workflow.json
    demo.workflow.json
  tools/
    my_custom_tool.py
    helpers/
  data/
  outputs/
  .bioimageflow/
    settings.json
    known_packages.txt
```

Rules:

- The user-visible workspace root is named `workspace`.
- Workflow organization happens below `workspace/workflows/`.
- Workflow identifiers become workspace-relative workflow paths, for example `segmentation/nuclei`.
- Workflow JSON filenames use a stable suffix, for example `<slug>.workflow.json`.
- Workflow-local custom tools move to workspace-local custom tools under `workspace/tools/`.
- Runtime outputs default to `workspace/outputs/<workflow_id>/`, with workflow id separators sanitized when needed for filesystem safety.
- Export archives remain portable and must not embed another machine's absolute workspace path.

## API Contract

Add workspace-aware models:

```python
class WorkflowInfo(BaseModel):
    id: str
    name: str
    folder: str
    display_name: str
    path: str
    workspace_path: str
    output_path: str
    last_modified: str
    description: str | None = None

class WorkflowFolderInfo(BaseModel):
    path: str
    display_name: str
    children: list[WorkflowFolderInfo | WorkflowInfo]
```

Keep `name` for compatibility during migration, but move all new frontend state and new endpoints to `id`.

Add endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/workspace` | Return current workspace path, workflows root, tools root, outputs root, deployment mode, and admin-managed flags. |
| `PATCH` | `/api/v1/workspace` | Desktop-only user workspace path change. Webapp non-admin returns 403. |
| `GET` | `/api/v1/workflows/tree` | Return folder/workflow tree rooted at `workspace/workflows`. |
| `POST` | `/api/v1/workflows/folders` | Create folder. Body: `{path}`. |
| `PATCH` | `/api/v1/workflows/folders/{path}` | Rename or move folder. Body: `{new_path}`. |
| `DELETE` | `/api/v1/workflows/folders/{path}` | Delete empty folder. Non-empty folders return 409. |
| `PATCH` | `/api/v1/workflows/{id}` | Update metadata, rename, duplicate, or move workflow. |
| `POST` | `/api/v1/editor/open-tool` | Open workspace project and focus a tool file. Body: `{tool_name, workflow_id?}`. |

Retain existing root-level workflow endpoints as compatibility wrappers until callers are migrated.

## Spec, README, Docs

Update these before implementation PRs land:

- `specs.md`: clarify workspace project layout and workspace-owned custom tools.
- `platform_specs_v1.md`: workflow management API, Workflows panel, Settings panel, editor behavior, dataset/storage path defaults.
- `platform_specs_v2.md`: code editor behavior so the project folder is always the user workspace and tool-open focuses a file.
- `platform_specs_v3.md`: webapp workspace root admin model, per-user workspace derivation, dataset/workflow/output scoping, and container volume table.
- `README.md`, `backend/README.md`, `frontend/README.md`: add storage model and development defaults.
- Existing docs or plan files that mention `./workflows`, `workflow_root/tools`, or per-workflow arbitrary `storage_path` as the main organization model should be updated or marked superseded.

There is no existing lightweight docs consistency test pattern in this repo, so
do not add a new harness in the docs-only slice. Run these exact grep checks
before handing off implementation slices and investigate any match outside this
plan's "Current Repo Facts", "Migration Rules", or explicit compatibility notes:

```bash
rg -n 'workflow_root/tools|workflow-local custom tools|per-workflow .*storage_path|storage_path.*primary organization|./workflows as the user-facing default' specs.md platform_specs_v1.md platform_specs_v2.md platform_specs_v3.md README.md backend/README.md frontend/README.md
rg -n 'Open(ing)? a tool.*folder|tool.*folder as the project|POST /editor/open.*Tools Panel' platform_specs_v1.md platform_specs_v2.md README.md backend/README.md frontend/README.md
rg -n 'output_data_folder|datasets_root.*configurable|workflow directory.*tools/' platform_specs_v1.md platform_specs_v3.md README.md backend/README.md frontend/README.md
```

Deprecated storage language to remove or mark as legacy compatibility:

- `workflow_root/tools`
- `./workflows` as the user-facing default
- per-workflow editable `storage_path` as the primary organization model

## Parallel Worktrees

Use one integration branch plus four worker branches:

```text
feature/workspace-root-specs
feature/workspace-root-backend
feature/workspace-root-frontend
feature/workspace-root-editor
feature/workspace-root-integration
```

Dedicated worktrees:

```text
../bif-workspace-specs
../bif-workspace-backend
../bif-workspace-frontend
../bif-workspace-editor
```

Worker agents must not edit outside their owned areas. Reviewer agents run in read-only mode against each worker branch before integration.

## Agent 1: Specs, README, Docs

Owned files:

- `specs.md`
- `platform_specs_v1.md`
- `platform_specs_v2.md`
- `platform_specs_v3.md`
- `README.md`
- `backend/README.md`
- `frontend/README.md`
- targeted non-ignored docs or plan files

TDD sequence:

1. Add the docs consistency test and confirm it fails.
2. Update specs, README, and docs.
3. Run the consistency test and confirm it passes.

Reviewer focus:

- Desktop and webapp workspace settings do not contradict each other.
- Workspace root and workflows root are not conflated.
- Webapp admin-only root is distinct from desktop user-editable workspace path.
- VS Code behavior says workspace project plus focused tool file.

## Agent 2: Backend Workspace And Workflow Store

Owned files:

- `backend/src/bioimageflow_server/models/workflow.py`
- `backend/src/bioimageflow_server/models/settings.py`
- `backend/src/bioimageflow_server/models/tools.py`
- `backend/src/bioimageflow_server/services/workspace.py` (new)
- `backend/src/bioimageflow_server/services/workflow_store.py`
- `backend/src/bioimageflow_server/services/workflow_context.py`
- `backend/src/bioimageflow_server/routers/workflows.py`
- `backend/src/bioimageflow_server/routers/settings.py`
- `backend/src/bioimageflow_server/app.py`
- backend tests covering those files

TDD sequence:

1. Add failing `WorkspaceService` tests:
   - desktop default resolves to the chosen default workspace path;
   - desktop configured setting overrides workspace path;
   - webapp derives `<workspaces_root>/<user_id>/workspace`;
   - webapp non-admin workspace PATCH is rejected;
   - all returned paths are absolute and normalized.
2. Add failing workflow store tests:
   - list returns a nested tree;
   - create workflow in `segmentation/nuclei`;
   - reject path traversal and absolute workflow ids;
   - create/delete/rename folders;
   - move workflow between folders;
   - rename folder updates child workflow ids and paths;
   - delete non-empty folder returns conflict;
   - legacy `root/<name>/workflow.json` migrates to `workspace/workflows/<name>.workflow.json`;
   - output paths resolve under `workspace/outputs/<workflow_id>/`.
3. Implement path validation:
   - slash-separated safe segments only;
   - no `..`, empty segment, absolute path, or Windows separator escape;
   - derive leaf slug and folder from id.
4. Implement workspace-aware store:
   - `workflows_root = workspace / "workflows"`;
   - `tools_root = workspace / "tools"`;
   - `outputs_root = workspace / "outputs"`;
   - workflow JSON path `<workflows_root>/<folder>/<name>.workflow.json`;
   - atomic writes remain in the target folder.
5. Update routers and compatibility wrappers.
6. Update graph, execution, and node-result storage resolution to use workflow id and workspace output path.

Reviewer focus:

- Every filesystem entry is contained by workspace root using `resolve()` and prefix checks.
- Folder rename/move is atomic where possible.
- No destructive delete of user-provided external paths remains.
- Backward compatibility tests still pass.

## Agent 3: Frontend Workflow Tree And Settings

Owned files:

- `frontend/src/stores/workflow.ts`
- `frontend/src/stores/settings.ts`
- `frontend/src/components/panels/WorkflowsPanel.vue`
- `frontend/src/components/workflow/*.vue`
- `frontend/src/components/panels/SettingsPanel.vue`
- `frontend/src/components/panels/sections/StorageSection.vue`
- related frontend tests

TDD sequence:

1. Add failing store tests:
   - fetch tree endpoint populates folders and workflows;
   - create/rename/delete folder calls correct APIs;
   - move workflow updates id/current workflow safely;
   - old flat list computed view remains available for menus/search if needed.
2. Add failing component tests:
   - tree renders nested folders and root workflows;
   - buttons create, rename, delete selected folder;
   - delete disabled for non-empty folders or surfaces conflict;
   - workflow drag uses workflow id;
   - folder drop calls move workflow;
   - search filters tree while preserving ancestors.
3. Replace flat Workflows panel with a tree.
4. Keep drag-to-canvas behavior for sub-workflow creation separate from drag-to-folder movement.
5. Settings UI:
   - Desktop: editable `workspace_path` with folder picker.
   - Webapp non-admin: read-only workspace path.
   - Webapp admin-only workspaces root is not exposed in ordinary user settings.
6. Update all API identity callers from `workflow.name` to `workflow.id`.

Reviewer focus:

- Tree interactions are predictable.
- Drag-to-canvas and drag-to-folder are not confused.
- Existing sub-workflow creation from workflow drag still works.
- Settings optimistic updates do not leave the frontend pointing to an old workspace.

## Agent 4: Editor And Custom Tools Workspace Integration

Owned files:

- `backend/src/bioimageflow_server/services/editor.py`
- `backend/src/bioimageflow_server/models/editor.py`
- `backend/src/bioimageflow_server/routers/editor.py`
- `backend/src/bioimageflow_server/routers/tools.py`
- `backend/src/bioimageflow_server/services/custom_tools.py`
- `frontend/src/api/editor.ts`
- `frontend/src/components/panels/ToolsPanel.vue`
- `frontend/src/components/panels/CodeEditorPanel.vue`
- related editor/tool tests

TDD sequence:

1. Add failing backend editor tests:
   - tool-open returns workspace folder as project plus tool file as focus path;
   - embedded code-server opens `workspace` as folder and then calls opener for the tool file;
   - external editor command supports workspace and file placeholders;
   - package tool source can be focused while project remains workspace;
   - webapp restrictions still apply.
2. Extend editor model:
   - keep generic `EditorOpenRequest(path)`;
   - add `EditorOpenToolRequest(tool_name, workflow_id?)`;
   - response includes `project_path` and optional `focus_path`.
3. Update embedded manager:
   - first ensure workspace folder is loaded as the code-server project;
   - then use opener extension to focus file;
   - avoid reloading iframe when already on the same workspace.
4. Move custom tools root from per-workflow `tools/` to `workspace/tools/`.
5. Update frontend ToolsPanel to stop using `parentPath(data.path)` for tool script opening.

Reviewer focus:

- No path outside workspace is accepted as a project root in webapp mode.
- Package source focus behavior does not expose arbitrary server paths in hosted deployments.
- Custom tool migration preserves existing tools.

## Integration Order

Merge worker branches into `feature/workspace-root-integration` in this order:

1. specs/docs
2. backend workspace store
3. editor/custom tools
4. frontend workflow tree/settings

Resolve conflicts only in the integration worktree. If a worker branch is rebased after review, rerun its reviewer agent.

## Test Matrix

Backend:

```bash
uv run pytest backend/tests/test_services/test_workflow_store.py
uv run pytest backend/tests/test_routers/test_workflows.py
uv run pytest backend/tests/test_routers/test_settings.py
uv run pytest backend/tests/test_routers/test_editor.py
uv run pytest backend/tests/test_routers/test_tools.py
uv run pytest backend/tests/test_routers/test_graph.py
uv run pytest backend/tests/test_routers/test_execution_router.py
uv run pytest backend/tests/test_routers/test_nodes.py
uv run ruff check backend/src backend/tests
```

Frontend:

```bash
cd frontend
bun test src/components/panels/__tests__/WorkflowsPanel.test.ts
bun test src/stores/__tests__/workflow.test.ts
bun test tests/unit/components/SettingsPanel.test.ts
bun test src/components/panels/__tests__/ToolsPanel.test.ts
bun test src/api/__tests__/editor.test.ts
bun test src/components/canvas/__tests__/CanvasView.test.ts
bun test
bun run lint
```

E2E:

```bash
cd frontend
bun run test:e2e -- workflow-crud.spec.ts workflow-publishing.spec.ts settings.spec.ts
```

Manual smoke:

1. Desktop: change workspace path in Settings, create folders, create workflows inside folders, restart, verify tree persists.
2. Desktop: drag workflow from one folder to another and save/load it.
3. Desktop: drag workflow from tree onto canvas and verify SubWorkflowNode creation still works.
4. Desktop: create custom tool and click "Open tool script"; code-server or external VS Code opens workspace as project and focuses the script.
5. Webapp: ordinary user sees read-only workspace path and cannot PATCH it.
6. Webapp: user A cannot list/open/move/delete user B workflows.

## Migration Rules

- Existing `./workflows/<name>/workflow.json` imports as root-level `<name>.workflow.json` under the new workspace.
- Existing `./workflows/<name>/tools/*.py` migrates to `workspace/tools/` if no collision exists.
- On custom tool filename collision, suffix the migrated filename and update registry metadata.
- Existing per-workflow `metadata.storage_path` is preserved for compatibility but no longer exposed as the primary organization control.
- New workflows default to workspace outputs.

## Commit And Merge Checklist

Each worker branch:

- Failing tests committed before implementation or included in PR history.
- Implementation committed after tests pass locally.
- Reviewer agent report attached to branch/PR notes.
- No unrelated formatting churn.

Integration branch:

- Full backend, frontend, and E2E targeted suites pass.
- Specs, README, docs, generated frontend API types, and tests are updated.
- OpenAPI snapshot/types regenerated if endpoint schemas changed.
- Manual smoke checklist completed.
- Commit message:

```text
Implement per-user workspace root and workflow tree
```

Merge:

1. Fast-forward or squash merge `feature/workspace-root-integration` into `main`.
2. Run final smoke on `main`.
3. Push `main`.
4. Remove temporary worktrees and delete worker branches after successful CI.
