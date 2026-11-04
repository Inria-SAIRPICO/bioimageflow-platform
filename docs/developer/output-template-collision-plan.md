---
orphan: true
---

# Output template collision implementation plan

Prevent declared processing outputs from overwriting one another, explain how conflicting filenames were produced, and let GUI users correct their workflow templates before restarting execution.
The library reports an actionable error; the platform offers **Cancel execution** or **Update template and continue**.
There is no silent renaming or overwrite option.

This is a proposed implementation, not a description of released behavior.
It covers the BioImageFlow library and the platform's local Direct/Wetlands execution path, including nested workflows and Run Selected.
Managed distributed execution is a separate follow-up: preserve its existing contracts and do not imply that changing a local draft changes an immutable remote submission.

## Agreed user experience

At execution time, stop before dispatching a node whose declared writable output destinations collide or whose template assigns different destinations to rows contributing to one file.
After the run has settled, show the node, conflicting filename, number of affected rows or fields, effective template, and a short breakdown of template parts and their resolved values.
Show representative differing expansions when rows reach the same filename through different values; do not claim all token values are identical unless they are.
Keep large collision sets bounded in the dialog, with accurate totals and expandable examples.

For the reported ATLAS case, use this copy and layout:

> **Output filenames collide**
>
> Six rows in **atlas_detections** produce the same filename: `13432_c0_detections.tif`.
>
> Your template is `{input_image.stem}_detections{ext}`:

| Template part | Resolved value |
| --- | --- |
| `{input_image.stem}` | `13432_c0` |
| `_detections` | Literal text |
| `{ext}` | `.tif` |

> These values are identical across the six rows, so the filename does not distinguish their results.
> Add `{row_index}` or another value that differs between rows.
>
> **Output template**
> `{input_image.stem}_detections_{row_index}{ext}`
>
> Updating the template changes your workflow.
> Continuing restarts execution and reuses available cached results.
> Changed filenames may affect downstream tools that interpret them.
>
> **Cancel execution** · **Update template and continue**

Prefill a simple deterministic suggestion when adding `{row_index}` resolves a collision between rows.
Do not use an AI suggestion service or infer arbitrary filename conventions.
For collisions between keyed file groups, suggest a verified `{group_index}` suffix instead: all rows contributing to one file receive the same group index.
For example, `{label_image.stem}_tracks_{group_index}.tif` distinguishes source-image groups without splitting their contributing rows.
For conflicts between fields within one row, show editable templates for the affected fields and explain that those fields need distinct destinations.
Do not present a row suffix as a verified solution in that case.
When members of one file group request different paths, explain the declared grouping and suggest removing within-group variation; adding a row suffix would make that problem worse.
Preserve recognized compound extensions when constructing a suggestion; if a safe insertion point is not established, keep the original template for manual correction.

Do not implement a live preview in the first version.
On submission, resolve the proposed templates against the captured input rows and keep the dialog open if the collision remains or the template is invalid.
No workflow change occurs until that check succeeds and the ordinary draft edit is accepted.

During editing, show an inline warning beside an affected output template only when the current graph and available exact inputs prove a collision.
Unknown cases remain silent, including the common case where upstream outputs do not exist yet.
Omitting `{row_index}` is not itself a warning condition.
Warnings do not block editing or saving.

Add this short description to the Nodes panel OUTPUTS section for processing tools:

> Each file written by a tool needs its own destination.
> Some tools combine several rows into one file.
> Use the values shown below to distinguish separate files.

Each field also has a read-only description: **One file per input row**, **One file for the whole batch**, or **One file per source image**, using the relevant input display name for keyed groups.
Grouping is declared by the tool author; GUI users edit filename patterns without configuring groups.
Naming bases are labelled **Base name; this tool generates the individual filenames** and do not claim complete collision detection.

## File grouping contract

