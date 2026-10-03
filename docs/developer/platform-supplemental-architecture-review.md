---
orphan: true
---

# Supplemental architecture and test review — October 3, 2026

**Findings/triage gate accepted by the campaign lead and independent completeness reviewer on October 3, 2026, within the explicit scope and limits below.**
This review records problems and architectural decisions before further repair code.
It supplements the accepted M1 per-file audit with cross-file common-task, owner/API, type/resource, failure/cancellation, migration/publication and test-strategy review.
The frozen M1 coverage remains 1,799 agreed inputs (1,649 human-written inputs marked fully reviewed and 150 justified classifications); it is not rewritten and does not establish end-to-end performance assurance or universal correctness.
The [complete candidate disposition inventory](platform-architecture-candidate-dispositions.tsv) preserves every one of the original 573 qualified IDs, including original severity, uncertainty, source provenance and explicit current owner/trigger.
ROOT-F098 and ROOT-F099 are later supplemental findings, not changes to that denominator.
A source-qualified candidate is not automatically a confirmed runtime bug or a request to rewrite an entire subsystem.

The current platform product source is tree-request delivery f32c9b472c9a39e5e133580149bdd2e8d8296ff7; documentation-only descendants through 04f9588f76ee7122e6c11e6bf61ea112d75f7bb0 do not change that product projection.
Read-only review used three disjoint owners, followed by independent cross-owner source/contract samples: startup/Open/edit-Save and frontend API ownership; dataset/Run and library/Core/Wetlands ownership; and whole-suite/lane/fixture strategy plus the original candidate inventory.
Their bound input sets are 63, 104 and 66 targeted source/spec/test paths respectively, with overlaps; those counts are not distinct full files re-read, executed cases or measured coverage.
High-risk families outside the five task maps were explicitly routed and sampled; lower-priority unvalidated mechanisms remain qualified with their own responsible owner and trigger rather than silently being marked safe.
No product changes, new tests, test collection, profiling, runtime, native app or environment installation occurred during this supplemental review.
The only completion check for the intended review documentation is the consolidated documented docs lane after the source/contract/method gate.

## Separate source and runtime projections

| Projection | Actual authority | Limit |
| --- | --- | --- |
| Main platform | Current accepted product; installed editable BioImageFlow dff04e3 and Wetlands2.4.2 | Published Wetlands2.5 has not changed platform source, pins, installed runtime or lock. |
| Reconciled isolated library | Clean reconciliation3859 plus six preserved force/public-completion WIP paths, source metadata0.8.7 | WIP accepted only for local source development; original lock2.4.2 is explicitly overridden in its private candidate environment. No final aligned library release or commit certificate. |
| Published Wetlands | Released2.5.0 source3cda2236fe000b30dabf42a04e9ad347265630a0; wheel identity and29modules+py.typed match accepted candidate | Published-wheel source-disabled nine controls pass with18 filtered cases; public Operation completion is not a Task/worker/PID/platform admission certificate. |
| Historical campaign phases | Exact earlier source/dependency/runtime manifests and qualified phase recoveries | Original full/app/frontend failures, unrun phases, Firefox infrastructure block and final M5 desktop gate remain recorded. No assembled evidence is renamed a monolithic full PASS. |

## Architecture judgment and priority decisions

The underlying architecture has useful owners worth retaining: canonical recursive GraphState, canvas-registered resources, backend draft CAS and identity locks, public library compilation, worker-safe Core declarations, immutable modern result provenance, and cooperating catalog writer/staging boundaries.
The recurring problems are at the seams between those owners: admission that captures identity too late, async continuation that reads a newer live owner, duplicated semantic projections, logical completion mistaken for physical retirement, and ancillary work that can fail after accepted publication.
Several measured multiplicity errors were static review omissions; profiling established magnitude and priority, not the existence of repeated source work.
The earlier file review was real, but file coverage and local findings were insufficient synthesis for common-task cost/freshness and exact cross-package authority.

The post-gate queue should make explicit decisions before small causal repairs: recovery absence/conditional deletion; caller incarnation and Save promotion semantics; configured server source-opening capability; physical Run/request admission; migration/containment writer ordering; and exact public source/cache/transport/scientific identity.
Published Wetlands2.5/library floor+lock alignment is a coherent next dependency task, followed by platform strict force/T1 admission only against its accepted public library contract.
This does not erase higher-risk release prerequisites for the affected source/archive, shared transport, scientific or managed retry behavior.
Lower-risk projection/form/accessibility/doc corrections and measured request-local performance work can be grouped by one owner after those decisions, preserving the original feature scope.
No blanket state manager, global cache, pool registry, graph rewrite or mass test deletion follows from this review.

## Completeness and evidence matrix

| Required acceptance dimension | Current delivered review | Explicit limit / remaining authority |
| --- | --- | --- |
| Common-task chains | Startup, Open/Create/Save As/Import, edit/Save, dataset browse/upload/delete/Files and local/managed Run through actual producers, public owners and consumers below | Source traces include late/error/cancellation boundaries; no new runtime journey or managed/distributed execution certification. |
| Broader architectural families | Public source containment/import/cache, interface mutation before refusal, migration/lock ordering, resource/transport/numerical identity, result/export publication, environment lifetime, deployment and API/spec authority | Highest-risk source mechanisms and real mitigations sampled; actual deadlock, memory/process retirement, numerical harm and remote uncertainty require owning causal controls. |
| Original candidate completeness | Exact frozen573 IDs, families, priorities/uncertainty and each responsible owner/trigger;144 distinct current keyed annotations from43/80/28 packets |429 IDs have no current annotation and are deliberately deferred; annotation includes historical mitigations/deferrals and is not synonymous with reproduction or bug confirmation. |
| Highest-risk and unranked treatment | All56 original High/MediumHigh/P1 candidates have specific current annotations;21 unranked headings retain body qualification and explicit owners | No highest-risk family is closed by mechanical grouping; reviewer084/085/093/094 remain explicit historical/deferred controls/contracts. |
| Cross-layer/spec coherence | GraphState versus plain Core IOModel, saved versus accepted draft Run, explicit Files snapshot, Clear status, authoring/install/dev-mode prose, generated API versus handwritten wrapper | Existing authority order retained; futurev3 and excluded engines are preserved proposals/regressions, not implemented guarantees. |
| Test architecture and cross-review | Dedicated suite owner, distinct fake/ASGI/browser/worker/artifact evidence, native-selector gaps, weak existing oracles and bounded consolidation candidates; independent cross-owner source samples | No suite-wide execution/coverage percentage; current selection failures, Firefox admission and final nativeM5 remain separate. |

The historical register/ledger extraction is bound to `b6dabfa34371218228d2d13729ee86c8a991f1c2`, findings SHA256 `50876661e57aa591ca1ef0d13b02a8ccd68aed5ba989d200938ce4d86130323d` and ledger SHA256 `164c799e2b22be06c16518b2451a8e7cd9fe759ef5f7bd62df2030e4923a5036`.
The exact original author counts are A181/B195/ROOT97/reviewer100; aliases and related references remain separate original IDs.
Primary family routing covers tools/source/types/dependencies141, execution/admission/runtime117, graph/workflow/recovery104, results/scientific/cache75, test-suite/CI/fixtures/oracles66, specifications/public contracts42 and configuration/persistence/datasets28.
These are descriptive routes with overlapping mechanisms, not counts of confirmed defects or mutually exclusive runtime components.
Current disposition grouping is14 bounded-repair retained,1 bounded repair with qualified residual,128 current-source-qualified open/deferred and430 historical/current-unvalidated; the last group includes429 unannotated candidates plus the explicitly deferred reviewer-F084 accessibility case.
Those bins preserve mitigations and uncertainty; they are not repaired-versus-open incident totals.
The TSV retains original canonical links, frozen headings/provenance and current scope qualifications; the report explains architectural synthesis rather than copying all573 headings.

## Dependency-ordered repair decisions after this findings gate

| Bounded wave / owner | Priority and concrete decision | Distinguishing acceptance before expanding |
| --- | --- | --- |
| Public release prerequisites — library/Core/source owner | Decide public archive containment/isolated worker imports (A024/A138), rejected invocation state (A036/A041) and typed/numerical transport (B074/B115/B134). These are source-qualified high-risk public boundaries, not all demonstrated defects. | Source-disabled archive/import, unchanged graph on rejected public invocation, exact scalar/typed producer-consumer controls. Decide each relevant library release blocker before certifying a new package; no automatic repair of all public engines. |
| Dependency closure — library then platform lifecycle owners | Published Wetlands2.5 is available; align held library floor/root-dev declaration/registry lock and minor metadata only against actual published closure, then select platform T1 strict force/admission integration. | Retain local force controls; validate published library/Core worker closure and same-manager generation/physical admission against the exact released owner. Main installed dff/Wet2.4.2 stays authoritative until explicit pin/runtime task. |
| Configured source-opening/Reveal capability — backend API policy owner | A106 older editor entrypoints and B042 node Reveal still lack consistent configured webapp refusal despite corrected immutable settings policy. This is a current high-risk entrypoint gap, not evidence of an external exploit. | Refuse configured webapp actions before mocked native/editor dispatch; preserve supported desktop and explicit unsafe/source-opening policy. Native launch belongs only to finalM5. |
| Recovery and first admission — frontend persistence/API/store owner | A061/A063/A062 recovery absence, conditional deletion and failed-draft policy; A004/A059/A072 caller incarnation and explicit Save promotion semantics. Prioritize accepted-data authority over lower-risk presentation cleanup. | Typed absent versus migration/source failure; atomic stale-entry clear; held explicit stale caller versus omitted legacy ownership and saved-promotion conflict. Existing CAS/queue/close controls retained. Cross-stack contract edits use scoped app completion. |
| Physical execution and writer ordering — backend/library owner | B024/A007/raw awaiter lifetime, B041 managed submission and A018/A082/A083 import/migration/containment lock ordering. Set physical admission and lock-order contracts before adding flags/caches. | Actual held body/public operation after raw cancellation; original error retained; no early admission reuse; staged writer/lock-order controls. Cooperative Stop and Operation completion are distinct evidence. |
| Dataset and deferred canvas ownership — store/panel/command owner | ROOT016/017/023/024/027/028/029, plus newer intent/event/form seams. One coherent captured attempt/destination/publication packet instead of separate per-panel guards. | Deferred real owner promises: abort then retry, old refresh/error/finalizer, exact delete selection/revision and original canvas/node command. Preserve supported folder/Files snapshot behavior and backend containment. |
| Result/scientific/export contract — result/Core/tool owner | B067/B068/B080 pinned cache/provenance/export; ROOT031/032/A114 scientific metadata/lineage; B188 Clear status authority. Keep these different contracts separate. | Exact retained record and no-replace race, numerical known-value/lineage controls and existing Clear status oracle; no inferred scientific correctness from JSON/unit serialization. |
| Suite/specification maintenance — affected package/test/doc owner | reviewer001/003/060 cold closure and selector gaps, selected skips, mirrored/conditional oracles, generated wrapper debt and A178/reviewer038/B190/191/192 prose. Group documentation coherently, improve an existing weak assertion before adding a new journey. | Exact package/marker selections, conservative CI truth table and affected public examples; one smallest lane per coherent packet. Only measured representative setup justifies suite work reduction. |

