---
name: bioimageflow-platform
description: Use when working on BioImageFlow platform architecture, agent-facing workflow editing, REST APIs, frontend/backend state contracts, or repository-wide behavior.
---

# BioImageFlow Platform

Use this skill when an agent needs the overall platform map before editing BioImageFlow workflows, tools, execution state, or agent-facing docs.

## Core Rules

- Backend drafts are authoritative for agents and execution snapshots.
- Use draft APIs for current workflow state when stable draft APIs are available in the branch.
- Never edit saved workflow JSON manually unless explicitly requested.
- Validate after graph/tool changes.
- Create custom tools through workflow-local `tools/` paths, preferably via the workflow-scoped tools API.

## Read First

- `AGENTS.md` for repository-wide agent constraints.
- `.agents/resources/rest-cookbook.md` for REST endpoints and scaffolded MCP inventory.
- `.agents/resources/frontend-state-map.md` for frontend stores and graph serialization.
- `.agents/resources/openapi.snapshot.json` for a checked-in API snapshot.

## Platform Shape

- Backend API prefix: `/api/v1`.
- Workflow CRUD is under `/api/v1/workflows`.
- Graph validation is under `PUT /api/v1/graph`.
- Execution control and status are under `/api/v1/execution`.
- Tool listing, package management, environments, and workflow-local custom tools are under `/api/v1/tools`.
- The frontend serializes Vue Flow canvas state to backend `GraphState` before validation, saving, running, or clearing caches.

## Working Pattern

1. Identify whether the task touches workflow graph state, tool code, execution state, or docs only.
2. Read the relevant router, model, store, and composable before changing behavior.
3. Use the existing REST contract and generated frontend types as the source of truth.
4. Add or update focused tests for the resource or behavior being changed.
5. Run the narrow check first, then broader checks when the change touches shared behavior.
