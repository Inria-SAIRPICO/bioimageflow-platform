---
name: bioimageflow-workflow-editing
description: Use when creating or modifying BioImageFlow workflow graphs, node parameters, connections, sub-workflows, published interfaces, validation, save, or run state.
---

# BioImageFlow Workflow Editing

Use this skill when editing workflow graph structure, node parameters, sub-workflows, published interfaces, or workflow metadata.

## Source Of Truth

- Use draft APIs for current workflow state.
- Treat the frontend's serialized `GraphState` plus backend draft validation as the current editing contract.
- Saved workflow JSON is not an editing surface unless the user explicitly requests manual file edits.
- Agents must never edit platform source while building user workflows.
- Work in the workflow-root workspace. The platform reference is a copy and read-only reference for contracts and examples only.
- Prefer Agent Panel bridge tools for draft reads, proposals, validation, execution, and undo when available.

## Workflow

1. Identify the active `draft_id` and revision. If unavailable, load workflow metadata and graph through `/api/v1/workflows/{name}` and create or initialize a draft.
2. Serialize canvas state with the same shape as `useGraphSync.serializeGraph`.
3. Validate structural changes with `POST /api/v1/workflow-drafts/{draft_id}/validate`.
4. Use `PATCH /api/v1/workflow-drafts/{draft_id}/nodes/{node_id}/parameters` for constant parameter patches.
5. For structural edits, create a proposal with `POST /api/v1/workflow-drafts/{draft_id}/agent-proposals` and let the user apply or reject it.
6. Save through `PUT /api/v1/workflows/{name}` after validation succeeds and the user expects persistence.

## Novice Scenario

For `Files > Atlas > Connected Components`, autonomously propose a Files input or loader, Atlas node, and Connected Components node against the current draft id and revision. Validate the draft, request package install approval before dependency installation, ask for execution permission before running, and leave undo available through the Agent Panel after applying changes.

## Preserve Fields

Preserve node ids, edge ids, positions, parameters, resources, output templates, `enabled`, `collapsed`, sub-workflow fields, and published input/output definitions unless changing them is the point of the task.

## Execution Lock

Workflow and graph editing endpoints can reject changes while execution is running. If a request returns `423`, fetch execution status and wait or ask before retrying.