These waves express dependency and contract choices, not automatic implementation authorization or an exhaustive serial schedule.
The root selects the next bounded packet after completeness acceptance, including whether any high-risk published-library prerequisite must precede the previously held force release.
Dynamic unknowns remain named acceptance work, rather than a reason to resume blind full-suite execution or erase implemented features.

## Authority and dependency overview

| Layer / module family | Owner and public boundary | Dependency direction and state | Architectural pressure / constraint |
| --- | --- | --- | --- |
| CanvasView + registered session resources | Immediate editable graph, node incarnation, semantic edit epoch, undo and presentation; canvas command/persistence resources are registered by canonical canvas identity. | Panels and menus route commands into a canvas. Root persistence calls draft HTTP; nested persistence uses private snapshot HTTP. | An active-canvas facade is a routing convenience, not a durable asynchronous operation owner. Deferred consumers must capture the resource/registration and node identity before awaiting. |
| App/Dockview | Canonical root/nested panel lifetime, activation cause, close/delete coordination. | Global window commands and panel API events connect MenuBar/WorkflowsPanel/CanvasView. | Multiple channels use string events and structural detail objects. App fences automatic startup and canonical activation, but a foreground producer's own continuation needs its own intent owner; event receipt cannot reconstruct an earlier lost owner. |
| Workflow catalog / presentation stores | Tree/flat catalog snapshots and retained metadata; presentationPublication carries immutable foreground/startup intent. | Distinct HTTP tree and flat routes, saved GETs and accepted mutation metadata. | Catalog authority is distinct from workflow incarnation and selected row. Same-ID metadata invalidates pending read authority; it must not imply new workflow generation or force a Browse choice. |
| Root persistence coordinator / recovery coordinator | Per-canvas queued snapshot and expected draft revision; per-key fallback write/clear ownership. | WorkflowDraftStore retains cross-canvas remote notices; IndexedDB stores browser fallback. | Draft revision, local queue revision, local identity generation and server identity generation are separate clocks. A valid operation cannot be fenced by comparing only one of them. Strict deliberate clear differs from conditional stale-entry deletion. |
| API models and generated TypeScript | Backend GraphState/discriminators and OpenAPI model contract. | API wrappers should import generated shapes; graph translator/compiler consumes canonical GraphState. | A-F006 handwritten draft request/response types remain transitional duplicate contract authority; v2 explicitly acknowledges the debt. Do not invent a second graph model or make wire identity implicit in a global active store. |
| WorkflowStoreService | Canonical saved WorkflowDocument, path identity and durable generation, source manifest, migration/admission and structural transaction boundaries. | Router admits idle mutations, service locks identity, uses owned sources and public library archive/materialization contracts. | Tree/list is an editable catalog, not complete absence authority. Saves are identity-locked atomic document publications, but graph-only wire cannot distinguish an old first-admitted caller from a recreated same-ID workflow. |
| WorkflowDraftService / GraphValidationService | Durable accepted draft CAS, response validation/status projection, fresh saved/generation/storage checks. | Complete recursive compiler → installed BioImageFlow library/Core; AnyIO worker for blocking work; status/cache read fence. | Do not reuse a snapshot across released lock phases as current authority. Ancillary agent-context publication is distinct from graph commit and from UI activation. Worker promise cancellation is not a physical-lifetime proof. |
| Library/Core/Wetlands projections | Public compile/materialization and resource semantics; environment lifecycle and managed execution belong to their own packages. | Main installed library dff04e3/Wetlands2.4.2 is unchanged. Reconciled library3859 plus six held force WIP paths uses a private2.5 candidate override; published Wetlands2.5 closure is separately accepted. | No pin, floor, lock or platform integration was changed here. Source-development local checks do not certify published library/worker compatibility. The later dataset/Run and high-risk sections detail library/Core/Wetlands and result/scientific boundaries. |

## Task trace 1 — startup and browser fallback recovery

| Step | Actual source and owner | Captured authority / released boundary | Work, publication and failure behavior |
| --- | --- | --- | --- |
| Mount and readiness | App.vue163–231,310–480 | App rootOpenRequest and isUnmounting; captured Dockview API; explicit Open starts a new request. | WebSocket starts separately. Startup does not provision tool environments. App awaits resolveStartupWorkflow, refuses superseded/unmounted or already-open-root presentation, then opens the target with startup cause. |
| Catalog resolution | startupWorkflow.ts51–59 → workflow.ts594–676; WorkflowsPanel.vue350 | Pending tree flight keyed by current catalog epoch + structural generation; max-two attempts for each caller. | Normal same-authority startup/panel callers share pending tree transport; flat fallback is a different endpoint. No resolved-response cache. Historical causal7/owner135 and production before/after prove2→1 requests, not a universal startup latency multiplier. |
| Choose candidate and recovery | startupWorkflow.ts59–76; useAutoSave.ts80–99 | Last-opened ID + stable editable tree ordering; only most-recent fallback entry examined; workflow metadata timestamps. | Missing catalog membership currently clears recovery and last-opened key before direct saved GET. The catalog deliberately hides pending-format workflows in workflow_store.py1714–1733, and hides invalid entries, so omission is not authoritative absence. A-F061 extension. |
| Saved authority | rootWorkflowPresentation.ts33–54 → workflow.ts696–719 → workflows.py620–654 → workflow_store.py2711+ | Local captured identity checked around saved read; server saved document/source manifest; background canPresent governs presentation, not all subsequent recovery side effects. | Saved GET performs migration/source admission; absent file404 differs from missing source409/workflow_source_missing and pending-format409. Metadata upsert invalidates catalog epoch. No missing-package installation is attempted. |
| Live draft authority | rootWorkflowPresentation.ts56–73 → draft GET → workflow_draft.py297–369,640–753 | Existing durable draft or revision-zero synthesis, captured server generation and saved artifact/storage baseline; final projection checks accepted graph/revision/generation/storage and Clear-owned latest output state. | No durable draft: validate outside lock, reacquire, prefer another accepted draft, recheck fresh saved state. Response projection is not a persisted draft/status write. Initial validation compilation and later cache-status compilation have distinct purposes and a released-lock gap; do not delete either by counting alone. |
| Fallback policy | rootWorkflowPresentation.ts58–73 | Current code does not preserve typed draft failure or distinguish absent/unavailable/corrupt/conflicting authority. | All draft failures silently produce saved graph with dirty=false. Canvas without seeded draft later initializes from GET; a retained newer local graph can be queued at that fetched CAS base. A-F062 remains a source-qualified replacement risk, not executed data loss. |
| Recovery comparison | startupWorkflow.ts21–36,40–49,79–93 → useAutoSave.ts102–109 | Recovery timestamp versus max(saved modified, accepted draft updated_at); local workflow identity checked after explicit Open. | Newer same-ID recovery keeps accepted draft revision as CAS base. Older recovery deleted by key in a separate transaction without comparing the inspected entry. An intervening newer entry or superseding startup can be affected: A-F063. Catch-all saved-load error also clears fallback: A-F061. |
| Canonical mounting | App.vue1380–1495 → CanvasView.vue230–263,1718–1787 | Immutable api+targetPanelId+cause activation scope; per-canvas authoritative draft supplied in panel params; registration owned until unmount. | Existing panel is activated rather than rehydrated with a newly fetched graph. New canvas installs initial graph and already-fetched authoritative draft, avoiding a duplicate initialization GET. Unmount disposes own resources and listeners. |

Required rechecks are distinguished from repeated work: the accepted same-lock synthesis repair8→3 saved reads and11→6 format plans applies to the measured no-durable-draft fixture; complete-workspace migration admission and fresh post-validation/projection saved/generation/storage checks remain required.
Startup tree coalescing does not coalesce saved GET, draft GET, tools/packages, recovery transactions or flat catalog transport.
The currently open recovery questions are error/absence authority and conditional deletion ownership, not a request to install another cache or replace IndexedDB.

Existing meaningful oracles: startupWorkflow.test.ts107 newer same-workflow recovery/CAS base;125 unrelated recovery separation;171 newer recovery with accepted draft;223/240 stale/unknown cleanup;259/285 untyped Error('404') fallback; rootWorkflowPresentation.test.ts87 actual deferred background saved+draft versus another current canvas;121 delete while draft held; canvasPersistenceRouting.test.ts652 already-fetched draft does not refetch;819 one held initialization joins; stores/__tests__/workflowTreeRequests.test.ts actual mounted panel/resolver and real-store deferred transport boundaries.
The missing distinctions are structured404 versus409/5xx, hidden migration entry versus truly absent file, conditional storage delete versus an intervening same-key write, and final initialization owner after an explicit resolution.
Mocked AutoSave/presentation tests cannot certify actual IndexedDB transaction ordering.
The existing withStore completion-handler attachment follows an awaited request callback (useAutoSave.ts44–55); a theoretical missed transaction completion is not established by earlier Firefox setup failure and is not asserted as a new defect here.

## Task trace 2 — explicit Open, Create, Save As, Import and active selection

| Step | Source / actor | Acceptance boundary and protected behavior | Remaining distinction |
| --- | --- | --- | --- |
| Browse choice | WorkflowsPanel.vue241–265,392–403,842–843 | Immutable intent is consumed synchronously; explicit row/folder Browse owns selection, including already-selected node-unselect gesture. Startup cannot replace it. Passive same-ID updates follow normally when Browse has not claimed ownership. | ROOT-F098 controlled defect repaired. Tests distinguish stale marker A→B→A, same-name foreground, initial Create/Open, startup row/folder, explicit canvas activation. This is not general foreground request supersession or a server incarnation repair. |
| Named Open command | WorkflowsPanel → window workflow-command → MenuBar.vue988–1013,385–407 | Mutation lock checked before load and after await; emits root-workflow-open-started before load; captures requested workflow name. | Named Open event advances App startup fence. MenuBar has no per-foreground-open request epoch across concurrent producers; whether all requested root tabs may open versus last intent wins needs an explicit policy. Older WebSocket active-workflow refresh remains reviewer-F092. |
| Read/recovery presentation | loadRootWorkflowForOpen → rootWorkflowPresentation + IndexedDB | Captured local identity and accepted draft; newer same-workflow local fallback remains dirty at accepted CAS revision. | A-F059 draft acknowledgment can recreate forgotten same-ID retained state before outer identity refusal. A-F061/062/063 failure/cleanup boundaries apply. |
| Graph event admission | MenuBar.vue248–265 applyGraph → App.vue1380–1495 | App verifies current local workflow identity and exact canonical panel; deletion/startup/canvas ownership retain their guards. | applyGraph returns void and silently refuses during mutation/lifecycle lock. Producers can already have committed create/duplicate/import then close their forms as though presentation succeeded: A-F169, distinct from backend rollback. |
| Create / copy / import | MenuBar.vue325–367,565–580,800–818 | Create/duplicate/import service returns exact accepted metadata; Save As captures target canvas/graph before submission; common presentation publishes foreground cause. | Shared dialog fields/finalizers lack invocation token and can close/clear newer forms when older continuation completes: A-F168. A saved duplicate is not rolled back merely because presentation fails. |
| Saved-source context Open | CanvasView.vue1510–1538 | Captures source workflow ID; helper captures identity; App canonical event admission remains final owner. | Window event arrival is not proof the initiating component still exists or source node still owns the gesture. No user failure reproduced; future fix must decide whether Open intentionally survives initiating view closure. |
| Nested editor admission | nested_workflow_snapshot.py128–173,767–782,878–923; model16–40 | Nested sessions have their own UUID/revision, root generation and parent chain. | A-F072 explicitly supplied old root generation is canonicalized to current at first admission; private session later generation/CAS checks are real protection, not first-admission proof. This is not the same thing as the ordinary Open dialog name-only request. |