Keep `RowConsumption.MAPPED` and `RowConsumption.COLLECTIVE` for input independence and returned-record lineage.
They cannot be inferred from the grouping of files or output records: normalizing one scalar per row against the whole-batch mean produces per-row records whose values depend on every input.
Moving that dependency into output annotations would restate the same computation contract.
Do not change DataFrame indices, consumed-row relations, scalar interpretation, mapped explosion, or collective return conventions as part of file grouping.

Add an immutable worker-safe `FileGroup` declaration to each exact writable `Template`:

```python
# ATLAS: one independently written file per input observation.
detections: Path = Template(
    "{input_image.stem}_detections{ext}",
    group=FileGroup.per_row(),
)

# Mosaic: all tiles contribute to one file.
mosaic: Path = Template(
    "{node_name}_mosaic.png",
    group=FileGroup.once(),
)

# TracksToLabels: all tracks for a source contribute to one file.
labels: Path = Template(
    "{label_image.stem}_tracks.tif",
    group=FileGroup.by("label_image"),
)
```

`FileGroup.by(...)` accepts one or more named tool inputs, such as `by("image", "channel")`.
Grouping uses complete admitted typed values, including full paths rather than filename stems, with an explicitly defined scalar/path equality contract.
Do not hash file contents or run callbacks to establish a group.
Initially reject unsupported container keys and ambiguous nonfinite numeric keys rather than inventing equality semantics.

On a mapped tool, an omitted `group` defaults to `per_row()` so ordinary exact-output declarations remain concise.
On a collective tool, each exact `Template` must declare its group.
A `process_row` callback supports only `per_row()` files.
A single whole-node `process_batch` supports all three group forms under either row-consumption mode; shared groups prohibit dispatching independently writing chunks of that batch.
A mapped batch can write independent row results plus a shared constant manifest without acquiring collective scientific lineage solely because the file is shared.
The author remains responsible for correctly declaring any computation that actually depends on all rows as collective.

An intended file owner is `(invocation, output field, group identity)`.
For `per_row()`, the identity is the actual observation position/identity, not its display index string.
For `once()`, there is one potential owner for the invocation.
For `by(...)`, there is one potential owner for each distinct admitted key tuple.
Fields can use different group forms in the same tool, for example per-row prediction images and one batch report.
A destination is reserved as a potential output; its presence in the plan does not require a tool to write a file or return a sentinel row.
Several returned records may legitimately reference the same planned file.

Two invariants define validation:

1. Every member of one owner resolves to the same destination.
2. Different owners, including different output fields, resolve to different destinations within their shared assets namespace.

The first invariant distinguishes an inconsistent grouped template from a collision between independently written files.
Mosaic accepts repeated references to its single destination.
TracksToLabels accepts repeated references within one source group, but rejects distinct source groups that resolve to one filename.

Add `{group_index}` as a filename-safe deterministic ordinal within a field's grouping for the invocation.
For `per_row()`, use admitted observation order; for `by(...)`, use first occurrence in ordered observations followed by previously unseen eligible reference groups; for `once()`, use `0`.
Every member of one group receives the same value.
It is not a permanent source identity and may change when input selection or order changes.
Preserve `{row_index}` semantics; if a row-index suggestion still collides because indices repeat, test a group-index suggestion instead.
Template syntax describes names only; do not embed grouping directives in user-editable patterns or infer ownership from the variables a pattern happens to contain.

Make writable intent explicit:

```python
source_image: Path                         # Returned reference; no implicit destination.
result_image: Path = Template("result_{row_index}.tif") # Exact writable destination.
tile: Path = PathBase("{input_image.stem}_tile.tif")
```

A bare `Path` output becomes a returned path value rather than automatically acquiring a writable template.
Node overrides replace patterns only on declared `Template` or `PathBase` fields; they cannot convert a plain reference into a write destination or alter file grouping.
`Template` means the exact destination the tool receives and may return.
`PathBase` preserves an explicit customizable naming base for existing tools that derive additional filenames, such as tilers, without promising complete pre-write collision detection.
Repeated bases alone neither prove nor disprove a collision among the filenames generated later.
Do not infer exact versus derived output behavior from output record cardinality: many object records can reference one exact image file.

