---
orphan: true
---

# Platform test obligation dashboard

This is the canonical campaign denominator for the implemented, in-scope features catalogued by the [GUI](coverage-gui.md), [workflow](coverage-workflows.md), and [runtime](coverage-runtime.md) inventories.
The inventories retain assertion details, selectors, manual boundaries, and gaps; this dashboard assigns stable feature IDs and records the countable scenario decisions without copying that prose.
The dashboard baseline is `b213223` (2026-09-15); its counts remained provisional until the complete applicability audit recorded in this revision.
Change the denominator only when implementation or specification reconciliation adds, removes, splits, combines, or changes the applicability of a feature, and record the revision that made that change here.

The [new campaign](platform-test-plan.md) is running: the four readiness outcomes pass in both browsers, and Wave 2 feature work is delegated.
The counts combine retained historical evidence with the ten newly accepted N1/E1 obligations at `884be6e` and `2290c67`; baseline reconciliation must assess the remaining historical cells before reporting a current campaign percentage.
No cell is promoted or reset by the campaign redesign alone.

## Counting rules

Each row has five scenario dimensions: successful behavior (`S`), invalid input or refused action (`R`), cancellation/failure/recovery (`F`), persistence/reload (`P`), and applicable identity/concurrency/ownership/permission boundaries (`B`).
The cell states are `V` verified by the cited campaign evidence, `G` known evidence gap, `I` work in progress, `B` externally blocked, `U` applicable but not yet assessed, and `N` not applicable with the reason in the cell.
Only `N` is excluded from the denominator.
`V` means executed evidence, not merely an inspected test body; the linked inventory describes exactly what was asserted.
A row is `verified` only when all of its applicable cells are `V`; otherwise its row status is `in-progress`, `gap`, `blocked`, or `unassessed` according to the work still required.

`Primary GUI` is a deliberately selected core set: the ordinary create/edit/connect/run/inspect/save/reopen journeys, immediate nested-edit loss-prevention, execution-context continuity, and immediate result-lifecycle boundaries.
It is not a synonym for every ordinary or user-visible GUI feature; routine settings, layout, catalog administration, datasets, and external integrations remain in the overall denominator unless they participate directly in those core journeys.
All applicable cells of a `yes` row enter the primary-GUI denominator; lower-level tests may supply a boundary obligation, but a `V` success cell on a user-visible action still requires behavioral UI evidence on the supported surface.
Priorities are `P0` core journey/loss or wrong-result risk, `P1` ordinary remaining user behavior, and `P2` specialist, native, or less-frequent integration behavior.

The ID prefix names the source inventory and table: `GUI-SHL`, `GUI-EDT`, and `GUI-AUT` map to the three GUI tables; `WF-LIF`, `WF-REC`, and `WF-SRC` map to the three workflow tables; `RT-EXE`, `RT-RES`, and `RT-XCT` map to the three runtime tables.
Each stable ID is declared directly on its source inventory row and is the sole inventory/dashboard mapping key; labels and row positions are descriptive only.
The numeric suffix records the ID's original baseline assignment, not a live ordinal, so inserting or reordering source prose must not renumber an existing ID.
IDs must be unique across the inventories and dashboard.

The original 98-row applicability audit remains recorded, but a platform change scan through `15c5cc7` (2026-09-24) found ten additional in-scope obligations awaiting scenario-level evidence, including one older omitted import-readiness action.
The counts below include those new gaps; older `V` cells cite their exact historical revisions and require focused revalidation when later changes affect their contract.

- Overall: **327 V + 167 G + 0 I + 0 B + 6 U = 500 applicable obligations**, so **327 / 500 are verified (65.4%)**; this is accumulated evidence, and blocked and unassessed are reported separately from the ratio numerator.
- Primary GUI: **224 V + 0 G + 0 I + 0 B + 0 U = 224 applicable obligations**, so **224 / 224 are verified (100.0%)**.
- Inventory reconciliation: 108 feature rows, 540 scenario decisions, including 40 justified `N` decisions.

