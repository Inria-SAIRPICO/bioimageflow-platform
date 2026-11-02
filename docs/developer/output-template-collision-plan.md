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

At execution time, stop before dispatching a node whose declared writable output destinations collide.
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
For conflicts between fields within one row, show editable templates for the affected fields and explain that those fields need distinct destinations.
Do not present a row suffix as a verified solution in that case.
Preserve recognized compound extensions when constructing a suggestion; if a safe insertion point is not established, keep the original template for manual correction.

Do not implement a live preview in the first version.
On submission, resolve the proposed templates against the captured input rows and keep the dialog open if the collision remains or the template is invalid.
No workflow change occurs until that check succeeds and the ordinary draft edit is accepted.

During editing, show an inline warning beside an affected output template only when the current graph and available exact inputs prove a collision.
Unknown cases remain silent, including the common case where upstream outputs do not exist yet.
Omitting `{row_index}` is not itself a warning condition.
Warnings do not block editing or saving.

Add this short description to the Nodes panel OUTPUTS section for processing tools:

> Output templates should produce a unique path for each result.
> Use `{row_index}` or other distinguishing values to avoid collisions.

## Ownership and detection boundaries

The library owns effective template selection, expansion, destination comparison, explanations, and correction checking.
The backend adapts public library diagnostics to typed API models and owns draft/run identity checks.
The frontend renders diagnostics and applies accepted corrections through existing canvas commands and persistence coordination.
It must not parse error strings or implement a second template resolver.

The initial guaranteed check covers actual declared writable destinations, including output defaults and node overrides, across independent mapped rows and output fields sharing an invocation's assets root.
Compare normalized destinations under the library's existing containment and filesystem naming rules; include case equivalence on supported case-insensitive filesystems.
Identical basenames in separate invocation roots are not collisions.
Repeated input paths, untemplated read-only output aliases, and DataFrameTool path-valued columns are not writable destinations.
Retain existing path-containment checks and the final no-overwrite guard for unexpectedly occupied paths and competing external writers.
The correction dialog does not authorize overwriting unrelated files.

Respect `RowConsumption.MAPPED` versus `RowConsumption.COLLECTIVE`, synthetic empty-batch anchors, and reference-row semantics.
A mapped `process_batch` still represents independent row writes.
Collective tools can write one aggregate file or several files grouped by a source input; row-consumption metadata alone does not identify their independent writers.
For example, Mosaic intentionally shares one destination across rows, while TracksToLabels can write one file per source image, including reference-only sources.
Check collective destinations only when an existing public contract identifies distinct writer groups; otherwise leave them unknown and retain their existing execution safeguards.
Do not deduplicate all collective paths, which would hide collisions between distinct source groups, or reject intentionally shared aggregate paths.
Extending the public grouping contract to cover remaining collective tools is a follow-up, not a new prerequisite for the mapped-write feature.
Detect equal declared destinations in the initial scope; directory/descendant overlap is an error only where declared artifact semantics prove incompatible writes.
Do not claim complete prediction of arbitrary internal file writes or filenames invented by 1-to-N tools.

Use a single pass over already resolved destinations, with bounded diagnostic examples rather than copying all argument values into API payloads.
Expansion evidence contains only template-referenced values needed to explain the path, not arbitrary tool arguments or credentials.
Preserve exact destination comparison separately from abbreviated display text.

## Source baseline and specification work

The platform source baseline is `0db9a8c`, with unrelated working-tree changes that must remain untouched.
The backend selects published BioImageFlow 0.9.6 and Core 0.5.1.
The sibling `bioimageflow/` link currently points to older source at `8ba6ef6`; its `bioimageflow-v0.9.6` tag is available locally.
Select the published release lineage or a reviewed descendant before implementing library changes, read that checkout's AGENTS and testing instructions, and verify source/artifact correspondence.
Do not patch installed `.venv` files or use the old sibling working tree as the runtime authority.
Create any task worktrees under their repository's `.worktrees/` and keep dependencies and runtime state separate.

Implementation must update the library specifications for execution, validation, templating, cache compatibility, and errors, plus its public API reference.
Update affected platform v1 execution, Node Panel, error-handling, and API sections; v2 validation, execution, nested-editing, and storage sections; and `PLATFORM_CONTEXT.md` when implementing the corresponding behavior.
Add concise public user guidance for template corrections.
This planning-only task leaves implemented specifications unchanged.

## Phase 1 Define the public library contract

Introduce a dedicated domain exception, provisionally `OutputPathCollisionError`, with a stable structured report and a self-contained Python error message.
Its report includes scoped node identity, output field identities, effective templates, conflicting relative destinations, total conflict/member counts, representative row positions and row-index strings, and template expansion parts.
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

**Exit:** reviewed report schema, writer-enumeration rules, expansion evidence, context lifetime, and a finite set of proven editing-warning cases.

## Phase 2 Enforce the contract in execution and cache selection

Integrate checking after complete row/batch destination resolution and before the affected node's first Direct callback or Wetlands task submission.
Cover constant-bound and column-bound mapped processing, row and vectorized batch paths, nested scoped nodes, and mapped synthetic empty-batch inputs without running callbacks twice.
Collective controls must retain intentional shared destinations and report no unsupported claim of collision freedom.
Raise the dedicated error in the orchestrator and terminalize the owned attempt through the existing failure path.
No partial result or current-selection pointer may be published for the refused node.
Successful upstream records remain usable, and independent concurrent branches settle through the scheduler's existing failure/cleanup behavior before graph mutation is allowed.

