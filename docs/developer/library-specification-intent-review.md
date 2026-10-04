---
orphan: true
---

# BioImageFlow library specification intent — accepted S review

Status: S intent accepted on October 4 after one cross-domain review and focused essential-feature corrections.
The owning normative clarification is the separate documentation increment described below; T/C conformance and global findings are not accepted by S.
The clarification is committed in the owning library at `e0f41b11e62defcd84b913db12b14e481b7c9a0b`: exactly 48 documentation paths over source baseline `2cd79a24`, with no source/test/dependency change.
Source bound: owning library `2cd79a24c59cf1093e934da9aa97744d2f8709c8`; campaign authority `daf4300015d56677f316d57b58930e08b9ced50f`.
This is a specification review, including primary and secondary intent, before test-oracle review (T) and causal code review (C).
It is not a test result, implementation conformance finding, complete architecture acceptance, scientific accuracy claim or release approval.
S reading/decision acceptance performed no product/source/test/runtime/install/network/release work.
The ensuing documentation increment revises affected normative clauses and guides without changing source, tests or dependencies.
Historical M1 and previous targeted repairs are evidence with named limits; earlier production-first notes remain provisional C questions and are not promoted to normative truth.

## Project idea and clean local architecture

BioImageFlow is a lazy, inspectable and editable graph of typed scientific tools and reusable recursive workflows.
One portable current definition captures tool/source identity, bindings, interfaces, enabled state, templates and declared resources; live execution configuration and owner handles remain separate.
The orchestrator resolves a selected graph, runs DataFrame operations, selects immutable results, maintains scientific row lineage and owns correlated progress/errors/cancellation/storage.
Core supplies lightweight declarations and one current typed worker request/result contract without pandas, Pydantic or GUI dependencies in scientific workers.
Within-machine Direct and managed WorkerPool processing are essential; Direct is explicit non-isolated debug/local execution, while managed workers own declared scientific dependency environments.
File and shared mapped-image values remain supported, with exact numerical identity and explicit controller resource ownership.
Optional scientific tools, viewer metadata, local result exports, logging and useful CLI operations remain project features.
Parsl/Dask/remote/SSH/site-scheduling implementations and their capability certification are excluded; their mixed local return/type/resource interfaces remain covered without deleting delivered features.

Specifications should state ownership, admitted values, effects, refusal and cleanup rather than preserve incidental flags, aliases, module layout or procedural implementation lists.
One current grammar is sufficient; old schemas, legacy wrappers and historical configuration aliases are not requirements merely because they appear in old prose.
Protected existing data and held work are preserved; retiring compatibility is a deliberate later refactor, not deletion of user data.

## Coverage, authority and phase limits

Section/line anchors below refer to the pre-clarification `2cd79a24` documentation snapshot.
Domain memos and full section/file ledgers are retained in the campaign's temporary evidence directory; their filenames in the table are provenance labels, not additional published normative documents.

| Domain | Actual S scope | Evidence / exclusions |
|---|---|---|
| Core and declarations | specs §1, §§2–3.5a, §5.1, §8; Arguments, typed grammar, Core import and viewer cross-seams; Core README and eleven full guides | `specs-core/spec-review.md`, `section-coverage.json`; no new source/test traversal; distributed-only intro classified excluded. |
| Workflow, graph and archives | specs §§3.6–3.12, §4 construction/edit/session, §7.1 and §14; full unified contract and twenty-two public guides | `specs-workflow/spec-review.md`, `section-file-ledger.json`; recursive local export remains included; remote transport excluded. |
| Runtime, storage and secondary features | operational §4, §§5.2–7.2, §§9–13 and Wetlands appendix; full detailed cache/storage reference, local config/execution/result/export/error/logging/install guides; all nine package READMEs and their tool/index/workflow docs; scientific workflow catalog | `specs-runtime/spec-review.md`, `section-file-ledger.json`; mixed documents judged for local obligations only, not distributed execution. |