Current correct architecture separates selection ownership, catalog read authority, root incarnation and panel lifetime.
A broad request manager would collapse different contracts and is not justified by the review.
The narrower follow-on design question is immutable per-invocation presentation result/refusal and source-owner admission at the common public producer boundary, retaining normal multiple open canvases and accepted create/import bytes.

ROOT-F024 also extends to parameter editing: NodePanel.vue667–699 awaits native/browser pick result, then reads selectedNode/tool predicate and invokes the active canvas facade; updateParameter363 reads current selected node.
usePathPicker routes browser file selection to Datasets' pending resolver, so ordinary browser canvas/node changes can occur while selection is pending; newest picker cancellation only retires the previous picker resolver, not the consumer's node/canvas identity.
Existing NodePanel-path-pickers controls check immediate argument and resulting parameter shape, not a delayed result after registration/node replacement; deferred resource+node admission belongs to the original ROOT-F024, not a new duplicated issue.
Field focus tracking separately captures canvas/node/field on focus, demonstrating an existing local pattern to preserve rather than a reason for a generic panel rewrite.

## Task trace 3 — edit, validated draft persistence and explicit Save

| Step | Actual owner and source | Snapshot / revision / physical boundary | Correct behavior and remaining risk |
| --- | --- | --- | --- |
| Graph edit | CanvasView.vue3617–3631, canvas command registration; NodePanel363 | Captured owning canvas; immediate complete graph; rootEditEpoch advances; provisional dirty state. | Synchronous command mutation, undo and status projection are distinct from async accepted draft. Deferred picker route currently loses initiating node/canvas (ROOT-F024). |
| Queue / fallback | useCanvasPersistence.ts478+, recovery coordinator; WorkflowDraftCoordinator queue | Clone queued graph at invocation; local queue revision; independent recovery key ownership. | Copies protect mutable edits across awaits, separate undo/recovery/durable requests. No measured full-graph copy optimization is claimed; Core B-F137 separate supported-container copy work remains deferred. |
| Initialize authority | useCanvasPersistence.ts419–475 | Seeded accepted draft avoids network; otherwise one joined GET captures workflow ID and accepted server revision. | Matches response workflow ID, preserves newer pending local graph; old held initialization can still install after explicit resolve clears initialization (A-F047). No per-init object comparison at final publication. |
| Transport | workflowDraftCoordinator.ts159–205 → useCanvasPersistence.ts451 → workflowDrafts.ts37–50 | Exactly one in-flight serialized write; expected server revision; queue snapshot retained; local dispose promise + AbortController. | Production draft adapter omits signal; disposal rejects local waiting but does not certify no future HTTP/server commit (A-F049). Wrong response identity/revision not checked in coordinator (A-F050); normal backend returns correct shape. |
| Server admit/prepare | workflow_drafts.py143–174; workflow_draft.py750–795 | Idle mutation lease; per-workflow lock captures current generation/saved baseline/current CAS and graph; expensive validation outside identity lock. | Another Run waits admitted mutation; validator deep-copies into bounded AnyIO worker. Public cancellation lifetime separate from cooperative Stop (A-F007/B-F024). |
| Server commit | workflow_draft.py799–858 | Reacquire lock, require captured generation, expected revision, fresh saved hash; atomic next draft JSON publication. | Freshness rechecks are intentional. Later agent-state/AGENTS writes can fail after durable commit; router notification can also fail (A-F014). Do not blindly replay a committed old-CAS operation or roll back accepted graph for ancillary notification. |
| Client acceptance | workflowDraftCoordinator.ts179–205; useCanvasPersistence acceptDraftWrite | Accepted revision/queue advances; graph/status/error projection is per canvas and retained notice per workflow. | Callback can throw after acceptance and leave operational error state (A-F052). Real production reachability remains conditional; callback tests mostly nonthrowing. A-F059 retained notices lack same-name incarnation. |
| Save capture | MenuBar.vue451–475 → rootWorkflowSave.ts48–90 | Exact initiating canvas/workflow + cloned graph; rooted resource identity rechecked; routeSave delegates nested case separately. | Tests prove captured root selection survives another active canvas and newer edits remain dirty before/after draft flush. This is not a global graph-session save. |
| Save freshness | useCanvasPersistence.ts591–609 | Flush local queue; fresh GET accepted revision; blocks if remote revision increased. | No response workflow identity, regressed-revision refusal or final coordinator/edit owner recheck in helper (A-F055). Main callers use exact resource checks; root-close additionally holds lifecycle lock, materially limiting newer-edit reset risk. |
| Saved publication | workflow.ts739+ → PUT /workflows/name; models/workflow.py158; workflow_store.py2756–2772 | Body contains graph only; service idle+identity locks, migration guard, containment/source capture, atomic saved document hash. | Caller incarnation/draft revision absent (A-F004). Backend capture rejects replacement during the operation but cannot reject an old request first admitted after recreate. A draft freshness GET and saved PUT are separate server operations, so another client can win between them. |
| Save finish | rootWorkflowSave.ts65–88; workflow.ts739+ | Saved commit → draft queue/flush rebases dirty_against_saved → compare exact local graph again → mark initiating canvas clean. | Newer local edit is preserved, never overwritten or marked clean. A draft CAS failure can follow an already successful saved write; saved graph commit and draft acknowledgment are not atomic promotion. Decide contract explicitly before adding wire fields/transactions. |
| Close with Save/Discard | App.vue854–965 | Captured actual panel object + canvas ID; per-canvas saving/discarding lease; mounted-target checks after awaits. | Close only on exact successful save with no newer edit; discard retains retryable committed draft/cleanup error and keeps tab if failure. This mitigates A-F055 ordinary close UI reachability; lower-level helper and other callers remain qualified gaps. |

### Root/draft/source contract consistency

Platform v1§2.2/4.1/4.3 and v2§12 correctly distinguish immediate canvas, accepted durable draft, saved/exportable artifact and browser fallback.
Their “Save promotes accepted graph” and “remote changes resolved before destructive operations” wording leaves the interleaving between freshness GET, graph-only saved PUT and later draft CAS unresolved.
Proposed clarification is a contract decision, not silently changing code to define the specification: capture exact accepted draft/incarnation at server Save admission or explicitly specify intentional historical graph capture with conflict/commit acknowledgment semantics.

Root draft GET additionally writes workspace-wide agent-state.json, client configs and AGENTS (workflow_draft.py498–574) for every addressed read.
Concurrent canvas reads can select agent context independently of UI active selection; A-F020 retains the explicit active-agent authority decision.
Draft request routing itself remains workflow-scoped, so this does not establish graph cross-contamination.
Mandatory agent context publication after graph commit is A-F014; optional client-config failures have separate isolation and should not be conflated.

API schema authority is already specified: OpenAPI generated graph/draft types are sole; A-F006 handwritten drafts remain admitted transitional debt.
A future incarnation change should update backend and generated caller contract together, without retaining a hidden stale handwritten body.
Public compiler, actual bound class/resource authority and validation node_tools must remain the single executable/schema source; carried pins must not be replaced by active name-only registry (A001/002 repaired portion, A003 adjacent availability remains open).

## Current-source dispositions supplied to the complete candidate inventory

These are sampled/current-source annotations, not blanket closure of their historical IDs.

| Canonical IDs | Current judgment / severity | Evidence and counter-evidence | Owner / trigger before repair |
| --- | --- | --- | --- |
| A-F001/002 | Bounded repaired carried executable/resource/materialization authority; adjacent package availability not certified. | First-wave accepted source commits in current main; all current compilation consumers use same canonical public boundary. | Platform compiler owner; a new source/package behavior change requires actual bound-class public control, not name-only metadata test. |
| A-F003 | Partial bounded repair; locality/same-package rebind repaired, exact missing-class GET/metadata consumers open. | M2 recorded disposition; editable unresolved import retained. | Platform registry/API + frontend schema owners; exact package/version+missing-class distinguishing control. |
| A-F068 + startup request cost | Structural fence retained; same-ID tree/list message/loading/error and pending duplicate repaired. | Current workflow.ts177–190,517–547,594–676, actual causal7 and preserved benchmark source proof. | Catalog owner; future other endpoint singleflight requires separate authority contract, no URL cache. |
| ROOT-F098 | Controlled selection defect repaired, bounded; no general foreground supersession or full-browser certification. | Current sync intent watchers/Tree events/App target cause and prior exact controls. | Presentation/canvas owner; protect same-name ordinary metadata and Browse. |
| A-F004/A-F059/A-F072 | Open high-risk first-admission/incarnation family; wire gap and retained notice risk current-source confirmed, runtime loss unproved. | Graph-only Save/CAS-only draft bodies; current generation captured after admission; outer response guard does not undo server commit or already acknowledged stale retained state. | API/store/session owners jointly; actual same-ID recreate delayed caller oracle and explicit absent-vs-stale legacy policy. |
| A-F061/A-F063 | Open high-priority recovery authority/conditional deletion source risks. | Catch-all load and editable catalog omission clear recovery; old-entry comparison separated from key delete. Current list migration hiding is a concrete new A061 extension. | Startup/recovery + workflow read owner; typedabsence/error and atomic conditional-delete public storage controls. |
| A-F062 | Open source-confirmed draft failure fallback, qualified replacement risk. | Catch-all dirty=false saved fallback; unseeded coordinator later admits pending newer graph at fetched CAS. Existing fallback tests do not distinguish endpoint500 from absent authority. | Root presentation/persistence; explicit failed-draft UX contract before permitting edits/replacement, preserve offline recovery. |
| A-F047 | Open superseded initializer publication source risk. | Coalesced init is correct; old initialization lacks final token versus resolveFromDraft. | Canvas persistence; one held init/explicit resolution owner control before change. |
| A-F049/A-F007 | Open cancellation/physical-lifetime contract, distinct local/HTTP/backend boundaries. | Local abort signal ignored in root adapter; graph_worker awaits AnyIO bounded worker without explicit raw-asyncio drain owner. | Client transport + backend admission/thread owner; raw cancellation actual held-worker witness, deliberate durable-write cancellation policy. |
| A-F050/A-F052 | Open response guard and commit-vs-callback distinctions, lower current reachability. | Current normal backend correct ID/revision; production callback simple bookkeeping. Existing tests nonmalicious and nonthrowing. | Draft coordinator/API; adapt one contract control only when owner packet selected, no speculative full rewrite. |
| A-F055 | Open helper-level critical/reset admission; ordinary root-close materially mitigated. | Exact root-close panel object/lifecycle lock/rechecks read; helper no final lifetime/id/lower-revision guard. | Persistence/caller owner; distinguish actual admitted helper path versus theoretical unlocked mock. |
| A-F014 | Open definite postcommit acknowledgment seam, P2. | Atomic draft before mandatory context/notification; neighboring workflow publication has isolation. No injected current-source fault run. | Draft/agent integration + notification owner; committed failure semantics and exact fault after durable commit. |
| A-F020 | Open global agent context authority decision, P2 conditional interleaving. | Every addressed GET writes active_workflow_id globally; graph route itself scoped. | Agent workspace owner; read versus explicit set_active policy and concurrent independent read oracle. |
| A-F168/A-F169/reviewer-F092 | Open producer invocation, presentation refusal and source-event ordering. | New/copy/import forms mutate live finalizers after await; applyGraph void may refuse; older WS active event awaits refresh then emits Open. | App/Menu/dialog/WS owners; narrowly captured invocation and committed-refusal semantics, preserve multiple canvas behavior. |
| ROOT-F024 | Open deferred dataset/NodePanel command owner, source-confirmed. | Picker await then current selected node/current canvas; existing immediate picker tests do not hold lifetime. | Shared consumer+canvas command owner; capture original registration/node incarnation and one-edit parameter semantics. |
| A-F006 | Open duplicate type authority, P3 maintenance. | Actual handwritten draft wrapper fields match today; v2 explicitly records debt. | API types owner; replace during related API contract edit with generated shapes and exact migration compile check. |
| A-F178, reviewer-F038, B-F190 | Open concise spec/doc reconciliation candidates; current source claims require owner decision. | Dependency dialog install-all vs old prose; plain Core IOModel vs Pydantic and required row_consumption examples; saved vs accepted draft Run wording. | Separate bounded cross-package docs task after review findings gate; preserve every essential feature and public schema authority. |