These ratios are coverage status, not a claim that the current revision passed a complete test lane.
The integrated image/file/export evidence is credited only for its exact browser, archive-byte, deterministic refusal, rollback, and identity assertions; its remaining recovery, reload, and native-boundary cells stay gaps.

## GUI editing and authoring obligations

| Stable ID | Feature (inventory row) | Priority | Supported surface | Primary GUI | S | R | F | P | B | Status | Evidence revision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GUI-SHL-009 | Image Viewers environment settings, defaults, and filename rules | P1 | Desktop GUI/API; restricted webapp | no | V | V | V | V | V | verified | `dfb5cb3` implementation; controlled GUI and persisted API evidence `198e6f6` |
| GUI-SHL-001 | Default docks, menu, and panel visibility | P1 | Desktop and webapp GUI | no | G | N (no invalid-input or refused-action contract for shell layout) | N (no cancellation or recovery lifecycle for static shell layout) | G | N (no identity, concurrency, ownership, or permission boundary for shell layout) | gap | `fcb4408` inspection |
| GUI-SHL-002 | Empty-workspace chooser without implicit workflow | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `4208769`, `75be9c2` |
| GUI-SHL-003 | Recovery preference and obsolete identities | P0 | Desktop and webapp GUI/draft API | yes | V | V | V | V | V | verified | `dd20821`, `75be9c2`, `301c19c` |
| GUI-SHL-004 | Recovered-edge geometry | P0 | Desktop and webapp GUI | yes | V | N (geometry rendering accepts no user input to refuse) | N (geometry rendering has no cancellation or recovery lifecycle) | V | N (geometry is derived within the owning canvas and has no separate boundary) | verified | `dd20821` |
| GUI-SHL-005 | Preferences opening and desktop availability | P1 | Desktop and webapp GUI | no | V | G | V | V | G | in-progress | `settings.spec.ts` Chromium/Firefox at base `4ef9068`: controlled load failure, real reopen recovery and cached settings; availability/refusal limits in inventory |
| GUI-SHL-006 | Persisted Node Data page size | P1 | Desktop and webapp GUI/settings API | no | V | V | N (page-size selection has no separate cancellation lifecycle) | V | N (the global display preference has no scoped identity or ownership boundary) | verified | `settings.spec.ts` Chromium/Firefox at base `4ef9068`, plus real settings API invalid-value refusal; new-table/local override limits in inventory |
| GUI-SHL-007 | OMERO settings cards and secret handling | P2 | Desktop GUI/settings API; webapp restrictions | no | G | G | G | G | G | gap | `fcb4408` inspection |
| GUI-SHL-008 | Desktop/editor settings and forbidden webapp mutation | P2 | Desktop and webapp settings API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| GUI-EDT-014 | Deterministic recursive imported-graph layout persists after first materialization | P1 | Desktop and webapp GUI/import | no | V | N (invalid graph rejection belongs to import/validation, not layout) | N (layout computation has no separate cancellation or recovery lifecycle) | V | V | verified | `imported-graph-layout.spec.ts` Chromium/Firefox; `test_graph_translator.py` recursive and edge-case layout |
| GUI-EDT-001 | Catalog inspect, double-click add, drag add, and select | P0 | Desktop and webapp GUI | yes | V | V | V | V | V | verified | `eb0dc74`, `4208769`, `a44851e` |
| GUI-EDT-002 | Fit large/small graphs and encoded paths | P1 | Desktop and webapp GUI | no | G | N (viewport fitting accepts no invalid domain input) | N (viewport fitting has no cancellation or recovery lifecycle) | N (fit geometry is recomputed and is not durable workflow state) | N (viewport fitting has no identity, concurrency, ownership, or permission boundary) | gap | `fcb4408` inspection |
| GUI-EDT-003 | Whole-DataFrame edges and dynamic columns | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `4208769`, `4456435`, `bd92dfc` |
| GUI-EDT-004 | Column input labels and disconnect/reconnect | P0 | Desktop and webapp GUI | yes | V | V | V | V | V | verified | `e0aa123`, `4456435`, `bd92dfc` |
| GUI-EDT-005 | Mapped/collective column appearance | P1 | Desktop and webapp GUI | no | G | N (row-consumption appearance accepts no user input to refuse) | N (derived edge appearance has no cancellation or recovery lifecycle) | N (appearance is derived from metadata and is not persisted) | G | gap | `fcb4408` inspection |
| GUI-EDT-006 | Parameter controls feed the accepted Run | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `1261326`, `4208769` |
| GUI-EDT-007 | Node rename preserves identity and refuses duplicates | P0 | Desktop and webapp GUI | yes | V | V | N (rename validation is synchronous; refusal is owned by R and no separate recovery follows) | V | V | verified | `ec0ca3b` |
| GUI-EDT-008 | Selection, multiselection, collapse, and enablement | P0 | Desktop and webapp GUI | yes | V | V | V | V | V | verified | `30faeb6`, `1d7cbd7` |
| GUI-EDT-009 | Bulk delete and root output clear | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `30faeb6` |
| GUI-EDT-010 | Undo/redo granularity and canvas isolation | P0 | Desktop and webapp GUI | yes | V | V | V | V | V | verified | `e0aa123`, `30faeb6`, `4ec5dbc` |
| GUI-EDT-011 | Clipboard structure and fresh identities | P0 | Desktop and webapp GUI | yes | V | V | V | V | V | verified | `790345a`, `26551d6` |
| GUI-EDT-012 | Keyboard commands, active context, and text focus | P0 | Desktop and webapp GUI | yes | V | V | V | V | V | verified | `790345a`, `4ec5dbc` |
| GUI-EDT-013 | Processing resources and output templates | P1 | Desktop and webapp GUI/API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| GUI-AUT-008 | Manage Tools environment inventory and create/recreate | P1 | Desktop and webapp server processing GUI/API | no | V | V | V | V | V | verified | current T1 actualforce GUI72.764s, public-provider failure/retry/science60.066s, controlled visible Chrome8.872s/Firefox11.406s and deterministic105; physical versus client and original failures qualified in current checkpoint |
| GUI-AUT-001 | Catalog search and selected-tool reveal | P1 | Desktop and webapp GUI | no | G | N (search has no invalid domain input; an unmatched query is successful empty-result behavior) | N (search and reveal have no cancellation or recovery lifecycle) | N (query and reveal state are not specified as durable) | G | gap | `fcb4408` inspection |
| GUI-AUT-002 | Custom-tool create/rename/delete and editor opening | P1 | Desktop GUI/API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| GUI-AUT-003 | Package versions, install/uninstall, and errors | P1 | Desktop GUI/API; restricted webapp | no | V | V | V | V | V | verified | `package-management.spec.ts` Chromium/Firefox at base `c99d76c`; local ZIP/exact non-active removal scope, public recorded-bytecode regression and nine reload neighbors; network and native limits in inventory |
| GUI-AUT-004 | Editable-source watcher and invalid-edit recovery | P1 | Desktop GUI/WebSocket | no | V | V | V | V | V | verified | `8ce0c043` + owned-source Chromium/Firefox receipts; installed failure transport excluded |
| GUI-AUT-005 | Embedded editor startup, progress, and stable iframe | P2 | Desktop GUI/external editor | no | G | G | G | G | G | gap | `fcb4408` inspection |
| GUI-AUT-006 | Node-addressed source opening | P1 | Desktop GUI/API | no | G | G | G | N (opening or focusing a source is ephemeral; source persistence belongs to WF-SRC rows) | G | gap | `fcb4408` inspection |
| GUI-AUT-007 | Trusted Python preview/apply/cancel | P1 | Desktop GUI/API; denied in webapp | no | V | V | V | V | V | verified | October8 source-preserving Apply/root-title repair; `python-authoring.spec.ts` Chromium/Firefox and eight owning service cases, receipt-qualified |

