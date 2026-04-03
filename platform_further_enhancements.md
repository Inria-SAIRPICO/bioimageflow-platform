# BioImageFlow — Further Enhancements

> Ideas and features considered for future versions beyond v3. These are not prioritized or scheduled.

---

## 1. Canvas Minimap

**Description** — A small overview panel rendered in a corner of the canvas showing the entire workflow graph at a reduced scale, with a viewport rectangle indicating the current visible area. Useful for navigating large workflows where the user has zoomed in and lost spatial context. Vue Flow provides a built-in `MiniMap` component that can be dropped in with minimal effort.

**Complexity** — Low. Vue Flow ships this as an optional component; integration is mostly configuration (position, size, styling, node color mapping).

**Dependencies** — Requires the v1 canvas (Section 3.3) to be in place. No other prerequisites.

**Notes** — The spec lists this alongside pan, zoom, and fit-view as a canvas control (Section 3.3.4) but marks it as "optional." It becomes more valuable once workflows grow large enough to trigger the large-workflow warning (see below). Consider making it auto-visible above a certain node count and manually togglable otherwise.

---

## 2. Large Workflow Warning Banner

**Description** — A persistent info banner displayed when the workflow exceeds a configurable node threshold (default: 50 nodes). The message reads: "Your workflow has {N} nodes. Consider splitting it into sub-workflows for better organization." The goal is to nudge users toward modular workflow design before performance or readability degrades.

**Complexity** — Low. Counting nodes is trivial; the banner is a simple reactive UI element tied to the node array length. The threshold should be stored in user preferences so power users can adjust or dismiss it.

**Dependencies** — Requires the v1 canvas and basic workflow editing. No dependency on sub-workflow support (which is itself a separate future feature) — the banner is advisory only.

**Notes** — The spec (Section 2.2) frames this as a UX guardrail, not a hard limit. Consider adding a "Don't show again" option per workflow, or a global preference to disable it. If sub-workflow support is ever added, the banner could link to documentation or offer a one-click action to extract a selected group of nodes into a sub-workflow.

---

## 3. Step-by-Step Execution

**Description** — A debugging-oriented execution mode where the workflow runs one node at a time, pausing between nodes so the user can inspect intermediate outputs before proceeding. Built on the library's existing `compute_steps()` API, which already provides per-node prepare/execute control. The UI would add "Step" and "Continue" buttons alongside the current "Run" button.

**Complexity** — Medium. The library-side plumbing (`compute_steps()`) exists. The main work is on the platform side: a new execution mode in the backend that yields after each node, WebSocket messages to signal "paused at node X," frontend controls for stepping/continuing, and UI for inspecting intermediate data while paused.

**Dependencies** — Requires v1 execution infrastructure (REST endpoint, WebSocket node-state messages, output viewers). Benefits significantly from v2 data viewers (DataFrames, images) since the value of stepping is directly tied to the ability to inspect intermediate results.

**Notes** — The spec (Section 11.1) explicitly states this should not change the current `compute()` flow — it is a parallel mode, not a replacement. Key design questions: Can the user modify parameters while paused? (Probably not — graph editing is locked during execution.) Should stepping respect skip/cache logic, or always force-execute each node? Consider also adding breakpoints (click a node to mark it as a pause point) rather than pausing at every single node.

---

## 4. WebSocket Message Sequencing

**Description** — Adding a monotonic sequence number to every server-to-client WebSocket message. This enables three capabilities: (1) the frontend can detect and discard stale messages that arrive after a reconnection resync, (2) the frontend can detect gaps in the sequence to know if messages were missed, and (3) it opens the door to backpressure mechanisms where the client signals it is falling behind.

**Complexity** — Medium to High. Adding the sequence field itself is simple, but the implications are broad: the frontend needs logic to buffer, reorder, or discard messages based on sequence numbers; reconnection logic (Section 2.5) must reconcile the sequence state after a resync; and backpressure requires a feedback channel from client to server plus server-side buffering or throttling.

**Dependencies** — Requires the v1 WebSocket infrastructure to be stable. The current reconnection strategy (exponential backoff + full state resync via REST) works without sequencing, so this is an incremental reliability improvement rather than a prerequisite for anything.

**Notes** — The spec (Section 2.5) calls this out as a "future improvement" and notes the current protocol has no ordering guarantees. A pragmatic first step would be to add the sequence number to messages and implement stale-message detection on reconnection, deferring the more complex backpressure mechanism. The sequence counter should reset on server restart (the reconnection resync already handles state reconstruction, so a reset is safe as long as the client treats reconnection as a sequence boundary).