### One additional qualified projection candidate for independent triage

ROOT-F099 (supplemental, not added to frozen573): rootWorkflowPresentation.ts49 copies global workflowStore.missingTools rather than returning the addressed saved read's diagnostic tuple with graph/info.
loadWorkflow696–719 updates that global only when presentation is permitted and returns only graph; overlapping foreground continuation scheduling can expose another load's global diagnostics, while rejected background presentation must not assume the global belongs to its request.
App startup request guard prevents a superseded startup from mounting, and accepted validation node_tools can repair tool schema later; no incorrect badge or schema was reproduced.
Severity P3 qualified projection coupling, not an executable-identity failure.
Independent source review accepts this as a distinct qualified projection candidate; minimum future contract is a request-scoped immutable presentation record, not a global rewrite.

## Test strategy and architecture judgment

A component/store/coordinator/backend/native test with similar graphs can protect different acceptance boundaries; no blanket duplicate deletion is justified by fixture resemblance.
Keep rootWorkflowSave four tests: exact registered target, edit while save pending, microtask edit before flush, conflict refusal. They differ from coordinator queue/CAS and real browser storage witnesses.
Keep startup helper policy tests separate from deferred actual store/App ownership, but the plain Error('404') success oracle cannot support destructive typedabsence behavior.
Keep route-level mutation admission/CAS and service-level generation/saved/recovery checks; add only the missing adversarial boundary control when a bounded repair is selected.
Shared helpers must preserve exact production call path, teardown/drain, original failure, current module/dependency origin and filtering semantics; do not certify worker/PID from a fake public manager.
The complementary dedicated suite owner supplies lane selection, redundant-test candidates, setup cost and actual library/Core/Wetlands coverage beyond these samples.
No fullsuite, filesystem power-loss, real canceled request, native dialog/editor/viewer launch, live OS keyring, distributed restart or actual new profiling was performed.

## High-risk families outside the five maps — current source sample

This extension follows the original severity/family inventory, not a new entire-codebase audit.
These are original candidate IDs with additional current owner/source validation; priorities remain qualified, and lack of a new runtime control is explicit.

| Canonical ID / family | Current decisive source | Judgment / mitigation / next owner |
| --- | --- | --- |
| A-F018 import admission | workflows.py854–883 checks _ensure_unlocked then awaits UploadFile.read, then synchronously imports without idle mutation lease; WorkflowStore.ensure_workflow_mutations_available533–550 fences move journals, not execution. | Current high-risk route admission gap confirmed. Existing import423 test1635 tests already-running entry only. Hold actual upload-read while Run admits, then observe store/admission before selecting a lease repair. Preserve archive transaction/source validation. |
| A-F064 duplicate node serialization | workflowGrouping.ts70–107 common/tool/workflow fields omit viewer_additions; useGraphSync serializer91/108 and workflowGraph112/128 preserve it. | Current semantic field-loss mechanism, no grouping runtime loss executed. Owner frontend graph transforms; share canonical semantic node projection or enforce field parity with one meaningful grouped viewer declaration control, preserving interface IDs/edges/resources/source. |
| A-F066 carried templates versus catalog | workflowGraph.ts100–110,163–174 hydrates explicit carried nodes through getToolByName and reconcileOutputTemplates; outputTemplates15–30 clears missing/DataFrame and filters live path outputs. CanvasView829–842 uses this before mounting;1228 later actual node_tools is used for reconciliation. | Current qualified bound-hydration risk. Original authoritative graph is remembered/synced before later Vue serialization, and actual validation schemas mitigate some later metadata; neither restores every dropped carried template at initial hydration. Explicit user rebind legitimately reconciles. Owner frontend schema/compiler contract, distinguish bound missing/versioned node from deliberate rebind before repair. |
| A-F069 structural operation admission | workflow.ts342–357 rejects currently mounted identities;1033–1087 patch,1156–1185 folder move and1278–1308 direct move await without marking a structural in-flight admission fence. | Current qualified Open-versus-rename/move risk; final local-generation checks and mounted entry refusal real. delete/folder-delete have explicit workflowDeletionsInFlight ownership1224; do not label them unfenced or erase protections. Owner catalog/App/session; one held structural mutation plus actual registering canvas control. |
| A-F079 forward move provenance | workflow_store.py1028–1056 recovery restores moved saved metadata/draft path; normal move2971 calls _rewrite_moved_source_provenance, helper1199–1239 visits saved/draft/snapshot graphs. | Current incomplete forward recovery effect family. Embedded graph remains authoritative; risk is provenance/source refresh/navigation, not automatic compute corruption. Owner structural journal/source store, held fault before global provenance effect with unrelated parent bytes and idempotent recovery. |
| A-F082 migration writers | workflow_store.py1994–2016/2101 structure lock only;2180–2255 verifies source digest then atomic writes without workflow identity/snapshot lock; migration router348–362 does not supply execution lease. | Current qualified concurrency boundary. Pending-format guards prevent new ordinary editable root requests, backup/digest/forward journal protections valid; previously admitted/private writes remain a separate owner. Choose common admitted writer locks and stale-plan control before change, not GUI delay. |
| A-F083 nested lock acquisition | save2756 @_identity_locked→workflow_mutation351→sorted workflow_mutations358;validate_containment1551 calls separately @_identity_locked get_workflow2711 while holding destination; containment walker44 follows saved sources. | Current exact possible A→B/B→A inversion; RLock solves same-thread recursion only. Existing containment rejection is sequential. Owner store/containment, bounded two-thread schedule and coherent ordered snapshot contract; no observed deadlock or unsorted-lock blanket rewrite claim. |
| A-F087 source update versus editable draft | CanvasView1546–1596 checks clean/ID once then awaits freshness/saved GET/preview/apply/reset and uses live accepted revision, no lifecycle lease/edit epoch at continuation. | Current qualified high impact: source preview owns saved snapshot, not newer local graph; existing confirmation/hash/reset CAS constrain server state but do not express initiating UI edit owner. Owner source operation + canvas, held preview/new edit distinguishing test before repair. |
| A-F096 cross-workflow clipboard source | clipboard.ts145–170 copies source_workflow_id and graph references, no source bytes; CanvasView2839–2905 adds copied nodes without consuming source_workflow_id or prepare-embedding transfer. | Current source boundary mismatch with v2§6.3 destination-owned transfer. Same-workflow source already exists; catalog-only clipboard tests valid but do not cross this boundary. Owner clipboard/source store, actual custom bytes and existing same-ID destination source before admitting paste; no code-injection/output failure claim. |
| A-F106 deployment source opening | editor.py61–70 guarded /open-node;139–153 /status launch and /open plus207 /open-tool lack mode/unsafe dependency. App669 injects EditorService in both modes; configured mode callback is process-owned. | Current high-priority implemented-policy mismatch despite ROOT002/003 repair. v1§2.4 unsafe=false disables server source-opening. Existing router tests no webapp/refusal case; prioritize entrypoint-consistent configured-capability refusal before dispatch, preserve desktop. No restricted HTTP/native run or internet-exposure exploit claimed. |
| A-F048/051/053 nested persistence | nestedSnapshotPersistence145–286 accepts inside transport, resolution GET controller untracked by dispose; latestAccepted graph may differ from coordinator.currentGraph; useGraphSync273–294 retains per-session writer and first callback. | Current response/disposal/normalized projection qualified boundaries. Ordinary PUT forwards signal and checks UUID/next revision, strong protection. CanvasView265 callback goes shared nested session store, downgrading A053 old-mounted-observer concern; UUID reuse constrained. Owner nested persistence/session, held resolution/disposal or normalization only if policy selected, not generic writer replacement. |

CanvasSessionRegistry69–91 keeps one immutable descriptor and registration token per mount; tokens change after unregister/remount and existing tests assert this exact contract.
That owner is available for future deferred consumers; it should not be replaced with a second global registry.
Canvas command resources enforce disposed state, while parameterless facade resolves active resource at invocation (useCanvasCommands141–160,200–315); this proves why an earlier picker/request must capture registration, not why synchronous active commands are wrong.
This high-risk sample covers source migration, recursive locking, semantic serialization, clipboard bytes and configured policy beyond startup/performance.
It does not certify filesystem crash/recovery, concurrent process integrity or native/code-server readiness; those owners and triggers stay explicit.


### Qualified original headings without numeric rank

Missing rank in a heading is not low priority: the body preserves its original qualified severity.
reviewer-F086 (P2 destructive target) remains current: StorageSection147–155 keeps installed demo workflow_id but discards returned identity_generation; captureDeletionRequest104–117 takes whichever incarnation the current catalog now knows. DemoWorkflowService120 supplies provenance-proven generation. Generic delete guards protect their captured current target, not equality with the installed-demo evidence; the existing test supplies generation but asserts only deleted names. Owner demo consumer/generic delete admission, future held status/replacement control; no demo deletion loss executed.
reviewer-F087 (P3 presentation) remains current: StorageSection78–100 refreshes workspace/demo info without root/request/disposal owner. Ordinary Settings policy/root retarget acceptance is not disproved; stale reveal path/demo affordance is the qualified risk. Owner storage/settings presentation; hold old status across accepted current root refresh before repair.
reviewer-F091 (P2 socket lifetime) remains current: useWebSocket537–550 retires state.socket before old asynchronous close without detaching handlers; new connect resets intentionallyClosed, and old onclose460–463 cancels mutable singleton pending ACKs/schedules reconnect. Direct pointer replacement429–441 does detach, an important distinct mitigation. Owner WebSocket connection epoch/pending ACK/reconnect recovery, future held retired callback against newer socket; no actual ghost/network loss run.
reviewer-F100 (P2 semantic contract) remains current: workflow_draft_operations134–166 DeleteNode filters a shared input only if ALL targets survive, whereas workflowGraph25–37 prunes removed targets and retains the same input if B survives. Structural validation accepts the resulting dropped input and cannot restore it. Canonical v1/interface contract preserves surviving targets. Actual semantic owner tests exercise explicit input deletion, not DeleteNode with shared A/B exposure. Owner semantic graph transforms/agent draft authority; extend that existing operation fixture with surviving immutable port/target content, not a new whole agent/browser journey.
These four original IDs extend the architecture coverage to confirmed-selection provenance, retired connection publication and duplicated frontend/backend mutation semantics beyond the common task maps.