Verify old cache compatibility explicitly.
An older successful record may contain several rows referencing the same file because earlier tools silently overwrote it.
Do not let a warm cache hit bypass the new guarantee or relabel those files as repaired results.
Prefer a documented execution/output contract version change scoped to the affected processing semantics, unless equivalent public validation can safely establish old-record eligibility.
Preserve existing records and export/read access; do not mass-delete caches or automatically clear upstream results.
Template edits already participate in processing identity; confirm changed descendants recompute while causally unchanged valid upstream results can be reused.

**Exit:** a six-row ATLAS-equivalent fixture raises an explained collision before any affected scientific callback, and corrected templates complete without overwrites.

## Phase 3 Transport diagnostics and apply corrections safely

Extend strict backend execution and validation response models with typed collision reports and nonblocking warning diagnostics where needed.
Adapt the public exception at `services/execution.py`, propagate it through completion events, status snapshots and retained local-run diagnostics, and preserve it across reconnect without treating ordinary failure strings as collision reports.
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
If submission finds remaining collisions, update the explanation and retain the user's input without mutating the draft.

Integrate inline proven-collision warnings and the agreed OUTPUTS description in `components/panels/NodePanel.vue`.
Warnings are separate from blocking graph errors, follow node/scoped-field identities, disappear when their evidence is no longer current, and stay absent for unknown cases.
Use the selected bound tool's metadata and effective default template rather than a same-named catalog tool.

**Exit:** users can cancel unchanged or submit a valid custom template, understand its expansion, and continue from the accepted updated draft without automatic Save.

## Phase 5 Validate and adopt the library release

Use ordinary imported processing fixtures with small files; do not use scientific models or downloads for routine coverage.
Follow the selected library checkout's authoritative focused and completion commands and record its exact source/artifact revisions.
Platform adoption must use a published compatible dependency in its manifest and lock, rather than depend on an ignored sibling checkout.
The plan does not authorize publishing packages or modifying the user's actual demo workflow; those actions require their own explicit implementation/release scope.

| Area | Required evidence |
| --- | --- |
| Destinations | Six mapped rows for one image; two fields within one row; non-unique index strings; distinct paths without `{row_index}`; case-equivalent names where applicable; no confusion with shared read-only references or isolated node roots. |
| Dispatch | No affected callback/task submission before refusal under Direct or Wetlands; mapped row and batch controls; collective shared-output and grouped-source controls without false collision claims; empty-batch controls; a corrected small-file fixture actually completes in a Wetlands worker. |
| Explanation | Exact token/literal expansion, defaults and overrides, different token values yielding one final name, compound extensions, bounded examples and accurate totals. |
| Cache and lifecycle | Unsafe old warm records cannot evade enforcement; upstream reuse after correction; no failed-node publication; concurrent branch settlement; missing/expired correction context does not advertise full validation. |
| Mutation and restart | Cancel/dismiss unchanged before submission; dismissal disabled during submission; custom correction remains invalid; accepted edit marks draft dirty; persistence refusal prevents restart; start failure preserves edit; duplicate submission; graph/workspace/new-run races; Run Selected and nested ownership. |
| Editing | A proven collision warns; unique or unknown cases stay silent; warning clears on correction and evidence invalidation; unavailable bound-tool metadata cannot produce a catalog-derived warning. |
| Browser | Clear dialog copy and expansion table; keyboard cancellation; successful correction, accepted draft, new run ID and actual distinct files; reload recovers diagnostics without reopening an already dismissed dialog in a loop. |

During platform implementation, use `scripts/test focus backend ...`, `scripts/test focus unit ...` and exact Chromium E2E selectors for the changed paths.
Add focused coverage near execution-manager/router tests, NodePanel and execution store/component tests, and `frontend/tests/e2e/execution-failure-rerun.spec.ts` or a dedicated collision spec.
Use `scripts/test quick` only at an intermediate coherent increment when development will continue.
At cross-stack completion run `scripts/test check app`, plus the focused noncritical collision browser scenario if it is not covered by the smoke selection.
Run `scripts/test check cross-browser-smoke` for localized browser compatibility and the exact new scenario in Firefox where appropriate; do not stack broader lanes without a new coverage reason.
Run `scripts/test check docs` for documentation completion.
Run the full lane only if the selected release/adoption's package-loading or external-compatibility changes require it under `docs/testing.md`; keep distributed validation explicitly separate.
Report each completion command, result, duration and source revision, including exclusions or externally blocked phases.

## Acceptance criteria

- The reported parameter sweep cannot dispatch six writes to the same declared destination.
- The library error explains the node, template, conflicting destinations and representative expansions without relying on a worker traceback.
- GUI users can cancel unchanged or explicitly change templates in their workflow and start a new run using valid cached results where available.
- The dialog explains filename-dependent downstream behavior and preserves accepted edits if restart fails.
- Proven editing-time collisions warn; unknown cases stay silent.
- Independent mapped writes are covered; collective tools without an explicit writer-group contract remain outside the complete detection guarantee and must not gain false warnings.
- No silent rename, overwrite authorization, automatic Save, private-snapshot overwrite, user-data deletion, or change to remote submission semantics is introduced.
- Every affected implemented specification is updated with the implementation, and the published library dependency plus platform checks certify the actual adopted behavior.