Expose the library's admitted destination groups to batch callbacks through `context.output_files[field]`.
Each immutable planned-file entry carries its resolved path, group index, named key values, and observation/reference positions.
Continue providing applicable resolved paths in row arguments; a `once()` destination is also available in batch arguments.
Do not invent a representative batch destination for a keyed field with several owners.
Migrate TracksToLabels to consume these planned groups rather than independently reimplement the same grouping and destination checks.
Do not reuse the existing public `OutputGroup` name, which already describes returned records and consumed-row associations.

Preserve the selected release's actual local empty-input callback rules; declaring a file does not independently request a callback.
An empty mapped observation set has no per-row owners, while the existing constant-only mapped invocation keeps its configuration row.
For a dispatched collective invocation, `once()` has one potential owner even without observations; `per_row()` has none.
Keyed owners include real selected reference-only sources under the existing auxiliary-input contract, allowing TracksToLabels to render a blank source image with no observed tracks.
Composite reference keys must come from genuinely associated admitted tuples; do not manufacture observation rows or a Cartesian product from separate inputs.
Missing required key values and unresolved input-dependent tokens are explicit planning errors; do not fabricate a source identity for an empty batch.

## Ownership and detection boundaries

The library owns effective template selection, expansion, destination comparison, explanations, and correction checking.
The backend adapts public library diagnostics to typed API models and owns draft/run identity checks.
The frontend renders diagnostics and applies accepted corrections through existing canvas commands and persistence coordination.
It must not parse error strings or implement a second template resolver.

The initial guaranteed check covers all exact `Template` destinations, including defaults and node overrides, across declared file owners in mapped and collective tools sharing an invocation's assets root.
Compare normalized destinations under the library's existing containment and filesystem naming rules; include case equivalence on supported case-insensitive filesystems.
Identical basenames in separate invocation roots are not collisions.
Repeated input paths, bare returned-path references, and DataFrameTool path-valued columns are not writable destinations.
Retain existing path-containment checks and the final no-overwrite guard for unexpectedly occupied paths and competing external writers.
The correction dialog does not authorize overwriting unrelated files.

Implement the three file-group forms in the first version, covering ATLAS, Mosaic and TracksToLabels without a mapped-only limitation.
Group ownership does not introduce output rows, change a collective result's consumed-row relation, or reinterpret scalar fields as global metadata.
Preserve existing manifest-only artifacts and zero-row scalar metadata behavior.
Detect equal declared destinations in the initial scope; directory/descendant overlap is an error only where declared artifact semantics prove incompatible writes.
At result admission, exact-template paths must belong to an admitted owner for that field and applicable row scope; repeated references to the admitted file remain valid.
This is a cooperative execution contract, not a filesystem sandbox for arbitrary Python.
`PathBase` families and undeclared internal writes remain outside the complete prediction guarantee.
A general dynamic output enumerator, exclusive-directory API, and universal safe-writer migration are optional follow-ups rather than prerequisites for this feature.

The current external-command helper detects occupied paths before launching and uses atomic no-replace publication after completion; this is not a general workflow collision checker.
Ordinary direct writers such as `imageio.imwrite` do not universally use that helper.
The new planner therefore checks declared destinations before any affected callback, independently of the writer library.
Do not misclassify an unexpected occupied-path error from a lower-level writer as a proven template collision without matching planned-owner evidence.

Use a single pass over already resolved destinations, with bounded diagnostic examples rather than copying all argument values into API payloads.
Expansion evidence contains only template-referenced values needed to explain the path, not arbitrary tool arguments or credentials.
Preserve exact destination comparison separately from abbreviated display text.

## Source baseline and specification work