## Repository and dependency owners

| Layer | Owns | Does not acquire authority merely by projecting it |
| --- | --- | --- |
| Vue panel/store/session | User gesture, local selection, pending request/error/loading and owning canvas interaction | Catalog persistence, accepted graph validation, physical worker completion |
| REST models/generated types | Strict graph/request/response wire shape and transport | Executable tool class, current workflow incarnation, backend admission |
| DatasetStore / WorkspaceService / SettingsStore | Managed catalog and bytes; active root resolution; configured deployment policy and preferences | A browser dialog's confirmed selection, ordinary local filesystem security for every tool |
| Workflow store/draft/compiler | Saved versus accepted draft/private snapshot, captured sources, identity generation/CAS, request-local materialization | Result history or an independently compiled mutable UI graph |
| ExecutionManager / coordinator | Run admission, captured workflow/revision/storage, run identity/status and retained remote acceptance | Thread/process termination from logical terminal state alone |
| BioImageFlow scheduler/backends/storage | Graph semantics, node/cache provenance, row/batch dispatch and public result assets | Platform graph/UI persistence or shutdown of a borrowed manager |
| Core | Worker-safe IOModel/type metadata, row-consumption declarations and strict task/result envelopes | Pydantic validation, orchestrator imports, site resource enforcement |
| Wetlands | Managed environment generation/pools, task transport/cleanup and environment operation completion | Platform Run admission, graph editing, arbitrary callback liveness or OS reclamation certification |

The direction is frontend → platform transport/services → public BioImageFlow → Core/Wetlands.
The concrete main-path graph is RunButton/useExecutionLock → execution store/ExecutionRequest → execution router/reserve_start → draft authority/GraphValidationService/GraphCompiler → graph_builder/source capture/public Workflow.from_dict → DefaultEngine scheduler/dispatch → Core worker_protocol and Wetlands pool/task; result publication returns through public Storage → ResultStore/node models → table/viewer consumers.
The dataset graph is DatasetsPanel/store/API → request root provider → DatasetStore writer/snapshot/bytes → resolve selection → originating canvas command owner → accepted draft → built-in Files DataFrameTool, with the browser picker returning only a path/null and no independent filesystem authority.
Separate platform GraphState Pydantic models, orchestrator Pydantic adapters, Core IOModel declarations and versioned worker envelopes have distinct responsibilities; their existence is not itself redundant business authority.
Handwritten dataset/draft/execution client shapes alongside generated OpenAPI models are maintenance debt, while client upload-progress options and canvas intent state remain legitimate client-only types.
Large files are candidates for owner-based decomposition, not sufficient evidence to rewrite them: current ExecutionManager, WorkflowStore, App, RunButton and DatasetsPanel still mix multiple substantial responsibilities, but any extraction must retain admission/publication identity and existing public behavior.

## Dataset task map: browse, upload, select, delete and use Files

### Normal browse and data publication

1. `DatasetsPanel.vue:346` mounts and starts `void store.refresh()`.
2. `stores/datasets.ts:64–68` concurrently requests dataset and folder lists through `api/datasets.ts`.
3. `routers/datasets.py:57–65` captures the request's current managed root and creates DatasetStore; `app.py:1063–1073` resolves that root from explicit AppConfig or the current WorkspaceService.
4. `dataset_store.py:179–187` creates the directory, initializes SQLite and reconciles filesystem/catalog; `list():352–360` reconciles again and returns newest-first records, while `list_folders():362–367` independently sorts logical folders.
5. The client publishes both returned arrays together after Promise.all, constructs a Map-backed tree, sorts folders before files and filters display/original names plus logical folder ancestry (`DatasetsPanel.vue:256–318,400–428`).
6. Logical folder/display changes preserve the physical path/ID; selection expansion uses the backend `resolve_selection():564–581` snapshot and deterministic order rather than making a Files node subscribe to a mutable logical folder.

SQLite snapshot reads and cooperating writer transactions are separate owners.
Backend list requests do not share a catalog revision envelope, so the two HTTP responses need not represent the same catalog moment.
Client refresh has no request/workspace/accepted-mutation epoch, loading/error owner or stale-result fence; a held list can erase accepted upload rows, and a rejected initial list leaves an unhandled promise with an empty presentation (ROOT-F017/027).
The Map-backed tree is already present; repeated ancestry `.find` walks are a conditional deep-folder cost candidate, not proof of replacing the Map or of gaining the entire measured flat-search time.
The recorded same-request constructor+list double reconciliation is statically redundant candidate work; any later repair must retain external/legacy file visibility, missing-file removal, catalog revision and request-local freshness, without a permanent directory cache.

### Upload, interruption and retries

1. Browser File objects enter `queueUploads()`; the store admits at most three requests and keeps pending entries and per-request AbortControllers (`datasets.ts:103–219`).
2. The client submits one multipart request per file with folder ID, progress and abort signal; backend upload loops retain earlier per-file successes and return typed individual errors (`routers/datasets.py:114–173`).
3. DatasetStore writes unrecognized exclusive staging and completes short writes, then `_publish():410–453` acquires BEGIN IMMEDIATE before name/folder decisions, reserves an unowned target, renames complete bytes and commits the catalog.
4. Known uncommitted failures remove only owned staging/final bytes while the writer remains held; accepted or ambiguous commits retain recoverable complete bytes. Multipart cleanup cannot roll back an already accepted file.
5. Accepted responses upsert visible datasets and selection; abort suppresses success publication. Network failure or abort acknowledgement is not proof that the backend did not store complete bytes.

Accepted A/D2 publication controls cover two-store held streaming, short/zero write, staging cancellation/close failure, folder deletion during stream, commit ambiguity, collision ownership and real cooperating writer ordering.
These repairs retain ROOT-F006/007/009/010/011/015 invariants and do not authorize removing legacy recovery or claiming filesystem+SQLite crash atomicity.
ROOT-F013 original-name fidelity remains open because `_publish` reconstructs original names from sanitized names; natural suffixes/truncation cannot be recovered losslessly that way.
ROOT-F014 remains open: an UploadFile/Form route causes framework multipart parsing before the Content-Length dependency, so the comment/test's pre-parser claim differs from actual admission; per-file streamed cap is a separate valid guarantee.
ROOT-F016 remains a concrete client attempt gap: immediate retry reuses the same UploadEntry, and the old aborted catch can change its new uploading status to cancelled; finalizer controller identity protection does not fence entry publication.
ROOT-F028 remains destination ambiguity: retry UI passes current `uploadFolderId`, while UploadEntry does not retain the original folder.

### Destructive and asynchronous actions

`confirmDelete():DatasetsPanel.vue:579–591` opens one shared dialog and asynchronously fetches counts using current selected IDs; `deleteConfirmed():593–610` later submits current selected IDs with that shared revision.
Backend `delete_selection():589–626` correctly acquires the real writer before revision/selection checks and returns successful IDs plus per-file errors, preserving failed descendant folders.
The revision protects catalog freshness, not the equality of the user's confirmed selection: cancel/reopen or selection change can substitute a different target set (ROOT-F023).
The minimal later owner is a captured dialog attempt + selected IDs + accepted preview revision, with stale completion suppression; no new backend preview authority is automatically required.
Folder moves use Promise.all then refresh in finally (`DatasetsPanel.vue:647–666`); first rejection may start refresh while other PATCHes are still committing (ROOT-F029), so outcome settlement and refresh ownership need a bounded repair rather than falsely promising a multi-file transaction.
`createFilesNode` and `setSelectedFilesNode` await resolution then call a parameterless active command facade (`:687–706`); ROOT-F024 is confirmed by the facade's invocation-time active resource lookup.
Capture the originating canvas registration/incarnation, selected node identity and operation intent before the await; backend path resolution and the canvas's graph admission are independent checks, not replacements for that capture.
The selected Files-node shortcut still recognizes `toolName.toLowerCase()==='files'` (`:330–336`), so an explicitly bound same-named custom tool can have a different contract (qualified ROOT-F026).
The public built-in Files class (`common-tools/files.py`) preserves explicit file order, verifies file existence, or performs a sorted singular-directory scan; Directory and Files remain mutually exclusive.

### Workspace and deployment limits

WorkspaceService uses administrator-managed `<root>/<user_id>/workspace` in webapp and user-editable workspace_path only in desktop.
Configured mode/workspaces_root mutation fixes are accepted, with frontend settings PATCHes sparse; the root contract is not inferred from a mutable response preference.
SettingsPanel's workspace_path handler refreshes only workflow/storage/demo state, while datasets are browser-only in the normative dock and desktop edits do not normally expose that panel; do not present this as a default webapp UI workspace-switch exploit.
A general dataset request/publication workspace epoch still matters for programmatic/reconfiguration boundaries and future authenticated operation; ROOT-F017 already records that qualified scope.
AppConfig/defaults, not live datasets_root/max_upload_size preferences, drive request configuration (ROOT-F022); settle admin-configuration versus inert preference semantics before retargeting storage.
v3 authenticated multi-user isolation is proposed, not implemented acceptance; managed chooser paths alone do not prove sandboxed arbitrary tool execution.

## Run task map: accepted revision, preparation, compute, Stop and results

### Local Run and selected/retry variants

1. `RunButton.vue:runCore` captures canvas ID/workflow identity, crosses `ensureFreshForCriticalOperation`, flushes pending validation/persistence and captures graph, validation and accepted draft revision.
2. Out-of-date confirmation compares graph/revision again and repeats preparation if they changed; active-target checks prevent a late local confirmation from redirecting Run.
3. `useExecutionLock.ts` applies selected diagnostic filtering then synchronously calls exec.run, which enters starting before HTTP; the request sends only workflow ID/revision/nodes/mode/retry identity (`execution.ts:497–595`, `models/execution.py:ExecutionRequest`).
4. `routers/execution.py:146–251` acquires reserve_start before loading draft authority, rejects stale draft revision, captures workflow generation/storage, and rechecks after compilation/Clear preparation; a storage-context retry keeps the same pending execution identity.
5. `_start_reserved():execution.py:632–746` performs one request-local validate+compilation of the complete accepted graph, limits only post-compilation diagnostics to selected/upstream scope, refuses unknown/empty/unresolved/global errors and uses public workflow.nodes.
6. Build captures current owned source bytes and binding before public `Workflow.from_dict(... validate_only=True,partial=True,auto_install=False)`; actual bound capability chooses Direct/Wetlands and materialized resource errors check the loaded class (`graph_builder.py`, `graph_translator.py`, `materialized_resources.py`).
7. Compute retains immutable ExecutionContext/run context and per-workflow storage, dispatches on a thread, materializes disposable latest outputs and independently retains result exports; events are fenced to the current running context.
8. Stop asks the captured Workflow to cancel cooperatively; terminal processing retains prior completed/cached nodes and records cancellation instead of starting a replacement graph.