The actual outline resolves IOModel §3.5a, Arguments §3.6, current typed grammar §5.2 and viewer metadata §14.3; these are cross-reviewed explicitly rather than dropped by approximate initial section numbers.
Every in-scope normative section is assigned; full public-document/range ledgers are supporting completeness, not an architecture correctness guarantee.
The detailed storage contract is authoritative for cache publication/layout; the unified workflow contract owns recursive definition/interface/archive semantics; specs.md states the coherent essential model and links rather than independently duplicating full protocols.
Type/registry/GUI guides teach this same declaration/schema model; generated autodoc is navigation, not a substitute for later public-source/test review.

No new test bodies were reviewed for S and no implementation was reopened to decide what the specification should mean.
No primary scientific paper, dataset checksum, model/binary download, public artifact installation or OS capability was independently verified online.
Windows/Linux and Python3.9/NumPy1.26 support remain named capability gates; current Mac/Python3.12 targeted proofs do not close them.
The next gate is whole applicable-suite/oracle review T after accepted intent; C then follows main end-to-end causal paths before secondary paths, followed by global findings synthesis before fixes.

## Accepted coherent decisions

These accepted defaults resolve the three domain question sets without treating current code as the oracle.
They preserve essential features; none requires a new user permission question or a speculative broad redesign.
Behavior-changing choices remain recorded findings until global C acceptance; approved specification clarifications can be applied before T.

### S01 — one current graph, typed values and exact identities

Use one strict current recursive graph/archive grammar with explicit source and viewer metadata; use one independently versioned current worker DTO/value grammar.
Unknown/missing fields, duplicate IDs and malformed endpoints/origins refuse instead of guessing; do not invent V1 adapters or aliases.
A bound node addresses package/version/module/class or logical source ID plus captured verified bytes, never whichever catalog display name currently wins.
Graph export serializes the admitted definition without re-running a Python factory; materialization runs the one selected trusted factory once.
Reference: unified contract:141–164,233–283; specs:1533–1593,2453–2479,3230–3277; S-WF-D01/08/11, CS-D10.

### S02 — one edit authority, transactional normal refusal and diagnostic editing

The session's canonical definition is the edit authority; a cached Workflow is a projection, not a second independently mutable authority.
Ordinary construction/bind/expose/rebind/delete either publishes a coherent change or leaves prior node/edge/interface/name ownership unchanged.
Diagnostic editing deliberately retains incomplete values with current scoped errors and never labels a half-published result executable.
Meaning-changing edits invalidate affected schema/validation/planning facts; corrected errors do not persist merely because an edit was called non-structural.
Names and stable IDs belong to their containing definition, so unrelated/reentrant workflow construction cannot reset another workflow's reservations.
Reference: unified:107–133,310–325; specs:2231–2255,2333–2388; S-WF-D02–05.

### S03 — immutable effective execution and safe admission

A run captures exact inputs/targets/definition/source bytes and effective per-environment configuration before run-visible effects; later edits affect later calls only.
Portable definition, live runtime manager, cancellation context and callbacks remain distinct; shared caller resources are never captured as owned engines.
One Workflow admits one active public execution; overlap/setup failure leaves no stray running binding or storage claim, and every reservation releases once on all exits.
Selected ad-hoc targets follow necessary data ancestors; recursive invocation also completes enabled internal terminals before its boundary returns.
Completion-only obligations do not contaminate unrelated scientific identity; disabled subtrees remain wired but are not expanded/executed, and skipped steps advance without execute().
Reference: specs:1794–1797,1975–2058,3043–3118,3223–3226; S-WF-D03/07, R-D01.

### S04 — declaration, validation and runtime value boundaries

