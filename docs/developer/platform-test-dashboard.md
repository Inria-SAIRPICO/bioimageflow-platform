---
orphan: true
---

# Platform test obligation dashboard

This is the canonical campaign denominator for the implemented, in-scope features catalogued by the [GUI](coverage-gui.md), [workflow](coverage-workflows.md), and [runtime](coverage-runtime.md) inventories.
The inventories retain assertion details, selectors, manual boundaries, and gaps; this dashboard assigns stable feature IDs and records the countable scenario decisions without copying that prose.
The dashboard baseline is `b213223` (2026-09-15); its counts remained provisional until the complete applicability audit recorded in this revision.
Change the denominator only when implementation or specification reconciliation adds, removes, splits, combines, or changes the applicability of a feature, and record the revision that made that change here.

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

The initial totals were provisional while every scenario dimension was reconciled against its source contract. This revision completes that audit; the following totals are no longer provisional:

- Overall: **229 V + 222 G + 0 I + 0 B + 6 U = 457 applicable obligations**, so **229 / 457 are verified (50.1%)**; blocked and unassessed are reported separately from the ratio numerator.
- Primary GUI: **207 V + 13 G + 0 I + 0 B + 0 U = 220 applicable obligations**, so **207 / 220 are verified (94.1%)**.
- Inventory reconciliation: 98 feature rows, 490 scenario decisions, including 33 justified `N` decisions.

These ratios are coverage status, not a claim that the current revision passed a complete test lane.
The integrated image/file/export evidence is credited only for its exact browser, archive-byte, deterministic refusal, rollback, and identity assertions; its remaining recovery, reload, and native-boundary cells stay gaps.

## GUI editing and authoring obligations

| Stable ID | Feature (inventory row) | Priority | Supported surface | Primary GUI | S | R | F | P | B | Status | Evidence revision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GUI-SHL-001 | Default docks, menu, and panel visibility | P1 | Desktop and webapp GUI | no | G | N (no invalid-input or refused-action contract for shell layout) | N (no cancellation or recovery lifecycle for static shell layout) | G | N (no identity, concurrency, ownership, or permission boundary for shell layout) | gap | `fcb4408` inspection |
| GUI-SHL-002 | Empty-workspace chooser without implicit workflow | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `4208769`, `75be9c2` |
| GUI-SHL-003 | Recovery preference and obsolete identities | P0 | Desktop and webapp GUI/draft API | yes | V | V | V | V | V | verified | `dd20821`, `75be9c2`, `301c19c` |
| GUI-SHL-004 | Recovered-edge geometry | P0 | Desktop and webapp GUI | yes | V | N (geometry rendering accepts no user input to refuse) | N (geometry rendering has no cancellation or recovery lifecycle) | V | N (geometry is derived within the owning canvas and has no separate boundary) | verified | `dd20821` |
| GUI-SHL-005 | Preferences opening and desktop availability | P1 | Desktop and webapp GUI | no | G | G | G | G | G | gap | `fcb4408` inspection |
| GUI-SHL-006 | Persisted Node Data page size | P1 | Desktop and webapp GUI/settings API | no | G | G | N (page-size selection has no cancellation or recovery lifecycle) | G | N (the global display preference has no scoped identity or ownership boundary) | gap | `fcb4408` inspection |
| GUI-SHL-007 | OMERO settings cards and secret handling | P2 | Desktop GUI/settings API; webapp restrictions | no | G | G | G | G | G | gap | `fcb4408` inspection |
| GUI-SHL-008 | Desktop/editor settings and forbidden webapp mutation | P2 | Desktop and webapp settings API | no | G | G | G | G | G | gap | `fcb4408` inspection |
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
| GUI-AUT-001 | Catalog search and selected-tool reveal | P1 | Desktop and webapp GUI | no | G | N (search has no invalid domain input; an unmatched query is successful empty-result behavior) | N (search and reveal have no cancellation or recovery lifecycle) | N (query and reveal state are not specified as durable) | G | gap | `fcb4408` inspection |
| GUI-AUT-002 | Custom-tool create/rename/delete and editor opening | P1 | Desktop GUI/API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| GUI-AUT-003 | Package versions, install/uninstall, and errors | P1 | Desktop GUI/API; restricted webapp | no | G | G | G | G | G | gap | `fcb4408` inspection |
| GUI-AUT-004 | Editable-source watcher and invalid-edit recovery | P1 | Desktop GUI/WebSocket | no | V | G | G | V | V | in-progress | `353b425` |
| GUI-AUT-005 | Embedded editor startup, progress, and stable iframe | P2 | Desktop GUI/external editor | no | G | G | G | G | G | gap | `fcb4408` inspection |
| GUI-AUT-006 | Node-addressed source opening | P1 | Desktop GUI/API | no | G | G | G | N (opening or focusing a source is ephemeral; source persistence belongs to WF-SRC rows) | G | gap | `fcb4408` inspection |
| GUI-AUT-007 | Trusted Python preview/apply/cancel | P1 | Desktop GUI/API; denied in webapp | no | G | G | G | G | G | gap | `fcb4408` inspection |