The plan-update source baseline is platform revision `dbdae39`; inspect and preserve unrelated working-tree changes when implementation starts.
The backend currently selects published BioImageFlow 0.9.7 and Core 0.5.2.
The sibling `bioimageflow/` link points to older source at `8ba6ef6`; the `bioimageflow-v0.9.6` tag used for the initial design investigation is not the current runtime baseline.
Select the published release lineage or a reviewed descendant before implementing library changes, read that checkout's AGENTS and testing instructions, and verify source/artifact correspondence.
Do not patch installed `.venv` files or use the old sibling working tree as the runtime authority.
Create any task worktrees under their repository's `.worktrees/` and keep dependencies and runtime state separate.

Implementation must update the library specifications for execution, validation, templating, cache compatibility, and errors, plus its public API reference.
Update affected platform v1 execution, Node Panel, error-handling, and API sections; v2 validation, execution, nested-editing, and storage sections; and `PLATFORM_CONTEXT.md` when implementing the corresponding behavior.
Add concise public user guidance for template corrections.
This planning-only task leaves implemented specifications unchanged.

## Phase 1 Define the public library contract

Define and capture `FileGroup`, exact templates, naming bases, the group-index token, and the compact destination-group projection in the public library/Core contract.
Audit every affected first-party processing tool, including inherited declarations, and classify its path outputs as exact destinations, naming bases or returned references before changing the implicit-Path default.
Convert existing implicit writable defaults into explicit `Template` declarations, and migrate actual path-deriving tools to `PathBase` without losing customizable naming.
Declare Mosaic's single file and TracksToLabels' source-keyed files explicitly; do not infer groups from existing patterns.
Inventory saved overrides and pinned package compatibility: provide an actionable incompatible-tool/override diagnostic rather than silently discarding overrides, rebinding package versions, or treating a legacy declaration as newly checked.
Coordinate compatible tool-package releases and demo bindings before platform dependency adoption; retain current user workflow documents and make any needed dependency change explicit.

Introduce a domain-error family with stable codes `output_path_collision` and `output_group_destination_mismatch`, provisionally exposed through `OutputPathCollisionError` and `OutputGroupDestinationMismatchError`.
Reports include scoped node identity, output field identities, group descriptions and keys, effective templates, conflicting relative destinations, total owner/member counts, representative row positions and row-index strings, and template expansion parts.
Missing grouping keys, unsupported key types, invalid declarations and unavailable sources remain tool/input errors rather than automatically opening a filename-correction dialog.
Distinguish a row position from an authored index; do not assume row-index strings are unique or safe filename fragments.
Use the existing resolver to generate ordered literal/token expansion evidence so substitutions retain exactly the same semantics as execution.
Keep complete evidence for selected representative paths and explicitly identify truncated examples.

Provide a public side-effect-free inspection/correction operation that uses the same destination planner.
Prefer stateless reconstruction from the captured graph/bindings and exact immutable input-record/selector references already retained by execution.
When those references are insufficient, use a bounded server-owned snapshot of lightweight scalar/path template inputs with explicit expiry and release ownership.
The evidence must cover eligible variables newly introduced by a custom template, not only tokens in the original template; do not serialize every input row to the browser.
Do not retain worker pools or whole image/SharedArray results merely to keep a dialog usable.
If complete correction checking becomes unavailable, keep the explanation available and offer ordinary template editing and Run; do not label a sample-only check as complete validation.
The normal execution check still protects the restarted run before its affected node writes.
No new correction-session registry, persistent workflow authority or persistent correction journal is required by default.

Specify editing-time inspection as a conservative use of the same public checker.
It may use static facts that prove equal writable destinations or already available inputs selected for the exact current graph.
It must not execute upstream DataFrameTools, scientific callbacks, environment provisioning, or array hydration to decide whether to show a warning.
Changed bindings, source generations or templates invalidate prior evidence; unrelated latest results are not proof.
If these conditions leave row values or cardinality unknown, return no collision warning.

**Exit:** reviewed declaration/migration contract, deterministic owner enumeration, both diagnostic schemas, expansion evidence, correction-evidence lifetime, and a finite set of proven editing-warning cases.

