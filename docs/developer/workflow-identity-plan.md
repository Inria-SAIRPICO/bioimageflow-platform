---
orphan: true
---

# Workflow identity and folder plan

Keep real folders and per-workflow directories containing definitions, owned tools, drafts and results.
Separate identity from location to preserve references and open canvases during reorganization.
This proposal does not supersede current path-based specifications until implemented.

## Scope and decisions

- Store an immutable UUID in the platform workflow document envelope, outside the portable graph and artifact hash.
- Use that UUID for workflow references and canvas ownership; expose workspace-relative `path` separately for browsing and filesystem operations.
- Preserve display name and portable definition name independently of location; moving a workflow changes neither.
- Keep folder identities as relative paths.
- Keep existing single-item drag-and-drop and folder rename interactions.
- Exclude multi-selection, cut/copy/paste, Move-to, tags, favorites, saved searches, linked folders and database-backed storage.

## Implementation order

1. **Introduce persistent identity and migrate existing state.**
   Inventory path-based ownership in saved documents, root drafts, nested snapshots, source provenance, execution records, viewer preferences, recovery snapshots, tabs and agent/API clients.
   Extend the existing confirmed, backed-up, restart-safe migration to cover server references and a durable migration-only old-path/generation-to-UUID mapping; assign UUIDs once in the confirmed plan.
   Remap browser recovery and tabs on reconnect using that mapping; ambiguous or missing owners remain recoverable conflicts, never guesses based on a reused path.
   Retire the mapping after recovery reconciliation; it is never an alternative addressing authority.
   Change backend models/routes, regenerate frontend types, then switch consumers to UUID addressing and explicit paths, removing path-as-identity handling.
   Keep UUIDs outside portable archives and graph hashes; creation, import and duplication allocate fresh UUIDs, while moves preserve them.
   Preserve draft/snapshot revisions and dirty baselines, identity-generation fences and captured-operation ownership; a move changes none of them.

2. **Create in the currently selected folder.**
   Route every New-workflow entry point through the Workflows panel's shared selection.
   Resolve the selected folder when Create is submitted, then freeze the workspace and destination for the request and any conflict retry.
   A selected workflow row means its containing folder; no selection means the workspace workflows root.
   Show the destination in the creation dialog and update it if selection changes before submission.
   If the destination disappears or becomes invalid, retain the entered name and report the problem instead of silently creating at the root.
   Load the backend-created graph with its slash-free definition name and configuration.

3. **Preserve open canvases during application moves.**
   Resolve the captured UUID to its current location under the existing mutation gate and reuse the move journal for physical directory changes and path-bearing metadata.
   Flush drafts and private nested snapshots without saving or applying them; retain canvases, unsaved state and undo history after workflow or containing-folder moves.
   Rebind pending persistence to the accepted location without allowing a late response to recreate the old directory.
   Keep execution/storage locks and recoverable failure behavior; refuse moves while any affected local or managed run owns storage.
   Keep changing a display title distinct from renaming a directory.

4. **Reconcile external filesystem changes.**
   Use fresh catalog scans and explicit Refresh to resolve UUIDs to current paths; any index is rebuildable from workflow documents.
   Recheck UUID and storage before writes, independently of Refresh; reconcile external moves without replacing locally edited graphs or recreating missing directories.
   Report missing workflows and duplicate UUIDs without overwriting files or choosing an arbitrary directory.
   External copies require explicit resolution to receive fresh identities.
   If an external move affects an active run, report unavailable storage and retain recovery state rather than retargeting the running engine.

## Acceptance and validation

- Migration preserves graph hashes, owned sources, results and unsaved edits, and resumes safely after interruption.
- Every New entry point follows selection changes until submission; delayed responses cannot retarget creation.
- Workflow and containing-folder moves preserve UUIDs, source references, preferences and open root/nested editor state; late saves cannot restore old paths.
- Import and duplicate receive fresh identities; external moves, missing directories, duplicate UUIDs and path reuse produce deterministic recovery or conflict behavior.
- Run focused tests per step, then `scripts/test check app` and `scripts/test check cross-browser-smoke`; use `scripts/test check all` for broad browser/test-infrastructure changes.
- Update every affected platform specification and `PLATFORM_CONTEXT.md` alongside implementation, distinguishing persistent IDs, paths, display names and definition names.
