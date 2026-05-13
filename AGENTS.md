# BioImageFlow Platform Agent Instructions

These instructions apply to agents working in this repository. Keep changes aligned with the existing backend and frontend contracts, and prefer small documentation or scaffolding updates unless the task explicitly asks for runtime behavior.

## Authority And State

- Backend drafts are authoritative for agents and execution snapshots.
- Use draft APIs for current workflow state; if this branch does not expose stable draft routes yet, use the current frontend graph serialization and `/api/v1/graph` validation path as the closest check, and do not describe it as a draft API.
- Saved workflow files are persistence artifacts. Never edit saved workflow JSON manually unless explicitly requested.
- The frontend may hold an unsaved, debounced graph while editing. Do not infer current canvas state from the saved workflow document alone.

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