The accepted carried-class/resource/engine repairs (A-F001–003 relevant repaired portions) preserve unbound catalog discovery and explicit rebind, while Core resource declarations describe floors/concurrency requirements rather than asserting OS allocation enforcement.
DataFrameTool runs in the orchestrator even with a Wetlands graph; a DataFrame-only Direct result is not worker isolation certification.
Processing rows/batches encode strict task/node/invocation/cache-attempt/retry identities and position+row-index correlation in Core worker_protocol, validate returned correspondence, and use independent mapped/collective input-row semantics.
Worker payload input declarations are plain Core IOModel, not Pydantic; orchestrator schema.py builds validation models separately and excludes orchestration from worker imports.

### Physical admission and error boundaries

`execution.py:774–782` creates an asyncio task around `asyncio.to_thread(_run_sync)`; `_on_run_done():1331–1346` maps task CancelledError to exc=None/success, and `:1507–1512` releases running state/graph/workflow/task ownership.
Cancelling the awaiter can leave compute/materialize/export running physically; B-F024 is still an open source-established high-risk ownership gap, not a newly executed corruption or a claim public Stop cancels that task.
Graph compilation/draft/Clear offload uses AnyIO's bounded run_sync (`graph_worker.py`); its default cooperative cancellation protection is not proof against every raw asyncio cancellation direction (A-F007).
The future causal control must hold the real offloaded body, cancel its owning awaiter and observe thread exit, run status and admission before/after release; do not use sleep or a terminal flag as physical completion.
ExecutionManager's cooperative Stop test releases a fake compute Event and then drains its normal task; it protects that distinct path and cannot substitute for this physical control.
`_ExecutionEnvironmentManager` shares a reentrant preparation guard with background general-environment refresh and submits through a public adapter; do not globally close borrowed managers or mutate manager methods for logging.
Current manual ToolEnvironmentService.recreate still performs preliminary best-effort stop then get_or_create(True), aliases environment targets by environment/tool/package and lacks the aligned T1 exclusive physical admission boundary; B-F013/B-F014 and the preserved T1 packet remain open.
The library main get_or_create(True) still stops cached ownership and delegates matching-ready reuse; accepted isolated force WIP now uses strict close/public removal/provision(False), but is not integrated or floor/lock aligned.
The published Wetlands2.5 Operation completion API solves completion/outcome and callback-selfwait publication; it does not prove public Task cancellation retirement quiescence (ROOT-F053), prevent late queued sends (ROOT-F056), or close platform offload admission.
Current library `_WetlandsTaskTracker.cancel_and_drain` inspects task.state.terminal and waits task outcome; preserve separate lower cleanup-owner questions and original-error precedence rather than treating the new Operation API as automatically applicable to tasks.

`_export_managed_result` still has destination/context/digest work outside its unavailable-export boundary (B-F025); a retention failure can turn successful compute into failure, while the intended export-state owner should remain distinct.
ResultStore modern capture/load verifies exact run/node/result-key/record identity and canonical provenance via public Storage; retain this fail-closed modern path.
Its legacy branch captures latest again after capture returned None (`result_store.py:36–49`), allowing legacy→modern pointer advance to bypass the first modern provenance gate (B-F026); a held pointer transition is the minimal missing distinction.
NodeDataResponse still accepts Any-valued cells with no explicit nonfinite JSON policy, while Node Data routes pass pandas records directly (B-F043); the recorded Pydantic/FastAPI default null conversion is a dependency-qualified static inference, not a new endpoint serialization run. Valid infinity must not be changed into a finite scientific result merely to satisfy JSON; model/API/display semantics need one explicit presentation decision.
OME conversion still writes one shared `<cache-key>.tmp` before replace and unlinks that same path on failure (B-F044); this is a multiple-process/shared-cache ownership risk, not a demonstrated same-event-loop race. Unique owned staging is the narrow future direction if that execution model is supported.
Traditional image/thumbnail/Reveal and filtered CSV calls still cannot carry the table's ResultArtifactIdentity (B-F045), unlike pinned table query and the exact Napari output action; a record validated after a later latest-pointer lookup is not proof it is the displayed table record.
Clear still rewrites every downstream unexecuted status to out_of_date after its refreshed retained-output-aware plan (`execution.py:1769–1778`, B-F188); compare that immediate response to authoritative draft GET for a never-produced chain, while preserving deliberate staleness of retained outputs.
The `/graph` output-schema router still dereferences `result.workflow._nodes` after a BuildOutput(None) (`routers/graph.py:235–251`); ROOT-F019/020 remain current, and public workflow.nodes already exists as an appropriate owner direction for a later narrow repair.

### Managed Run branch

RunButton captures exact workflow/draft/target/profile and preflights, optionally awaits data resolution, then consumes a strictly bound one-use backend token and registers the returned public cluster handle.
It does not apply the local post-await active-owner barrier before submission or resolve pending dialogs on component disposal (B-F179); classify as command-lifetime/reentry contract, not wrong-target backend execution, because captured binding remains exact.
PreparedSubmissionTokenManager.consume pops the intent, awaits asyncio.to_thread(submit), closes it in finally, and only after a return does the route register the durable accepted identity (`execution_preflight.py:100–165`, `routers/executions.py:90–119`).
Raw route-task cancellation can therefore lose returned public acceptance while physical submission continues (B-F041); browser disconnect does not automatically establish that cancellation direction, and no scheduler allocation was reproduced here.
Keep the existing uncertainty response/attach-first/no-replay rules and public cluster owner; do not invent private launcher scanning or a new submission ID to compensate for unknown acceptance.
The coordinator's cancel uses the retained execution ID/public adapter and refresh; retry/cleanup require their exact persisted public plans and confirmation, and result transfer remains independent from succeeded compute.
Deep remote retry/storage/SSH/scheduler paths were not re-reviewed in full here; their original M1 findings remain triaged candidates, not accepted current certification.

## Current finding triage and next bounded packets

| Existing family | Current disposition | Owner and minimum next decision/control |
| --- | --- | --- |
| ROOT-F001–003 | Repaired within accepted credential/configured-policy scope | Preserve compensation/pre-replace and loaded process-mode guards; ROOT-F004 independent writers and initial/distributed root capture remain separate |
| ROOT-F006/007/008/009/010/011/015 | Relevant staging/cooperating admission/delete/partial-error mechanisms repaired in accepted A/D1/D2 | Retain real two-store writer/staging/commit-byte tests; no crash/external-writer atomicity claim |
| ROOT-F013/014 | Open metadata/early-parser source gaps | Dataset owner; original submitted name and true admission boundary controls, preserving safe naming and streamed cap |
| ROOT-F016/017/027/028/029 | Open client attempt/publication/failure/destination/partial-settlement gaps | Dataset store/panel owner; one coherent pending/accepted ownership packet, exact deferred promises and captured original destination |
| ROOT-F023/024 | Open P1 confirmation and canvas-owner gaps | Dataset + canvas lead; held selection/dialog/canvas switch controls before any destructive/misrouted gesture fix |
| ROOT-F018/022/026 | Defer/contract decision: generated types, inert preferences, exact Files capability | API/settings/library owner; settle actual supported identity/config states before extraction or new endpoints |
| Dataset double reconciliation | Missed M1 cost mechanism, measured/queued | Request/store owner; one request-local freshness control and same workload measurement, no persistent cache |
| A-F001–003 repaired portions | Retain accepted carried-class/resource/requirements repairs | Compiler/library owner; actual binding beats same-name catalog; broader availability/version cases remain explicitly scoped |
| A-F004 | Qualified pre-admission incarnation wire gap | Lead/API owner; inspect old request admitted only after same-ID recreation, not merely late response suppression |
| A-F016 | Current source-established Python-authoring/archive mismatch | Source/archive owner; producer's v2 four-key envelope versus consumer's exact v1 three-key extraction, with an actual captured custom-source fixture |
| A-F007 / B-F024 | Open high-risk raw async-versus-physical completion seams | Platform execution/draft owner; causal held-body admission/status control, independent of cooperative Stop |
| B-F001/013/014 | Isolated force source WIP accepted; main manual/T1 alignment held | Library/platform lifecycle owners; published2.5 floor/lock/version closure then strict public recreate and physical admission evidence |
| B-F007 | Owning Operation fix and published2.5 accepted | Wetlands owner; preserve normal result behavior and public completion limits, not broad Task/PID closure |
| ROOT-F053/055/056/057/069 | Qualified lower cleanup/admission/retry risks remain open | Wetlands owner; distinct cleanup-owner/queued-send/attempt-start/disposal/provision verification controls; no private platform workaround |
| B-F041/179 | Open qualified managed submission/command lifetime | Managed execution/frontend owner; held public submit/intent disposal controls retaining exact token and uncertain attach semantics |
| B-F025/026 | Open export-status boundary/legacy identity recapture | Execution/results owner; destination/digest error and legacy→modern pointer controls, preserving compute success/history |
| B-F043/044/045/188 | Current qualified scientific presentation/cache staging/result pinning/status-parity seams | Results/model/frontend owners; nonfinite policy, shared-process staging, held table→latest identity and never-produced Clear/read controls, no native or numeric recomputation needed |
| ROOT-F019/020 | Current absent BuildOutput/private-library caller defect/debt | Graph transport/library owner; typed absent output refusal and public nodes access, existing metadata schema preserved |
| B-F042 | Current missing node Reveal desktop guard | API policy owner; configured webapp refusal before mocked native dispatch, preserve desktop exact-result functionality |
| ROOT-F038 | Open mutable IOModel declaration default aliasing | Core owner; explicit instance-default policy and scalar/mutable control, no Pydantic dependency/blanket coercion |
| B-F020/B-F137 | Recorded P3, still unmeasured/deferred | Environment inventory/Core protocol owners; request-local scan counts or supported payload cost, no cache/duplicate image-pixel claim |
| reviewer-F038 / A-F178 / B-F190 | Confirmed current source-authoring/dependency-dialog/Run documentation contradictions | Library/platform docs owners; concise coherent runnable skeleton + correct explicit install/draft behavior, preserving features |
| ROOT-F031/032 scientific family | High-risk known scientific candidates, not runtime-certified by these maps | Package scientific owner; retain harmonic/unit/numeric oracle obligation; phasor lifetime still passes fundamental frequency after discarding harmonic in current source |

The table is a sampled high-risk/current-task/cross-layer revalidation, not all 573 original IDs.
The combined gate must inventory the complete original ID set once, retain known qualifications and give unreviewed/deferred families named owners/triggers; do not promote every candidate to a confirmed bug or declare this report complete M1 replacement.

## Normative coherence and concise-doc strategy