## Workflow obligations

| Stable ID | Feature (inventory row) | Priority | Supported surface | Primary GUI | S | R | F | P | B | Status | Evidence revision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
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
| WF-REC-004 | Deleting exposed node prunes interface atomically | P1 | Desktop and webapp GUI/API | yes | V | G | V | V | V | in-progress | `1e84421`, `dd9e231` |
| WF-REC-005 | Group selected graph with stable ports | P1 | Graph utility/API | no | V | G | G | G | V | in-progress | `a36a4cb` |
| WF-REC-006 | Group through canvas controls | P0 | Desktop and webapp GUI | yes | V | G | V | V | V | in-progress | `da0ded6`, `152c82b`, `0dc71b5` |
| WF-REC-007 | Durable private nested snapshot isolation | P0 | Desktop and webapp nested GUI/API | yes | V | V | V | V | V | verified | `af58e4e`, `14582d0` |
| WF-REC-008 | Nested CAS and descendant cleanup | P1 | Nested API/storage | yes | V | V | V | V | V | verified | `7575d0e` |
| WF-REC-009 | Nested conflict waits for explicit choice | P1 | Nested GUI/session coordinator | yes | V | V | V | V | V | verified | `d86c9b0` |
| WF-REC-010 | Stale parent refuses nested apply | P0 | Desktop and webapp nested GUI/API | yes | V | V | V | V | G | in-progress | `f920c9b` |
| WF-REC-011 | Destructive nested interface apply is confirmed and recoverable | P0 | Desktop and webapp nested GUI/API | yes | V | V | V | V | G | in-progress | `cf794fb` |
| WF-REC-012 | Nested execution and scoped durable results | P0 | Desktop and webapp GUI/runtime | yes | V | G | G | V | V | in-progress | `fd96f8f` |
| WF-REC-013 | Semantic operation-batch atomicity | P1 | Draft operation API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-REC-014 | Containment-cycle rejection | P1 | Workflow API/storage | no | N (this row owns cycle refusal; successful embedding is covered by WF-REC-005 and WF-REC-006) | G | N (cycle insertion is refused atomically before a recovery lifecycle begins) | G | G | gap | `fcb4408` inspection |
| WF-SRC-001 | Explicit identity-bound source update preview/apply | P1 | Desktop API/storage | no | V | V | V | V | V | verified | `d02dea9` |
| WF-SRC-002 | Detach changes provenance only | P1 | Desktop GUI/API | no | G | G | N (atomic synchronous operation; no recovery lifecycle) | G | G | gap | `fcb4408` inspection |
| WF-SRC-003 | Owned-source import materializes editable files | P1 | Desktop API/storage | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-SRC-004 | Captured code and independent imports remain stable | P1 | Desktop runtime/storage | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-SRC-005 | Copy/export captures edited owned sources | P1 | Desktop API/storage | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-SRC-006 | Source-bound metadata and invalid edits | P1 | Desktop API/runtime | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-SRC-007 | Imported and embedded source independence | P1 | Desktop GUI/API/runtime | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-SRC-008 | Import collision rename and naming contract | P1 | Desktop and webapp GUI/API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-SRC-009 | Portable export versus results-bundle distinction | P1 | Desktop and webapp GUI/API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| WF-SRC-010 | Trusted Python materialization and fresh helpers | P1 | Desktop API; denied in webapp | no | G | G | G | G | G | gap | `fcb4408` inspection |

## Runtime and integration obligations