Core's supported portable annotation grammar is distinct from current scientific runtime values and GUI display strings.
Requiredness, a supplied None, a default and MISSING remain independent; all required fan-out targets resolve using explicit value, interface default then applicable target default.
IOModel constructor checks structural fields; graph/editor validation reports scoped declaration/binding/value errors without execution or implicit heavy imports/install, while execution admits resolved scientific values.
Normalize only declared, meaning-preserving conversions; never infer numeric strings or silently stringify unsupported scientific constants.
Graph constants have a finite faithfully reversible grammar or explicit refusal; runtime arrays, owner-bound references and live invocation inputs are not silently stuffed into portable definitions.
Python3.9 Core import and supported annotation resolution are essential scientific capability, separate from NumPy runtime transport: portable examples may use typing.Union/Optional/Annotated, and postponed/inherited declared metadata must resolve consistently on supported interpreters.
Do not use source syntax acceptance alone as proof of Python3.9 runtime introspection.
Reference: specs:319–336,1107–1164,2236–2247,2453–2479; validation API:129–146; CS-D01/04/05, S-WF-D06.

### S05 — complete, honest schema and public inspection

Static/dynamic/merge/Passthrough schemas preserve added declared type/image/viewer metadata and inherited columns; unknown upstream columns remain unknown rather than fabricated Any success.
Image compatibility uses the declared four constraint dimensions and asymmetric unknown warnings, not a claim of actual pixel validation or biological suitability.
Each concrete tool kind satisfies its own contract: ProcessingTools require an admitted worker environment, IOModel outputs and explicit row semantics; DataFrameTools need no worker environment or RowConsumption and can have static, Passthrough or genuinely dynamic outputs without an Outputs declaration.
Dynamic DataFrame tools remain executable concrete features; discovery represents unresolved schemas honestly and runtime validates the actual result at the declared boundary, rather than marking the tool abstract or inventing available columns.
Reusable incomplete families stay abstract and unadvertised as executable tools.
Schema failure reports its actual unavailable/invalid phase rather than an empty successful schema; metadata snapshots/defaults do not leak mutable authority to callers.
Base package imports and light registry/schema inspection do not require model runtimes, provisioning or optional distributed dependencies.
Current public codecs/origins and supported external-command helpers receive explicit curated API scope; undoc-members is not an accidental support promise.
Reference: specs:248–279,897–902,1160–1164,1659–1683; CS-D02/08/09/11, S-WF-E02.

### S06 — scientific rows, collective meaning and batch correlation

Columns from one lineage align by explicit parent/child index rules; independent sources or sibling expansions require an explicit DataFrame merge, not accidental ordinal pairing.
Index strings and numerical values retain meaning: numeric-looking strings remain strings, exact integer/signedness/dtype/precision/nonfinite semantics are not lost through generic table/serialization guesses.
Mapped versus collective describes input meaning, not scheduling or output cardinality.
Current process_batch preserves ordered correlated transport groups and zero/one/many output cardinality.
Collective processing retains isolated whole-batch GPU inference, training and aggregate results, including configured empty-input aggregates; it does not require duplicated scientific aggregate rows or relocation into pandas/the orchestrator.
Collectively computed outputs retain an explicit association with all consumed inputs and an aggregate lineage distinct from a fabricated single-row parent.
The exact current public representation of that association is an owned T/C obligation, not a new mode invented by S or permission for an uncorrelated return.
Zero-row declared asset/scalar facts remain manifest/provenance metadata without invented object rows, including explicitly configured empty-batch aggregate artifacts.
Explicit table transforms such as Concat/CrossJoin may create new lineage, but must define it and retain source association instead of describing reset ordinals as preserved provenance.
Reference: specs:596–629,1378–1380,2444,2485–2508; storage:424–456,469–470; CS-D03, R-D02.

### S07 — scientific cache identity and one captured selected binding

