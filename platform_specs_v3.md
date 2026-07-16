# BioImageFlow Platform Specifications — v3 (Webapp & Multi-User)

Read the [BioImageFlow library specification](bioimageflow/docs/source/specs.md) for the underlying workflow and tool contracts.

> **Status: future proposal.** The [v1](platform_specs_v1.md) and [v2](platform_specs_v2.md) documents define the implemented platform. This document proposes webapp and multi-user behavior; it must not be used as evidence that a feature is currently implemented unless that feature is explicitly inherited from v1 or v2.

The proposal builds on stable canvas ownership and backend workflow-draft revision CAS. Before multi-browser locking is implemented, the startup root must also use the same stable canonical canvas lifecycle as later roots; the current bootstrap canvas alias documented in v2 is not a sufficient long-term claimant identity. Revision conflicts remain authoritative, locks are advisory UX, and CRDT or automatic merge semantics remain deferred until simultaneous collaborative editing becomes a product requirement.

---

## 1. Dual Deployment Mode

BioImageFlow v3 introduces a dual deployment model. The same codebase runs in two distinct modes, selected at server startup and exposed as the read-only `deployment_mode` field in the `Settings` model.

### 1.1 Desktop Mode

- The FastAPI server binds to `localhost` only.
- No authentication required.
- Native file dialogs via pywebview for path selection.
- Napari is the primary image viewer (managed by `NapariLauncher` via Wetlands).
- Tool creation, editing, and hot-reload are enabled.
- The `POST /fs/reveal` endpoint opens paths in the system file browser.
- No CORS restrictions (localhost only).
- No rate limiting.

### 1.2 Webapp Mode

- The FastAPI server is exposed behind a reverse proxy.
- All API and WebSocket requests require authentication (see Section 2).
- Path selection uses the Dataset Browser modal (see Section 3) instead of native file dialogs.
- Viv is the primary image viewer (in-browser, see Section 4).
- Tool creation and source editing are disabled to prevent remote code execution.
- Tool hot-reload is disabled.
- The `POST /fs/reveal` endpoint returns 403 Forbidden. The frontend hides "Reveal in file browser" buttons.
- CORS is configured to allow requests from the frontend's deployed origin. The allowed origins list is configurable at deployment time.
- Rate limiting and request guards are active (see Section 9).
- Dataset management endpoints are available (see Section 3).
- Drag and drop triggers upload via the Dataset Browser (see Section 3.4).

### 1.2.1 Webapp Workspace Root

Webapp deployments use an admin-configured `workspaces_root`. Ordinary users
cannot choose or patch their workspace path. For each authenticated user the
server derives exactly one workspace:

```text
<workspaces_root>/<user_id>/workspace/
```

The per-user workspace contains `workflows/`, `data/`, `outputs/`, and
`.bioimageflow/`. Workflow ids are paths relative to `workspace/workflows/`,
GUI-created custom tools are scoped to each workflow's `tools/` folder, dataset
uploads are stored under the user's workspace data area, and runtime outputs are
stored under `workspace/outputs/<workflow_id>/`. `GET /api/v1/workspace`
returns these resolved roots plus read-only/admin-managed flags. In webapp mode
`PATCH /api/v1/workspace` returns 403 for ordinary users; only deployment/admin
configuration changes `workspaces_root`.

Workflow and folder path segments may contain spaces; they remain ordinary
workspace-relative path segments and cannot be empty, absolute, or traversal
segments. The server lists only workflow directories containing `workflow.json`;
other JSON files under the workspace remain ordinary files.

### 1.3 Mode Detection

The frontend reads `deployment_mode` from `GET /api/v1/settings` at startup and stores it in Pinia. All mode-conditional UI behavior (button visibility, viewer selection, path selection mechanism) branches on this value. The mode cannot be changed at runtime.

---

## 2. Authentication & Security

### 2.1 REST API Authentication

**Desktop mode:** No authentication required. The server binds to `localhost` only.

**Webapp mode:** All API endpoints require a session token or API key, passed as an `Authorization: Bearer <token>` header. The authentication mechanism is a simple shared secret configured at deployment time. Requests without a valid token receive HTTP 401 Unauthorized.

The authentication layer is implemented as FastAPI middleware. It checks the `Authorization` header on every request except:
- `GET /api/v1/health` — health check must be accessible without authentication for monitoring and reverse proxy health probes.

**Token format:** Opaque string (UUID or similar). In the per-user container architecture (Section 10), the launcher service issues tokens and the per-user FastAPI server validates them against the launcher.

### 2.2 WebSocket Authentication

**Desktop mode:** No authentication required for WebSocket connections.

**Webapp mode:** The WebSocket connection must include the session token as a query parameter: `/ws?token=<token>`. The server validates the token before accepting the connection. Invalid or missing tokens result in an immediate close frame with code 4001 and reason `"authentication_required"`.

On token expiration or invalidation, the server closes the WebSocket connection with code 4002 and reason `"token_expired"`. The frontend detects this close code and redirects the user to re-authenticate rather than attempting automatic reconnection.

### 2.3 Desktop-Only Endpoints

The following endpoints are disabled in webapp mode and return HTTP 403 Forbidden with error body `{"error": "desktop_only", "detail": "This endpoint is only available in desktop mode"}`:

| Endpoint | Reason |
|----------|--------|
| `POST /api/v1/fs/reveal` | Filesystem access (no system file browser in webapp) |
| `POST /api/v1/napari/open` | Launches a desktop GUI process |
| `GET /api/v1/napari/status` | Napari is not used in webapp mode |

### 2.4 Tool Creation and Editing Restrictions (Webapp Mode)

In webapp mode, the following are disabled to prevent remote code execution:

| Endpoint / Feature | HTTP Response | Reason |
|---------------------|---------------|--------|
| `POST /api/v1/tools` | 403 Forbidden | Tool creation would allow arbitrary code on the server |
| `POST /api/v1/editor/open` | 403 Forbidden | Source editing would allow arbitrary code modification |
| `POST /api/v1/editor/open-tool` | 403 Forbidden | Source editing would allow arbitrary code modification |
| Tool hot-reload (Section 2.7 of v1) | Disabled silently | No user-editable tool code in webapp mode |

The frontend hides the "Create Tool" button in the Tools Panel and "Open in editor" buttons on tool rows when `deployment_mode === "webapp"`.

Tool packages can still be installed from the **known packages list** (see Section 2.5) via the Tools Panel. Only packages on this pre-defined list are available for installation in locked-down webapp mode — users cannot install arbitrary PyPI packages, GitHub/GitLab package sources, or `.zip` package archives. The Manage Tools inline **Install tool package** footer for unknown package sources is hidden in locked-down webapp mode and its backend endpoints return HTTP 403. ProcessingTools are sandboxed by Wetlands; DataFrameTools from known packages run in the main process.

### 2.5 Available Package Versions and Known Packages Registry

Tool packages are published on **PyPI**. The server queries PyPI's JSON API (`https://pypi.org/pypi/{package_name}/json`) to retrieve available versions. The response's `releases` field lists all published versions. Version lists are fetched at server startup, refreshed after each successful install, and refreshable on demand via `POST /tools/packages/refresh`. Responses are not time-cached.

The list of known BioImageFlow tool packages is maintained in a configuration file (`~/.bioimageflow/known_packages.txt`) that is updated at startup from a central registry URL. The central registry URL fetch is planned but not yet implemented; until then, the bundled default is authoritative and the user file at `~/.bioimageflow/known_packages.txt` is honored if present.

**Registry requirements:**
- The URL must use HTTPS.
- The request has a 5-second timeout.
- If the registry is unavailable, the server falls back gracefully to the bundled default list shipped with the BioImageFlow installation.

**Format of `known_packages.txt`:** One package name per line, optionally followed by a comment:

```
bioimageflow-cellpose
bioimageflow-stardist
bioimageflow-omero
# Add new packages above this line
```

**Webapp mode restriction:** In webapp mode, `POST /api/v1/tools/packages/{name}/install` validates that the requested package name appears in `known_packages.txt`. Requests for unlisted packages return HTTP 403 Forbidden with `{"error": "unknown_package", "detail": "Package '{name}' is not in the approved package list"}`.