v1 owns implemented dataset management/chooser modes; v2§16 owns Files inputs and overrides desktop Datasets visibility; v2§9 owns accepted recursive Run/results; distributed spec owns managed target/attachment; library specs own graph/tool/row/cache/resource semantics; v3 auth is future proposal.
Preserve these separate authorities and use short linking deltas rather than merging everything into one manually transcribed specification.
Current v1 dependency dialog says it does not install packages, while MenuBar and its mounted controls implement explicit install-all exact versions/partial failures (A-F178); correct the description without making passive checks install.
User run guide says saved workflow, while GUI/server execute accepted draft including unsaved edits (B-F190); correct the noun/authority without adding Save as a requirement.
Library custom_tool/tool_packaging examples and v1 Cellpose concrete example omit required RowConsumption; plain inner Outputs examples also lack IOModel kwargs construction, and packaging's eager orchestrator factory export violates worker import direction (reviewer-F038).
The library's actual specification correctly distinguishes Core plain declarations from orchestrator Pydantic models; do not remove Pydantic validation globally when making prose shorter.
Trusted Python authoring still selects custom sources only from the exact three-key archive envelope (`workflow_sources.py:504–525`), while current public library serialization adds viewing_requirements as a fourth v2 key whenever sources exist; A-F016 remains an actual producer/consumer format mismatch, and the existing Python-helper freshness test returns an empty workflow with no custom source. Preserve portable viewers/source hashes and use the public supported-envelope contract rather than another ad hoc key list.
Mapped versus collective describes input-row meaning, not worker concurrency/output cardinality; DataFrame positional inputs, immutable interface IDs and worker-safe image/shared metadata remain essential.
The documented broader Path/str/SharedArray runtime validation adapter remains an explicit implementation gap; narrower constant builder behavior is not silently accepted as the complete desired contract.
Resources state author floors/concurrency caps and site allocation separately; no schema wording should promise local CPU/memory/GPU isolation that was not actually enforced/observed.
Core processing result validation explicitly correlates task/node/invocation/cache-attempt/retry/mode and ordered row identities, but application-defined DataFrameTool summaries can still discard those identities: ParameterSweepResults resets each branch index and concatenates ordinally (A-F114). Its normal shared lineage mitigates shipped recipes; changed upstream ordering/cardinality needs explicit helper policy and a numerical/identity oracle before claiming a scientific failure.

## Evidence and validation strategy

Read actual owning test bodies: dataset staging/CAS/two-owner/partial-byte controls, dataset store abort/progress and panel Files/drag/folder tests, Run freshness/confirmation/revision/local canvas controls, manager Stop/selected scope/admission tests, router stale draft/replacement/storage retry selectors, Core missing-row/default scalar controls and strict worker correlation.
These layers are intentionally distinct: mocked panel commands do not certify backend storage; a real SQLite writer test does not certify PrimeVue dialog identity; Direct execution does not certify worker/PID; package wheel controls do not certify platform admission.
No deletion of apparently similar tests follows from this review; The dedicated suite section distinguishes unmeasured setup/redundancy candidates from lane decisions, using the precise uncovered distinctions above.
During later repairs use causal owner selectors first, reuse meaningful retained controls, then the smallest documented completion gate; cross-stack API/runtime changes require app scope, package-loading/published compatibility require the milestone full/certification gate, and desktop remains M5.
Keep original failed invocations/skip/unrun/blocked phases and exact source/dependency/fixture/runtime projections when assembling unchanged passing phases.
Do not stack quick/scoped/full or repeat Sphinx for every status sentence; consolidate consequential specification changes and report completion once.

## High-risk family deepening beyond the common-task maps

The current complementary annotations now cover 80 original IDs, with 104 bound source/spec/test paths and added explicit targeted ranges; this is not a count of whole files fully reviewed or of confirmed runtime bugs.
The source review deliberately revisited high-risk public archive, executable origin, cache identity, exact numeric identity, shared-memory transport, output replacement, distributed retry/cancellation/reference admission and physical cleanup owners before selecting priorities.
It also checked unranked finding bodies rather than assuming headings without a severity word were low risk.

| Original family | Current source judgment and mitigation | Owning follow-on acceptance boundary |
| --- | --- | --- |
| A-F024/026, A-F138 | Public single-file filename/bundle source-ID containment is weaker than platform staging; same-ID bundle import can reuse a module despite changed accepted content. Ordinary content-derived source IDs mitigate the cache case. Example worker entry imports orchestration packages not guaranteed by GENERAL_ENV. | Public source/archive owner must distinguish unsafe extraction before writes and valid changed-content bundles; package authoring owner must use source-disabled worker import, retaining trusted Python functionality and separate factories. B independently owns A024/A138 confirmation. |
| A-F036/041 | Exposed input/invocation bindings can publish parent interface mutation before final admission refuses; the current source retains partial source-column preflight, but not all missing-required/refusal checks. | Public rejected invocation must preserve the original graph/interface; retain legitimate existing ports and valid/defaulted invocation. This is an exception-state owner issue, not a reason to replace nested graph architecture. |
| B-F067/068 | Logical signature omits qualified class origin while captured source hashes do participate via version. Cached frame loading returns values without the captured immutable record; later provenance recaptures current selection. Coordinated platform Run/Clear and first-winner cache selection mitigate normal paths. | Two valid same-name/version origins and a public shared-storage removal/reselection schedule must distinguish executable/cache provenance; no claim all source changes collide or normal publication always overwrites a pointer. |
| B-F074/115/134 | Canonical DataFrame cells pass through iterrows, leaving a mixed large-integer/float coercion question. Raw SharedArray helpers omit object-dtype safety; codec asdict flattens the typed descriptor before the worker's direct Arguments construction. | Core/library owning numerical/typed controls must preserve exact scalar identity, reject unsafe raw dtype before allocation/attachment and retain typed SharedArray through the actual Wetlands producer/consumer. Direct integration bypasses that codec and Parsl refusal remains intentional. |
| B-F080 | Initial no-replace export refusal is valid; after staging, the final destination backup/replacement no longer checks no-replace authority. | Introduce a foreign destination between staging and final admission; preserve explicit whole-tree replace, rollback and owned staging cleanup without overwriting the new unapproved target. |
| B-F049 | Current ImageCell omits available result_identity; the real Fiji route refuses absence before native dispatch, while the mocked200 component oracle explicitly expects the identity-less body. | Narrow caller/schema/oracle repair can be verified without desktop launch; preserve pinned exact-result selection, legacy refusal and final M5 desktop certification. |
| B-F168 | Bounded repaired in current package installer: exact components, lstat/resolved ancestry, captured identities and recheck precede owned retirement. The thin route still delegates to the corrected owner. | Retain accepted selected-target/quarantine controls; no new uninstall rewrite or blanket arbitrary external filesystem atomicity claim. |
| ROOT-F031/032, A-F114 | Higher-harmonic scientific metadata/API and ordinal result-summary lineage remain distinct known candidates. Their numerical oracles were not rerun here; normal first-harmonic/shared-lineage recipes mitigate the sampled cases. | Scientific owner must establish pinned upstream contract and known higher-harmonic values or changed row ordering/cardinality before affected tool release; do not call status-parity B188 a numerical algorithm defect. |
| B-F131/132, reviewer-F072/076 | Retry recompute replay checks absence even after child publication; same-plan launch happens outside allocation guard. Exclusive logs/claim fencing prevent two successful local owners but do not prove losing acknowledgments are harmless. Gateway submission/cancel snapshots and cleanup/reference admission lack a shared final authority boundary. | Exact public controlled phase schedules must preserve one accepted child, attach/no-replay uncertainty, durable pre-submit cancellation and retained references. No remote job or real race was executed. |
| ROOT-F053/063/069 | Task canceled acknowledgment can precede an existing retirement owner; launched cleanup skips live-leader identity validation after poll reports exit; failed provisioning cleanup drops its runner retry handle. Fatal admission, prompt cleanup, structured failure and stronger attached-session checks mitigate different paths. | Proper Wetlands owning packets require held cleanup/second cancellation, genuine descendants versus recycled group, and retained failed-cleanup owner. Operation completion2.5 is not a physical Task/PID certificate and must not be used to close these findings. |

Additional scoped current-source confirmations retain reviewer-F088/089 OMERO confirmation index and late successful form reset, reviewer-F095 catalog snapshot overwriting newer active/environment updates, reviewer-F096 malformed user-file decode policy, reviewer-F097/098 malformed PyPI shape/latest-version selection and reviewer-F081/090/099 truthful clipboard/capability/notfound reporting.
No real keyring, clipboard, native viewer, live malformed index or remote scheduler was accessed; these remain narrowly source-qualified with concrete owner/control triggers in the annotation JSON.
B-F191 Clear invalidation versus retained bytes and B-F192 default/UI dev-mode wording are current documentation contradictions for the same future concise-doc packet, alongside A178/B190/reviewer038.

The proposed post-gate order should first settle data-loss/destructive or wrong-owner admission and physical ownership policies, then select minimal causal repairs, rather than promoting every P1 source candidate into one broad rewrite.
Published Wetlands2.5/library force floor+lock alignment is a coherent dependency packet; platform T1 admission follows only after the correct public library contract is aligned and accepted.
Public archive containment, exact shared transport/cache/scientific contracts and managed reference/cancellation remain named release prerequisites for their affected behavior, not silently deferred because the five everyday maps are complete.
Lower-impact form/capability/metadata/doc repairs can be grouped by one owner, reusing existing selectors and a proportionate completion gate after the architectural decisions are recorded.

## Explicit uncovered and critical unknowns

This report does not exhaustively re-read every API/tool/remote scheduler/scientific algorithm, all 573 source mechanisms, all managed-viewer/OMERO/agent operations or every worker transport/OS cleanup path.
The complete original finding inventory, other three task maps and dedicated suite review are part of the same supplemental gate.
Dataset server upload acknowledgement under arbitrary connection/process death, arbitrary external writers, deep cyclic malformed catalog rendering and authenticated per-user isolation remain separate limits.
Raw asyncio cancellation/admission, remote lost-acceptance and Task physical retirement are source risks awaiting causal diagnostics; publication2.5 does not close them.
Same-ID caller incarnation contract, mutable IOModel defaults, Files capability recognition and dataset preference authority require explicit owner policy before changes.
The accepted force WIP/private environment and main installed dff/lockedWet2.4.2 remain different source/runtime projections until reviewed publication floor/lock/version closure.
No final Firefox/native/full-worker acceptance, universal performance assurance, exhaustive correctness or blanket architectural refactoring is claimed.


## Dedicated test-suite architecture

### Architecture and evidence layers

