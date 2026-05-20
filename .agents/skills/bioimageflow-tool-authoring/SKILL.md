---
name: bioimageflow-tool-authoring
description: Use when creating, editing, renaming, deleting, validating, or debugging workflow-local BioImageFlow tool source code and metadata.
---

# BioImageFlow Tool Authoring

Use this skill when creating, renaming, deleting, or debugging BioImageFlow tools for a workflow.

## Source Of Truth

- Workflow-local custom tools live under the workflow directory's `tools/` folder.
- Use the `/api/v1/tools` endpoints with `workflow_name` whenever possible; this keeps path resolution, registry refresh, and platform validation consistent.
- Package tools are not editable through custom tool endpoints.
- Agents must never edit platform source to create user tools. Use the workflow-root workspace, and treat the platform reference as a copy and read-only reference.

## Workflow

1. Load or identify the active workflow name.
2. Create tools with `POST /api/v1/tools?workflow_name=<name>` and a body containing `name` and `tool_type`.
3. Fetch source with `GET /api/v1/tools/{tool_name}/source?workflow_name=<name>`.
4. Rename with `PATCH /api/v1/tools/{tool_name}?workflow_name=<name>`.
5. Delete with `DELETE /api/v1/tools/{tool_name}?workflow_name=<name>` only after checking usage.
6. Refresh tools/packages and validate affected graphs after changes.

## Naming Constraints

Tool class names must be non-empty, unpadded, valid Python identifiers, start with an uppercase letter, and contain no whitespace, path separators, or `..`.

## Safety Notes

- Do not write arbitrary files outside a workflow-local `tools/` directory.
- Request package install approval before installing dependencies needed by a custom or package-backed tool.
- Keep undo available by making graph references to new tools through draft id and revision proposals instead of manual saved JSON edits.
- In webapp mode, tool creation, rename, and deletion may be disabled unless unsafe webapp features are enabled.
- If a tool is referenced by saved workflows, report the affected workflows before deleting or renaming.
