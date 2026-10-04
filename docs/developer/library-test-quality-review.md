---
orphan: true
---

# BioImageFlow library test quality — accepted T review

Status: T accepted on October 4 after one independent cross-domain review and two bounded wording clarifications.
This acceptance advances to C main review; all primary owners finish before secondary review, and global findings acceptance remains required before fixes.
This document assesses test bodies, fixtures, selection and assertion quality; it is not a runtime test result, production C review or library certification.
The authoritative accepted intent is platform `docs/developer/library-specification-intent-review.md` at `0500b25b3b3f135237bf3530b7d152be8a619b56`.
Owning docs HEAD is `e0f41b11e62defcd84b913db12b14e481b7c9a0b`; production and test bodies remain `2cd79a24c59cf1093e934da9aa97744d2f8709c8`.
The order stays S accepted → T accepted → C primary causal paths → C secondary paths → global recorded findings accepted → prioritized repairs/tests → one scoped library milestone.
No source/test fixes, runtime imports/collection/execution, dependency changes, network, CI or publication occurred during T.

## Scope and evidence boundary

Three domain packets were adjudicated against the sixteen accepted flows, not summed as independent coverage of the same files.
The Core packet covers declaration/type/codec/loader/public helper/GUI oracles; workflow/science covers graph/archive/session/template/composition plus all nine scientific packages; runtime covers local dispatch/environment/cancellation/cache/storage/results plus global suite infrastructure.
The deduplicated source inventory has 194 root test modules: 145 have full-body evidence from at least one domain; 49 distributed-engine/remote scheduling/cluster transport modules are excluded from this phase without a full-body claim.
All 22 scientific tool test modules have B whole-body evidence; nine domain conftests are documentation-only and their optional requirements occur in test bodies.
Full-module evidence includes some explicitly excluded distributed-only nodes in mixed local files: it is not a claim every node in 145 modules belongs to the milestone.
Local export/returns/assets/inputs/control state and actual within-machine processes stay covered despite launcher names; remote scheduling, Parsl/Dask/PSI-J/SSH execution and site provisioning do not.
Local-named cases in `tests/integration/parsl/test_launcher.py` exercise Parsl executor capability and remain excluded for that feature; their names or directory alone do not decide the boundary.
The preserved review receipts under `/private/tmp/bioimageflow-library-deep-review/` include `tests-runtime/global-scope-closure.json` and the three domain ledgers, naming every root module/hash, full-read or unchanged prior-body reuse, fixtures, line ranges and substantive owners.
A's final domain ledger records 113 full test/config/fixture/tooling inputs; Core records 46; B records 77 including 62 distinct test modules and shared/domain fixtures.
Those input counts overlap and must not be added into a whole-suite count.
B's 674 selector stems and the other AST maps are mechanical source names, not pytest-collected parameter-expanded cases, selected runs, skip totals or pass counts.
The historical 351 PASS / 1 skip receipt is retained only as earlier bounded evidence; its uncaptured skip reason remains UNKNOWN and cannot be inferred from a skip predicate discovered now.
Prior local artifact, managed worker, focused owner and OS configuration receipts retain their original byte and capability limits; no earlier PASS establishes conformance to new S target contracts.

## What should be kept

The suite contains meaningful public behavioral controls and should not be replaced wholesale.
Keep rejected mixed fanout graph/result equality, actual same-ID changed-source executable/helper/asset coexistence, namespace-resolved annotations, exact malformed task/result correlation refusal, independent numeric dtype/precision/nonfinite values and current literal container identity.
Keep actual selected-record B/99→downstream198 and key changes, concurrent first-valid publication/winner-conflict agreement, pointer corruption distinguished from valid immutable records, staged publication rollback and unrelated/outside sentinel preservation.
Keep root/slice/asarray reference lifetime, pending→closed after final-reader drain, strict failed-close grant retention/retry and physical-drain-before-result-disposition control.
Keep the real local cancellation socket barrier proving admitted writers cannot finish the controller early; keep a separate actual local child wait/reconnect witness, without calling either a certificate for every pool/PID/grant.
Keep independently expected scientific axes, rectangles, assignment counterexamples, explicit foreground/connectivity, sparse label/dtype refusal, seeded clean/noisy metric and exact table values.
Mock adapter equivalence, native smoke and scientific accuracy establish different claims; retain each useful assertion with its honest label.
S05 permits a known heterogeneous merge column, such as the int/str concat in `test_merge_strategies.py::TestMergeSchemaPropagation::test_concat_type_conflict_falls_back_to_any`, to be honestly summarized as Any/dynamic; that differs from fabricating empty/Any success for an unavailable or failed schema.