## Phase 2 Enforce the contract in execution and cache selection

Implement one destination planner that captures the effective declarations and timestamp, establishes observation/reference file owners, resolves member destinations with expansion evidence, checks within-owner agreement, then checks collisions across owners.
Integrate it before the affected node's first Direct callback or Wetlands task submission.
Cover constant-bound and column-bound inputs, row and whole-node batch paths under either row-consumption mode, nested scoped nodes, and actual empty/reference-only cases without running callbacks twice.
Reuse the admitted plan in worker contexts rather than grouping or expanding templates again with different values or a new timestamp.
Extend the strict public task/context protocol and worker validation for the destination-group projection; reject malformed or declaration-incompatible groups before scientific callbacks.
Preserve existing record-lineage and result-cardinality validation independently of file ownership.
Raise a structured planning error in the orchestrator and terminalize any owned attempt through the existing failure path.
No partial result or current-selection pointer may be published for the refused node.
Successful upstream records remain usable, and independent concurrent branches settle through the scheduler's existing failure/cleanup behavior before graph mutation is allowed.

Verify old cache compatibility explicitly.
An older successful record may contain several rows referencing the same file because earlier tools silently overwrote it.
Do not let a warm cache hit bypass the new guarantee or relabel those files as repaired results.
Version the processing-output contract and include exact/base/reference roles, ordered grouping keys and effective templates in declaration capture, worker admission and reusable identity.
The version change prevents an old warm record from bypassing checks that previously allowed silent overwrites; do not relabel historical records as validated by the new planner.
Preserve existing records and export/read access; do not mass-delete caches or automatically clear upstream results.
Keep unaffected DataFrame cache eligibility where the identity contract permits, and document any one-time processing-cache misses at adoption.
Template edits already participate in processing identity; confirm changed descendants recompute while causally unchanged valid upstream results can be reused.

**Exit:** ATLAS-equivalent collisions and inconsistent group templates refuse before any affected callback; Mosaic shares one owner correctly; TracksToLabels separates source owners and reference-only groups; corrected templates complete without overwrites.

## Phase 3 Transport diagnostics and apply corrections safely

Extend strict backend execution and validation response models with typed file-planning reports, exact/base/reference output metadata, read-only group descriptions, and nonblocking warning diagnostics where needed.
Adapt the public exceptions at `services/execution.py`, propagate both report kinds through completion events, status snapshots and retained local-run diagnostics, and preserve them across reconnect without treating ordinary failure strings as planning reports.
Review `models/execution.py`, `models/validation.py`, event-bus schemas, `services/execution_runtime.py` local retention, and the corresponding routers together.
Use the existing failed-run lifecycle; do not add a paused worker or change a failed run into a successful run after editing.

Bind any correction check or edit to the captured workspace/workflow generation, root draft revision, run ID, scoped node path, original template values and compiled source/input authority.
Reject stale dialogs after graph edits, workflow replacement, workspace changes, a newer run, or incompatible nested-editor ownership.
Do not silently retarget an inactive canvas or overwrite newer templates.
When browser restart or input-evidence expiry leaves explanation-only information, keep the report readable and withdraw the one-click correction action with ordinary edit-and-run guidance.

After the run's scientific callbacks and submitted tasks have settled and its normal mutation lock is released, check the proposed templates using the library, apply them through ordinary root-draft compare-and-swap, and wait for durable acceptance before starting a new run.
Normal warm application-owned pools may remain available under their existing lifetime contract; correction does not require gratuitous environment or pool retirement.
The edit marks the workflow modified and does not promote it to saved `workflow.json` automatically.
Correction and restart are separate outcomes: if the edit succeeds but restart fails, retain the accepted edit and show the start failure without rolling it back or replaying the submission.
Double clicks, duplicate completion events and reconnect must not apply the correction or start a run twice.
Undo/Redo records the correction as an ordinary graph edit.