Reusable identity contains exact tool/source origin/version, declared effective computation values/output contract, canonical root frame values and exact consumed selected record/selector references.
Run/transport names, mmap file tokens, output projections and capacity-only resource/runtime details never substitute for scientific identity.
Bind validated record, data, asset locators and provenance together; first-valid losers use the selected record downstream rather than their non-current candidate.
Plan is a fresh diagnostic storage snapshot, not a promise that mutable selection cannot change before compute; corruption stays visible and strict in execution.
Retain explicit path-based external-input identity for current un-fingerprinted sources; same-path file/model changes need explicit invalidation or a declared captured fingerprint/version, not automatic global scans.
Canonical logical values determine record identity; Parquet bytes determine integrity only, and human CSV/JSON remain derived outputs.
Reference: specs:2511–2673; storage:127–177,303–456,588–654; R-D03/04.

### S08 — effects, templates and truthful storage publication

Resolve declared template variables/accessors and owned-output collisions before affected dispatch; input-row base paths are distinct from exploded child siblings.
Only declared asset/path fields acquire path semantics; URLs/string spellings never become owned files by heuristic.
Attempt work is private, reusable records become immutable only after full validation/publication, and terminal attempt metadata follows cessation of possible writers.
Invalidation/cleanup coordinates active readers and writers; age alone cannot delete consumed/transient data or published records.
Explicit requested export failures raise and preserve prior destinations; automatic disposable projection failures warn without invalidating successful computation.
Linked output projections are read-only canonical aliases, while copies are independent; no promise that linked writable scratch can safely mutate immutable cache.
Reference: specs:2676–2707,2709–2878; storage:459–621,939–1055; S-WF-D10, R-D07/09.

### S09 — three drain fences, failure and cancellation

Keep correlated task outcome/writer cessation, public operation completion and physical worker-pool retirement distinct.
Cancellation stops admission, cooperatively cancels unfinished tasks, ignores late outcomes and drains possible writers; it does not promise arbitrary native/pandas preemption.
Strict release reports pending/error truthfully and retains failed-close pool/grants/cache ownership for retry; best-effort stop/shutdown is an explicit convenience, not physical cleanup certification.
Engine close denies new work and safely resolves admitted work; external lifetime drains only its submitted work and leaves caller-owned resources running.
Primary failure is deterministic among actual submitted failures, and cleanup/diagnostic failure cannot mask it.
Progress callbacks are observational: ordinary observer errors are isolated/logged, and any supported propagation of callback failure is explicitly documented for that interface.
Callback failure is distinct from independently observed owner-thread interruption; exception type alone cannot universally identify the caller's intent or channel.
Owner interruption preserves its identity through cancellation/drain, with no event-thread wait deadlock or reentrant lifecycle mutation.
Reference: specs:1936–2058,2939–2958,3043–3118; environments:135–176; R-D05/08.

### S10 — one explicit array/resource ownership model with bounded ordinary cleanup

Uniform SharedArray means scoped numeric NPY2 mmap backing and zero-copy mapped views after allocation; decoding is pure and never attaches or adopts arbitrary paths.
Controller preowns output namespaces, including output-only producers; null context means no shared input or allocation capability.
Accepted outputs and exact admitted input pass-through regain reachable strong owners; automatic execution/Workflow/context exit does not close them, so unopened refs remain usable after temporary Workflow collection.
Expose public exact result/group release and owner/status access; releasing one result cannot close unrelated result groups or the entire shared owner.
Explicit release denies new controller admission and may remain pending for live root/slice/asarray views or already admitted worker grants; never force mapped views closed.
Normal pool reuse can retain physical grants: provide explicit idle/quota-pressure physical retirement of the owning pool before reclaiming them, without invalidating active views or unrelated groups; if enough safe space cannot be reclaimed, finite budget admission refuses clearly.
Failed/rejected/unreturned allocations retire automatically after writer/grant and controller-disposition fences; pending outputs survive drain-before-acceptance races.
GC does not initiate accepted-result/whole-owner release; last-reader drainage may finish a previously requested release.
Borrowed scientific input values are immutable to consumers by contract; mutable processing allocates an independent output/work value rather than modifying a selected upstream result.
Define any supported explicitly writable creation-stage view separately from accepted read-only result access; zero-copy alone is not mutation authority.
Durable cache/export hydration preserves numeric bytes/dtype/shape/order, owns rollback only for newly created groups and leaves durable/unrelated data intact.
Reference: specs:2463–2468,2890–2935; storage:1068–1112; CS-D06/07, R-D06.