## Prioritized quality findings and C obligations

These are consolidated test-quality concerns with domain-local provenance, not new canonical reproduced product defect IDs.

| Priority / concern | Actual evidence | Intended action after C |
|---|---|---|
| P1 — essential local worker lane omission | README smoke omits required external admission; complete job intersects `complete and wetlands`, excluding wetlands-only smoke/task-API modules | Correct explicit local lane/skip ownership; keep fast exclusion honest. Do not add a new worker matrix merely to fix selection. |
| P1 — lifetime/outcome closure gap and inconsistent expectations | Strong grant/result-disposition/view tests coexist with failed-close fixture discarding owners, cancellation context `failed` versus run `cancelled`, stale SharedMemory cleanup and no exact accepted group/discard/quota witness | Trace one current outcome/resource authority through C; retain strict retryable ownership and add only missing normal-result group/repeated-discard/idle-retirement boundary after design. |
| P1/P2 — isolated collective aggregate has no decisive lineage oracle | MAPPED batch normalization, CellposeTrain per-row stub, repeated spot aggregate rows and method-identity tests do not prove true collective all-consumed-input association | Preserve isolated training/inference/aggregate and configured empty outputs; settle current representation in C, then one independent aggregate/association witness rather than forced duplicate outputs. |
| P2 — immutable definition/config capture is weak | Snapshot labels and TrackingEngine context pass without distinguishing effective per-environment config, source/default capture and setup/refusal/finalization authority | Main C joins editable graph → captured definition/config → admitted execution; select a held public changed-definition/control only for a real uncovered invariant. |
| P2 — schema/default/discovery authority is incomplete | Passthrough extras only inspect annotations; failed versus empty schema, family/concrete registry, Optional metadata, detached mutable defaults and current loaded/programmatic parity lack distinctions | Keep dynamic no-Outputs DataFrame features; trace truthful known/unknown/failed schemas and kind-specific admission, then narrow public metadata/value refusal controls. |
| P2 — source import authority and transport no-I/O gaps | Equal dependency fixtures don't consume differing dependency values; old SharedMemory sentinels don't observe mmap; source loaders lack same-size/mtime/current-root and publication-failure contrasts | Main C traces exact current origin/content and pure decoder/acquisition boundaries; no legacy origin matrix or blanket dataclass support. |
| P2 — high-level assertions can be vacuous or wrong-stage | Empty progress loops, lowercase cache filter, detached AddColumn, invalid CSV for dynamic-column refusal, unresolved timestamp count and fake current-record switch | Strengthen/repurpose the exact existing selector with captured target, nonempty events, independent values/effect sentinel; merge with stronger equivalent family where redundant. |
| P2 — scientific shape/smoke can overclaim | Model all-zero output passes; Nagini signatures, mocked CZI/Zarr/ATLAS, finite binary shapes and self-derived counts do not prove scientific/native resource truth | Secondary C distinguishes domain numerical intent, adapter protocol, actual named model/binary/native data and owned failure effects. Small independent representative truth, not one test per tool. |
| P2/P3 — fixtures/legacy expectations bias the contract | Graph-v1 goldens, retired source flags, AST blanket union rejection, arbitrary default→str fallback, globally removed sys.modules and ordered lists sorted in goldens | Retire obsolete-only policy and isolate fixtures after C; preserve essential current origin coexistence, literal wire identity and supported scientific Python. |
| P3 — organization/tooling assertions outstrip architecture claims | Literal CI jobsets, path/line guards, advisory affected mapping, wheel PYTHONPATH import and mocked publishers | Keep cheap organizational diagnostics but require actual source-disabled artifact/resolver/public consumer closure separately; choose one explicit local milestone lane. |