## Workflow obligations

| Stable ID | Feature (inventory row) | Priority | Supported surface | Primary GUI | S | R | F | P | B | Status | Evidence revision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WF-LIF-015 | Confirmed workflow-format migration and backups | P1 | Desktop and webapp GUI/API/storage | no | V | V | V | V | V | verified | `4a2a344` implementation; focused browser/backend evidence `2ce96a0` |
| WF-LIF-001 | Canonical saved document and graph-owned visible name | P1 | Workflow API/storage | no | G | G | N (canonical document validation is synchronous; invalid documents are owned by R) | G | G | gap | `fcb4408` inspection |
| WF-LIF-002 | Create from dialog with generated identity | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `4208769`, `4a03750` |
| WF-LIF-003 | Save As and workflow switching | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `a25ac17`, `4a03750` |
| WF-LIF-004 | Save and reopen an accepted edited graph | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `4208769`, `dd20821` |
| WF-LIF-005 | Duplicate definition without results | P1 | Workflow API/storage | no | V | G | G | V | V | in-progress | `a25ac17` |
| WF-LIF-006 | Copy captured agent graph and recursive owned sources | P1 | Desktop and webapp GUI/API | no | V | V | V | V | V | verified | `e817d77` |
| WF-LIF-007 | Reject stale duplicate generation | P1 | Workflow API/storage | no | N (this row owns stale-generation refusal; ordinary duplication is WF-LIF-005) | G | N (stale duplication is refused before side effects and has no recovery lifecycle) | G | G | gap | `fcb4408` inspection |
| WF-LIF-008 | Durable workflow generation across restart | P1 | Workflow API/storage | no | G | N (generation durability accepts no user input to refuse) | G | G | G | gap | `fcb4408` inspection |
| WF-LIF-009 | Move results and rewrite provenance safely | P1 | Workflow API/storage | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-LIF-010 | Delete exact tab and preserve empty state | P1 | Desktop and webapp GUI/API | no | V | G | V | V | V | in-progress | `0b3ee1e` |
| WF-LIF-011 | Revisioned draft writes, dirtiness, and validation | P0 | Draft API/storage and GUI | yes | V | V | V | V | V | verified | `dd20821` |
| WF-LIF-012 | Explicit root discard and conflict recovery | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `dd20821` |
| WF-LIF-013 | Agent edits synchronize to a clean canvas | P1 | Desktop and webapp GUI/WebSocket | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-LIF-014 | Browser fallback and accepted-draft recovery | P0 | Desktop and webapp GUI/storage | yes | V | V | V | V | V | verified | `dd20821`, `301c19c` |
| WF-REC-001 | Stable field/output publication and rename | P0 | Desktop and webapp nested GUI/API | yes | V | V | V | V | V | verified | `af58e4e`, `bcedaec`, `14582d0` |
| WF-REC-002 | Positional DataFrame publication and compaction | P1 | Desktop and webapp nested GUI/API | yes | V | V | V | V | V | verified | `1e84421`, `bcedaec` |
| WF-REC-003 | Forward a child DataFrame port through parent interface | P1 | Desktop and webapp nested GUI/API | yes | V | V | V | V | V | verified | `3422e1c`, `dd9e231` |
| WF-REC-004 | Deleting exposed node prunes interface atomically | P1 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `1e84421`, `dd9e231`, `72b21a0` |
| WF-REC-005 | Group selected graph with stable ports | P1 | Graph utility/API | no | V | G | G | G | V | in-progress | `a36a4cb` |
| WF-REC-006 | Group through canvas controls | P0 | Desktop and webapp GUI | yes | V | V | V | V | V | verified | `da0ded6`, `152c82b`, `0dc71b5`, `72b21a0` |
| WF-REC-007 | Durable private nested snapshot isolation | P0 | Desktop and webapp nested GUI/API | yes | V | V | V | V | V | verified | `af58e4e`, `14582d0` |
| WF-REC-008 | Nested CAS and descendant cleanup | P1 | Nested API/storage | yes | V | V | V | V | V | verified | `7575d0e` |
| WF-REC-009 | Nested conflict waits for explicit choice | P1 | Nested GUI/session coordinator | yes | V | V | V | V | V | verified | `d86c9b0` |
| WF-REC-010 | Stale parent refuses nested apply | P0 | Desktop and webapp nested GUI/API | yes | V | V | V | V | V | verified | `f920c9b`, `6025ee6` |
| WF-REC-011 | Destructive nested interface apply is confirmed and recoverable | P0 | Desktop and webapp nested GUI/API | yes | V | V | V | V | V | verified | `cf794fb`, `6025ee6` |
| WF-REC-012 | Nested execution and scoped durable results | P0 | Desktop and webapp GUI/runtime | yes | V | V | V | V | V | verified | `fd96f8f`, `8cdc768`, `339330f`; exact nested-instance GUI recheck `9c4a435` |
| WF-REC-013 | Semantic operation-batch atomicity | P1 | Draft operation API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-REC-014 | Containment-cycle rejection | P1 | Workflow API/storage | no | N (this row owns cycle refusal; successful embedding is covered by WF-REC-005 and WF-REC-006) | G | N (cycle insertion is refused atomically before a recovery lifecycle begins) | G | G | gap | `fcb4408` inspection |
| WF-SRC-011 | Import viewing readiness and setup guidance without blocking execution | P1 | Desktop GUI/import/API | no | V | V | V | N (readiness is recalculated on saved Open; workflow archive persistence is WF-SRC-008) | V | verified | October 8 source-bound I1 receipts; Chromium/Firefox six exact and ten affected browser passes |
| WF-SRC-001 | Explicit identity-bound source update preview/apply | P1 | Desktop API/storage | no | V | V | V | V | V | verified | `d02dea9` |
| WF-SRC-002 | Detach changes provenance only | P1 | Desktop GUI/API | no | G | G | N (atomic synchronous operation; no recovery lifecycle) | G | G | gap | `fcb4408` inspection |
| WF-SRC-003 | Owned-source import materializes editable files | P1 | Desktop API/storage | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-SRC-004 | Captured code and independent imports remain stable | P1 | Desktop runtime/storage | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-SRC-005 | Copy/export captures edited owned sources | P1 | Desktop API/storage | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-SRC-006 | Source-bound metadata and invalid edits | P1 | Desktop API/runtime | no | V | V | V | V | V | verified | retained scoped-metadata anchor + `8ce0c043` owned-source Chromium/Firefox receipts |
| WF-SRC-007 | Imported and embedded source independence | P1 | Desktop GUI/API/runtime | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-SRC-008 | Import collision rename and naming contract | P1 | Desktop and webapp GUI/API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-SRC-009 | Portable export versus results-bundle distinction | P1 | Desktop and webapp GUI/API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-SRC-010 | Trusted Python materialization and fresh helpers | P1 | Desktop API; denied in webapp | no | V | V | V | V | V | verified | October8 fresh immutable manifests, exact captured sources, factory-free Apply and poisoned-authoring reopen/Run; public/service/browser evidence |