For nested failures, update the node inside the accepted root graph's embedded workflow, not its saved-workflow provenance source.
Use existing nested-editor ownership rules; if an open private snapshot conflicts with that edit, explain the conflict and require ordinary reconciliation rather than overwriting private work.
The corrected Run Selected preserves the original requested root targets and dependency closure; a full Run remains full.
Start the new run with ordinary cache reuse, not forced recomputation or deletion of all failed descendants.

Regenerate `frontend/src/api/types.ts` from backend OpenAPI after API model changes.
Keep the existing generated-type authority and avoid new handwritten response copies.

**Exit:** structured errors survive API/event/status paths, stale corrections cannot mutate a workflow, and accepted edits restart exactly once under a new run identity.

## Phase 4 Add the dialog and editing warnings

Add a focused component under `frontend/src/components/execution/` and integrate it with `stores/execution.ts`, accepted canvas commands, and the root-draft persistence barrier.
Reuse the existing failure log/traceback for diagnosis, but present the actionable dialog instead of a competing generic error toast.
Deduplicate presentation by owning run and scoped node; before correction submission, Cancel, Escape and backdrop dismissal leave the workflow unchanged and do not restart execution.
If multiple nodes report collisions, list their reports and allow only explicit edits; a later newly discovered collision uses the same flow without an automatic retry loop.

Render literal/token expansion as escaped text, with representative row labels, accessible input labels, validation messages, keyboard focus containment and focus restoration.
After correction submission, disable both actions and Escape/backdrop dismissal while checking, persisting or starting, and restore controls only when the operation settles.
If checking or persistence refuses, no accepted edit occurred and cancellation remains unchanged; if the edit succeeded but start failed, explicitly report that the template change remains applied.
The initial version has no per-keystroke preview request.
If submission finds remaining collisions or group destination disagreement, update the explanation and retain the user's input without mutating the draft.

Integrate inline proven-collision/group-disagreement warnings, read-only grouping descriptions, and the agreed OUTPUTS description in `components/panels/NodePanel.vue`.
Warnings are separate from blocking graph errors, follow node/scoped-field identities, disappear when their evidence is no longer current, and stay absent for unknown cases.
Use the selected bound tool's metadata and effective default template rather than a same-named catalog tool.
Only exact destinations and declared naming bases receive template editors; returned references do not receive implicit template controls.
Keep naming-base limitations visible without treating unknown generated-file collisions as errors or routine warnings.

**Exit:** users can cancel unchanged or submit a valid custom template, understand its expansion, and continue from the accepted updated draft without automatic Save.

## Phase 5 Validate and adopt the library release

Use ordinary imported processing fixtures with small files; do not use scientific models or downloads for routine coverage.
Follow the selected library checkout's authoritative focused and completion commands and record its exact source/artifact revisions.
Platform adoption must use a published compatible dependency in its manifest and lock, rather than depend on an ignored sibling checkout.
The plan does not authorize publishing packages or modifying the user's actual demo workflow; those actions require their own explicit implementation/release scope.