Source-bound domain provenance: Core T-C01–T-C11, workflow TWQ01–TWQ13, runtime TR-01–TR-09.
Existing qualified M1/architecture references remain related context, not silently changed to confirmed current product failures by this review.

## Exact selection defect and future lane scope

`conftest.py:11–19,50–62` puts `wetlands` in the externally gated set and applies skip unless `--run-complete` is set.
`README.md:343` says `uv run pytest -m wetlands tests/integration/test_wetlands_smoke.py`; its two source nodes are `test_processing_tool_executes_through_published_wetlands` and `test_configured_logging_routes_wetlands_worker_streams`.
As written that command skips them at collection modification rather than establishing local worker coverage.
`.github/workflows/complete.yml:51` runs `uv run pytest -m "complete and wetlands" --run-complete -rsx`.
Smoke and all fifteen task-API selector stems have only wetlands; the cancellation module has complete plus wetlands, so only that module participates in the intersection among these three families.
README fast unit/integration expressions explicitly exclude wetlands/complete/package tools/model/binary/data and the real Parsl marker; do not call fast PASS local-worker/scientific certification.
`not parsl` alone also does not exclude mocked distributed test directories; an explicit current local node/file packet must be used for this milestone.
The minimum prospective local actual-worker command is `.venv/bin/python -m pytest --run-complete tests/integration/test_wetlands_smoke.py tests/integration/test_wetlands_task_api.py tests/integration/test_wetlands_cancellation.py -rs`, with exact affected nodes first and only after C/repair authorization.
This is a proposed corrected family, not an instruction to run it during T or a promise all current fixtures satisfy current S/cohort contracts.
Record actual skips/reasons/resources when later run; public numeric artifact OS gates are separate from ManagedWorkerPool and scientific optional capability.

## Sixteen-flow oracle map

Canonical flow labels below come from the accepted S report; the domain packets' related coverage is synthesized rather than substituting a second flow taxonomy.

| Accepted flow | Strong existing evidence | Remaining decisive boundary / owner |
|---|---|---|
| F01 import/declare | Cold worker-safe import and public kind/annotation assertions | Concrete families, dynamic known/unknown/failed schema and actual floor annotation resolution; Core + infra |
| F02 build/edit/validate | Rejected public fanout preserves captured graph/results | Successful replacement reachability, None/default/mixed-required parity, fresh diagnosis and refusal phase; workflow/Core |
| F03 capture/invoke/rebind | Independent nested snapshot values and injected execution context | Held effective configs/sources/defaults, overlap/setup/finalization and reservation; workflow/runtime |
| F04 load/export source graph | Whole-table sentinel refusal and A/B/A executable/helper/asset identity | Current graph fixture, outer destination/ancestor ownership and imported dependency authority; workflow/Core |
| F05 plan/align/cache identity | Exact index parser, selected-record values/keys and explicit merge routes | Nontrivial mapped worker correspondence, exact joins/explosions and same-path external-input policy; runtime/workflow/science |
| F06 Direct/local mapped/collective | Actual mapped worker transport and explicit empty-batch effects | True isolated aggregate consumed-input association, exact caps/config and dynamic DataFrame execution; runtime/Core/workflow |
| F07 reuse/force environments | Same public manager generations, warm False and strict close retry | Real current SDK/import origin, logical/physical fences and captured configuration; runtime |
| F08 publish/select/load | Concurrent first-valid winners, corruption refusal and immutable no-current return | Correct the weak switch/key assertion; accepted input nonmutation and no stale pointer recapture; runtime |
| F09 fail/cancel/step/close | Real writer barrier, exact primary errors and retryable grants | Timeout/interrupt versus completed writer versus retired pool, setup/step termination authority; runtime/workflow |
| F10 allocate/open/accept arrays | Numeric/ref refusal, derived views, contained files and disposition race | Current no-I/O sentinel, malformed headers, output-only scope, immutable accepted values and supported OS/floor; Core/runtime |
| F11 retain/release/repeat | Unopened refs survive temporary Workflow and failure rolls back only new groups | Accessible exact accepted-group release, repeated ordinary discard and quota-pressure retirement; Core/runtime |
| F12 hydrate/export local return | Exact immutable record/asset load, copied bundle integrity/atomicity | Current result/group owner access, scientific numeric public Workflow export and independent transient lifetime; runtime |
| F13 templates/output projection | Owned/external refusal, atomic destination preservation and zero-row facts | Resolved timestamp, pre-dispatch collision effects and empty collective aggregate association; workflow/runtime/science |
| F14 schema/viewer/logging/CLI | Portable requirements, opt-in logging handlers, exact DTO/refusal and CLI forwarding | Failed/empty catalog distinction, ordered metadata, safe real staged command/export boundaries; Core/runtime |
| F15 table/IO/classic science | Independent axes/assignment/metric/foreground/table values | Exact centroid/overlap/SNR/unit and mutation/destination identities, native format versus adapter proof; science |
| F16 optional model/binary/FLIM | Mock channel/routing; named native smoke; numerical phasor consistency | Resource/checkpoint/data identity, representative independent expected truth, honest capability skips; science + infra |