## Runtime and integration obligations

| Stable ID | Feature (inventory row) | Priority | Supported surface | Primary GUI | S | R | F | P | B | Status | Evidence revision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RT-EXE-016 | Overall execution plan progress and setup phase | P1 | Desktop and webapp GUI/runtime | yes | V | V | V | V | V | verified | `9b3cb22`, `7f56806` implementation; `6a3c5df`, `18aa760` focused GUI evidence; setup presentation uses a controlled local retained-run fixture |
| RT-EXE-017 | Corrupt selected cache refusal, quarantine, and recovery | P1 | Desktop and webapp GUI/API/storage | no | V | V | V | V | V | verified | `4a2a344`, `2dbdd7f` implementation; focused GUI, result-integrity, and recovery evidence `e58b8f1` |
| RT-EXE-018 | Lazy stale processing-environment rebuild | P1 | Desktop GUI/local runtime | no | V | V | V | V | V | verified | `2290c67` integrated repair; real worker, three journeys per browser and scoped app completion |
| RT-EXE-001 | Run accepted draft and Run Selected boundary | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `8908388`, `339330f`; accepted-draft router selectors `71b82da` |
| RT-EXE-002 | Compilation/storage retry keeps one identity | P1 | Execution API/manager | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-EXE-003 | Second-run refusal and mutation serialization/lock | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `da2ced2` |
| RT-EXE-004 | Real Direct source execution | P0 | Desktop and webapp GUI/runtime | yes | V | V | V | V | V | verified | `4208769`, `9698d5b`; Direct manager/API selectors `71b82da` |
| RT-EXE-005 | Recursive Direct execution and result attribution | P0 | Desktop and webapp GUI/runtime | yes | V | V | V | V | V | verified | `fd96f8f`, `8cdc768`, `339330f` |
| RT-EXE-006 | Real sequential worker isolation and output files | P0 | Local desktop runtime/integration | yes | V | V | V | V | V | verified | `da2ced2`, `4676ffb`, `f09a8a7`; real-worker GUI `6a3c5df`, graph routing `71b82da` |
| RT-EXE-007 | Progress and completion keep one context | P1 | API/WebSocket/GUI | yes | V | V | V | V | V | verified | `2c1ff72`, `f09a8a7` |
| RT-EXE-008 | Failure, cancellation, correction, and rerun | P0 | Local desktop GUI/runtime | yes | V | V | V | V | V | verified | `da2ced2`, `4676ffb` |
| RT-EXE-009 | Cache invalidation and selected clear | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `30faeb6`, `fe0cf9d`, `0043397`, `58520b5`; ISSUE-011 resolved |
| RT-EXE-010 | Validation/cache flags match computation | P1 | Runtime/API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-EXE-011 | Output-template filename and signature | P1 | Desktop and webapp GUI/runtime | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-EXE-012 | Latest projection symlink/pointer fallback | P2 | Local filesystem/runtime | no | G | G | G | G | U | gap | `fcb4408` inspection |
| RT-EXE-013 | Exact latest-result read and incomplete-data refusal | P1 | Results API/storage | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-EXE-014 | Latest-results folder export and rollback | P0 | Desktop and webapp GUI/API/storage | yes | V | V | V | V | V | verified | `7ab16e6`, `6ae081d` |
| RT-EXE-015 | Workflow-results bundle pins one run | P0 | Desktop and webapp GUI/API/storage | yes | V | V | V | V | V | verified | `7ab16e6`, `6ae081d` |
| RT-RES-012 | Result-scoped napari chooser and exclusive output favorite | P1 | Desktop GUI/API; restricted webapp | no | V | V | V | V | V | verified | `884be6e`; seven intercepted-client GUI scenarios in Chromium/Firefox, captured-action unit regressions, and separate real CAS favorite storage; no native launch credit |
| RT-RES-001 | Table filtering, sorting, paging, and CSV identity | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `d1072ce`, `168b487` |
| RT-RES-002 | Merge compatible selections and stack unrelated data | P0 | Desktop and webapp GUI/API | yes | V | V | N (projection selection is synchronous and has no cancellation or recovery lifecycle) | V | V | verified | `c050207`, `7d9de88` |
| RT-RES-003 | Column labels, filters, widths, and ordering | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `c050207`, `125ee3d` |
| RT-RES-004 | Dataset upload partial success and path limits | P1 | Desktop and webapp GUI/API | no | V | V | V | V | V | verified | `ac1d6c9` scoped dataset Chromium/Firefox receipts + retained backend boundaries |
| RT-RES-005 | Dataset folders, moves, stale delete preview | P1 | Desktop and webapp GUI/API | no | V | V | V | V | V | verified | `ac1d6c9` scoped dataset Chromium/Firefox receipts + retained backend boundaries |
| RT-RES-006 | Cancel and retry browser upload | P1 | Desktop and webapp GUI/API | no | V | G | V | V | V | in-progress | `ac1d6c9` scoped dataset Chromium/Firefox receipts + retained backend boundaries |
| RT-RES-007 | Image identity, conversion, offsets, and browser viewer | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `7ab16e6`, `af1951b`, `bfb6197`; exact viewer GUI recheck `9c4a435` |
| RT-RES-008 | Thumbnail placeholder, paths, formats, and GUI display | P1 | Desktop and webapp GUI/API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-RES-009 | Reveal path and native file dialogs | P2 | Native desktop/manual | no | G | G | G | N (native reveal and chooser actions are ephemeral) | G | gap | `fcb4408` inspection |
| RT-RES-010 | Fiji result resolution and native launch | P2 | Native desktop/manual external app | no | G | G | G | N (launch is ephemeral; settings persistence is GUI-SHL-008) | G | gap | `fcb4408` inspection |
| RT-RES-011 | Napari environment, launch, and reconnect lifecycle | P2 | Native desktop/manual external app | no | U | U | U | U | U | unassessed | `fcb4408` inspection pending |
| RT-XCT-007 | Logger selection and filtered-log copying | P1 | Desktop and webapp GUI | no | V | N (an empty selection is a valid empty-result state, not invalid input) | N (copy has no durable cancellation or recovery lifecycle) | N (selection and clipboard content have no platform reload contract) | V | verified | `4a5b870`; exact Logger selectors in Chromium and Firefox at `cd81d42` |
| RT-XCT-001 | WebSocket subscriptions, reconnect, and backpressure | P1 | Desktop and webapp GUI/WebSocket | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-XCT-002 | Execution-log provenance and global background logs | P1 | Backend/WebSocket/GUI | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-XCT-003 | Contextual error history, Logger, and navigation | P0 | Desktop and webapp GUI/WebSocket | yes | V | V | V | N (session-only Error History and Logger have no reload-retention contract; durable run diagnostics belong to execution history) | V | verified | `4676ffb`; specialist contract review |
| RT-XCT-004 | Structured HTTP errors and expected-error logging | P1 | REST API/logging | no | G | G | N (request error translation is synchronous and has no cancellation or recovery lifecycle) | N (request-scoped; no persisted user state) | G | gap | `fcb4408` inspection |
| RT-XCT-005 | MCP typed operations and stable interface IDs | P2 | MCP/API/GUI | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-XCT-006 | Desktop startup identity, window, and shutdown | P2 | Native desktop/manual | no | G | G | G | N (startup shell has no portable saved state) | G | gap | `fcb4408` inspection |

## Applying later evidence

When a batch lands, update only the affected cells, row status, and evidence revision, then recompute both ratios.
Run `scripts/test check campaign` on the consolidated inventory/dashboard edit; `scripts/test check docs` also invokes this verifier before Sphinx when documentation structure changes or at certification.
Do not replace the detailed inventory evidence with dashboard prose.
If one existing row is found to contain separable user actions with different obligations, split it under new stable IDs and retain the old ID as a documented alias; never silently reuse an ID for a different contract.
If a manual or external obligation cannot run, keep it `B` with its recovery procedure in the source inventory or [manual testing guide](manual-testing.md); owner acceptance records a limitation but does not turn it into `V`.