| Stable ID | Feature (inventory row) | Priority | Supported surface | Primary GUI | S | R | F | P | B | Status | Evidence revision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RT-EXE-001 | Run accepted draft and Run Selected boundary | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | G | in-progress | `8908388` |
| RT-EXE-002 | Compilation/storage retry keeps one identity | P1 | Execution API/manager | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-EXE-003 | Second-run refusal and mutation serialization/lock | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `da2ced2` |
| RT-EXE-004 | Real Direct source execution | P0 | Desktop and webapp GUI/runtime | yes | V | V | V | V | V | verified | `4208769`, `9698d5b` |
| RT-EXE-005 | Recursive Direct execution and result attribution | P0 | Desktop and webapp GUI/runtime | yes | V | G | G | V | V | in-progress | `fd96f8f` |
| RT-EXE-006 | Real sequential worker isolation and output files | P0 | Local desktop runtime/integration | yes | V | G | V | V | V | in-progress | `da2ced2`, `4676ffb` |
| RT-EXE-007 | Progress and completion keep one context | P1 | API/WebSocket/GUI | yes | V | G | V | V | V | in-progress | `2c1ff72` |
| RT-EXE-008 | Failure, cancellation, correction, and rerun | P0 | Local desktop GUI/runtime | yes | V | V | V | V | V | verified | `da2ced2`, `4676ffb` |
| RT-EXE-009 | Cache invalidation and selected clear | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `30faeb6`, `fe0cf9d`, `0043397`, `58520b5`; ISSUE-011 resolved |
| RT-EXE-010 | Validation/cache flags match computation | P1 | Runtime/API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-EXE-011 | Output-template filename and signature | P1 | Desktop and webapp GUI/runtime | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-EXE-012 | Latest projection symlink/pointer fallback | P2 | Local filesystem/runtime | no | G | G | G | G | U | gap | `fcb4408` inspection |
| RT-EXE-013 | Exact latest-result read and incomplete-data refusal | P1 | Results API/storage | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-EXE-014 | Latest-results folder export and rollback | P0 | Desktop and webapp GUI/API/storage | yes | V | V | V | V | V | verified | `7ab16e6`, `6ae081d` |
| RT-EXE-015 | Workflow-results bundle pins one run | P0 | Desktop and webapp GUI/API/storage | yes | V | V | V | V | V | verified | `7ab16e6`, `6ae081d` |
| RT-RES-001 | Table filtering, sorting, paging, and CSV identity | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `d1072ce`, `168b487` |
| RT-RES-002 | Merge compatible selections and stack unrelated data | P0 | Desktop and webapp GUI/API | yes | V | V | N (projection selection is synchronous and has no cancellation or recovery lifecycle) | V | V | verified | `c050207`, `7d9de88` |
| RT-RES-003 | Column labels, filters, widths, and ordering | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | G | in-progress | `c050207` |
| RT-RES-004 | Dataset upload partial success and path limits | P1 | Desktop and webapp GUI/API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-RES-005 | Dataset folders, moves, stale delete preview | P1 | Desktop and webapp GUI/API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-RES-006 | Cancel and retry browser upload | P1 | Desktop and webapp GUI/API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-RES-007 | Image identity, conversion, offsets, and browser viewer | P0 | Desktop and webapp GUI/API | yes | V | V | V | V | V | verified | `7ab16e6`, `af1951b`, `bfb6197` |
| RT-RES-008 | Thumbnail placeholder, paths, formats, and GUI display | P1 | Desktop and webapp GUI/API | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-RES-009 | Reveal path and native file dialogs | P2 | Native desktop/manual | no | G | G | G | N (native reveal and chooser actions are ephemeral) | G | gap | `fcb4408` inspection |
| RT-RES-010 | Fiji result resolution and native launch | P2 | Native desktop/manual external app | no | G | G | G | N (launch is ephemeral; settings persistence is GUI-SHL-008) | G | gap | `fcb4408` inspection |
| RT-RES-011 | Napari environment, launch, and reconnect lifecycle | P2 | Native desktop/manual external app | no | U | U | U | U | U | unassessed | `fcb4408` inspection pending |
| RT-XCT-001 | WebSocket subscriptions, reconnect, and backpressure | P1 | Desktop and webapp GUI/WebSocket | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-XCT-002 | Execution-log provenance and global background logs | P1 | Backend/WebSocket/GUI | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-XCT-003 | Contextual error history, Logger, and navigation | P0 | Desktop and webapp GUI/WebSocket | yes | V | V | V | G | V | in-progress | `4676ffb` |
| RT-XCT-004 | Structured HTTP errors and expected-error logging | P1 | REST API/logging | no | G | G | N (request error translation is synchronous and has no cancellation or recovery lifecycle) | N (request-scoped; no persisted user state) | G | gap | `fcb4408` inspection |
| RT-XCT-005 | MCP typed operations and stable interface IDs | P2 | MCP/API/GUI | no | G | G | G | G | G | gap | `fcb4408` inspection |
| RT-XCT-006 | Desktop startup identity, window, and shutdown | P2 | Native desktop/manual | no | G | G | G | N (startup shell has no portable saved state) | G | gap | `fcb4408` inspection |

## Applying later evidence

When a batch lands, update only the affected cells, row status, and evidence revision, then recompute both ratios.
Run `python3 scripts/verify-platform-test-dashboard.py` after every inventory or dashboard edit; `scripts/test check docs` also invokes this verifier before Sphinx.
Do not replace the detailed inventory evidence with dashboard prose.
If one existing row is found to contain separable user actions with different obligations, split it under new stable IDs and retain the old ID as a documented alias; never silently reuse an ID for a different contract.
If a manual or external obligation cannot run, keep it `B` with its recovery procedure in the source inventory or [manual testing guide](manual-testing.md); owner acceptance records a limitation but does not turn it into `V`.