Preserved finite domain selector maps retain exact existing file/class/function stems and fixture provenance; no giant per-test matrix or guessed collected IDs is introduced.
No suite body found establishes the missing isolated aggregate or exact normal accepted-group release merely by a similar name; absence is qualified to the complete in-scope body review.

## Scientific and secondary preservation

All nine scientific feature families remain in scope and must be preserved; optional Phasor first-project publication is separate from deterministic feature quality.
Synthetic arange tensors/rectangles/trajectories/assignment counterexamples are often good independent truth, while text `FAKE_IMAGE` is deliberately only a graph/file-name fixture.
A valid text filename fixture is invalid as CSV/image scientific input; a wrong upstream parse error cannot be accepted as missing dynamic-column validation.
Native model/binary/data predicates include importorskip, configured checkpoint paths and the external marker hook; they were inspected, not evaluated.
Model/binary shape/finite smoke is operational evidence only; no biological correctness guarantee or new mathematical theory is invented.
Input mutation, existing destination preservation, zero/empty assets, explicit label/index/unit conventions and parser acceptance/refusal remain secondary C effect obligations.
GUI/viewer/public constants have current logical contracts; retire legacy graph normalization or arbitrary stringification only, without treating independently versioned viewer/origin/task entities as one global version.

## Cleanup, focused validation and next C gate

No test is deleted merely for matching a title or file location.
Keep distinct public boundaries; merge boilerplate and weak duplicated hit/schema/export assertions only when their stronger replacement actually covers the same effect/refusal.
Retire historical-only wire/source-policy/AST expectations; preserve current-process origin coexistence, literal dictionary/path/container identity and essential Python3.9/NumPy1.26 features.
After C selects coherent repairs, establish an exact meaningful causal RED where appropriate, fix once, exact GREEN, affected owners and one smallest subsuming milestone; no quick/full/OS/native stack per edit.
Reuse the current private environment without reconciliation, freeze artifacts when causal setup runs in parallel, reuse unchanged byte-bound evidence and one final independent review.
The C main trace order should follow declarations/admission → captured graph/config → aligned local dispatch/correlation → publish/cache → accepted return/resource lifetime/error cleanup, then secondary scientific/public-tooling paths.
Specific new test design remains contingent on those actual source paths and recorded global findings; a test gap is not evidence the product code fails.
T acceptance advances only to C review, not repairs or release/platform adoption.
Unexecuted OS/Python artifact, normal current package resolver/consumer, scientific resources, exact published closure and desktop gates remain explicit later obligations.