### S11 — source and outer archive effect ownership

Admit the complete immutable source/path/hash manifest before writes/imports; validate outer extraction destination and preexisting ancestors separately from inner source containment.
Hashes establish content identity, not trust or Python safety; trusted Python may have arbitrary effects that task staging rollback cannot undo.
Current definitions retain exact helper/assets/executable content independently of loading newer same-logical-ID content; no global live-module purge or source staging overwrite.
Temporary extraction/runtime roots and persistent destinations have explicit owners, budgets and retirement; failed import cleans only owned staging, not user destinations or another live definition.
Define process-global installed-package/transitive dependency conflicts as explicit authority/refusal rather than promise isolation from a prepended path or one script declaration.
Reference: unified:248–283; specs:1533–1751,3258–3277; S-WF-D08/09.

### S12 — accepted local results, bundles and viewer metadata

Definition export, trusted Python import and successful correlated result export are separate effects.
Attached export snapshots before caller mutation/removal, retains exact accepted record/return ownership, verifies all bundle content and installs atomically; a verified repeat remains idempotent.
Owned assets are self-contained; external paths remain declared external dependencies.
Loaded/exported shared numeric values receive an accessible bound cleanup owner and stay usable independently of transient source lifetime.
Viewer declarations/additions are portable diagnostics bound to the accepted output/result; they neither install packages nor affect execution/cache and never certify incompatible requirements resolvable.
Latest per-node views can mix successful nodes from different failed/cancelled/selected runs; they are not a single complete successful workflow snapshot.
Reference: specs:2167–2177,2786–2861,3238–3277; storage:801–1027; result/viewer references; S-WF-D11, CS-D10, R-D09.

### S13 — secondary scientific feature and install/support intent

Retain all nine packages: common table/source/glue; IO/axes/OME; label/object/intensity measurements; classic and model segmentation; restoration/checkpoint metrics; ATLAS/puncta/matching; deterministic and division/gap lineage tracking; SAIRPICO binaries; optional FLIM phasor analysis.
Their contracts state axes/units, label/coordinate/index conventions, declared model/data/parameter identity, meaningful empty outputs, invalid-value refusals and owned artifacts.
Keep exact distinct algorithms distinct: common components use face connectivity, MaskToLabels uses stated eight-connectivity, object-overlap greedy matching differs from global spot/nearest-neighbor assignment, and foreground IoU/Dice is not instance-quality proof.
Scientific input/output validity is not biological correctness; mocked CLI/model calls, screenshots and generated fixtures are separate from optional pinned data/model/binary acceptance.
Preserve explicit upstream citation/data/model checksum requirements; missing units/reference or ambiguity becomes an owned T/C obligation, not an invented equation or automatic new benchmark.
The Core Python floor >=3.9 with NumPy1.26 support, and orchestrator Python floor >=3.10, remain required current scientific constraints; these are interpreter floors, not package-version floors.
Actual normal installs, OS/lifetime and model/binary capabilities require their own evidence.
Current cohort metadata alone is not a published-artifact or scientific support certificate.
Use one explicit current source-development configuration and no backward-only Core override alias.
External-command wrappers and supported Core helpers own argv/cwd/output/error boundaries: no global chdir, no same-output partial-publication collision, no success without admitted completed outputs, and timeout/interruption cannot advertise physical termination without a drain fence.
Reference: installation; root/BIF README; all nine package and tool/workflow documents; specs:669–671,2873; CS-D11, R-D10/11.

## Finite flow catalog for T then C

