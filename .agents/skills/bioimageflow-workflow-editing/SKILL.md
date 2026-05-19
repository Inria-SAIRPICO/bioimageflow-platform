---
name: bioimageflow-workflow-editing
description: Use when creating or modifying BioImageFlow workflow graphs, node parameters, connections, sub-workflows, published interfaces, validation, save, or run state.
---

# BioImageFlow Workflow Editing

Use this skill when editing workflow graph structure, node parameters, sub-workflows, published interfaces, or workflow metadata.

## Source Of Truth

- Use draft APIs for current workflow state when they are available and stable.
- Until stable draft routes exist in a branch, treat the frontend's serialized `GraphState` plus backend validation as the current editing contract.
- Saved workflow JSON is not an editing surface unless the user explicitly requests manual file edits.

## Workflow

1. Load workflow metadata and graph through `/api/v1/workflows/{name}` or the active frontend store.
2. Serialize canvas state with the same shape as `useGraphSync.serializeGraph`.
3. Validate structural changes with `PUT /api/v1/graph` and include `workflow_name`.
4. Use `PATCH /api/v1/graph/nodes/{node_id}/parameters` only for constant parameter patches.
5. Save through `PUT /api/v1/workflows/{name}` after validation succeeds and the user expects persistence.

## Preserve Fields

Preserve node ids, edge ids, positions, parameters, resources, output templates, `enabled`, `collapsed`, sub-workflow fields, and published input/output definitions unless changing them is the point of the task.

## Execution Lock

Workflow and graph editing endpoints can reject changes while execution is running. If a request returns `423`, fetch execution status and wait or ask before retrying.
