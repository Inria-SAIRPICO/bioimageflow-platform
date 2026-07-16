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

The dev server proxies `/api` to `http://127.0.0.1:8000` and `/ws` to `ws://127.0.0.1:8000`. Start the backend first.

To specify another backend port:

```bash
BIOIMAGEFLOW_BACKEND_PORT=8008 bun run dev
```

## Workspace UX

The frontend treats workflows as a tree rooted at the current user's workspace:

```text
workspace/
  workflows/    folders and workflow directories
  tools/        workspace-owned custom tools
  data/
  outputs/
```

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
bun run test:e2e                 # Run E2E tests (Playwright, needs backend + frontend)
```

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

Requires the backend running at http://localhost:8000. Fetches `/openapi.json` and generates `src/api/types.ts` using `openapi-typescript`.

## Linting

```bash
bun run lint                     # ESLint
```
