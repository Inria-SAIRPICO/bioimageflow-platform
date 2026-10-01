---
orphan: true
---

# Architecture and test reconnaissance — 2026-10-01

The earlier bounded pass completed selective reconnaissance only; **M1 agreed-scope whole-codebase review is COMPLETE**; the final closure below supersedes the dated partial checkpoints.
The initial synthesis and diagnoses below are preserved as partial historical findings, not a completed whole-codebase review.
The [campaign plan](platform-test-plan.md#reconnaissance-gate-architecture-and-tests-together) defines the gate and [checkpoint](platform-test-progress.md) owns the executing queue.
The [per-file ledger](platform-test-file-review.tsv) records exact inventory revisions, subsystem ownership and inspected depths.
The early selective depth/denominator paragraphs below are historical; the complete-review status, individual current input hashes and later source/control checkpoints govern current completeness.
Reviewed now means full human input plus its recorded caller/oracle judgment; classified means an explicit generated/asset producer boundary, not human implementation review.

## Source and inspection limits

Product source is integrated application `2290c67`; inspected main began at `d8bc910` and the campaign-only revision is `2b945ccc8198258710d516658ea48a24e5150d81`.
Editable library/Core is clean `dff04e3eb7c15ded7984aa6b0befa44febe4cb37`; installed Wetlands 2.4.2 is runtime authority and checkout `874febd999d9c1984c96570912e1ce43962ff4c2` is source context.
The three inspected Wetlands lifecycle/provisioning implementation files are byte-equivalent between installation and checkout.
I1/T1 remain isolated and uncommitted; their earlier test results do not become new M1 results.

| Source | Tracked inventory | Scoped files inspected | Remaining inventory-only or classified |
| --- | ---: | ---: | ---: |
| Platform | 738 | 107: 48 read, 32 traced, 27 deep | 631 |
| Library/Core | 909 | 37: 11 read, 20 traced, 6 deep | 872 |
| Wetlands checkout | 118 | 5 traced | 113 |

Three installed-Wetlands seams and three T1-WIP seams are recorded separately from those denominators.
Overlapping reviewers are counted once; filename-based routing was corrected for suite/CI/configuration and dataset/settings/deployment ownership.
Much of editing/editor code, broad library/Core internals, scientific tool packages and MCP/REST/WebSocket families remains inventory-only or only partly traced.
The ledger covers all tracked paths at the named baseline; generated files/assets/excluded execution families remain explicit entries rather than omitted safety claims.
Further review now covers every human-written source, test, script/configuration and specification, with generated/asset classifications justified through actual producers/consumers.
Earlier scoped depths remain historical; a separate complete-review status starts pending, and this pass is not an exhaustive source audit.

## Authorities to preserve

| Boundary | Authority and meaningful tests |
| --- | --- |
| Editable workflow | Canonical recursive GraphState, canvas-local queues, backend CAS draft, separate saved artifact and private snapshot; response suppression and durable-write refusal are different oracles |
| Bound tool/source | Carried package/module/version or destination-owned source, public library materialization and resource semantics; global catalog is discovery rather than a replacement binding |
| Execution/environment | Platform admission/physical completion, library wrapper recipes/caches and exact injected manager, public Wetlands ownership/generations; a selected engine name does not prove worker execution |
| Results/scientific data | Immutable record/provenance and public asset/transport APIs; per-request resolution, viewer-session identity and runtime representation crossing are separate contracts |
| Settings/datasets | Process deployment policy, JSON preferences, separate credential authority, contained physical bytes and revisioned SQLite catalog; filesystem visibility and catalog publication must agree |
| Test architecture | Proportionate existing lanes, strict scope collections, isolated runtimes and library ownership selections; component, persistence, public-loader, GUI and real-worker oracles are not interchangeable |

No general rewrite or universal async coordinator is justified by this pass.
Preserve graph/CAS/identity/source/result/deployment contracts and delivered out-of-scope distributed implementations/tests.

## Reviewed findings and next packets

Priorities distinguish an executed defect from a source mismatch or hypothesis; static review alone closes no obligation.

| ID / priority | Finding and current evidence | Owner / decision |
| --- | --- | --- |
| B1 / P1 | Actual T1 provisioning red: matching force-Recreate reuses its generation. Wetlands provisioning is idempotent; public removal then provisioning can force replacement but is destructive and not compound generation CAS/rollback. | B develops a reviewed public library-wrapper plan on the same injected owner, with strict close/removal failure, preflight, progress, selected failure/retry and unchanged normal reuse/E1 stale semantics; no private deletion or recipe nonce. |
| A1 / P1 | Source mismatch: translation prefers live catalog identity over a portable node's carried binding. Resource/engine classification also consults same-name catalog classes; an existing recursive rebind test supplies binding fields after translation and misses the seam. | A diagnoses root/nested preservation and actual bound-class/resource/engine consumers before a coherent authority repair; explicit rebind remains the version-changing operation. |
| C3 / P1 | Source interleaving: streamed bytes use a recognizable final name, so a second store can reconcile a partial upload as legacy and conflict with final insertion. | Root diagnoses paused stream/list, then real HTTP disk-spooled reachability; independently review staged publication, cross-instance catalog serialization, no-overwrite, cancellation/folder/refusal and crash ordering before code. |
| C1 / P1 next | Source rollback loss: failed settings/keyring writes delete successfully overwritten keys instead of restoring their previous credentials. Existing tests begin with empty keys. | Root diagnoses populated-key rollback using the injectable protocol; capture distinct preimages, preserve original failure and report secret-free restoration failures without claiming a transactional OS keyring. |
| C2 / P1 next | Source alternate write path: generic settings can change webapp `workspaces_root` when effective roots come from settings, while direct workspace mutation is forbidden. Explicit configured roots mask the path. | Root diagnoses settings-derived versus explicit-config webapp roots and desktop controls; enforce current deployment policy without introducing future-v3 auth. |
| A2 / P1 next | Draft/save caller incarnation is absent before admission; revision zero can recur after same-ID recreation. Existing generation rechecks during validation and client late-response suppression do not distinguish this old-caller entry. | Dedicated identity contract/storage diagnosis and plan; retain during-validation CAS/generation/hash checks and consume generated draft types when that contract changes. |
| A/B lifetime / P1–P2 diagnosis | Raw task cancellation can release graph-worker/run/refresh/thumbnail ownership before physical completion; T1 proves one manual route case, while adjacent paths remain unexecuted hypotheses. | Choose one shared held-thread graph-worker diagnostic first; distinguish supported cooperative Stop from raw task/host teardown before any common change. |

Additional ranked diagnostics remain open: unpinned viewer-session image requests, empty-cache Clear versus fresh status, library runtime image adapters, TIFF axis fidelity/conversion concurrency, SharedArray reclamation, public single-file source containment, cross-workspace recovery namespace and global import/source-preview races.
They require their own accepted oracle/lifetime contract, not speculative fixes or repeated mocked GUI success tests.
Known original-filename fidelity and missing Napari default-recipe debts remain; the upload concurrency packet does not silently absorb those requirements.

## Test cost, redundancy and specification decisions

Retained E1 timing gives backend pytest 165 s / phase 183 s, frontend units 26 s and app completion 268 s; its longest backend case is 5.63 s.
There is no measured global before/after speedup or suite-wide duplicate removal.
Cold/warm setup, collection/fixture costs and comparable optimization measurements remain missing; gather them only for a concrete decision rather than rerunning broad lanes for statistics.
Retain layers with different contract/entry/oracle/failure behavior; extend missing distinctions in existing tests before adding copies.
The SettingsPanel test claiming section event forwarding calls the store directly, so its title/oracle needs correction.
The manual-QA real archive/compile/compute case remains a small integration-marker candidate (retained call 1.19 s), not a demonstrated major performance gain.
Local zero-retry Playwright plus first-retry-only tracing lacks a first-attempt failure trace; use retained traces in focused ordering diagnosis and preserve artifacts before cleanup/pytest retention.
The library already has `tests/ownership.toml` and documented test tiers; no additional runner framework is justified.

Keep normative requirements in their product-owned specification and context as navigation; shorten repeated narratives without removing essential features or explicit debts.
Update every affected specification/context with actual repairs, consolidate ordinary campaign records, and perform low-frequency retrospectives at consequential integrations.
Desktop execution remains final M5; no static/headless/injected-store result supplies native acceptance.

## Complete-review checkpoint

The refreshed source ledger has 1,798 entries: 740 platform, 909 library, 118 Wetlands checkout, three installed-Wetlands seams and 28 held task files.
Assignments and source hashes are recorded separately from actual completed reviews.
All entries begin pending; batch reports must establish full-content review plus relevant caller/test reasoning or a specific justified classification.
The [findings register](platform-code-review-findings.md) records every identified future action, including uncertainty, test-suite and specification candidates.
Review batches do not execute tests or implement fixes.
The gate remains open until pending/unmatched/hash-mismatched human-written inputs are zero, classification exclusions are reconciled, findings are synthesized and independent completeness review accepts the evidence.
No completion deadline or representative sample alone closes this gate.

First accepted complete-file checkpoints: A batch 1 reviewed 20 platform files; root batches 1–2 reviewed 37 additional platform files plus two held dataset test files.
That is 59 reviewed entries / 1,798 baseline entries, zero accepted classifications, and 1,739 pending entries.
The original selective depth counts above remain historical and are not added to these complete-review counts.
Forty-two identified candidates (A-F001–012 and ROOT-F001–030) are recorded with uncertainty and future actions; dependent consumer reviews remain pending where explicitly stated.
The current codebase review is far from complete and releases no repairs or campaign execution.

B batch 1 adds 19 complete context/library/Wetlands files; shared-infrastructure batch 1 adds 25 reviewed files and one producer-justified lockfile classification.
The checkpoint now contains 104 complete entries (103 reviewed / one classified) and 1,694 pending baseline entries; no domain is globally certified.
The register contains 65 identified candidates, with source defect, runtime red, risk, design and maintenance distinctions retained.
Five test counterpart assignments were corrected to their subsystem reviewers; reassignment itself supplies no complete-review credit.

The newly authored findings register is a separate pending current-document input beyond the frozen baseline: that checkpoint was 1,799 entries, 104 complete and 1,695 pending.
A batches 2–3 add 17 full-content files (11 platform and six library); current total is 1,799 entries, 121 complete (120 reviewed / one classified) and 1,678 pending.
The register now contains 86 identified candidates; public-loader corroboration strengthens the source-envelope and SyntaxError findings while public/platform containment boundaries and unreviewed owners remain explicitly distinguished.

### Complete-review source checkpoint: 197 entries

B batch 2 adds 28 complete main/held inputs, A batch 4 adds four public-library inputs, root batch 3 adds 17 scientific implementation/test inputs and shared-infrastructure batch 2 adds 27 release/package/configuration/test inputs.
Every accepted new hash matched its assigned source; held main/WIP versions remain separate inputs.
Current scope is 1,799 entries / 197 complete (196 reviewed / one classified) / 1,602 pending, with 116 identified findings recorded.
Owners have completed A 41/334, B 47/539, root 56/533 and shared reviewer 53/393; these are review judgments, not passing tests or domain certification.
M1 remains OPEN; unreviewed files, cross-owner conclusions, current control-document hashes and independent final completeness acceptance still prevent release of repairs or campaign testing.

### Complete-review source checkpoint: 222 entries

A batch 5 adds six callable/command/session implementation and test inputs, root batch 4 adds eleven complete scientific I/O inputs and B batch 3 adds eight local execution/result implementation and test inputs.
Every new completed hash matches its assigned source.
Current scope is 1,799 inputs / 222 complete (221 reviewed / one classified) / 1,577 pending, with 133 findings recorded.
The pending recovery coordinator test was explicitly reassigned to its complete session-source reviewer to avoid repeated review; reassignment grants no credit.
Owner progress is A 47/335, B 55/539, root 67/532 and shared reviewer 53/393.
M1 remains OPEN, with repairs and application tests held; independent final completeness review and remaining source/specification work are unrun.

### Complete-review source checkpoint: 374 entries

A batches 6–8 add 36 complete graph/persistence/recovery/workflow-store and counterpart inputs, B batches 4–6 add 27 retained-execution/preflight/result/viewer inputs, root batch 5 adds fourteen Core/worker-preflight/external-command and counterpart inputs, and reviewer batches 3–5 add 75 complete collection/reference/package-documentation inputs.
Every accepted input's current hash matches its assigned source; the new judgments include retained protections and uncertainty rather than requiring every finding to become a fix.
Current scope is 1,799 inputs / 374 complete (373 reviewed / one classified) / 1,425 pending, with 206 findings recorded.
Owner progress is A 83/339, B 82/ 541, root 81/522 and shared reviewer 128/397.
Four campaign-collection counterparts, ten engine/frontend helper inputs and three MCP source inputs were explicitly reassigned to their subsystem reviewers; reassignment itself grants no review credit.
Full workflow-store callers materially mitigate A-F053: the retained nested acceptance callback targets the shared session store, so the proposed old-mounted-canvas effect is unproved and observer changes are conditional debt.
The existing planning/cache reference target is confirmed; reviewer-F026 concerns converter/kind drift, not a missing page.
Default node serialization loses infinity/missing-value distinction through JSON null on the inspected dependency baseline; B-F043 does not claim JSONResponse failure or invalidate scientific infinite PSNR.
M1 remains OPEN: 1,425 inputs, current control-document reconciliation, cross-owner synthesis and independent final completeness acceptance remain pending.
Repairs, new diagnostic tests and all application/browser/worker/external/native phases remain held; native desktop acceptance remains final M5.

### Complete-review source checkpoint: 501 entries

A batches 9–10 add twelve complete nested persistence/recovery/codec and counterpart inputs; B batch 7 adds thirteen full public runtime/engine/Fiji inputs; root batches 6–7 add twenty-one complete MCP/common-tool and counterpart inputs.
Reviewer batches 6–8 add 28 complete human IO/phasor/tracking guides and 53 individually justified generated wrappers; the orchestrator also inspected every classified wrapper's complete content and explicit include/navigation source authority.
Current scope is 1,799 inputs / 501 complete (447 reviewed / 54 classified) / 1,298 pending, with 229 findings recorded.
Owner progress is A 95/338, B95/ 548, root 102/517 and shared reviewer 209/396; helper/engine/test/API ownership transfers grant no incidental review credit.
The public Workflow.plan cycle exception is confirmed consistent; reviewer-F026 remains only catalogue/converter drift.
Root's MCP trace corroborates A-F020 global named-draft context publication; ROOT-F048 separately records incompatible argument/recommendation examples.
ROOT-F050–F052 are qualified image-layout, merged-schema and external table/cache ownership decisions, preserving documented features rather than treating every uncertainty as a confirmed runtime defect.
The full human specifications, remaining source/test suites, current control-document reconciliation, cross-owner synthesis and independent final completeness review remain pending.
M1 remains OPEN; no repair, diagnostic test, application/browser/worker/external/native execution is released by these review counts or generated classifications.

### Complete-review source checkpoint: 705 entries

A batches 11–14 add fourteen complete workflow-store, generation/migration/demo, CanvasView, App and Save-helper inputs; B batches 8–9 add 52 complete execution-identity/storage/publication and counterpart inputs.
Reviewer batches 9–16 add 92 complete human package/authoring/platform/remote guides and 46 individually justified generated navigation wrappers.
The orchestrator read the complete reports and every new wrapper's full content; all accepted source hashes match the assigned manifest, and borrowed excerpts or complete context without an owned judgment grant no duplicate credit.
Current scope is 1,799 inputs / 705 complete (605 reviewed / 100 classified) / 1,094 pending, with 269 findings recorded.
Owner progress is A 109/338, B 147/465, root 102/600 and shared reviewer 347/396.
The 23 pending storage implementation/test inputs were formally transferred from root to B, and the 106 pending Wetlands checkout inputs from B to root; transfer itself grants no credit.
The source findings include exact mixed-numeric dataframe identity and final no-replace export admission risks, incomplete enclosing-interface grouping, migration validation authority, asynchronous clipboard admission and nonstartup shell lifetime ownership.
These are static findings with their documented mitigations and future discriminating selectors, not newly executed failures.
B-F068 requires pointer invalidation/reselection without documented coordination; ordinary first-winner publication does not prove a default supported Run race.
A-F091 is conditional two-endpoint callback debt: ordinary one-endpoint cross-region gestures are refused.
The full App review further narrows A-F088: ordinary Open activates an existing root rather than replacing its graph, and supplies no explanation of historical ISSUE022.
ROOT-F050 and ROOT-F052 source citations were corrected to Mosaic's actual initial-frame read and WriteTable's actual transform; their qualified behavior/contract findings are unchanged.
The current authoring examples' missing concrete-class declarations/output constructor and stale implemented-tool claims are recorded without weakening essential behavior or implementing roadmap proposals.
M1 remains OPEN: remaining source/tests/specifications, current control-document reconciliation, cross-owner synthesis and independent final completeness acceptance are pending.
Repairs, new diagnostic tests and every application/browser/worker/external/native execution phase remain held; native acceptance remains final M5.

### Complete-review source checkpoint: 913 entries

A batches 15–20 complete 65 additional editor, clipboard, recursive graph, library example/manifest and counterpart inputs; B batches 10–13 complete 76 additional remote submission, launcher/control, typed-return and Core/shared-memory inputs.
Root batches 8–10 complete 49 Wetlands lifetime/protocol/codec, native-entrypoint source, selected-node presentation and complete counterpart inputs.
Reviewer batches 17–21 complete 12 additional human specifications/guides/producers and six individually justified artifact classifications.
The orchestrator fully read the new reports, reconciled named contract disagreements and verified current hashes before accepting distinct owned judgments; borrowed context and ownership transfer grant no duplicate credit.
Current scope is 1,799 inputs / 913 complete (807 reviewed / 106 classified) / 886 pending, with 348 identified findings recorded.
Owner progress is A 174/347, B 223/490, root 151/565 and shared reviewer 365/397.
Four editor implementations and two corresponding tests were transferred to A, the desktop entrypoint to root, the 750-line preview producer to the reviewer, 31 pending Parsl source/counterpart inputs to B and three pending resource/viewer/origin tests to A.
HPC runtime exclusion does not exclude static Parsl engine/future lifetime review; desktop source review performs no native acceptance action, which remains final M5.
The backlog now distinguishes configured-webapp editor guards from mutable-settings policy, physical cancellation acknowledgment from retained cleanup ownership, native destruction retry from harmless already-absent close, and possible live-output EOF/group-identity interleavings from executed failures.
The earlier library Python-floor claims were explicitly withdrawn: Core supports Python >=3.9 and the library >=3.10; the retained platform prerequisite finding is separate.
Type partial-overlap compatibility is explicitly tested existing behavior, and available plain-string schema derives known/viewer=None; neither is reclassified as a confirmed compatibility defect.
Example factory checks establish structural/public-load validity, not declarative quantitative scientific acceptance, while current static previews are illustrations and their precise producer/caption correspondence remains pending.
Test-suite improvements are recorded against actual oracles: unreached failure branches, manually replicated subscriber logic, file-handler/child fixture lifetime and timing coordination; no deletion, new diagnostic test or measured speed gain is claimed.
Full remaining source/tests/specification review, current mutable-control reconciliation, cross-owner synthesis and independent final completeness acceptance remain pending.
M1 remains OPEN; repairs, new diagnostic tests and all application/backend/frontend/browser/worker/external/native execution remain held.

### Complete-review source checkpoint: 1,034 entries

A batches 21–23 complete 22 additional loading, inspection, public registry/session, GUI guidance and counterpart inputs; B batches 14–16 complete 38 additional Parsl, managed-factory, retry and counterpart inputs.
Root batches 11–12 complete nineteen Wetlands provisioning/runtime-registry and scientific wrapper/counterpart inputs; reviewer batches 22–25 complete 21 human inputs and 21 individually justified asset/lock/link classifications.
Every newly accepted owned source hash was checked against actual bytes, and all new reports were read in full before integration.
Current scope is 1,799 inputs / 1,034 complete snapshot judgments (907 reviewed / 127 classified) / 765 pending, with 392 distinct identified findings.
Owner progress is A 196/353, B 261/490, root 170/504 and shared reviewer 407/452.
Fifty-five remaining Wetlands configuration, documentation, CLI/debug/diagnostic, release and counterpart inputs were transferred to the shared reviewer; loader and source/session counterparts were transferred to A.
Transfers supply no review credit, and the library specs.md link classification supplies no human target credit: its complete human target belongs to B and remains pending at this checkpoint.
Canonical finding headers were reconciled so the A-F026 and A-F117 extensions do not inflate the distinct count.
The review distinguishes physical cleanup acknowledgments, malformed registry diagnostics and postinstall lock fidelity from actual new runtime failures; scientific wrapper argument mocks do not certify each external dimensional mode.
Public-loader cache and dependency lifetime, incremental Session wire/cache authority, retry-after-publication replay and concurrent dispatch ownership retain their specific mitigations and future distinguishing diagnostics.
The managed-factory trace corroborates reviewer-F040: the current public route refuses ordinary common-tool recipes at exact runtime attestation, rather than demonstrating execution in a wrong worker.
Five mutable campaign controls were fully reviewed against exact current snapshots; changed administrative deltas still require reopening before final acceptance, and stale historical J1/J3 wording is recorded as reviewer-F052 without releasing repairs.
All remaining human source, tests and specifications, current mutable-control and generated-ledger provenance reconciliation, cross-owner synthesis and independent completeness acceptance remain pending.
M1 remains OPEN; repairs, new diagnostic tests and application/backend/frontend/browser/worker/external/published-compatibility/native execution remain held.
Native desktop acceptance remains final M5.

### Complete-review source checkpoint: 1,189 entries

A batches 24–26 add 42 fully reviewed library contract/example/counterpart inputs and seven exact producer-linked wrapper classifications; B batches 17–19 add thirty fully reviewed specification/protocol/validation/counterpart inputs.
Root batches 13–15 add 37 fully reviewed segmentation/tracking/spot runtime/helper and complete numerical/model/worker/mock counterparts; reviewer batches 26–29 add 35 human Wetlands source/tutorial/release-test inputs and four individually justified artifact classifications.
Current scope is 1,799 inputs / 1,189 complete snapshot judgments (1,051 reviewed / 138 classified) / 610 pending, with 426 distinct findings.
Owner progress is A 245/353, B 291/489, root 207/462 and shared reviewer 446/495.
The public cluster source and its 43 root-owned pending counterparts were transferred cohesively to the reviewer; two complete Wetlands protocol counterparts went to B, and the segmentation execution counterpart plus two scientific helper sources went to root.
Ownership transfer itself grants no credit, and all newly accepted source hashes matched actual current bytes.
The complete 3,314-line human library specification is now B-reviewed; the navigational specs.md alias adds no second human body credit.
A's entire assigned library slice and the reviewer's newly transferred Wetlands slice are individually complete, while other library/platform/current-control and held-WIP inputs remain pending; neither subtotal closes the global audit.
Complete scientific counterparts preserve useful sparse-ID, numerical assignment/motion/plateau, empty immutable artifact, cache/readback and distinct mock/actual-runtime oracles.
New scientific findings qualify local-model digest versus reused model ownership, singleton spatial-axis extraction, root versus immediate-image grouping, empty rendering admission and unbalanced assignment matrix costs; no model/binary execution or measured optimization occurred.
The whole specification narrows B-F067: captured custom-source hashes already participate through tool version, so its earlier blanket exclusion was withdrawn in the canonical finding; the remaining equal-version different-origin/output-contract risk is explicit.
Current public authoring grammar, constructor storage scope, inherited image metadata and typed shared-memory task serialization were reconciled against actual consumers without treating a surviving partial plan as permission for invalid execution.
Wetlands suite review identifies existing transport oracles omitted from automatic CI and bounded-versus-total debugger deadlines; the real-Pixi chain's distinct lifetime/oracle/setup amortization remains valuable and unrun.
The review keeps future repairs, diagnostic selectors, documentation reconciliation and unmeasured performance candidates separate from accepted runtime evidence.
All remaining platform/library/cluster/installed-runtime/held-WIP inputs, current mutable-control and generated-ledger provenance reconciliation, cross-owner synthesis and independent completeness acceptance remain pending.
M1 remains OPEN; every repair, new diagnostic test and application/backend/frontend/browser/worker/external/published-compatibility/native execution phase remains held.
Native desktop acceptance stays final M5.

### Complete-review source checkpoint: 1,292 entries

A batches 27–29 add fifteen complete human platform inputs and one explicitly producer-linked generated API classification; B batches 20–24 add forty-three complete platform/library implementation, test and human-contract inputs.
Root batch16 adds twenty-six complete public authoring/runtime/Core-dependency/path/template/logging source and exact counterpart inputs; reviewer batches30–33 add eighteen complete public cluster value/protocol/preparation/deployment source and counterpart inputs.
Current scope is 1,799 inputs / 1,292 complete snapshot judgments (1,153 reviewed / 139 classified) / 507 pending, with 463 distinct findings.
Owner progress is A 261/353, B 334/492, root 233/459 and shared reviewer 464/495.
Three already completely borrowed query/output-view counterparts were formally transferred from root to B before their pending per-file judgment; ownership transfer itself adds no credit.
All accepted input bytes match their exact owned manifests; no inventory scan or partial source excerpt is counted as a complete human review.
The registry/watcher/UI review identifies stale snapshot/lifetime/admission/display seams while preserving real exact-byte reload and rollback tests; generated API ownership is explicitly classified without claiming regenerated schema equality.
Public authoring review records global automatic-name reset, positional rejected-invocation mutation, Core extras/channel identity classification and genuine DataFrame duplicate-suffix column loss; actual Direct path/template/plan and logging ownership oracles are preserved.
Runtime cache suite and full storage/contracts were reconciled: durable SharedArray assets and Direct cache tests remain essential, while zero-copy/general transport claims and external typed task codec certification stay qualified.
Cluster review records pre-coercion public input refusal, source-open boundedness, cleanup retry ownership and declared project-root capture risks; later refusal, exact confirmation digests and trusted-local limitations remain explicit.
All remaining human source/tests/specs, assets/gitlinks/installed-runtime/held-WIP inputs, current mutable controls and generated-ledger producer provenance, cross-owner synthesis and independent completeness acceptance remain pending.
The finding count includes qualified source risks, documentation/test-oracle discrepancies and unmeasured maintenance/performance candidates; it is not a count of executed failures or approved repairs.
M1 remains OPEN; repairs, new diagnostic tests and application/backend/frontend/browser/worker/external/published-compatibility/native acceptance remain held and unrun.
Native desktop acceptance remains final M5.

### Complete-review source checkpoint: 1,550 entries

Since the1,292-input checkpoint, accepted additions are A65 human, B35 human, root55 human plus5 individual artifact/pointer classifications, and reviewer98 human inputs.
These encompass A batches30–38, B25–30, root17–19 and reviewer34–41.
Current scope is1,799 inputs / 1,550 complete snapshot judgments (1,406 reviewed / 144 classified) / 249 pending, with532 distinct findings.
Owner progress is A 326/354, B 369/493, root 293/365, reviewer 562/587.
Pending coherent UI/utilities/error/WebSocket counterparts and installer/preference tests were formally reassigned before individual review; ownership transfer itself grants no credit.
Complete public runtime/cache/integration and worker/cluster counterpart review distinguishes seeded records, mocked transport and actual Direct execution test bodies without claiming fresh passes.
The unused IndexedDB helper is separated from current recovery storage, and active ImageCell clipboard handling is traced through the real hidden-action PathCell consumer.
Ordinary same-app workspace mutation serialization narrows B-F157/B-F159/B-F161; internal callbacks, draft bypasses and independent writers retain separately qualified concerns.
Source-established uninstall target escape, Tree key collision and demo-removal identity discard join the held backlog; no destructive diagnostic or repair occurred.
The signing pointer hash explicitly addresses its canonical tracked gitlink descriptor, not private signing contents; each visual artifact has an individual producer/consumer qualification with no native rendering claim.
Frozen I1 source review preserves its captured recipe/provenance improvements and distinguishes constructed archive/runtime test bodies from untouched roundtrip or published/native certification.
Documentation/test process findings concern existing selectors and assertion fidelity; no coverage removal or measured speedup is claimed.
All remaining human inputs, current mutable controls and generated-ledger/self-hash provenance, cross-owner synthesis and independent completeness acceptance remain pending.
M1 remains OPEN: repairs, new diagnostic tests and application/backend/frontend/browser/worker/external/published-compatibility/native acceptance remain held and unrun.
Native desktop acceptance remains final M5.

### Complete-review source checkpoint: 1,702 entries

Since the1,550-input checkpoint, individually accepted additions are A20 human, B41 human, root72 human and reviewer19 human inputs.
These encompass A39–46, B31–36, root20–27 and reviewer42–46; reports were read fully before exact-hash integration.
Current scope is1,799 inputs /1,702 complete snapshot judgments (1,558 reviewed /144 classified) /97 pending, with558 distinct identified findings.
Owner progress is A346/354, B410/463, root365/365, reviewer581/617.
The30 pending backend model/service/router sources were formally transferred from B to reviewer; transfer grants no review credit.
Root's frozen owned slice is complete, while the whole review remains open for the other owners, current mutable controls, synthesis and independent completeness gate.
Actual browser source review preserves accepted-draft CAS, real Direct rows, owned recursive source bytes, immutable record quarantine and distinct gesture-to-storage oracles.
Mock execution202, injected diagnostic/progress state, fabricated development metadata and absent navigation assertions remain explicitly qualified rather than accepted as worker/native evidence.
The moved-position Redo oracle gap does not imply globally missing Redo coverage: existing everyday tests assert actual accepted mixed edits, enabled state and atomic deletion through Redo.
Current and held viewer/specification review distinguishes carried authority and managed guidance ownership from ordinary Save's missing requirement-report refresh; dependency-dialog prose contradicts a tested explicit install-all feature and must retain that feature.
Clear's never-run response/read status seam is separate from the useful retained-downstream out_of_date behavior demonstrated by existing real compute/reload/rerun tests.
No tests or product/spec behavior were changed; candidate findings remain qualified source risks, oracle/documentation discrepancies and unmeasured optimization candidates, not558 reproduced failures or approved repairs.
M1 remains OPEN; repairs, new diagnostic tests and application/backend/frontend/browser/worker/external/published-compatibility/native acceptance remain held and unrun.
Native desktop acceptance remains final M5.

## Cross-subsystem synthesis before the completeness gate

The whole-file review identifies a small number of recurring architectural causes across many distinct callers: competing authorities for executable identity, asynchronous continuations without an invocation owner, logical terminal state published before physical retirement, and publication/read models that do not preserve the identity of what was accepted.
The findings register retains every individual candidate and its counter-evidence; grouping them here does not merge distinct failure mechanisms, turn source risks into executed bugs or authorize implementation while M1 is open.
A full source review cannot establish that every possible bug was discovered, and none of its file counts replaces behavioral certification.

### Decisions and dependencies for the later repair backlog

| Priority family | Representative canonical findings | Decision required before a repair | Essential behavior and existing evidence to retain |
| --- | --- | --- | --- |
| Portable executable/resource authority | A-F001–003, A-F066, A-F097; B-F067 | Distinguish carried qualified binding from ordinary unbound catalog discovery through public library load/materialization, including resource and engine classification. | Explicit rebind, recursively owned source bytes, declaration floors, typed structural validation and actual Direct versus ProcessingTool dispatch; held red diagnostics remain red evidence. |
| Identity and invocation ownership | A-F004, A-F072, A-F168; ROOT-F016–017, ROOT-F023–024, ROOT-F093–094; reviewer-F092 | Specify root incarnation and request/dialog/source-owner barriers at actual admission and finalization seams; distinguish committing physical work from publishing obsolete UI state. | Accepted CAS, independently open canvases, agent conflict/recovery, exact sibling/source bytes, generation-bound deletion, no replay after ambiguous or committed action. |
| Publication, destructive effects and credentials | ROOT-F001, ROOT-F006, ROOT-F008–010; A-F076, A-F080, A-F124; B-F168; reviewer-F047 | Resolve the exact owner, publication point, rollback preimage and crash/retry policy; separate single-app serialization from independent cooperating writers. | Streaming progress/cancel, successful sibling uploads, original credentials, atomic favorite/import/result identity, edited demo preservation and maintained exporter source inputs. |
| Physical execution/environment lifetime | A-F007; B-F001–002, B-F024, B-F120, B-F132, B-F152, B-F162; ROOT-F053–056, ROOT-F069; reviewer-F072–074 | Bind admission and terminal acknowledgment to physical cleanup/retained retry ownership, and establish a supported public force-Recreate capability. | Cooperative acknowledgment, no partial result publication, retained successful cache, exact public recipe/Core attestation, genuine worker PID/files; never private environment deletion or recipe nonce substitution. |
| Result/source projection and scientific meaning | B-F043–045, B-F188; A-F030, A-F111–115; ROOT-F036, ROOT-F080, ROOT-F096 | Distinguish immutable chosen records from latest projection, immediate Clear from authoritative read, declared image/units from guessed bytes and actual lineage from ordinal association. | Corrupt-present refusal, explicit legacy absent-provenance fallback, quarantine/history/sibling byte preservation, retained downstream stale outputs, exact numeric tests and public row/cardinality policy. |
| Deployment, external and native boundaries | ROOT-F002, ROOT-F058; A-F106; B-F042, B-F163; reviewer-F040 | Use configured capabilities and exact dependency/public environment routing; decide spawn acknowledgment versus actual reader/editor/native readiness claims. | Desktop/webapp separation, trusted Python materialization guard, local/managed datasets, explicit viewer selection/favorites and public compatibility refusal; native desktop acceptance stays final M5. |
| Test/specification authority and clarity | A-F006, A-F012, A-F178–180; B-F012, B-F189–190; ROOT-F091, ROOT-F095; reviewer-F020, reviewer-F038, reviewer-F060 | Correct examples/assertions/selection at their existing seams, and measure cost before removing or moving coverage. | Real browser gesture-to-draft/storage witnesses, separate mock transport oracles, ordinary versus campaign/external lane accounting and explicit package/scientific/native prerequisites. |

Prioritize demonstrated wrong-authority/publication failures and reachable destructive/admission risks ahead of optional cleanup or documentation polish.
Within each family, complete a bounded diagnostic only after M1 closes and only if its existing evidence does not already distinguish the decision; extend a relevant existing fixture rather than duplicate a broad successful journey.
A source risk with a real mitigation or unresolved contract remains deepen/decide, not an automatic rewrite.
Accepted N1/E1 product work and unchanged historical evidence are retained; I1/T1/dataset/portable work remains held until its explicit source and completion checks are reconciled.
No individual family is certified or declared repaired by this ordering.

### Specification reconciliation scope

Reconcile platform v1/v2/viewer documents and library/Core contracts around one explicit authority per concept: canonical recursive GraphState and immutable ports, carried executable/viewer declarations, accepted draft/CAS/incarnation, immutable result provenance, public environment recipes/resources, deployment capabilities and physical lifetime.
Preserve the project fundamentals and supported features, including explicit exact dependency installation, recursive owned sources, agent editing, parallel/selected execution, force-Recreate, result exports and viewer favorites.
Conciseness should come from references to authoritative schema/public contracts and a concise feature-to-invariant map, not deletion of essential functionality or silently making the code the definition of intended behavior.
Current contradictory examples include missing concrete row-consumption declarations, Pydantic-versus-IOModel wording, dependency dialog no-install prose despite implemented install-all, saved-versus-accepted-draft Run wording and global catalog versus carried workflow pins.
For each such disagreement, the register records current behavior, intended contract and actual distinguishing tests; decide explicitly before changing either side.
Historical campaign records remain dated evidence, with prospective checks, mocked gestures, red diagnostics and real passes distinguishable.

### Testing and documentation efficiency decisions

During later localized implementation, use the existing authoritative `scripts/test focus` selector and exact failing browser; use five repeats only for a suspected timing/race seam.
After a coherent increment that will continue, use quick; at completion use the smallest applicable scoped check, without stacking commands subsumed by a later check.
Use app checks for cross-stack/schema/runtime/dependency changes, all/browser-all only for broad architecture/test-infrastructure changes, full for major milestone/release/package compatibility certification and published common-tools certification where applicable.
Maintain separate externally blocked and native phases; an offline protocol mock or excluded test body remains useful but earns no actual worker/scheduler/native acceptance.
Use campaign guards for routine record consolidation, Sphinx for navigation/structure and substantial documentation milestones/final certification; avoid rebuilding docs after each status row.

Preserve focused deterministic CAS/ownership/typed-error tests alongside the fewer real gesture/storage/worker witnesses: these protect different boundaries even when setup looks similar.
Existing redo accepted-graph tests mitigate the weak incidental moved-position redo check; real source-copy bytes and literal worker rows mitigate broad response waiters without proving every result field.
Improve old empty-search selectors, copied App shortcut harness and missing node-navigation assertions in place; changing assertions is not evidence of a production defect by itself.
Shared controlled worker/HTTP helpers need explicit acquisition, timeout, release/drain and failure cleanup before suite parallelism can safely increase.
Measure comparable source/fixture/dependency/environment revisions, per-selector duration, setup cost, failures, retries/skips and artifacts before moving tests or claiming speed gains.
Serial shared-workspace/hot-reload tests must retain isolation; no blind global parallelization or measured optimization is claimed during this read-only review.

### Checkpoint and retrospective policy

M1 closes only after zero pending/current-hash-mismatched human inputs, explicitly reviewed/classified producers, reconciled cross-owner findings and independent acceptance of method, evidence samples and prioritized backlog.
At each later major milestone, revisit architectural causes, test cost/oracle fidelity, specification coherence and remaining risks, then update the next bounded packets; do not run a whole-campaign retrospective after every small edit.
Source-sensitive evidence is reused only for unchanged equivalent phases, with exact command/revision/duration and skipped/flaky/blocked accounting.
The final campaign certificate must include complete applicable local checks, real required external compatibility and final desktop acceptance separately; no review count or scoped check stands in for that certificate.

### Complete frozen-source review checkpoint and final-control reopening

All frozen source/test/specification/held-WIP and dependency inputs have now received an individual full review or explicit producer/consumer classification, subject to final current-control reconciliation and independent acceptance.
A's354, B's438 and root's390 assigned inputs are complete; the shared reviewer has611 previously accepted snapshot judgments, with six pending controls and the changed architecture audit explicitly reopened.
The installed Wetlands2.4.2 three-seam review is a newly captured current snapshot because the initial reconnaissance lacked hashes; all three full installed bodies match their source checkout bytes, without claiming historical runtime baseline equality.
All740 frozen platform,909 library and118 Wetlands tracked entries remain inventoried;28 held WIP and3 installed dependency inputs plus the newly authored findings register complete the1,799-input scope.
The signing row addresses only its identical canonical tracked gitlink descriptor, with private signing content excluded; packaged icons/VSIX/lockfiles/generated schemas have individual producer/consumer limits.
Reviewed rows no longer retain stale inventory-only depth; the conservative minimum is read, with prior traced/deep evidence retained, while classified rows explicitly record their producer boundary.
The ledger's generated self-input uses SHA256 of its canonical LF TSV after replacing only its own content_sha256 cell with a literal dash; this avoids an impossible recursive hash and is verified separately from raw human-input SHA256.
The register and audit are human review deliverables, with the already-reviewed base plus every changed delta requiring final exact-content reconciliation.
There are1,792 accepted snapshot inputs (1,643 reviewed /149 classified) and seven pending/reopened current controls, with573 canonical identified candidates.
These candidates include source-established behavior, qualified risks, test/doc discrepancies and unmeasured cost debt; they are not573 reproduced bugs or approved fixes.
Cross-subsystem synthesis is recorded above, including public force-Recreate, executable authority, destructive publication, invocation ownership, scientific/result semantics and proportionate test/documentation lanes.
Independent review samples other owners; A does not independently accept its own354 judgments, which B cross-checks separately.
M1 remains OPEN while the current controls and independent method/evidence gate finish; all repairs, new diagnostic tests and application/external/native acceptance remain held.
Desktop native acceptance stays final M5.

### M1 complete-review closure — 2026-10-01

All 1,799 agreed-scope inputs are accepted: 1,649 complete human reviews and 150 explicit generated/asset classifications, with zero pending, missing, duplicate, unmatched or current-hash-mismatched entries.
The scope remains 740 platform tracked paths, 909 library/Core paths, 118 entire Wetlands checkout paths, 3 current installed seams, 28 held WIP inputs and 1 new human findings register.
Final ownership is A 354, B 437, root 390 and shared reviewer 618; the cleanup-policy Context control was formally transferred from B to the reviewer, adding no source credit.
The reviewer read all nine current human controls completely, including the complete 7,656-line register, recovered truncation holes and all terminal deltas, and classified the ledger through complete row/producer reconciliation plus its documented nonrecursive selfdigest.
The independent method review supports other owners' source/oracle samples and exact membership; B separately cross-checks A, avoiding self-acceptance and any claim of a second full reading of every input.
Its specificity, historical/current wording and selfdigest concerns were corrected and reconciled before closure.
All 573 canonical candidates and their qualifications remain in the register; this is agreed-scope review completeness, not proof of defect absence, 573 reproduced bugs or blanket repair approval.
The prioritized cross-subsystem synthesis preserves essential project features and defines bounded repair/retain/deepen/defer decisions, proportionate existing test/docs lanes and low-frequency strategic retrospectives.
No product fixes, new tests, dependency provisioning or application/browser/worker/external/native acceptance occurred during M1; accumulated dashboard evidence remains 276/500 with its historical limits.
Next is the M1 strategic retrospective and M2 packet prioritization: reconcile demonstrated portable-authority/dataset-publication reds, reachable destructive/credential risks and public force-Recreate ownership before dependent repairs, retaining accepted N1/E1 and held I1/T1 evidence.
Every later source change reopens its affected review/contract/oracle claims; unchanged review inputs and valid equivalent passing phases are retained rather than blindly repeated.
Desktop application execution remains final M5.
