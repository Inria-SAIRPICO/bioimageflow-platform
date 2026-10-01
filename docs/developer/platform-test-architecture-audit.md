---
orphan: true
---

# Architecture and test reconnaissance — 2026-10-01

The earlier bounded pass completed selective reconnaissance only; **M1 complete-codebase review is OPEN**, with repairs and further campaign testing held by the user's clarification.
The initial synthesis and diagnoses below are preserved as partial historical findings, not a completed whole-codebase review.
The [campaign plan](platform-test-plan.md#reconnaissance-gate-architecture-and-tests-together) defines the gate and [checkpoint](platform-test-progress.md) owns the executing queue.
The [per-file ledger](platform-test-file-review.tsv) records exact inventory revisions, subsystem ownership and inspected depths.
Depth describes the stated invariant or excerpts, not every line of a large file; inventory-only/classified means unreviewed implementation.

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