**Desktop mode:** No restriction. Any PyPI package can be installed. The known packages list is used only to populate the "available packages" section of the Tools Panel (packages the user hasn't installed yet but might want).

---

## 3. Dataset Management — Multi-User Extensions

Base dataset management (endpoints, Dataset Browser modal, drag-and-drop upload, filename sanitization, file size limit, path traversal prevention) is specified in **v1 Section 2.4.10 and Section 3.14** and is available in both deployment modes. v3 extends it for multi-user operation.

### 3.1 Per-User Storage Scoping

In webapp mode, datasets are partitioned by user:

```
datasets/{user_id}/{timestamp}_{sanitized_filename}.{ext}
```

- `{user_id}` is derived from the authenticated session token.
- The per-user directory replaces v1's single shared `datasets_root/` directory.
- Each user can only see and use their own datasets. The `GET /datasets` listing, the `POST /datasets/upload` target directory, and the `DELETE /datasets/{dataset_id}` authorization check are all scoped to the caller's `user_id`.
- `DELETE /datasets/{dataset_id}` returns HTTP 404 Not Found if the dataset exists but belongs to another user (same response as "not found", to avoid leaking IDs across users).
- No quota system is implemented in v3.

Desktop mode is unchanged: storage remains single-user and uses the v1 layout.

### 3.2 Path Traversal Gate (Multi-User)

v1's path traversal gate (`Path.resolve()` + prefix check) still applies, with the allowed prefix now `datasets/{user_id}/` rather than the shared `datasets_root/`. This ensures that even a forged `dataset_id` cannot escape into another user's directory.

### 3.3 Authenticated Access

All dataset endpoints (`GET /datasets`, `POST /datasets/upload`, `DELETE /datasets/{dataset_id}`) require an `Authorization: Bearer <token>` header in webapp mode (Section 2). Unauthenticated requests receive HTTP 401.

### 3.4 Dataset Browser — Webapp-Only Behavior

The Dataset Browser modal UI is specified in v1 Section 3.14. In webapp mode it is the **only** path-selection mechanism (native file dialogs are unreachable — there is no pywebview runtime), so the v1 behavior of "shown in browser mode, bypassed in pywebview mode" collapses to "always shown" in webapp deployments. The UI itself is unchanged.

---

## 4. Image Viewing — Viv (Webapp Mode)

### 4.1 Overview

v1 already defines workflow-scoped node-image serving, on-demand OME-TIFF conversion, and the external Avivator action. In the proposed webapp mode, Napari is unavailable because it requires a desktop GUI process. v3 replaces the external viewer dependency with an embedded [Viv](https://github.com/hms-dbmi/viv) panel and extends the image API for authenticated, per-user OME-TIFF and OME-Zarr access.

### 4.2 UI Integration

In the Data Table, image cells (columns typed as `ImagePath` or `ImageShared`) show:
- A thumbnail (loaded lazily from `GET /api/v1/nodes/{node_id}/thumbnail`).
- A **"View image"** button (replaces the "Open in Napari" button shown in desktop mode).

Clicking "View image" opens the Viv viewer inline in a new Dockview panel (or as a floating panel, depending on user layout preference). The viewer loads the image from the server via the image endpoint.

**Ctrl+Click** on "View image" replaces the current image in the viewer (if one is open) rather than opening a new panel.

### 4.3 Image Endpoint

The v1 node-image endpoint remains the base contract. v3 adds authentication, per-user workflow scoping, and OME-Zarr static-tree behavior.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/nodes/{node_id}/image` | Serve a full image file for the Viv viewer |

**Query parameters:**
- `row` (integer, required): Row index in the node's output DataFrame.
- `col` (string, required): Output column name (must be an image-typed column).
- `format` (string, optional): When set to `ome-tiff`, forces conversion to OME-TIFF regardless of source format.

**Response behavior by source format:**

| Source Format | Default Response | Notes |
|---------------|-----------------|-------|
| OME-TIFF | Served as-is (`image/tiff`) | Viv loads OME-TIFF natively with metadata (channels, resolution levels) |
| OME-Zarr | Redirects to a static file tree URL | The server serves the Zarr directory as static files under `/api/v1/nodes/{node_id}/zarr/{row}/{col}/`. Viv loads the `.zattrs` and chunk files directly. |
| Standard TIFF | Served as-is (`image/tiff`) | Viv handles standard multi-page TIFFs |
| PNG/JPEG | Served as-is (`image/png` or `image/jpeg`) | Simple 2D images |
| NIfTI (`.nii`, `.nii.gz`) | Served as-is (`application/gzip` or `application/octet-stream`) | Frontend uses a NIfTI loader for Viv |
| `SharedArray` (in-memory) | Converted to OME-TIFF on-the-fly and served | Includes shape/dtype metadata in OME-TIFF headers |

**Caching:** Responses include `ETag` headers based on `SHA256(file_path + file_mtime)`. Viv's HTTP loader respects conditional requests (`If-None-Match`), avoiding redundant transfers.

**OME-Zarr static serving:** For OME-Zarr data, the server exposes the Zarr directory tree as static files at `/api/v1/nodes/{node_id}/zarr/{row}/{col}/`. Viv loads the root `.zattrs` file to discover the multiscale structure, then fetches individual chunks on demand as the user pans and zooms. This is more efficient than converting to OME-TIFF for large multi-resolution images.

**Desktop mode:** This endpoint is available but rarely used (Napari is the primary viewer). It serves as a fallback for in-browser preview.

### 4.4 Viv Viewer Panel

The Viv viewer is rendered as a Dockview panel with the following controls:

- **Channel selector:** Toggle visibility and adjust contrast/brightness per channel (for multi-channel images).
- **Color map selector:** Choose from standard colormaps (grayscale, magma, viridis, etc.).
- **Zoom controls:** Mouse wheel zoom, fit-to-view button, zoom percentage display.
- **Pan:** Click and drag.
- **Resolution level selector:** For multi-resolution images (OME-TIFF pyramids, OME-Zarr), the viewer loads the appropriate resolution level based on the current zoom. Manual override is available.
- **3D orthogonal projections:** For 3D stacks, Viv provides XY, XZ, and YZ slice views with a slider to navigate through the stack.
- **Metadata panel:** Collapsible panel showing image metadata (dimensions, pixel size, channel names, data type).

---

## 5. Summary DataFrame

### 5.1 Overview

When multiple nodes are selected in the canvas, the Data Table (bottom panel) displays their individual DataFrames stacked vertically. When possible, a **Summary DataFrame** is displayed at the top, above the individual DataFrames.

### 5.2 Summary Computation

The summary is an **outer join on index** of all selected contiguous nodes' DataFrames. NaN values fill gaps where indices don't match. Column headers in the summary include a tooltip with the originating node name.

The summary join is computed **server-side** via `POST /api/v1/nodes/summary` to handle large DataFrames correctly with pagination.

### 5.3 Summary Endpoint

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/nodes/summary` | Compute summary DataFrame for multi-node selection |

**Request body:**

```json
{
  "node_ids": ["cellpose_segmenter_1", "stardist_segmenter_1"],
  "page": 0,
  "page_size": 50
}
```

**Response (success):**

```json
{
  "columns": [
    {"name": "mask", "source_node": "cellpose_segmenter_1", "type": "ImagePath"},
    {"name": "cell_count", "source_node": "cellpose_segmenter_1", "type": "int"},
    {"name": "mask", "source_node": "stardist_segmenter_1", "type": "ImagePath"},
    {"name": "nuclei_count", "source_node": "stardist_segmenter_1", "type": "int"}
  ],
  "index": ["img_001", "img_002", "img_003"],
  "rows": [
    {"cellpose_segmenter_1.mask": "/path/to/mask1.tif", "cellpose_segmenter_1.cell_count": 42, "stardist_segmenter_1.mask": "/path/to/sd_mask1.tif", "stardist_segmenter_1.nuclei_count": 38},
    {"cellpose_segmenter_1.mask": "/path/to/mask2.tif", "cellpose_segmenter_1.cell_count": 17, "stardist_segmenter_1.mask": null, "stardist_segmenter_1.nuclei_count": null}
  ],
  "total_rows": 250,
  "page": 0,
  "page_size": 50
}
```

Column keys in `rows` are namespaced as `{node_id}.{column_name}` to avoid ambiguity when multiple nodes have columns with the same name.

**Response (error):**

```json
{
  "error": "summary_unavailable",
  "reason": "no_common_index_lineage",
  "detail": "Selected nodes do not share a common index lineage"
}
```

Possible `reason` values:
- `"no_common_index_lineage"` — selected nodes' indices are not derived from the same root index.
- `"column_name_conflict"` — duplicate column names exist across DataFrames (this is now handled by namespacing, but reserved for future edge cases).

### 5.4 When Summary Is Shown

The summary is attempted whenever all selected nodes share a **common index lineage** — i.e., all selected nodes' indices are derived from the same root index (possibly through explosions). This is more permissive than requiring a strict linear chain: selecting a parent node and its two children (a fork) produces a valid summary.

### 5.5 When Summary Is Not Shown

- If selected nodes have no common index lineage (e.g., two independent source branches), the summary is omitted.
- The frontend shows a subtle message below the summary area: `"Summary unavailable — {reason}"`.
- When a single node is selected, no summary is needed (the node's own DataFrame is shown directly).

### 5.6 Display Limit

When more than 5 nodes are selected, only the first 5 individual DataFrames are shown below the summary, with a "Show all ({N})" toggle to display the rest. The summary always includes all selected nodes regardless of this limit.

---

## 6. OMERO Multi-User Extension

v1 defines the current OMERO instance and operating-system-keyring contract. A v3 deployment must scope credentials to the authenticated user's container or an equivalent isolated credential store. A shared launcher or host keyring must never expose one user's OMERO credential status or secret to another user. OMERO data access continues to use dedicated tool packages; the platform does not become an OMERO data broker.

---

## 7. Tab-Level Locking

### 7.1 Problem

Each root canvas already writes a complete graph to its workflow draft using `expected_revision`. If the same workflow is edited from multiple browser runtimes, draft CAS detects stale writes but cannot decide which user's edit should win. v3 adds an advisory single-writer experience so ordinary users encounter read-only mode before a CAS conflict, without weakening the backend conflict boundary.

### 7.2 Mechanism

The frontend uses a **`BroadcastChannel`** named `"bioimageflow-lock"` to coordinate between browser runtimes for the same authenticated user. A claim is bound to the path-derived workflow ID, a stable browser-runtime ID, and the canonical root canvas ID:

```json
{
  "type": "lock_claim",
  "workflow_id": "segmentation/my_workflow",
  "browser_id": "uuid-of-this-browser-runtime",
  "canvas_id": "workflow:segmentation%2Fmy_workflow",
  "timestamp": 1712160000000
}
```

**Lock acquisition rules:**

1. Before enabling mutations for a resolved root canvas, the runtime broadcasts `lock_claim` and waits 200ms for responses.
2. If another runtime responds with `lock_held` for the same authenticated user and workflow ID, the new canvas opens in **read-only mode**.
3. If no response arrives within 200ms, the canvas acquires the advisory lock and begins editing from the latest accepted backend draft revision.
4. The lock holder sends `lock_heartbeat` every 5 seconds. After 15 seconds without a heartbeat, another claimant may attempt acquisition, but it must reload or reconcile the latest accepted draft before enabling mutations.
5. Every write still sends `expected_revision`. A `draft_revision_conflict` always enters the explicit conflict UI; possession of an advisory lock never authorizes an overwrite.

**Messages:**

| Type | Fields | Description |
|------|--------|-------------|
| `lock_claim` | `workflow_id`, `browser_id`, `canvas_id`, `timestamp` | A canonical root canvas wants to edit this workflow |
| `lock_held` | `workflow_id`, `browser_id`, `canvas_id` | Another runtime already holds the advisory lock |
| `lock_heartbeat` | `workflow_id`, `browser_id`, `canvas_id`, `timestamp` | Periodic keepalive from the lock holder |
| `lock_release` | `workflow_id`, `browser_id`, `canvas_id` | The owning canvas is being closed or disposed |

### 7.3 Read-Only Mode

When a tab opens in read-only mode:

- A persistent banner is shown at the top: `"This workflow is open in another tab. Close that tab to edit here."`
- All graph mutations are disabled: node/edge creation and deletion, parameter editing, enable/disable toggle, clear outputs, save, undo/redo.
- Read-only interactions are allowed: selecting nodes, viewing the Node Panel, browsing the Data Table, scrolling the Logger Panel, panning/zooming the canvas, opening images in the viewer.
- The Run button is disabled with tooltip: `"Cannot execute in read-only mode."`

### 7.4 Lock Release

When the lock-holding canvas is closed or its browser runtime is disposed, it broadcasts `lock_release`. Merely activating another internal Dockview tab does not release the lock, because the original canvas remains mounted and owns its draft coordinator.

**Fallback for unclean closure:** If the lock-holding tab crashes or is killed (no `beforeunload` event fires), the heartbeat timeout (15 seconds) ensures other tabs can eventually acquire the lock.

**`localStorage` fallback:** If `BroadcastChannel` is not available, the frontend falls back to a `localStorage`-based advisory lock. The lock key is `"bioimageflow-lock-{encoded_workflow_id}"` and its value contains `{browser_id, canvas_id, timestamp}`. Runtimes poll every 2 seconds to detect stale locks. Backend draft CAS remains the authority in both mechanisms.

---

## 8. Customizable Keyboard Shortcuts

### 8.1 Overview

All keyboard shortcuts are customizable via the Settings panel. Users can rebind any shortcut to a different key combination.

### 8.2 Settings Panel UI

The Settings panel includes a "Keyboard Shortcuts" section with a table:

| Column | Content |
|--------|---------|
| **Action** | Human-readable action name (e.g., "Delete selected", "Undo", "Save workflow") |
| **Default** | The default key binding (read-only, for reference) |
| **Current binding** | Editable field showing the current key binding |
| **Reset** | Button to reset this shortcut to its default |

**Editing a binding:** Clicking the "Current binding" cell puts it into recording mode (the cell shows `"Press a key combination..."`). The next key combination pressed by the user is captured and displayed. Press `Escape` to cancel recording without changing the binding.

**Conflict detection:** If the user assigns a key combination already used by another action, a warning is shown inline: `"This shortcut is already assigned to '{other_action}'. Reassign?"` with "Reassign" (moves the binding, clears the old action's binding) and "Cancel" buttons.

**"Reset All" button:** Below the table. Resets all shortcuts to their defaults.

### 8.3 Default Shortcuts

| Shortcut | Action ID | Action |
|----------|-----------|--------|
| `Delete` / `Backspace` | `delete_selected` | Delete selected nodes/edges |
| `Ctrl+Z` | `undo` | Undo (client-side) |
| `Ctrl+Shift+Z` | `redo` | Redo (client-side) |
| `Ctrl+C` | `copy` | Copy selected nodes (+internal edges) |
| `Ctrl+V` | `paste` | Paste |
| `Ctrl+A` | `select_all` | Select all nodes |
| `Ctrl+S` | `save` | Save workflow |
| `Ctrl+Enter` | `validate_now` | Validate immediately (skip debounce) |
| `Ctrl+F` | `focus_search` | Focus tool search bar |
| `Space` (hold) | `pan_mode` | Pan mode |
| `F` | `fit_view` | Fit all nodes in view |
| `Escape` | `deselect` | Deselect all / cancel current action |

### 8.4 Storage

Shortcut overrides are stored in the `keyboard_shortcuts` field of the `Settings` model:

```python
keyboard_shortcuts: dict[str, str] = {}  # Action ID -> key binding
```

Only overridden shortcuts are stored. Missing entries use the default. The key binding format follows the standard web convention: `"Ctrl+Shift+Z"`, `"Delete"`, `"Space"`, `"F"`, etc. Modifier order is normalized to `Ctrl+Alt+Shift+Meta`.

Example stored value:

```json
{
  "keyboard_shortcuts": {
    "delete_selected": "Ctrl+Backspace",
    "fit_view": "Ctrl+0"
  }
}
```

### 8.5 Frontend Implementation

The frontend registers a global keydown handler that maps key combinations to action IDs using the merged shortcut map (defaults + overrides from settings). The handler is updated whenever settings change. Vue Flow's built-in keyboard handling is disabled in favor of the custom handler to ensure all shortcuts go through the same configurable system.

---

## 9. Rate Limiting & Request Guards

### 9.1 Overview

In webapp mode, the server applies rate limiting and request guards to prevent abuse and protect server resources. These protections are disabled in desktop mode.

### 9.2 Rate-Limited Endpoints

The following endpoints are rate-limited server-side:

| Endpoint | Limit | Reason |
|----------|-------|--------|
| `PUT /api/v1/workflow-drafts/{id}` | 10 requests/second per session | Bounds authoritative root-draft validation writes |
| `POST /api/v1/workflow-draft-operations/{id}` | 10 requests/second per session | Bounds structured agent mutations |
| `PUT /api/v1/nested-workflow-snapshots/{session_id}` | 10 requests/second per session | Bounds authoritative private-snapshot validation writes |
| `PUT /api/v1/graph` | 10 requests/second per session | Bounds explicit stateless compatibility or transient-validation calls |

Rate limiting is per-session (identified by the authentication token). Requests exceeding the limit receive HTTP 429 Too Many Requests with a `Retry-After` header.

### 9.3 Request Body Size Cap

All endpoints have a maximum request body size of **5MB** (configurable). Requests exceeding this limit are rejected with HTTP 413 Payload Too Large before the body is read. This applies to all endpoints except `POST /api/v1/datasets/upload`, which has its own configurable file size limit (default 2GB; see v1 Section 2.4.10).

### 9.4 Validation Timeout

Graph validation performed by authoritative workflow-draft or nested-snapshot writes, structured draft operations, and explicit request-local `PUT /graph` calls has a timeout of **10 seconds** (configurable). If validation exceeds this timeout, the server aborts the request and returns HTTP 504 Gateway Timeout with:

```json
{
  "error": "validation_timeout",
  "detail": "Graph validation exceeded the 10-second timeout. Simplify the graph or increase the timeout."
}
```

The frontend shows a toast with this message. The immediate canvas snapshot remains visible, while the last accepted backend draft or private snapshot revision remains unchanged and the canvas stays pending or conflicted until retry.

### 9.5 Configuration

Rate limiting and request guard parameters are configurable at deployment time via environment variables or the launcher service configuration:

| Parameter | Environment Variable | Default |
|-----------|---------------------|---------|
| Rate limit (validated graph endpoints) | `BIOIMAGEFLOW_RATE_LIMIT` | `10` (requests/second) |
| Request body size cap | `BIOIMAGEFLOW_MAX_BODY_SIZE` | `5242880` (5MB) |
| Validation timeout | `BIOIMAGEFLOW_VALIDATION_TIMEOUT` | `10` (seconds) |
| Dataset upload size limit | `BIOIMAGEFLOW_MAX_UPLOAD_SIZE` | `2147483648` (2GB) |

---

## 10. Multi-User Architecture

### 10.1 The DataFrameTool Security Problem

In the current architecture, `DataFrameTool` runs in the **main server process** (the same process that hosts FastAPI, manages the Workflow, and holds all state). This is by design — DataFrameTools need full pandas access and benefit from zero-overhead DataFrame manipulation. However, in webapp mode, this means any DataFrameTool code (including from installed PyPI packages) has unrestricted access to the server's filesystem, network, and memory.

Sandboxing ProcessingTools is straightforward (Wetlands already isolates them in separate processes). Sandboxing DataFrameTools is harder because their core abstraction — "I transform DataFrames in the main process" — is inherently incompatible with process-level isolation.

Three approaches were evaluated:

| Approach | Description | Spec Impact | Drawbacks |
|----------|-------------|-------------|-----------|
| **Per-user container** | Each user's entire BioImageFlow server runs in a rootless Podman container | None (operational only) | Higher resource usage per user |
| **DataFrameTool in worker** | Move DataFrameTools to sandboxed workers (like ProcessingTools) | Major — redesigns a core abstraction | DataFrame serialization overhead, blurs tool type distinction |
| **Hybrid trust model** | Sandbox only user-created DataFrameTools, trust installed packages | Moderate — two execution paths | Complexity, "trusted" is a judgment call |

### 10.2 Recommended Architecture: Per-User Containers

The recommended approach for webapp mode is to run each user's BioImageFlow server inside a **rootless Podman container**. This provides full isolation without changing the library architecture.

```
                    +-----------------------------------+
                    |        Launcher Service            |
                    |  (auth, container orchestration)   |
                    +----------------+------------------+
                                     |
                    +----------------v------------------+
                    |       Reverse Proxy (nginx)        |
                    |   routes /api/user_token -> container
                    +----+---------------------+--------+
                         |                     |
          +--------------v----+  +-------------v-------+
          | Podman (user1)    |  | Podman (user2)      |
          |                   |  |                     |
          | FastAPI server    |  | FastAPI server      |
          | bioimageflow      |  | bioimageflow        |
          | DataFrameTools    |  | DataFrameTools      |
          |   +-- Wetlands    |  |   +-- Wetlands      |
          |   |   workers     |  |   |   workers       |
          |   +-- code-server |  |   +-- code-server   |
          +-------------------+  +---------------------+
```

**Why this approach:**

1. **Zero library spec changes.** DataFrameTool keeps its "main process" semantics. ProcessingTool keeps its Wetlands isolation. The sandboxing is purely operational.
2. **The DataFrameTool design is architecturally correct.** Merge/filter/aggregate operations are fundamentally DataFrame-level and benefit from running in-process with full pandas access. Forcing them into workers would add serialization overhead and blur the clean separation between "per-row processing in isolated env" (ProcessingTool) and "holistic DataFrame manipulation" (DataFrameTool).
3. **Standard pattern.** Per-user containers is the established approach for multi-tenant compute platforms (JupyterHub, Google Colab, Gitpod).
4. **Solves multi-user.** Each container is a user session with its own filesystem namespace, tool store, and workflow state.

### 10.3 Launcher Service

A new lightweight service (`bioimageflow-launcher`) manages user containers.

**Responsibilities:**

| Responsibility | Description |
|----------------|-------------|
| **Authentication** | Validates user credentials (OAuth, LDAP, or simple token-based). Issues session tokens. |
| **Container lifecycle** | Spins up a rootless Podman container on first authenticated request. Reuses it for subsequent requests. Stops it after an idle timeout (configurable, default 30 minutes). |
| **Reverse proxy** | Routes HTTP and WebSocket traffic to the correct container based on the user's session token. |
| **Resource limits** | Configures per-container CPU, memory, and GPU limits via Podman flags. |
| **Data volumes** | Mounts the user's derived workspace into the container. |

**Container lifecycle states:**

```
  [No container]
       |
       | First authenticated request
       v
  [Creating]  (~2-5 seconds)
       |
       | Container ready
       v
  [Running]
       |
       | Idle timeout (default 30min)
       v
  [Stopped]
       |
       | Next authenticated request
       v
  [Running]  (restart, ~1-2 seconds)
```

**Launcher API:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/login` | Authenticate user, return session token |
| `POST` | `/auth/logout` | Invalidate session token, optionally stop container |
| `GET` | `/status` | Return launcher health and container count |

All other requests are proxied to the user's container based on the session token in the `Authorization` header.

### 10.4 Container Configuration

**Container image:** A pre-built OCI image containing:
- Python (version matching the BioImageFlow requirement)
- `bioimageflow`, `bioimageflow-core`, pandas
- code-server
- Wetlands

Tool packages are mounted from a shared read-only tool store to avoid duplication across containers. Wetlands environments are created inside the container's own filesystem.

**Data volumes:**

| Host path | Container mount | Mode |
|-----------|-----------------|------|
| `{workspaces_root}/{user_id}/workspace/` | `/workspace/` | Read/Write |
| `{workspaces_root}/{user_id}/workspace/.bioimageflow/settings.json` | `/home/bioimageflow/.bioimageflow/settings.json` | Read/Write |
| `{data_root}/shared/tool_packages/` | `/home/bioimageflow/.bioimageflow/tool_packages/` | Read-Only |
| `{data_root}/shared/known_packages.txt` | `/home/bioimageflow/.bioimageflow/known_packages.txt` | Read-Only |

Inside the container, `BIOIMAGEFLOW_WORKSPACE=/workspace` and the backend
reports `/workspace` as the user's workspace path. Workflow files live under
`/workspace/workflows/`, workflow-local custom tools under
`/workspace/workflows/<id>/tools/`, uploads under `/workspace/data/datasets/`, and runtime outputs under
`/workspace/outputs/`. Workflow creation accepts an optional description. The
workflow detail UI shows and edits that description, opens the workflow folder
through the system file browser when available, and avoids showing both a
workflow-file row and storage-path row for the same concept.

**Resource limits (Podman flags):**

| Resource | Flag | Default |
|----------|------|---------|
| CPU | `--cpus` | 4 |
| Memory | `--memory` | 8GB |
| GPU | `--device nvidia.com/gpu=N` | 0 (no GPU by default) |

Resource limits are configurable per-user or globally via the launcher configuration.

### 10.5 GPU Support

Podman supports GPU passthrough via `--device nvidia.com/gpu=all` (requires `nvidia-container-toolkit` on the host).

**GPU allocation strategies:**

| Strategy | Description |
|----------|-------------|
| **Exclusive** | Each container gets one or more dedicated GPUs. Simple but limits concurrency. |
| **Shared** | All containers share all GPUs via `nvidia.com/gpu=all`. Relies on CUDA's built-in scheduling. Higher utilization but risk of OOM. |
| **On-demand** | The launcher allocates GPUs to containers only when an execution requests GPU resources (via the node's `ResourceSpec`). GPUs are released when execution completes. Best utilization but requires launcher-level GPU tracking. |

The launcher configuration specifies the strategy. The default is **shared** for simplicity.

**Container GPU configuration:** When a user's workflow includes nodes with GPU requirements (either from tool `ResourceSpec` or user overrides in `NodeState.resources`), the launcher attaches GPU devices to the container. The Wetlands workers inside the container handle GPU allocation for individual ProcessingTool executions.

### 10.6 Startup Latency

| Phase | Duration |
|-------|----------|
| Container creation (cached image) | ~2-5 seconds |
| FastAPI server startup (tool store scan) | ~1-3 seconds |
| Total first-request latency | ~3-8 seconds |

Subsequent requests within the same session hit the running container instantly. The launcher shows a loading screen during container creation: `"Starting your BioImageFlow session..."` with a progress indicator.

### 10.7 Idle Timeout and Cleanup

Containers are stopped after an idle timeout (configurable, default 30 minutes). "Idle" means no HTTP or WebSocket activity. The launcher checks container activity every 60 seconds.

**Before stopping:**
1. The launcher sends a shutdown signal to the FastAPI server inside the container.
2. The server follows its normal shutdown sequence (stop execution if running, terminate Napari, clean shared memory, save settings).
3. The container is stopped (not removed — restarting is faster than recreating).

**Container removal:** Stopped containers are removed after a longer timeout (configurable, default 24 hours) to allow quick restarts. Data is preserved on the host volumes.

### 10.8 Impact on Existing Components

| Component | Change Required |
|-----------|----------------|
| `bioimageflow-core` | None |
| `bioimageflow` (library) | None |
| GUI backend (FastAPI) | None (runs inside the container as-is) |
| GUI frontend | Minimal — login page, token storage, loading screen during container startup |
| Deployment | New: launcher service, Podman configuration, container image build, nginx config |
| Settings | New: launcher config file (idle timeout, resource limits, auth provider, GPU strategy) |

### 10.9 Desktop Mode

Desktop mode is unaffected by multi-user architecture. No containers, no launcher, no authentication. The FastAPI server runs directly on the user's machine, bound to `localhost`. This is the v1/v2 architecture and remains unchanged.

---

## 11. Updated API Endpoint Summary

The following table lists all endpoints that are **new or modified** in v3. Endpoints unchanged from v2 are not listed.

### 11.1 New Endpoints

| # | Method | Endpoint | Mode | When Used |
|---|--------|----------|------|-----------|
| 1 | `POST` | `/api/v1/nodes/summary` | Both | Summary DataFrame for multi-node selection in Data Table |

Node-image serving and tool-package refresh are current v1 endpoints. Dataset management endpoints (`GET /datasets`, `POST /datasets/upload`, `DELETE /datasets/{dataset_id}`) are also defined in v1 Section 2.4.10. v3 modifies these existing contracts with per-user scoping and authentication.

### 11.2 Modified Endpoints

| # | Endpoint | Change |
|---|----------|--------|
| 1 | `PUT /api/v1/workflow-drafts/{id}` | Rate-limited authoritative root persistence and validation; validation timeout applies. |
| 2 | `POST /api/v1/workflow-draft-operations/{id}` | Rate-limited structured draft mutations; validation timeout applies. |
| 3 | `PUT /api/v1/nested-workflow-snapshots/{session_id}` | Rate-limited private-snapshot persistence and validation; validation timeout applies. |
| 4 | `PUT /api/v1/graph` | Rate-limited only as stateless compatibility or transient validation; validation timeout applies. |
| 5 | `POST /api/v1/tools` | Returns 403 Forbidden in webapp mode. |
| 6 | `POST /api/v1/tools/packages/{name}/install` | In webapp mode, only known packages are allowed (403 for unknown). |
| 7 | `POST /api/v1/fs/reveal` | Returns 403 Forbidden in webapp mode. |
| 8 | `POST /api/v1/napari/open` | Returns 403 Forbidden in webapp mode. |
| 9 | `GET /api/v1/napari/status` | Returns 403 Forbidden in webapp mode. |
| 10 | `POST /api/v1/editor/open` | Returns 403 Forbidden in webapp mode. |
| 11 | `POST /api/v1/editor/open-tool` | Returns 403 Forbidden in webapp mode. |
| 12 | `GET /api/v1/workspace` | Returns the derived per-user workspace and admin-managed flags. |
| 13 | `PATCH /api/v1/workspace` | Returns 403 Forbidden for ordinary webapp users. |
| 14 | `GET /api/v1/settings` | Returns read-only deployment and workspace information for the authenticated user. |
| 15 | WebSocket `/ws` | Requires `?token=<token>` query parameter in webapp mode. |

### 11.3 Launcher Service Endpoints (New Service)

| # | Method | Endpoint | Description |
|---|--------|----------|-------------|
| 1 | `POST` | `/auth/login` | Authenticate user, return session token |
| 2 | `POST` | `/auth/logout` | Invalidate session, optionally stop container |
| 3 | `GET` | `/status` | Launcher health and container count |

All other requests to the launcher are proxied to the user's BioImageFlow container.

---

## 12. Settings Behavior in v3

The current v1 API already exposes `deployment_mode`, `update_mode`, and `keyboard_shortcuts`; their presence in the JSON model does not mean the future v3 controls are implemented. v3 adds the following normative behavior around those existing fields.

### 12.1 `deployment_mode`

- The deployment supplies `"desktop"` or `"webapp"` at server startup.
- In v3 it is read-only through `PATCH /api/v1/settings`; attempts to change it return 422.
- The frontend uses it for authentication, path selection, viewer choice, desktop-only action visibility, and request-guard behavior.

### 12.2 `update_mode`

- The future update UI edits the existing `Literal["auto", "manual"] | str` field.
- `"auto"` selects the latest supported stable release, `"manual"` disables automatic updates, and a version string pins that release.
- The dropdown and package-index version discovery described here are v3 UI requirements, not current v1/v2 guarantees.

### 12.3 `keyboard_shortcuts`

- The future shortcut editor writes normalized action-ID-to-key-binding overrides into the existing `keyboard_shortcuts` dictionary.
- Missing entries use defaults and an empty value disables an action.
- The recording, conflict-resolution, and reset UI is specified in Section 8 and is not implemented by merely exposing the settings field.

---

## 13. Deferred Enhancements Preserved From The Legacy Specification

These items remain future proposals and are not part of the implemented v1/v2 contract:

- **Large-workflow warning:** show a persistent informational warning above a configurable node-count threshold, initially around 50 nodes. For sub-workflows, count the flattened internal total.
- **Canvas minimap:** offer an optional overview minimap for large graphs without making it a required default control.
- **WebSocket sequencing and backpressure:** add a monotonic server-to-client sequence number and a bounded delivery policy so reconnecting clients can detect gaps and discard messages older than their contextual resynchronization snapshot.
- **Step-by-step execution:** expose the library's `compute_steps()` capability as a future debugging mode that prepares and executes one node at a time while preserving the execution context and canvas-lock invariants.

CRDT merge behavior is intentionally not part of these enhancements. Draft revision conflicts and the advisory single-writer UX remain the concurrency boundary until simultaneous collaborative editing is explicitly required.