| Area | Required evidence |
| --- | --- |
| Declarations | Mapped group defaults; explicit collective groups; bare `Path` references; retained implicit-write templates after migration; `PathBase` families; mixed per-row and once outputs; forbidden grouping/role overrides; existing pinned-package and saved-override diagnostics. |
| Destinations | Six mapped rows for one image; two fields within one row; non-unique index strings; distinct paths without `{row_index}`; distinct source paths with equal stems; intentional sharing within one owner; case-equivalent names where applicable; no confusion with read-only references or isolated node roots. |
| Grouping | Full typed scalar/path keys and multiple key fields; unsupported/ambiguous keys; deterministic group indices; inconsistent destinations within one group; real reference-only groups without fabricated tuples; empty batches; one exact file referenced by many returned records. |
| Dispatch | No affected callback/task submission before refusal under Direct or Wetlands; mapped row/batch and collective controls; shared files force one whole-node batch call; admitted worker plan matches controller evidence; unchanged record lineage; corrected small-file fixture completes in an actual Wetlands worker. |
| Explanation | Both diagnostic codes; exact token/literal expansion; defaults and overrides; different token values yielding one final name; row-index versus group-index suggestions; compound extensions; bounded examples and accurate owner/member totals. |
| Cache and lifecycle | Unsafe old warm records cannot evade the new contract version; grouping and exact/base/reference declaration changes affect identity; valid upstream reuse after correction; no failed-node publication; concurrent branch settlement; missing/expired correction context does not advertise full validation. |
| Mutation and restart | Cancel/dismiss unchanged before submission; dismissal disabled during submission; custom correction remains invalid; accepted edit marks draft dirty; persistence refusal prevents restart; start failure preserves edit; duplicate submission; graph/workspace/new-run races; Run Selected and nested ownership. |
| Editing | Proven collisions or group disagreements warn; unique or unknown cases stay silent; warning clears on correction and evidence invalidation; unavailable bound-tool metadata cannot produce a catalog-derived warning; group descriptions are read-only and path references have no template editor. |
| Browser | Clear dialog copy and expansion table; keyboard cancellation; mapped row correction and keyed group correction; rejection of a row suffix that splits one owner; accepted draft, new run ID and actual distinct files; reload recovers diagnostics without reopening a dismissed dialog in a loop. |

During platform implementation, use `scripts/test focus backend ...`, `scripts/test focus unit ...` and exact Chromium E2E selectors for the changed paths.
Add focused coverage near execution-manager/router tests, NodePanel and execution store/component tests, and `frontend/tests/e2e/execution-failure-rerun.spec.ts` or a dedicated collision spec.
Use `scripts/test quick` only at an intermediate coherent increment when development will continue.
At a platform cross-stack implementation milestone run `scripts/test check app`, plus the focused noncritical collision browser scenario if it is not covered by the smoke selection.
Run `scripts/test check cross-browser-smoke` for localized browser compatibility and the exact new scenario in Firefox where appropriate; do not stack broader lanes without a new coverage reason.
Run `scripts/test check docs` for documentation completion.
The final dependency/tool-package adoption changes public output declarations and external compatibility, so validate the actual published cohort with `scripts/test full` under `docs/testing.md`.
That final full lane subsumes the app/product/browser scopes: retain earlier unaffected milestones and do not repeat `check app` or cross-browser smoke immediately before it.
Keep distributed validation explicitly separate; this local feature must not imply remote grouping support or silently change immutable remote submissions.
Report each completion command, result, duration and source revision, including exclusions or externally blocked phases.

## Acceptance criteria

- The reported parameter sweep cannot dispatch six writes to the same declared destination.
- The library explains both collisions between file owners and disagreement within one owner using the node, group description, template, destinations and representative expansions without relying on a worker traceback.
- GUI users can cancel unchanged or explicitly change templates in their workflow and start a new run using valid cached results where available.
- The dialog explains filename-dependent downstream behavior and preserves accepted edits if restart fails.
- Proven editing-time collisions warn; unknown cases stay silent.
- The first implementation includes per-row, once and keyed groups: ATLAS's independent rows, Mosaic's single file, and TracksToLabels' source files, including reference-only groups, receive the same exact-destination guarantee.
- Grouping remains a tool-author declaration independent of `RowConsumption`; workflow users edit ordinary patterns and receive grouping-aware suggestions without configuring ownership.
- Bare paths are references; writable destinations and generated naming bases are explicit; legacy declarations, saved overrides and pinned tool packages receive a coordinated migration rather than silent reinterpretation.
- Naming bases and undeclared internal writes remain outside the complete prediction guarantee; returned records and consumed-row lineage retain their existing semantics.
- No silent rename, overwrite authorization, automatic Save, private-snapshot overwrite, user-data deletion, or change to remote submission semantics is introduced.
- Every affected implemented specification is updated with the implementation, and the published library dependency plus platform checks certify the actual adopted behavior.