| Layer/owner | Existing fixture authority | What meaningful evidence establishes | Important limit |
| --- | --- | --- | --- |
| Platform pure models/service owners | Real tiny typed fixtures, isolated filesystem, deterministic catalogs | Validation/identity/public returned value and owned state transitions | Root conftest still imports the app and prepares runtime directories even for pure selectors; overhead unmeasured |
| Platform ASGI/router owners | Actual routes/services with injected registry/managers and temporary stores | API admission/error shape, disk/catalog revision, publication/CAS barriers | Generic ASGITransport client does not enter application lifespan; fake managers cannot certify worker drain |
| Frontend Node store/session owners | Deferred transports, explicit generation/owner barriers | Stale-response suppression, bounded retry, error/loading/finalizer ownership | Resolved immediate promises do not cover abort settlement, late confirmation or late canvas resolution |
| Frontend jsdom component owners | Actual components, typed Pinia state; confirmation/toast defaults no-op | Rendered state and exact user event where invoked | Confirmations need explicit accept callbacks; copied production logic/conditional assertions give weaker guarantees |
| Frontend IndexedDB owners | Fresh fake IndexedDB per case plus real AppShell/session code | Browser API transaction/recovery intent at fake storage boundary | Not native browser durability/quota/transaction scheduling certification |
| Chromium/Firefox E2E owners | Headless real DOM and isolated backend/runtime roots | Actual public gesture, accepted graph, painted rows/selection/clipboard geometry where observed | Default E2E uses Vite dev, so production performance uses its separate preserved build-bound task harness; Firefox currently blocked and full certification open |
| Library/Core unit owners | Real models/origins/codecs plus focused manager/task fakes | Public type/serialization/declaration/admission behavior | Fake public Operation methods are not actual operation completion, provisioning or physical worker evidence |
| Library deterministic integration owners | Tiny generated files, Direct compute, real record/cache state | Actual cache publication/rehydration/dispatch counters, selected records, Paths/SharedArray boundaries | DataFrame equality alone cannot show no recompute; projection-only tests do not prove second execution |
| Library complete/resource owners | Opt-in declared Wetlands envs/public data/binaries/model runtimes | Actual isolated whole-module imports and public worker/tool compatibility when run | Local host import/factory validation cannot stand in for worker origin/package closure; selector gaps remain |
| Wetlands operation/manager owners | Actual publicly returned RemovalOperation with bounded gate/finally cleanup; focused fakes elsewhere | Published completion API/result/error/listener/self-wait semantics | Operation completion is not every Task/async-awaiter/PID/reclaimer cleanup guarantee |
| Wetlands transport owners | Fake Pixi provisioning but actual subprocess workers and lease ledger/segment observations | Codec refusal, copy independence, cancellation/death unlink | Different from real Pixi download/provisioning; current automatic CI does not select five transport controls |

The mechanical module inventory has 590 tracked source files: platform311, library251, Wetlands28; 60 Python fixture/helper files, 360 Python test modules, 139 frontend unit/helper files and 31 browser modules.
Its 4,065 Python function definitions and 1,362 lexical frontend calls are source-definition counts, not native parameterized case counts, collected coverage, or full-read credit.
Vitest Node/jsdom/IndexedDB project exclusions are disjoint; no source evidence that those projects run the same module twice.
Platform logging-order's seven repeated cases are a deliberate separate order-sensitive contract and must not be removed merely because ordinary backend pytest also selects them.

### Development and completion lane ownership

| Change boundary | Existing appropriate lane | Optimization/retention decision |
| --- | --- | --- |
| Localized owning behavior | Exact `scripts/test focus` native file/case/browser | Map owner/callers/storage/events first; related-test discovery is advisory and marker filtering still collects/imports modules |
| Continuing coherent development | `quick` | Backend excludes integration/serial/slow/external and frontend runs Node; do not count quick as full nor stack it just before a subsuming gate |
| Internal backend read/fixture change | Smallest documented backend completion | Exact owner/race/CAS/migration first, one check backend at acceptance; accepted draft read reuse used this lane without redundant app/full |
| Local frontend behavior | Frontend scoped completion, localized browser smoke when needed | Node/jsdom/IndexedDB owner control distinguishes authority; native browser demonstrates rendering/gesture where necessary |
| Cross-stack API/schema/dependency/runtime | `check app` | All backend/frontend phases + critical Chromium; preserve actual phase assembly on late failure rather than claim the original command passed |
| Broad architecture/browser/test infrastructure | Appropriate all/browser-all | Only after actual exact failure passes; no broad command during this source-only review |
| Package-loading/external/release certification | `full`, published compatibility `certification` | Required technical milestone, not every edit; main installed old dependency and library unpublished-WIP lock mismatch remain explicit prerequisites |
| Result-only campaign records | `check campaign` | Structure/link/revision proof only, not runtime evidence authentication |
| Normative/developer docs or resume instructions | `check docs` | Cheap campaign check followed by Sphinx once; no browser/source suite merely for prose |

Platform `full` does not include native desktop/manual judgment or docs; those remain separate declared gates, with desktop final M5.
Original full/app failures and qualified retained recoveries are not rewritten by this review; no Firefox retries or broader certification is implied.
External opt-in/manifest exclusions must stay separately reported, including whole-module exclusions that can hide otherwise deterministic local ownership cases (existing B-F038).
Campaign backend/Vitest/Playwright manifest auditing rejects missing/extra/duplicate/reason drift against native collection; useful scope integrity does not prove excluded contracts or genuine executed evidence.

### Source-confirmed priority gaps

1. **Cold platform CI dependency closure (reviewer-F001):** backend lock requires sibling editable library/Core, all checkout steps provide only platform, and documented frozen sync needs that sibling.
   Prepared local tests are valid for their exact editable source, but do not prove clean hosted CI; next published pin milestone must supply the actual released owner or a deliberate exact source checkout.
2. **Public source containment and isolated import (A-F024/A-F138):** single-file filename/bundle source-ID writes lack complete public containment screening; example worker entry executes imports not declared by GENERAL_ENV.
   Stronger platform staging and package worker-import tests mitigate different boundaries, not these public/exemplar ones; no exploit/import failure was run.
3. **Selected worker coverage (reviewer-F003/F060):** library wetlands-only Task API misses both ordinary and complete selectors; Wetlands transport integration controls miss automatic fast/real-Pixi selectors.
   Reconcile existing selector/marker authority at the owning package milestone; keep actual-worker transport distinct from real provisioning and fake owner unit evidence.
4. **CI result and docs scope (reviewer-F005/F006/F007):** selected skipped jobs can be admitted by the aggregate; CI docs omits cheap campaign/TOC checks; coverage cleanup oracle is source-text matching.
   Existing conservative selection/fail-fast tests are valuable; small existing owner truth-table/cleanup controls should improve confidence without running every lane on every edit.

### Improve existing oracles before adding scenarios

| Finding | Exact weakness retained now | Smallest useful future change and boundary retained |
| --- | --- | --- |
| ROOT-F087 | Equal deterministic cache frames; upstream data changes before first compute | Existing hit/miss transitions observe exact tool executions/selected record; retain stronger runtime-cache counters and artifact rehydration |
| ROOT-F088 | Conditional nonempty segment branch; row assertions loop possibly empty list | Require promised nonempty node-correlated events; preserve legitimately absent telemetry by tool mode |
| B-F135 | Real worker ordering prefix/pool row-count/batch completed/detached DataFrame/aggregate seven-second threshold | Strengthen exact promised output/index/worker/event/overlap in existing case, not hard absolute timing assertions or another broad journey |
| ROOT-F095 | Copied ShortcutHost can pass after production wiring disappears | Exercise actual narrow production handler/wiring; preserve platform/native-mode distinctions and restore global descriptor |
| reviewer-F083 | Close event conditional assertion after hidden button | Invoke actual visible control, require event in same existing case |
| A-F163 | Install refresh title asserts POST only; old initial GET indistinguishable | Require exact post-action refresh/visible state and cleanup, retain held spinner/logger/uninstall consumer controls |
| B-F189 | Seeded cache→validator projection does not execute unchanged/changed second run | Label projection scope; retain execution-counter counterparts rather than duplicate broad cache journeys |
| reviewer-F025 | Immediate AST body import scan misses eager conditional/class import | Extend owning guard with eager contexts, preserving lazy functions/TYPE_CHECKING and stdlib+Core rule |

The companion dataset/Run review identifies abort-settlement→retry, delete-confirmation attempt/selection, held resolve→canvas switch, raw awaiter cancellation/physical admission and result identity gaps.
Immediate mocked lists, cooperative released fake Stop and typed endpoint successes remain scoped evidence; they do not silently close those higher-order ownership contracts.

### Fixture lifecycle and concrete consolidation candidates

B-F010/B-F011/B-F012/B-F117 expose manager/singleton/unbounded gate/unowned SHM test cleanup authority; source confirms the missing ownership, while retained thread/segment counts and suite cost are unmeasured.
The new actual public Operation fixture improves its own failure-safe release/completion cleanup without claiming every legacy fixture is repaired.
A-F101 relies on legitimate outer E2E runtime retirement; establish cumulative workload before adding destructive per-case cleanup that could invalidate nested ownership checks.
A-F163/ROOT-F095 have mounted-wrapper/global cleanup debt; failure-safe teardown strengthens isolation, not a claimed product leak or measured speedup.
B-F189's child process invocation lacks a timeout, but **root collection already marks its `test_integration` path integration**; do not schedule a redundant classification repair from its loose original module-marker wording.

A-F009 validator valid/unexecuted and A-F022 simple locked PUT are specific two→one same-boundary scenario candidates; preserve all distinct status/errors/no-publication assertions and admitted-validation/CAS races.
ROOT-F043 direct basic IOModel duplication can move to Core unit ownership while keeping class-local annotations/MRO/interface/Passthrough contracts.
Reviewer-F015's two artifact builds have distinct workspace-default versus no-sources postures: first establish whether both postures are required, then reuse one authoritative prebuilt set for shared artifact/import assertions if safe.
These are **candidate reductions of redundant work**, not permissions to delete now, measured savings, or suite-wide performance claims.
The already scheduled separately measurable suite optimization should select ONE candidate, preserve semantic outcomes/fixture isolation/conditional skips, and compare source-bound build/setup counts and wall time before/after; no flaky absolute timing CI threshold.

### Explicit deferred/unknown scope

Unranked original headings do not imply low risk; their original bodies and cross-owner triage carry actual P2/P3 qualification, owning subsystem and trigger.
Reviewer-F084 edited-control ARIA remains explicitly original-M1-qualified/deferred to parameter-control accessibility ownership, not freshly validated here.
No full body read of all590 files, native collection totals, suite-wide coverage percentage, wall-time speedup, cross-test contamination, actual physical PID cleanup, public tool/image pipeline benchmark or global architecture safety is established.
Pure selector root-conftest app import and per-case runtime-directory preparation is a source-visible **unmeasured setup-coupling candidate**, to investigate only if representative profile identifies material cost; broad fixture-scope caching would risk isolation and is not recommended without proof.
No canonical finding ID is allocated for the provisional supplementary `SA-SUITE-001`; it remains an unmeasured investigation trigger, not a confirmed setup-cost defect.
Published Wetlands2.5 Operation closure, library candidate override tests and untouched platform old installed environment stay separate evidence boundaries; eventual released floors/worker Core/platform pins and published compatibility are still required.


## Supplemental acceptance and retained limits

All review findings and explicit dispositions are recorded before selecting repair code.
The original573 inventory has exact frozen membership, no missing/duplicate IDs, responsible subsystem/trigger and explicit historical-versus-current proof; source validation is not inferred from a filename or priority label.
Independent and lead acceptance checked the five detailed paths, broad module/dependency map, critical family coverage, current fixed/open distinctions, suite owners/oracles, normative disagreements and explicit dynamic unknowns together.
The frozen per-file ledger is preserved rather than rebound to current repairs.
The next implementation uses exact owning failure controls, then one smallest applicable documented completion lane; no blind broad suite redo is authorized by this review.
Published compatibility, package floors/locks, remote acceptance/cleanup, scientific numerical controls, Firefox admission and native M5 are separate remaining campaign gates.

The [campaign plan](platform-test-plan.md), [checkpoint](platform-test-progress.md), [frozen findings](platform-code-review-findings.md) and [historical architecture audit](platform-test-architecture-audit.md) remain complementary records.
Review completion means this source/contract/method findings gate is accepted; it does not mean every candidate was reproduced, fixed, runtime-certified or safe under every deployment.
