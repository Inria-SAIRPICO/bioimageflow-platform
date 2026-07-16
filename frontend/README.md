# BioImageFlow Frontend

Vue 3 single-page application for visually building and inspecting bioimage analysis workflows. Features a node-based DAG editor, dockable multi-panel layout, and real-time execution monitoring.

## Tech Stack

- **Vue 3** with Composition API and TypeScript
- **Pinia** for state management
- **PrimeVue** (Aura theme) for UI components
- **Vue Flow** for the node-based DAG canvas
- **Dockview** for the multi-panel dockable layout
- **Vite** for dev server and builds
- **Vitest** for unit tests, **Playwright** for E2E tests

## Project Structure

```
src/
  App.vue                     Dockview shell with MenuBar
  main.ts                     App entry point
  api/
    client.ts                 Axios HTTP client
    types.ts                  Auto-generated from OpenAPI schema
  stores/
    ui.ts                     Panel visibility, selection, tab title
    toolRegistry.ts           Tool metadata from backend
    execution.ts              Execution state
    settings.ts               Application settings
    workflow.ts               Workspace workflow tree and active workflow state
  components/
    layout/
      MenuBar.vue             PrimeVue Menubar with panel toggles
    panels/
      ToolsPanel.vue          Searchable tool tree with drag support
      WorkflowsPanel.vue      Workspace workflow tree and folder controls
    canvas/
      CanvasView.vue          Vue Flow DAG editor
      ToolNode.vue            Custom node component
      ColumnRefEdge.vue       Column reference edge
      PositionalEdge.vue      Positional edge
  composables/
    useUndoRedo.ts            Client-side undo/redo
    useGraphSync.ts           Graph state synchronization
    useCanvasStatusProjection.ts  Canvas-scoped derived node statuses
  utils/
    clipboard.ts              Copy/paste serialization
    nodeIdGenerator.ts        Unique node ID generation
    typeColors.ts             Type-to-color mapping
```

## Setup

```bash
bun install                      # Install dependencies
```

## Development

```bash
bun run dev                      # Start Vite dev server (port 5173)
```

The dev server proxies `/api` and `/ws` to the backend port selected by `BIOIMAGEFLOW_BACKEND_PORT`, defaulting to `8000`. Start the backend first.

To specify another backend port:

```bash
BIOIMAGEFLOW_BACKEND_PORT=8008 bun run dev
```

## Workspace UX

The frontend treats workflows as a tree rooted at the current user's workspace:

```text
workspace/
  workflows/                          folders and workflow directories
    <workflow-id>/tools/              custom tools owned by one workflow
```

Execution outputs use the backend's configured output-data folder rather than `workspace/outputs`, and uploaded datasets use the configured dataset root rather than `workspace/data`.

Desktop users can change the workspace path in Settings with a folder picker.
Webapp users see a read-only workspace path; the admin configures the
workspaces root server-side. The Workflows panel renders folders and workflow
rows, supports folder names with spaces, create/rename/delete folder actions,
and uses drag/drop for moving workflows and folder subtrees between folders.
Creating a workflow from a selected folder adds it to that folder. Dragging a
workflow onto the canvas remains the sub-workflow creation gesture.

The Tools panel opens source through the editor API that keeps VS Code or
code-server rooted at the workspace project and focuses the selected tool file.

## Testing

```bash
bun run test:unit                # Run all unit tests (Vitest)
bun run test:unit:watch          # Watch mode
bun run test:e2e                 # Run E2E tests with Playwright-managed isolated servers
```

Playwright starts and stops the backend and frontend servers declared in `playwright.config.ts`; do not start shared development servers for the normal E2E command. See [`../docs/testing.md`](../docs/testing.md) for the required Chromium lane, optional Firefox lane, and environment-isolation details.

## Building

```bash
bun run build                    # Production build to dist/
bun run preview                  # Preview the production build
bun run type-check               # TypeScript type checking (vue-tsc)
```

## Code Generation

```bash
bun run generate-types           # Generate TypeScript types from backend OpenAPI schema
```

By default this requires the backend at `http://localhost:8000`. Set `OPENAPI_URL` to use another schema URL, for example `OPENAPI_URL=http://localhost:8008/openapi.json bun run generate-types`.

The script regenerates OpenAPI paths and schemas and appends its declared compatibility aliases. Workflow-draft helpers also retain manual types in `src/api/workflowDrafts.ts`, so review the generated diff and run type-checking before committing it.

## Linting

```bash
bun run lint                     # ESLint
```