Each row drives review of existing oracles, not an instruction to add a full test matrix now.
For T, label faithful public/negative/lifetime/numeric evidence, mock-only capability, weak/duplicated assertions, missing tests and skipped external gates.
For C, trace accepted trigger through authority/admission, values/identity, effects, failure/cancel/cleanup and observable return; production file coverage remains supporting completeness.

| Flow | Essential expected success/refusal/ownership | Main / secondary |
|---|---|---|
| F01 Import and declare | Lightweight Core/BIF base imports, kind-specific abstract/concrete admission including genuinely dynamic DataFrame tools without Outputs, postponed/inherited metadata on supported scientific Python; failed schema not empty success | Main |
| F02 Build/edit/validate | Atomic coherent graph mutation or explicit incomplete edit; stable IDs/defaults/None/current diagnostics; static/Passthrough/dynamic schemas and runtime resolution represented honestly | Main |
| F03 Capture/invoke/rebind | Independent recursive definitions, exact effective source/config snapshot, data versus completion dependencies and transactional refusal | Main |
| F04 Load/export source graph | One current grammar, whole manifest/outer destination admission, actual helpers/assets retained, no factory replay or silent source fallback | Main |
| F05 Plan/align/cache identity | Pure fresh plan, exact root/row/selector/scientific values, explicit independent joins, current external-path limitation | Main |
| F06 Execute Direct/local rows/batches | Correlated ordered current groups, numerical fidelity/zero rows, isolated collective whole-batch inference/training/aggregation with all-consumed-input association and aggregate lineage; local scheduling/caps/exact origin; Direct isolation limits explicit | Main |
| F07 Reuse/force environments | Captured exact recipes/config/Core, False warm reuse, physical strict close before removal, retryable failure and unrelated pool isolation | Main |
| F08 Publish/select/load | Immutable complete records, first-valid selected data/provenance agreement, corruption refusal, safe explicit invalidation | Main |
| F09 Fail/cancel/step/close | Safe setup/overlap/reservation, deterministic actual primary error, stop new effects, admitted writer drain and retryable owner state | Main |
| F10 Allocate/open/accept arrays | Output-only admitted scope, bounded dtype/header/path admission, zero-copy root/derived-view lifetime, pending/accepted/rejected disposition | Main |
| F11 Retain/release/repeat | Returned unopened references survive temporary execution; exact group release, normal repeated/discarded runs, physical pool-grant retirement and bounded quota refusal; failure/cancel cleanup | Main |
| F12 Hydrate/export local return | Exact accepted source/record/data identity, durable numeric reconstruction/rollback, contained atomic bundle and usable explicit result owner | Main |
| F13 Templates/output projection | Collision/missing-value refusal, owned versus external/scratch, collective/empty-input aggregate artifacts with explicit association, zero-row manifest facts, warning-only automatic projection and strict export | Main |
| F14 Schema/viewer/logging/CLI | Pure truthful catalog/metadata, additive viewers, opt-in handlers, current API/examples/install vocabulary and safe supported output CLI | Secondary |
| F15 Table/IO/classic image science | Explicit lineage/axes/units/numeric labels and values; empty/invalid shapes/types; algorithms and identity conventions retained | Secondary |
| F16 Optional model/binary/FLIM science | Actual named packages/models/binaries/data with honest fake versus native versus pinned-public-data evidence; no biological correctness from smoke | Secondary |

## Owning normative clarification scope

