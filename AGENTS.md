# BioImageFlow Platform Agent Instructions

These instructions apply to agents working in this repository. Keep changes aligned with the existing backend and frontend contracts, and prefer small documentation or scaffolding updates unless the task explicitly asks for runtime behavior.

## Authority And State

- Backend drafts are authoritative for agents and execution snapshots.
- Use draft APIs for current workflow state; every agent edit must target the active draft id and revision. If this branch does not expose stable draft routes yet, use the current frontend graph serialization and `/api/v1/graph` validation path as the closest check, and do not describe it as a draft API.
- Saved workflow files are persistence artifacts. Never edit saved workflow JSON manually unless explicitly requested.
- The frontend may hold an unsaved, debounced graph while editing. Do not infer current canvas state from the saved workflow document alone.
- Agents must never edit platform source while helping a user build or run a workflow. Keep all agent-created files in the workflow-root workspace, especially workflow-local `tools/`, data staging, and generated outputs.
- The platform reference is a copy for agent inspection only. Treat copied repo reference material as a read-only reference; do not patch it, commit it, or use it as the active workspace for workflow edits.

## Agent Panel Safety

- Prefer bridge tools exposed by the Agent Panel or MCP layer for draft reads, graph proposals, tool creation, package checks, validation, execution, and undo. If a bridge tool is unavailable, use the matching REST route from `.agents/resources/rest-cookbook.md`.
- Graph changes should be proposals against the current draft id and revision so the user can preview, apply, reject, or undo them.
- Ask for package install approval before installing missing Python packages or package-backed tools. Explain which workflow node needs the package and what command or platform action will run.
- Execution is allowed when the user asks to run or verify a workflow, but use the draft graph, pass the workflow context, and keep run/stop/status visible through platform APIs.
- Undo must remain available for agent-applied graph or parameter edits. Do not bypass the draft/proposal flow with direct source edits that cannot be undone from the panel.

## Workflow Editing

- Read workflows through the platform API/store layer before changing them.
- Validate after graph/tool changes with the backend graph validation endpoint or the established frontend validation flow.
- Preserve node ids, edge ids, published input/output fields, sub-workflow fields, positions, parameters, resources, and output templates unless the user asks to change them.
- Treat execution locks as authoritative. Editing endpoints can return `423` while execution is running.

## Tool Authoring

- Create tools under workflow-local `tools/`.
- Prefer the workflow-scoped tools API (`workflow_name`) over writing files directly.
- Use valid Python class names for tool names: no whitespace, no path separators, valid identifier, starts with an uppercase letter.
- After creating, renaming, deleting, or editing a tool, refresh tool metadata and validate affected graphs.

## Novice Scenario: Files > Atlas > Connected Components

When a novice asks to build the common `Files > Atlas > Connected Components` workflow, keep the interaction autonomous and safe:

1. Work in the workflow-root workspace and inspect the copied platform reference only as a read-only reference.
2. Read the active draft id and revision, then propose nodes in order: a file input or Files loader, the Atlas step, and Connected Components.
3. Use bridge tools or REST draft proposal endpoints to add/connect nodes and set parameters; never edit platform source or saved workflow JSON.
4. Validate the draft graph after each meaningful change and preserve node ids, edge ids, published fields, positions, resources, and output templates unless the user asked to change them.
5. If a required package is missing, request package install approval before installation.
6. Ask for or confirm execution permission before running; then run the draft graph through the execution API and report status/results.
7. Leave the user with undo available for applied agent edits.

## Execution Debugging

- Use backend execution status and WebSocket state as the source of execution state.
- Use workflow-scoped storage by passing `workflow_name` where the API supports it.
- For cache clearing, validate the target graph and clear only the requested nodes unless the user asks for a broader reset.

## Agent Resources

- Platform overview skill: `.agents/skills/bioimageflow-platform/SKILL.md`
- Tool authoring skill: `.agents/skills/bioimageflow-tool-authoring/SKILL.md`
- Workflow editing skill: `.agents/skills/bioimageflow-workflow-editing/SKILL.md`
- Execution debugging skill: `.agents/skills/bioimageflow-execution-debugging/SKILL.md`
- REST cookbook: `.agents/resources/rest-cookbook.md`
- Frontend state map: `.agents/resources/frontend-state-map.md`
- OpenAPI snapshot: `.agents/resources/openapi.snapshot.json`