| Owner / files | Coherent clarification scope | Editorial versus semantic |
|---|---|---|
| Shared `docs/source/specs.md` | Essential model links, current declaration/value distinctions, effective snapshots, row/cardinality/cache, three drain fences and exact group ownership, explicit current schemas | Coordinated single writer/hunks; semantic clauses S01–S13 recorded, no code adjustment yet. |
| Workflow `reference/unified_workflow_contract.md` and graph/session/wire/basic/merge/template/custom authoring guides | Atomic normal versus diagnostic editing, current graph grammar, exact origin/source/extraction, lineage/defaults and complete examples | Correct same-contract contradictions; API/return-shape/legacy retirement choices remain explicit semantic decisions. |
| Core README/how-to/shared_memory, type/tool/schema/registry/validation/API/viewer guides | One lightweight current authoring/schema/typed-value API, explicit result/group cleanup/mutability/physical lifecycle and no legacy-only source flag | Accurate current intent and example consolidation; newly supported public lifecycle surfaces tracked into T/C. |
| `reference/output_cache_storage.md`, local/environment/resource/monitoring/results/errors references, caching/execution/planning and cancel/parallel/export guides | One identity/publication contract, fresh plan bounds, IPC timeout, best-effort versus strict drain, mmap vocabulary and exact local bundle owners | Pure stale vocabulary/procedural/guarantee corrections separated from behavior-changing ownership/mutation rules. |
| Root/BIF README and installation | Honest isolation/current candidate versus published support, explicitly owned exports/configuration, links instead of duplicated normative promises | Process/support precision; no publication or resolver claim. |
| Nine tool docs and scientific examples | Preserve all named features, complete current examples/worker prerequisites, explicit algorithms/units/empty/lineage/model identity and measured-proof limits | No new mathematical/biological capability promise; ambiguous scientific choices recorded for T/C with owner. |

Do not blindly rewrite all duplicate paragraphs or change schema numbers by analogy.
Prefer one normative clause plus concise examples/links; remove stale instructions only after deciding they are historical rather than essential current features.
The clarification uses one strict owning documentation gate with the existing private interpreter and one platform docs gate for this new report/navigation; neither supplies product certification.
Documentation changes invalidate exact doc/sdist artifact equality; unchanged source-module proofs retain only their original module/runtime scope.

## Owned unknowns and next acceptance boundary

S accepts the contracts above; actual implementability, public API shapes and conformance are not resolved by specification reading.
T must assess current complete in-scope oracles/fixtures/selectors, including real local WorkerPool opt-in tests that regular README lanes skip and local result tests inside mixed launcher directories.
Critical C follow-ups include exact normal repeated-run discarded-result cleanup, idle/quota retirement and close-error recovery; scientific table dtype/index identity; mutable schema/definition projections; source import/dependency origin; and correlated return/bundle hydration.
These are finite obligations, not claims of a new reproduced leak, data loss or universal library flaw.
Scientific primary reference/model/binary/OS capability verification stays explicitly owned for later milestone gates; it does not block coherent intent acceptance or justify removing features.
Accepting S unlocks T and agreed documentation clarifications only, not source fixes, test additions, releases or platform adoption.
Only accepted S→T→C main/secondary global findings unlock repairs; the accepted scoped library milestone later unlocks the paused release/platform chain.

Owning `.venv/bin/python docs/generate_tool_package_docs.py --check` passed in 0.409s; `.venv/bin/sphinx-build -W --keep-going docs/source docs/_build/html` passed initially in 12.175s and after the named applied-review corrections in 4.243s.
The existing private Python3.12 environment was reused without reconciliation or package installation; no product check was run.
Platform `env UV_OFFLINE=1 scripts/test check docs` at `daf4300` plus this five-document projection failed overall in 0.996s: dashboard and 77 links passed, while Documentation could not fetch its declared Furo dependency offline.
The exact Documentation phase from `scripts/test` (`uv run --no-project --with-requirements docs/requirements.txt -- sphinx-build -W --keep-going docs docs/_build/html`, with captured absolute paths) recovered with network enabled in 23.834s against unchanged document content.
This is qualified phase assembly with the original overall FAIL retained, not a successful complete `check docs` invocation; no repeated campaign/product phase was run.
Both strict Sphinx witnesses were warning-clean; no runtime test, skipped test count, scientific capability or OS certification follows from documentation builds.
The final task-commit/proof entries add only factual source identities and results after that validated projection.
