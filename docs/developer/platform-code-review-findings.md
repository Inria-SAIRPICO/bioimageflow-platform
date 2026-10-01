---
orphan: true
---

# Complete codebase review findings

**Review open; fixes and further campaign tests held.**
This register records every identified candidate from the complete review, preserving source risks separately from executed defects and accepted design limitations.
The [audit](platform-test-architecture-audit.md) and [per-file ledger](platform-test-file-review.tsv) define scope, hashes, owners and actual review status.
Recording an action does not authorize its implementation before the complete-review gate closes.

## Carried partial findings

The initial [selective findings](platform-test-architecture-audit.md#reviewed-findings-and-next-packets) remain in the backlog; they do not count as completed full-file reviews.
These include portable binding/resource/engine authority, force-Recreate, dataset publication, credential rollback, deployment-root policy, caller incarnation, cancellation/physical lifetimes, result/image identity, source containment, suite oracles/artifacts, original filename fidelity and Napari defaults.
Held dataset diagnostics demonstrate early partial publication (ISSUE-023); held portable diagnostics demonstrate four real binding/resource/engine mismatches; the T1 generation defect remains ISSUE-024.
No coverage or repair completion is credited by this register.

The independent held dataset-publication plan review adds future acceptance requirements: retain transaction/publication ownership through ordinary failure cleanup, never delete after successful or ambiguous commit, handle partial writes, and preserve earlier successful uploads if a later per-file publication fails.
A bare recognized empty final placeholder is not an accepted crash-recovery strategy; cross-instance cooperating catalog writers and unsupported noncooperative filesystem replacement must be distinguished.

## Full-review batches

Accepted complete-file batches: A batch 1 (20 platform files), root batch 1 (27 platform files plus two held dataset test files), root batch 2 (10 platform client/component/test files).
B batch 1 adds 19 complete files; shared-infrastructure batch 1 adds 25 reviewed and one specifically classified file.
A batches 2–3 add 17 full-content files (11 platform and six library); the checkpoint contains 121 complete entries (120 reviewed / one classified), with 1,677 baseline entries still pending.
B batch 2, A batch 4, root batch 3 and shared batch 2 add 76 more full-content judgments.
Current checkpoint: 1,799 inputs / 1189 complete (1051 reviewed / 138 classified) / 610 pending, with 426 identified findings.
The newly authored findings register remains a pending current-document input beyond the frozen baseline.
Ownership was corrected for nine existing counterpart tests without silently granting review credit.
Each accepted finding will name its ID/severity/classification, exact source and relevant lines, causal reasoning/consequence, existing test/oracle or missing distinction, essential contracts to retain, uncertainty and proposed future action.
Files with no finding retain specific review reasoning in the ledger rather than an implied clean bill.

### Graph and portable authority — A batch 1

#### A-F001 — High, defect + test-oracle gap: portable binding overwritten by active catalog

`backend/src/bioimageflow_server/services/graph_translator.py:38–80` retains explicit module/class/package/version first only for owned source.
Other carried portable bindings resolve the global class by display name before falling back to the binding.
`graph_requires_wetlands:216–239` independently uses that catalog class, and `graph_builder:73–85` supplies its classification to actual materialization.
A captured Processing v1 can become active DataFrame v2 and Direct without explicit rebind; this was reproduced in the preserved pre-freeze actual two-version public-loader diagnostic, not re-executed here.
The contract is explicit `Use installed versions` in v1spec407/1676; unbound catalog-created nodes still require registry resolution.
Main `test_requirements_and_version_rebinding_recurse:496` inserts package/version after translation, so it cannot detect preservation failure.
Main builder tests use graph/canonical class identities that agree.
Retain public-library semantic ownership and explicit rebind; future action is the bounded reviewed authority decision after the entire audit, including serialize-only callers and actual bound engine selection.

#### A-F002 — High, defect + test-oracle gap: resource constraints use another class authority

`graph_translator.py:155–189` uses same-name registry class for Processing-only applicability and declaration floors even when `_tool_library_identity` selected an owned source.
Preserved pre-freeze actual public source controls accepted bound CPU3/floor2, while platform build rejected it as DataFrame-only or against catalog floor8.
Main `test_owned_tool_identity_takes_precedence_over_same_named_registry_tool:591` checks identity fields but no overrides; resource roundtrip/floor tests use matching registry identities.
Consequence is rejecting a valid bound source or applying the wrong constraints; public class declarations must remain authoritative.
Future action: route bound resource data/classification through exact captured class/public loader, preserve structural value validation, scoped invalid-floor diagnostics and Run refusal; no repair is released.

#### A-F003 — Medium, source risk + missing distinction: dependency helpers use unqualified catalog identity

`graph_translator.py:645–756` calls `_is_local_tool_reference(node, metadata)` in requirements/rebind, where any same-name metadata with `source_kind='custom'` classifies an explicit portable package node as local.
Thus a global custom class can suppress the portable package requirement and explicit version rebind.
Conversely `_detect_missing_tools:719–740` treats *any* global class-name presence as tool availability, even if the requested installed package/version lacks that class; `_detect_missing_packages` only checks installed version membership.
These are source-observable decisions; no new runtime fixture or loss assertion was executed.
Main custom/missing tests cover a node itself marked local or an empty registry, not captured package identity conflicting with a same-name custom/different-version catalog.
Future action: define availability/locality by bound package/source identity, retain scoped node paths and allow legitimately unresolved editable imports; assess full registry/store callers in later batches before priority/fix.

#### A-F004 — High potential impact, source risk/design boundary: caller incarnation absent from draft/save mutation wire

Complete `models/workflow.py:158`, `models/workflow_draft.py:16–47` and `frontend/src/api/workflowDrafts.ts:37–62` have graph/CAS revision but no expected caller workflow incarnation.
The existing model test `test_save_body_carries_only_the_canonical_graph:118` deliberately enforces that body shape.
Earlier selective trace showed service captures current generation after worker admission and correctly rechecks it during commit, but fresh same-ID workflows synthesize revision0; an old request first admitted after recreation has no incarnation discriminator.
Full service/store/router review is **still pending**, so this batch records the wire-level gap and retains the qualified previous hypothesis; it does not claim newly demonstrated user loss.
Client delayed-response guards certify presentation suppression, not absence of an already committed durable write.
Future action after full review: dedicated identity/API compatibility decision and stale-caller storage oracle; retain during-validation generation rechecks, draft CAS, and snapshot owner hierarchy.

#### A-F005 — Medium, design/performance/source-side-effect risk: reverse adapter materializes recursively before projecting

`graph_translator.py:497–518` calls public `Workflow.from_dict(deepcopy(payload), storage_path='.', validate_only=True, partial=True, auto_install=False)` for structural confidence, then recursively calls `lib_dict_to_graph_state` at line535 for every child.
The public load already materializes recursive children, so a deep chain's descendants can be reconstructed once per ancestor plus their own projection.
This can repeat module/source/class construction and source context work while only reconstructing an editable wire document; no measured slowdown or unintended write was executed here.
The adapter also duplicates a strict allowlist and classifies structural errors using message fragments at518–528.
Main recursive/golden/layout tests assert returned shape/positions, not loader invocation count, import/source side effects or typed structural error boundaries.
Retain rejection of fields the GUI would discard and public semantics; future action is a library/adapter boundary decision after complete loader/serialization review, not deleting validation blindly or compiling twice.

#### A-F006 — Low, maintenance/type authority debt: handwritten draft wrappers duplicate generated schema

`frontend/src/api/workflowDrafts.ts:4–24,39–45` handwrites response/conflict/request types whereas complete nested/source wrappers import generated contract types.
The relevant generated draft schema fields agree today; this is not claimed schema drift.
A future incarnation/response change can update backend/generated schema but leave the real caller stale.
Retain per-segment URL encoding and consumer-owned acceptance; future action is contract-coupled replacement with generated types/adapted optional-default semantics, not a generic API refactor before review completes.

#### A-F007 — High potential impact, cross-owner concurrency source risk: async cancellation versus physical worker lifetime

Complete `graph_worker.py:16` awaits AnyIO `to_thread.run_sync`; complete async validator deep-copies input and delegates through it.
Graph/draft routes hold async admission leases around worker awaits, but raw asyncio cancellation can be distinct from AnyIO cooperative cancellation scopes.
The earlier T1 physical-worker/admission evidence makes this a B/root seam; draft/graph/Clear cancellation is not independently reproduced here.
Existing ordinary held-validation admission oracle releases normally; tests in this batch are synchronous and cannot prove physical completion after request cancellation.
Future action remains B/root-owned after full review: distinguish raw task cancellation, cooperative Stop and physical-thread teardown before any admission-holder repair; preserve bounded AnyIO worker limit and immutable input copy.

#### A-F008 — Medium, source risk/diagnostic debt: error kinds inferred from exception message substrings

`graph_translator.py:800–808` maps `unknown_tool` to missing-package when detail contains `package` or `load`, and any `construction_failed` containing `cycle` to a graph cycle.
A tool construction error mentioning e.g. a cycle-related parameter can therefore be reported as graph dependency cycle, and validator skips planning when any cycle error exists (`graph_validator.py:102`).
This is a causal source path, not a newly executed false-positive.
Main mapping tests cover correct scoped missing-input and explicit environment incompatibility, not misleading text in an unrelated construction error.
Future action: reconcile public library typed error distinctions before replacing text fallbacks, preserve backward-compatible readable detail and real cycle handling; do not grow one special-case branch per error sentence.

#### A-F009 — Low, test redundancy candidate: valid/unexecuted validator journeys share the same oracle

Complete `test_graph_validator.py::test_valid_graph` and `::test_cache_unexecuted` call the same public validation entry with the same uncached Processing class/required input and differ mainly in path literal; the first already asserts unexecuted status plus validity/errors.
This is a specific dedup candidate, not a claimed suite speedup or authorization to remove tests now.
Retain cache publication/selected-record identity, prior-selection miss, same-ID request-local isolation, cycle vs self-loop topology, core compatibility, positional negatives and model/adapter boundaries; those are different contracts.
Future action: combine the unexecuted-only assertion after test-ownership review and measure actual cost before claiming optimization.

#### A-F010 — Low, source risk/equality debt: locale comparator is not an explicit canonical key total order

`frontend/src/sessions/graphDocument.ts:22–27` recursively sorts object keys with `localeCompare` before equality serialization.
Locale collation can consider distinct Unicode-normalization-equivalent strings equal, leaving stable-sort order dependent on insertion order; this risks false dirty/inequality for object-valued constants with such keys.
No JS runtime example was executed, and ordinary ASCII graph field names are unaffected.
The function correctly preserves array order and removes undefined properties; do not change those semantics or equate this UI equality with backend artifact provenance hashing.
Future action: decide exact JSON object-key equivalence contract and use a deterministic exact comparator only if a distinguishing Unicode-key case confirms the risk after review.

#### A-F011 — Low, contract/model source risk: optional binding metadata admits incomplete/empty combinations

`models/graph.py:305–310` allows independent optional module/class/package/version/source strings with no nonempty/joint consistency validator.
Forward translation checks truthiness for module/class, `is not None` for source ownership, and elsewhere truthiness for worker engine; empty/partial binding can therefore enter different fallback branches.
Main model tests validate unknown fields, stable ports and viewers but not these inconsistent identity combinations.
This is not proof every partial value must be invalid: unbound catalog-created nodes are deliberate and imported unresolved bindings must remain editable.
Future action: record and resolve the exact allowed identity states during complete source/import/registry review, then add narrow normalization/validation only where the contract requires it.

#### A-F012 — Low, test-fixture accuracy debt: validator metadata labels DataFrame classes as Processing

`test_graph_validator.py:152–167` uses `_meta` with `tool_type='ProcessingTool'` and mapped row consumption for every fixture class, including MockDataFrameTool and source DataFrameTool.
The actual compiled class currently drives graph semantics, so this mismatch does not establish a product bug; it can hide an accidental future dependency on misleading metadata and obscure class-authority distinctions.
Builder's `_make_metadata` correctly derives class kind.
Future action: share a focused correct metadata constructor where independence permits, preserving actual importable classes and boundary-distinct assertions; do not replace real public materialization with mocks merely to simplify fixtures.

### Persistence and clients — root batch 1

#### ROOT-F001 — P1, source defect: overwritten credentials are deleted on rollback

`backend/src/bioimageflow_server/services/settings_store.py:191–205,337–372` records successful key writes, then deletes those keys if a later key or JSON write fails.
A preexisting credential overwritten by the attempt is therefore lost while previous disk/memory settings remain active; a backend set that mutates then raises is not tracked at all.
Tests `TestPatch::test_omero_settings_write_failure_rolls_back_written_password` and `test_omero_partial_keyring_set_failure_rolls_back_written_keys` start with empty stores and cannot distinguish restoration from deletion.
Future action: capture distinct preimages before any mutation, restore overwritten keys/remove only new ones, preserve original error and report secret-free rollback failures; OS keyring failure cannot be made transactionally infallible.
Alias records with distinct display names may share a credential key, so deduplicate restoration by key rather than row index.

#### ROOT-F002 — P1, policy source risk: persisted/client-patched mode differs from process policy

`models/settings.py:77`, `services/settings_store.py:147–150,178–190`, `routers/settings.py:119–175` accept/load `deployment_mode` without enforcing the process authority exposed separately at `settings_store.py:174`.
`app.py:1025–1042` injects live Settings into Fiji consumers; complete A router review confirms `routers/workflows.py:591,701` examines Settings mode for server filesystem reveal and folder export.
Trusted Python-source preview/apply instead uses the immutable config-mode provider (`app.py:499–503`); that path is not admitted by this mode patch.
Complete B Fiji review confirms both launch gates consume the mutable live Settings mode.
Workspace/tool/Napari guards using process configuration and execution-profile store editability are independent defenses and must not be assumed bypassed.
Consequence: presentation and some policy consumers may observe desktop mode in a webapp process, including after reusing a desktop settings file.
No runtime exploit is claimed; B and A must finish full consumer reviews and link consequences to this canonical finding.
Existing router tests only refuse webapp Fiji configuration with an explicitly configured webapp store; they do not patch mode or load conflicting persisted mode.
Future action: choose one process-authoritative policy at load/response/write and all affected consumers, preserving supported desktop controls and file-only unsafe features.

#### ROOT-F003 — P1, alternate policy source risk: generic settings retargets a webapp workspace root

`services/workspace.py:43–55` falls back to live Settings.workspaces_root when config lacks an explicit root; `routers/settings.py:119–175` permits that generic patch, while `routers/workspace.py:24–33` correctly refuses direct workspace mutation in webapp mode.
`app.py:392–402,1055–1061` derives request-time workflow/dataset roots from that mutable workspace service.
Existing workspace/Fiji webapp tests use explicit configured roots and mask the fallback.
Future action: diagnose/repair process-admin root policy across both mutation paths, with settings-derived, configured-root and desktop controls; do not introduce future multi-user authorization as a substitute.

#### ROOT-F004 — P2, persistence risk: settings atomic temporary file is shared across store instances

`settings_store.py:304–319` uses one fixed settings.json.tmp, guarded only by an instance asyncio.Lock.
Multiple desktop/backend processes or store objects sharing the standard per-user path can truncate/rename/unlink another writer's temporary file or persist stale snapshots.
`TestPatch::test_concurrent_patches_serialize` uses a single object and verifies only same-object serialization.
Future action: establish supported multi-process writer semantics, use owned temporary files and appropriate compare/serialization if concurrent processes are supported; no generalized transaction framework is justified yet.

#### ROOT-F005 — P2, client source defect: GET completion can overwrite a newer settings PATCH

`frontend/src/stores/settings.ts:49–64` coalesces GETs; `:78–107` separately serializes PATCHes. Both publish full snapshots without ordering between chains.
A captured old GET completing after an accepted PATCH replaces current settings; failed PATCH rollback can likewise restore a snapshot older than an intervening GET.
`frontend/tests/unit/stores/settings.test.ts` covers GET coalescing and PATCH serialization separately, not their crossed ordering.
Future action: distinguish request/accepted mutation ordering and retain optimistic rollback/OMERO secret behavior; extend existing deferred tests only after audit closure.

#### ROOT-F006 — P1, executed defect retained: streamed dataset becomes visible before completion

`dataset_store.py:236–264,343–381` creates a recognized final filename before streaming. A second store reconciles those partial bytes as legacy, then the uploader's INSERT conflicts and cleanup removes the file.
Held ISSUE-023 has two exact causal reds at store and real disk-spooled HTTP boundaries; no rerun occurred in this batch.
Existing main tests cover completed legacy files and upload errors, not concurrent partial publication.
Future action: independently reviewed complete staging/publication and reconciliation ownership, preserving legacy recovery, containment, cancellation and collision safety.
Held plan concerns: cleanup while transaction/publication ownership is retained; no deletion after successful/ambiguous commit; no recognized empty final placeholder as crash recovery.

#### ROOT-F007 — P1, byte-completeness source risk: os.write return value ignored

`dataset_store.py:352–355` increments catalog size by supplied chunk length but ignores the actual short-write result.
A legitimate partial write can publish truncated bytes with the original size and apparent success.
Existing `test_store_writes_file` uses ordinary full writes and exact bytes, which does not exercise this branch.
Future action: handle complete writes and zero/error outcomes, with one meaningful controlled short-write distinction after audit; do not claim reproduction yet.

#### ROOT-F008 — P1, identity source defect: compatibility delete accepts any contained decoded filename

`dataset_store.py:557–567` decodes the client ID to a path and unlinks before looking up a catalog record.
An ID encoding `.bioimageflow-datasets.sqlite3` or another unrecognized file under the managed root passes containment; the catalog or unrelated managed-root file can be deleted even though it is not a dataset.
`routers/datasets.py:309–327` exposes this compatibility path. Main tests cover listed IDs, unknown paths and outside-root traversal, not existing non-catalog files or the catalog itself.
Future action: resolve exact catalog membership/physical ownership before any unlink, preserving compatibility API statuses and root containment; no destructive diagnostic was run.

#### ROOT-F009 — P1, concurrency source risk: delete CAS is read before the SQLite write lock

`dataset_store.py:519–542` checks revision and selects identities using SELECT before BEGIN/first DML, then unlinks physical bytes before DELETE acquires a write transaction.
A second cooperating store/thread can mutate after the expected-revision check and before physical deletion, violating the promised refusal before stale deletion.
`test_recursive_delete_requires_current_preview_revision` interleaves changes before the call and does not distinguish this window.
Future action: define one cooperating catalog mutation boundary covering CAS, name checks, publication and physical deletion; distinguish ordinary filesystem partial failures and SQLite failure semantics.
No process-level reproduction or universal external filesystem CAS guarantee is claimed.

#### ROOT-F010 — P1, partial-failure source mismatch: containment failure aborts recursive deletion

`dataset_store.py:535–540` raises PathTraversalError inside a handler catching only OSError; `routers/datasets.py:297–305` does not map that error.
If a later selected path escapes via a replaced symlink, earlier successful unlinks can already have happened while the SQL transaction rolls back and the response aborts, rather than returning successful IDs and per-file errors.
The v1 deletion contract requires actionable partial failures and retained failed records/folders.
Existing main recursive-delete test is all-success/current-revision, without symlink containment or mixed failures.
Future action: ensure exact per-file containment failure semantics and bookkeeping under the shared catalog boundary; no symlink mutation test was executed.

#### ROOT-F011 — P2, catalog uniqueness source risk: check-then-insert without shared serialization/constraint

`dataset_store.py:273–305,385–450` checks sibling names across folders/files using SELECT; schema at `:198–226` lacks normalized sibling unique constraints and read checks precede writes.
Two separate cooperating store instances can both accept the same case-insensitive sibling name, or encounter transient locking errors rather than intentional conflict handling.
`test_sibling_names_are_case_insensitively_unique` is sequential same-object folder creation only.
Future action: share the mutation boundary or intentional database constraints across the two namespaces; verify mixed folder/file and two-owner paths after audit, without removing essential folder semantics.

#### ROOT-F012 — P2, filename source defect: negative extension budget can exceed platform filename limit

`dataset_store.py:129–139` subtracts extension bytes from the budget without checking for a negative result.
For a very long extension, a negative stem slice can retain a substantial stem and return a final name beyond 255 bytes; OS failure replaces the specified bounded/rejected-name validation outcome.
The existing long-UTF8 test covers a long stem with `.tif`, not extension-dominated names or exact collision suffix bounds.
Future action: reject impossible valid names or bound them under the preserved extension/UTF8 policy; no execution in this batch.

#### ROOT-F013 — P2, known metadata defect/test oracle: original names inferred from sanitized names

`dataset_store.py:118–158,363` discards submitted directory/truncation/reserved-name detail and strips any natural numeric suffix as if it were a collision suffix.
A genuine `cells_1.tif` loses original-name fidelity even on its first upload; metadata is independent of safe physical/display naming in v1.
`test_id_round_trip` includes numeric names but checks only ID/delete, and router traversal test asserts sanitized original metadata, encoding the known debt.
Future action: preserve original submission separately and explicitly reconcile multipart filename normalization/legacy reconstruction; retain safe basename and collision behavior.

#### ROOT-F014 — P2, admission/test-oracle source mismatch: Content-Length guard is a dependency after multipart parsing

`routers/datasets.py:92–119` documents pre-body parsing, but UploadFile/Form causes FastAPI form parsing before dependency resolution; the installed FastAPI ordering was traced during earlier reconnaissance.
`test_upload_dos_guard_rejects_huge_content_length` sends a non-multipart bytes body and asserts status only; it cannot prove multipart admission timing.
Future action: preserve the specified coarse early guard with actual request-admission placement and a distinguishing multipart parser boundary test, or explicitly resolve the contract; avoid generic unrelated hardening.
Per-file byte counter exists and is a different guarantee.

#### ROOT-F015 — P2, per-file source mismatch: SQLite publication error aborts successful siblings' response

`routers/datasets.py:124–164` catches store-domain, ValueError and OSError failures, not sqlite3.Error during INSERT/commit.
A later file's catalog failure turns a multi-file response into a request error after an earlier file was durably stored, contrary to successful-file disclosure.
Existing partial-success test uses oversize and exercises a caught domain error, not catalog failure.
Future action: define safe catalog error wrapping/per-file response after publication ownership is reviewed; do not hide successful uploads or suppress ambiguous commit outcomes.

#### ROOT-F016 — P2, client attempt-identity source defect: cancelled upload can overwrite immediate retry

`frontend/src/stores/datasets.ts:116–143,202–214` reuses the same entry for retry while the old aborted request may still settle.
The old catch checks its own aborted signal but sets `next.entry.status` to cancelled whenever the reused entry is currently uploading; the later attempt's controller is protected in finally, but its status is not.
The cancel and queued-batch tests never retry before the old abort settles.
Future action: bind every publication/cleanup to a captured attempt identity and preserve concurrency/progress/retry semantics; no new test or fix authorized during review.

#### ROOT-F017 — P2, client snapshot source risk: dataset refresh can overwrite newer local accepted changes

`frontend/src/stores/datasets.ts:64–67,198–200` publishes two list snapshots without ordering against accepted uploads, another refresh or workspace changes.
A stale in-flight list can remove a newly uploaded file from the visible store; dataset/folder parallel lists may also represent different catalog revisions.
Store tests mock list calls as immediate empty arrays and do not exercise refresh ordering; panel callers require full review next.
Future action: trace panel/workspace ownership and choose one coherent refresh publication rule; no broad new coordinator is assumed.

#### ROOT-F018 — P3, maintainability candidate: dataset API types duplicate generated schema

`frontend/src/api/datasets.ts:3–28` hand-maintains DatasetRecord/Folder/Upload/Selection shapes alongside generated OpenAPI types.
Current fields match the backend reviewed here; this is drift/duplicate authority risk, not an observed wrong response.
Future action: reconcile generated-type policy and adopt generated models when coherent; retain transport/progress options as client-specific types.
API wrapper tests verify endpoint/form options but do not independently certify server schema compatibility.

#### ROOT-F019 — P2, source defect: output-schema resolution dereferences an absent built workflow

`backend/src/bioimageflow_server/routers/graph.py:233–246` protects only the call to build_workflow, then dereferences result.workflow._nodes.
A confirms graph_builder returns BuildOutput(workflow=None) for source-capture failures (SyntaxError/ImportError/OSError), so a transient invalid owned source can raise AttributeError instead of the documented unresolved schema.
Existing A-owned malformed-schema test has a compilable workflow with a bad constant, missing the absent-workflow return distinction.
Future action: handle the typed build outcome through the public materialization/schema boundary; retain real 404 for absent requested node.
No execution occurred; A owns full builder/test review and root fully read this caller.

#### ROOT-F020 — P3, architecture candidate: output-schema router depends on private library node storage

`routers/graph.py:242` accesses Workflow._nodes directly, despite context's public-library boundary.
Future action: identify an existing public node/schema API and use it coherently with ROOT-F019; if none exists, propose a narrow library public capability rather than a second platform authority.
Current node absence handling and serialized column schema must remain unchanged; private access alone is not proof of current functional failure.

#### ROOT-F021 — P3, test portability/oracle candidate: traversal test reads host /etc/passwd

`backend/tests/test_services/test_dataset_store.py::test_store_blocks_absolute_path_escape` checks `/etc/passwd` bytes, creating a Unix-only dependency rather than owning the purported outside-root victim.
`test_list_when_root_missing` describes removing a directory after startup but only supplies a never-existing path, so it does not exercise the stated lifecycle.
Future action: use a disposable outside-root sentinel and align titles with actual lifecycle assertions; retain traversal and constructor behaviors without duplicate weak tests.

#### ROOT-F022 — P3, configuration/API clarity candidate: accepted dataset settings do not drive runtime configuration

Settings exposes and accepts datasets_root/max_upload_size, but app.py:1055–1066 uses AppConfig/default cap and active workspace, not those live fields.
V1 calls deployment configuration authoritative; the schema/API accepts misleading apparently editable values and model tests only validate storage.
Future action: reconcile admin configuration versus persisted preferences and UI/API descriptions; do not silently move roots or change upload policy to match a field name.
Complete app/spec review may establish an intentional startup-only or retained compatibility explanation.

#### Reviewed retain decisions

Keep separate JSON preferences and injectable secret store; typed Napari registry CAS rejects generic registry mutation and preserves unrelated fields under its lock.
Retain per-file upload cap, safe stored identity, logical folder/selection behavior and explicit delete preview/revision; defects do not justify feature removal.
Drag MIME decoder performs structure/dedup checks rather than server containment; its consumers remain responsible for path authority.
Current API wrappers are deliberately thin; mocked wrapper/store success is not server persistence or native acceptance.

### Dataset panel and bridge clients — root batch 2

#### ROOT-F023 — P1, destructive-confirmation source risk: dataset delete preview and selection are not captured together

`DatasetsPanel.vue:579–602` has one shared deletePreview ref; confirmDelete awaits using the current selection without dialog/request identity, and deleteConfirmed reads current selectedIds again.
Cancel/reopen on another selection can let an earlier preview overwrite the newer dialog. Catalog revision alone does not bind the displayed counts to the exact selection when selection changes without a catalog mutation.
The existing full component file mocks preview/delete but does not exercise confirmation; real E2E tests cover upload/organize/drag/cancel, not recursive-delete confirmation ownership.
Future action: capture selected identities, revision and dialog attempt together, refuse stale completion/confirmation and retain conflict/partial errors; no new reproduction was run.
Related editor save completion can close a subsequently reopened dialog and must be checked under the same narrow owner rule.

#### ROOT-F024 — P1 potential impact, source risk: deferred dataset resolution can address a different active canvas

`DatasetsPanel.vue:675–694` awaits real selection resolution, then calls setup-created commands.addToolNode/updateParameters; the update captures a node ID but no canvas registration or incarnation.
Complete command-facade/registry review confirms updateParameter/addToolNode resolve the active command resource at invocation, so an awaited dataset result can mutate the newly active canvas.
The exact facade-test review is still pending; no interleaving was executed.
Existing Files-node component assertions mock commands and resolve immediately; no held result plus canvas switch/same-node-ID distinction exists.
Future action: preserve originating canvas/session identity and one-edit parameter replacement across the await; do not narrow multi-canvas operation or silently lose picked data.

#### ROOT-F025 — P3, E2E oracle/title candidate: managed-file snapshot journey does not assert captured Files parameters

`frontend/tests/e2e/datasets-panel.spec.ts::uploads, organizes, renames, and snapshots managed files` checks upload presentation, rename/folder UI, drag-created node count/position and action geometry, but never the actual Files parameters or saved/reopened snapshot.
Component tests check explicit payload with mocked commands; this is a different layer and does not substantiate the real E2E title's snapshot claim.
Future action: either align the stated coverage or add one meaningful real exact-parameter/persistence assertion to the existing journey after audit, avoiding another long generic end-to-end chain.
Fake TIFF bytes are appropriate for transport/client UI but supply no scientific image-read acceptance.

#### ROOT-F026 — P2, class/name authority source risk: selected Files tool inferred from display name

`DatasetsPanel.vue:316–322` treats a selected node whose toolName lowercases to files as the built-in Files contract and offers path/files replacement.
A same-name bound custom/versioned tool can have another parameter contract, consistent with the catalog-binding issues in A-F001–003.
Full tool/UI-node metadata consumer review is still pending with A; this is a qualified authority candidate, not a new demonstrated failure.
Future action: distinguish the actual compiled/bound capability while retaining built-in source convenience and accepted aliases.

#### ROOT-F027 — P2, failure-presentation source gap: initial catalog refresh rejects without an actionable panel state

`DatasetsPanel.vue:346` starts `void store.refresh()` without catch; `stores/datasets.ts:64–67` also has no loading/error state.
A rejected dataset/folder list can leave an empty tree saying No datasets found with an unhandled promise, even though absence and service failure are different outcomes.
Full component fixtures always resolve initial lists; main E2E failure/cancel concerns only uploads.
Future action: surface one coherent catalog load/failure/retry state without weakening actual list errors or masking partial list consistency.

#### ROOT-F028 — P2, retry destination source risk: retries use current selection rather than original upload folder

`DatasetsPanel.vue:48` passes live uploadFolderId to retry; UploadEntry retains no original folder even though the queued attempt did.
Changing selection after a failed/cancelled upload can place a retry in another folder or root without an explicit destination change.
The store error tests inspect status/detail only and do not retry into a held original folder.
Future action: establish expected retry provenance and capture/present original destination or require intentional retargeting; do not silently infer it from current unrelated selection.

#### ROOT-F029 — P2, partial-move source risk: refresh starts while sibling mutations may still run

`DatasetsPanel.vue:641–658` awaits Promise.all for checked-node moves, then refreshes in finally.
The first rejection ends Promise.all while other PATCHes can remain in flight; refresh can capture the catalog before those successful siblings commit and publish a misleading partial tree.
The component move test has immediately successful mocks; real E2E response count/child assertions cover all-success only.
Future action: retain each settled outcome before canonical refresh and report actionable partial move failures, with captured operation ownership; no all-or-nothing folder transaction is promised.

#### ROOT-F030 — P3, suite-cost candidate: settings E2E serial scope groups independent scenarios

`frontend/tests/e2e/settings.spec.ts:7` configures every settings case serial, while each starts a new page and most assert presentation or independent intercepted viewer state.
A single earlier failure consequently skips unrelated later settings assertions; potential scheduling cost and genuine shared fixture dependencies need the reviewer-owned global harness/fixture analysis.
Future action: measure/evaluate whether serial scope is necessary and separate only coupled cases; no removal, runtime speedup or passing run is claimed.
The viewer reopen journey persists only its intercepted in-memory backend model, not real keyring/provisioning/native app state.

#### Retained complete-file judgments

Path picker routes actual pywebview availability to native selections and browser selection to one managed-dataset picker; re-entry returns null to the previous owner, folder picking is deliberately unsupported in browsers.
The native bridge uses typed call forwarding and detects optional detached-editor capability separately; complete units prove calls/fallbacks, not operating-system behavior.
Execution lock synchronously checks target, scoped validation and exact accepted draft revision before dispatch; complete tests retain starting/stopping locks, selected dependency error scope and stale target refusal.
Its global watch is component-scoped in normal Vue usage; store-level lifetime consumers remain under B/A review and no new lock regression is inferred.
Complete panel test fixture distinguishes real PrimeVue checkbox/search behavior from stubbed command forwarding and controlled drag events; retain those boundary differences.

### Environments and public lifecycle — B batch 1

#### B-F001 — P1 defect/spec/test: matching recipe is reused despite BioImageFlow's force promise

Library `packages/bioimageflow/bioimageflow/env_manager.py:418–424` promises `replace_existing=True` replaces even a current recipe; lines 435–446 close a cached pool and lines 484–491 forward the flag to public `provision`.
Wetlands `_internal/provisioning.py:2324–2334` returns the matching ready generation before evaluating replacement permission.
Closing/restarting workers therefore does not force a new physical generation.
The previously retained real T1 generation red demonstrates the matching-generation failure; this audit performed no new runtime reproduction.
Only the relevant provisioning excerpt was read here, so that file remains pending.

`tests/unit/test_env_manager_core_dependency.py::test_get_or_create_explicitly_recreates_current_cached_recipe` checks close/start counts and flag forwarding against a fake whose environment returns the same pool every time.
The changed-recipe test at lines 388–403 even asserts `new_pool is old_pool`; these are adapter-interaction oracles, not generation replacement evidence.
Retain their useful forwarding/isolation assertions but distinguish the force integration oracle.
Future action: after the complete-review gate, independently review the held same-injected-wrapper public remove→provision→start plan, reconcile the existing public force promise and add genuine generation/pool/file/failure/isolation evidence.
Do not narrow the force requirement, delete directories privately, or weaken normal matching reuse.

#### B-F002 — P2 source-risk/design: failed pool closure discards wrapper ownership before physical success

Library `env_manager.py:542–554` removes the pool/environment/spec/config entries before `pool.close()`, suppresses its exception and returns success.
`get_or_create(..., replace_existing=True)` then proceeds after this best-effort stop.
A failed close can leave a physically live resource absent from wrapper status and unavailable to wrapper retry; Wetlands may still refuse removal through its separate ownership tracking, so unsafe destruction or a real worker leak is **not** demonstrated here.
The established best-effort stop contract is itself a compatibility consideration, not permission to change it silently.

`tests/unit/test_environment_lifecycle.py::test_manager_stop_and_status_introspection` injects failure and asserts the cache is empty and closure is attempted only once.
Future action: distinguish strict recreate closure from best-effort shutdown, retain the selected failed owner for strict-operation retry, and use a physical-resource failure oracle before changing status/stop compatibility.
Keep engine-owned/external-manager lifetime boundaries and unrelated pools intact.

#### B-F003 — P2 source defect: local mapping names use inconsistent distribution canonicalization

Library `env_manager.py:184–193` compares declared local mapping names using only underscore replacement and lowercasing.
Its direct-URL path uses `re.sub(r"[-_.]+", "-", ...)` at line 219, while Wetlands `specs.py:370` uses packaging's canonical name normalization.
A valid project name such as `My_Distribution.Name` canonicalizes to `my-distribution-name` in Wetlands but to `my-distribution.name` in the wrapper mapping path and is incorrectly refused.
This mismatch follows directly from the normalization expressions; no input was executed here.

Wetlands `tests/test_v2_specs.py::test_local_package_discovers_and_canonicalizes_distribution_name` covers dotted project canonicalization.
Library `test_wetlands_v2_translates_local_pypi_reference_to_typed_package` exercises the other translation path, not dotted declared mapping names.
Future action: use one public canonicalization convention and a focused mapping-path case while retaining rejection of genuinely different project names.

#### B-F004 — P3 source-risk/validation: local mapping translation converts invalid values into different recipes

Library `env_manager.py:179–183` applies `bool()` to `editable` and `tuple()` to `extras` before creating public `LocalPackage`.
Thus an `editable="false"` mapping means editable installation, and an `extras="cuda"` mapping becomes four one-letter extras.
Wetlands `specs.py:387–391` would explicitly reject a string extras input, but the wrapper conversion defeats that public validation.
This is a malformed-input interpretation risk at the dictionary boundary, not a claim that correctly typed recipes fail.
No focused wrapper negative test currently distinguishes these cases.
Future action: define and validate supported mapping value types before translation; retain valid boolean/list/tuple inputs and public package validation.

#### B-F005 — P2 source-risk: rejected construction can establish sticky process manager configuration

Library `env_manager.py:244–249` obtains/initializes the shared manager before rejecting incompatible or invalid Core-source configuration at lines 259–274.
`get_shared_environment_manager` returns an existing manager without applying later root/configuration requests at lines 123–125.
A failed first wrapper construction can therefore pin the process manager root/configuration, and a corrected later constructor can silently receive that root.
Construction is filesystem-side-effect-free at the Wetlands layer, but process singleton authority is a side effect.
Ordinary successful first-initialization-wins behavior is documented and should not be mistaken for this rejected-construction case.

`test_explicit_false_rejects_explicit_core_source_argument` and `test_invalid_core_source_environment_is_rejected` assert the error, not subsequent corrected root ownership.
Future action: a distinguishing failed-first-construction→corrected-root diagnostic, then validate wrapper configuration before first shared initialization if confirmed compatible.
Preserve one process manager and deterministic established root policy.

#### B-F006 — P2 source-risk: manager shutdown conflates an operation's TimeoutError with its own wait deadline

Wetlands `environment_manager.py:411–422` catches every `TimeoutError` from `operation.wait_for(remaining)` as close deadline expiry.
`Operation.wait_for` at `operation.py:210–211` also propagates the operation's stored exception unchanged.
An active operation that itself ends with `TimeoutError` can therefore produce the `normalized_timeout is not None` assertion during `close(timeout=None)`; with a finite timeout it is mislabeled as close timeout and prevents the subsequent cleanup pass.
The generic exception path is source-proven; which actual provisioning/worker failure paths deliver an unwrapped TimeoutError remains for the incomplete helper review.
No real external failure has been reproduced by this audit.

`tests/test_v2_manager_shutdown.py::test_close_aggregates_active_operation_failure` uses RuntimeError, while `test_close_timeout_is_one_deadline_for_active_operations` covers genuine wait expiry.
Neither distinguishes an inner TimeoutError after terminal completion.
Future action: exact exception-provenance diagnostic and bounded correction retaining one shared close deadline, aggregate errors and retryable resource cleanup.

#### B-F007 — P2 source-risk/design: terminal listeners can synchronously wait on their own unpublished completion latch

Wetlands `operation.py:457–485` installs terminal state, delivers the terminal event synchronously, then sets `_done`.
A terminal listener calling the same operation's `wait_for()` waits for a latch that its own callback prevents the publisher from setting.
This follows from the publication ordering; no hanging test was run.
The public listen surface does not state a nonblocking/no-wait callback restriction.
Manager close has an active-operation thread guard, but that does not by itself resolve every operation-listener reentrancy path; no blanket manager-listener bypass is claimed.

`tests/test_v2_operation.py::test_terminal_state_and_event_are_published_atomically` checks state/event visibility, not listener reentrant wait.
`test_listener_failure_does_not_fail_operation` checks ordinary thrown exceptions, not blocked callback completion.
Future action: define callback reentrancy semantics, add a bounded distinguishing diagnostic and consider fail-fast self-wait detection without weakening terminal publication ordering or cancellation-cleanup semantics.

#### B-F008 — P3 source-risk: fast cancellation completion can leave the executor waiter exception unconsumed

Wetlands `operation.py:216–229` shields an executor future and requests operation cancellation, then drains only while `_done` is unset.
If cancellation callbacks complete the operation synchronously or completion wins the loop-entry race, the loop can be skipped while the shielded waiter later receives OperationCanceled or another failure without being awaited/retrieved.
That can generate an unhandled-future diagnostic; this is **not** evidence that physical cleanup is abandoned.
`test_canceling_await_requests_operation_cancellation_and_waits_for_cleanup` deliberately delays cleanup, covering the loop body rather than this fast path.
Future action: immediate-completion cancellation with an event-loop exception-handler oracle, then consume the waiter outcome while preserving outer cancellation and physical completion.

#### B-F009 — P3 validation/design debt: public typed flags are not uniformly validated

Wetlands `specs.py:335–392` never validates that `LocalPackage.editable` is a boolean, and `PostInstallCommand` at lines 400–411 treats any truthy `shell` value as shell mode.
Several sequence entries are also coerced through `str()` rather than checked against their annotated types.
Malformed direct API callers can select semantics different from an apparent configuration value, such as the string `"false"` enabling shell mode when a display is supplied.
Correctly typed Python callers are unaffected; runtime strictness requirements must be reviewed rather than inventing a universal prohibition.
Existing spec tests enforce safe shell display and dependency formats, but do not distinguish non-boolean mode values.
Future action: clarify accepted coercion policy and prioritize flags that choose side effects; retain the safe-display requirement, immutable snapshots and portable recipe identity.
B-F004 is the separate wrapper conversion that already bypasses an explicit public extras rejection.

#### B-F010 — P3 test isolation/debt: removal fixture managers can retain idle background reclaimers

Wetlands `environment_manager.py:212,256,276` wakes/enqueues the manager reclaimer on mutation/removal.
The inspected `environment_cleanup.py:624–653` creates a daemon thread that waits indefinitely when idle until explicit close at lines 698–711; it holds the manager through the reclaimer object.
For example, `tests/test_v2_environment_management.py::test_remove_ready_environment_returns_snapshot_and_invalidates_cache` creates a manager and completes removal at lines 194–214 without closing it.
Other reclamation tests intentionally close managers, but there is no per-test cleanup in the complete-read `tests/conftest.py`.
A passed test can therefore leave idle manager/reclaimer resources resident for the remainder of that test process.
This is source-confirmed lifetime behavior; retained thread counts, material suite cost and cross-test filesystem interference have **not** been measured.
The complete cleanup helper still remains pending despite this scoped loop review.
Future action: fixture/context ownership with failure-safe manager cleanup after the destructive test phase; keep physical-reclamation blocking and retry tests' intentional timing distinctions.

#### B-F011 — P3 test isolation: Core constructor tests clear environment variables but retain process singleton state

Library `tests/unit/test_env_manager_core_source.py:15–18` and `test_env_manager_core_dependency.py:26–29` clear two environment variables through autouse fixtures but do not reset the process shared manager.
The test-directory inventory contains only `tests/integration/conftest.py`, with no nearer tests or unit conftest.
The shared-infrastructure reviewer independently read root conftest and confirmed its reset is confined to the session-scoped `complete_wetlands_config` fixture's entry/finally, not these individual constructor cases.
The Core-source tests therefore share a first initialized public manager while assertions mostly inspect only their wrapper's Core dependency.
This can hide B-F005 or make first-root/config behavior order-dependent; no executed contamination outcome is claimed.
Future action: identify tests needing constructor isolation versus tests intentionally asserting singleton reuse, then use explicit fixture ownership/reset only where appropriate.
Do not globally replace the singleton or erase intentional shared-manager compatibility coverage.

#### B-F012 — P3 test resilience: operation tests can leave runners blocked after an assertion/observation failure

Wetlands `tests/test_v2_operation.py:68,139,178` uses runner `Event.wait()` calls without a timeout and releases them only on the normal assertion/observation path.
An early assertion failure or failed event observation can leave the daemon runner stalled, and the async event test can wait indefinitely for completion rather than report its distinguishing failure promptly.
Some later concurrency cases are bounded; the issue is these specific gates, not all concurrent tests.
Future action: bounded gates and `finally` releases with explicit completion joins where appropriate, preserving the source ordering/cancellation race oracles instead of replacing them with timing sleeps.
No hang was executed, and no measured runtime improvement is claimed.

### Shared test and documentation infrastructure — reviewer batch 1

#### reviewer-F001 — P1, source configuration defect: cold platform CI cannot supply its editable library inputs

`backend/pyproject.toml:26–27` selects sibling BioImageFlow source; `backend/uv.lock:61,74,90,145` locks BioImageFlow and Core to `../../bioimageflow/packages/...`.
Every platform backend/browser/certification CI job checks out only the platform repository, then runs frozen backend synchronization; examples are `.github/workflows/ci.yml:95–105,169,208,278,337,398,436`.
There is no sibling checkout step in the complete workflow.
`docs/testing.md:27` explicitly confirms that a checkout without this sibling cannot run the frozen sync.
The source wiring therefore lacks an input required by clean GitHub-hosted jobs; cached dependency downloads do not establish that missing source checkout.
No CI run was performed here and no particular historical run is labelled failed.
Existing `backend/tests/test_ci_job_selection.py` checks selected jobs, not cold checkout/install closure.
After the full-review gate, choose one reproducible dependency policy: capture/check out the exact required library revision while this editable fix is necessary, or return to a published registry dependency once that fix is actually released.
Preserve frozen resolution and honest editable-source provenance rather than bypassing it with an unrelated installed package.

#### reviewer-F002 — P3, documentation drift: prerequisites and runner help disagree with authoritative inputs

`scripts/test:58–61` says CI and local runs use published versions locked in the backend lock, although the lock contains editable BioImageFlow/Core inputs.
`README.md:28–30` says Python 3.12 or newer and Bun or Node 20+, while `backend/pyproject.toml:4` restricts Python to `<3.15` and the authoritative frontend/browser runner explicitly requires Bun.
Node may remain a valid separately documented development path; it is not sufficient for the documented Bun runner commands.
Use the existing precise explanation in `docs/testing.md:27` and distinguish development alternatives from validation prerequisites.
This is a small documentation correction after the hold, not a reason to change supported runtimes or remove editable-source testing.

#### reviewer-F003 — P2, test-selection gap: Wetlands-only integration tests miss both CI tiers

Library `tests/integration/test_wetlands_task_api.py:36` has `pytestmark = pytest.mark.wetlands`; whole-file marker searches found no `complete` marker.
Ordinary integration CI explicitly excludes `wetlands` (`.github/workflows/ci.yml:95`), while complete Wetlands CI requires `complete and wetlands` (`.github/workflows/complete.yml:51`).
Root `conftest.py:50–62` skips external markers by default; it does not add a `complete` marker.
The completely read integration conftest has no selection hook that supplies that missing marker.
These source selectors therefore omit this file from both tiers, even though the enabled local selector `-m wetlands --run-complete` would select it.
The test-body file belongs to the execution reviewer: only its first 135 lines and whole-file marker searches were read here, and **no full-file credit is claimed**.
That owner has acknowledged the handoff and will confirm the complete marker/test contract in its assigned batch.
After review, reconcile the existing resource marker with the intended CI selector or marker policy, using the existing tests; retain the opt-in real-worker boundary and do not run these in deterministic CI by accident.

#### reviewer-F004 — P3, documentation defect: the documented release-validation job no longer exists

Library `docs/source/reference/testing.md:154–159` says Complete validation exposes a manual `release-validation` job and that the release workflow reruns equivalent deterministic evidence.
The complete workflow has only four resource jobs and no such dispatch choice or job (`complete.yml:13–18,32–123`).
The completely read release workflow instead requires a successful ordinary CI run for the exact commit (`release.yml:72–85`), then validates/builds artifacts; it does not rerun deterministic tests itself.
Correct that description to the actual retained evidence policy after the hold.
Do not invent a new repeated release suite merely to preserve stale wording.
The release workflow remains pending for full review of `scripts/release_set.py`, `scripts/check_package_release.py` and their release-tooling tests; this documentation finding does not certify those helpers.

#### reviewer-F005 — P3, infrastructure hardening candidate: aggregate acceptance does not distinguish selected skips

Platform `.github/workflows/ci.yml:240–258` calls its aggregate “Require every selected job to pass,” but accepts `skipped` for every dependency without checking the changes job's selection outputs; even the changes job is accepted when skipped.
Current individual job conditions correctly use those outputs, so no incorrectly skipped current run is demonstrated.
The aggregate would nevertheless accept a future condition/output mismatch that silently skips a required selected job.
When this infrastructure is next changed, consider checking `success` for selected jobs and allowing `skipped` only for explicitly unselected jobs, with a small selection/result truth-table oracle.
Preserve conservative changed-path selection and fail-safe unknown/empty inputs; do not replace job selection with all suites on every edit.

#### reviewer-F006 — P3, documentation consistency candidate: cheap existing guards are not all in the CI docs boundary

Platform `scripts/test:370–381` runs the campaign dashboard/link guards before Sphinx, whereas CI's documentation job runs only Sphinx (`ci.yml:136–141`).
The existing generated-spec TOC producer supports `--check` (`scripts/generate_specs_toc.py:91–101`) but is not invoked by either this docs lane or the completely read CI workflow.
The producer names its three spec inputs and generated output at lines 14–19; the source documents and generated output are still pending full review, so no stale TOC is claimed.
A Sphinx success alone therefore does not establish campaign-table consistency or generated-TOC freshness.
After the hold, decide whether to reuse these cheap existing guards at the appropriate documentation boundary and align reported scope; no new browser lane or duplicate Sphinx invocation is needed.
Keep the dashboard guard's limited role clear: it checks documentation structure/counts and revision fields, not the authenticity of runtime evidence.

#### reviewer-F007 — P3, distinguishing-oracle candidates in existing runner/selector tests

`backend/tests/test_test_runner.py:99–103` establishes transient coverage cleanup by searching for two source strings; it does not exercise cleanup after success or failure, and dead/unreachable cleanup could satisfy it.
`backend/tests/test_ci_job_selection.py:46–53` checks the ordinary backend-test Firefox exclusion, but no test covers the implemented exception for `backend/tests/e2e_app.py` (`scripts/ci/select_ci_jobs.py:46–48`).
Both counterpart test files were read completely here but belong to another owner and receive no duplicate ledger credit.
If those infrastructure paths change after review, extend the existing oracles with the missing behavior, using stubbed commands where appropriate rather than launching product/browser suites solely to test routing.
The existing fail-fast and explicit Firefox/project tests already distinguish useful behavior and should be retained.

#### reviewer-F008 — P3, maintenance candidate: duplicate marker registration authority

Library `pyproject.toml:64–79` and `conftest.py:11–29,45–47` separately register the same markers and descriptions.
The inspected definitions are currently consistent; this is drift risk, not a present marker-validation failure.
Prefer one authority or a small existing configuration consistency assertion if future marker work warrants it; defer a standalone refactor with no behavior benefit.
Preserve strict marker checking, explicit resource gates and the separation between descriptive resource markers and CI selection.

#### reviewer-F009 — P3, packaging reproducibility candidate requiring launcher-contract review

Platform launcher archive configuration runs plain `bun install` (`backend/packaging/launcher/application.yml:15–18`), while ordinary and full CI use `bun install --frozen-lockfile`.
This permits packaging to resolve or update dependency state where CI refuses lock drift.
The launcher consumer/release implementation is not completely reviewed in this batch, so this is a qualified reproducibility candidate, not a proven broken archive.
Review that producer contract in the release batch before deciding whether frozen installation is the intended policy.
Preserve the signed-manifest trust key, included frontend artifact, desktop entry point and initialization handshake; the different macOS/Windows launcher package versions are not evidence of an application-version defect.

#### reviewer-F010 — P3, evidence-scope gap: an empty manual public-data tier is green with a warning

Library `complete.yml:74–83` converts pytest's no-tests status 5 into success and emits a warning.
That is explicit rather than silent, but a green manually selected public-data job does not prove any public-data case ran; `docs/source/reference/testing.md:176` otherwise describes manual resource suites as blocking pre-release evidence.
The scientific test owner must establish whether applicable public-data obligations are actually empty, deselected, or covered under different selectors before proposing coverage changes.
Document an empty tier as no evidence, and make any future applicable gate distinguish that outcome from a passing populated tier.
Keep scheduled service-dependent monitoring nonblocking where documented and preserve the explicit public-download opt-in; do not add resource tests merely to make the count nonzero.

#### reviewer-F011 — P4, checker scope/documentation candidate: local link existence is narrower than link correctness

`scripts/verify-platform-test-links.py:24–30` ignores fragment-only targets and tests only local file existence; it does not validate heading fragments, reference-style links or all Markdown link syntax.
This is an appropriate bounded file-existence guard, but its generic “Verified local links” output can be overread as anchor validation.
Subsequent administrative validation demonstrated two broken MyST heading-fragment links while this file-existence guard passed; no general Markdown parser is proposed.
Clarify that scope in checker/lane documentation when it is next touched, or reuse an existing anchor-aware documentation check if one is found during the remaining audit.

### Drafts and source mutation — A batch 2

#### A-F013 — Medium, static defect + reviewed-test gap: TOML rewriting is not TOML-aware

`services/workflow_draft.py:188–216` removes existing server tables with a line parser recognizing only headers whose stripped text ends in `]` and exactly matches the unquoted dotted name.
A valid `[mcp_servers.bioimageflow] # comment` or `[mcp_servers."bioimageflow"]` survives; appending the generated equivalent table produces duplicate TOML definitions.
Conversely an unrelated commented table header encountered while `skipping=True` fails to end skipping, so unrelated configuration can be dropped.
There is no parse validation before replacing the file.
`test_routers/test_workflow_drafts.py::test_get_synthesizes_draft_from_saved_workflow` parses only a newly generated empty-file configuration; it cannot distinguish preserving valid pre-existing syntax.
No TOML failure was executed here; this is complete-source reasoning, not a new runtime reproduction.
Retain unrelated client configuration and deterministic generated server configuration; a future correction should use valid TOML-aware table ownership and preservation, with existing-config assertions rather than another whole GUI journey.

#### A-F014 — Medium, static commit-boundary defect + error-path oracle gap: draft commits can fail acknowledgment afterward

`services/workflow_draft.py:817–833` writes the next durable draft revision before `write_agent_context` finishes.
`write_agent_context:508–571` catches optional client-config errors individually but mandatory agent-state JSON or workspace AGENTS writes can still raise after the draft commit.
The route receives no successful service return and publishes no draft event; an old-CAS retry then conflicts against the already incremented revision.
Separately `routers/workflow_drafts.py:99–111,163,201` invokes the notification callback without the post-commit exception isolation already used by ordinary workflow tree events.
This is an acknowledged-state/response boundary risk, not evidence of lost graph bytes; no injected I/O or notification failure was executed here.
`test_put_writes_atomic_draft_and_conflicts_on_stale_revision`, `test_put_publishes_one_workflow_draft_changed_event_per_success`, and `test_put_does_not_publish_for_unsuccessful_writes` cover ordinary commit/CAS and refusal, but do not inject failures after durable write.
`test_routers/test_workflows.py::test_committed_move_ignores_tree_change_publish_failure` demonstrates the intended nearby separation of commit and notification.
Retain atomic CAS and integration diagnostics; future action must make the commit acknowledgment contract explicit without rolling back a committed draft merely because ancillary integration fails.

#### A-F015 — Medium, static destructive-update refusal defect + oracle gap: enclosing exposed ports are not repaired

`services/workflow_sources.py:426–472` replaces a child workflow and filters only its direct edges and binding IDs.
It leaves enclosing `graph.interface.inputs.targets` and `graph.interface.outputs` referring to removed child ports.
Changed field→dataframe input IDs also retain constants that `models/graph.py:329–342` forbids; edge-kind incompatibilities are retained by ID.
`_destructive_effects:346–394` describes direct edges/bindings but not enclosing interface exposures.
Store `_write_raw:1505–1508` revalidates, so apply refuses the resulting graph and rolls back newly published files; it does **not** persist a corrupt document.
A confirmed source update can therefore remain unappliable, with the exposed-port consequence absent from its effect summary.
`test_source_refresh_is_previewed_and_applied_explicitly` uses empty interfaces; no reviewed source test exercises removing/retyping a child port exposed by its parent/ancestor.
Retain stable port identity, exact explicit confirmation and structural validation; future action is a deliberate cascading repair/refusal policy that includes enclosing exposures, rather than bypassing validation.

#### A-F016 — High functional impact, static cross-version defect + oracle gap: trusted Python custom source bytes are dropped

`services/workflow_sources.py:504–525` converts `Workflow.to_dict(include_custom_tools=True)` but extracts custom sources only when its keys equal the v1 three-key envelope exactly.
Current public library `workflow/serialization.py:25–43` returns a four-key archive-version-2 envelope including `viewing_requirements` whenever custom sources exist.
`graph_translator.py:407–420` accepts that v2 graph, so source IDs survive while the Python materializer returns an empty source-record list.
Fresh authored custom tools then cannot transfer their captured bytes into workflow-owned files; subsequent collection/validation can fail because referenced source files were never staged.
The no-custom-source case remains valid and returns a bare graph.
`test_python_materialization_uses_workflow_local_factory_and_fresh_helpers` creates an empty Workflow and checks display-name/helper freshness, so it passes without crossing the actual custom-source boundary.
`test_editable_workflow_sources.py` does exercise actual custom-tool compute, but via a fake v1 archive adapter rather than this Python materializer.
No new runtime test was executed; public producer and consumer shapes directly establish the mismatch.
Retain public archive-envelope authority, source hashes/forking and viewing snapshots; future correction should share the supported envelope contract rather than another ad hoc exact-key discriminator.

#### A-F017 — Low/Medium, resource-lifetime debt: previews never expire or cancel

`services/workflow_sources.py:79,148–150,187–194,197–212` keeps every graph, source-record tuple and Python manifest in `_prepared` until successful apply.
There is no expiry, bound, cancellation route or pruning on conflict, although the unknown-token message says "expired".
Ordinary repeated canceled previews accumulate captured data for the service lifetime.
No memory-pressure benchmark or abuse claim is made; source code establishes missing disposal, not a measured exhaustion threshold.
Reviewed source tests always apply or end with a new short-lived service, so cannot distinguish lifetime accumulation.
Retain immutable captured preview semantics and exact confirmation; future action should define lifecycle/bounds and dispose abandoned tokens without reloading/replaying their source.

#### A-F018 — High potential impact, source concurrency risk + oracle gap: archive import checks execution before an await

`routers/workflows.py:854–883` calls `_ensure_unlocked`, awaits `UploadFile.read`, and imports into the store without rechecking or reserving `_idle_mutation_lease`.
A disk-spooled upload can yield; Run may reserve/start between that guard and the mutation.
The state check does not provide the ordinary save/draft route's admission exclusion.
`test_import_returns_423_while_execution_running` checks execution already running at route entry, and success uses immediately available fixture bytes; neither holds the read while another Run is admitted.
No race was executed here, and full store review remains pending; this finding is about missing route admission across the explicit await, not the separate root-owned multipart-size/guard-order issue.
Retain archive validation and actual source-commit transaction boundaries; future diagnostic must hold this existing upload-read boundary and observe actual execution admission/store mutation, before selecting the smallest shared lease correction.

#### A-F019 — Medium, static preview fidelity defect: removed-source summary includes unaffected siblings

`services/workflow_sources.py:131–145` computes `custom_source_ids_removed` from **all** parent source IDs minus replacement subtree IDs.
Replacement IDs are freshly forked, so sources used only by unrelated parent/sibling nodes are reported removed although `_replace_workflow_node` leaves those nodes and `_commit_graph_and_sources` recollects them.
This is misleading preview/confirmation context rather than actual deletion of those files.
Reviewed source-refresh tests have no custom source sibling; the editable-source embedding test proves independent files but never previews refresh in such a parent.
Retain private independent source IDs and exact actual replacement scope; future action should derive additions/removals from the resulting full graph and distinguish a referenced ID from an orphaned stored file.

#### A-F020 — Medium potential impact, cross-owner authority/interleaving risk: draft reads update workspace-wide active agent state

`services/workflow_draft.py:307,497–571` writes workspace-global `active_workflow_id`, draft revision, client configs and AGENTS for each GET as well as commit.
GET context publication occurs after authority projection and outside its workflow lock; writes for separate workflows have no shared ownership lock or request generation.
Concurrent completion can publish an older workflow/revision after a newer active UI/agent selection; client config read-modify-write also has no workspace serialization.
This requires full root-owned agent-MCP caller/active-selection contract review before concluding unintended targeting or lost unrelated config.
No demonstrated agent mis-targeting, deleted-workflow revival or data loss is claimed; generated context is explicitly part of the current GET behavior.
The synthesized-draft test verifies one request's state, not interleaving.
Retain bootstrap metadata/client commands and explicit set-active capability; parent received this handoff to resolve which action owns workspace active state.

#### A-F021 — Medium potential impact, pending lock-order risk: nested-editor exclusion is checked outside source commit lock

`services/workflow_sources.py:219–221,257–258` calls the open-editor predicate before taking the destination workflow mutation lock.
`app.py:499–504` correctly binds it to `NestedWorkflowSnapshotService.has_open_at_or_below`.
A snapshot could open after this predicate and before replacement unless snapshot service admission shares an outer lock across this source operation.
That complete service/caller review is still pending, so this is a bounded seam to resolve, not a proved race or missing production callback.
The reviewed service tests use its default false predicate and provide no controlled snapshot-open interleaving.
Retain source apply's prohibition when target/descendant editors exist, and retain snapshot-before-workflow order already enforced by move/delete; future conclusion must come from the actual snapshot admission locks.

#### A-F022 — Low, test consolidation candidate: duplicate locked draft request scaffolding

`test_workflow_drafts.py::test_put_does_not_publish_when_locked` and `::test_put_rejects_writes_while_execution_is_running` each issue the same simple locked PUT using a fake manager.
The former uniquely checks no event, while the latter uniquely checks the structured `workflow_locked` code.
They could share one exact scenario asserting both contracts, preserving the error and publication oracle.
This is a candidate only, with no measured suite-wide saving and no claim these assertions are redundant.
Held admitted-validation/Run and revision-zero reservation tests exercise different causal boundaries and should remain independent.

#### A-F023 — Low/Medium, pending public-error-contract risk: Python preview omits SyntaxError mapping

`routers/workflows.py:811–827` maps ValueError/ImportError/TypeError/FileNotFoundError but omits SyntaxError from trusted Python rebuild, unlike prepare-embedding's explicit syntax mapping.
`_materialize_python_manifest:515` delegates authoring to the public Python loader without local normalization.
If that public loader propagates invalid authoring syntax as SyntaxError, the preview returns an unstructured server error rather than repairable 422.
Complete public-loader failure semantics remain pending, so this is conditional source risk, not a newly reproduced defect.
The reviewed helper-refresh test supplies valid Python; invalid editable-source validation is a different entry point.
Retain accurate source filenames and public loader authority; resolve the exception contract in the library-loading batch before requesting any new diagnostic or repair.


### Public serialization and source capture — A batch 3

#### A-F024 — High potential impact, static public-source containment defect; platform exploit not established

Library `workflow/custom_sources.py:250–317` validates record keys and a nonempty unique source ID, but a single-file `filename` is directly joined to a fresh directory at lines294–298 without validating absolute/traversal paths.
A caller-controlled absolute filename can target another path before Python execution, with valid content/hash; no attack was executed here.
Bundle `source_id` is also inserted into `scoped_root`/filesystem path at lines323–327 without path or identifier validation, despite individual file paths being screened at lines331–335.
Public `Workflow.from_dict`, `load`, and `import_archive` all reach this loader; graph structural validation occurs after `_load_custom_sources` in loading.py363–364.
Trusted Python execution is explicit public functionality, but confinement of extracted/captured source files is still a separate boundary.
Platform `OwnedWorkflowSources.stage/_safe_file` has stronger containment and symlink checks; no platform import bypass is claimed until its full import ordering is reviewed.
Reviewed public golden archive tests contain safe names; platform `test_import_rejects_unsafe_source_paths` tests the stronger platform stage entry, not the public loader.
Retain public source/hash authority and independent bundles; future action should enforce the same complete source-path/ID containment before any file write or execution, then inspect actual public negative selectors rather than infer coverage from platform staging.
Parent/root received the security handoff; this is A's canonical finding.

#### A-F025 — Medium potential impact, public import-state concurrency risk; Low deterministic restoration defect

Library `loading.py:83–161` mutates process-global sys.path/sys.modules and restores an old sys.path snapshot without a serialization lock.
`custom_sources.py:87–109` similarly evicts/restores the global `tools` package and filters every matching root string from sys.path on exit.
That filter removes a root entry that existed before entry, even in a single call; it does not restore the prior list/multiplicity.
Concurrent public loads can choose another invocation's helper module or erase/restore another invocation's imports; no interleaving was executed here.
`test_from_python_is_fresh_and_calls_exact_factory_once` and factory inventory call serially; they distinguish sequential freshness, not simultaneous authority or prior-path preservation.
Platform source previews currently execute synchronously in their async route, but compilation/embedding use threads elsewhere; this is a public/global seam, not an assertion that every route overlaps.
Retain captured fresh helpers and cleanup on ordinary exceptions; future action must first define shared import-state ownership and use exact restoration, without deleting worker origins that live compiled workflows still require.

#### A-F026 — High functional potential, static same-ID bundle cache risk + oracle gap

`custom_sources.py:323,381–392` scopes bundle module names solely by caller source ID and resolves with importlib.import_module, which reuses an existing same-name module.
Two otherwise accepted records can carry the same nonempty ID but changed source bytes/hash; the second loader creates fresh files yet may return the first module's class and then stamp it with the second hash.
No controlled second-load execution was run, so observed stale output is not claimed.
Public exporter IDs normally derive from content, and platform `capture_library_sources:95–99` hashes complete records, which mitigates its ordinary compile/export path.
The public loader does not enforce such an ID/content equivalence, so arbitrary valid explicit IDs are a distinguishing boundary.
Single-file loading explicitly replaces sys.modules instead, raising a separate worker-origin lifetime question for already compiled workflows; B received that qualified handoff.
Golden archive roundtrip and helper freshness tests do not reload a directory bundle with the same ID and changed bytes.
Retain independent compiled snapshots/public worker-origin authority; future diagnostic should use valid changed-hash bundle records and actual compute before selecting content scoping or conflict refusal.

#### A-F027 — Low/Medium, temporary-source lifetime and error cleanup debt

Public `loading.py:88–91,169` and `custom_sources.py:294,324` create persistent mkdtemp trees.
There is no cleanup on later syntax/hash/construction failure, and no explicit lifetime owner/disposal on successful workflows in these files.
Successful source paths can be required for worker imports, inspection and future export, so blindly deleting them after construction would violate retained compiled-source semantics.
The actionable source-proven issue is failure-path orphaning; long-lived successful growth remains a lifetime design question for runtime/worker-owner review.
Reviewed tests use short-lived workflows and do not inspect these library-created global temporary directories.
Retain source availability for live workflows; future action should associate immutable source storage with an explicit owner and clean failed loads after preserving exception diagnostics.

#### A-F028 — Low, duplicate/dead authority debt: unused platform import scope

Platform `services/workflow_archive.py:30–47` duplicates a process-global import helper despite read_archive explicitly not extracting/importing tools.
Repository search finds only its definition; active archive import scopes are library-owned.
It is neither exercised by adapter tests nor used by the adapter's public methods.
Retain the no-import inspection contract and library public authority; future cleanup can remove this dead copy after checking intended private compatibility, rather than maintaining two implementations that appear authoritative.
No runtime saving is measured.

#### A-F029 — Medium, static local resolution failure scope + reviewed-test gap

Platform `workflow_artifacts.py:121–131` parses every top-level workflow tools/*.py while resolving a missing registry binding.
An unrelated invalid Python file can raise SyntaxError before a valid requested class is resolved, so a valid graph referencing another file can be blocked by unrelated workspace code.
The known-registry fast path avoids this scan; `test_known_local_source_can_be_opened_to_repair_invalid_python` deliberately uses that fast path and does not cover an unregistered requested class plus an unrelated broken file.
No exact failing run was executed here.
Retain ambiguity refusal and explicit source binding; future action should isolate parsing errors to the requested source/diagnostic scope without silently executing or selecting an ambiguous class.

#### A-F030 — Medium potential impact, cross-owner current-selection race risk

Library `workflow/common.py:271–299` inspects/loads current selection and then unlinks current.json with no expected-record comparison or shared lease visible here.
A publication between inspect and unlink could remove a newer record while returning the previously inspected identity.
`_inspect_current_selection:314–318` also calls load_current().record_id after exists(); concurrent removal may make load_current return None.
Storage internals/admission are B-owned and remain required to establish whether actual public callers permit that interleaving.
No race was reproduced; platform execution lease and normal Clear usage may constrain some callers but do not prove the general public operation atomic.
Nested invalidation tests use serial actual compute/invalidate and distinguish semantic cascade scope, not simultaneous publish/Clear.
B received this seam and will link the same A finding during complete storage/runtime review.
Retain exact selection identity, corrupt-record quarantine and semantic invalidation scope; future authority decision must precede a controlled storage-publication diagnostic.

#### A-F031 — Medium, corroborated raw-class scientific-package classifier omission

Library `custom_sources.py:33–45,51–73` enumerates built-in scientific package prefixes but omits bioimageflow_phasor_tools.
Raw public classes without `_bif_package`/version stamps therefore may be treated as workflow custom classes and embedded as individual source files, unlike the other scientific packages.
Off-owner `test_tool_package_export.py::test_all_tool_packages_are_not_workflow_custom_classes` omits phasor too.
Root batch 3 confirms raw direct-imported phasor classes have no package/version stamps; loader-stamped classes retain the mitigation.
No incorrect export was executed during review.
Retain stable installed-package identity versus true workflow-owned editable sources; root received the exact classifier/test omission handoff.

#### A-F032 — Low/Medium, multi-file source publication failure cleanup gap

Platform `workflow_artifacts.py:418–421` publishes staged files one at a time; a later replacement failure leaves earlier files published.
`WorkflowSourceService.prepare_embedding:100–107` only discards remaining temporary files in finally and does not undo already published files if publication fails.
The parent graph is still unchanged and IDs are fresh, so this is orphan/partially published source storage, not a proven graph/data overwrite.
Source apply separately tracks published paths and unlinks them on failure; store import cleanup still requires its complete later review.
Existing `test_invalid_later_record_leaves_no_staged_source_files` proves prevalidation cleanup, not a mid-publication filesystem failure.
Retain per-file atomic replacement and fresh independent IDs; future action can make the publication transaction's cleanup responsibility explicit and reuse the actual staged-source fixture if a repair is eventually authorized.

#### A-F033 — Medium potential impact, public export containment source risk: package symlink files are followed

Library `custom_sources.py:120–175` iterates package files, stats and reads their contents without rejecting symlinks or proving each resolved file remains inside tools/.
A file symlink under a workflow-local tools package can include outside-file bytes in the portable source bundle.
This is a source-proven containment omission; no sensitive file was read or leakage reproduced in the audit.
Platform OwnedWorkflowSources read/stage explicitly rejects symlinks, so public and platform boundaries differ.
The parent security synthesis should evaluate the intended export package/asset boundary; explicit trusted local authoring does not by itself establish that outside assets are intended portable contents.
Reviewed public source tests contain ordinary files only.
Retain legitimate local package assets and existing per-file export size bound; future action should make external/symlink export policy explicit before testing or changing behavior.


Public loader review confirms A-F023 as a static SyntaxError-to-HTTP mapping defect, rather than a conditional risk; no new execution established this.
A-F001/A-F003 also reach the earlier local-source promotion consumer in workflow_artifacts.py:146–175, which does not first preserve an explicit portable binding.
The two administrative Sphinx failures expose the limited scope of reviewer-F011: the file-existence checker passed while MyST heading-fragment resolution rejected two actual links; source slugs and rendered HTML IDs differ for those em-dash headings.

### Application and declared environment lifecycle — B batch 2

These are held backlog entries, not implementation or diagnostic-test authorization.
P1 marks essential demonstrated contract breaks; P2 marks material source risks; P3 marks narrower test, validation or maintenance candidates.
Existing selectors are source identifiers only; no command was run in this stage.

#### B-F013 — P1 established T1 defects: current manual lifecycle lacks Run admission and canonical target/recipe authority

Main `routers/tools.py:603–633` delegates start/stop/recreate without an execution reservation or mapped ownership/recipe refusals.
Main `services/tool_environments.py:61–104,159–174` inspects and prepares manual start in separate offloads outside the shared guard, authorizes the requested alias rather than the declared spec name, chooses the first matching declaration, and stops the requested alias rather than the actual pool name.
`_environment_spec` at lines 198–207 rebuilds from metadata and drops original declaration flags such as `allow_flexible_versions`; main recreate publishes/stops before public Core validation and main start has no failure-status transition after a failed get-or-create.
These are the previously retained T1 exact reds and source-derived defects, not newly executed audit failures.
Do not reopen their established evidence as untested speculation, or count held WIP as accepted product behavior.

The held versions contain bounded corrections and distinguishing selectors:
`test_environment_lifecycle_is_refused_during_run_admission`, `test_accepted_environment_lifecycle_keeps_run_admission_until_completion`, `test_legacy_alias_cannot_bypass_declared_environment_owner`, `test_unambiguous_stop_alias_addresses_declared_pool_and_status`, `test_ambiguous_package_alias_does_not_select_first_environment`, `test_exact_environment_name_precedes_colliding_tool_alias`, `test_conflicting_declarations_for_one_environment_refuse_mutation`, `test_selected_recreate_preserves_valid_declared_flexible_recipe`, and `test_incompatible_declared_recipe_refuses_before_pool_or_status_mutation`.
Future action after the complete-review gate: review/resume the bounded held packet and public-force wrapper plan with actual generation/failure/retry/isolation evidence.
Retain intentional no-environment no-op behavior, unambiguous alias compatibility, declared lifecycle controls in webapp mode and the distinction from arbitrary source/package mutation.
No universal webapp lifecycle ban or coordinator rewrite is justified.

#### B-F014 — P2 source-risk: startup-refresh close can return before its offloaded physical operation

Both main `tool_environments.py:117–133` and held `tool_environments.py:97–113` cancel the refresh asyncio task and swallow its cancellation while refresh directly awaits `anyio_to_thread.run_sync`.
Raw `Task.cancel()` can unwind that await while the worker continues; the held manual `_run_lifecycle` drain at lines 68–86 addresses exactly this distinction for manual actions, but is not used by startup refresh.
App awaits service close before later teardown (`app.py:746–748`), so the service can appear closed while its worker still prepares/replaces and publishes status through shared objects.
This shutdown path has not received a distinguishing actual-runtime or exact coordinated cancellation reproduction; do not claim physical leakage or pool corruption is observed.

`test_background_refresh_failure_releases_automatic_preparation_guard` exercises an ordinary physical exception and `test_startup_general_refresh_cannot_retire_processing_handoff` coordinates normal preparation, not shutdown cancellation during that worker.
Future action: a bounded startup-close/physical-completion diagnostic after the audit gate; retain asynchronous startup, the shared guard and completion outside the event-loop lock.
Avoid treating AnyIO scope shielding as evidence for raw asyncio cancellation.

#### B-F015 — P2 source-risk/design: lifespan cleanup does not cover early startup failures and can be short-circuited

App `app.py:670–742` performs settings/profile loading, distributed migration/coordinator startup, workflow recovery/registration, catalog initialization and log/watcher setup before reaching the `try: yield` cleanup scope at lines 743–745.
A later startup failure therefore cannot execute that scope's cleanup for resources already constructed or started.
Inside teardown, service/coordinator/token/Napari-service close at lines 746–754 and settings/profile flush at lines 797–800 are unguarded; one failure can skip later viewer/thumbnail/editor/watcher/log/PyPI cleanup.
The viewer/thumbnail/editor sections already isolate ordinary exceptions, showing a useful local pattern; cleanup needs ownership-aware completeness rather than swallowing all errors indiscriminately.
No failed-startup leak or teardown fault was executed in this audit.

`test_lifespan_refreshes_catalog_on_startup`, `test_lifespan_swallows_network_error_from_refresh`, and `test_lifespan_starts_and_stops_hot_reload_service` cover normal life and the intentionally handled catalog exception, not another startup failure after coordinator start or an early close failure.
Future action: distinguish entered ownership stages and failure-safe cleanup/aggregate reporting with exact injected startup/close tests.
Do not globally close the borrowed process manager without reviewing pool/application ownership.

#### B-F016 — P2 source-risk/design: package-scoped environment status collapses distinct declared targets

Main `tool_environments.py:223–229` and held lines 252–258 write one `PackageInfo.environment_status` per selected tool's package and update the catalog at that package granularity.
`models/tools.py:102–121` models one status despite a package potentially containing tools declaring multiple environments.
Stopping or failing the selected target can therefore overwrite the package status representing an unrelated target that remains running.
This source-level status-authority collapse is established; its precise frontend presentation is still a cross-owner pending trace.

The held real integration test registers SelectedEnvironmentNumbers and OtherEnvironmentNumbers under `same-package`, but its isolation check compares managed inventory and unmanaged manifest digest, not distinct UI environment status.
The exact-name precedence unit case uses different packages, so it does not distinguish this shared-package status case.
Future action: reconcile declared-target status authority/read-model granularity and retain actual selected/unrelated inventory isolation; avoid duplicating lifecycle execution just to test status mapping.
No filesystem or worker mutation of the unrelated environment is alleged from this status finding.

#### B-F017 — P2 source-risk/persistence: profile loading discards every unknown schema version

`services/execution_profiles.py:131–136` rewrites the store to an empty v2 envelope whenever `profiles_version != 2`, although its comment and `test_v1_profiles_are_dropped_without_archive` justify discarding obsolete v1 specifically.
Missing, malformed or future version values take the same destructive branch and can lose stored profiles on application startup.
The branch is source-demonstrated; no future-format file or data loss was executed here.
Future action: distinguish the explicitly authorized v1 discard from unknown/malformed versions and preserve unsupported data on refusal.
Retain the intentional no-archive v1 policy rather than inventing a migration requirement for obsolete contracts.

#### B-F018 — P3 design/debt: profile update executes trusted configuration before target/CAS refusal

`execution_profiles.py:179` offloads trusted script loading/evaluation before acquiring the lock, finding the target and checking expected revision at lines 180–187.
A nonexistent/stale update can execute the script and perform expensive or scripted side effects before returning its predictable profile refusal.
The scripts are intentionally trusted code; this is not a claim of a webapp edit bypass or a new sandbox requirement.
The CRUD/CAS tests assert persisted revision state, not whether refused updates evaluate the script.
Future action: consider a cheap initial target/CAS precheck followed by authoritative recheck after loading, with an evaluation-count oracle if the contract merits it.
Retain exact content capture/digest validation and no reflection of script credential-bearing exception text.

#### B-F019 — P3 source-risk: profile-load rejection can leave a partially accepted in-memory catalog

`execution_profiles.py:137–140` assigns the id-indexed `_profiles` before detecting duplicate persisted IDs.
After raising, an existing store object's `list/get` can expose the last duplicate value instead of retaining its previous validated catalog or remaining explicitly unloaded.
Normal app startup stops on this error, so request exposure through default startup is not demonstrated.
There is no duplicate-ID load-failure state oracle in the complete profile-store tests.
Future action: validate into a local complete candidate before publication; distinguish initial/repeated load failure while retaining atomic writes and revision CAS.

#### B-F020 — P3 performance/design candidate: async tool listing synchronously repeats full managed-root scans

`routers/tools.py:240–258` calls `service.location` synchronously for each declared tool environment.
`tool_environments.py:176–195` calls public `managed_environments()` each time; duplicate tool declarations sharing a target repeat the same filesystem-wide discovery and the async route performs these scans on the event loop.
Large catalogs or slow storage can block unrelated API/WS progress and multiply discovery work.
No performance regression, blocking duration or suite speedup has been measured.
`test_get_tools_includes_managed_environment_location` checks one fake location and original metadata immutability, not discovery cardinality or event-loop work.
Future action: request-local managed snapshot/location mapping and offload if measurements justify it; preserve public discovery, managed ownership and original recipe metadata nonmutation.
Do not introduce a long-lived second environment authority/cache without reviewing invalidation.

#### B-F021 — P3 test/artifact debt: real lifecycle evidence is written only after all assertions succeed

Held `test_tool_environment_lifecycle.py:74–80` writes the combined generation/fault/recovery/worker evidence only at the successful end.
An earlier failed assertion, such as the retained matching-generation red, prevents this automatic artifact from being produced even though meaningful real phases already occurred.
The parent retained the actual T1 red through separate manual artifacts; those are valid, but the test does not itself guarantee first-failure phase preservation.
Future action: retain stage snapshots/failure context before cleanup using the existing fixture and one genuine runtime journey, not duplicate runs or simulated provisioning pass claims.
The selected-generation/PID/recipe and exact worker values/report content assertions are useful and must be retained.
Fault injection remains the explicit one armed real Pixi install exit 77, not an invented external-provision success.

#### B-F022 — P3 test gap: profile policy test does not distinguish the independent editable guard

`test_routers/test_execution_profiles.py::test_webapp_profile_mutations_are_forbidden` supplies both webapp settings and `editable=False`.
It passes even if either side of `_mutable` is accidentally removed; the source has the two guards, and the default process-mode store flag currently prevents ROOT-F002 from becoming a default webapp profile edit bypass.
Future action: extend this existing parameterization for the independent guard combinations and read-model editable result; preserve administrator-managed profiles and trusted explicit describe semantics.
No additional remote lifecycle execution is necessary to distinguish this local policy oracle.

#### B-F023 — P3 false-confidence test: Fiji identity-required test fails on a different missing field

`test_routers/test_fiji_router.py::test_open_requires_complete_result_identity` at lines 145–150 sends node_id and row but omits the required `col` field as well as result_identity.
Its 422 assertion therefore succeeds in model validation even if the route's explicit immutable-result identity requirement at `routers/fiji.py:57–61` is removed.
Other cases use a valid complete identity; they do not repair this missing negative distinction.
Future action: send all non-identity required fields and assert the identity refusal/launcher non-call, preserving real pinned-result resolution as separate result-store integration coverage.
Do not count the mock selected-cell test as whole image/session immutability certification.


### Public graph materialization and interfaces — A batch 4

#### A-F034 — Medium, static public endpoint-validation/roundtrip risk + oracle gap

`workflow/materialization.py:250–301` validates edge variants/field combinations, unique edge IDs and node membership, but does not validate endpoint value types/nonempty IDs, nonnegative positional indices or uniqueness of incoming destinations.
`kwargs`/`positional` at lines364–396 use target keys as dictionaries, so two different edge IDs targeting the same endpoint silently overwrite the earlier source while both contribute topological dependencies.
A negative positional index can fall outside the later `range(max(positional)+1)` at lines483–486, so the accepted record's edge can disappear from actual args and reserialization.
Platform GraphState is a stronger typed structural boundary, but public from_dict is also an authoritative entry for direct callers/archives and should not silently discard accepted wire edges.
No constructed edge execution was run here; full Node binding review may constrain individual constructions but cannot restore an edge already overwritten in these dictionaries.
`test_recursive_parser_rejects_unknown_variants_and_fields` covers variant/extra-field errors; `test_recursive_graph_round_trip_is_canonical` uses a well-formed single-endpoint graph.
Retain symbolic fanout to distinct endpoints, stable edge IDs and partial missing-node diagnostic continuation; future action should define/reject competing endpoint ownership and malformed positions at the public boundary, not infer schema coverage from field-set checks.

#### A-F035 — Medium, static public resource-applicability defect: DataFrame overrides silently ignored

`materialization.py:487–527` applies resource_overrides only in the non-DataFrame branch.
The DataFrame branch accepts a node record carrying resource_overrides because that field is allowed at lines213–228, then neither validates nor assigns it.
The resulting workflow can lose the override in reserialization rather than refusing a Processing-only setting.
Platform translator's explicit DataFrame refusal is a different boundary and can itself use the wrong same-name class (A-F002).
No resource override test was run here; existing clean API/unified tests in this batch contain no DataFrame override payload.
Complete public resources/test review is pending to confirm all surrounding selectors/contract wording.
Retain Processing class declaration floors through actual Node setter and conservative engine classification; future action should make public invalid applicability a structured rejection using the actual resolved class.

#### A-F036 — Medium, static exception-state mutation defect: rejected expose_input leaves a new port

`interfaces.py:134–170` registers a new public input through self.input before `_bind_input_target` checks active ownership, conflicting internal edges and competing published targets.
If that later check raises, the newly inserted `_interface_inputs` entry remains, with no rollback.
The caller receives a refusal but the workflow definition/interface has changed; an unused required port can then alter validation/invocation semantics.
No rejected exposure was executed; source order and mutation directly establish the exception-state discrepancy.
`test_exposed_input_preserves_local_constant_as_fallback` verifies a valid exposure, not invalid exposure preserving the previous graph.
Retain unique interface names/IDs and explicit internal-edge conflict refusal; future action should preflight or transactionally commit port+target ownership, without deleting a previously existing legitimate input on error.

#### A-F037 — Medium, static workflow context reentry defect + test-oracle gap

`interfaces.py:454–463` stores the previous active workflow in one mutable `self._prev_workflow` slot.
Entering the same object twice sets that slot to self on the inner entry; both exits then restore self, leaving the object active after the outer exit.
There is neither reentry rejection nor a per-entry token/stack.
Normal distinct workflow nesting and exception propagation remain correct; context-local storage in Node is not disproved.
`test_active_workflow_is_context_local_across_threads` creates a separate Workflow in each thread, so cannot distinguish same-object reentry or the shared previous-slot authority.
No reentry test was executed here.
Retain context-local construction and outer workflow restoration; future action must choose supported nested reuse versus explicit refusal before mutating active state, with a narrow same-object scope oracle.

#### A-F038 — Low/Medium, qualified target-membership ownership risk

`interfaces.py:515–539` resolves named nodes from self, but returns a passed Node reference without proving membership/identity.
`enable`/`disable` then mutate that object even when it belongs to a different workflow.
Actual compute/selection callers may intentionally accept reference targets; complete Node/WorkflowNode/runtime review is required before deciding the full API policy.
This is not evidence of unintended platform cross-canvas mutation or a permission bypass.
Reviewed tests use own named/reference targets; context/reference ownership tests do not exercise this selector branch with a foreign node.
Retain caller-friendly own Node references and copied public mapping; future action should document/enforce one consistent membership policy rather than silently selecting an unrelated owner.

#### A-F039 — Low/Medium, pending fallback fanout authority risk

`common.py:98–126` reports a public input fallback if **any** target has one, while `interfaces.py:342–376` independently applies a supplied value to every target.
If one field target has a constant/default and another remains required, that global fallback result may conceal a missing required input at a different target.
Complete WorkflowNode/root input validation and IOModel default handling remain pending, so no admitted bad execution is claimed.
The public unified fallback test has one target, while dataframe fanout has no mixed field-default scenario.
B received this seam to reconcile invocation/runtime required-input authority.
Retain local constant fallbacks and explicit root input override semantics; future diagnostic must distinguish per-target defaults from an actual shared boundary default.


### Scientific adapters and test oracles — root batch 3

#### ROOT-F031 — P1 scientific correctness, static defect plus harmonic-specific oracle gap

`packages/bioimageflow-phasor-tools/bioimageflow_phasor_tools/phasor.py:180–197` obtains matching frequency and harmonic but calls phasor_calibrate without the harmonic.
Conversion accepts any positive requested harmonic and writes it into the exchange file, so higher-harmonic coordinates can reach this branch with their correct metadata.
The [official PhasorPy 0.12 lifetime API](https://www.phasorpy.org/docs/stable/api/lifetime/#phasorpy.lifetime.phasor_calibrate) defines an explicit harmonic parameter whose default is the first harmonic.
Consequently the reference lifetime is interpreted at the fundamental frequency even when the accepted coordinates are at a higher harmonic, changing calibration values while the output retains the higher-harmonic label.
This is source/API corroboration; no numerical failure was executed.
`test_calibration_accepts_different_reference_shape_and_selects_center_method` checks reference shape/method using harmonic 1 and ignores the frequency/harmonic arguments; the real PhasorPy roundtrip also uses harmonic 1.
After full review, preserve fundamental frequency, matching sample/reference acquisition and selectable harmonics; pass the actual harmonic through the authoritative upstream contract and distinguish a known higher-harmonic reference, without another whole-platform journey.

#### ROOT-F032 — P1 scientific correctness, static defect plus lifetime oracle gap

`phasor.py:310–317` discards the stored harmonic and passes only the fundamental frequency to phasor_to_apparent_lifetime.
The [official PhasorPy 0.12 conversion contract](https://www.phasorpy.org/docs/stable/api/lifetime/#phasorpy.lifetime.phasor_to_apparent_lifetime) computes lifetime using angular frequency 2πf and has no separate harmonic argument.
For unmodified calibrated coordinates at harmonic h, using f rather than hf scales the inferred lifetime by h; any preceding erroneous calibration is a separate ROOT-F031 distortion.
This is a source/mathematical inference, not an observed numerical run.
The adapter's fixed mocked lifetime and real first-harmonic roundtrip cannot detect it; modulation output bytes are also not asserted in that runtime test.
Retain float32/NaN policy, correct physical units and fundamental acquisition metadata; future action must use the effective harmonic frequency and a known nonfirst-harmonic numerical oracle.
Do not compensate by rewriting acquisition metadata to disguise the requested harmonic.

#### ROOT-F033 — P3 validation defect, separator-only statistics escape the nonempty guard

Measurement `table_tools.py:374–384` rejects an empty/blank stats string before splitting, but a nonblank separator-only string such as `","` becomes an empty requested list and passes all remaining checks.
AggregatePerImage schema/runtime callers therefore accept no actual statistic despite the helper's explicit “at least one aggregation” contract; the schema can still publish object_count only.
No pandas empty-aggregation behavior or failure was executed and no lost scientific rows are alleged.
`test_table_tools_validate_selection_and_output_collisions` covers empty string and repeated mean, not an empty token set; the exact schema/runtime test covers valid requested stats only.
Future action is a post-tokenization nonempty check at the existing shared helper and a narrow malformed-token oracle, retaining case normalization, supported aggregations and duplicate refusal.

#### ROOT-F034 — P3 test organization candidate, broad synthetic case obscures independent tool failures

`tests/test_measurements.py::test_measurement_tools_schema_and_synthetic_execution` performs schema checks and actual scientific/table assertions for ten tools in one long case.
An early failed schema or region assertion prevents later independent matching/table/normalization assertions from running and gives those tools no independent selector.
Later focused tests distinguish meaningful label/threshold/collision/index contracts, so these are not simply redundant tests to delete.
After the hold, consider parameterizing the independent tool/oracle cases or splitting them with the same small synthetic fixtures, preserving every exact scientific assertion.
The coherent public workflow/worker boundary remains a separate integration obligation; no extra complete journey is proposed.
No timing saving has been measured and this review does not claim suite-wide optimization.


Root batch 3 fully corroborates raw phasor classification A-F031: direct imported classes and their Core bases have no package/version stamps; loaded/stamped classes retain the mitigation.
A full command-facade/registry review resolves ROOT-F024: parameterless useCanvasCommands returns a shared facade whose updateParameter/addToolNode methods choose the active command resource at invocation, so the original dataset resolution awaits do not bind the later mutation to its original canvas.
Root scientific review also corroborates reviewer-F003 for the CAREamics configured-checkpoint test: ordinary collection skips its model_runtime marker, while the complete model-runtime selector requires a complete marker that this test lacks; no test was executed.

### Release and package contracts — shared reviewer batch 2

#### reviewer-F012 — P2, source contract risk: compatible published dependency versions are reduced to one latest version

`scripts/release_support.py:198–215` exposes only PyPI JSON's `info.version`; `scripts/release_set.py:122–147` requires an unselected first-party dependency to accept that single returned version.
`reference/releasing.md:31–38,127–129,197–198` preserves accurate lower/upper ranges and says a dependency needs a compatible published version.
Consequently, when a dependency has advanced beyond an unchanged package's upper bound, the tool can refuse its independent release even if an older compatible version remains published.
That is a source-derived scenario, not an observation about any current PyPI project: no registry was queried.
`test_release_tagging.py::test_unselected_workspace_dependency_must_be_available` covers a latest version below the floor and an accepted latest version; it does not distinguish a latest version above the upper bound with another compatible published version.
After the complete audit, clarify availability policy and resolve against actual compatible published candidates if the existing independent-release contract is retained.
Do not automatically broaden upper bounds, raise unrelated package versions, or infer API compatibility from metadata alone.
Optional/conditional first-party dependency handling is also a future boundary of these helpers: they currently inspect only `project.dependencies` and do not interpret requirement markers; none of the eleven present manifests has a conditional/optional first-party edge, so no current marker-induced failure is claimed.

#### reviewer-F013 — P2, source failure-path risk: later invalid artifacts are checked after an earlier upload

`scripts/release_set.py:530–552` validates one package's artifact pair, publishes it, then validates the next pair.
A malformed/missing later artifact pair can therefore stop the public CLI after an earlier package has already been uploaded, despite all artifact directories being locally available before publication starts.
Current GitHub CI mitigates this path: every selected build validates its pair before the publish job starts, and its staging shell checks expected names/counts (`release.yml:112–126,161–189`).
The public CLI's exposed preflight remains weaker; the finding is not a claim that normal CI has published a bad pair.
`test_release_tooling.py::test_release_set_publishes_validated_artifacts_in_dependency_order` supplies two valid pairs and checks order; it does not assert zero publisher calls when the later pair is invalid.
After review, consider validating every selected pair before the first irreversible upload, retaining those exact paths for publication.
Preserve dependency order, exact artifact identity, trusted publishing and explicit retry; PyPI publication cannot be promised atomic rollback.
The one-time bootstrap helper deliberately builds/uploads sequentially (`publish_packages.py:167–217`); its documented partial-publication/retry behavior is explicit, so do not silently redefine that separate bootstrap contract.

#### reviewer-F014 — P3, source defect: excluding every bootstrap package crashes plan formatting

`scripts/publish_packages.py:71–83` permits exclusions yielding an empty selection; `build_publish_plan` returns an empty list and `publish_batch` explicitly accepts no work.
But `_print_plan:233–235` calls `max(header_length, *row_lengths)` with no row arguments, reducing it to `max(int)` and raising `TypeError` before the intended no-work/plan completion path.
This is a source-level reasoning result; it was not executed.
The complete `tests/unit/test_publish_packages.py` covers mixed/unknown filters and token/clean-tree behavior, but not an all-excluded CLI plan.
After the audit, make empty selection either an explicit clear refusal or a valid empty plan/no-op according to the retained CLI contract, using the existing formatter/filter tests.
Preserve fail-closed version checks and token-free build subprocesses.

#### reviewer-F015 — P3, cost/clarity candidate: the CI metadata step already performs an artifact build

Library CI runs `test_package_artifacts.py` at lines 218–219 without a prebuilt directory.
Its session fixture builds all packages (`test_package_artifacts.py:97–120`); CI then explicitly builds all packages with `--no-sources` and reruns the same artifact file against `dist/packages` (`ci.yml:220–225`).
Thus the first step is not merely a metadata-only check, as the workflow label suggests.
The build postures differ: the fixture fallback uses workspace defaults; the authoritative explicit build disables workspace sources.
This refines batch 1's general retain-pre/post-boundaries note: retain both builds only if that posture distinction has a required distinguishing contract.
Otherwise keep source-manifest checks and one authoritative release-posture build with all current artifact/import oracles.
No build was run, no savings were measured, and no test names should be deleted solely because they repeat.

#### reviewer-F016 — P3, bounded efficiency/reliability candidate: tagged subset preflight queries unrelated packages

`scripts/release_set.py:575–583` queries every discovered workspace package for `plan/publish/verify --check-pypi`, even when tags select one independent subset.
Any unrelated package's query error aborts the selected operation (`fetch_package_versions:282–286`).
The same module already narrows explicit `tag` queries to its recursive required workspace dependency closure (`_version_query_packages:379–411`; `tag_release_set:429–435`), and `test_explicit_selection_queries_only_its_dependency_closure` distinguishes that behavior.
After review, consider reusing the required closure for explicitly tagged subsets while retaining all-package queries for automatic whole-workspace discovery.
Do not remove required dependency availability checks or the second validation after network input; the latter protects against local state changes across the query boundary.

#### reviewer-F017 — P3, verification failure-path/scope candidate: the wait loop compares latest metadata and aborts on transient query faults

`scripts/release_set.py:556–572` compares the single returned PyPI version with each requested version and retries only a nonmatching return value.
A query exception aborts immediately rather than using the stated bounded visibility wait; a later latest version can also prevent this loop from recognizing the requested published version.
The completely read matching release tests do not directly exercise this loop's transient-error or exact-version-presence outcomes.
No registry response or failure was observed here.
When this boundary is repaired, distinguish requested-version visibility from latest-version equality, retain explicit bounded retry/deadline behavior, and report publication separately from later verification failure.
The CLI accepts arbitrary integer `--attempts` and float `--interval` (`590–599`); negative interval reaches `time.sleep` and zero/negative attempts perform no queries, so validation of that configuration is an adjacent small robustness candidate.
Do not let additional retries exceed the workflow's overall time budget or automatically republish artifacts because a visibility probe failed.

#### reviewer-F018 — P4, version-policy/maintenance candidate: duplicated three-part validation has an epoch ambiguity

`release_support.py:93–115` and `publish_packages.py:46–62` separately implement stable three-part version validation.
They reject prerelease/development/postrelease/local or noncanonical forms, but do not reject a nonzero PEP 440 epoch: release tuple length and canonical public spelling alone still permit an epoch-bearing stable version.
Their help/policy describes plain `<major>.<minor>.<patch>` and all current manifests use plain triples.
No current release uses an epoch and no failure was executed; treat this as a policy clarification/maintenance candidate, not an urgent publication defect.
If plain triples are the intended exact contract, reuse one validation authority and add that distinction to the existing invalid-version cases; otherwise document the deliberately accepted epoch form.
Retain all currently intended stable-version and exact-tag checks rather than narrowing legitimate version syntax accidentally.

#### reviewer-F019 — P3, artifact-oracle scope candidate: prebuilt pairs are not compared to current manifest identity/version

`test_package_artifacts.py:86–94,123–143` selects prebuilt files by package-name glob and reads metadata for dependency/extras assertions, but the file has no assertion that each artifact's metadata name/version equals its current source manifest.
A sole stale-version pair can satisfy the prebuilt tests' filename shape and content/dependency checks.
The clean CI build path is a mitigation, and the release helper separately checks exact identity/version before publication (`release_support.py:239–251`); no stale current CI output is claimed.
If extending this artifact boundary after the audit, reuse manifest identity and the existing artifact metadata reader/validation helper for that missing distinguishing outcome rather than adding another build.
The wheel import oracle correctly uses a separate process and verifies import origins; it specifically blocks Parsl/PSI/J imports, while using the current development environment for ordinary declared dependencies.
It does not certify every allowed historical dependency version or a dependency-free fresh installation.

#### reviewer-F020 — P3, validation guidance/cost inconsistency: release fixes always demand rerunning full

Platform `docs/developer/releases.md:46–47` says that any validation fix must be committed and followed by the full lane again.
Current AGENTS and `docs/testing.md:143–148` instead retain successful unchanged phases and rerun the exact failure plus invalidated checks with explicit composite revision/input evidence.
After the hold, reconcile this release guidance with that proportionate rule while preserving complete required release evidence for the final relevant inputs.
Do not replace release certification with quick/scoped results, waive manual release evidence, or hide original failed/unrun phases.
The application archive still needs its signed manifest and matching static version, and rebuilt launchers still need their independent operating-system signing/startup checks.


Shared batch 2 completes the release workflow/helpers and previously context-only infrastructure tests; reviewer-F004 also reaches stale installation.rst/reference tool-package claims about automatic tags and repeated validation, while current releasing.md correctly describes manual coordinated dispatch and retained exact-commit evidence.

### Complete-review checkpoint — A-batch-5

#### A-F040 — Medium, static nested fallback roundtrip defect + oracle gap

`interfaces.py:134–170,286–316` permits exposing a WorkflowNode child input; `common.py:117–124` deliberately resolves recursive child fallbacks.
`WorkflowNode.bind_port:195–225` maintains nested constants in `_input_constant_bindings`, whereas expose_input updates the separate `_workflow_input_bindings` bookkeeping.
Serializer `serialization.py:88–93` always emits nested constant bindings.
Materializer `materialization.py:430–443` rejects a constant binding whenever kwargs already contains that child port, including a symbolic WorkflowInputRef from the enclosing exposed interface, with the error "both an edge and a constant binding".
A nested local fallback exposed by its parent can therefore serialize a definition that its public loader refuses, unlike the explicitly supported plain tool-field fallback.
No new roundtrip was executed here; the source mismatch concerns the permitted WorkflowNode/exposure branch.
`test_exposed_input_preserves_local_constant_as_fallback` covers a plain ValueTable target, not a child workflow port.
Retain local fallback semantics and real edge-versus-constant exclusion; future action should distinguish a symbolic boundary fallback from a competing data edge consistently across nested serialization/loading.

#### A-F041 — Medium/High, static rejected-invocation mutation defect: parent targets published before final admission

`workflow_node.py:115–134` preflights prohibited column bindings, then applies every binding before checking missing required inputs and before parent registration.
A symbolic binding publishes an enclosing target at lines199–206 through parent `_bind_input_target`.
If a later required child input is missing or a later dataframe binding is invalid, the constructor raises while that parent interface target remains, pointing to an invocation that never registered.
This extends A-F036's exception-state problem to a separate constructor with an explicit partial preflight comment; the preflight does not cover every remaining refusal.
No failed construction was executed here.
Unified callable tests provide all required bindings or defaults; nested storage tests likewise use valid invocations.
Retain early source-tool column rejection, own symbolic references and unique parent names; future action should admit all bindings/required inputs transactionally before publishing parent targets.

#### A-F042 — Medium, static binding bookkeeping risk: rebind retains old competing representation

`workflow_node.py:209–235` inserts a new column or constant/dataframe binding without removing the old representation for that port or old upstream dependency.
The underlying definition `_apply_interface_binding` does switch a plain field target between column and constant, but the invocation's `_input_column_bindings`/`_input_constant_bindings` can continue to contain both.
Serializer emits both old edge and new constant, which materializer explicitly refuses; old upstream dependencies may also continue to schedule despite actual internal binding replacement.
Existing tests construct once; no reviewed test rebinds the same stable child port column→constant or constant→column and checks roundtrip/dependency semantics.
Runtime public root-binding use may constrain which transitions happen automatically; B is reviewing that authority.
No changed execution output was reproduced.
Retain stable child port identity and binding preflight; future action must update all binding/dependency representations as one operation, with narrow public rebind/serialization oracles.

#### A-F043 — Medium potential impact, source lifetime risk: stale fixed dispose removes a remounted session

`useCanvasCommands.ts:208` fixed API dispose unregisters by canvasId only.
A previously disposed wrapper retains this method; unregister/remount with the same ID obtains a new token, but calling old dispose again removes that new session/resources.
Registry token support exists but is not checked at this disposal boundary.
Normal callbacks on the old resource throw after disposal, so those callbacks do not retarget the remount.
`canvasSessionRegistry.test.ts` checks token change and repeated unregister only before remount; command disposed-call tests do not dispose an old API after remount.
No actual UI lifecycle interleaving was executed, so the production occurrence remains a caller-lifetime risk.
Retain exact canvas ownership and registration token distinction; future consumer review should prove whether stale disposal can occur before introducing a token-bound unregister guard.

#### A-F044 — Low/Medium, optional fallback defect: bulk parameter fallback short-circuits

`useCanvasCommands.ts:294–299` falls back to Object.entries(values).every(updateParameter).
An unchanged/refused false return stops later entries, so it can skip valid subsequent updates or leave a partial update while returning false.
Neighboring enabled-state fallback intentionally attempts all nodes and aggregates changes, with an exact test asserting true/false/true.
`routes an atomic parameter update to the active canvas` supplies the custom bulk callback and never exercises this fallback.
Production CanvasView supplies updateNodeParameters, so this defect is bounded to the optional fallback API and is not claimed as the current dataset update's product failure.
Retain production atomic bulk callback; future action should define fallback change versus success semantics and either make it consistent or remove unsupported pseudo-atomic fallback.

#### A-F045 — Low/Medium, cleanup fault isolation risk

`canvasSessionRegistry.ts:144–159,174–178` removes registrations and clears resource maps before iterating dispose calls without catching errors.
A throwing disposer stops cleanup of later resources/canvases, with no remaining registry handle to retry them.
Current full resource implementations still need complete review to assess real throw paths, so this is a source failure-path risk, not an observed leaked subscription/timer.
Registry tests use nonthrowing spies only.
Retain unique-resource disposal and immediate registry/activation removal; future action should define best-effort cleanup/error aggregation so one faulty resource does not abandon unrelated ownership.

#### A-F046 — Low, setup failure mutation risk

`useCanvasCommands.ts:144–147` registers a nested session before refusing a missing required Save callback.
A rejected setup can leave a registry entry/count with no commands resource.
No production missing-Save call is claimed; CanvasView's nested branch supplies it.
Existing facade tests do not inspect registry state after this setup error.
Retain required nested Save and valid registration idempotence; future action can preflight options before registration or explicitly undo only the newly created registration.


### Complete-review checkpoint — root-batch-4

#### ROOT-F035 — P2 scientific layout source defect plus writer-specific oracle gap

`bioimageflow_io_tools/_raster.py:52–64,67–70` validates explicit output axes but sets TIFF photometric=minisblack only when its shape heuristic says grayscale.
For a declared ZYX/CYX/TYX three-dimensional grayscale array whose X size is 3 or 4, the heuristic instead returns false; no photometric is supplied, allowing the underlying TIFF writer's RGB(A) inference to override the declared absence of S.
Both write_ome_tiff (`writers.py:193–199`) and BioIO's ordinary TIFF branch (`bioio_convert.py:121–126`) explicitly prevent exactly this inference, confirming a divergent shared-writer policy.
No incorrect TIFF was newly produced; this is source corroboration and its underlying writer-default behavior remains a future exact reproduction boundary.
The existing narrow-volume test uses ConvertToOmeTiff, while the ordinary writer's exact RGB test covers axes ending S; selection tests use X widths 5/6 and miss this grayscale shape.
After full review, preserve real RGB(A) S axes and ordinary grayscale stacks; make explicit axes authoritative in the lightweight TIFF branch and extend the existing narrow-volume/ordinary-writer oracle without another full workflow journey.

#### ROOT-F036 — P2 metadata fidelity defect: physical pixel units are discarded

`bioimageflow_io_tools/metadata.py:174–185` parses raw PhysicalSizeX/Y/Z numeric attributes but ignores their respective PhysicalSize*Unit attributes; ImageMetadata and ReadImageMetadata.Outputs expose only unlabeled float values.
The [official OME 2016-06 Pixels schema](https://www.openmicroscopy.org/Schemas/Documentation/Generated/OME-2016-06/ome_xsd.html) binds physical sizes to per-axis units, with micrometers as the default.
Two equivalent physical lengths written in nm and µm can therefore produce different unlabeled results, and downstream callers cannot recover a nondefault unit from this response.
This is source/schema reasoning, not a newly executed image or measured scientific error.
`test_read_image_metadata_reports_ome_tiff_pixel_sizes` writes only sizes with default units; it cannot distinguish either normalized-unit correctness or explicit-unit preservation.
Future action after the gate: choose/document a canonical returned unit or preserve per-axis unit identity through the public model and callers, with one nondefault-unit variant in the existing metadata test.
Retain header-only inspection, unknown values, and distinct X/Y/Z rather than silently assuming every source uses the default unit.

#### ROOT-F037 — P3 external-compatibility evidence gap: actual BioIO writers are substituted by permissive mocks

`test_image_io.py::test_bioio_convert_image_uses_bioio_plugins_and_selection` and `::test_convert_to_ome_zarr_uses_writer_and_reopens_output` replace BioImage and writer classes with local fakes, including constructors accepting arbitrary keyword arguments.
They distinguish adapter selection/delegation and desired shape/dtype checks, but cannot establish the pinned BioIO/plugin recipe creates a readable real artifact, exports the expected API, or preserves actual pixel values.
A whole-repository search of package tests, integration/unit tests and scripts found no other actual BioIO/OME-Zarr writer invocation in test coverage; no executed historical compatibility result is inferred solely from this search.
The upstream public writer documentation supports the chosen single-shape constructor posture, but does not substitute for installed pinned-version acceptance.
After the complete audit, reconcile this obligation with existing package-loading/external-compatibility milestone evidence first; if absent, use one small actual pinned-worker writer/reopen/exact-array case there.
Retain fast mocked adapter tests during local development and execute real dependency compatibility only at the relevant milestone or recipe change, rather than installing/running all BioIO plugins for each localized edit.
The general conversion functions currently preserve axes/pixels but do not carry source physical sizes/channel names into the output writers; whether full microscopy metadata preservation is essential is a qualified product/specification decision, not a newly proved violation of the existing axis-focused contract.


### Complete-review checkpoint — B-batch-3

#### B-F024 — P1 source risk: asyncio Run-task cancellation releases admission before physical completion and reports success

`backend/src/bioimageflow_server/services/execution.py:775–781,1331–1345,1491–1512` stores an asyncio task wrapping `asyncio.to_thread(_run_sync)`.
The done callback catches `asyncio.CancelledError`, sets `exc=None`, publishes succeeded/completion, and releases `_workflow`, `_active_graph`, `_run_task` and `state` without a separate physical-completion holder.
Cancellation of this task can cancel its awaiter without stopping the already-running thread; `_run_sync` can continue compute, latest-output materialization and export after the callback has admitted a later operation.
This is a source risk, not an executed race or a claim that the public Stop route directly cancels this task: `stop()` correctly requests `workflow.cancel()`, and `TestExecutionManagerStop::test_stop_cancels_running_workflow` covers that distinct cooperative path.
The exceptional branch is explicitly `pragma: no cover`; the complete manager/router test files contain no distinguishing raw-task cancellation oracle.
Future diagnostic should coordinate a physically blocked computation, cancel the stored task, and assert actual completion/admission/status rather than elapsed sleep.
Retain cooperative cancellation, selected-run scope, cached-node outcomes, external manager ownership and one accepted execution identity; do not globally close borrowed managers.
Coordinate with A's physical-worker/admission seam in draft/Clear offloads; this finding does not establish that their worker commits corrupt storage because workflow mutation locking can supply additional ordering.

#### B-F025 — P2 source defect: some managed-export failures become compute failures instead of unavailable exports

`services/execution.py:798–830` computes the destination and looks up the run context before its export `try`, and calculates `_archive_digest(archive)` in the `else` outside that catch.
A raising configured destination provider or archive-digest read error escapes `_export_managed_result` into the compute task, so the completion callback marks an otherwise completed computation failed.
The same method deliberately records export/retention failures as unavailable exports while preserving computation success when they occur inside its guarded branches.
No failure was injected in this audit; execution-runtime counterpart inspection is still incomplete.
Existing selector `backend/tests/test_services/test_execution_runtime.py::test_attached_export_failure_preserves_success_and_disables_download` was located and must be inspected fully in the next batch before coverage credit; it appears to exercise the exporter, not destination resolution.
Future action is a bounded diagnostic for destination-provider and digest failures and a consistently bounded export-only failure boundary, retaining independent compute status and download availability.

#### B-F026 — P2 source risk: legacy fallback recaptures latest and can bypass modern provenance validation after pointer advance

`services/result_store.py:36–48,51–108,251–280` first captures latest modern identity; when capture returns `None` for a legacy view, it resolves latest again and loads that second record using raw `cache_load`.
If latest advances from a valid legacy view to a modern view between those reads, the second record can be loaded without `read_run_node_result`/record-integrity validation and without captured identity attributes.
The static modern-corruption tests prove fail-closed behavior for a fixed modern selection, not that legacy-to-modern pointer advance preserves it.
No concurrent reproduction or exact-viewer bypass is claimed: modern identities use the public validated library path, and legacy results do not authorize exact viewer opening.
`test_modern_corrupt_record_never_falls_back_to_raw_or_historical_rows`, `test_present_malformed_modern_provenance_is_not_legacy` and `test_get_latest_dataframe_falls_back_to_legacy_latest_link` are the existing differentiating coverage to extend after the review gate.
Future action should retain one captured selection through legacy/modern discrimination rather than remove legacy compatibility.
The `identity is not None` condition at line47 is unreachable in this fallback; cleanup belongs to the same bounded change, not a second test journey.

#### B-F027 — P3 source defect: malformed result.json fallback shape escapes the declared not-ready error

`services/result_store.py:270–279` reads fallback metadata then calls `payload.get` without checking it is a mapping.
When a selected node view has no record link and its fallback JSON is an array/scalar, `get_csv_path`/`has_data` can raise `AttributeError` instead of a controlled not-ready response.
The primary modern `capture_latest_result_identity` path checks mapping shape and remains fail closed.
Existing malformed-provenance tests exercise the primary dataframe path; no complete negative fallback-shape oracle occurs in `test_result_store.py`.
Future diagnostic should construct this exact no-record-link fallback case, retaining canonical path confinement and malformed-link refusal.
Do not broaden this to a promise that every I/O exception from `has_data` must be hidden.

#### B-F028 — P3 test defect: router invalid-workflow-identity cases also omit required revision

`backend/tests/test_routers/test_execution_router.py::test_run_rejects_invalid_workflow_identity` and `::test_clear_rejects_invalid_workflow_identity` omit `draft_revision` for every parameterized invalid identity.
They still return 422 if workflow-id validation is removed because a separate required field is missing, so these cases do not distinguish their stated invariant.
The complete model test file covers required draft identity and several request-mode constraints, but does not repair the oracle of these specific HTTP selectors.
Future action should make every other field valid in those negatives; retain separate omission cases and do not duplicate the whole HTTP journey.

#### B-F029 — P3 contract/test debt: frozen ExecutionContext is only shallowly immutable

`models/execution.py:45–66` documents a stable frozen context but exposes mutable lists/dictionaries (`requested_nodes`, `planned_node_ids`, `planned_node_names`).
`tests/test_models/test_execution.py::TestExecutionContext::test_is_immutable` checks only field reassignment.
In-process holders can mutate a retained execution's requested/plan identity in place; no client HTTP mutation or observed retry corruption is claimed.
Future decision should clarify public immutability versus a stable field-assignment boundary, then either enforce the intended collection contract or document it and add a distinguishing model-level oracle.
Do not infer the literal default lists in ExecutionResult are shared: Pydantic supplies instance defaults; this review found no mutable-default cross-instance defect.

#### B-F030 — P3 retention/design risk: local finished-run maps and all progress events have no eviction boundary

`services/execution.py:463–469,718–724,868–894,1016–1022,1491` retains status, result-export descriptors and complete per-execution event lists for every local run for the manager's lifetime.
Run contexts are normally released after export/failure, but historical progress/status/export maps persist, and row/task events can grow with workload.
This supports independent execution queries, so blanket clearing on completion would violate existing retained-run behavior.
No measured memory cost or approved retention bound is claimed; execution registry/runtime persistence must be read before choosing a retention policy.
Future action is to reconcile durable registry ownership with bounded live snapshots and measure representative event volume, reusing retained-progress tests rather than add redundant successful-compute integration cases.

### Complete-review checkpoint — A-batch-6

#### A-F047 — Medium/High potential impact, superseded root initialization ownership risk

useCanvasPersistence.ts:419–473 stores an initialization promise, awaits fetchDraft, then creates and publishes the coordinator without checking whether that initialization is still the current operation.
resolveFromDraft:548–564 clears initialization and replaces authority but does not abort or invalidate a held earlier GET; initializeFromDraft can likewise seed a newer authoritative response while the older GET is pending.
The old response can subsequently pass the same workflow-ID/disposal checks, adopt its old graph when pendingDraft has been cleared, and replace the newly resolved coordinator/revision.
An old catch also clears the shared initialization slot and publishes its error without an operation-identity check.
This is a demonstrated source interleaving, not an executed UI loss; full CanvasView resolution/admission callers remain pending and server CAS protects a stale subsequent PUT from overwriting newer server data.
Existing selectors `clears pending after edits coalesce while draft initialization is in flight` and `clears a sticky CAS conflict only after explicit authoritative resolution` exercise each behavior separately, not resolution/reinitialization while the earlier GET is held.
Retain fixed workflow ID, CAS and latest edit coalescing; future action should assess caller reachability and fence initialization publication/finalization by the captured operation.

#### A-F048 — Medium potential impact, nested disposal does not own transport-side acceptance

nestedSnapshotPersistence.ts:158–186 mutates latestAccepted and invokes onAccepted inside the asynchronous transport function before graphSyncCoordinator's disposal race can protect acceptance.
More directly, startConflictResolution:196–230 creates an untracked AbortController for a held GET; dispose is only coordinator.dispose at line282.
After disposal the GET can still invoke the resolution callback, which mutates latestAccepted/onAccepted at234–248 before resumeAfterConflict/acceptAuthoritativeSnapshot rejects the disposed coordinator.
The normal Axios PUT respects the forwarded abort signal, which mitigates ordinary aborted PUT completion; the conflict GET is not aborted through this resource's dispose.
No held-response disposal was executed, and stale mounted UI effects remain a caller-lifetime risk pending CanvasView.
`holds a revision conflict and rebases the latest local graph only after an explicit action` and `replaces conflicted local work with the explicitly selected latest snapshot without another PUT` have immediate GET responses; graph coordinator disposal tests cannot observe these wrapper-side mutations.
Retain explicit resolution and session/revision checks; future action should own and fence every transport-side acceptance and resolution finalizer.

#### A-F049 — Medium potential impact, root disposal is a local wait barrier rather than a PUT cancellation barrier

workflowDraftCoordinator.ts:177–178 schedules the transport in a microtask and races its result against disposal; dispose aborts request.signal.
useCanvasPersistence.ts:66–83 and452–457 omit any signal from the production transport interface/PUT delegation, so that abort is never forwarded to fetch/PUT.
Even disposing before the scheduled transport callback runs does not stop that callback, which receives an already-aborted signal that the root adapter ignores.
A pending request may therefore still reach or commit at the server after the local wrapper stops waiting; do not claim this alone is data loss, since a durable already-admitted draft write can be intentional and server CAS remains active.
`unregistering one canvas cancels only its persistence resources` tests queued debounce work; `disposing one canvas rejects its write without affecting another canvas` proves local promise rejection, not whether a server write starts/commits.
This is separate from A-F007's physical backend worker/admission risk and A-F004's missing wire incarnation.
Retain physical recovery clear ordering; future action should specify the root write disposal contract and either forward cancellation/preflight admission or explicitly document durable completion semantics.

#### A-F050 — Medium, draft response authority guard gap

workflowDraftCoordinator.ts:179–190 accepts response.workflow_id and response.draft_revision without checking the captured workflow ID or expected next revision, unlike nestedSnapshotPersistence.ts:178–183.
Its root onAccepted callback adopts that response directly at useCanvasPersistence.ts:396–410; the initial GET path does check workflow identity.
A wrong-identity or regressed/jumped PUT response can therefore advance the root authority without refusal.
The normal server implementation returns the correct identity and CAS increment, so this is an adapter-contract/oracle gap, not a demonstrated normal-server misroute.
All complete draft coordinator/routing test responses have matching identities and expected revisions; existing captured-request assertions do not distinguish a mismatched response.
Retain server CAS and generated response models; future action should enforce equivalent response admission checks at the client authority boundary.

#### A-F051 — Low/Medium, nested accepted graph and current graph can diverge after normalization

nestedSnapshotPersistence.ts:184–186 stores the accepted server document but returns only validation to graphSyncCoordinator.
The graph coordinator's normal acceptance retains the queued graph, and nested currentGraph aliases that graph at line275; flushLatest returns latestAccepted.graph at190–193.
The complete nested test `joins an in-flight write and returns the newest exact accepted document` deliberately changes the response node name to server-normalized-b and asserts the flush result/onAccepted callback, but does not assert currentGraph.
Thus the mock contract already permits a server graph for which the public currentGraph and flush result differ; root routing has an explicit contrasting accepted-graph authority test.
The current backend may return the submitted graph unchanged; no real normalization or visible drift was executed, and CanvasView onAccepted hydration must still be reviewed.
Retain newest local edits queued during an older response; future action should decide when the accepted latest graph replaces the projection without discarding those edits.

#### A-F052 — Low/Medium, accepted callback failure mixes committed acceptance and operational retry state

workflowDraftCoordinator.ts:190–198 updates acceptedQueueRevision/currentDraftRevision before calling onAccepted; an exception then enters the ordinary failure catch.
flushLatest:254–259 returns the already recorded acceptance on retry without calling the callback again or clearing that error state.
Nested acceptance similarly updates latestAccepted before onAccepted; a callback exception can make an already committed PUT appear failed and a subsequent retry submit it again at the newer revision.
Production root callback includes draft-store acknowledgment; actual throw reachability remains pending full store/UI review.
Complete coordinator tests use nonthrowing callbacks and transport failures, so they do not distinguish failed local projection/acknowledgment from failed persistence.
This is analogous to, but separate from, backend postcommit acknowledgment A-F014.
Retain durable response revision and no stale replay; future action should explicitly separate committed persistence from ancillary callback failure/recovery.

#### A-F053 — Medium potential impact, retained nested writer retains its first mounted callback

useGraphSync.ts:273–281 constructs a durable writer only once and supplies onAccepted from its first registration.
Ordinary tab dispose leaves that writer alive, and remount reuses it without replacing or leasing the callback.
The writer can therefore keep references to the old mounted consumer and omit the remounted consumer's callback.
This is a source lifetime risk, not a proven broken remount: full CanvasView callback closure and hydration behavior remain pending.
`retains a writer across ordinary tab disposal but forgets it after root deletion` verifies durable PUT reuse but supplies no onAccepted callbacks across remount.
Retain durable writer lifetime; future action should separate durable authority from mounted observer ownership if the caller closure is instance-local.

#### A-F054 — Low/Medium, nested registration does not check descriptor/session agreement

useGraphSync.ts:258,273–286 registers descriptor.sessionId but keys/constructs the resource from initialSnapshot.session_id without checking agreement.
A descriptor A with snapshot B can bind A's registry session to B's durable writer while other descriptor consumers retain A.
Every reviewed test passes consistent identities, and no production inconsistent caller is claimed; full callers remain pending.
Missing initial snapshots also register before refusal, extending A-F046's setup-error mutation to graph sync.
Retain immutable descriptor identity; future action should preflight one consistent session identity before registering or attaching any writer.

#### A-F055 — Medium potential impact, late root critical/reset responses lack final operation admission

useCanvasPersistence.ts:592–608 captures a coordinator then awaits the freshness GET without rechecking disposal/current coordinator, workflow response identity or a superseding local edit/resolution before returning true or publishing remote revision.
discardToSaved:611–658 flushes first, awaits reset, then unconditionally disposes the current coordinator, clears pending edits and adopts the response; it has no post-await lifetime/operation check.
Server reset CAS protects server authority at the request boundary, but cannot alone protect newer client edits/resolution made while the response is held.
A critical GET with a lower revision is accepted as fresh; A-F004 already owns workflow incarnation absence and is the canonical broader related finding.
Tests fence preexisting draft/recovery work and distinguish reset CAS loss and cleanup failure, but do not queue a newer local edit or dispose/resolve while GET/reset is held.
Actual GUI editing/lifecycle guards are pending full CanvasView/MenuBar reads; no global Open defect or reset loss is claimed.
Retain explicit user reset intent, server CAS, strict recovery cleanup and the committed-response cleanup error; future action should verify caller guards and captured operation ownership before publication.

#### A-F056 — Low, recovery invalidation tombstones accumulate by historical key

recoveryPersistenceCoordinator.ts:83,169–176 stores invalidatedOwnershipThroughByRecoveryKey entries on every strict clear and never removes them.
Unlike ownership/write-tail maps, this map has no empty-key cleanup; many historical unique deleted workflow keys remain for the page lifetime.
The map is required to fence outstanding previously owned writes; blindly removing a tombstone at clear completion would weaken that invariant.
No memory growth was measured and ordinary finite workspace use is not claimed problematic.
The complete tests cover physical clear ordering and ownership release, not tombstone retirement after all older owners finish.
Future action may consolidate tombstone lifetime with known outstanding owners only if a measured or bounded lifecycle need warrants it.


### Complete-review checkpoint — A-batch-7

#### A-F057 — Low/Medium potential impact, apply coalescing is keyed by ID before checking session object

nestedWorkflowApplyCoordinator.ts:89–91 returns an existing in-flight promise solely by sessionId, before the sessionIdentity check used for retained retry at94–95.
clear/reset removes map ownership but does not cancel an already running parent runner; its later completion is guarded only when deleting map state, not when applying effects outside the coordinator.
A same-ID replacement caller could join or be acknowledged using an earlier object's accepted transaction.
Production captures parent/nested registration/session guards, and ordinary durable delete recreates a different UUID; this substantially constrains the risk.
Full App/CanvasView lifecycle and parent runner remain pending; no parent overwrite or real same-ID replacement was executed.
`coalesces concurrent saves around the first exact accepted private revision` uses one session object; the retry test changes registration but preserves that object, both intended sound cases.
Retain exact first-transaction coalescing and retry; future action should first prove whether same durable ID can denote a replacement object during an in-flight apply, then decide admission/cancellation behavior.

#### A-F058 — Low/Medium, direct overwrite API clones a mutable graph after the first await

workflowDraft.ts:144–155 fetches the latest server draft before cloning the graph argument for PUT.
A caller mutating that object while GET is held changes the submitted recipe relative to the action's invocation; the persistence coordinators correctly clone at queue time.
CanvasView:1039 passes a freshly serialized submittedGraph and separately preserves newer local edits after acknowledgment, mitigating this current primary consumer.
`overwrites a newer remote draft with the current graph revision` uses an unchanged localGraph; the delayed overwrite test holds PUT, not the GET before cloning.
No changed production payload was reproduced.
Retain explicit overwrite intent and latest CAS fetch; future action can make the API's payload capture contract consistent if it remains public, without replaying new local edits as the old action.

#### A-F059 — Medium potential impact, late responses recreate forgotten draft revision authority

workflowDraft.ts:132–137 tracks before GET but has no operation/incarnation barrier when acknowledgeAcceptedDraft runs after await; overwrite likewise acknowledges after PUT.
forgetWorkflow:174–178 removes state, but acknowledgeAcceptedDraft:194 creates it again by workflow_id and records max old revisions.
If an old response lands after delete/forget and same name reuse, the new workflow's lower revisions/events can be treated as already known.
The full root presentation helper rejects stale final presentation through workflow-store generation, but that happens after the direct draft-store acknowledgment, so it does not prevent retained-state contamination.
This is a concrete companion source path for canonical A-F004, not a separately proved recreation loss.
`forgets only the deleted workflow state before the id is reused` is synchronous; `does not reactivate a workflow when its in-flight overwrite is acknowledged` protects a different active name, not forgotten same-name incarnation.
Retain inactive accepted writes and monotonic notice ordering within one incarnation; future authority work should key/guard those acknowledgments by captured incarnation rather than dropping all inactive responses.

#### A-F060 — Medium qualified source risk, recovery rename bypasses per-key write/clear ownership

useAutoSave.ts:114–135 loads the old entry, writes the new key and separately clears the old key in different IndexedDB transactions.
It neither fences an old-key recovery write nor compares the old entry atomically before deletion, and a failed old-key clear is logged/swallowed while rename can resolve.
A concurrently queued writer can recreate the old key or be deleted after producing a newer snapshot; partial moves can leave both names while last-opened preference advances.
Targeted workflow store calls guard identity changes against mounted workflows, strongly mitigating ordinary active-canvas writes; the complete store and pending physical write shutdown still need review.
No IndexedDB concurrency/partial failure was executed.
There is no dedicated useAutoSave unit file in the tracked source inventory; persistence tests mock recovery transports and therefore do not exercise this actual move primitive.
Retain copy-before-delete safety when the new write fails; future action should review lifecycle fencing and one atomic move/conditional-delete boundary before changing it.

#### A-F061 — High potential recovery loss, startup treats any load failure as authoritative missing-workflow evidence

startupWorkflow.ts:76–92 catches every presentation load error and clears the matching recovery entry and last-opened preference.
A transient saved-workflow request error, server 500 or stale-identity refusal therefore takes the same destructive cleanup branch as a confirmed 404.
useAutoSave.clearAutoSave performs actual deletion, so this can remove the only browser recovery graph merely because startup loading temporarily failed; no failing request was executed here.
`clears a missing startup target and falls through to the next known workflow` mocks a plain Error('404') rather than a structured status; it cannot distinguish confirmed absence from transient failure.
`returns null instead of creating a special startup workflow when none can load` uses the same untyped failure policy.
Retain graceful fallback to another known workflow and cleanup of confirmed obsolete names; future action should distinguish authority-backed absence from retryable/unclassified load errors before destructive recovery cleanup.

#### A-F062 — Medium/High potential impact, all draft load failures silently fall back to saved graph

rootWorkflowPresentation.ts:56–71 catches any draft loading failure and presents savedGraph with dirty=false, without retaining the draft failure or distinguishing unsupported/missing draft from unavailable/corrupt/conflicting authority.
An existing unsaved durable draft can thus be hidden during a temporary endpoint failure.
If editing begins on that saved fallback and the persistence initializer later succeeds, its retained pending local graph can be PUT using the now-current draft CAS base; the user may replace the hidden durable draft without first seeing/resolving it.
That consequence remains caller-qualified pending full CanvasView initialization/edit gates; the source fallback itself is definite, with no data loss execution claimed.
`marks a resolved graph stale when its workflow generation is later deleted` deliberately mocks draft failure but checks only generation fencing; other complete presentation tests use successful drafts.
Retain compatibility fallback only where the contract genuinely permits it and generation fencing; future action should make missing versus failed draft authority visible/explicit before allowing replacement semantics.

#### A-F063 — Medium/High potential impact, stale recovery cleanup deletes by key without checking the inspected entry

startupWorkflow.ts:26–30 inspects a loaded entry's timestamp then awaits clearAutoSave(name); useAutoSave.ts:75–78 deletes the key unconditionally in another transaction.
A newer recovery write for that same key between the read and deletion can be removed by a cleanup decision about the older entry.
Startup supersession protects loading presentation through canPresent, but does not pass that guard through recovery inspection/cleanup; the post-load helper can continue while explicit Open owns the app.
The stronger strict clear coordinator addresses deliberate workflow discard/delete, not this conditional stale-entry cleanup; blindly using strict clear here could also invalidate valid newer snapshots.
Complete startup tests mock immediate clear and loaded snapshots, and root presentation supersession tests mock AutoSave, so no test distinguishes conditional read/delete from an intervening new write.
No actual recurrence or ISSUE022 cause is claimed; its cause remains unproved.
Retain deletion of genuinely stale recovery; future action should condition cleanup on the captured entry/owner in the actual storage transaction and review superseded startup side effects.


### Complete-review checkpoint — A-batch-8

#### A-F064 — Medium/High, static grouping serializer drops node viewer additions

workflowGrouping.ts:70–105 serializes selected tool/nested nodes through a second handwritten serializer without viewer_additions.
The canonical graph sync serializer and graphStateToVueFlow:113,133 preserve that field, and strict graph models accept it for both node variants.
Grouping a node with user-declared viewer additions therefore removes those additions from the captured child definition even though other tool/source binding metadata is carried.
No grouping gesture/serialization test was executed during audit.
`publishes exposed output schemas without an absent viewer declaration` tests catalog output field schema only, not node additions or nested invocation additions.
Retain structural viewer declaration semantics and portable captured identity; future action should reuse one canonical node serializer or assert semantic field parity across every serializer.

#### A-F065 — Medium, static nested dataframe grouping kind mismatch

workflowGrouping.ts:176–204 recognizes positional dataframe targets but declares every other supported workflow-input target as kind='field', independently of its incoming edge and child input kind.
An existing nested workflow node receiving a dataframe through its stable workflow-input handle can be grouped; its rewritten incoming edge remains dataframe at279–283 while the new outer public port is field.
The complete backend GraphState validator explicitly refuses that combination at models/graph.py:466–470 with wrong workflow input kind.
No new grouping validation was executed; this is a direct source contract mismatch.
`publishes an incoming positional DataFrame and preserves exact DataFrame routes` covers plain positional targets, not an already-nested dataframe port.
Retain stable nested port IDs and dataframe positional distinction; future action should derive the new public port kind/schema from the actual boundary edge/child port.

#### A-F066 — Medium/High potential impact, bound or missing-tool hydration rewrites templates using live name-only metadata

workflowGraph.ts:155–166 looks up current ToolMetadata solely by node.tool_name while retaining explicit package/version/class/source identity separately.
toolNodeData:106 reconciles the saved output_templates against that live metadata.
Root-owned outputTemplates.ts:15–18 returns an empty map if metadata is unavailable or names a DataFrameTool; lines21–30 drop keys not recognized as current path outputs and fill defaults from the live class.
A captured portable v1 node under catalog v2 or a currently missing captured tool can thus lose saved templates or adopt incompatible defaults merely on client hydration; subsequent canonical serialization persists that altered map.
This extends A-F001's captured-versus-live authority seam into presentation/payload transformation; it does not equate ordinary unbound catalog metadata updates with defects.
`renders tool and workflow nodes from their discriminators` has one matching current tool; root-owned reconciliation tests deliberately assert stale-key removal under an explicitly selected current tool, which is valid for rebind but does not establish safe portable hydration.
No actual UI persisted template loss was executed; full hydration/rebind callers remain pending.
Retain deliberate reconciliation when the user chooses a new tool definition; future action must distinguish captured-bound hydration/unavailable metadata from explicit rebind.

#### A-F067 — Medium, incremental upsert ignores returned folder authority

workflow.ts:496–530 inserts/replaces returned info but never assigns workflowFolderIds[infoId] from info.folder.
For a new create/import/duplicate in an already-known folder, sanitizeWorkflowTreeState maps the absent folder association to root.
For a rename/patch changing folders, upsert copies the previous folder mapping even if returned info.folder changed.
Dedicated moveWorkflowToFolder later fixes its mapping and folder operations refetch the full tree, but general create/import/patch paths do not perform that correction in the store.
Targeted panel consumers can refresh afterward, so persistent visible misplacement is caller-qualified pending their full read; the inconsistent intermediate store state is definite.
Tests create/import/duplicate at root and exercise dedicated move APIs, not nested-folder incremental upsert without a later refresh.
Retain server canonical workflow IDs and local sibling ordering; future action should adopt returned folder membership consistently without using an old folder for a newly moved identity.

#### A-F068 — Medium potential impact, older collection responses can remove newer observed generations

workflow.ts:246–253 replaces the flat list with only items passing acceptWorkflowInfoGeneration; tree visit:269–282 likewise drops rejected older items.
Observing a newer generation from ordinary fetched info at204–211 does not advance collection generation unless structuralEvent was explicitly supplied.
Two concurrent refreshes can therefore share one collection generation: a newer response first installs generation12, then an older response10 is rejected and the replacement collection excludes the generation12 workflow entirely.
A websocket structural event or local identity mutation advances collection generation and mitigates this path, but a fetched newer server generation without such an observed event remains possible at the API boundary.
No reordered refresh was executed.
`retries a stale flat-list response that crosses workflow deletion` and its tree counterpart test a local generation change, not out-of-order refreshes with no independently observed event.
Retain rejection of stale incarnations and bounded refresh retry; future action should ensure rejecting stale entries cannot erase a fresher retained collection authority, or make newer observation invalidate the captured collection generation.

#### A-F069 — Medium/High potential impact, mounted-identity guard is checked only before structural API awaits

workflow.ts:323–336 refuses currently registered presenting canvases.
patchWorkflow:958–975, applyWorkflowIdentityMove:1196–1220 and folder rename/move:1106–1119,1180–1192 check unmounted state before awaiting mutation but do not hold an in-flight identity fence or recheck a canvas that mounted while the response was held.
A load already admitted before that mutation can present a tab after the initial check and before mutation response adoption; the mutation may then advance/rename the identity while a registered immutable canvas descriptor still denotes the old one.
Local DELETE does hold workflowDeletionsInFlight, and generation checks prevent later old loads after invalidation, which are strong retained mitigations but not a structural pre-await admission barrier here.
No real GUI interleaving was executed, and App/CanvasView presentation checks still await complete review.
Tests refuse already-mounted operations or reject responses after explicit removal; they do not register a presenting canvas while the structural mutation response is pending.
Retain the policy that mounted identities cannot be structurally changed; future action should review one admission owner across open versus rename/move/folder mutation rather than adding gesture waits.

#### A-F070 — Low/Medium potential impact, structural completion can restore an obsolete global current selection

applyWorkflowIdentityMove:1206,1221–1224 captures wasCurrent before awaits then sets current afterward without checking whether the user selected another workflow meanwhile.
applyWorkflowFolderIdentityMove:1085,1102–1103 and child promotion:1143,1168–1171 similarly capture previousCurrent and activate its remapped identity after recovery work/tree refresh.
Actual mounted-identity refusal and UI close/activation behavior constrain reachability; full panel/App callers remain pending and no wrong active canvas is established.
The explicit-target Save/metadata update path has active-canvas/current-name checks; these structural helpers lack their equivalent captured selection guard.
Tests remap the original current identity but do not switch current during held rename/recovery/tree work.
Retain successful structural identity remapping; future action should separate durable collection updates from optional global active presentation ownership.

#### A-F071 — Low, malformed disposition and exceptional download cleanup

workflow.ts:97–101 decodeURIComponent on filename*=UTF-8'' can throw for malformed percent text, turning an otherwise downloaded blob into a failed action instead of using the fallback filename.
The normal backend constructs valid headers; this is an external/adaptor robustness case, not a current backend failure.
downloadBlob:105–115 revokes/removes only on ordinary success, so an exceptional click/append could abandon its URL/anchor.
Export tests use valid plain filename or no header and mock a nonthrowing click; no malformed header/exception was executed.
Retain safe basename fallback and current endpoint/signal routing; future action can use bounded parser fallback and finally cleanup when this small boundary is maintained.


### Complete-review checkpoint — B-batch-4

#### B-F031 — P2 source defect: archive hashing can strand an attached run as running

`backend/src/bioimageflow_server/services/execution_runtime.py:322–353` catches result-export and archive-building errors, but `_archive_digest(archive)` in the success `else` can raise outside that catch and before `_complete`.
The attached task then ends exceptionally while `_status` remains running, so the coordinator observes a running adapter without that task failure; `_error` also remains unset.
The submitted adapter similarly performs archive construction/hashing outside its download failure handling at lines245–250, leaving its previous export descriptor on a local archive failure.
The normal manager variant is B-F025: its escaped export failure instead becomes compute failure.
`test_attached_export_failure_preserves_success_and_disables_download` exercises AttachedRunAdapter with a failing exporter, not destination-provider/digest failures on ExecutionManager; `test_direct_and_wetlands_managed_export_is_released_and_downloadable` covers the manager's positive export only.
Future exact diagnostics should distinguish these three ownership outcomes rather than duplicate successful compute journeys.
Retain successful computation independently of downloadable export availability; no injected failure or observed stranded run is claimed.

#### B-F032 — P2 destructive migration source risk: every non-local v1 backend is erased, including malformed/unknown values

`services/execution_registry.py:112–139` deletes any schema_version=1 snapshot whose backend is not direct/wetlands, before validating the backend or the rest of the snapshot.
The stated migration removes obsolete distributed formats, and `test_migration_erases_legacy_distributed_bytes` explicitly establishes removal of submitted_remote credentials/history; that essential cleanup must remain.
A missing/misspelled/unrecognized backend in a damaged v1 record is also irreversibly removed under the current branch, without distinguishing recognized retired formats from corruption.
No migration was executed in this audit.
Future decision should enumerate accepted retired formats and use explicit corruption handling for the rest, with an exact negative migration oracle; preserve required legacy credential erasure and local v1 retention.

#### B-F033 — P2 identity source defect: registry file/request identity is not compared with decoded execution_id

`services/execution_registry.py:157–170,206–238` validates requested path characters but accepts any valid snapshot payload's execution_id without checking it equals the requested id or JSON file stem.
A corrupted/swapped valid snapshot can make GET for execution A return execution B, and list/non_terminal bind roots using payload B even though the file names A.
`save` uses safe execution ids and normal atomic replacement, so ordinary writer behavior does not manufacture this mismatch; this is persistent-corruption/identity refusal coverage, not a hostile symlink claim or observed wrong-run operation.
The complete registry/reload/workspace-binding tests cover valid paths/CAS and do not distinguish mismatched ids.
Future exact diagnostic should swap only the payload id in an otherwise valid file and require controlled identity refusal before action binding, preserving active-run workspace pinning.

#### B-F034 — P2 source risk: publication or persistence failure can permanently stop observation of an accepted run

`services/execution_runtime.py:541–559` installs an adapter before registry reread/initial publication, but creates its poll task only afterward.
A raising publisher leaves an installed adapter with no poll task; a repeated attach is rejected as already attached.
`_refresh_once` at lines1226–1232 and `_record_observation_failure` at1259–1266 place persistence/publication outside their adapter-observation catch, and `_poll_loop` at1156–1167 has no failure recovery beyond cancellation and removes the task on exit.
A transient save/CAS/publication error can thus end polling while the accepted run continues, distinct from the correctly handled remote observation failures.
Complete tests cover network/handle observation loss and exact-child retry recovery, but not a fail-once publisher or registry-save failure during ongoing polling.
Actual default EventBus error behavior and durable registry conflict conditions need the adjacent authority trace before claiming a default user-facing reproduction.
Future diagnostic should use the existing coordinator fixture with one explicit fail-once persistence/publication hook, preserve accepted identity and observation-vs-authoritative-state separation, and avoid resubmission as recovery.

#### B-F035 — P2 source risk: cancellation requested before attached task execution is overwritten

`services/execution_runtime.py:289–293,322–323,366–372` lets `start()` schedule the task while status is starting; `cancel()` records cancel_requested and invokes the callback, then `_run` unconditionally sets running.
If cancellation arrives before the coroutine starts, the later cancellation checks no longer see the request; result/state can become succeeded when the callback does not itself interrupt compute.
This is an adapter lifecycle risk, not an executed Workflow cancellation failure: the callback/public library's cancellation state is a second authority that must be traced before default consequences are asserted.
Complete attached tests do not coordinate start→immediate cancellation before first compute admission.
Future exact adapter diagnostic should retain the cancellation intention and distinguish physical callback completion from merely scheduling an asyncio task.
Raw asyncio task cancellation for AttachedRunAdapter also releases its awaiter while compute can continue and leaves status running (CancelledError is not caught); record this as an additional B-F024 seam, not another general rewrite.

#### B-F036 — P3 persistence/design risk: attached completion/archive durability is weaker than registry durability

`services/execution_runtime.py:89–107,134–165` atomically replaces the archive and fsyncs the completion temporary file, but does not fsync the replaced completion directory or archive file/directory.
`services/execution_registry.py:428–448` explicitly fsyncs the replaced snapshot file and containing directory.
The attached sidecar is described as durable/process-independent and startup uses it to recover authoritative completion before registry polling; a stronger power-loss guarantee is not established by the current file/rename sequence.
Tests simulate process-independent reopen/tampering, not an OS power-loss oracle; no lost durable result was observed.
Future action should specify the intended crash boundary and reuse the platform durability helpers if filesystem durability is part of that contract, without pretending a normal reopen test proves power-loss behavior.

#### B-F037 — P3 corruption handling/test debt: retry-journal readers assume object envelopes

`services/execution_registry.py:289–422` several readers call envelope.get after JSON decoding without mapping-shape checks; JSONDecodeError and a scalar/list shape also escape most retry state methods as generic exceptions.
Cleanup journal reading has more explicit envelope/digest refusal, and the public RunRetryPlan parser protects payload integrity after successful journal read.
Complete retry tests distinguish child uncertainty, confirmation states, digest tampering and exact-child recovery, but not malformed envelope shapes or partial journal corruption.
Future action should choose a stable corruption error and fail closed before replay; keep the same preallocated child and never infer absence from journal-read failure.
This is error classification/maintainability debt, not a claim that malformed journal bytes currently authorize a second child.

#### B-F038 — P3 suite classification candidate: distributed module exclusion also labels local runtime contracts

`backend/tests/test_services/test_execution_runtime.py:35` applies campaign_excluded(distributed-engine) to every test, including local registry, progress reduction, AttachedRunAdapter restart/export and regular direct/Wetlands manager retention.
The distributed-integration and plural-router modules are similarly marked; their actual remote contracts warrant static review regardless of campaign execution exclusions.
This is a classification candidate, not an omission claim about ordinary CI/full lanes.
The shared infrastructure reviewer was notified and will reconcile actual pytest hook/filter authority before a coverage decision.
Future action may split per-test ownership/markers so local contracts are retained in the applicable campaign gate, without expanding campaign credits to unexecuted remote scheduling.

#### B-F039 — P3 test robustness debt: successful attached completion is inferred after a fixed 50ms sleep

`tests/test_services/test_execution_runtime.py::test_attached_export_failure_preserves_success_and_disables_download` sleeps0.05 then requires terminal success, while thread scheduling and polling are asynchronous.
This can become an incidental timing oracle on a loaded machine; no flake or measured suite cost is claimed.
Future action should await a bounded observable terminal transition/physical task completion using the existing fixture and retain the export-failure distinction.
B-F012 also extends to `test_retry_confirmation_refreshes_parent_after_waiting_for_run_lock`: its event wait is unbounded and manual lock release is not in finally; a failure before release can strand the confirmation task.
Other direct adapter tests explicitly await the actual task and supply a stronger physical-completion oracle.

#### B-F040 — P3 source defect: progress sequence filtering occurs after unsafe coercion

`services/execution_progress.py:53–59` promises/implements skipping non-int sequence values in the loop, but sorts first with int(event.get('sequence', -1)).
A non-numeric string/None sequence raises before that rejection and discards the entire reduction attempt, including otherwise valid events.
The coordinator classifies this as observation failure and retains its cursor; replaying the same malformed event can repeatedly block healthy later events.
Public library event producers and handle-parser validation remain a separate boundary to trace; no malformed event was observed and no assertion that valid public events contain these values is made.
The complete reducer tests cover valid replay, parallel diagnostics and phase values only.
Future narrow diagnostic should place one malformed sequence beside valid events, retain monotonic integer cursor behavior and avoid relaxing public diagnostic/secret validation.


### Complete-review checkpoint — B-batch-5

#### B-F041 — P2 source risk: cancellation can lose a returned managed run identity while submission continues

`backend/src/bioimageflow_server/services/execution_preflight.py:146–165` pops the intent then awaits asyncio.to_thread(entry.prepared.submit); finally closes the intent.
`ManagedSubmitIntent.submit` at104–120 can continue the physical public cluster.submit after cancellation of that awaiter, but the cancelled request no longer returns acceptance to `routers/executions.py:90–119` for registration.
Thus the documented residual process-crash allocation/identity window also exists under raw asyncio cancellation of the consuming route task; closing the intent only changes a flag and does not recover/persist the returned acceptance.
This is static risk, not an executed lost remote allocation or a claim that every browser disconnect cancels an ASGI handler.
The complete token/preflight tests cover binding mismatch and one-use submission, not physical submission completion under route cancellation.
Public library cluster.submit durability/recovery remains pending deeper review; no private scan/resubmission should compensate for an unknown identity.
Future exact diagnostic should coordinate a bounded fake public submission and cancellation, observe physical completion and acceptance persistence, then reconcile the owned operation lifetime before any actual remote test.
Link B-F024 physical-completion ownership while retaining explicit one-use token and direct-public-submit semantics; avoid a universal coordinator redesign.

#### B-F042 — P1 route policy defect: node Reveal lacks the desktop-only mode guard

`backend/src/bioimageflow_server/routers/nodes.py:641–659` resolves the result cell and directly invokes reveal_in_file_browser without a settings/process-policy dependency or mode check.
The completely reviewed app installs this router in both modes; its readiness middleware is not a desktop filesystem-policy gate.
PLATFORM_CONTEXT requires desktop-only filesystem capabilities gated in webapp; the complete node test file covers successful record-relative Reveal and exact asset delegation, with no webapp refusal case.
This is separate from ROOT-F002's mutable-mode authority at existing guards: this route has no guard to mutate.
No Reveal/native/webapp action was performed during the audit.
Future bounded diagnostic should use immutable AppConfig/process mode and assert refusal before native launch; preserve actual desktop functionality and result identity validation.
Root requested this separate finding and will link it in policy synthesis.

#### B-F043 — P2 presentation contract/test gap: valid infinite results lose their distinction from missing values in node JSON

`routers/nodes.py:150–166` passes DataFrame.to_dict rows into `models/nodes.py:40–70` Any-valued cells without a nonfinite presentation policy.
Scientific positive infinity can be valid (root's perfect-match infinite PSNR contract), and changing that mathematical result to a finite value is not warranted.
Installed FastAPI0.135.3 routing.py690–720 uses its default-response-model dump_json fast path; `_compat/v2.py:202–227` delegates to Pydantic dump_json.
Installed Pydantic2.12.5 `_internal/_config.py:297` defaults ser_json_inf_nan to null, with no NodeDataResponse override.
Static inference: the default node JSON path maps +infinity/-infinity/NaN to null, erasing valid infinity versus missing-data meaning; it is not the older JSONResponse allow_nan=False failure path for this baseline.
No serialization call or endpoint was executed, and no alternate dependency baseline is certified.
The complete node model/HTTP tests contain no nonfinite-value distinction; CSV still emits pandas' textual result representation.
Future action should choose an explicit JSON-safe presentation plus frontend/type semantics for valid infinity and missing values, retain scientific truth, and add one exact node model/API oracle rather than duplicate scientific computation.

#### B-F044 — P2 multi-process source risk: OME conversion uses one shared temporary filename per cache key

`routers/nodes.py:378–411` uses a fixed cache_path+'.tmp', writes it, then replaces the cache path; error cleanup unlinks that same temporary path.
Independent server processes converting the same source/key can write/remove each other's temporary file or publish an incomplete competing conversion.
The cache root is process-global system temp, while the source hash includes resolved path/mtime/size; a single async worker executes this synchronous block serially, so this is not a claimed default same-loop interleaving.
Complete OME tests cover one conversion, offsets, unreadable source and age pruning, not coordinated same-key processes.
Future decision should use unique owned temporary output and validated atomic publication if multi-process/shared-cache operation is supported; retain normal cache reuse and prune behavior.
No concurrent conversion or bad TIFF was produced in this audit.

#### B-F045 — P2 source/API risk: table identity cannot be supplied to image/thumbnail/Reveal or filtered CSV endpoints

The query endpoint accepts ResultArtifactIdentity and pins pagination, but `routers/nodes.py:540–568,610–688` image/thumbnail/Reveal and filtered CSV reread latest using only node/workflow/row/column.
A table captured from run A cannot name A in those calls after latest advances to run B; the asset resolver validates the record belonging to the newly read dataframe, which does not establish that it is the table's displayed record.
Complete tests distinguish pinned table pagination and exact assets within a selected dataframe; their image/thumbnail/Reveal mocks return a fixed dataframe and do not exercise table capture followed by latest advance.
This is the API's missing pinning capability and a source risk for callers, not yet a claim of the whole frontend behavior; complete ImageCell/NodeDataTable/Avivator callers are the next batch.
Retain explicit external paths and legacy_unpinned refusal distinctions; adding a captured identity must not cause fallback to whichever latest record is convenient.
B-F026 separately concerns legacy-to-modern recapture during the reader itself.

#### B-F046 — P2 source/spec mismatch: captured profile object is used at submit without a fresh submit-time script check

The complete managed runtime wiring reference, Profile loading and Admission sections, and normative specification§3.1/3.2 require a fresh script import/current digest check for submission.
Actual `DistributedPreflightService.preflight` resolves/imports the profile before graph/path discovery, then stores the live profile/workflow in ManagedSubmitIntent.
`ManagedSubmitIntent.submit` uses that captured cluster directly; the consume/apply route does not call `PlatformExecutionProfileResolver.resolve_revision` (that method has no source caller).
A script/profile change during the token lifetime therefore does not trigger the documented fresh submit-time check.
The token does retain the exact captured request/profile/overrides internally, so this is not a claim that a token can silently switch its target; ordinary captured immutable intent semantics must be preserved.
Full tests cover profile digest changes during explicit resolution and exact intent consumption, not a changed script between issue and consume.
Future contract decision must reconcile submission's fresh-code promise with immutable captured intent and state whether current profile disable/update invalidates admission; no automatic repeated preparation or target rebinding is recommended.

#### B-F047 — P3 lifetime/debt: expired submit intents remain retained until explicit use or app shutdown

`services/execution_preflight.py:132–144,173–183` retains workflows/profile objects in `_entries` and provides reap_expired, but no backend source caller schedules/invokes it.
Expiry is checked on consume, so expired tokens cannot submit; the defect candidate is resource retention/cleanup, not authorization beyond lifetime.
Users repeatedly requesting ready preflight and abandoning its token can retain expired immutable graphs and profile objects for the application's lifetime.
Tests cover once-only and mismatched consumption, not abandoned expiry/reap/close lifecycle; no measured memory cost is claimed.
Future action should tie bounded expiry cleanup to the existing app token owner and cover cleanup without new remote execution journeys.

#### B-F048 — P2 conversion design risk: array-shape heuristics can reinterpret scalar volumes as color

`routers/nodes.py:359–375` classifies any3D array whose final dimension is3/4 as YXS and analogous4D arrays as ZYXS, while `_read_image_array` returns only array values and discards input TIFF axes/photometric metadata.
A scalar ZYX volume with X=3/4 is ambiguous by shape and may become color-oriented OME output; larger multidimensional scientific inputs have an explicit2–4D refusal rather than an inferred universal support promise.
Existing complete OME tests use2D grayscale and preserve already-OME files; they do not distinguish scalar-volume width3/4 from color channels.
No misrender was reproduced; library/Core image metadata and the frontend format promise must be traced before choosing a correction.
Future narrow diagnostic should retain known source axes/metadata when available and explicitly handle genuinely ambiguous unlabeled arrays, preserving existing RGB/multiframe behavior.


### Complete-review checkpoint — B-batch-6

#### B-F049 — P1 source defect/test oracle: configured Fiji button always omits required captured identity

`frontend/src/components/panels/ImageCell.vue:303–320` calls openInFiji with node,row,col,workflow_name but omits its available resultIdentity prop.
The complete API wrapper forwards the request unchanged; `backend/src/bioimageflow_server/routers/fiji.py:57–63` refuses result_identity=None with422 before native launch.
NodeDataTable passes `data.source_identity` into ImageCell, so the modern table has the value but loses it on this specific action.
The generated/model field is optional (`models/fiji.py:19`), so frontend compile validation cannot distinguish the semantic admission requirement.
Complete borrowed selector `frontend/src/components/panels/__tests__/ImageCell.test.ts` / `opens the selected workflow image in configured Fiji` asserts precisely the identity-less obsolete payload and mocks HTTP200.
Backend `test_open_requires_complete_result_identity` has the separate B-F023 confounded negative oracle; preserve existing valid-identity backend cases.
This is deterministic source behavior for the default configured desktop action, not a claimed executed native failure.
Future bounded diagnostic should require the captured identity in the caller payload and route contract together, retaining exact-result selection and disabling/refusing legacy unpinned opens appropriately rather than loosening the backend guard.
Do not request or launch desktop/native tests during the audit freeze.

#### B-F050 — P2 source publication defect: thumbnail readers can serve partial or failed PNG writes as ready

`backend/src/bioimageflow_server/_external/thumbnail_generator.py:82–84` writes directly to the final cache pathname with img.save.
`services/thumbnail_manager.py:117–122,173–181,195–197` treats file existence/readability as completion before its tracked execution task has physically finished.
A concurrent poll can read a partial PNG while the worker writes; if save fails after creating a file, the cache-hit branch also prevents retry and returns that damaged file indefinitely.
The node endpoint labels any non-placeholder bytes ready with public caching, and ImageCell makes a blob without image-decode validation or img error recovery.
Whole manager tests write the complete mock payload in one call and helper tests inspect the file only after return; none distinguishes physical write admission/publication.
No damaged image or timing race was executed.
Future exact diagnostic should coordinate partial write→physical completion/failure and demand unique temporary ownership plus atomic complete publication, retaining same-key deduplication and no-store placeholders.

#### B-F051 — P2 source/docs mismatch: thumbnail launch failure raises instead of yielding the documented placeholder recovery

`services/thumbnail_manager.py:206–215` says failed launch should not raise and callers receive a retryable placeholder, but `_launch` at285–316 logs/resets then re-raises and its await has no catch.
`get_or_queue` therefore fails the request on provisioning/start failure instead of reaching the placeholder branch; ImageCell's HTTP error path stops retries immediately.
The complete tests exercise successful fake launch and missing/cached fast paths, not actual public operation failure.
Future diagnostic should use a failing public-operation fixture and choose a coherent visible failure/retry policy (placeholder versus explicit terminal error), preserving recorded underlying failure detail.
This is not an invented provisioning pass or a claim that bad recipes should silently succeed.

#### B-F052 — P2 source lifecycle risk: thumbnail launch/submit awaiters are not drained or coordinated with shutdown

`services/thumbnail_manager.py:205–235` awaits physical `_launch`/pool.submit_path under asyncio locks without cancellation-safe physical-completion ownership.
`shutdown` at260–282 neither takes that lock nor marks the manager closed, and snapshots only already-tracked tasks/pool.
Raw request cancellation can unwind the lock while physical launch/submission continues; shutdown during launch can see pool=None and return before the worker thread later assigns a live pool.
Likewise a physically submitted task whose awaiter is cancelled before return can be absent from `_pending_generations`.
The existing shutdown test begins only after fake submission/tracking and validates cancel/close; it does not distinguish physical launch/shutdown overlap.
Actual public WorkerPool.close completion/manager worker ownership remains pending the full Wetlands audit; do not claim observed orphan workers or directory loss.
Future exact lifecycle diagnostic should coordinate physical launch/submission return with shutdown/cancellation using the existing owner fixture and retain the borrowed shared EnvironmentManager lifetime.
Link B-F024/B-F014; scope is the thumbnail owner, not a universal service coordinator.

#### B-F053 — P3 source/test contract gap: extension-less dispatch cannot realize the helper's canonical-extension promise

`thumbnail_manager.py:220–233` derives extension solely from the physical suffix, yielding an empty string for extension-less files.
The helper always calls Path(image_path).with_suffix('.'+extension) at33; empty extension produces '.', which Python3.13 pathlib rejects as a suffix.
The current test `test_queue_generate_handles_extension_with_no_dot` only checks the empty dispatch value against a fake pool; the helper symlink test supplies an explicit tif extension and therefore exercises another path.
This is an inferred source incompatibility on the authoritative Python3.13 baseline, not an executed helper failure.
Future contract decision should distinguish unsupported unnamed formats from supported logical-format metadata and avoid promising that the worker can infer an absent format.
Do not invent a format or mutate arbitrary input directories; any supported temporary alias must be owned, unique and cleaned on failure.

#### B-F054 — P2 source/UI identity risk: thumbnail reset ignores changed result identity when path/row text stays equal

`ImageCell.vue:265–272` watches node/workflow/row/col/value/enabled only, excluding resultIdentity and identityGeneration.
A new retained record that uses the same relative assets/mask.png text and row can leave the old blob attached even though the table now carries a new source identity.
Napari receives updated identity separately; the thumbnail/Avivator/Reveal endpoints still resolve latest without pinning (B-F045), and full ImageCell/NodeDataTable reads now confirm the real caller path, not merely API capability absence.
`openAvivator` uses a request-id guard for changed watched properties, but identity-only changes do not invalidate it either.
The borrowed complete ImageCell test changes workflow/path during offsets; no same-text/new-record oracle is present.
Future exact component diagnostic should change only the captured identity/incarnation, require stale asynchronous results ignored and pin actual backend image selection, retaining lazy visibility and bounded retry behavior.
There is also no separate fetch generation check after response.blob; abort is the sole thumbnail stale-request defense.
Treat ignored/late abort fulfillment as a qualified source risk until a real fetch timing diagnostic establishes the default browser interleaving.

#### B-F055 — P2 source display defect: table helper field overwrites a real __absoluteRow column

`frontend/src/components/panels/NodeDataTable.vue:37–44` spreads the producer row then assigns __absoluteRow=response.absolute_rows[i].
If the legitimate dataframe contains a column named __absoluteRow, its displayed value is replaced by the row position; column rendering reads that overwritten object property.
The backend's separate absolute_rows channel deliberately avoids payload helper collisions; its literal _absolute_row test protects a different spelling.
No producer contract examined so far forbids __absoluteRow, and the NodeDataResponse row-key validator accepts it as an ordinary column.
No UI/test execution or persisted data loss is claimed; the defect is in the displayed row model.
Future narrow table oracle should use exactly the colliding producer name and keep metadata outside its column namespace, preserving row-action absolute positions.

#### B-F056 — P3 test isolation debt: thumbnail helper loader leaves fake external modules in sys.modules

`backend/tests/test_services/test_thumbnail_generator.py:31–54` writes bioio/bioio_tifffile stubs directly into sys.modules on every helper load and never restores prior entries.
Complete test fixtures here have no cleanup; platform shared conftest controls paths/offline registry but does not supply this module restoration.
A later host-side import can receive the earlier fake reader instead of the real module; no actual contamination failure is claimed and separate Wetlands subprocess imports are not this same interpreter.
Future action should use owned monkeypatch restoration or a scoped loader fixture, retaining dependency-free pure tests and separate actual worker acceptance.
The full ImageCell counterpart also mounts several wrappers without consistently unmounting and uses stubGlobal; actual Vitest global restoration configuration belongs to the shared infrastructure owner, so do not claim it is absent here.

#### B-F057 — P3 preview policy/debt: scientific channels are interpreted as display alpha and later channels dropped

`_external/thumbnail_generator.py:51–79` says keep all channels but renders2-channel data as luminance+alpha,4+channel data as first4 RGBA and drops channel5 onward.
For scientific TCZYX channels, the second/fourth channel is not inherently alpha; its zero intensity can hide the first channels in the preview.
Middle T/Z selection and intensity normalization are intentional thumbnail summarization, not scientific output mutation.
Complete helper tests distinguish constant/single/RGBA-shaped data only and do not assert a multi-channel scientific display policy or alpha metadata semantics.
No misleading thumbnail was generated in this audit.
Future decision should define supported channel preview semantics, retain explicitly tagged RGBA where appropriate and label/handle dropped channels rather than imply complete-channel visualization.

#### B-F058 — P3 UI recovery/docs gap: exhausted thumbnails cannot retrigger merely by scrolling away and back

`ImageCell.vue:90–94` describes scrolling away/back as retry recovery.
`activateThumbnail` at250–256 sets activated=true and removes the observer; after fetch exhaustion/error it remains activated and no visibility observer is restarted.
Ordinary scroll-out/in therefore does not retrigger without a prop reset/remount, and no explicit thumbnail retry button exists.
The complete counterpart tests enforce finite retries and unavailable state but not this claimed recovery action.
Future decision should provide an explicit bounded retry or correct the stated recovery behavior, retaining protection against an unbounded request loop.


### Complete-review checkpoint — reviewer-batch-3

#### reviewer-F021 — P2, source defect: advertised custom documentation paths lose their package owner

`docs/generate_tool_package_docs.py:96–102,107–143` accepts external `BIOIMAGEFLOW_DOC_PACKAGE_PATHS` and configured documentation roots.
But tool/workflow child wrappers call `include_page(source)` without their known output/package context (`223–227,270–287`).
`generated_wrapper_for_source` requires an ancestor whose parent is the repository's internal `PACKAGES_DIR` and then hardcodes `package_dir / "docs"`.
An opted-in external package with local detail pages therefore reaches `StopIteration`; an internal package using another declared documentation root can reach `ValueError`.
The error formatter for an invalid external index also assumes `package.index.relative_to(ROOT)` (`201–209`), replacing a useful diagnostic with another path exception.
`how-to/custom_tool_package.rst:83–95,137–146` explicitly advertises these local custom-package capabilities; URL-only external packages intentionally skip local inclusion and are a separate supported path.
No generator was executed and no existing first-party page failure is claimed.
After the audit, carry the discovered package/docs/output owner into child wrapper generation and make error paths work outside the repository, preserving custom local documentation and the no-tool-import build boundary.
The completed shared development tests cover package-doc navigation but do not distinguish an external local package or a nondefault docs root; reuse those oracles for the actual promised variants later.

#### reviewer-F022 — P3, source metadata defect: the documentation generator parses TOML as stripped text

`read_docs_metadata:147–173` strips text after every `#` before parsing strings and supports only a subset of double-quoted scalars.
A valid quoted title or URL fragment can be truncated; single-quoted TOML strings retain quotes and escaped basic strings are not decoded.
The public custom-package guide presents `[tool.bioimageflow.docs]` as ordinary TOML, without such syntax restrictions.
None of the eleven current first-party manifests declares this table, so this is a documented custom-metadata boundary, not a demonstrated first-party build failure.
After review, use the existing workspace's standard TOML parsing authority rather than a second partial parser, retaining fail-closed malformed metadata and the lightweight no-package-import producer.
The existing shared development test lacks quoted-fragment, literal-string and nondefault-root distinctions.

#### reviewer-F023 — P4, generated-output maintenance candidate: obsolete owned wrappers are outside the generator's check

`write_pages:294–297` writes only newly expected paths, and `check_pages:300–312` compares only those paths.
Removing or renaming a source page leaves its previously generated wrapper outside both operations' checks.
Sphinx may still identify a broken include, but the generator's freshness check cannot identify that owned orphan.
No obsolete file is claimed from this inspection and no generated-wrapper classification credit is taken yet.
If cleanup is introduced after the full review, scope it to explicitly owned generated headers/output paths and preserve human pages, package sources and custom-build navigation; do not broadly delete documentation.

#### reviewer-F024 — P3, developer configuration defect: debugger and type-path examples retain an obsolete directory spelling

`.vscode/launch.json:14` launches nonexistent `example-workflows/fish_analysis/workflow.py`; the actual tracked entry point is `example_workflows/fish_analysis/workflow.py`.
`pyrightconfig.json:34` repeats the nonexistent hyphenated directory.
The same extra-path list omits the current phasor package, although packages are generally included and the environment may resolve its installed distribution; no type-check failure is inferred from that omission.
After review, correct the dead debug/path references and align maintained package paths only where needed, without changing Python/runtime compatibility.

#### reviewer-F025 — P3, architecture guard/oracle limit: eager nested module imports evade top-level checks

`scripts/check_import_boundaries.py:66–70` implements `top_level_only` using only immediate `tree.body` import nodes.
An import in an eager module-level conditional or class body is executed during module import but is invisible to the Core and production-Parsl rules.
`reference/platform_development.md:28–30` states the worker-safe module-import boundary, and the existing shared development tests distinguish direct module imports from legitimate function-lazy imports, but not eager nested module contexts.
This is a guard limitation; no current forbidden conditional import or runtime break is claimed.
A later refinement must preserve legitimate lazy functions and nonexecuted typing guards, rather than replacing the scan with an indiscriminate recursive ban.
Keep dependency direction and the existing focused guard/test authority; no generic import-system redesign is proposed.

#### reviewer-F026 — P3, reference contract drift: the error catalogue overstates converters and omits an implemented kind

`reference/errors.rst:52–100` calls its table the full `ValidationErrorKind` set but omits `environment_incompatible`, present in `validation/models.py:18–30`, generated by `workflow/inspection.py:263–267` and specified in `docs/source/specs.md:389,2614`.
The sentence at `errors.rst:105–108` promises every listed domain exception has `to_validation_error`; actual `engine/common.py:356–378` and Core `environment.py:109–111` lack that method, while the four node exceptions provide it.
The existing normative sentence at `specs.md:2625` has the same overbroad converter wording and is handed to B's specification ownership rather than silently narrowing the feature.
The errors page's `/gui/planning_and_cache` link (`155`) resolves to the existing counterpart owned by B; absence from this reviewer's assignment list is not absence from the repository.
After the audit, make the curated catalogue exhaustive for implemented kinds and explicitly distinguish converter-bearing exceptions from execution/planning exceptions; retain cycle aggregate validation and public plan refusal.
The inspected validation implementation continues after cycle detection (`inspection.py:204–216`), matching that aggregate obligation.
The exact public planning exception remains a cross-owner trace: an internal engine graph helper raises `RuntimeError`, but that helper alone does not prove the public `Workflow.plan` contract is wrong.
This is reference/source reconciliation, not an executed planning failure or authorization to weaken stable kind semantics.

#### reviewer-F027 — P2, campaign applicability candidate: exact exclusions also encompass local retained-run obligations

B's complete runtime-test review identified the module-wide `campaign_excluded(reason="distributed-engine")` in `test_execution_runtime.py:36`.
The actual campaign auditor removes every marked identity, and the manifest explicitly includes local attached/direct/Wetlands cases (`campaign-local-scope.json:253–329,397–398`).
Targeted counterpart inspection confirms `test_regular_terminal_sidecar_recovers_failure_and_cancellation[failed-direct/cancelled-wetlands]` exercises an actual local `ExecutionManager` completion path and durable recovery (`test_execution_runtime.py:883–944`), while `test_direct_and_wetlands_managed_export_is_released_and_downloadable` exercises retained local export ownership and tamper refusal (`1387–1427`).
Those assertions are not all parallel scheduling or actual managed remote submission.
At the same time, they share the retained execution/coordinator schema intentionally designed for multiple backends; a mixed module may have a deliberate exclusion rationale.
Thus this requires explicit per-test local applicability adjudication after the complete source/spec review, not an automatic demand to run the entire distributed module or a claim that ordinary CI omitted these tests.
Preserve actual parallel/Parsl/managed-remote exclusions, historical counts/identities and exact marker-manifest self-audit.
Prefer retaining existing distinguishing local selectors over adding duplicate tests or granting static coverage credit.

#### reviewer-F028 — P4, fail-closed manifest diagnostic limit: malformed reason types bypass the promised controlled error

`load_backend_exclusions:46` and `audit_backend_collection:88` test reason membership in a frozenset without first establishing a string.
An unhashable malformed JSON value or marker reason (for example a list) raises `TypeError` outside the controlled `ValueError` conversion used by collection.
The suite still fails closed, so this is diagnostic robustness rather than scope bypass.
The exact collection tests distinguish duplicate/missing/unmarked/drift/zero-selection cases, but do not cover malformed reason types, malformed marker argument shape, or duplicate collected identities.
If the scope infrastructure changes later, extend those existing negative oracles proportionately and keep exact collection integrity; no new tests are authorized now.


### Complete-review checkpoint — reviewer-batch-4

#### reviewer-F029 — P2, documented wire contract drift: current output is still described as version 1

`gui/wire_format.rst:4–20,40–48` describes `Workflow.to_dict()` as schema-version-1 and exported envelopes as archive-version-1 without viewing metadata.
Actual `workflow/serialization.py:207–208` emits schema-version-2, and explicit archive serialization (`35–58`) emits archive-version-2 with the derived viewing snapshot.
The already reviewed viewer reference and actual loader (`loading.py:335–377`) distinguish strict current v2 envelopes and legacy v1 acceptance.
Thus these examples no longer describe current output, even though the loader continues accepting supported v1 graphs/envelopes.
After the audit, update the curated wire guide from the existing unified workflow contract and current golden fixtures, keeping legacy input compatibility, explicit unknown viewing snapshots, source ownership and strict field validation intact.
This is a documentation finding, not a new runtime red.
The default session's literal v1 graph is handed to A's pending complete session review; that literal alone does not prove incompatibility because the public loader explicitly supports v1.

#### reviewer-F030 — P3, architecture narrative and public reference drift: existing modes are presented as future features

`concepts/architecture.rst:64–66` calls distributed adapters future, and `concepts/tools.rst:64–65` calls row parallelism future, while the current public runtime constructs attached Parsl and the maintained execution/parallel guides describe actual current parallel scheduling.
The architecture's absolute statement that tool authors only import Core (`113–114`) also needs the already documented distinction between worker-safe ProcessingTools and orchestrator DataFrameTools; this is not a reason to move DataFrameTools into Core.
`how-to/run_in_parallel.rst:18` references nonexistent `bioimageflow_core.DataFrameTool`; the actual public class is `bioimageflow.DataFrameTool`.
After review, align these small explanatory statements with current implemented modes and process boundaries, keeping campaign runtime exclusions separate from static source coverage and preserving the lightweight Core dependency direction.
Do not redesign scheduling or broaden the held local campaign merely to reconcile a narrative.

#### reviewer-F031 — P3, host guidance defect: the documented step advancement rule contradicts existing behavior and oracle

`gui/disabled_nodes.rst:74–76` says execute is mandatory before advancing and the engine checks it.
Actual `engine/scheduler.py:270–275,340–345` auto-executes an unexecuted runnable step when iteration advances.
Skipped steps are yielded and then continued without automatic execution (`309–325`), consistent with the same page's worked skip loop.
The existing `tests/integration/test_compute_steps.py::TestAutoExecute::test_auto_executes_when_user_skips_execute` explicitly exercises a real Direct workflow and executes only the final step (`97–116`).
After the audit, correct the explanatory rule to the existing runnable/skipped behavior using that existing assertion; an additional duplicate test is unnecessary.
Keep explicit execution control, skipped-step refusal when invoked, deterministic downstream consistency and iterator cleanup ownership.
No step test was executed by this reviewer.

#### reviewer-F032 — P3, output-template examples: compound stems and explosion indices overpromise automatic filenames

`how-to/output_templating.rst:70–75` predicts `cells_result.ome.tif` for `{image.stem}_result{image.exts}` with `cells.ome.tif`.
The actual resolver uses `Path.stem` (`template.py:125–133`), retaining `.ome` in the stem and separately appending all suffixes; the stated output spelling is inaccurate.
The same guide (`90–103`) suggests an exploding tool automatically gets distinct `0::0`, `0::1` filenames from `{row_index}`.
Actual arguments build templates before processing from the input row index and replace `::` with `_` (`engine/arguments.py:253–268`); the engine cannot know returned child count before that processing call.
This does not establish a product overwrite: tool-side outputs may explicitly create their own distinct paths and the source/output validation owners must assess actual runtime semantics.
After review, clarify input-row versus returned-child index ownership and correct filename examples, preserving explicit owned output paths and the essential one-to-many execution contract.
The existing template resolver tests already distinguish stem/suffix/suffixes; use their actual expected spelling rather than changing the resolver solely to match prose.
An explosion naming promise, if essential, needs public contract adjudication before any implementation change or new oracle.

#### reviewer-F033 — P3, GUI schema reference drift: implemented picker/control distinctions and exception scope are incomplete

`concepts/type_system.rst:201–215` and `gui/tool_schemas.rst:37–69` omit implemented `GUIMeta.path_picker` / serialized `path_picker`, despite Core `types.py:117–159`, serializer `serialization.py:269–285` and normative `specs.md:302,315,1193,1217` documenting the file/folder/both hint.
The hint is rendering only, ignored for non-path fields/Outputs, and must not become filesystem validation.
The schema reference also presents generic connectability without the implemented DataFrameTool input exception: actual serializer documentation/branch describes those inputs as `never` (`219–230,284`).
Its exception advice (`gui/tool_schemas.rst:189–194`) describes serializer failure as `SchemaSerializationError` typically from tool instantiation, while the same page correctly says input serialization does not instantiate the class (`73–76`).
The actual serializers directly inspect normalized IO classes and validate templates; the registry catches arbitrary `Exception` around each schema (`registry.py:278–285`).
The exported `SchemaSerializationError` type alone does not prove that all direct introspection/template faults are translated into it, so consumers following only that catch advice can miss actual failures.
After complete source/spec review, document the actual public exception/normalization boundary or preserve an explicitly required typed failure contract in a bounded implementation packet; do not silently weaken a required guarantee.
Retain unknown/broken tool isolation, annotation-only introspection, input pin policy, path-picker intent and dynamic resolved outputs.
Existing Core picker tests and validation-serialization input/metadata tests are the relevant current oracles; no new test execution or coverage credit is assigned here.


### Complete-review checkpoint — root-batch-5

#### ROOT-F038 — P2 default-state design risk: IOModel instances alias mutable declaration defaults

`bioimageflow_core/tool.py:106–114` assigns getattr(self.__class__, name) directly when a field is omitted.
Two instances using a list/dict/array default therefore share the declaration's object; mutation through one can change another instance and the future default.
The source behavior is direct; no cross-row contamination was executed, and runtime resolution may supply explicit values on some paths.
`TestIOModel.test_default_used` and integration `test_default_values` exercise only immutable scalar defaults.
After full review, define independent instance-default semantics and either copy supported mutable defaults or explicitly refuse them, preserving immutable Template markers and intentional caller-supplied object identity.
Do not add Pydantic or coerce every tool field merely to solve default ownership.

#### ROOT-F039 — P2 recipe-validation defect: operator substrings are treated as exact version pins

`bioimageflow_core/environment.py:51–97` accepts pip exact mode whenever the string contains ==/=== and conda mode whenever it contains allowed equality characters.
A prefix requirement such as numpy==2.* passes allow_flexible_versions=False although it selects multiple versions; malformed equalities can pass declaration validation and fail only at later installation.
[Python's version-specifier contract](https://packaging.python.org/en/latest/specifications/version-specifiers/#version-matching) distinguishes wildcard prefix matching from an exact version.
No recipe was provisioned or declaration failure executed here.
Complete environment tests distinguish bare names/ranges/exact examples and preserve direct/local requirements, but omit wildcard and malformed-equality cases.
After review, validate actual requirement grammar and exact-versus-flexible semantics through one authority, retaining the deliberate direct/local dependency exceptions and supported conda channel syntax.
Core declaration policy and Wetlands runtime translation must remain consistent rather than enforcing only one copied list of strings.

#### ROOT-F040 — P2 version-authority defect: custom preflight comparisons disagree with supported version semantics

`bioimageflow_core/preflight.py:121–180` represents absent dev suffix as -1, so a release candidate with .devN sorts after the same release candidate without .dev; the dev branch precedes post handling, so a postrelease-development version sorts before its underlying final release.
The regex accepts local identifiers but comparison drops their labels, so ==0.4.1+foo can report a 0.4.1+bar candidate compatible.
The [official version ordering/matching specification](https://packaging.python.org/en/latest/specifications/version-specifiers/) requires the contrary distinctions.
No preflight result or cluster execution was produced; current stable-version tests do not demonstrate a live compatibility failure.
`test_probe_reports_incompatible_core_requirement` covers only an unrelated stable version; orchestrator mismatch tests use stable 0.1.7/0.1.8, while the caller's optional exact expected-version guard is retained as mitigation.
After review, reconcile worker/orchestrator version policy with the supported canonical authority; preserve Python 3.9 worker import posture and strict plain-wire constraints.
Do not loosen remote evidence or automatically change package-version floors to conceal a parser mismatch.

#### ROOT-F041 — P2 qualified concurrency risk: staged publication uses one temporary sibling per process

`bioimageflow_core/external.py:209–217` copies to .<final-name>.tmp-<pid>, then replaces and finally unlinks that fixed path.
Two threads targeting the same final file in one process share that temporary path, so one can publish or remove the other's copy and leave the other failing or returning different bytes.
Whether ordinary mapped rows can legitimately share a final target still requires complete output-template/storage ownership review; no race or tool-output corruption is claimed as observed.
`test_run_external_command_with_staged_output_copies_to_final_path` uses one serial fake command and does not distinguish publication ownership.
After the gate, clarify concurrent target policy and use an owned unique temporary sibling if concurrent last-writer publication is supported, retaining same-filesystem atomic replace and cleanup of only owned staging.
A global tool/process lock would need an actual justified contract, not blanket serialization.

#### ROOT-F042 — P2 bounded executable-selection defect: fallback ignores an explicitly supplied PATH

`external.py:56–69` calls shutil.which against the parent process environment before falling back to sys.executable's sibling command, although run_external_command separately accepts and forwards an explicit env.
If the parent PATH lacks the command, the supplied child PATH contains the intended command and an interpreter sibling also exists, the fallback hardcodes the sibling instead of allowing the child's PATH selection.
No subprocess was executed and no current scientific recipe is alleged to use this distinguishing configuration.
`test_subprocess_resolves_cli_next_to_environment_python` forces which=None and checks only default fallback; it has no distinct supplied-PATH case.
Future action is consistent resolution against the actual effective subprocess environment while retaining the useful interpreter-sibling fallback when that environment genuinely lacks the command.
Preserve explicit argv and cwd/env forwarding, not a shell-based workaround.

#### ROOT-F043 — P3 test consolidation candidate: duplicated basic IOModel scenarios provide the same boundary

Unit TestIOModel and integration TestIOModelBasics repeat scalar default/required/unknown/repr behavior, both directly importing Core IOModel and neither exercising orchestrator execution.
Several inherited-field examples also overlap, but integration uniquely checks class-local lazy annotations/metadata, override precedence, inner declarations, Passthrough and interface types.
After the gate, consolidate identical basic cases in the Core unit owner and retain those distinct integration/import/annotation contracts.
This reduces duplicated scenarios rather than replacing independent expected behavior with implementation-derived expectations.
No timing saving was measured and no cases were deleted here.

#### ROOT-F044 — P3 worker-import oracle inventory gap: first-party phasor tools are omitted

`tests/unit/test_worker_safe_tool_imports.py:27–133` enumerates first-party modules and processing exports but contains no bioimageflow_phasor_tools entry.
The fully reviewed package is a ProcessingTool/Core-only module, so its future orchestrator-import regression would escape this subprocess boundary, just as raw-class export classification omits it in A-F031.
Current phasor source is worker-safe by inspected imports; this is an oracle/inventory gap, not an executed bad import.
Future action should reconcile the intended first-party processing inventory with package metadata and extend this existing fresh-process assertion; avoid deriving expected classes solely from the same imports under test.
Retain exclusion of genuinely main-process DataFrame modules, lazy optional models and the explicit orchestrator blocker.

### Cross-owner qualifications at the 374-input checkpoint

A-F053 is downgraded to conditional observer-lifetime debt: the complete caller trace forwards acceptance to the shared nested session store, without directly hydrating an old mounted canvas.
A-F052's production draft acknowledgment is ordinary synchronous store bookkeeping; a callback failure remains an adapter contract question, without demonstrated normal-production reachability.
A-F063 also covers Save's unconditional recovery clear; full mounted editing/cleanup lifetime review remains pending before a data-loss assertion.
Reviewer-F026's planning/cache reference resolves to an existing page; its finding concerns the omitted error kind and overstated converters only.
B-F042 is a missing node Reveal deployment guard, distinct from ROOT-F002's mutable authority at guards which already exist; the complete ImageCell caller renders Reveal in webapp too.
B-F043 reflects the inspected FastAPI/Pydantic response-model path mapping nonfinite values to null, not an executed JSON serialization exception.
The complete ImageCell/NodeDataTable trace corroborates B-F045's omission of captured identity for thumbnails/Avivator/Reveal; B-F049 separately records the configured Fiji action's required-payload mismatch.
No source finding, corroboration or administrative validation above supplies runtime certification or releases the repair gate.

### Complete-review checkpoint — reviewer-batch-5
No additional defect IDs: complete common/measurement documentation retained scientific, ownership and refusal contracts; targeted implementation traces receive no duplicate full-file credit.

### Complete-review checkpoint — A-batch-9

#### A-F072 — Medium/High potential impact, explicit stale root owner generation is ignored on Open

nested_workflow_snapshot.py:767–782 canonicalizes an incoming root owner to the current workflow generation without comparing an explicitly supplied owner.identity_generation.
A delayed open request carrying old graph/generation can therefore become a new private session owned by the recreated current root instead of refusing its stale incarnation.
This is an adjacent concrete boundary to canonical A-F004's missing draft/save wire incarnation; supplying the generation alone would not currently fix this Open path.
After canonicalization the rest of validation/commit checks preserve the captured current generation correctly, so the gap is at admission, not every subsequent CAS operation.
No delayed request/recreation was executed.
`test_open_is_idempotent_and_root_owners_do_not_collide` and route open tests omit an explicit expected generation; generation/move router tests from batch2 exercise later ownership transitions, not stale requested admission.
Retain compatibility for truly generation-less legacy callers where permitted, immutable private session identity and root generation commit checks; future action should distinguish absent legacy ownership from an explicitly stale captured owner.

#### A-F073 — Medium, deletion durability asymmetry

nested_workflow_snapshot.py:389 direct DELETE,430 root-tree cleanup and661 orphan cleanup unlink snapshot records without fsync of the snapshot directory.
Write publication explicitly fsyncs the directory at1059, and move-root deletion does so at533–537 before the move journal can clear.
Ordinary acknowledged deletion therefore has weaker power-loss durability than acknowledged writes/move deletion and may permit removed directory entries to return after a crash.
No crash/power-loss failure was executed; ordinary process/service restart tests cannot distinguish this filesystem durability boundary.
`test_replace_and_delete_are_revision_checked` and depth-two ordered close assert current file absence; they do not assert directory sync on the separate deletion paths.
Filesystem helper/platform-specific policy is B-owned and must be reconciled before repair priority is finalized.
Retain revision/dependent checks and idempotent root-tree cleanup; future action should apply the documented durable acknowledgment policy consistently at unlink commit.

#### A-F074 — Medium qualified integrity risk, ordinary read lacks filename/body session identity check

Inventory scan:821–840 rejects a body session_id that differs from the UUID filename, but _read:1015–1025 returns _read_path without comparing that body's ID to the requested session.
A syntactically valid mismatched record introduced after startup can be returned through GET A as session B; PUT uses current.session_id at353 and can write the accepted replacement into B's path rather than refusing corrupted authority.
Normal service writes create matching UUID/body paths and startup cleanup rejects mismatch, so this is a corrupt/external filesystem state path rather than a normal API identity change.
No corrupted record was created during audit.
Complete service/router counterparts cover matching persisted records/restart only; move-recovery/cleanup integrity tests remain pending, so no claim that all integrity tests omit it.
Retain strict model validation and startup inventory classification; future action should enforce the same path/body agreement for ordinary targeted reads before mutation.

#### A-F075 — Low/Medium, unrelated malformed snapshot can block targeted open/delete scans

_find_snapshot:866–877 and _dependent_session_ids:921–932 call _read_path for every *.json without the tolerant classification used by _inventory_locked.
A malformed unrelated JSON record after startup can therefore fail opening a different owner or deleting a child without dependents, rather than isolating/refusing only the unreadable authority concerned.
Startup cleanup handles preexisting corruption, and refusing destructive operations in uncertainty can be intentional; this finding concerns the inconsistent targeted read/availability policy, not permission to silently delete an unreadable dependent.
No malformed record was written or request executed.
Complete current counterparts cover valid unrelated records and known dependent refusal; full recovery fault/inventory counterparts remain pending.
Retain fail-closed dependent ownership when unreadable data might matter; future action should define which corruption can be safely isolated and reuse one inventory classification rather than raw all-file parse.

#### A-F076 — Medium potential impact, staging cleanup can prevent attempted rollback of already replaced snapshots

_write_many:1062–1078 calls _remove_staged_files before iterating replaced paths for rollback.
_remove_staged_files:1136–1141 catches only FileNotFoundError; another unlink error can escape immediately and skip rollback of an already published earlier file in a multi-file replacement.
The final cleanup can likewise override a primary/rollback failure message.
A durable outer workflow move journal may retain/recover the partially rewritten operation, which is an essential mitigation pending full recovery-service/fault counterpart review.
No injected failure or partial move was executed.
The complete simple snapshot service/router tests do not inject cleanup/replace/fsync failures; batch2 workflow router faults cover outer move failure but are not an oracle for cleanup-before-rollback sequencing.
Retain durable staged writes and reverse restoration; future action should prioritize restorative work over ancillary temp cleanup and preserve meaningful failure evidence without weakening the outer journal.


### Complete-review checkpoint — A-batch-10

#### A-F077 — Low/Medium, advertised partial document rewrite fault does not isolate that boundary

`test_workflow_folder_move_recovery.py::test_folder_rename_recovers_second_workflow_after_first_document_rewrite` captures original_rewrite and calls it before checking whether old_id is project/b (lines204–212).
The injected failure therefore occurs after the second document rewrite, not between the first and second; the subsequent assertion explicitly observes archive/b's rewritten draft identity.
This is useful recovery after completed artifact writes but before later phase acknowledgment, yet its name/intended partial-first-document claim is stronger than its actual fault oracle.
The first folder test stops before any artifact rewrite, so these two tests do not isolate an interruption with exactly one of two workflow documents rewritten.
No fault/test was executed during audit, and there is no claim the production recovery fails that missing distinction.
Retain completed-artifact idempotence and before-any failure coverage; future test maintenance should label the actual boundary and, if required by the full transaction contract, place an existing fault hook before the second rewrite instead of adding a duplicate journey blindly.

#### A-F078 — Low/Medium, extra-field journal refusal fixture has confounding missing fields

`test_workflow_move_recovery.py::test_corrupt_or_extra_field_journal_is_rejected_without_mutation` writes only journal_version and unexpected=true (lines467–478).
The journal lacks required operation ID/kind/source/destination/moves, so it fails even if a future parser ignored extra fields; this fixture cannot specifically distinguish strict extra-field rejection.
The full B-owned model currently sets extra='forbid', so no current acceptance defect is claimed.
The test still usefully proves an untrustworthy incomplete journal prevents mutation and preserves the existing workflow.
Retain that corrupt-journal/no-mutation oracle; future test maintenance can derive a complete valid prepared journal and add an extra key if strict unknown-field rejection is a required independent distinction.
No new test or execution is authorized by this audit finding.


### Complete-review checkpoint — B-batch-7

#### B-F059 — P2 source defect/test oracle: abandoned eager step reservations are not released

`workflow/runtime.py:46–88,371–429` reserves the original Workflow before returning _WorkflowSteps; only wrapper exhaustion/error/explicit close calls _end_public_execution.
`scheduler.py:43–86,265–278` similarly reserves DefaultEngine before returning _EngineSteps; only wrapper methods release it and invoke owned backend cleanup.
Neither wrapper has context-manager/finalizer behavior, and dropping an unstarted inner generator cannot run its body/finally.
For a started workflow iterator, generator close can finalize its run/inner iterator but does not call the outer wrapper's _release; the original Workflow remains admitted unless explicit wrapper close/exhaustion occurs.
Thus temporary `for step in wf.compute_steps(...): break` does not establish reusable original Workflow admission, and dropping a never-started execute_steps iterator strands the original engine active flag.
This is source behavior, not an executed leak/PID observation; explicitly retained iterators may intentionally require explicit close.
`tests/unit/test_workflow_execution_context.py::test_steps_reserve_workflow_before_first_iteration` and `::test_engine_steps_reserve_engine_before_first_iteration` correctly verify eager exclusion and explicit-close release.
Borrowed `tests/integration/test_compute_steps.py::TestComputeStepsPartialIteration::test_early_break_does_not_leak` creates a different Workflow/engine afterward; the second test has no ownership oracle, so neither distinguishes release of the original owner.
Future diagnostic should reuse the exact original owners after never-started abandonment and after a started early break, preserve eager exclusion and deterministic explicit close, and establish/document an iterator lifetime contract before choosing cleanup behavior.

#### B-F060 — P2 source defect/authority: root compute wrappers lose per-environment launch overrides

`workflow/runtime.py:312–329,446–463` builds execution parents for compute(inputs=...) or no explicit targets and copies workflow-wide max_workers/wetlands_config but omits _env_configs.
A-complete `workflow/interfaces.py:372–408` structural snapshots also omit the per-environment configuration map.
`engine/dispatch.py:181–199` consults only the actual executing root workflow._env_configs to choose max_workers and worker_timeout.
Consequently `wf.get_environment(env).max_workers`/worker_timeout overrides that are effective for compute(explicit_node) are absent on the no-target/root-input wrapper path, using workflow defaults instead; captured child configuration is also not a runtime authority in the current scheduler.
This is not a demand to inherit every nested child's independent runtime: root execution policy may deliberately own all nested launch settings.
The root workflow's own override loss is a narrower inconsistency requiring a contract decision and distinguishing tests.
B1 `test_workflow_public_factory_preserves_configuration` checks global defaults only; full execution context root-wrapper test checks exact run context only, not launch overrides.
Future diagnostic should use an injected tracking public manager with explicit/no-target/input wrapper paths and distinguish root policy from child captured policy without provisioning or broad coordinator changes.

#### B-F061 — P2 source defect: prepare can launch a skipped ProcessingTool environment

`engine/common.py:606–631` returns False for skipped cached, then prepare calls backend.prepare_node without checking skipped.
Borrowed full `backends.py:110–131` WetlandsBackend.prepare_node resolves the ProcessingTool and get_or_create regardless of enablement.
`scheduler.py:295–317` intentionally yields skipped NodeStep objects, and execute correctly refuses them with DisabledNodeError.
A caller that prepares each yielded step before testing skipped can therefore provision/start workers for a disabled or blocked node despite no processing execution.
This is a source side-effect gap, not a claim that disabled process_row runs.
Borrowed complete TestPrepare cases exercise only enabled tools/direct mode; the documented disabled loop deliberately avoids execute but preparation refusal/no-op is not distinguished in those tests.
Future diagnostic must assert zero public manager calls for skipped prepare and retain cached/active preparation behavior and explicit disabled execute refusal.

#### B-F062 — P2 source candidate: disabled dependencies participate in environment mismatch admission

`engine/graph.py:129–161` collects all reached ProcessingTools without filtering disabled or downstream-blocked nodes.
`scheduler.py:289–298,363–384` performs that mismatch check before _filter_executable.
An enabled branch sharing an environment name with a disabled conflicting branch is refused before the scheduler can skip the disabled branch.
The current mismatch test requires both enabled tools, so it establishes legitimate conflict detection but does not decide whether disabled definitions should block an otherwise executable run.
Record as a behavior/contract candidate, not an executed disabled workflow failure or automatic removal of environment validation.
Future diagnostic should cover disabled node and disabled ancestor separately, retain conflicts between executable tools, and reconcile with validate/plan diagnostics.
Different Core flexibility/prerelease flags with the same dependencies are not automatically different runtime recipes: those flags authorize declarations, and translating the same accepted requirements to the same Wetlands recipe can be correct.

#### B-F063 — P2 source-risk: close can retire engine-owned pools during an active execution

`scheduler.py:233–243` holds the lifecycle lock and marks closed but never rejects or coordinates _execution_active before backend.close.
Execution holds the lock only at begin/end, and borrowed WetlandsBackend.close shuts down engine-owned managers immediately.
A separate caller can therefore close an engine with active tasks or a live stepped iterator; ownership is scoped correctly, but physical completion/cancellation admission is not coordinated by this lock.
External managers are expressly retained and are not implicated in this retirement path.
Full lifecycle tests cover sequential close after success/failure/cancellation and idempotence, with no concurrent active-close oracle.
This is unexecuted source risk; define supported close-during-execution semantics before introducing any coordination, preserving external ownership and normal finally cleanup.

#### B-F064 — P2 source-risk: start-run metadata failure leaves a bound running context

`workflow/runtime.py:530–584` calls run_context._bind then writes run-view fields and invokes Storage.start_run_metadata.
Both compute and stepped execution call _start_run_view outside their inner exception-to-_execution_failed handling (`350–366,479–499`).
If metadata creation fails after binding, eager Workflow admission is released, but the supplied public context remains running/bound without a terminal outcome and _run_view_context can remain populated.
A caller cannot reuse that single-use context or infer success/failure from terminal_status; subsequent manual finalize may itself fail if canonical run metadata was not created.
This is a fault-path source risk, not an observed filesystem failure or a request to make contexts reusable.
Full context tests distinguish deferred success and pre-requested cancellation, but not metadata start failure before engine.execute.
Future fault injection should verify context outcome, run-view clearing and absence of tool execution, preserving exact single-use binding, launcher reservation and deferred success semantics.


### Complete-review checkpoint — reviewer-batch-6

No new findings: exactly26 wrappers classified against the complete generator/header/include/toctree consumers and27 full human common/measurement authorities; all current hashes match.


### Complete-review checkpoint — reviewer-batch-7

#### reviewer-F034 — P4, output description ambiguity: selection removes an axis, not the selected data

`io-tools/docs/tools/select_channel.md:14` says the output has the selected channel removed, and `select_timepoint.md:14` says the selected timepoint is removed.
The actual shared selection owner returns the selected data and removes the selected axis from the remaining-axis declaration (`_axes.py:49–71`).
Their own later expected-result sections describe that actual behavior correctly.
After review, make these two short output descriptions agree with the existing selected-data/remaining-axes contract; preserve explicit selection and refusal semantics, and use existing slicing assertions rather than adding duplicate tests.
No pixel selection defect is asserted.

#### reviewer-F035 — P3, public tool documentation completeness: thin specialist pages omit essential configuration/failure contracts

All five phasor tool pages contain only three to six lines; the LapTrack tool page contains eleven.
They state useful high-level scientific meaning but omit a minimal configured workflow, explicit public input/output names and key failure/refusal requirements expected by the already reviewed package-author guide (`how-to/custom_tool_package.rst:76–80`).
The actual public inputs include acquisition dataset/channel/frame/detector-time/harmonic selection, `reference_lifetime_ns` and reference-center policy, median/intensity bounds, and LapTrack's `max_link_distance`, `gap_closing_distance`, `gap_closing_max_frames` and `division_distance`.
The actual source additionally validates positive finite metadata/constraints, matching calibration frequency/harmonic, ordered intensity bounds, source-specific object identity and shared batch parameters; those are essential existing behaviors rather than prospective feature expansion.
After the audit, fill those exact omissions from already implemented schemas, current workflow examples and existing package contract/runtime selectors.
Keep scientific units, acquisition versus exchange provenance, source isolation, pinned runtime gating, actual external skips and current merge exclusion explicit; do not add generic prose, duplicate long package manuals or claim a mock contract test proves the scientific backend.
This is a documentation completeness finding, not a request for new code/tests or permission to execute a native model/runtime now.


### Complete-review checkpoint — reviewer-batch-8

No new findings: exactly27 IO/phasor/tracking wrappers classified individually against the complete producer, human batch7 authorities, headers/includes/relative-docs/toctrees and matching hashes.


### Complete-review checkpoint — root-batch-6

#### ROOT-F045 — P2 protocol robustness defect: syntactically valid wrong-shaped JSON escapes structured errors

agent_mcp.py:788–822 validates response JSON syntax but not successful body shape.
Draft callers immediately use .get or draft['draft_revision']; list/tool callers iterate bodies and invoke mapping helpers; _operation_result:1211 likewise assumes a mapping.
A scalar/list successful draft/operation response or a mapping instead of a tool list therefore raises a raw TypeError/AttributeError rather than the declared malformed_backend_response result.
Normal FastAPI response models produce expected shapes, so no normal-server failure or executed malformed response is claimed.
The complete MCP test file checks missing state and positive mock bodies but has no malformed JSON/shape/HTTP-conflict transport oracle.
After the review, validate the minimal expected envelope at the transport/operation boundary and reuse focused negative transport cases, keeping exact structured backend errors and recursive public payloads rather than reimplementing all graph validation in the gateway.

#### ROOT-F046 — P2 qualified consistency risk: one logical operation rereads connection state between stages

_apply_operations:762–777 captures AgentState, fetches a draft when expected_revision is omitted, then posts using the captured workflow ID; _request:795–799 rereads AgentState separately to choose api_base_url for each HTTP call.
run_workflow likewise captures the workflow ID before the draft read and a fresh request-state lookup for Run.
If the state file's backend connection changes between awaits, one operation can combine a revision/target captured from one connection with another connection's base URL.
Ordinary active-workflow changes keep the base URL and captured workflow target, which is a useful mitigation; no actual backend switch/race or cross-workspace operation was executed.
This is separate from canonical A-F020's global context publication: request routing itself lacks an immutable per-operation connection snapshot.
After complete workspace/lifecycle synthesis, decide whether the supported reconnection contract needs captured URL/server identity through the entire operation; retain CAS and do not blindly retry a write against a new backend.

#### ROOT-F047 — P3 source-reference drift: existing/partial targets are treated as available without refresh/provenance

agent_workspace_context.py:52–56 treats any existing platform-source path as the reference, sanitizes it and marks it available without verifying a completed checkout or its source revision.
In the normal app call ensure_agent_workspace_context(workspace_path), source_root is None, so the existing-target branch passes None into _sync_agent_docs and does not rediscover the current checkout.
A later launch after source/docs changes therefore preserves the old reference; a failed clone leaving a partial target also satisfies target.exists and can be advertised available.
This does not change running application imports, and an explicitly supplied source_root refreshes agent docs; no actual stale or partial clone was created here.
The complete failure test raises before creating a target, while successful/existing reference assertions do not distinguish partial-clone status or default-call upgrades.
After the gate, record and check reference provenance/completeness and choose a bounded refresh policy, preserving best-effort startup and never deleting unowned existing directories merely to refresh context.

#### ROOT-F048 — P2 MCP example drift: positional connection and generated recommendations use obsolete names

Fully reviewed docs/agents/api-reference.md:230–237 sends positional_index to connect_nodes, while both the registered MCP signature and gateway implementation accept target_position (agent_mcp.py:628–648,1140–1156).
The same stale positional spelling is present in the targeted workflow-editing.md:95 counterpart, whose full document review remains with the shared reviewer.
WorkflowDraftService.write_agent_context:550–557 still emits recommended create_node/update_node_parameters and create_node operation names; the actual public inventory uses create_tool_node/update_tool_parameters and typed recursive variants.
The complete workspace documentation test bans obsolete tool/type names in three curated docs/template but never checks generated recommended_commands, and its layout-name checks do not validate argument names.
No MCP call or validation exception was executed; static signatures and the published example are incompatible.
After the audit, reconcile curated examples and generated runtime recommendations with the same maintained MCP contract, retaining recursive workflow operations and user-facing concise guidance; use existing focused contract assertions rather than adding broad repeated workflow journeys.

#### ROOT-F049 — P3 qualified artifact-ownership decision: custom root instructions are overwritten unconditionally

ensure_agent_workspace_context:39 and WorkflowDraftService.write_agent_context:570 replace workspace-root AGENTS.md without checking its existing owner/header or preserving a user section.
Hidden custom AGENTS.md is explicitly preserved by _remove_generated_hidden_instructions and its whole test, but that oracle does not cover the root file.
The public MCP guide explicitly identifies root AGENTS.md as generated workspace context, so replacement may be intentional policy rather than an implementation violation.
A preexisting custom workspace instruction file nevertheless has no demonstrated coexistence/admission contract in the inspected producer/tests; no user file was overwritten during this audit.
After reviewing onboarding/normative workspace ownership, either specify reserved generated ownership clearly or preserve separately owned instructions through an explicit supported mechanism; do not suppress the required MCP workflow controls or modify arbitrary instructions silently.


### Complete-review checkpoint — root-batch-7

#### ROOT-F050 — P2 qualified layout contract gap: Mosaic reads only the initial frame

mosaic.py:48–55 declares scalar image semantics without restricting layout; process_batch:112–115 loads/copies the initial Pillow frame without seek/n_frames selection or multiframe refusal.
A multi-page volume/channel/time TIFF therefore contributes its initial frame to the montage, with no explicit selected-plane policy in the complete source/guide.
This is source behavior and a contract question, not an executed pixel-loss result or a demand that QC montage preserve every volume dimension.
Full common-workflow tests cover planar grayscale/RGB/RGBA/palette behavior; the multi-channel TIFF fixture is used only by Files.
After axis/schema synthesis, specify supported geometry and explicit selection/refusal/annotation while preserving current image-count, row mapping, UInt16, color and alpha behavior.

#### ROOT-F051 — P3 qualified schema-policy debt: Concat retains first branch metadata for same-type columns

merge.py:307–315 degrades a shared entry only for a different top-level type; same-type entries retain the first image_spec/viewer/default verbatim.
The existing integration test_concat_same_type_keeps_first intentionally establishes this scalar/default policy; Path rows from multiple image semantic/layout declarations need a separate compatibility decision.
Node.get_output_schema delegates to this owner, and A's complete schema authority family remains pending.
Concat guidance expects compatible/equivalent rows, so this may be a caller precondition rather than a source violation; no bad admission/viewer was executed.
After the full contract review, decide whether incompatible image/viewer metadata requires refusal or conservative unknown metadata while retaining current scalar first-wins policy unless deliberately changed.
Use existing merge schema oracles if this distinction is required; no new broad suite is authorized.

#### ROOT-F052 — P2 qualified side-effect/cache contract gap: cached WriteTable does not recreate its destination

table.py:163–167 writes Inputs.path then returns only a passthrough table; the destination is not a declared owned Path output.
B's full node_execution/dataframe/cache trace confirms valid DataFrameTool cache hits return before merge/transform, and publication supplies outputs=[] without independently checking Inputs.path destination existence/content.
A deleted destination can therefore remain absent after an otherwise-valid cache hit while the guide still describes a written output table.
This is a traced source path, not an executed lost file; explicit external side-effect rematerialization remains a tool/cache contract decision.
Full WriteTable tests call transform once and check CSV/TSV bytes; they do not distinguish subsequent cache reuse after destination removal.
After cache/storage/spec synthesis, define destination ownership and cache-validity semantics, preserving arbitrary explicitly selected CSV/TSV destinations and passthrough behavior; do not take externally authored files into owned-cache deletion silently.
A single existing tool/cache oracle should own any required distinction instead of repeated successful E2E table journeys.

### Complete-review checkpoint — A-batch-11

#### A-F079 — Medium/High, source defect: move recovery omits interrupted global provenance rewriting

Normal direct move calls _rewrite_moved_source_provenance at2971; folder/promotion use _rewrite_moved_workflows1173–1178, which invokes the same operation.
That helper at1199–1239 rewrites workspace source IDs in every saved workflow, draft and private nested snapshot, not merely the moved workflow.
Forward recovery _recover_workflow_move_documents1028–1050 restores moved document metadata/display and draft path identity but never repeats this global provenance rewrite.
The full recovery coordinator then moves snapshot root owners and favorites; complete move_root_workflows changes owner fields only, not embedded graph source IDs.
A committed interruption before or partway through global provenance writes can therefore finish and clear the durable move journal with source references still naming the old ID.
Embedded definitions remain authoritative, so this is not a claim that ordinary execution loses graph bytes; source refresh/provenance/containment behavior and explicit source navigation can become stale.
test_move_rewrites_saved_workspace_provenance_without_changing_hash proves the ordinary path; existing direct/folder recovery tests prove moved artifacts/owners/results but do not inspect an unrelated parent's interrupted saved/draft/snapshot provenance.
No fault was executed in this audit.
Retain exact mapping, embedded content and artifact-hash invariants; future repair must make the whole existing provenance effect forward-idempotent without silently adding another source authority.

#### A-F080 — Medium, durability source risk: archive/source/copy publication has weaker directory ordering than templates/saved writes

Archive import1693–1726 fsyncs workflow.json then renames the staging directory and fsyncs its destination parent, but does not fsync the staging directory containing the newly created workflow.json before publication.
OwnedWorkflowSources.stage/publish writes and fsyncs source files but publish performs atomic replacements without reaffirming affected directories; newly created nested source/package directories are not flushed through a durable parent chain.
Duplicate2925–2942 fsyncs staging after source publication and copytree, but recursively copied editable tools and nested source directories/files do not share the stronger explicit durability treatment used by templates2650–2677.
Archive/copy parent creation also uses mkdir rather than the store's durable parent-chain helper.
Ordinary successful restart and current copy isolation tests cannot distinguish OS power-loss ordering; no power failure, missing file or byte loss was reproduced.
Retain staging, exact source verification, owned-byte isolation and atomic destination publication; future policy must define the promised durability level consistently before adding fault tests or claiming transaction survival.
This is related to A-F073 deletion durability but a separate publication boundary.

#### A-F081 — Low/Medium, exceptional cleanup defect: current template staging is untracked until preparation finishes

install_workflow_templates2643 creates staging and writes workflow.json/tools before adding the directory to prepared2677.
An invalid tool filename or write/fsync failure before that append enters cleanup, which removes only prepared and published directories; the current staging directory is retained.
The advertised atomic multi-template install still avoids publishing its intended destination, but can leave hidden temporary directories containing a canonical workflow.json and prevent parent/root cleanup.
Nested temporary paths are particularly relevant because list_workflows excludes names beginning with a dot, rather than every dot-prefixed path segment; workflow_tree also inventories plain directories.
No failed template install was executed; full demo/template tests remain pending, and trusted bundled inputs mitigate invalid-filename likelihood without covering operational write failures.
Retain all-or-nothing intended destination publication and existing generation reservations; future cleanup should track the current stage before fallible preparation and distinguish incomplete temporary artifacts from user workflow identities.

#### A-F082 — Medium/High, qualified concurrency risk: format migration does not join draft/snapshot mutation boundaries

apply_workflow_format_migrations1994 acquires only workflow_structure_mutation; recover_workflow_format_migration2101 does likewise.
Target application2189–2258 checks current byte digest and later calls atomic _write_schema_v2_json without holding each workflow identity lock or the nested snapshot mutation lock used by ordinary editing writes.
The complete HTTP format-migration route348–362 supplies no snapshot/identity/execution boundary itself.
Pending-format guards block ordinary editable access to affected workflows after the preview sees a pending plan, which materially mitigates new root requests.
They do not establish that a previously admitted draft write or separately locked nested snapshot write cannot commit between the digest read and migration replacement, nor that an old admitted writer cannot later overwrite the migrated state.
The global structure lock serializes moves, not every saved/draft/snapshot write; test_workflow_mutation_serialization covers save/delete/move, not migration-versus-write.
Full schema-format tests remain pending; no controlled concurrent schedule or data loss was executed.
Retain stale-plan refusal, backups, forward journal and canonical target validation; future authority decision must coordinate admitted physical writers rather than merely add a GUI wait.

#### A-F083 — Medium/High, source deadlock risk: containment validation recursively acquires identities outside sorted multi-lock admission

save_workflow2757 is identity-locked for its destination and calls validate_containment1551, whose resolve_saved_graph invokes identity-locked get_workflow for source IDs.
B-owned complete containment walker44 follows the saved source while the original destination lock remains held.
Concurrent saves of A referencing B and B referencing A can therefore hold A→waitB and B→waitA despite the store's sorted workflow_mutations primitive.
Even when existing saved graphs are empty and eventual source-cycle refusal is required, the lock inversion can occur before that traversal finishes.
The service uses RLocks, which support same-thread recursion but do not resolve this cross-thread cycle.
test_direct_and_transitive_source_containment_cycles_are_rejected is sequential; existing mutation tests do not distinguish a two-workflow containment schedule.
No concurrent diagnostic ran during the audit; this is an exact source risk, not observed hung production.
Retain transitive cycle refusal and missing-source embedded authority; future design must provide a coherent containment snapshot/admission order without replacing public graph semantics.

#### A-F084 — Medium, source availability risk: global migration preview can fail on one missing owned source

_plan_schema_v2_workflows1830–1835 and1901 collect owned sources for migration candidates outside the per-document parse/validation error handling.
OwnedWorkflowSources.collect_for_graph/read raises when an owned manifest/file is missing or invalid.
The planner is called by list_workflows1727, workflow_format_status2261 and ensure_workflow_format_current2294; an unrelated malformed schema-v1 candidate can therefore abort a workspace-wide list/status or editable access to another current workflow instead of becoming an isolated format notice.
Invalid JSON/model documents are deliberately hidden/reported per file, making this source-error asymmetry observable in control flow.
No corrupt-source fixture was executed; full schema-migration/format/source-registry counterparts remain pending and may refine intended fail-closed policy.
Retain refusal to manufacture missing source bytes and preserve explicit notices; future diagnosis should distinguish protecting the affected workflow from blocking unrelated identities.


### Complete-review checkpoint — A-batch-12

#### A-F085 — Low, test-oracle naming gap: distinct layout points do not establish nonoverlapping node rectangles

test_bundled_graphs_flow_left_to_right_without_overlapping_nodes57–73 asserts unique position tuples and increasing source/target x positions.
Two differently positioned nodes can still have overlapping rendered rectangles, especially if label/tool-specific size varies.
The first half of the test name is established; the nonoverlap wording overstates this point-only oracle.
No actual demo overlap was observed or renderer run, and no source-layout defect is claimed.
Retain recursive schema/layer direction and distinct positions; future maintenance should describe the actual geometric guarantee or use the existing layout dimensions/renderer boundary if full rectangle separation is a required contract.
Do not add broad GUI repetition merely to satisfy a misleading title.

#### A-F086 — Medium, source/test authority risk: legacy conversion promotes invalid accepted draft validation without semantic validation

B-owned normalize_legacy_workflow_draft293–305 replaces the old draft validation with valid=True/errors=[] while preserving old node_statuses, without calling graph semantic validation.
The complete owned test_migrates_legacy_workflow_and_dirty_draft_with_backups explicitly starts with valid=False and expects valid=True after migration; it uses an ExampleTool identity in an otherwise empty registry and does not distinguish converted structure from executable semantic acceptance.
Complete A draft service GET299–312 calls _read_projected_draft; its read-time projection retains accepted non-cache errors and adds only projected cache_corrupt errors at663–670, so cleared semantic errors are not generally reconstructed by reading the migrated draft.
get_draft_snapshot likewise returns the accepted persisted validation rather than rerunning full semantic validation.
This can present converted invalid or unresolved graph state as accepted-valid and can retain failed node statuses beside valid=True.
Execution compilation/validation remains a separate admission authority, so this is not a claim of unvalidated compute or observed scientific output corruption.
No migration/runtime diagnostic ran in this audit; B received the implementation/consumer seam.
Retain lossless graph conversion, original backups and refusal to guess unsupported interfaces; future authority choice should explicitly distinguish migrated structural acceptance from semantic validation and adjust the existing oracle accordingly.


### Complete-review checkpoint — A-batch-13

#### A-F087 — Medium/High, qualified source-update ownership risk: clean-parent check does not survive asynchronous preview/apply/reset

updateContextWorkflowFromSource1546–1606 checks the owning ID and canvas dirty state only at entry.
It then awaits critical freshness, saved artifact GET, preview, source apply and draft reset, without acquiring a lifecycle operation or checking rootEditEpoch, registration token, canvas disposal, current workflow incarnation or newer dirty state at those boundaries.
Graph commands remain available through most of this sequence; the context menu handler also does not reject isLocked at entry.
The server preview captures saved-artifact identity and confirms destructive effects, which protects its own source operation but does not represent new unsaved client edits.
The final reset uses the live accepted draft revision and installs saved truth; edits made during the sequence can be replaced or fail behind a conflict after saved source mutation already committed.
No controlled loss or external source update ran here; current confirmation/CAS barriers materially mitigate stale saved artifacts, and full App/other source-editor callers remain pending.
Prior full canvas persistence tests establish ordinary critical operations, not this context-source sequence with a held preview/new local edit.
Retain explicit preview/effect confirmation, accepted source ownership and independent draft authority; future diagnosis must capture the exact edited/submitted graph and operation owner rather than add speculative waits.
This concretizes an adjacent consumer of A-F055; it does not release a global Open repair.

#### A-F088 — Medium, qualified graph-install concurrency risk: shared boolean and unmount guard do not own a specific application

applyGraphState839–909 clears nodes/edges and yields twice before installing nodes/edges and accepted history.
It checks only isCanvasUnmounted across those yields, and isApplyingGraphState is a shared boolean reset by every finalizer.
Callers include initial mounting, authoritative agent draft installation, restore-saved event, replace-root event and nested-source-edit event; those handlers do not all acquire the same installation lease or monotonic operation token.
Overlapping admitted replacements can therefore interleave node/edge/interface/history state and an older finalizer can permit reconciliation while another installation remains pending.
Most current App lifecycle work and agent actions supply separate guards, materially limiting ordinary overlap; the full App and code-editor producer contracts remain pending, so this is a bounded source risk, not a demonstrated startup overwrite or ISSUE022 cause.
Existing import-only CanvasView test cannot distinguish it; prior mounted persistence tests cover disposed and accepted graph cases but no claimed exact overlap oracle here.
Retain two-tick handle mounting and independently captured authority; future diagnosis should compare actual admitted graph application tokens and owner lifetime before changing presentation behavior.

#### A-F089 — Medium, source race: asynchronous clipboard read bypasses later lock/disposal admission

pasteFromClipboard2840 checks isLocked before awaiting readClipboardPayloadResult.
After the read it prepares nodes/edges and directly calls addNodes/addEdges/emitGraphChanged at2886–2897 without another lock, unmount or registration check.
Execution may enter starting/running or the mounted canvas may be disposed while native clipboard permission/IO is pending; the continuation can still mutate its graph and queue persistence.
onDrop's asynchronous native-path branch at2386 instead delegates to onAddNode, which rechecks the lock, demonstrating a stronger immediate admission barrier (although disposal remains separate).
B's complete 'pasteFromClipboard is a no-op when locked' test sets running before calling paste, so it proves entry refusal but cannot distinguish a held clipboard read followed by starting/disposal.
No clipboard race test or gesture ran in audit.
Retain real clipboard parsing/reconciliation and canvas identity; future correction must refuse superseded admission at the physical mutation boundary, without replaying the paste onto a newly active canvas.

#### A-F090 — Medium, source interface-integrity defect: grouping does not remap the enclosing exposed interface

createSelectedNestedWorkflow2900–2934 passes nodes/edges/selection to groupIntoWorkflow, then replaces rendered nodes/edges and emits the graph.
The complete grouping helper returns nodes/edges/created nested node but does not receive or rewrite the enclosing interface.
Unlike deleteNodes2590, this consumer does not reconcile rootWorkflowInputs/rootWorkflowOutputs or a nested editor's current enclosing interface after selected nodes become internal children.
An exposed parent input/output targeting a selected node can therefore keep its old target/source ID, which no longer exists at that enclosing graph level, causing canonical GraphState refusal rather than successful grouping.
Existing complete grouping unit fixtures exercise ordinary edge boundaries, not an already exposed enclosing interface; the large real workflow-interface browser file remains pending full read and may refine its exact oracle.
No group operation ran here.
Retain portable nested structure, external boundary connections and source identity; future design must remap enclosing stable ports together with node grouping, without dropping viewer metadata (A-F064) or confusing DataFrame port kind (A-F065).

#### A-F091 — Low/Medium, conditional edge-update shape debt: endpoint rewrite retains the previous renderer edge discriminant

onEdgeUpdate2010–2084 changes source/target handles through updateEdge but does not update edge.type.
isValidConnection checks the new endpoints' header/body regions; a callback changing both endpoints to a valid different-region pair would retain the old column/dataframe discriminant.
The usual single-endpoint drag keeps the other endpoint fixed and rejects cross-region moves, which materially mitigates the ordinary GUI path; no normal two-endpoint gesture is established.
The complete serializer uses edge.type and then validates matching endpoint-handle kinds (useGraphSync118–145); mismatched retained type can throw during emitGraphChanged after the renderer edge already changed.
The locked-edge-update test proves late stopping refusal; it does not distinguish an unlocked edge reroute across valid regions, and broader real connection GUI tests remain pending.
No Vue Flow gesture or serializer failure was executed here; this remains conditional debt for programmatic or otherwise reachable two-endpoint updates, not an asserted current user gesture defect.
Retain in-place update identity needed for Vue Flow pointerup cleanup; future diagnosis should distinguish gesture reachability from the source's incomplete discriminant update and preserve rejection cleanup.


### Complete-review checkpoint — A-batch-14

#### A-F092 — Medium, qualified lifetime risk: nonstartup shell continuations lack the mount fence used by startup

activateWorkflowFallback1048–1076 captures DockviewApi, then awaits loadRootWorkflowPresentation and can call openWorkflowCanvasPanel/showEmptyCanvasState afterward without checking isUnmounting or API membership.
replaceMountedWorkflowGeneration1140–1176 removes a panel, awaits presentation reset/load and similarly opens a panel after those awaits; its catch can invoke fallback.
finalizeNestedWorkflowClose740–763 can queue reopening after a late DELETE error, while openNestedWorkflowPanel671 has no unmount fence.
onBeforeUnmount sets isUnmounting and removes listeners/disposables but does not clear dockviewApi or invalidate these independent operations.
The full startup path explicitly checks both isUnmounting and dockviewApi.value===capturedApi after awaiting, demonstrating that the corresponding guard is a deliberate supported lifetime contract.
Late nonstartup operations can therefore call the detached shell API and mutate shared presentation/session state after disposal.
No late response diagnostic ran; actual Dockview teardown may refuse some physical additions, so this remains qualified source risk rather than observed visible reopening.
AppShell's late-startup test does not distinguish fallback/generation/delete-close continuations, and full real browser counterparts are pending.
Retain durable admitted deletion/persistence effects; future consumer correction must fence presentation/finalizers without pretending an already committed backend operation was cancelled.

#### A-F093 — Low/Medium, qualified background-presentation design risk: generation replacement always activates its reopened root

replaceMountedWorkflowGeneration captures the affected panel/context but not whether it is the active canvas/dock presentation.
After reset/load it calls openWorkflowCanvasPanel, which always setActive for either an existing or newly added root at1405/1450.
A background collection refresh replacing an inactive workflow incarnation can therefore select that workflow over the user's current root, nested editor or dock; a user activation made during the awaited replacement is likewise not a barrier.
This is distinct from explicit user Open, whose activation is intentional and covered by startup tests.
No current selection loss or replaced graph loss was reproduced; a product decision to foreground replacement would change classification, and full real identity-refresh browser assertions remain pending.
Retain automatic stale-incarnation disposal and fresh authoritative loading; future policy should specify whether a background replacement restores its prior visibility or receives new presentation authority.

#### A-F094 — Low/Medium, conditional owner-finalizer debt: global close busy state can be finalized by an older target

saveAndCloseRootCanvas and discardAndCloseRootCanvas each capture a target but use the shared rootCloseBusy boolean as their finalizer ownership predicate.
disposeRemovedWorkflowCanvases1100 resets that boolean/dialog when an external removal disposes the target, allowing another close action while the original await still exists.
If a new close sets rootCloseBusy before the old operation's finally runs, the old finally can clear the new dialog's busy state and call canvasLifecycleStore.finish on its old canvas ID.
Ordinary modal/lifecycle behavior prevents overlapping closes until the exceptional external removal path, so this is conditional debt, not a reproduced common close race.
Same-ID recreation makes the lifecycle finalization axis particularly relevant because canvas IDs are reusable while registration tokens identify mount lifetime.
The helper tests guard persistence membership/newer edits, but do not distinguish two shell close operation finalizers after removal/replacement.
Retain exact mounted panel and recovery semantics; future ownership should associate finalization with the admitted close operation rather than rely on a reusable global boolean.


### Complete-review checkpoint — B-batch-8

#### B-F065 — P2 source defect: numeric coercion changes declared string outputs and labels

`engine/dataframes.py:256–265` tries pd.to_numeric on every string-typed column, irrespective of tool annotations or identifier semantics.
`engine/node_execution.py` applies it after transform, after validated processing output assembly/publication and on cache reads.
A declared Outputs.label:str value such as "001" passes the strict output validator, then becomes numeric1 in the returned dataframe; analogous DataFrameTool labels lose leading zeros too.
For processing output the published canonical record can preserve string while returned/cache-consumed frame is coerced; selected immutable record identity then describes the canonical stored representation, while downstream tools see a different runtime type/value.
This is deterministic source behavior, not an executed scientific failure.
Full `tests/unit/test_processing_output_validation.py::test_output_values_use_strict_annotation_validation` establishes strict declared type validation, but its label fixtures are nonnumeric and never exercise the later engine pipeline.
Column/source cache tests assert asset identity and counts, not numeric-looking declared string labels.
Future diagnostic should trace "001"/large identifier/ordinary numeric columns through first compute, exact record and cache hit, preserving intentional legacy numeric handling only where its authority is explicit.

#### B-F066 — P2 source defect: environment cache hash discards ordered channel priority

`cache/identity.py:15–28` sorts/deduplicates every dependency list, including dependencies.channels.
`env_manager.py` forwards declared channel ordering into public Wetlands EnvironmentSpec, and complete Wetlands specs.py preserves first-occurrence channel order and includes it in recipe serialization/hash (`473,522,553`).
Reordering Conda channels can therefore change the provisioned recipe/solver priority while leaving compute_env_hash and the tool cache result key identical.
The engine may accept the previous cache hit before inspecting/provisioning the changed environment; no version or actual solved-package mismatch is asserted without runtime evidence.
Full `tests/unit/test_cache.py::TestNormalizeDependencies::test_sorts_and_strips_lists` only checks an unordered pkgs example; dictionary-order independence is valid and should remain.
Future diagnostic must distinguish requirement sets from ordered channels and verify both Wetlands recipe identity and cache identity across channel reorder, retaining supported channels and ordinary requirement-order reuse.

#### B-F067 — P1 source-risk/identity defect: different tool origins can share a cache signature

`engine/identity_runtime.py:84–108` supplies only class.__name__, tool version, environment requirements, parameters/upstreams and optional dev-mode source hash to compute_signature_hash.
Module, qualified class and explicit output-contract identity are absent from this logical material.
Full get_tool_version review establishes that captured source hashes participate through the version value; the earlier blanket exclusion of custom-source content identity was overbroad and is withdrawn.
`cache/identity.py:70–108` then derives result key from tool kind, node key and this logical digest.
Lookup validates the record for that result key but does not compare requested tool origin; tool_identity is recorded in attempt diagnostics, not admission of a cache hit.
Distinct accepted classes with the same public class name/version/params at the same node key can therefore share a signature, for example different modules within one installed distribution/version or distinct qualified classes with the same source-file version.
Ordinary different captured source hashes are not asserted to collide.
This is separate from A-F001/A-F066 name-only catalog binding; A confirmed no existing cache-origin collision finding.
It is a source identity defect and unexecuted wrong-result risk, not a claim that all package upgrades require unconditional cache invalidation or editable source mutation must always be detected outside dev mode.
Full cache hash tests distinguish params/source-hash changes; a discriminating collision diagnostic must deliberately preserve equal version while changing accepted module/qualified output identity.
Future diagnostic should use distinct accepted tool origins with identical public names/versions and compare cache/materialization/plan signatures, retaining deliberate version-based source identity policy and portable module/source bindings.

#### B-F068 — P1 source-risk: record identity is recaptured independently of the consumed frame

`cache/dataframe.py:39–47` and `cache/processing_lookup.py:247–272` snapshot current once to load recordA but return only dataframe.
`engine/node_execution.py:121–159` later reads current again to record a provider outcome; completed/cached progress does likewise.
`engine/cache_runtime.py:57–81` reads current anew when writing the run-node record; `engine/identity_runtime.py:31–56` later recaptures current to sign a downstream consumer whose arguments came from the already-loaded frame.
A public Clear/removal followed by a new selection between those operations can attach recordB identities/signatures/provenance to values from recordA or make a successfully consumed immutable frame appear unselected.
Borrowed complete repository.select_current_record uses first-winner hard-link publication and retains current on nondeterministic competing publication; ordinary concurrent publication does NOT overwrite recordA.
The risk specifically requires pointer removal/new selection, such as another public Workflow sharing storage, not a claim that default platform Run/Clear admission is unguarded.
Platform's same workflow idle lease mitigates its own coordinated route calls; per-object library execution exclusion does not itself serialize independent Workflow objects/storage publishers.
A-F030 inspect-current→unlink race is related but remains A canonical; this finding concerns frame/identity handoff after lookup/publication.
Full `test_compute_steps_processing_tool_cached_step_emits_progress_identity` verifies matching IDs in a stable snapshot; full column invalidation tests preserve immutable records but do not interleave a reader and replacement.
Future diagnostic should coordinate pointer advance around one actual frame read and assert provider outcome, run view, downstream signature and consumed values all refer to the same immutable record, preserving first-winner arbitration and no wholesale current-pointer overwrite.

#### B-F069 — P2 source defect/confinement asymmetry: dataframe attempts follow symlinked parent directories

`cache/dataframe.py:66–80` recursively mkdir's result/attempt/staging paths before calling public start_cache_attempt, then writes canonical parquet there.
Borrowed complete `storage/repository.py:73–116` validates IDs and rejects only the final attempt directory symlink; it does not reject a symlinked attempts parent or establish storage-root confinement for that path.
A preexisting attempts symlink can therefore create a real new attempt directory and write attempt metadata/parquet outside the intended result subtree.
`processing_prepare_attempt` instead checks each child and rejects the attempts symlink before dispatch; the complete `test_source_processing_tool_rejects_symlinked_attempts_directory_before_execution` proves that intended protection only for ProcessingTool.
This is a source path ownership defect for tampered/preexisting cache state, not a claim of arbitrary remote path injection or a prohibition on an intentionally symlinked user-selected workspace root.
Future diagnostic should pair DataFrameTool and ProcessingTool attempts confinement and assert no outside writes, preserving portable explicit storage roots and immutable candidate installation.

#### B-F070 — P2 source-risk: attempt failure metadata can remain running or replace the original diagnostic

`cache/dataframe.py:73–139` creates running attempt metadata, then writes/validates/installs/selects without a failure-finalization scope; exceptions after start leave that attempt marked running despite no remaining writer.
Processing source/column paths do have failure handlers, but `engine/node_execution.py:424–438,653–691` calls finish metadata while handling the original exception without isolating a second metadata failure.
Corrupt/unwritable attempt metadata can replace the actual tool/processing error with a status-persistence error.
A completed immutable record can also be selected before a later success-status write fails; treat acknowledgement and durable selection separately rather than promising atomic rollback.
Existing safety tests correctly assert no current on earlier unsafe publication, but do not inject parquet/candidate/status persistence failures and inspect terminal metadata/original error together.
Future faults should establish no physical writer remains, stable primary diagnostic with secondary persistence evidence, and truthful record/attempt status; retain physical cancellation drain and any valid selected immutable record.

#### B-F071 — P3 source defect: malformed selected result metadata raises untyped shape errors

`cache/metadata.py:151–179` catches unreadable/invalid JSON syntax but calls metadata.get without proving a mapping.
A JSON list/scalar/null in result.json therefore raises AttributeError and aborts public iter_dataframe_result_metadata/iter_processing_result_metadata rather than returning a qualified corrupt/missing metadata result.
A-complete invalidation has metadata-less fallback, but this shape failure prevents it from reaching that fallback; do not silently treat a corrupted canonical record as ordinary absent cache.
This is separate from B-F027 legacy dataframe JSON shape handling.
Full cache/hash tests and column metadata-less invalidation tests do not cover nonmapping valid JSON result metadata.
Future diagnostic should preserve exact typed corruption/selection identity rather than skip arbitrary malformed records blindly.

#### B-F072 — P3 maintenance debt: unused path fixup helper retains obsolete flattening behavior

`engine/arguments.py:361–372` _fixup_output_paths strips all nested components to Path.name.
Whole library source search found no caller; current staging/template resolution and immutable publication preserve nested asset paths, established by full column nested-owned-path test.
Do not claim a present runtime flattening defect from this unused method.
Future cleanup can remove the obsolete helper or document its unsupported internal status after confirming public compatibility, avoiding future reuse that would contradict nested paths.

#### B-F073 — P3 test oracle/redundancy candidate: engine/configuration claims weaker than their assertions

Full `test_engine_injection.py::test_engine_parameter_is_keyword_only` only calls a keyword engine; no prohibited positional call is attempted.
Marker/state-accessible tests assert preexisting attributes survive, whereas TrackingEngine override tests genuinely distinguish the actual injected execute path.
The default test's prose says SequentialEngine even though a default parallel Workflow creates DefaultEngine; returned dataframe cannot distinguish that class.
Full environment management header promises Core auto-add and reuse, but this89-line module tests simple spec properties and one enabled dependency conflict with pytest.raises(Exception); the actual Core/manager counterparts are separate B1 unit modules.
These are confidence/maintenance candidates, not measured suite redundancy or proof of missing coverage across the whole suite.
Future revision should strengthen the distinguishing assertions and consolidate only genuinely duplicate contracts after the complete suite inventory/cost review; no automatic test deletion.


### Complete-review checkpoint — B-batch-9

#### B-F074 — P1, logical numeric identity source risk.

storage/identity.py:288 uses DataFrame.iterrows for canonical cells.
  Pandas' installed frame.py iterrows implementation/doc explicitly permits row dtype coercion; a mixed float/integer row can round integers above 2^53 before canonical scalar encoding.
  Distinct exact integer data may therefore share logical identity while the physical Parquet bytes differ; transport digest is deliberately excluded from content identity.
  tests/unit/storage/test_identity.py::test_canonical_dataframe_digest_is_stable_and_rejects_objects and ::test_canonical_dataframe_digest_includes_schema_material cover small/single-column integers, not this distinction.
  Future diagnostic should compare exact mixed int64/uint64 and float rows without weakening integer or schema identity.

#### B-F075 — P2, numeric categorical normalization mismatch.

identity.py:279 stringifies category schema labels, while cell encoding retains numeric labels; manifests.py:157 reconstructs categorical dtype from those string labels.
  Numeric category cells can become missing during manifest validation and then fail their own logical digest.
  Native transport with an already matching dtype can avoid that conversion, so this is not a claim that every categorical transport fails.
  test_manifests.py::test_record_manifest_validation_checks_files_and_digest and launcher/test_inputs.py categorical cases use string labels.
  Choose consistent lossless normalization or an explicit early refusal; do not silently replace values.

#### B-F076 — P2, column-name NFC consistency.

identity.py:274 normalizes schema column names but retains original DataFrame column keys; transport restoration requires declared schema names to exist in the original columns.
  Decomposed Unicode column names can be written and later refused, and normalized name collisions are not explicitly rejected before publication.
  test_identity.py NFC coverage addresses values, not column names or collisions.

#### B-F077 — P2, transport no-clobber admission gap.

dataframe_transport.py:179 checks destination existence before staging and later unconditionally os.replace installs it.
  A destination created meanwhile can be overwritten despite the nonreplacement contract.
  Unique internal paths mitigate routine callers; no default launcher loss was demonstrated.
  A bounded interval oracle should distinguish final admission from initial refusal.

#### B-F078 — P2, record reference validation asymmetry.

manifests.py validates listed assets and bytes but does not prove every record-relative Path cell references an owned listed asset.
  Processing cache hydration confines paths without the stronger named-membership check in storage/records.py.
  A self-consistent public record with an unlisted/missing reference can pass one boundary and fail the exact record reader; normal processing publication emits matching assets.
  test_current_pointer.py and test_manifests.py cover tampered named assets, not an internally rehashed unlisted cell reference.
  Preserve external path and owned asset distinctions when aligning validation.

#### B-F079 — P3, transient finalization weaker than backend diagnostics.

repository.py:383 overwrites transient status without validating run/node/invocation correlation or a running-to-terminal transition.
  Repeated finalization or swapped metadata can be accepted; valid nonmapping JSON produces an untyped failure.
  test_transient.py::test_transient_invocation_has_exact_identity_and_terminal_metadata is positive-only here, while test_backend_diagnostics.py distinguishes repeated terminal refusal.
  No late-writer outcome was executed.

#### B-F080 — P1, explicit export destination ownership race.

exports.py initially refuses an existing destination for replace=False, but after staging it backs up and replaces any destination then present without rechecking that flag.
  A foreign directory created during materialization can consequently be replaced and its backup deleted without replacement authorization.
  test_output_export_destination.py::test_destination_requires_replace_and_replaces_the_whole_tree tests an initially existing destination; ::test_destination_materialization_failure_cleans_staging does not introduce one in the interval.
  Next diagnostic should distinguish final no-replace admission while retaining explicit whole-tree replacement, source-overlap refusal and independent copies.

#### B-F081 — P2, canonical terminal finalization source risk.

run_views.py checks current running status and then writes a terminal result without holding an allocation guard or compare-and-set.
  Independent finalizers can observe running and publish contradictory terminal outcomes.
  The same WorkflowExecutionContext serializes its ordinary local finalization, and public cross-process recovery admission remains to be traced; this is not a demonstrated default race.
  test_run_finalization.py::test_canonical_terminal_state_cannot_be_rewritten proves sequential refusal only.

#### B-F082 — P3, derived run-view failure maintenance.

output_views.py:332 removes the existing derived node view and writes the replacement in place.
  Failure can leave a partial derived run tree and lose its preceding projection, while canonical immutable records remain rematerializable.
  test_output_materialization.py validates successful representations; latest-view rollback is a separate stronger contract.
  Do not infer a canonical record loss or silently impose transactional guarantees on every derived projection.

#### B-F083 — P2, durability recommendation gap.

identity.py:147 atomically replaces JSON without file/parent fsync; canonical cache publication also has paths without explicit durability barriers.
  The complete storage specification recommends supported file/parent fsync before visibility.
  Existing tests prove logical atomicity and process-readable state, not power-loss durability.
  Launcher durability must be reviewed separately; this is a qualified policy/source gap, not an executed recovery failure.

#### B-F084 — P2, postcommit cleanup failed acknowledgment.

explicit export/latest replacement installs the new tree before deleting the old backup.
  Backup cleanup failure can report failure after committed installation, leaving the new tree and backup instead of restoring the previous tree.
  test_output_replacement.py and test_output_export_destination.py::test_destination_replacement_rolls_back_and_cleans_staging inject preparation/install failures, not cleanup after installation.
  Define the commit boundary and recoverable cleanup outcome; retain backup safety rather than deleting unrelated paths.

#### B-F085 — P3, storage specification distinctions.

identity scalar encoding maps NaN through its missing-value branch although the document separately promises a NaN sentinel; deliberate infinite PSNR remains valid and is not a scientific defect.
  The work-scratch exception prose conflicts with stricter owned-assets confinement elsewhere and in implementation/tests.
  Numeric categorical prose links B-F075; source/tool/output contract identity links B-F067.
  Low-level safe legacy run names used by fixtures should be distinguished from UUID generation grammar, not labeled a traversal defect.
  Full documentation judgment remains pending its launcher chapters.


### Complete-review checkpoint — reviewer-batch-9

#### reviewer-F036 — direct segmentation examples omit required resolved output paths (P3)

`packages/bioimageflow-segmentation-tools/docs/tools/threshold_segment.md:28–30`, `watershed_segment.md:29–31` and `postprocess_labels.md:27` directly call `process_row(Arguments(...))` without `labels`, `labels` and `output_labels` respectively.
The actual methods directly access these fields at `bioimageflow_segmentation_tools/classical.py:153`, `:424` and `:783`.
Core `arguments.py:101–120` only copies supplied keyword fields and raises `AttributeError` for an absent field; `tool.py:139–230` does not wrap these calls or resolve the declared output template.
Thus a reader supplying otherwise valid image/parameter inputs reaches a missing output field rather than the promised minimal result; this is source-established documentation failure, not an executed red.
After the full audit, the smallest faithful correction is to add explicit output file arguments to these three examples, consistent with adjacent examples and the direct worker-method contract.
Do not alter processing semantics or inject engine template resolution into direct methods merely to match prose.
Existing package execution tests use explicit output paths and can be reused as documentation counterparts; no new model/browser suite is justified by this example-only correction.

### Existing reviewer-F035 extension — concise pages omit essential public usage guidance (P3)

The complete reads add CellposeSAM (16 lines), InstanSeg (11), Nagini3D (12), BilateralDenoise (15), CAREamicsPredict (7), RestorationMetrics (8) and TotalVariationDenoise (14) to the already held thin-public-tool-doc finding.
These pages name the operation and some important constraints but omit usable configured examples and/or the implemented input/output/refusal guidance required by the already reviewed custom package documentation contract.
Populate only those actual schema/weight/device/axis/checkpoint/range essentials from existing implementation and package workflow/contract selectors after the audit; avoid a duplicate long model manual or invented model availability guarantee.
Preserve pinned worker environments, model/license provenance and distinct real-runtime markers/skips.


### Complete-review checkpoint — reviewer-batch-10

### Existing reviewer-F036 extension — DetectSpots direct example omits resolved fields (P3)

`packages/bioimageflow-spot-tools/docs/tools/detect_spots.md:28–30` calls `process_row(Arguments(input_image=..., method="dog", threshold=0.3))`.
The implementation accesses `arguments.sigma`, `sigma_ratio`, `min_distance` and `output_labels` directly at `bioimageflow_spot_tools/detection.py:148–152` and `:188`.
Its declared Inputs defaults and Outputs template are resolved by the engine, not by Core's plain `Arguments` namespace or a direct method call.
The example therefore has the same source-established missing-field problem as the three segmentation examples in batch 9, beginning at sigma for an otherwise valid image.
The smallest future correction is explicit defaults plus output path in the direct example, or a coherent graph-node example that actually runs through the resolver; do not modify the scientific method or invent direct template/default injection.
By contrast, the concise FilterSpots, SpotSummary, SpotQualityMetrics and rasterization examples use implemented `getattr` defaults and explicit output paths where needed, so their omitted optional values are not blanket defects.
The Core/source excerpts remain separately owned; no execution or new test request is made.


### Complete-review checkpoint — reviewer-batch-11

No additional finding IDs.
Each classified navigation wrapper has exact source, generator and Sphinx/MyST consumer evidence in its ledger judgment; human source and runtime credit remain separate.


### Complete-review checkpoint — reviewer-batch-12

No additional finding IDs.
Each classified navigation wrapper has exact source, generator and Sphinx/MyST consumer evidence in its ledger judgment; human source and runtime credit remain separate.


### Complete-review checkpoint — reviewer-batch-13

No additional finding IDs.
Complete human/curated content judgments retain documented boundaries and distinct existing selectors; no incidental counterpart receives credit.


### Complete-review checkpoint — reviewer-batch-14

#### reviewer-F037 — explicitly implemented strategy clauses are stale despite roadmap disclaimer (P3)

`docs/tool_package_strategy.md` correctly labels itself a candidate strategy and defers metadata/release authority to current package references.
However, its explicit **Implemented tools** clauses describe `CellposeSegment`/`StarDist2DSegment`, make `ThresholdSegment` a multi-algorithm entry point, assign hole/border filtering to `PostprocessLabels`, call absent `LabelAdjacency`/`ColocalizationMetrics` implemented, and say `RestorationMetrics` reports SSIM.
The completely read current package docs and scoped actual export maps instead expose `Cellpose3`/`CellposeSAM`/`StarDistSegmenter`, separate Otsu/local/distance/filter tools, no exported adjacency/colocalization tool, and restoration MSE/PSNR/residual noise outputs.
The strategy also says the current common-tools package still contains the already moved model/axis/Atlas tools, contradicting its own later stabilized-boundary paragraph and current package overview.
The general candidate disclaimer should not make explicitly current/implemented claims false or turn essential implemented behavior into a proposal.
After the audit, minimally update exact current names/semantics or label actual future algorithms as candidates, preserving the dated planning inventories and workflow/provenance/validation standards.
A concise current-boundary table linking authoritative package pages can replace duplicated stale lists; do not implement roadmap tools or expand the campaign merely to satisfy stale prose.
No upstream release/date facts were independently browsed or presented as current external verification.

#### reviewer-F038 — primary custom-tool examples violate current concrete-class and worker contracts (P2)

`docs/source/how-to/custom_tool.rst`'s GaussianBlur, MeasureIntensity, BatchClassifier and TileImage examples and `tool_packaging.rst`'s MySegmenter omit an explicit `RowConsumption` enum declaration.
Core `tool.py:149–173` rejects those concrete classes at definition time, exactly as normative `docs/source/specs.md:609` requires; `tests/unit/test_tool.py::TestProcessingToolValidation::test_missing_row_consumption_raises` is the existing guard counterpart.
The custom guide additionally uses plain inner Inputs/Outputs classes and returns `self.Outputs(field=...)`; plain Outputs has no kwargs initializer whereas `IOModel` supplies that constructor in Core `tool.py:108–119`.
Even after fixing the first declaration refusal, those Outputs examples therefore remain unusable.
Declare the appropriate mapped or collective row meaning and inherit `IOModel` in concise runnable examples, keeping batch consumption distinct from output cardinality and parallelism.
Do not weaken class validation or add automatic backwards compatibility to make documentation pass.

The versioned packaging guide also eagerly imports `.pipeline.build_workflow` from package `__init__.py`, while that module imports the main-process orchestrator.
Workers importing `my_tools.segmenter` first execute the package initializer and should not require the orchestrator; the guide's own processing import rule and already reviewed first-party lazy-export maps contradict that recommended mixed barrel.
Use a lazy export or an explicit main-process factory import while preserving relative versioned imports and public workflow ownership.
Existing class-declaration, IOModel, package-import-boundary and versioned-loader assertions are appropriate source counterparts after audit closure; these prose changes do not justify redundant model/browser/full-suite execution.


### Complete-review checkpoint — reviewer-batch-15

`docs/developer/workspace-storage-and-demos.md` ends by saying ordinary platform development and CI use registry packages, whereas the actual backend lock and `local-development.md:116–126` require editable sibling orchestrator/Core source, including CI uv sync.
This extends held F001/F002 mode/prerequisite inconsistency; keep the clear distinction between source acceptance and published-package certification and correct the single stale sentence after closure.
The Node-only alternative in the development prerequisite repeats F002 because current documented runner/build commands require Bun; this is not an observed install failure.

`docs/agents/troubleshooting.md:17`'s required-first-call sequence omits `get_workspace_context`, unlike `docs/agents/README.md:23–26`, backend generated instructions and `workflow_draft.py`'s current recommendation.
This is a curated operational-doc corroboration proposed under root's existing ROOT-F048 interface/documentation drift family, not a duplicated new ID or permission to change MCP behavior.
Use the exact authoritative sequence rather than broadening client commands or copying long API reference examples into public pages.


### Complete-review checkpoint — reviewer-batch-16

No additional finding IDs.
Complete human/curated content judgments retain documented boundaries and distinct existing selectors; no incidental counterpart receives credit.

### Complete-review checkpoint — root-batch-8

#### ROOT-F053 — P1/P2 static physical-lifetime risk: terminal cancellation can precede an existing or unverified cleanup owner

ExternalEnvironment._cleanup_failed_task_worker1757–1780 marks _terminal_cleanup_in_progress, clears worker._current_task and claims retirement before physical cleanup.
Concurrent public Task.cancel can then find no owning worker in _cancel1697–1720 and publish _set_canceled immediately, even while another cleanup owner is still terminating that worker.
The forced-cancel and broken-connection paths also publish cancellation after cleanup returns False, which can mean another owner is still cleaning or process-tree termination could not be verified and a fatal worker record is retained.
Task._async_result waits the done event, not the independent retirement owner's completion, so the documented mandatory-cleanup-before-CancelledError/OperationCanceled guarantee can be acknowledged too soon.
The full asyncio/cancel guides explicitly require physical/transfer cleanup before that acknowledgment; preserve those essential guarantees rather than weakening the prose.
Existing worker-health tests protect claim-before-slow-cleanup, one-owner dispatch cleanup ordering and retryable unverified pool close separately; they do not distinguish a second cancellation acknowledgment during the first owner's held cleanup.
No race, surviving process or filesystem write was executed in this audit.
Retained manager/pool ownership and fatal admission mitigate later reuse, but do not establish physical quiescence at the task acknowledgment boundary.
After complete synthesis, distinguish successful cleanup, in-progress cleanup and failed verification through the same owned lifetime; reuse the exact local retirement/cancellation family for a discriminating diagnosis.
This is the Wetlands lower boundary, distinct from platform B-F024 raw compute-thread admission release.

#### ROOT-F054 — P2 source cleanup gap: envelope validation follows array allocation outside the cleanup scope

ExternalEnvironment._submit_encoded1851–1895 protects argument/keyword encoding, then constructs execution_envelope after leaving its cleanup try.
An invalid context_keyword is refused by protocol.execution_envelope after input arrays have already allocated durable host-owned shared-memory leases.
The task never becomes a submitted/queued owner and the failure path does not dispose those stored input leases.
SharedMemoryLease has no unlinking destructor, and complete codec recovery deliberately preserves segments belonging to a live creator, so ordinary reconciliation cannot release this abandoned live-host intent.
All-valid public submission is mitigated; no array was allocated or leaked during review.
The full codec tests protect partial recursive encoding, failed allocation and live/dead creator recovery; the worker-protocol context example covers None/valid identifiers, not post-allocation envelope refusal.
Future diagnosis should isolate invalid context metadata plus an otherwise supported array, preserving fail-before-dispatch validation and independent array ownership rather than adding a full environment journey.

#### ROOT-F055 — P2 exceptional retry risk: failed close-thread start leaves an unfinished attempt reusable forever

ManagedEnvironment._start_pool_close_attempts269–289 and _start_process_close_attempts318–339 install an attempt in the retained map before constructing/starting its thread.
If thread construction/start raises before the worker begins, the attempt has no completion publisher but remains in the map.
A subsequent close reuses that unfinished attempt without starting another worker; an unbounded close can wait forever and a bounded one can time out repeatedly.
The already reviewed manager shutdown contract requires retained cleanup to be retryable, and full health tests explicitly preserve control after detached-reaper thread-start failure; those stronger cases do not close this attempt-map boundary.
No thread failure/hang was executed, and ordinary started close workers set their completion events in finally.
Future correction must distinguish an unstarted attempt from an actually running retained cleanup owner, preserving no-duplicate cleanup after a legitimate timeout.

#### ROOT-F056 — P2 static queued-cancellation admission gap: dispatch can send a task already acknowledged canceled

_dispatch_or_idle1550–1581 checks a queued task's terminal state before calling _dispatch_to_worker.
_dispatch_to_worker performs lease/capability preparation before claiming worker._current_task and does not atomically recheck the task's cancellation/terminal admission at that claim or send.
A public queued task canceled in that interval has no current worker, so _cancel disposes its inputs and publishes terminal cancellation; the later dispatch still installs the task and sends its payload.
Task._set_running refuses an already terminal transition, but its void return does not prevent the caller's subsequent physical send.
Scalar calls can be sent after cancellation; array payloads can reference transport already released by that cancellation.
No remote function or race was executed, and normal queued tasks canceled before the first check are skipped correctly.
The complete worker-health test for retirement after idle-pop holds the same preparation boundary but changes worker ownership; it does not assert task cancellation admission.
Retain that worker-retirement and concurrent-shutdown coverage; future diagnosis should use the existing exact dispatch family to distinguish terminal task admission before actual send.

#### ROOT-F057 — P2 exceptional cleanup ownership gap: the first lease-disposal failure abandons later leases and the claimed task list

value_codec.dispose_leases944–950 stops at the first exception rather than attempting the remaining leases.
A creator unlink can raise while removing its durable record, even after its segment was successfully unlinked.
ExternalEnvironment._cleanup_task_inputs1782–1791 clears task._input_leases before calling this disposal loop, so another cleanup caller sees no retained list to retry the undisposed sibling leases.
Partial nested encode and ordinary terminal cleanup use the same loop; their initiating diagnostic can also be replaced by the cleanup exception.
The full codec and worker-health tests prove successful idempotence and exactly one atomic cleanup claimant, but do not inject durable-record removal failure during a multi-lease cleanup.
No IO failure or leaked segment was executed, and creator-death recovery remains a later mitigation rather than proof of live-host cleanup.
Preserve the single claimant and exact creator/attachment distinctions; later repair should attempt every owned cleanup and retain/report failed obligations without erasing the original operation diagnostic.


### Complete-review checkpoint — A-batch-15

#### A-F095 — Medium, source validation/oracle gap: valid clipboard envelope admits invalid recursive node/edge structure

clipboard.isNode85–91 checks only type/id/name and Array.isArray(position); it does not require valid numeric coordinates, tool_name/parameters or a workflow body/interface.
isEdge94–107 admits a DataFrame edge without its required position/input exclusivity and does not require endpoints to belong to copied nodes.
normalizeClipboardPayload109–128 returns a typed cloned ClipboardPayload after those shallow guards; prepareClipboardPaste maps missing endpoints with non-null assertions and can accept duplicate original node IDs into one idMap entry.
A marker/version-valid workflow node with no workflow body or tool node with missing parameters can therefore pass parsing and throw uncaught during prepare/hydration; structurally invalid edges can mutate renderer state before canonical persistence refuses them.
CanvasView awaits the reader but does not catch later prepare/hydration failures as an invalid-clipboard result.
Unit 'rejects records without the current strict discriminator envelope' distinguishes only missing marker/wrong version; the real browser refusal uses malformed JSON, not a syntactically valid malformed recursive graph.
No malformed structural payload was executed in audit.
Retain explicit envelope/version refusal and public backend semantic validation; future boundary should validate the complete clipboard structural shape before physical graph mutation without inventing a second execution validator.

#### A-F096 — Medium/High, source-owned copy boundary risk: clipboard graph references move without destination-owned bytes

serializeGraphSelection152–170 records source_workflow_id and clones source_module references recursively but includes no source bytes/manifests.
CanvasView.copySelected supplies its owning workflow ID; pasteFromClipboard never consumes source_workflow_id or calls a server source-transfer/preparation endpoint before adding nodes and queuing the destination draft.
prepareClipboardPaste likewise copies source references unchanged, including inside complete workflow nodes.
Pasting an owned tool/embedded source into a different workflow can therefore leave references without destination-owned manifests/bytes, or resolve an existing same-ID destination source rather than the copied source.
Workflow-local source collection/public loading remain authoritative; same-workflow paste has the source already present and is materially mitigated.
This is not a claim of arbitrary imported code execution or proven wrong scientific output; no cross-workflow owned paste was attempted.
Existing recursive unit child has no owned source, and real browser fixture uses SeedNumbers/IncrementNumbers catalog nodes; neither distinguishes the byte-transfer contract.
Retain exact accepted graph identity and destination-owned source isolation already proven by ordinary duplicate/archive paths; future clipboard policy must explicitly stage bytes or refuse unsupported cross-owner references before admitting graph mutation.

#### A-F097 — Medium, qualified binding/recipe authority risk: paste reconciles carried identity parameters against the live same-name catalog

reconcileToolNode261–293 looks up tool_name, compares package/version only to produce a warning, reconciles parameters against that catalog inputs map, and returns cloned node identity fields unchanged.
Thus a carried portable v1 binding or owned source can retain its exact v1/source identity while its parameter recipe is removed/reset according to unrelated same-name v2 metadata.
This differs from an intentional explicit installed-version rebind because the identity is not changed along with the recipe.
Missing catalog tools retain their cloned parameters, which is a useful mitigation for fully unavailable classes, but same-name collisions are the problematic axis.
The browser fixture has no conflicting version/source, and the complete recursive unit bypasses top-level tool reconciliation by copying a workflow node; no exact recipe/captured-class conflict oracle is present there.
Clipboard requirements may intentionally reconcile unbound ordinary catalog nodes; this source risk is limited to carried bindings and does not condemn that normal path.
No execution/reconciliation diagnostic ran; normative paste/version policy must be reconciled before repair priority.
Retain warned incompatibility, captured portable identity and A-F066's live-hydration distinction; future authority must change identity and recipe together only through an explicit supported policy.

#### A-F098 — Medium, source canvas-identity risk: connected-pin restart searches the whole document by reusable node ID

InputPin.vue56–61 uses document.querySelector for .vue-flow__node[data-id=source] and its handle, without limiting the lookup to the owning Vue Flow/canvas root.
Two retained root/nested canvases can legitimately have equal node/handle IDs; both may remain mounted even while one dock tab is inactive.
The first matching source element can therefore belong to another canvas; after disconnecting the owning edge, the component dispatches synthetic pointerdown to that other element.
The edge store lookup is canvas-contextual, but DOM identity is independently global, so these authorities need not agree.
The complete pointer unit installs a single fake global source and checks disconnectEdge called; it does not assert the dispatched source identity or two-canvas gesture separation.
No wrong-canvas drag was executed, and actual inactive DOM retention/gesture admission must be checked by the existing real tab/connection counterparts before a user-loss claim.
Retain the detach-and-restart gesture; future source-element resolution must be scoped to the same captured canvas rather than a globally first matching ID.

#### A-F099 — Low/Medium, source selector robustness: accepted node IDs are interpolated without CSS escaping

The same InputPin query inserts existing.source into a quoted CSS attribute selector without escaping.
Canonical tool/workflow node IDs are nonempty strings in the complete backend graph model, not a restricted CSS-safe identifier grammar; imported quoted/backslash-containing IDs can be structurally valid.
A valid ID containing a quote can cause selector syntax failure or unintended matching before the disconnect/restart logic completes.
Generated GUI IDs are conventionally safe, materially mitigating normal newly created nodes; the single fake-source test uses src/output and does not isolate an accepted imported special ID.
No selector fault was executed here; this is bounded robustness debt, not a server injection claim.
Retain arbitrary valid graph identities and encoded endpoint handles; future DOM matching should compare/scopingly escape exact identity rather than silently shrink portable graph compatibility.


### Complete-review checkpoint — A-batch-16

#### A-F100 — Low, test wording/oracle mismatch: missing-owner refusal changes revision despite title claiming neither durable state changes

The selector at1423 is 'refuses nested Save after its root owner closes without changing either durable state'.
Its assertion at1463–1464 explicitly requires privateAfterRefusal.snapshot_revision == privateBeforeSave.snapshot_revision +1 while graph bytes remain equal.
That is consistent with Save first flushing the private snapshot and then refusing the unavailable parent; it is not evidence of unwanted parent mutation or data loss.
The existing oracle is deliberate and useful, but the title overstates immutable durable state and can cause a reviewer or campaign record to credit a no-write guarantee the test does not provide.
Retain exact parent/saved graph preservation, private graph preservation, explicit revision semantics, refusal and reopen; future naming/documentation should distinguish unchanged graph content from unchanged snapshot metadata.
No test execution or behavior change is authorized.

#### A-F101 — Low/Medium, qualified suite fixture lifetime debt: interface journeys create durable workflows/snapshots without per-test removal

The sole describe uses beforeEach seed setup315–318 and has no afterEach cleanup anywhere in the complete file.
Multiple scenarios create distinct namespaced workflows, saved documents, root drafts and nested snapshots, including an explicit unrelated snapshot retained after the depth-two close scenario.
Unique Date.now-based names and isolated E2E runtime fixtures materially mitigate cross-test identity collisions; shared runtime teardown is reviewer-owned and must be reconciled before claiming lasting process/disk leakage.
This differs from clipboard tests' best-effort per-test DELETE: these journeys rely entirely on outer runtime retirement for durable fixture lifetime.
No leaked runtime or measured slowdown was observed, and destructive cleanup while nested owner tabs exist must not invalidate the very acceptance being checked.
Future suite work should document the outer cleanup authority and inspect cumulative runtime workload before adding cleanup or splitting scenarios; this is a maintenance/performance candidate, not a new application defect.


### Complete-review checkpoint — A-batch-17

#### A-F102 — Medium, source stale-presentation/lifetime risk: menu-mounted editor status can overwrite a newer explicit target

CodeEditorPanel onMounted176–195 checks codeEditorUrl/codeEditorOpening only before awaiting getEditorStatus({launch:true,workspace:true})182.
When an available response returns184–187 it unconditionally invokes the global UI setCodeEditorTarget with the returned URL and the *current* codeEditorPath, without checking mount lifetime, captured target request ID, newer opening or newer URL.
An explicit editor open accepted while this older menu status request is pending can therefore be replaced with an older managed workspace URL, combine that URL with the newer path, clear the newer opening flags, and set panels.codeEditor=true after close/unmount.
The root-owned setter274–287 confirms it also resets target request ID to null for this unkeyed call and reopens the panel flag.
App's normal editor event path carries requestId, and API helpers reject old request results, but this direct mount status setter bypasses those guards.
The exact existing unit 'starts and renders the embedded editor when the panel opens from the menu' supplies an immediately resolved status; it does not hold it across a newer explicit target or unmount.
No visible race was executed; keep the automatic menu startup feature and captured request presentation authority, and record a future owner-fenced diagnostic after the audit gate closes.

#### A-F103 — Medium, source polling lifetime risk: an in-flight status poll can restart its timer after unmount

onBeforeUnmount198–202 clears timers and removes listeners but sets no disposed flag and does not abort an in-flight getEditorStatus.
pollStartupStatus109–116 publishes its result and unconditionally calls scheduleStartupPoll in finally; that helper98 uses only retained loading/URL refs, which can remain loading=true/URL=null after component removal.
If unmount occurs while that request is pending, its completion can install a new timer and subsequent sequential polling from the retired component until global loading/URL state changes.
This is bounded sequential polling, not overlapping requests or proven permanent process leakage; the mounted watcher normally stops after opening completes, and API/server process teardown may end it.
The exact existing 'polls sequentially and stops when opening finishes' clears opening and waits before wrapper.unmount(), so its assertion cannot distinguish completion after unmount while opening remains pending.
Retain sequential polling and final-request error authority; future cancellation/retired-owner handling should cover the callback finalizer, not merely clear the currently visible timer.

#### A-F104 — Medium, source recovery defect: iframe failure remains latched across later successful editor targets

The iframe @error sets failed=true, and available requires !failed.
The URL/path watcher204–206 resets only focusedAfterLoadKey; successful API target changes or manual restore do not clear failed.
The only failed=false assignment is the one-time automatic mount status success186.
Once a mounted editor iframe errors, a later valid explicit target from api/editor→App→setCodeEditorTarget leaves the same panel in unavailable state and no new iframe is rendered; closing/recreating the component is a material workaround.
Existing 'switches to unavailable state on iframe error' checks the initial failure only; same-target/file switches and restore tests begin with failed=false.
No browser error/retry was executed here; preserve failure diagnostics and frame stability while future recovery policy resets only for an admitted replacement/retry target.

#### A-F105 — Low/Medium, qualified native acknowledgement risk: close result is ignored before declaring the editor restored

CodeEditorTab's detached close awaits closeCodeEditorWindow then unconditionally clears detached; CodeEditorPanel.restoreEditor does likewise.
The root-owned native bridge wrapper's public boolean returns false when unavailable, and forwards the native close acknowledgement otherwise.
The consumer therefore treats any resolved false as successful restoration, unlike native open which checks its boolean result before setting detached.
A bridge disappearance or native false acknowledgement may leave a child window present while the UI claims it is restored; the actual Python bridge close contract remains root-owned and must establish which false cases mean already absent versus failed close before severity is elevated.
Both exact consumers' existing native-close tests return true exclusively.
No native action/failure was attempted and no duplicate window was observed.
Retain manual window-closed event restoration and supported no-op browser behavior; future policy should distinguish the native acknowledgement rather than assume every resolved result signals closure.


### Complete-review checkpoint — B-batch-10

#### B-F086 — P2, remote profile DTO validation gap.

launcher/profile_validation.py:74 only checks report schema before accepting valid, executor_labels, allocation_created and workflow_run_created values; unknown fields are ignored.
  A malformed report such as valid="false" is truthy in a consuming preflight decision, and declared boolean/label fields are not enforced.
  RemoteNodePathPlan/from_dict in the same public API provides the stricter contrasting oracle.
  Platform preflight tests validate ordinary valid/invalid reports, not malformed transport fields.
  Future validation should retain sanitized diagnostics and non-submitting checks, with exact field and boolean/label refusal.
  No malicious server, workflow submission or policy bypass was executed.

#### B-F087 — P3, prepared lifetime nonfinite acceptance.

prepared.py:290 accepts NaN and infinity because its positive-number check lacks isfinite.
  expires_at=NaN makes every expired comparison false; an infinite lifetime retains staging indefinitely until explicit close.
  test_cluster_bundle.py::test_remote_preparation_exposes_pinned_cluster_pre_launch_source closes its positive case but does not distinguish nonfinite expiry.
  Preserve explicit owned staging/close and configured finite lifetimes; this is a source validation issue, not a measured leak.

#### B-F088 — P2, unresolved prepared exactly-once handoff.

prepared.py:221 checks _submitted and sets it only after transport returns; no submit/close admission lock exists.
  prepared_transport.py issues fresh allocation/commit/submit request IDs on each call.
  Concurrent calls can both enter handoff, while an ambiguous failure leaves the public object apparently resubmittable with new identities.
  The docstring promises submission exactly once, but server bundle/retry idempotence may mitigate specific outcomes and is not yet completely reviewed.
  test_cluster_bundle.py inspects staged copies and manifests without submitting the prepared object; no concurrent or ambiguous same-object oracle exists there.
  Keep this candidate open until the full SSH/server review; do not claim demonstrated remote replay or require a universal coordinator.

#### B-F089 — P3, strict wire edge inconsistencies.

submission_schema.py:356 compares protocol version mappings using equality, so bool True equals required integer 1.
  schemas.py performs set membership on state/backend/error/event fields before a string check, so a JSON array/object may raise untyped TypeError rather than LauncherSchemaError.
  Exact unknown-field, digest, retry-binding and state-dependent tests in test_schemas.py are meaningful but omit these shapes.
  Future tests should distinguish wrong scalar/container types while retaining exact schemas and unknown-version refusal.
  This does not establish acceptance of an executable invalid graph or an unsafe resource request.

#### B-F090 — P2, explicit cluster-path preservation inconsistency.

inputs.py exposes separate cluster-preserving codecs, and cluster_submit.py uses decode_cluster_typed_constant for transported request inputs and preserve_cluster_paths=True for its later invocation (targeted caller trace only).
  Yet submission_schema.py:223 and inputs.py:583 use the ordinary decoder, whose normalized-path check resolves against the host filesystem.
  An explicitly normalized cluster path through a symlink can therefore be refused after cluster-preserving staging, whereas the request decoder intentionally preserves its spelling.
  test_inputs.py covers local resolution; test_cluster_bundle.py::test_bundle_never_reads_unmarked_path and ::test_bundle_preserves_cluster_paths_strings_dataframe_and_upload cover staging, not that final cluster-host distinction.
  No laptop-host dereference or executed remote failure is claimed: final invocation validation occurs in the receiving cluster path too.
  Resolve path-spelling authority at the full submit/orchestrator boundary without reading/uploading unmarked cluster files.

#### B-F091 — P3, auxiliary artifact JSON reader weaker than canonical reader.

artifacts.py:51 uses ordinary json.loads, accepting duplicate keys and parser nonfinite constants before its artifact-specific validator.
  repository.py explicitly rejects both for canonical metadata, uses no-follow regular-file opens and normalized protocol errors.
  Typed artifacts often subsequently refuse wrong field values, but duplicate keys can already have been silently collapsed.
  Error/manual/process correlation tests should distinguish duplicate-key corruption; align the reader contract without weakening idempotent immutable writes or secret redaction.

#### B-F092 — P2, public allocation correlation and candidate-kind gaps.

repository.py:_allocate_locked validates the supplied backend independently but does not correlate it with submission.launch.backend.
  A valid public call can install a control status for a different backend than its captured launch configuration.
  _validate_candidate_tree:597 checks symlinks but not nonregular file kinds, unlike bundle staging's special-file refusal.
  test_paths_and_allocation.py proves actual cross-process namespace exclusivity, candidate visibility and symlink refusal, not backend mismatch or FIFO/socket candidates.
  Default submission callers derive consistent backend and create regular staged inputs; no default scheduling defect is asserted.
  Keep shared namespace admission and explicit immutable material intact.

#### B-F093 — P3, packaging limit/path-policy consistency candidates.

cluster_bundle.py:_copy_entry copies the full file before callers enforce aggregate byte limits, allowing an oversized explicitly authorized local file to consume disk/work before its refusal.
  Streaming digest/stat verification and immutable copied bytes are sound; this is bounded-cost enforcement debt, not a measured denial of service.
  Nested upload names and cluster path codec checks differ from the strict root basename/SSH/path override checks for backslash and control characters.
  types.py:_cluster_work_dir rejects NUL but permits newline/carriage return, while _absolute_posix_path explicitly refuses all three.
  Scheduler queue/project fragments are correctly refused; PSI/J use of work_dir needs the later complete adapter trace before treating controls as command injection.
  test_types.py unsafe work_dir matrix, test_cluster_bundle.py symlink/relative-path cases and explicit copy mutation oracle do not cover these distinctions.


### Complete-review checkpoint — B-batch-11

#### B-F094 — P3, progress append asymptotic cost.

control_progress.py:append_progress rereads and parses the entire existing journal under its guard for every event to obtain sequence and repair an incomplete tail.
  n events require cumulative O(n²) parsing/I/O despite append-only durable output.
  Page reads avoid retaining the entire history but scan preceding entries; that is a different cost.
  test_state_machine.py::test_progress_sequence_is_global_across_processes proves correct ordering of 45 actual multiprocess events; it is not a growth/cost oracle.
  Record a future measurement/optimization candidate while preserving global sequence, corruption refusal, incomplete-tail repair, fsync and writer fencing; no measured slowdown or speed gain is claimed.

#### B-F095 — P2, repeated takeover write-failure recovery gap.

control.py:takeover_claim explicitly resumes a claim one epoch ahead of status after claim write succeeds but status write fails.
  If that one-ahead claim expires, recovery archives it and writes another newer claim before updating status.
  A second status-write failure leaves the claim two epochs ahead; later recovery only accepts the exactly-one-ahead branch, then rejects the different epoch.
  test_claims.py::test_takeover_resumes_after_claim_write_crash covers resuming a still-live one-ahead claim after one injected write failure, not expiration plus a second failed status install.
  This is an unexecuted source recovery candidate; preserve backend-absence confirmation, fencing/history and recovery-without-compute replay.

#### B-F096 — P2, transport outcome ambiguity inconsistencies.

ssh.py:_decode_response raises its over-byte-limit error with ambiguous=False although a remote mutation may already have committed before an oversized response is observed.
  cluster_agent.py:run_agent maps generic exceptions to internal-error with retryable=False, and SSH maps the retryable field directly to outcome ambiguity.
  A dispatch-receipt persistence failure after scheduler acceptance can therefore look definitive to the client, even though same-request recovery remains possible.
  test_ssh_transport.py::test_response_loss_is_ambiguous covers malformed JSON, not oversized or a structured generic post-effect error.
  Separate ability/desirability to retry from whether effects may have occurred; retain sanitized errors and same-key recovery, with no asserted executed scheduler outcome.

#### B-F097 — P2, connection timeout also caps full operation.

ssh.py passes transport.connect_timeout both to OpenSSH ConnectTimeout and subprocess.run(timeout=...) for complete agent commands and SFTP uploads.
  A valid slow upload/hash/commit may be terminated after the connection budget even after prompt connection establishment.
  test_ssh_transport.py::test_ssh_uses_exact_safe_argv_environment_and_stdin currently explicitly asserts that coupling, so this is a contract/test-design decision rather than an accidental untested branch.
  Review connection versus operation deadlines and cancellation/ambiguity semantics; no slow transfer was executed.

#### B-F098 — P3, wire byte limit is checked after process buffering.

execute_cluster_command captures entire stdout/stderr with subprocess.PIPE before _decode_response enforces MAX_RESPONSE_BYTES.
  A noisy or broken trusted remote executable can consume memory beyond the declared wire limit before refusal; stderr has no explicit bound.
  Timeouts bound duration but not bytes.
  Actual fake-executable tests certify argv/env/process capture, not bounded streaming.
  Record bounded resource handling as a future maintenance diagnostic; do not present this as an observed hostile-server attack or claim every protocol input is unbounded.

#### B-F099 — P3, staged payload lifetime and fault cleanup.

cluster_upload.py retains allocated partial and committed ready copies after installing the immutable object, with no cleanup/retention operation in these complete owners.
  A failed copy/verification/read-only conversion can leave a unique object temporary tree; create-before-receipt failures can leave unreferenced allocations.
  These may be intentionally recoverable/retained, but policy/ownership is not explicit here; no repository-wide absence of a janitor is certified yet.
  test_cluster_upload.py covers refusal/idempotence/read-only reuse, not these fault/lifetime intervals.
  Payload copytree also lacks explicit payload file fsync before parent publication, extending the qualified B-F083 durability discussion; metadata writers themselves do fsync.
  Future action must respect retained run inputs and selected/unrelated ownership, not delete staging indiscriminately.

#### B-F100 — P3, test-name oracle drift.

test_ssh_transport.py::test_response_rejects_duplicate_keys_and_non_boolean_retryability exercises duplicate JSON keys only.
  It does not reach a nonboolean retryable value despite naming both contracts.
  The implementation has a strict bool guard; expand/rename the distinguishing oracle later rather than claim a demonstrated product acceptance defect or delete the test.

#### B-F101 — P2, receipt recovery depends on renewed preflight availability.

cluster_submit.py validates/materializes the workflow, imports the factory and verifies current secret references BEFORE looking up an existing submit receipt.
  A previously accepted request whose response was lost may become unrecoverable through the same request ID when a secret or import disappears, although its run/dispatch receipt exists and replay is not needed.
  test_cluster_submission.py::test_cluster_pre_launch_is_snapshotted_before_idempotent_dispatch correctly retains copied script bytes after the original changes; it does not remove a required secret/import after acceptance.
  This is a qualified availability/acknowledgment risk, not duplicate execution or authority to accept changed/corrupt bundle bytes.
  Resolve immutable request/run recovery authority separately from preflight needed for a new dispatch.


### Complete-review checkpoint — reviewer-batch-17

#### reviewer-F039 — golden failure display uses a nonexistent public diagnostic field (P3)

Both example failure loops use `diagnostic.node` in `docs/source/remote_cluster_experience_spec.md` (the common laptop submission and later reconnect example).
Actual `cluster/run.py:375–383` returns `NodeFailureDiagnostic` values; `integration.py:212–242` declares/serializes `scoped_node_path` and has no `node` property or fallback.
The already completely read current how-to guide uses `diagnostic.scoped_node_path` correctly.
A returned node failure therefore makes the documented display code encounter an absent attribute rather than present the structured message; this is exact static evidence, not an executed failure.
The smallest future change is to use the public scoped field in both loops, preserving structured per-node failures and avoiding log parsing or another API alias.
Existing run-diagnostic serialization/round-trip assertions can remain the source counterpart; a new scheduler runtime test is not necessary for this example correction.

#### reviewer-F040 — common managed factory promise and golden binding omit actual processing environment identity (P2, source diagnosis required)

The golden `cluster/parsl.py` returns only `runtime.executor_binding(slot=...)`.
The following prose says that this automatically supplies environment identity and that the managed common path should not expose dependency hashes or repeated environment declarations.
The actual static flow is narrower:

- `parsl/factory.py:172–198` creates exactly one attestation for `runtime.environment_name`, with its deployment-derived environment identity.
- `cluster/_gateway_state.py:658–660` sets that name to `uv` or `existing-python` for the managed deployment.
- The golden processing class `ShapeProperties` declares `GENERAL_ENV` in `processing_tools.py:94–105`, whose name is `bioimageflow-general` and whose identity uses its actual scientific recipe.
- `cluster/client.py:434–447` passes the prepared workflow and validated bindings directly to `plan_distributed_execution`.
- `parsl/routing.py:82–92` matches exact attestation and worker-requirement environment identities; `:111–116` reports a missing attestation, with no generic deployment-name substitution in this flow.

The current `how-to/remote_cluster.rst` explicitly adds the selected processing tool's environment attestation in its factory, illustrating the current extra declaration needed for an actual tool recipe.
A deployment-wide assertion is not by itself the exact scientific environment declaration used by the ordinary processing route.
The golden uv manifest also contains orchestrator/common/measurement distribution dependencies rather than an explicit promise that worker-only scientific requirements are installed; those modules deliberately keep heavy imports out of main-process package metadata.
The narrow source evidence is thus a common-path binding/recipe obligation mismatch; it is not a reproduced scheduler failure, a proven package installation defect, or permission to bypass exact attestation.

After the full audit and precedence reconciliation, diagnose this first at the public factory/plan boundary with a real declared ordinary processing tool and retained complete identity; no worker or scheduler allocation is needed for that distinguishing diagnosis.
Resolve whether the current golden example omitted an explicit supported declaration or the approved managed API lacks the promised faithful derivation of exact tool requirements/compatible worker recipes.
Preserve the essential common-path simplicity, precise environment/Core compatibility and incompatible-environment refusal rather than changing the spec to silently accept deployment identities or turning all tools into a single arbitrary environment.
The library/backend owner must choose a bounded coherent public correction after evidence/review, not an example-only workaround that falsely declares installed science dependencies or narrows the reviewed promise to match source.
No implementation or diagnosis execution is released here.

The side-effect table's validation/planning **No writes** needs reconciliation against the current UI guide's explicit bounded temporary validation state; trusted selected-code side effects are separately acknowledged and neither wording authorizes a scheduler allocation.
That technical precedence check remains an explicit pending review item rather than an additional defect assertion now.

### Cross-repository prerequisite correction

Library/orchestrator manifests require Python >=3.10, Core >=3.9 and platform >=3.12,<3.15.
The previously recorded reviewer-batch-14/17 claims that the library Python >=3.10 authoring scaffold was stale incorrectly applied the platform minimum across repositories and have been withdrawn.
Original reviewer-F002 platform runner/prerequisite drift remains distinct; no library compatibility minimum change is justified by those removed claims.

### Complete-review checkpoint — root-batch-9

#### ROOT-F058 — P2 source retry/ownership gap: native destroy failure discards the still-live child window handle

DesktopApi.close_code_editor_window321–333 clears _code_editor_window before calling window.destroy.
If destroy raises, it returns False without retaining the window for retry; later close sees no child and a later open can create another while the old native child survives.
The full desktop test covers successful destroy and already-absent False, not a destruction exception and retained retry ownership.
This corroborates A-F105's frontend acknowledgment ambiguity: False can mean harmless absence or actual destruction failure, so treating every False as a failed close would also be wrong.
No native window/failure was executed; this is an exceptional source lifetime defect, with source-level uncertainty about OS-specific destroy behavior.
Preserve deliberate programmatic/manual event distinction and admitted window ownership; future correction should retain/report failed destruction without making unrelated windows or already-absent closes destructive.

#### ROOT-F059 — P2 source startup-lifetime gap: several failures after starting Uvicorn bypass shutdown

start_desktop starts the backend daemon thread at426, then waits for health, creates/configures the main window and registers callbacks before entering the shutdown-protected try at460.
A readiness timeout with a still-live backend, create_window failure/None or a callback/configuration exception can leave that started server without should_exit/join from this owner.
The strong existing test_shutdown_called_even_if_webview_start_raises applies only after entry into that protected try; the direct dead-thread readiness test needs no live cleanup and does not cover this interval.
Uvicorn/app lifespan remains the actual backend resource owner, so desktop's placeholder log lines are not evidence that no application cleanup exists.
No leaked backend/native startup was executed; eventual process exit and dead-thread failures mitigate some outcomes, but do not establish failure-safe cleanup for a surviving started backend.
Future diagnosis should distinguish each acquired lifetime from preacquisition failures and keep normal app lifespan as the cleanup authority.

#### ROOT-F060 — P2 selected-node presentation defect: a null toggle survives selection and shadows another node's accepted value

NodePanel.nulledFields177 is keyed only by field name; toggleNull470–480 stores True there.
The selected-node watcher401 resets list/name/tab state but never clears or scopes that null override.
isFieldNulled491 prioritizes the retained True over the currently selected node's actual parameters, so selecting another node with a same-name nullable field can hide its nonnull widget and show null.
Clicking its toggle can then restore the schema default instead of presenting the accepted value that was merely hidden by another node's local override.
A same-ID node in another canvas can share this state too; the complete UI store tests explicitly establish those valid separate identities.
No UI mutation was executed, and actual serialized parameters are not changed merely by selection; this is local presentation/next-action authority, not an asserted backend data loss.
The complete colocated NodePanel tests do not distinguish nullable toggling followed by another node/canvas selection; later broad parameter/widget source remains pending its separate owner.
Preserve explicit nullable behavior, connected-source presentation and accepted values; future state should derive from the current owned recipe or be scoped/reset with that node/canvas authority.

#### ROOT-F061 — P2/P3 qualified interface feature seam: the GUI forwards child DataFrames but not child fields or outputs

The complete NodePanel offers availableChildDataframes publication, while nested workflow field rows only edit bindings and the Outputs/exposure block requires nodeData.tool.outputs.
A's complete ToolNode authority confirms nested nodes carry their own workflow.interface while tool is null.
A's complete CanvasView toggleWorkflowInput supports the child DataFrame branch but child field IDs fall through ordinary tool metadata; toggleWorkflowOutput likewise uses tool metadata only.
Thus the current GUI lacks an equivalent child-field/output forwarding action despite the recursive public graph model supporting stable workflow ports.
Existing complete browser forwarding acceptance covers a child DataFrame port, not those other kinds; the component import smoke does not establish unified recursive editing.
This is a source capability gap with product-phase/GUI-promise qualification, not a demonstrated refusal of valid library workflow grammar or authority to remove that grammar.
After full specification precedence synthesis, determine which recursive editing capability is promised now and keep every essential binding/interface/source ownership feature; record a bounded coherent UI correction if required.
No speculative browser journey or extra source test is released here.

### Existing findings refined and maintenance opportunities

ROOT-F024's late-current-command hazard also has an exact NodePanel consumer: pickFile/pickFolder/pickFiles await a result and only then read the selected node/current canvas and tool predicate before updating parameters.
The complete usePathPicker returns the browser Datasets picker promise too, so this is not limited to modal desktop behavior; a node/canvas can change while selection is pending.
The path-picker tests resolve immediately and only inspect native call arguments; they do not establish captured node/incarnation/field admission at the actual update.
This extends the existing canonical captured-picker owner finding rather than adding a duplicated new ID.
Source URL reuse in DesktopApi focuses an existing child without navigating to a different admitted URL; producer workspace/port identity and intentional same-window policy still require A's full editor synthesis before a wrong-target claim.
NodePanel's numeric choices are displayed through String(value) while choice options retain their original types; complete Core/schema choice authority remains pending before alleging invalid allowed scalar behavior.
UI matchMedia listeners have no store-disposal teardown; ordinary single app lifetime mitigates this, and failure-safe repeated store/test disposal should be reconciled before a leak claim.
Desktop tests independently repeat min size/default size/resizable/confirm-close assertions already present in the exact full create_window call oracle, and an unused placeholder stop-timeout constant has its own tautological test.
Future suite optimization can consolidate those repeated argument/placeholder checks while retaining distinct server failure ownership, URL modes, OS icons, dialogs, entrypoint and drop ordering; no runtime saving is measured and no test has been removed.
The ordered placeholder shutdown-log test asserts log messages, not execution/Napari/shared-memory/settings effects; preserve actual lifespan/physical-worker counterparts as acceptance authority.
Native unsaved-close behavior is explicitly TODO and currently always allows close; full product-spec/recovery/close-owner reconciliation remains pending before claiming or altering a promised close contract.
All repairs and execution remain held; full source/test/spec review and independent completeness stay OPEN.

New full source total: 4989 lines / 8 inputs; root cumulative138/599,461 pending.


### Complete-review checkpoint — A-batch-18

#### A-F106 — High, source-established policy bypass: older editor routes omit configured webapp source-opening guard

Only /editor/open-node checks configured deployment mode and unsafe feature dependency at router66–70.
/editor/open157 and /editor/open-tool207 have neither policy dependency; the former passes an arbitrary existing absolute server path to EditorService and the latter resolves custom/catalog source then opens it.
/editor/status?launch=true139–146 likewise starts code-server, and workspace=true can materialize/expose the managed multi-root project.
EditorService.open_path reads live external_editor configuration but never deployment_mode; otherwise it launches loopback code-server with auth none/workspace trust disabled and can return a managed workspace containing writable workflow sources.
Actual app construction injects this service in webapp mode as well as desktop.
Normative v1 line694 says webapp unsafe=false disables local source-opening actions, specifically opening custom scripts; this omission is independent of ROOT-F002's mutation of a live Settings mode because it is reachable even when configured mode remains webapp.
Existing complete editor router tests all use default desktop config, and no mode allowlist/refusal assertion is present in these files.
No restricted-mode request was executed; severity refers to the direct source/contract mismatch, not proven remote exploit, arbitrary code execution or internet-exposed code-server.
Root owns the broader settings/deployment/security allowlist reconciliation and was notified.
Retain legitimate desktop catalog/node editor and managed workspace paths; future entrypoint policy must cover all physical server source-opening operations consistently rather than only the new node route.

#### A-F107 — Low/Medium, test false confidence: legacy-uninstall failure test never reaches uninstall

The exact selector test_embedded_manager_ignores_missing_legacy_opener_uninstall returns object() for --list-extensions and only throws if --uninstall-extension sairpico.opener is called.
_install_extensions410–414 enters _uninstall_legacy_opener only when the parsed stdout includes sairpico.opener.
With this fixture stdout is absent, installed is empty and the exception path never runs; the final assertions merely prove list/install/launch ordinary sequence.
The implementation actually catches uninstall errors and continues, so this is an oracle gap rather than an established production failure.
Retain the explicit compatibility cleanup and no unnecessary uninstall when absent; a future corrected existing fixture should deliberately advertise the legacy extension and require the failing uninstall invocation.
No diagnostic edit/test execution is authorized.

#### A-F108 — Medium, source command rendering defect: a single argv token containing both placeholders leaves one literal

_launch_external renders tokens with if '{file_path}' ... elif '{workspace_path}' at979–986.
A configured token containing both placeholders replaces file_path only and leaves workspace_path literally in the editor argument.
The normative external command API offers both placeholders without limiting them to distinct argv tokens; separate-token recommended examples mitigate common use.
Existing test_external_editor_focus_path_placeholder_prefers_focused_file has placeholders in separate tokens, so it cannot distinguish this branch.
No external program was launched here; failure concerns incorrect argv, not shell injection because launch remains argv-based.
Retain shell-free launching and exact project/focused file separation; future rendering should substitute both supported markers consistently in each argument.

#### A-F109 — Low/Medium, source error classification gap: malformed external command quoting escapes the declared launch error boundary

_launch_external's shlex.split at969 occurs before its try/except around process_launcher.
An external_editor string with unmatched quotes raises ValueError, while router /open and /open-tool catch only declared path/launch errors.
A malformed accepted setting therefore produces an unclassified internal failure rather than the existing logged503 launch response or an explicit invalid-configuration response.
Settings validation/command UX remain root-owned and could reject malformed input earlier; root must reconcile that admission before an end-user failure claim.
The complete service tests exercise process-launcher OSError, not malformed shell-like syntax; no request was run.
Retain original exception detail and single-error logging, and future parser admission must classify configuration errors without introducing actual shell execution.

#### A-F110 — Medium, qualified lifecycle race: shutdown does not exclude an in-flight launch from committing a new process afterward

EditorService.shutdown589–594 invokes manager.shutdown through asyncio.to_thread without its _embedded_lock.
EmbeddedCodeServerManager.shutdown521–530 reads/clears _process, while launch assigns _process after synchronous provisioning/install/spawn at382 or390 without a closing owner flag.
If shutdown runs while provisioning/launch is in flight and _process is still None, teardown returns and a later launch can publish a process that this shutdown never closes.
Actual ASGI lifespan request draining may exclude this overlap in normal shutdown; complete app/platform lifecycle authority is root-owned and must qualify its reachability, and this is separate from B's raw task cancellation execution-owner finding.
The complete editor service test file has no shutdown selector or held-launch/teardown oracle.
For injected legacy subprocess.Popen launch, manager only calls a close method if present, so non-managed objects are also outside its normal managed close protocol; current production default uses Wetlands ManagedProcess and is materially mitigated.
No leaked process, shutdown or spawn was observed.
Retain nonblocking event-loop teardown and managed process ownership; future lifecycle must prevent or retire late process publication rather than merely clear the current field.

### Existing binding finding extension and qualifications

A-F001's captured tool-binding authority also reaches editor presentation: open-node's non-owned branch ignores carried package/module/class metadata and calls resolve_tool_project_open_paths with live tool_name only.
Owned source_module explicitly bypasses that registry and is strongly verified by the actual execution tests above; ordinary unbound catalog nodes appropriately use current catalog source.
A carried non-owned portable v1 class alongside same-name active v2 can therefore execute its captured class after translator repair while still opening a live catalog v2 script, unless editor policy explicitly supports that rebind.
This extends the existing canonical binding seam; no duplicate defect ID, actual portable editor request or claim that every catalog refresh is wrong.
Node resolution releases workflow/snapshot locks before the physical editor open; path-based owner changes during long editor startup remain a qualified accepted-operation lifetime boundary, not a proven cross-incarnation script edit.
Nested source preparation may commit before editor launch later fails; existing retry reuses the private source, and client acknowledgements should distinguish accepted source preparation from successful presentation rather than assume failure rolled back bytes.
The VSIX 'matches source package' test checks name/publisher/version literals and a few substrings, not complete generated JavaScript equivalence; root/reviewer owns the actual extension build provenance/opaque archive boundary, so no stale bundle conclusion is drawn from these assertions alone.
Repeated response projection/path fixtures could be parameterized, while separate real owner bytes, actual worker rows, lexical symlink projects, single-launch concurrency and cold-workbench readiness must remain disjoint oracles.
No suite runtime gain or repair authorization is claimed.


### Complete-review checkpoint — A-batch-19

No new finding IDs. AppShell's held-startup and unmount oracle and the migration test's actual interrupted publication/restart preserve distinct authority boundaries; the broader lifecycle and admitted-writer risks remain A-F092/A-F082/A-F084. Both complete test judgments were formally transferred and current hashes checked; borrowed documentation/producer reads receive no credit here.


### Complete-review checkpoint — reviewer-batch-18

#### reviewer-F041 — experience effect table understates bounded validation writes (P3)

The previously completely reviewed `docs/source/remote_cluster_experience_spec.md:523–529` marks validation and planning as **No** for remote installs/writes.
Technical precedence instead explicitly permits bounded private temporary validation state in §8.1 and labels `validate()` **Temporary bounded state only**, with `plan()` permitting that state only if validation refreshes, in §16 (`remote_cluster_technical_spec.md:977–978`).
The current public how-to guide already makes the bounded temporary-state qualification.
The smallest later documentation correction is to carry that same qualification into the experience table, preserving no deployment installation, workflow run, DFK, worker allocation or implicit scheduler test during validation/planning.
This is a documentation inconsistency, not a demonstrated unexpected remote write or permission to expand the validation boundary.
Existing `tests/unit/cluster/test_lifecycle.py::test_deploy_prepare_validate_and_confirmed_plan_have_bounded_effects` and `::test_plan_without_validation_refreshes_validation_only` distinguish public transport/effect boundaries; no new scheduler test is required for this wording correction.
The pending check at the end of batch 17 is now resolved by the complete normative review.

#### reviewer-F042 — plan JSON illustration and acceptance count lag current strict public shape (P3)

Technical §18.2 (`remote_cluster_technical_spec.md:1060–1112`) presents `bioimageflow.remote_execution_plan.v1` JSON alongside its `from_dict()`/detached-summary behavior.
The illustration omits currently required plan keys `validation_expires_at`, `validation_evidence`, `executor_claims` and `task_policy`, and required node keys `kind`, `will_dispatch`, `tool_origin`, `environment_name`, `environment_identity`, `storage_mode` and `diagnostics`.
It also gives `incompatibilities` an array, whereas `cluster/plan.py:84–101` reconstructs a mapping via `.items()`; the strict plan decoder at `:317–342` requires all 18 public keys.
The example therefore is not a current round-trip payload, independently of its illustrative placeholder digest.
Its `cache_status="missing"` is also not a processing status emitted by the current producer: `cluster/client.py:456–472` forwards `execution_status`, `planning.py:288` derives `node_plan.status.value`, and `engine/common.py:412–417` contains six statuses including `corrupt` (no `missing`).
The already fully reviewed acceptance map `docs/source/reference/parsl_acceptance.md:24` still says **All five**; its existing linked `tests/integration/test_node_plan_status.py::TestNodePlanStatusValues::test_str_enum` explicitly asserts all six values including `CORRUPT`.

The smallest later change is to align the illustration with the actual public producer/serializer, or label an intentionally abridged summary clearly and avoid presenting it as the schema-v1 round-trip shape; preserve complete required identity/validation/route diagnostics in the real contract.
Use a current processing status and change the count to six rather than weakening corruption reporting or the strict decoder.
Existing `tests/unit/cluster/test_lifecycle.py::test_plan_digest_round_trip_is_stable_and_detached` already proves the actual DTO serialization/detachment contract; do not add a scheduler test or change the product API merely to accept a stale illustration.
No decoder call, schema red, site operation or runtime status was executed here.


### Complete-review checkpoint — reviewer-batch-19

#### reviewer-F043 — completed guide points acceptance gates at the resolved-decision section (P3)

`parsl_phase1a_implementation_spec.md:13,17,36,319,1087–1090` repeatedly refers to distributed acceptance **21.1–21.6** and submitted **21.7**.
The complete actual distributed document places acceptance at **20.1–20.7** (`:2036–2174`); §21 is a numbered list of resolved design decisions and has no those subsections.
The permanent `reference/parsl_acceptance.md` correctly maps the §20 family.
The smallest later correction is to align these exact guide cross-references with the current authority rather than infer unfulfilled behavior from a stale section number or duplicate the acceptance table.
Retain every real attached gate, separate submitted scope and the process-isolated smoke release requirement.
No file/schema test or new selector is required for this reference-only correction.

#### reviewer-F044 — completed implementation guide promises NumPy-only Core despite current worker-safe packaging dependency (P3)

The completed Phase1a guide says Core **keeps NumPy as its only dependency** (`:197`) and **must remain NumPy-only** (`:1021`).
Current Core manifest declares `numpy>=1.23.5` and `packaging>=24.0` (`packages/bioimageflow-core/pyproject.toml:28–30`).
Core's current viewer contract imports `packaging.specifiers` and `packaging.utils` (`bioimageflow_core/viewer.py:13–14`), and existing `tests/unit/test_core_package_metadata.py::test_core_declares_worker_safe_runtime_dependencies` explicitly asserts both names (`:139–146`).
The guide's premise is thus stale against the selected public viewer/version validation contract, not evidence of forbidden pandas/Pydantic/Parsl dependency leakage or a reason to remove packaging.
The smallest later correction is to name the actual small worker-safe dependency set and preserve Python3.9 compatibility and the excluded orchestrator dependency boundaries.
The existing manifest assertion is adequate; do not create a redundant test or change the product package to satisfy obsolete wording.


### Complete-review checkpoint — reviewer-batch-20

#### reviewer-F045 — manual graph-creation gesture contradicts current click ownership (P3)

Manual C4 says to **click a Processing Tool row** and drag a DataFrame Tool row onto the canvas to create tools.
The same completely reviewed guide C6 correctly says single-click toggles documentation and double-click adds a node.
Actual `components/panels/ToolsPanel.vue:910–915` binds click to `toggleDocumentation`, double-click to `onToolDoubleClick` (`:322–323` calls `canvasCommands.addToolNode`).
Existing `components/panels/__tests__/ToolsPanel.test.ts` assertions **single click on a rendered tool row toggles documentation without creating a node** and **double click on a rendered tool row creates exactly one node and emits add-tool once** already distinguish both behaviors (`:464–499`).
The smallest later correction is just C4's creation gesture to double-click, preserving drag creation and C6's single-click documentation behavior.
No product/UI change or new automated/manual test is needed for that text correction.

#### reviewer-F046 — future advisory-lock sketch omits its required user/workspace namespace (P3, future-only)

V3 §7.2 says claims coordinate **the same authenticated user** and workflow, but its fixed `BroadcastChannel("bioimageflow-lock")`, message field table and §7.4 localStorage key carry only workflow/browser/canvas identities, with no stable account/workspace discriminator.
The proposed proxy serves multiple user containers under one frontend origin; workflow-relative IDs can naturally repeat across distinct user workspaces.
The sketch therefore has no way to enforce its own same-user predicate when separate logged-in user/workspace contexts share the origin/storage domain.
It also must not present browser-local channel/storage coordination as a guaranteed cross-profile/device lock; backend draft CAS remains the actual authority and closes neither a user-namespace nor a single-writer UX promise by itself.
This is a future design clarification, not an implemented security defect, a proven browser race or a current campaign repair priority.
When that proposal is selected, define a non-secret stable account/workspace namespace for both channel messages and storage keys and explicitly state the browser-local coordination domain or choose a separately reviewed server advisory mechanism if broader single-writer UX is essential.
Preserve exact workflow/canvas claimant identity, revision conflicts and no automatic overwrite/CRDT expansion.
No speculative current product fix, additional test, authentication rollout or denominator/coverage change is authorized by this note.


### Complete-review checkpoint — B-batch-12

#### B-F102 — P2, public secret-alias configuration rejected at launcher handoff (source defect).

submission.py:125–137 projects all ParslConfigRef.secret_refs values into a tuple.
Distinct factory keyword arguments can legitimately reference the same opaque environment name; public config validation/building does not forbid that aliasing.
backends.py:87–100 rejects duplicated names, so such a valid public configuration fails at dispatch and the submission is marked failed.
test_backends.py::test_secret_reference_names_are_strict deliberately verifies backend-list uniqueness, but test_submission_api.py and test_psij_submission.py do not distinguish two argument names using one environment reference.
Future correction should reconcile the public projection with the backend's strict unique descriptor, retaining opaque references and secret non-persistence; no secrets or processes were used here.

#### B-F103 — P2, monitor start failure can escape terminal handling or prevent cleanup (source risk).

orchestrator.py:477 starts ClaimHeartbeat before the try/finally at :487.
Thread-start failure therefore leaves a claimed starting run without that handler's terminal/error reconciliation.
CancellationWatcher.start at orchestrator_monitor.py:103–105 starts its thread after a synchronous check; if thread.start raises, orchestrator.py:713 calls watcher.stop, whose join of an unstarted thread raises before heartbeat.stop and engine.close.
Sequential finally cleanup also means an earlier stop exception prevents later cleanup.
The full orchestrator/cancellation tests inject workflow and CAS failures but not thread-start/stop failures.
Future bounded lifetime correction should preserve one claim owner, cancellation projection and absence-confirmed recovery; this is not an executed leaked worker claim.

#### B-F104 — P2, engine close failure is always suppressed (source diagnostic/lifetime risk).

orchestrator.py:486 initializes durable_result to failed; the only later assignment is succeeded at :615.
The close exception handler at :723 rethrows only when that variable is outside the terminal set, a condition unreachable along these assignments.
Consequently failed close produces no error or retained cleanup diagnostic in these owners.
The orchestration tests have no distinguishing close-failure oracle.
Actual Parsl execution-lifetime cleanup still needs its full engine/future review, so this finding does not assert ordinary terminal success leaves active workers.
Retain durable committed success and avoid replay; make cleanup failure ownership/diagnostics explicit rather than roll back completed computation.

#### B-F105 — P2, launcher text redaction does not span writes (source confidentiality risk).

orchestrator.py:68–73 replaces known secret strings independently in each write.
A secret split across two writes is emitted without replacement, despite _RedactingTextStream's claim to redact known resolved secrets before Python text reaches logs.
__getattr__ also delegates buffer/fileno access, but this does not establish an obligation to intercept every native/subprocess output channel.
test_orchestrator.py::test_configuration_failure_never_persists_secret_value checks the persisted terminal error, not split CLI stream writes.
Future diagnostic must distinguish the documented Python text boundary and partial writes, preserving sanitization without assuming arbitrary output can be reliably scrubbed.

#### B-F106 — P3, orchestrator polling interval accepts nonfinite values (source validation/test gap).

run_orchestrator at :440 checks only <=0; NaN and infinity are not refused for poll_seconds.
Monitor Event.wait intervals occur outside the monitor's caught operation failure region; nonfinite values can fail polling without recording the monitor failure.
RemoteWorkflowRun.wait explicitly validates finite poll/timeout values, demonstrating inconsistent public timing validation.
Existing tests use finite intervals and do not distinguish NaN/infinity or bool inputs.
Record a future exact validation oracle; no thread or wait was run and no timing consequence measured.

#### B-F107 — P2, known heartbeat failure before workflow attachment does not prevent execution (source risk).

ClaimHeartbeat._run at orchestrator_monitor.py:65–78 records failure and returns; it cancels only if a workflow is already attached.
attach_workflow at :51 merely assigns the workflow.
During slow preparation, a failed renewal can therefore predate attachment; run_orchestrator does not call heartbeat.raise_if_failed until after _execute_workflow at :553.
If status/epoch checks still admit the transition, tool work may proceed after a known renewal failure and be reported failed afterward.
The full tests do not coordinate renewal failure during preparation.
Preserve strict claim fencing and no automatic replay; a future diagnostic must control this interleaving before any broader ownership redesign.

#### B-F108 — P3, duplicated directory durability helpers have different failure policy (maintenance/contract candidate).

pre_launch.py's directory sync propagates POSIX open/fsync failures, while the fully reviewed repository helper tolerates unsupported directory synchronization/OSError; other cache JSON owners lack directory sync.
Run-owned script snapshots otherwise correctly bound reads, validate bytes/digests, reject symlinks and install readonly content.
The complete pre-launch tests do not distinguish unsupported directory-fsync behavior.
Define where synchronization is required or best effort before consolidating helpers; do not erase essential durability or infer an executed filesystem failure.
This extends B-F083's qualified durability inventory rather than demonstrating ordinary crash loss.

#### B-F109 — P2, documented readonly remote inspection can schedule hard termination (source contract defect).

remote_control.py:74–76 promises inspection without mutating launcher state, then calls _open.
WorkflowRun.open reaches constructor run.py:145–154, which schedules hard termination for retained cancel_requested local/PSI/J runs with a configured grace period.
Thus inspect/read-progress/read-log and retry-plan opening can initiate a daemon lifecycle operation, not just observe durable bytes.
Reconnection resumption after an explicit prior cancellation may be intentional and must be retained under a clearly authorized operation; the mismatch is the readonly boundary.
test_workflow_run.py::test_reconnected_hard_cancel_uses_persisted_process_identity explicitly calls cancel after opening and does not distinguish inspection-only effects.
No inspection or process was executed during this audit.

#### B-F110 — P3, remote result test name asserts an unreached destination contract (test oracle gap).

test_remote_run.py::test_result_requires_absent_destination_parent_to_be_created_by_caller mocks a running run and expects not-succeeded refusal.
It never reaches result transfer or tests destination-parent creation, so the named contract is not certified by that test.
The state refusal remains useful; future rename or distinguishing succeeded-result oracle should retain that coverage rather than remove it as duplicate.

### Complete-review checkpoint — A-batch-20

#### A-F111 — Medium, documentation/CLI output contract mismatch: tutorials describe wider results than default compute returns

B confirms workflow/runtime.py312–337 wraps an untargeted root in WorkflowNode, whose engine output assembles only published interface mappings; runtime367–369 returns that boundary table.
The example CLIs call compute() without explicit terminal-node target.
Cell counting publishes only image/object_count but documentation describes the per-image phenotype summary/object features; low-SNR publishes restored_image/preview_image while prose says terminal table reports error/PSNR metrics; parameter publishes sensitivity/size/label_count/mosaic_path while its typical terminal row includes source path/output_image/foreground_fraction; BBBC publishes method/foreground_iou/foreground_dice while prose terminal table includes counts/overlay paths.
FISH publishes image_index and two averages, while prose terminal table also names total nuclei/marker associations; its CLI actually prints per-step heads, rather than a single final wider result table.
The wider values do exist in the terminal/intermediate node tables, so this is not lost scientific computation or a wrong metric claim.
Expected_outputs.yml deliberately names terminal_node and can validly describe that explicit target, but tutorials/CLI do not explain the difference; users following the shown command do not receive all described columns.
Existing factory test checks validation/export shape, not executed CLI output columns; no workflow ran in audit.
Retain explicit published interface boundaries and complete intermediate tables; future docs/recipes must either target the declared terminal table or describe the narrow root result honestly.

#### A-F112 — Low/Medium, manifest/source drift: parameter sweep requires a node name no longer in its graph

parameter_space_exploration/expected_outputs.yml required_nodes includes input_images at20.
The complete factory creates DownloadImages named download_cil_image at62; no input_images invocation remains.
The accompanying public page's conceptual input_images step is likewise a stale diagram/list label for an actual download source, though the overview correctly says the image is downloaded.
The root-owned factory self-contained test deliberately checks any DownloadImages class and absence of data_dir/output_dir, so it cannot distinguish stale required_nodes.
No manifest-consumer test executed; this is a definite declaration/name mismatch, not an execution failure.
Retain the source-download self-contained contract and stable actual node identity; future acceptance metadata/diagram should reflect that identity rather than invent another input node.

#### A-F113 — Medium, qualified scientific acceptance oracle gap: declarative expected outputs are not established by structural factory tests

Seven expected_outputs manifests declare counts, required terminal fields and selected quantitative criteria, including restored PSNR > degraded, minimum segmentation IoU and six-way parameter row counts.
The complete existing factory test public-loads/validates definitions and inventories factory source, but never executes tools, reads manifests or compares those values.
A Python-wide search found no expected_outputs.yml/data_manifest.yml consumption or custom helper scientific tests beyond the factory inventory; non-Python/release infrastructure remains reviewer-owned, so this is not a claim no external acceptance exists anywhere.
The data manifests' normal_ci supplied-data statements must not be interpreted as passing scientific execution evidence from these graph checks.
Retain graph-only safe ordinary validation and explicit opt-in external/model boundaries; future suite/records should identify actual acceptance consumers or label unexecuted declarative criteria, rather than duplicate structural tests and claim scientific verification.
No new test or expansion is authorized by this backlog item.

#### A-F114 — Medium, qualified custom merge identity risk: parameter and SAIRPICO summaries associate rows by position without verifying identity/cardinality

ParameterSweepResults.merge_dataframes resets indices of parameters/detections/counts independently and concatenates by ordinal, then broadcasts the first mosaic row.
DeconvolutionMetrics similarly iterates min(len(psf_denoised),len(deconvolved_table)) and associates each row by index position, silently truncating any extra table rows.
Their normal shipped graph derives the parallel branches from the same parameter/source lineage and the engine may preserve matching order, materially mitigating the original recipes.
When an adapted upstream transform changes order/cardinality, these public DataFrameTool implementations can assign settings/PSF/input to a different output or omit unmatched rows without an explicit identity refusal.
This is a conditional extensibility/robustness risk, not an executed wrong scientific result or a claim the default engine reorders ordinary mapped rows.
No complete dedicated helper oracle was found by the Python source/test search, and factory validation cannot inspect data-row correspondence.
Retain the actual row provenance expected by the public worker/cache protocol; future helper contracts should require/verify shared row identities or document and refuse incompatible ordinal inputs rather than silently truncate.

#### A-F115 — Low/Medium, declaration debt: workflow-local produced image paths are plain strings without image/viewer semantics

RestorationPreview, BBBC reference/input/overlay producers and parameter mosaic summary outputs declare actual image file paths as str; several corresponding workflow inputs are bare Path.
The reviewed public image/viewer contract derives compatibility from declarations, so path-looking text alone cannot establish image layout/semantic/viewer requirements.
These local images therefore lack intended image semantic/layout declarations available from ImageSpec/ImageFile-bearing package tools; actual model outputs and manual path inspection can still work.
The complete public viewing derivation marks an available plain-str output schema known with viewer=None; it does not mark it unknown merely because the path lacks ImageSpec.
This is declaration/consumer capability debt rather than a default viewer crash, compatibility rejection, or a demand to guess semantics from local bytes.
Unknown guidance is appropriate when authoritative metadata/schema is unavailable, independently of these known no-viewer declarations.
Marker image/nuclei bindings already carry ImageSpec semantics, showing the available explicit authority in the same examples.
The structural factory test and current manifests do not check the local image declaration/viewer boundary.
Retain unknown-snapshot independence and supplied image validation; future example declarations should state intended semantics/layouts rather than implicitly treat every str path as an image.


### Complete-review checkpoint — reviewer-batch-21

#### reviewer-F047 — demo exporter deletes its curated input tree before replacement publication (P3, source-only)

The exporter legitimately consumes library Python examples and platform-owned tool sources; `docs/developer/workspace-storage-and-demos.md:115–123` declares that mixed ownership.
Actual `_render_definition` reads curated source bytes from the current **OUTPUT_DIR** at `export_demo_workflows.py:205–207,247–250` to include FishLabelOverlaps/AverageSpotsPerNucleus and SpotMaskMetrics/ParameterSweepResults in the staged bundle.
Write mode fully renders and stages first, but then calls `shutil.rmtree(OUTPUT_DIR)` before `staging.rename(OUTPUT_DIR)` (`:366–367`).
A process interruption or rename failure in that gap removes not just derived workflow JSON but those maintained source inputs; the command cannot reconstruct them from the library examples alone on a subsequent invocation.
This is a statically identified maintainer publication failure boundary, not an executed loss or a live application/workspace mutation.
The repository makes it recoverable through version control, so it is below user-data publication/admission priorities and does not authorize repair now.

The smallest later correction should retain the old complete source bundle until replacement publication is secured and preserve/recover the curated authorities on failure, without inventing another global storage transaction framework or silently treating human tool sources as disposable generated output.
An explicit recoverable sibling backup/swap policy is a candidate once the source authority and failure semantics are independently reviewed; no code, test or generator execution is released here.
Existing demo service tests prove installed-demo ownership/version/reuse, not this maintainer CLI rename boundary; do not credit them as publication-failure proof or rerun app/browser suites for a future producer-only correction.


### Complete-review checkpoint — B-batch-13

#### B-F111 — P2, export installation can replace a concurrently appearing empty directory (source ownership risk).

result_download.py:428 and :507 use os.rename(candidate, destination) after earlier absence checks and catch FileExistsError.
On POSIX, renaming a directory onto an existing empty directory can succeed; that exception is not a no-clobber guarantee.
A distinct empty destination appearing during download/export can therefore be replaced rather than refused.
The local path has another exists check immediately before rename, but the check and rename are still separate operations.
test_result_bundle.py::test_local_run_result_destination_is_atomic_and_idempotent and ::test_local_export_rejects_a_different_self_consistent_bundle establish retained manifest identity, not coordinated empty-destination arrival.
Future exact diagnostic should establish selected destination ownership at install without weakening atomic publication, idempotent same-bundle reuse or explicit destination-parent policy.
This differs from B-F080's directory backup/replacement behavior; no filesystem race was executed.

#### B-F112 — P3, return candidate initialization is outside cleanup scope (source failure-isolation risk).

returns.py:212–214 creates the candidate and its dataframes/assets children before entering try.
A child mkdir failure can leave a partially initialized candidate with no cleanup by this owner.
Later serialization/validation failures are correctly cleaned inside try; this gap is limited to initialization.
The full return tests do not inject either child mkdir failure.
Extend staged-tree lifetime ownership (B-F099) with a bounded future fault oracle; do not infer successful returns are corrupt or authorize deleting unrelated temporary trees.

#### B-F113 — P2, record-backed shared locator does not attest returned array contents (source provenance risk).

return_assets.py:_record_shared_locator (:195 onward) selects an exact provider route and row label with matching shape/dtype metadata.
It never compares the returned SharedArray's bytes or another immutable identity to the selected record asset.
A different or modified array with the same row/shape/dtype can therefore select the old immutable asset when a route still names that provider; reloading exports the record bytes rather than the supplied return bytes.
Ordinary unmodified processing/root/passthrough paths are covered and valid; this does not prove a default tool changes arrays or that every DataFrameTool mutation must preserve upstream authority.
test_returns.py::test_record_backed_shared_array_uses_raw_exact_record_locator checks expected values from an unchanged root output, not same-shape changed contents or reordered lineage.
Future diagnostic should distinguish actual bytes and permitted passthrough/merge authority before selecting an implementation; retain exact immutable record ownership and fail-closed ambiguous routes.

#### B-F114 — P2, external reference validation depends on receiving host filesystem (source portability risk).

return_schema.py:_validate_locator requires external path.resolve(strict=False) to equal the serialized string.
The same validator runs for downloaded bundle manifests on the client in result_download.py:_load_manifest.
A cluster-normalized unowned reference can therefore be refused because the corresponding spelling is a symlink on the receiving host, although external references are intentionally not copied or verified as local owned assets.
return_assets.py:_external_locator normalizes on the producing host; those two filesystem authorities can differ.
This extends B-F090's host-dependent path interpretation, while explicitly distinguishing unowned return references from marked/copied cluster inputs.
Existing external and Arrow string-extension return tests run on one host and do not distinguish receiving-host symlinks.
No remote host, path mutation or symlink was accessed beyond reading code; preserve explicit external-reference labeling and owned-asset confinement.

#### B-F115 — P1, shared helper permits process-local object dtype representation (source safety risk).

Core shm.py:create_shared_output accepts any NumPy-coercible data, allocates arr.nbytes and constructs a same-dtype shared ndarray without rejecting dtype.hasobject.
Core open_shared_array and io.py:load_image likewise trust SharedArray.dtype without rejecting object-containing dtypes.
Object-containing NumPy representations hold process-local Python object references and are unsuitable as raw bytes for cross-process readers; the worker-safe SharedArray descriptive dataclass imposes no dtype safety validation.
This is an unexecuted public-helper safety candidate, not evidence that existing scientific tools produce object arrays or that all worker codecs accept them unchecked.
The full shared-memory/return tests use numeric types only; worker-envelope validation remains next-batch pending.
Future exact diagnostic should reject unsupported object-containing storage before allocation/attachment while retaining numeric/structured non-object layouts and declared metadata validation.

#### B-F116 — P2, scalar and empty array helper behavior lacks a declared restriction (source behavior/contract gap).

create_shared_output uses arr[:] on both sides; a zero-dimensional scalar array cannot follow that indexing path.
An array with zero total bytes reaches SharedMemory(size=0), which does not represent a positive-size segment.
SharedArray permits empty shape and zero dimensions, and return_schema.py explicitly permits zero dimensions; no common positive-size/non-scalar contract is declared in these owners.
This is separate from object dtype safety: valid numeric scalar/empty data requires a supported representation or an early documented refusal.
Existing helper and cache tests use positive-sized vectors/matrices and do not distinguish either case.
If assignment fails after allocation, the helper closes without unlinking, so it also leaves a segment for a failed operation whose caller never received a reference.
No arrays/segments were created during review.

#### B-F117 — P3, direct shared helper test retains an unowned allocation (test isolation/oracle gap).

tests/integration/test_shared_memory.py::TestSharedMemoryHelpers::test_create_shared_output_and_open allocates a segment and exits without unlinking it.
Its comment assigns cleanup to the engine, but this test calls the helper directly and has no engine holding that allocation.
Other full tests explicitly unlink in finally, showing a feasible existing cleanup convention.
The cache-persistence test compares two DataFrames but supplies no producer-call/cache-hit oracle or complete segment ownership oracle; equality alone is not a cache-hit proof.
Record per-test cleanup and distinguishing cache evidence as future improvements, not an executed leak count or blanket invalidity of the shared-memory suite.

#### B-F118 — P2, failed public-return hydration does not unwind earlier allocated segments (source lifetime risk).

returns.py:_rehydrate_public_return walks locators and _load_shared_array creates persistent shared outputs as it goes.
If a later locator/array allocation fails, earlier allocated references are not unlinked before raising and no returned DataFrame exposes them to the caller.
File/tree/manifest validation is strong and happens first, reducing ordinary integrity failures; it cannot guarantee later allocation succeeds.
The same hydration occurs after local/remote export destination installation, so a failed acknowledgment may leave a valid installed bundle while transient allocation ownership is lost.
Core create_shared_output deliberately closes but does not unlink; successful references are caller-owned and must remain usable.
Full tests clean successful references, but do not fail a later hydration after one succeeds.
Future fault oracle should retain installed immutable identity and successful-reference lifetime, clean only failed-handoff allocations and avoid computation replay.

#### B-F119 — P3, bundle digest test reaches schema refusal only (test oracle gap).

test_result_bundle.py::test_bundle_digest_corruption_is_rejected writes a manifest with schema=wrong.
It asserts schema refusal and never reaches a valid-schema bad digest.
Other tests meaningfully cover tamper/retained identity and duplicate keys, so this is a named-branch distinction rather than a claim that digest validation is absent.
Future rename or valid-schema digest oracle should retain the existing schema refusal and avoid duplicate broad integration coverage.


### Complete-review checkpoint — root-batch-10

#### ROOT-F062 — P2 qualified live-output completion race: a final event can arrive between an empty poll and the separate EOF check

ManagedProcess.events1035–1040 awaits _next_event(cursor,0.1), then separately checks _streams_closed when that poll returned None.
A reader can publish the final event and the supervisor close the streams after the empty timeout return but before that second check; the observer then returns without checking its still-pending cursor event.
wait_for_line1062–1064 has the analogous separate empty-return/EOF check and can refuse a final matching event.
The complete managed-process guide promises every retained event available to the observer is yielded and readiness examines all output before EOF.
Existing async interleaving and trailing-partial tests are useful real-process checks but do not hold this specific empty-return/publication/closure interval.
No event loss was executed; this is a source-established possible interleaving, not measured flakiness or an assertion that ordinary completed-process replay drops events.
A future distinguishing oracle should control that interval and keep closure plus pending-cursor admission consistent; preserve independent observers and bounded lag semantics.

#### ROOT-F063 — P1/P2 qualified identity gap: launched POSIX cleanup stops revalidating ownership after the direct leader has exited

terminate_launched_process_tree80 validates start/session identity only when process.poll() is None, then sends signals to the recorded numeric process group.
ManagedProcess._kill_tree739 has the same leader-running predicate before direct killpg.
If the original group has disappeared and a delayed cleanup resumes after that numeric leader/group identity is reused, a cached exited Popen does not establish ownership of the newly existing group.
The attached exited-leader path instead explicitly enumerates recorded-session membership and rejects a newly reused leader in recorded_posix_group_exists; this stronger existing authority must be preserved.
Current PID-reuse tests exercise attached live mismatch, not launched/reaped leader followed by group reuse before signal admission.
No PID reuse, signal or unrelated termination was executed; this is conditional source identity debt, mitigated by the normal prompt supervisor cleanup and the OS's group lifetime, not a claim routine descendant termination targets unrelated processes.
Future diagnosis must distinguish genuine remaining descendants from a recycled isolated group and retain legitimate cleanup after natural wrapper exit; simply refusing every exited leader would break that supported feature.

#### ROOT-F064 — P2 qualified internal callback reentrancy hazard: ProcessLogger invokes subscribers under a nonreentrant state lock

ProcessLogger.subscribe52 and live notification134 invoke application callbacks while holding threading.Lock; get_output/update_log_context/subscribe acquire that same lock.
A callback that synchronously inspects captured output or updates/subscribes can deadlock its reader or the historical subscribe caller; a blocked reader can then retain pipe/cleanup ownership.
This is an internal subscriber capability risk: current worker startup uses its output access from another thread, and ordinary trivial callbacks do not establish a shipped production deadlock.
Full test_process_logger mocks/manual callbacks never call back into the logger; its real-process subscribers append only, so they do not distinguish reentrant access.
Record a bounded future callback contract/diagnostic before changing synchronization; moving callbacks out of a lock alone does not make arbitrary blocking callbacks safe.
Retain ordering/history and owned reader shutdown, with explicit callback exception policy.

#### ROOT-F065 — P3 internal readiness lifetime debt: ProcessLogger.wait_for_line never releases its subscription

wait_for_line creates a closure retaining its predicate/event/result, appends it via subscribe and returns after match or timeout without removing it.
Repeated readiness checks therefore retain every previous callback and execute their predicates on later output for the rest of that logger's lifetime.
The managed public event model does not share this subscription list; do not claim its bounded observers leak this way.
No repeated-service memory growth was measured; source retention is exact, while severity depends on use frequency/lifetime.
Existing timeout/matching tests inspect only the return and do not establish subscriber count or post-completion predicate retirement.
Future internal subscription ownership should expire on both outcome paths while retaining external long-lived subscriber behavior.

#### ROOT-F066 — P3 source/API mismatch: ProcessLogger historical readiness returns the last matching line despite promising the first

wait_for_line's callback overwrites found_line for every matching historical entry while subscribe replays the entire _output synchronously.
With two matching history lines, the result is the later line although its docstring promises the first matching line; a subsequent live match can also overwrite the winner before return.
The existing test manually calls its private callback once, so neither actual reader/replay behavior nor first-winner selection is distinguished.
No process/readiness execution occurred; preserve historical replay and define an immutable first match rather than removing the useful readiness feature.

#### ROOT-F067 — P3 source/test gap: file logger duplicate prevention compares an absolute string against the caller's unnormalized Path or relative string

logger.enable_file_logging109 compares logging.FileHandler.baseFilename to filepath before converting its Path or resolving a relative string.
Repeated calls with the same documented pathlib.Path create multiple handlers; relative string calls also disagree with the handler's absolute path.
The complete integration test named test_file_logging_prevents_duplicates calls twice with a Path but only asserts the file exists, so it never certifies duplicate prevention.
Its file-logging tests also leave newly attached global handlers/levels alive; several otherwise strong console/handler tests restore state in finally, demonstrating a maintainable existing isolation pattern.
No handlers were created during audit; normalize the actual destination identity before comparison and use an exact handler/log-count oracle later, with cleanup independent of assertion success.
Retain user-configured file logging and do not make every logger convenience call trigger a new broad suite.

### Existing test-suite optimization opportunities and qualifications

Several test_process_logger subscriber/error tests manually reproduce the callback loop or mutate _output; their assertions certify their own test code more than actual _read_stream behavior.
Keep real pipe/startup/cleanup and stream-context integration oracles, replace or rename those weak claims after the review rather than add another broad mirrored layer.
The managed-process fixture returns an environment without unconditional cleanup of its retained child list; many tests close only on success, and fixed short sleeps control live interleaving/readiness.
These are targeted fixture/coordination improvements, not measured speed gains or permission to delete distinct real-descendant/Windows/thread-start semantics.
The POSIX verifier intentionally ignores inaccessible unclassified processes and fails closed for known members with unknown status; the existing test explicitly chooses that boundary, so no new blanket uninspectable-members defect is asserted without a stronger supported-platform contract.
Windows Job-close and recursive fallback differ in their physical verification boundary; exact real Windows acceptance remains pending, and no mock is promoted to that certificate.
M1 remains OPEN; all fixes, diagnostic tests and campaign execution remain held.

Thirteen new full inputs / 4598 lines; root cumulative151/568,417pending.

### Complete-review checkpoint — root-batch-11

#### ROOT-F068 — P3 source recovery isolation gap: malformed quarantine state containers abort discovery instead of remaining individually untouched

environment_cleanup._read_record validates state through membership in _VALID_STATES without first requiring a string.
A well-formed candidate JSON with otherwise valid record fields and a list/dict state raises TypeError outside the caught parse block, aborting discover_quarantined_environments's loop rather than skipping that entry.
The background scanner catches/logs the whole discovery error, so subsequent valid orphan tombstones may remain unreclaimed; already queued records and later repair/wake can mitigate it.
B confirms its complete test_reclaimer_ignores_malformed_and_unowned_quarantine_entries uses syntactically broken JSON, not a valid JSON container state.
No malformed file or reclamation was executed; this is static recovery availability/diagnostic debt, not authorization to erase ambiguous entries or a proved unauthorized deletion.
Future exact refusal should isolate each bad record and preserve all known token/inode ownership requirements.

#### ROOT-F069 — P1/P2 qualified provisioning lifetime gap: unverified process cleanup discards the runner's physical retry owner

ProcessTreeRunner.run's finally clears _active/_active_job even when tree termination, child reap or reader completion supplied cleanup_errors.
It returns a structured failure rather than a false clean cancellation, but terminate_active can no longer reach that process after the failed terminal handoff; the next provision cleanup can quarantine the environment tree without a registered managed-process owner for the unresolved provisioning command.
The complete real stream tests retain a blocked reader's close ownership, and injected tree-verification errors normally first kill the process or let a short command finish; they do not keep an actual survivor across the cleared owner and retry/name reuse.
Manager close drains operation runners but a terminal FAILED operation does not itself prove that an unresolved external tree is physically dead; no additional durable provisioning survivor registry is evident in these fully reviewed owners.
This is conditional failed-cleanup ownership debt, distinct from ROOT-F053 ExecutionTask early canceled acknowledgment and from supported disk reclamation after proven name detachment.
No surviving command or filesystem removal was executed; retain honest failure status and diagnose an exact retained survivor before choosing retry/fencing ownership.
Future correction must preserve identity-safe refusal and not signal an unverified group or silently reuse/delete its generation.

#### ROOT-F070 — P2/P3 qualified crash-durability asymmetry: worker registry replacement omits its parent directory synchronization

runtime_state.atomic_write_json flushes/fsyncs the temporary worker/controller/pool registry file then replaces the destination without synchronizing the parent directory.
The auth-key publisher in the same fully reviewed module explicitly fsyncs its parent after replacement, and provisioning/quarantine publication does too.
Those different source durability boundaries matter to the crash-recoverable persistent worker journal; atomic ordinary readers alone are not a complete crash-publication contract.
Current tests verify ordinary byte identity, concurrent key publication, state corruption, commissioning and descendant reconciliation, without establishing registry replacement durability under crash/power loss.
No crash or record loss occurred; this is a documented durability-policy/diagnostic candidate, conditional on supported filesystem/platform guarantees and contract strength, not a claim every registry update loses workers.
Reconcile required versus best-effort directory sync and preserve existing full-record retained cleanup before any helper consolidation.

#### ROOT-F071 — P2 source lockfile contract gap: late post-install/validation changes to a supplied lock are accepted into ready metadata

The complete dependency guide says Wetlands rejects any lockfile change during locked provisioning.
provision_environment checks supplied_lock_hash immediately after pixi-install, but later post-install commands and validate-runtime run without --locked and final lock/manifest reads publish their new hashes without comparing to the supplied bytes again.
A trusted post-install command that changes pixi.lock after the initial check can therefore complete readiness with a different lock, contradicting that refusal promise; normal no-mutation recipes remain sound.
Existing test_modified_supplied_lock_fails_and_removes_incomplete_target modifies the initial install phase only; positive supplied/local-lock tests' fake Pixi does not simulate resolver mutation during run.
No lock, command or resolver was executed; do not imply ordinary model download post-install necessarily mutates dependencies.
Future narrow fault oracle should change the lock only in that later admitted stage and preserve exact locked identity/refusal through final ready publication; retain legitimate post-install assets and managed-runtime validation.

#### ROOT-F072 — P3 source diagnostic boundary: an oversized integer timestamp escapes the declared corrupt-registry error type

runtime_state._is_positive_number converts any exact int to float without handling OverflowError.
A valid JSON integer much larger than float range can reach this timestamp validator in an otherwise well-shaped worker/controller/pool entry and raise outside RuntimeRegistryError's typed refusal.
The registry still fails closed and remains unchanged; this is diagnostic/error-classification consistency, not an accepted invalid worker or code execution risk.
The complete corrupt-state tests cover JSON/type/version/missing fields and inaccessible state, not an oversized positive integer timestamp.
A bounded later validation should preserve finite-positive/exact-bool refusal and ordinary timestamp meaning without rewriting the registry or treating corruption as missing.

### Additional test and architecture decisions

test_v2_provisioning is a broad1,216-line module mixing recipe/lock/local-source/publication tests with actual persistent workers; narrower feature selectors and separation by dependency boundaries are suite-maintenance candidates after the whole review.
Do not split by speed alone or duplicate actual shared lifecycle fixtures: filesystem/no-follow oracles, locked metadata assertions, real worker admission, cancellation and persistent restart each prove different things.
Many fake-Pixi tests establish orchestration/materialization/refusal while substituting installation/version resolution; complete marker/global-CI review must keep them distinct from pinned real Pixi/external package certification.
The stream blocked-reader test explicitly proves bounded failure retains reader-owned close; moving pipe close to the parent would invalidate its physical boundary.
A Thread.start exception after actual OS start can leave the reclaimer's _thread reference unpublished and allow another worker on later wake; the cross-process purge lock still serializes tree deletion, so do not equate this exceptional bookkeeping possibility with concurrent destructive purge without a discriminating oracle.
Several helper constructors/mutators assume validated internal values (positive worker count etc.); type-surface tightening should preserve actual public manager validation and not invent supported invalid-call cases.
Ready publication followed by journal-unlink failure currently enters provisioning cleanup; determine postcommit failure/ack policy before calling that intentional operation rollback a proven data-loss bug.
Canonical quarantine and worker registry JSON have weaker duplicate-key/shape guards than strict worker protocol; trusted local-state and fail-closed status must be retained when deciding whether to consolidate readers.
M1 remains OPEN; repairs, new diagnostics and all campaign execution remain held.

Ten new full inputs / 6983 lines; root cumulative161/565,404pending.


### Complete-review checkpoint — A-batch-21

#### A-F116 — Low, conditional snapshot invariant debt: frozen manifest contains a mutable output dictionary

viewing.py64–76 defensively copies input entries and validates complete against their statuses, but assigns an ordinary dict to the public Mapping field.
A caller can mutate manifest.outputs after construction and leave complete=True while inserting an unknown entry, or remove an entry without recomputing completeness; to_dict78–86 does not revalidate.
The frozen dataclass prevents attribute assignment but does not enforce immutability of this nested dictionary.
Normal public derivation/inspection constructs fresh valid manifests, and no reviewed consumer mutates outputs, so this is a public invariant/lifetime debt rather than an observed archive corruption.
The strict wire tests validate construction and malformed dictionaries, not post-construction mutation.
Retain defensive input copying and offline inspection; future snapshot policy should explicitly make the mapping immutable or revalidate at serialization rather than imply deeper freezing.

#### A-F117 — Medium, qualified nested partial snapshot completeness omission

viewing.py120–154 recursively visits present nested nodes, but expected-minus-present detection164–172 runs only for the root workflow.
Materialization.py406–426 propagates partial mode into children and retains their build errors; interfaces.py514–516 tracks each child's own expected names.
A retained partial child with an unavailable internal tool and no surviving interface output requiring that tool can therefore omit its missing scoped wildcard entry, while all remaining entries are known and complete is computed True.
The root-level missing tool path is represented correctly; strict ordinary imports refuse missing tools, and a child whose output resolution raises may refuse earlier rather than emit a misleading snapshot.
This is a source-level completeness risk for supported partial materialization, not a claimed failure of the existing missing-module archive-inspection test or a performed partial export reproduction.
The current recursive viewer test has fully loadable children, and the offline missing-module test inspects a previously complete carried archive, so neither distinguishes fresh derivation from a retained partial child.
Retain imported carried snapshot independence; future derivation should account for missing scoped expected nodes at every visited definition, with refusal versus unknown explicitly preserved.

#### A-F118 — Medium, qualified installed-origin authority risk: distribution declaration is checked but actual imported module file is not

Core worker_origins.py589–602 verifies the named distribution/version and whether it advertises the requested top package, then calls ordinary import_module.
Unlike shared425–450 and versioned476–525 branches, it does not verify that the actual module selected from sys.modules/sys.path belongs to that distribution's resolved installed/editable source.
With an already imported or earlier-path same-name module, matching distribution metadata does not by itself prove the loaded ProcessingTool class came from the captured installed origin.
Ordinary environments with unambiguous imports are sound, and arbitrary trusted Python code can deliberately modify import machinery; no current deployment shadowing or hostile execution is asserted.
The exact test_installed_module_requires_explicit_distribution_identity uses the already correct Core module and verifies class identity, so it cannot distinguish the alternate module case.
Archive loading also relies on isolated import after tree/path verification without a final loaded-file check582; clearing the selected top-package and prepending materialization root materially mitigate normal resolution, so this remains a qualified adjacent consistency concern rather than a separate confirmed escape.
Retain public ProcessingTool validation, exact version and origin identity; future origin policy should prove actual imported source membership where it claims a distribution-backed origin, not substitute display names or metadata alone.
This is executable origin loading, distinct from portable platform rebinding A-F001/A-F066 and cache signature B-F067.

#### A-F119 — Medium, qualified versioned import failure/retry ownership risk

Core worker_origins.py503–514 installs a scoped package into sys.modules before executing its initializer; an exception does not remove that partial package.
A later identical retry sees scoped_root already present and skips initialization, potentially loading a submodule against incomplete package state or repeatedly failing even after transient initialization prerequisites recover.
Final target path verification still runs, and many packages have trivial initializers or import failure prevents tool instantiation entirely; this is not a universal successful wrong-class claim.
The source-file branch418–421 cleans its owned module on execution failure, while this versioned branch lacks the analogous failure cleanup.
The transferred origin-construction tests cover Shared/Installed branches only; no reviewed selector here establishes versioned initialization retry behavior.
Retain scoped version isolation and exact source-path verification; future retry ownership should discard only the failed package/module incarnation it created without damaging unrelated live imports.

### Existing A-F026 extension — Qualified source hash versus stale timestamp bytecode axis, not a new result-cache finding

Core worker_origins.py405–418 hashes the source bytes, then delegates execution to the normal file-location loader.
That loader may use timestamp/size-valid cached bytecode for the same path after a same-length edit within filesystem timestamp granularity, despite the new origin source_hash and new private module name.
This is a separate mechanism from the already reviewed same-source-ID custom class cache, but shares the requirement that executable code match the captured source digest.
No such edit or bytecode reproduction was executed; content-addressed/stable source paths and ordinary timestamp changes mitigate normal use.
B confirms no duplicate canonical bytecode/source-import finding; B-F067 concerns result signatures, not loading executable bytes.
Retain source digest validation, private module names and origin-keyed caching; future diagnostic should distinguish source bytes, cached code and actual returned worker class before proposing a repair.


### Complete-review checkpoint — B-batch-14

#### B-F120 — P2, failed DFK cleanup loses the owned retry reference (source lifetime risk).

parsl/engine.py:_cleanup_owned_dfk (:650–657) clears _active_dfk before dfk.cleanup().
If cleanup raises before releasing all resources, the engine no longer retains that DFK for a retry; execution-lifetime execution can admit a new DFK afterward, while close has already made the engine closed.
A later close returns immediately because _closed is true, so explicit close failure is not retryable by that handle either.
The cleanup exception is raised by _finish_execution, so this is not silent ordinary success or evidence that all DFK cleanup fails.
test_engine_lifecycle.py::test_engine_lifetime_reuses_owned_dfk_until_idempotent_close and ::test_execution_lifetime_creates_and_cleans_one_dfk_per_execution exercise only successful cleanup.
Future diagnostic must fail cleanup after a retained partial resource, assert exact owner/retry behavior and retain external DFK nonownership and registered-future drain.
This shares a failure-reference pattern with B-F002 but is a distinct Parsl resource owner.

#### B-F121 — P2, simultaneous close calls do not share a completion barrier (source concurrency risk).

ParslEngine.close at :768–774 marks _closed before cancelling/draining active execution; another close sees true and immediately returns.
That second successful return can therefore precede the first closer's physical future drain and owned cleanup, despite close's public drain promise.
Single-close behavior is sound and coordinated with active execution; a closed flag alone does not establish completed closure for overlapping callers.
test_engine_lifecycle.py::test_close_waits_for_noncancellable_writer_before_owned_cleanup establishes the first closer's wait, not a second concurrent close.
Future diagnostic should coordinate two closers with one registered running writer and preserve caller-owned DFK isolation, same-thread execution close behavior and idempotence after completed closure.
No concurrent close was executed during audit.

#### B-F122 — P2, terminal diagnostic failure stops only its local collector (source failure-projection risk).

BoundedParslCollector.run at submission.py:329–342 catches task_terminal failure, records pre_submission_error and cancels its own active window.
Unlike pre-submission/task-result failures, this branch does not call failure_observed, so ParslEngine._report_task_failure does not set the shared sibling stop flag at that point.
Other parallel node collectors may continue submitting/processing until their own natural completion before the scheduler returns the failing node.
The actual terminal hook writes storage diagnostics, so this is a fault-path metadata failure rather than an ordinary worker failure or a claim that all diagnostic failures require immediate global cancellation.
Full submission tests distinguish iterator/runtime validation/task failures and deterministic late sibling errors, but not a failed terminal diagnostic writer.
Decide this failure policy and use a narrow coordinated oracle before correction; retain deterministic primary errors, full drain and no replay.

#### B-F123 — P2, collector cancel exceptions can bypass its own drain contract (source failure-isolation risk).

submission.py:204–209 stop_and_cancel calls future.done/cancel without the exception isolation used by ParslEngine._request_submitted_cancellation and _report_task_failure.
A cancel exception exits run while other futures remain active; the collector alone does not run a finally drain or report all task-terminal callbacks for them.
The actual ParslBackend registers every submitted future with ParslEngine, whose execute finally still drains them, so this is not a demonstrated default physical writer escape.
That mitigation does not restore the collector's diagnostics/primary-error behavior or cover standalone callers of its documented drain helper.
Full submission tests use standard futures with false/successful cancellation, including deliberately running noncancellable futures; no cancel-raises adapter is supplied.
A future diagnostic should retain the engine safety mitigation and distinguish metadata/primary-error outcomes before deciding whether collector-local exception isolation is required.

#### B-F124 — P3, optional boundary test supplies only a callable oracle (test-name/overlap candidate).

test_optional_dependency.py::test_external_parsl_is_loaded_only_through_focused_boundary imports the internal optional_dependency wrapper and asserts require_parsl is callable.
It does not demonstrate an external Parsl import occurs through that function or exclude another path.
The stronger separate subprocess test blocks all external Parsl imports during ordinary public import/construction, and missing/transitive error tests meaningfully distinguish failures.
Record the weak named oracle for later rename/strengthening or evidence-backed deduplication; no test deletion or speed gain is proposed now.

### Resolved qualifications and structures to retain

**Ordinary registered-future drain is explicit and covered.**
_submit_future holds the lifecycle condition across submit plus registration, preventing a closer from overtaking successful handoff.
_close from another thread requests cancellation and waits active execution; _finish_execution drains only this engine's registered futures before owned cleanup and admission release.
Running futures whose cancel returns false remain awaited; the full lifecycle and partial-window tests establish this with actual concurrent.futures objects.
An injected external DFK is never cleaned, and two engines sharing it own/cancel only their own registered futures.
This contradicts a blanket claim that routine engine close ignores physical future completion; actual remote worker/scheduler quiescence remains a separate unexecuted dependency contract.

**B-F104 refinement.**
The launcher suppresses its extra post-terminal engine.close error, but primary execution-lifetime cleanup failures from ParslEngine.execute's finally propagate to Workflow/run context.
Do not label that primary cleanup exception silently succeeded.
B-F120 instead records lost retry ownership after the cleanup attempt.

**B-F059 extends to the Parsl steps wrapper.**
_ParslEngineSteps eagerly reserves admission; only exhaustion/error or explicit close finishes it.
Dropping an unstarted iterator supplies no finalizer/context-manager release.
Full test_steps_reserve_engine_before_first_iteration_and_close_cleanly proves explicit close, not abandonment of the original owner.
This is the same scoped iterator lifetime decision, not a second global engine admission redesign.

Startup compiles/scopes reachable nodes, treats cached/skipped processing nodes separately and rejects remote SharedArray schemas before DFK acquisition.
A changed planned cache selection fails closed through PlannedCacheBackend rather than silently allocating workers on a newly missing record.
Worker preflight futures remain engine-registered and execution cleanup drains them even when a later startup stage fails.
Actual runtime Config.retries must be exactly integer zero, and labels are checked before DFK acquisition on the real prepared path.
The factory-reference helper deliberately validates/builds in an isolated process and rebuilds the actual config in the parent; this has repeated trusted factory costs/effects, but isolation is intentional and the later effective runtime validation remains authoritative.
No generic metadata-purity or immutable arbitrary Config object claim is made; measurement/contract refinement is a maintenance candidate, not authorization to remove validation.
BoundedParslCollector retains deterministic failure keys across late sibling failures, bounded unfinished future count and row-position publication order.
ParslBackend eagerly materializes rows/task tuples while the collector submits lazily; this is a memory/cost inspection candidate, not violation of the tested unfinished-future bound or a measured slowdown.
Structured task error correlation and strict immutable public JSON value types remain supported; root/library Python floors are >=3.10/orchestrator and >=3.9/Core, with platform >=3.12,<3.15, as corrected by the shared reviewer.
Several thread tests lack finally-based event release after assertion failure (B-F012); no hang or suite contamination was executed.
Constructor, optional import, resource lifetime, bounded submission and startup refusals cover distinct contracts; textual fixture similarity alone does not make them redundant.
Next serial batch follows full routing/requirements/materialization, worker attestation/preflight and their counterparts, then retained retry admission.
Audit remains open; no repair or campaign test release.


### Complete-review checkpoint — reviewer-batch-22

#### reviewer-F048 — documentation producer uses permissive legacy record/path reads instead of current validated artifact ownership (P3, source-only fidelity)

`generate_workflow_previews.py::WorkflowArtifacts` reconstructs views/records itself (`:253–419`): it checks only selected link schema/kind/target, accepts absolute targets, falls back to legacy `run_*` enumeration, manually chooses record paths and reads unvalidated Parquet or legacy CSV without requiring the canonical current manifest/transport/logical identity.
For a relative path cell, `_resolve_record_path` (`:405–419`) tries not only the exact named record but the storage root, source checkout and repository root, selecting the first existing file.
Thus a missing owned record asset can be substituted by an unrelated equal relative spelling outside that record, and CSV/legacy state can be consumed rather than refused under the current strict format.
The script also chooses independent latest node records alongside fixed external input crops, so it does not prove a coherent single-run/input binding merely by finding files.

These are documentation-source fidelity risks for a trusted maintainer command, not an exposed HTTP traversal defect, an untrusted-code sandbox claim or demonstrated incorrect scientific data.
The smallest later correction is to reuse current public `Storage` run-node/record/asset reading contracts (`read_run_node_result`, `load_record_manifest`, `load_record_dataframe`, `resolve_record_asset`) with exact chosen record identities and declared external-path distinctions, rather than maintain another fallback reader.
Bind the input crop and selected figures to the intended artifact/run provenance when claiming actual outputs.
Existing storage/record identity, corruption and asset-refusal assertions are source counterparts owned by B/root; their presence does not automatically test this producer.
Do not add an external model/binary run merely to resolve a helper ownership decision, or allow legacy fallback to weaken the actual product cache contract.

#### reviewer-F049 — committed illustrations are not current-generator provenance (P3, observed static artifact drift)

The committed PNGs contain explicit text that current producer bytes cannot emit:

- `cell_counting_features.png` shows **shape features** as its fourth table label, whereas `cell_counting_assets` fixes **mean_perimeter** (`:564–569`).
- `tracking_metrics.png` has four qualitative labels **track_length/displacement/mean_speed/scope**, whereas `tracking_assets` fixes six numeric row labels **track_count/mean_track_length/net_displacement/net_speed/gap_count/short_track_fraction** (`:711–718`).
- `restoration_metrics.png` shows **comparison/metric/checkpoint/preview**, whereas `restoration_assets` fixes **mse_degraded/mse_restored/degraded_psnr/restored_psnr** (`:600–606`).
- `sairpico_input_psf.png` labels **Generated Gaussian PSF**, whereas the current producer fixes **Workflow-generated Gaussian PSF** (`:641`).

These are direct source-literal versus displayed-asset disagreements, not an inference that geometrical circles prove fabricated science or that any production workflow failed.
The producer intends to read real artifacts; current exact input/model/binary/run provenance and the original figure-authoring revision were not established.
The human low-SNR/SAIRPICO/parameter consumers explicitly qualify documentation illustration or typical output, so retain that distinction and do not treat those images as golden fixtures or runtime acceptance.
Other matching layout/title pairs remain unproved current renders; visual plausibility cannot supply an absent manifest or computation history.

The smallest later documentation/provenance action is to make curated illustrations explicitly distinguishable wherever prose could imply actual measured output, and decide whether the current producer is an actual-result renderer or intended illustration source.
If real-result regeneration is later selected, capture real inputs/configuration/records and reconcile all14figures with that intended producer; this audit does not authorize running model/binary workloads or replacing captions with fabricated numeric output.
The exact artifact classification is **opaque curated illustration with known intended producer/consumer and mismatches**, not **verified generated output of current source**.

#### reviewer-F050 — float-valued integer counts use one significant digit (P3, qualified future rendering risk)

`_format_number` (`:447–450`) formats any Python/NumPy float with `.{digits}g`.
Callers pass `digits=0` for `object_count`, `track_count` and `gap_count` (`:566,713,717`).
General-format precision zero yields one significant digit, so a multi-digit count arriving as a float is rounded rather than displayed exactly.
Rows selected from mixed numeric pandas summaries may expose count fields as floats; integer-valued Python inputs take the separate `str` branch and are unaffected.
No current numeric counter discrepancy was executed or inferred from the qualitative committed tables.
After the audit, use an explicit exact integral-count formatting boundary (and reject/qualify non-integral values), preserving declared counts rather than converting all scientific measurements to integers.
This is a narrow renderer candidate, not a processing/measurement result defect or reason to add another scientific runtime suite.


### Complete-review checkpoint — reviewer-batch-23

#### reviewer-F051 — UI illustration wiring and result alt text disagree with current contract/content (P3)

`node-editing.png` and `results-inspection.png` show a body-column wire into the numeric `number` field of **Normalize measurements / IncrementNumbers**, which is labelled DataFrame and remains an actual `DataFrameTool` (`routers/dev.py:139–151`).
Current platform v2 (`:92–94`) explicitly forbids column edges/node shorthand into DataFrameTool keyword fields and serializes them `connectable="never"`; ordinary whole-table inputs must use positional header pins.
The screenshots therefore illustrate an obsolete development-fixture binding rather than the current supported graph.
This is a static documentation mismatch, not a newly reproduced application defect or permission to re-enable forbidden field wiring.

The result image shows numeric/string SeedNumbers data, logs and older table sizing buttons, but `docs/user/run-and-results.md:58` describes it as **an image preview and path actions in Node Data**; neither is present in that asset.
The smallest immediate future correction is accurate alt text describing the visible completed table; no product test or image-generation run is required for the prose correction.
When illustration refresh is later authorized, use a current faithful whole-DataFrame fixture or a real ProcessingTool field route, and the current result controls, preserving existing metadata/connection/resize requirements.
Do not narrow the normative constant-only/DataFrame-positional contract to make an old screenshot appear valid.
No documentation/browser/native refresh is released by this static review; desktop remains campaign-LAST.

### Complete-review checkpoint — root-batch-12

#### ROOT-F073 — P2 qualified example dimension contract: documented planar data is sent to3D while its metric assumes exactly two dimensions

The A-complete SAIRPICO example/data manifest declares a YX crop, applies median2D, generates a depth5PSF, then dispatches RichardsonLucyDeconvolution deconvolution_type=3D.
The completely reviewed adapter passes the unchanged image path to simgrichardsonlucy3d with that PSF; it performs no hidden volume conversion.
The human Richardson-Lucy page requires selecting a mode matching input layout and leaves refusal to the external binary.
The example's _sharpness simultaneously unpacks np.gradient into exactly gy/gx, so an actual3D output cannot follow that metric implementation unchanged.
This establishes incompatible/underspecified planar-versus-volumetric recipe/metric intent, not an executed simglib rejection or proof that the binary cannot represent a single-plane input.
The current complete binary profile tests Richardson-Lucy only in2D, and structural factory validation does not execute the example.
Resolve the intended image/layout/PSF/mode/metric contract coherently before later scientific diagnosis, preserving the original PSF→denoising→deconvolution teaching idea and essential supported2D/3D modes; do not silently remove the PSF or fabricate passing binary evidence.

#### ROOT-F074 — P3 qualified milestone coverage boundary: exported-class real-binary profile covers representative modes, not the declared executable inventory

Eight complete-profile cases cover the two3DPSF generators and only2D deconvolution/median, oneCImg algorithm and hotspot.
The common declared inventory also includes three2D-slice and three3D deconvolution commands plus3D/4D median; ordinary staged argv tests exercise only selected mappings with monkeypatched outputs.
Therefore the profile can establish those representative binary routes when actually run, but cannot certify every documented mode/shape simply because every exported binary-tool class has a case.
Its planar shape[-2:] check permits extra dimensions, and max>=min is redundant after positive-size/finite checks; neither demonstrates restoration effect or scientific quality.
No profile was run; this is exact coverage/claim/selector guidance, not a mandate to add every parameter combination or rerun external environments during ordinary feature development.
Retain a narrow development lane for guards/argv/staging and an explicit milestone compatibility matrix for genuinely distinct mode/binary/layout boundaries; retain actual finite/readback/PSF metadata oracles and identify unexecuted routes honestly.

### Existing B-F056 import-isolation pattern and other suite opportunities

The882-line wrapper test directly deletes package modules and subprocess from sys.modules without restoring their original objects.
Other test code can then retain an older imported module/class while monkeypatches target a replacement, an order-dependent ownership risk matching B-F056 rather than a new canonical finding.
Several command-refusal tests patch subprocess.run while the actual complete Core runner uses its captured subprocess module; the destructive import test makes that relationship especially fragile, even though the direct guard currently refuses earlier.
Use isolated subprocess import checks or exact module-state restoration later; do not expand an ordinary external-free package guard into binary provisioning.
The wrapper module mixes lazy import/schema/environment/argv/numeric/image/scalar-storage tests; split focused selectors/dependency fixtures by actual boundaries only after global suite synthesis.
Repeated schema class loops and argv parametrization have different purposes; no measured redundancy/speed gain or blanket deletion follows from file length.
Internal diagnostic finite-timeout/empty-selection policy can be made explicit if those helpers become user-facing; it is not a present public workflow-tool defect.
M1 remains OPEN; repairs, new diagnostics and execution remain held.

Nine new full inputs / 2510 lines; root cumulative170/504,334pending.


### Complete-review checkpoint — A-batch-22

#### A-F120 — Medium, definite supported-metadata parser gap: PEP723 TOML is parsed with quoted-string regexes

Tool_loader.py294–351 recognizes the script comment block but parses dependencies with a non-TOML array regex and double-quoted string extraction335.
Valid single-quoted TOML dependencies are silently omitted, and a quoted example in a TOML comment inside the matched array can be treated as an actual dependency.
Valid exact version pins containing local-version '+' are rejected by the narrower name/version regex341 even though exact-pin reproducibility does not require that exclusion.
No parser action or install occurred in audit.
The metadata tests cover double quotes, whitespace, missing block and non-exact >= refusal only; test_parse_ignores_non_tool_deps actually tests ignoring requires-python rather than distinguishing package categories.
Retain exact-pin admission and no-metadata no-op; future public metadata parsing should use the authoritative TOML grammar and explicitly state any narrower supported version policy, rather than silently discard valid declarations.

#### A-F121 — Medium, source-authority risk: package/version module cache ignores selected tool-store root

Tool_loader.py49–53 returns any existing scoped package-and-version module, while the scoped name172–174 contains no selected store_path/source identity.
Two independently supplied stores holding the same package/version name can therefore return the first store's class even when the caller explicitly selected the second store.
Ordinary immutable single-store deployments are materially mitigated; this is not a claim that two different version numbers collide in the existing tests.
The API accepts store_path and the public worker constructor resolves the returned class's actual store, so the wrong-store selection can propagate into a complete otherwise-valid origin.
Test_cached_on_second_load deliberately exercises the same store; two-version selectors distinguish version numbers only.
Retain reuse of the same immutable source and distinct versions; future cache ownership must reconcile the requested store/source boundary rather than assuming equal labels prove equal content.

#### A-F122 — Medium, qualified publication race: in-process versioned loader exposes a module before initialization/stamping without its own ownership guard

Tool_loader.py52–53 considers any sys.modules entry a complete cache hit, but inserts that entry72 before exec/materialize/stamp79–91.
An overlapping direct loader/register call can return the partially initialized module and see missing exports or unstamped tool metadata; unload/load can similarly affect shared global state during construction.
The Core worker instance loader's RLock from A21 does not guard this public orchestrator loader; ToolRegistry register also has no local lock.
Platform tool-manager lifecycle guards may serialize its normal calls, while public concurrent callers and independent registry instances remain conditional.
Existing selectors are sequential, and lazy failure cleanup tests do not distinguish an admitted overlapping cache hit.
Retain scoped class independence and failure cleanup; future ownership policy should distinguish initializing, ready and failed module incarnations without installing a global catalog name as executable identity.
No overlapping call was run in audit.

#### A-F123 — Medium, qualified transitive-dependency isolation and lifetime limitation

Tool_loader.py55–60 permanently prepends each loaded version directory to ordinary sys.path, while absolute dependencies share canonical sys.modules entries.
Two tool versions can keep distinct tool classes but use the first-imported same-name dependency, or a subsequently imported dependency selected by the most recently prepended directory.
Unloading125 removes every path ending in package/version, not only the exact path insertion owned by that load, affecting independently present stores with that suffix.
The documented public loader isolates tool package namespaces and intentionally exposes transitive dependencies to main-process DataFrameTool code; this is a scope limitation to reconcile, not proof of full isolated environment support or a current wrong scientific result.
The shared fixture gives dep_pkg DEP_VALUE=42 in both versions, and both AlphaTool process methods return hardcoded v1/v2 without reading that value; the exact two-worker-version selector cannot distinguish conflicting dependency behavior.
Fixture-local cleanup removes dummy/lazy/broken module families and their paths but not dep_pkg; broader shared cleanup remains reviewer-owned, so a whole-suite leak is not asserted from this local fixture alone.
Retain tool version and worker-origin isolation; future compatibility claims should explicitly bound dependency isolation, and any diagnostic must actually use differing dependency values rather than duplicate the already proved class distinction.

#### A-F124 — Medium, qualified install publication/rollback race

Tool_loader.py377–401 checks module directory presence, creates the final target and runs pip directly into it, without a per-target lock or staged atomic publication.
A concurrent install/load can treat a partially created module directory as installed; a failed contender's unconditional rmtree401/412 can remove another contender's successful target.
The normal platform manager may hold a lifecycle/admission boundary, and single user-driven calls are sound; public registry/install helpers and independent processes do not establish that serialization in this source.
Current loader fixtures construct stores completely before calls, and no reviewed selector here admits overlapping installation or partial-target loading.
Retain explicit install/register separation, argv subprocess and failure diagnostics; future shared store publication should own/stage its target and coordinate rollback rather than delete by package/version label alone.
No package installation/network or race reproduction occurred.

#### A-F125 — Medium, qualified carried module authority weakening in package class fallback

Resolve_tool_class137–166 checks a requested scoped submodule when loaded, but if that module is absent it falls back to a same-named top-level re-export regardless of its actual canonical defining module.
A stale/invalid carried tool_module plus an existing top-level class_name can therefore resolve a different module's class rather than refuse the captured module identity.
Materialization.py682–689 passes graph-carried package/version/module/class directly into this public resolver, making this distinct from an ordinary name-only catalog lookup.
The fallback is intentionally documented for re-exports, and valid exports of the exact intended class remain sound; its required identity check is the qualified boundary.
Both existing ResolveToolClass selectors use already loaded correct submodules and inspect version/name, so neither distinguishes absent carried module versus a different same-name top-level export.
Retain legitimate package re-exports and exact captured package/version; future fallback should verify the actual class's canonical module or explicitly refuse inconsistent carried identity.
This extends the executable portable binding authority map without duplicating platform A-F001's live registry overwrite.

### Existing A-F117 extension — Child invocation snapshot also drops missing-node provenance

Materialization.py406–426 assigns child build errors and expected node identities, then calls child at447–451.
Interfaces.py372–413 creates that invocation snapshot by copying nodes/interfaces/custom sources/imported viewing requirements, but omits _expected_node_names, _build_errors and _failed_nodes, which initialize empty/None82–84.
Thus a retained partial child with missing internal nodes can lose its missing-node provenance before viewing derivation, not merely have provenance that the recursive visit ignores.
The same omission can make the child snapshot's is_partial/errors views look clean, while the outer materialization error list still retains prefixed child errors.
A future completeness correction cannot rely on adding recursive expected-name checks alone without preserving the captured partial-build authority.
The complete inspection counterpart covers root partial errors/failed_nodes/is_partial only; no nested partial snapshot selector distinguishes this path.
Strict complete children and normal immutable independent invocation copies remain sound; no imported partial archive was executed/exported in this audit.
This amends canonical A-F117, not a new duplicate finding.


### Complete-review checkpoint — B-batch-15

#### B-F125 — P2, provider adapter's version predicate is weaker than reported compatibility (source compatibility risk).

providers.py:_release_tuple extracts only year and month; validate_managed_provider accepts the entire (2026,5) pair.
Returned evidence states compatible_parsl >=2026.5.25,<2026.6.
A same-month version below that patch floor, or a dev/post spelling with the same parsed year/month, can pass the predicate despite the stated supported range.
The full provider tests use the installed public API and do not distinguish below-floor same-month metadata.
Future bounded version diagnostic should retain exact public executor/provider types, scheduler match and worker_init verification; no installed version was changed and no external API compatibility failure was executed.

#### B-F126 — P2, managed validator startup and secret handoff are not fully inside the bounded lifetime (source failure-isolation risk).

managed_validation.py:validate_managed_factory allocates private_root/pipes and starts the process before entering try/finally.
Process.start failure can leave private state/pipe handles outside that cleanup owner.
The subsequent secret_parent.send occurs before timed report_parent.poll; a child stalled before its recv can block the send independently of the advertised timeout, especially with the allowed larger secret payload.
No deadlock was reproduced; spawned imports/setup must reach recv for the ordinary path, and broken pipe outcomes are caught.
test_managed_validation.py::test_timeout_terminates_child_and_removes_private_state covers a factory sleeping after handoff, not startup failure or a pre-recv stall.
Termination sends SIGTERM to the child group but the later SIGKILL fallback targets only the leader; a descendant ignoring TERM is a qualified physical-retirement risk, not proof that trusted factories normally spawn such descendants.
Future fault diagnostics should retain private secret transfer, safe process identity ownership, normal timeout cleanup and no scheduler allocation during validation.

#### B-F127 — P2, successful structured factory report can carry a resolved secret (source confidentiality risk).

The worker deliberately suppresses arbitrary exception text when secrets are present, but successful _validate_result facts are returned without checking resolved secret values.
Factory-defined executor labels, attestation strings and allowlisted provider string settings are echoed into the report; a secret-derived value placed in one of those fields can therefore be returned as a supposedly sanitized fact.
This is a qualified accidental/trusted factory projection risk, not a claim to sandbox malicious Python or redact all arbitrary transformed secrets.
test_secret_values_use_private_handoff_and_never_enter_report supplies secret_failure only and verifies the failure report; no successful secret-derived label/settings oracle exists in this full module.
Future diagnostic should preserve safe opaque references and intentional useful deployment facts while deciding how known resolved values are excluded from persistent/report fields.

#### B-F128 — P2, archive readonly conversion failure leaves a reusable writable published tree (source immutability/recovery risk).

materialization.py installs staging with os.rename, then invokes _make_read_only on the already visible destination.
If chmod fails after publication, the staging path is gone and finally cannot remove/recover the published tree.
Later reuse calls _validate_materialized, which checks content/hash/symlinks/special files but not write bits; it returns reused=True without repairing or rejecting writable content.
A concurrent reuser can also return before the winning readonly conversion finishes; the existing concurrency test inspects final trees only after all calls complete.
The bytes are already fully written before publication, so this is not a claim of partial file content visibility or wrong code execution.
test_materialization.py::test_existing_valid_destination_is_reused_without_rewriting and ::test_concurrent_materialization_installs_one_complete_tree lack chmod-failure or paused readonly-conversion oracles.
Future diagnostic should preserve immutable content address, same-content concurrent reuse, no symlink replacement and exact worker origin; B-F083 durability and B-F111 empty-destination rename qualifications also apply without an executed filesystem race.

#### B-F129 — P3, duplicate detection performs quadratic scans (source cost/maintenance candidate).

routing.py computes duplicate node names using names.count for every name; materialization.py:_bundle_files does the same for paths.
These operations are O(n²) even when all inputs are unique; routing also recomputes stable environment identities across bindings/requirements.
Current full tests use small sets and prove correct duplicate/refusal/order behavior, not growth cost.
A future measurement and linear duplicate collection/identity reuse candidate should retain deterministic error ordering, exact duplicate refusal and immutable input validation.
No measured performance regression or suite speed gain is claimed, and broader input size bounds have not been certified absent repository-wide.

#### B-F130 — P3, canonical Core requirement helper does not validate constraint grammar (source validation/contract candidate).

requirements.py:normalize_core_requirement requires the distribution spelling and an operator-prefixed nonempty suffix, but does not parse that suffix as a version specifier.
Malformed constraints such as bioimageflow-core>=garbage can become a WorkerRequirement and compare equal to an equally malformed attestation until the worker's actual Core compatibility check refuses them.
The ordinary startup constant is valid, so no default processing acceptance defect follows; the gap affects public custom requirement/attestation construction and earlier diagnostics.
test_requirements.py::test_core_requirement_must_name_and_constrain_core tests empty/unconstrained/wrong-name strings only.
Future diagnostic should decide the claimed canonical requirement grammar while retaining strict distribution identity, conservative exact route comparison and actual worker Core enforcement.


### Complete-review checkpoint — A-batch-23

#### A-F126 — Medium, qualified workflow-local registry source identity loss

Registry.py257–272 keys custom workflow classes by package/version/canonical module/class without their _bif_custom_source_id/hash or owning workflow identity.
Two captured custom sources with the same original module/class and empty package/version can replace each other's class/metadata entry in a shared registry even though their immutable source identities differ.
The same public qualifiers used to distinguish package versions cannot select both custom-source incarnations.
The docs describe discovery for a specific workflow and one-registry-per-workflow use mitigates the issue; replacing a revised source within that one scope can be intentional.
This is a shared-registry capability/source-ownership risk, not an executed wrong-class dispatch or proof every refresh rebinds a workflow.
The full existing registry test covers package versions only and no custom workflow registration call was found by the source/test search.
Retain exact package qualifiers and workflow-local discovery; future public source indexing should either state/enforce single-workflow scope or preserve captured custom source identity as a selectable authority.
A-F026 cached custom source and platform A-F001 binding overwrite remain distinct mechanisms.

#### A-F127 — Medium, source-level editing dual-authority risk: cached constant mutation disagrees with wire reconstruction for edge-bound fields

Session.py167–180 adds a serialized constant and directly edits cached bindings without resolving an existing incoming edge or refusing the edit.
For an ordinary tool field, its _column_bindings and upstream edge remain alongside the new constant; for a nested input, _input_column_bindings remains while _apply_interface_binding changes child targets.
Materialization.py440–444 and475–477 explicitly reject graph-carried constant plus incoming edge at the same port/field on a fresh rebuild.
Thus the cached workflow can remain available after an edit whose canonical serialized graph refuses reconstruction; normal unconnected constants are sound, as the existing edit test proves.
The setter also stores the original value object in the cached bindings while serialize_constant captures wire values, so a caller later mutating a passed list can diverge the cached object from session.to_dict without a session edit; this is conditional caller-lifetime debt.
No edit or wrong computation was executed in audit.
Retain cheap cached edits and canonical wire state; future mutation policy must consistently reject conflicting authority or atomically change the topology/bindings and capture mutable values rather than leave two different representations.
Existing selectors do not test edge-bound or nested constants, reload equivalence or passed-value alias mutation.

#### A-F128 — Medium, qualified refused-edit state/cache ownership failure

Session.py169 publishes the wire constant,177 mutates the cached nested invocation, then178 applies the port before181 invalidates validation.
An unknown nested port or a later target application error raises after those earlier writes; a previously cached validation result remains available and session/cache can be partially changed despite the failed setter.
A valid port and normal complete target set are sound; unknown ports and damaged/adapted definitions are the distinguishing failure boundary.
The setter intentionally permits invalid values for iterative editing, but an exception must still have an explicit accepted-versus-refused state contract and accurate validation ownership.
The existing constant test uses only a known ordinary unconnected field and cannot distinguish this path.
Retain incremental editing and target fanout; future failed edits should either remain a deliberate accepted invalid state with invalidated diagnostics or preserve both authorities atomically, rather than leave a stale validation cache after refusal.
This is the Session consumer of related interface mutation debt, not a new claim that A-F036's producer rollback already works.

#### A-F129 — Low/Medium, definite lookup contract mismatch on re-registering an existing key

Registry.py265–266 and package discovery assign into an existing dict key; _matching_keys387–394 preserves initial insertion order and _find_key377 selects its last element.
After registering v1 then v2 then v1 again, the name-only lookup still selects v2 even though its public docstring315–318 promises the most recently registered class.
Exact package/version/module lookup remains correct; this is ordinary catalog selection, not corruption of already captured portable nodes.
Test_register_keeps_same_class_name_from_multiple_versions covers first-time v1 then v2 only, so it proves retention but not re-registration recency.
Retain distinct version entries and qualified selection; future implementation/prose should agree about insertion order versus most recent registration without switching captured executable binding authority to name lookup.

#### A-F130 — Low/Medium, definite documentation drift for current registry and Session mutation admission

Gui/tool_registry.rst123 describes a flat class_name-to-metadata index and recommends two registries or direct resolver to address both versions.
The actual four-part index and public qualifier parameters already support both versions in one registry; the docs unnecessarily direct callers away from that authority.
The ToolMetadata table also omits actual row_consumption, while the source publishes it as capability metadata.
Gui/workflow_session.rst56 says add_edge requires variant endpoint fields, but session139–147 checks only common fields and variant type before storing; stricter endpoint validation happens later during materialization.
Its set_constant description58–60 says constants dictionary without describing nested bindings stable port IDs.
The in-source validate docstring254 says cached across nonstructural edits, although both compute-affecting setters invalidate it; the human guide correctly describes caching until such an edit.
The guide's round-trip wording is semantic dict-copy identity, not literal byte preservation of JSON formatting, which should remain precise for undo/export expectations.
Retain valid legacy normalization and explicit runtime/wire separation; future guidance should name actual qualified lookup and mutation admission boundaries without inventing extra APIs or requiring premature validation.
No documentation rendering or app checks ran.

#### A-F131 — Medium, qualified discovery diagnostics/authority debt: schema serialization failure becomes an unmarked empty schema

Registry.py278–285 catches all input/output schema serialization exceptions and publishes {} without error/status provenance.
An introspection failure therefore looks like a successfully discovered tool with no fields to ordinary palette consumers; the registry preserves the class and row metadata independently.
Well-formed tool declarations are sound, and a host may deliberately prefer partial discovery; no existing reviewed consumer is shown executing a tool on that empty schema alone.
The current registry tests assert valid serializers populate fields and have no failing-schema distinction.
Retain useful best-effort discovery if intended; future metadata should distinguish unavailable schema from a real empty IO model rather than silently present both as authoritative {}.
This is separate from A-F115's known plain-string image declarations and from offline carried viewer snapshots.

#### A-F132 — Low, conditional metadata snapshot mutability debt

ToolMetadata is frozen but inputs_schema/outputs_schema are mutable dictionaries returned through get_metadata/list_tools without copying.
A caller can modify stored palette metadata while the registered class remains unchanged; the frozen wrapper does not preserve schema snapshot invariants.
No reviewed current consumer mutates those dictionaries, and public callers may intentionally treat metadata as mutable, so this is a contract/aliasing qualification rather than an observed stale palette.
Retain cached discovery and tuple tags; future policy should explicitly define mutable metadata or provide immutable/copying access instead of implying deep freezing.
The existing tests only read schemas, so their no-mutation oracle is appropriately bounded.

#### A-F133 — Medium, qualified archive-versus-graph Session editing shape mismatch

Session constructor/from_dict preserves arbitrary supplied data, and to_workflow delegates to public Workflow.from_dict, which accepts portable archive envelopes.
Mutators/nodes/edges operate on top-level nodes/edges rather than an archive's workflow graph, so an accepted archive can materialize initially but later node lookup fail or structural additions append invalid envelope fields.
The Session docs demonstrate graph-shaped dictionaries and do not explicitly promise archive mutation, materially narrowing this finding; callers can intentionally extract archive.workflow before editing, but would need to preserve its custom sources separately.
The tests supply ordinary graphs only, and no archived editing scenario was executed.
Retain executable archive loading and raw graph incremental editing; future constructor contract should explicitly reject unsupported envelopes or model their graph/source/snapshot ownership coherently, without promoting a stale viewer snapshot to live metadata.


### Complete-review checkpoint — B-batch-16

#### B-F131 — P1, recompute replay can reject the child's newly published current selections (source idempotence defect).

retry.py:start_retry_plan retains and recognizes the existing child plan and dispatched transaction, but always invokes _cleanup_invalidation_backups inside the allocation guard.
That helper refuses whenever a targeted current.json exists, even when the child has subsequently recomputed successfully and published a legitimate new selection.
A second start_retry(plan) after that publication can therefore raise “An invalidated cache pointer was unexpectedly restored” instead of reconnecting to the same child.
The prior journal phase establishes the old selection was invalidated; it does not establish that the key must remain unselected for the child's entire later lifetime.
This follows the reachable source path; no new test or actual replay was executed.
Existing selectors tests/unit/launcher/test_retry.py::test_recompute_resumes_a_partially_journaled_invalidation and ::test_retry_plan_round_trip_and_retained_submission_clone cover interrupted invalidation and ordinary non-recompute completion separately.
Neither replays the same recompute plan after the child regenerates that key.
Future diagnostic should join those exact phases, retaining durable journal recovery, current-pointer-only invalidation, child identity, unrelated selections and no launcher replay.

#### B-F132 — P1, concurrent same-plan local retry handoff lacks one dispatch owner (source concurrency/failed-ack risk).

start_retry_plan protects allocation/journal changes with repository.allocation_guard, then releases it before _launch_or_reconnect_retry checks status/backend markers and invokes _launch_prepared_control.
Two same-plan callers can complete that guard with phase invalidated and both observe prepared/no marker before either creates local logs.
The local backend uses exclusive log creation, so one caller can fail rather than launch twice; this is an important mitigation against duplicate processes.
However _launch_prepared_control catches that failure and _mark_launch_failed can commit failed while the first accepted launch has not yet claimed running.
The second caller's failed handoff can thus publish a terminal failure for the first caller's accepted child launch, even though orchestrator claim/epoch fencing prevents two successful execution owners.
This is a coordinated source schedule candidate, not an executed race or claim that every backend duplicates jobs.
Manual command creation and PSI/J intent logic have their own semantics; no general scheduler duplicate claim is inferred.
Existing ::test_cluster_agent_retry_is_idempotent_and_reconnectable is sequential and patches the launch handoff under a manual backend; ::test_retry_submission_uncertainty_is_never_resubmitted proves the retained uncertain phase only.
Future exact local same-plan coordination diagnostic should retain one child, one accepted physical launch, immutable receipt and claim fencing, and prevent a losing concurrent observer from failing an accepted owner.


### Complete-review checkpoint — reviewer-batch-24

#### reviewer-F052 — P3 stale restart descriptions despite a preserved operative hold

Source:platform-test-start.md:7–8, platform-test-dashboard.md:12, platform-test-plan.md:77–78 and platform-test-issues.md:73–90.
The fresh restart record still leads with RUNNING/continued execution and the dashboard says Wave2 is delegated, while the current plan and later restart instructions correctly hold all repairs/new diagnostics/application execution for complete review.
The plan also says current J1 does not assert backend and J3 siblings produce identical rows, although current canvas-interactions.spec.ts:575–580 asserts backend direct plus accepted workflow/revision, and nested-execution.spec.ts:442–445/471–481 supplies distinguishable10/20/30 versus1/2/3 sibling results.
Those are scoped counterpart reads only, not complete test-file review credit.
The conditional "if current code still has those gaps" and the explicit zero-pending hold materially mitigate accidental implementation, so this is administrative/specification drift, not a claimed permission bypass or runtime defect.
Smallest future correction:describe review as running while application execution and repair queues are held; label the J1/J3 gaps as historical now repaired; prefix023/024 next repair actions with after-gate release without weakening their retained real-red contracts.
Do not rerun accepted readiness solely to refresh prose.


### Complete-review checkpoint — reviewer-batch-25

#### reviewer-F053 — P3 obsolete Wetlands IDE launch profiles

.vscode/launch.json:11 points at removed src/wetlands/_internal/module_executor.py and:23/36 at removed src/wetlands/main.py; literal existence checks confirm both targets absent.
The checked-in Main profiles also bake in one workstation's interpreter and a different project's live Wetlands root.
Current pyproject.toml:36–37 exposes wetlands.cli:main, and current worker bootstrap is src/wetlands/module_executor.py.
This affects maintainer launch guidance, not the valid shipped console entry point or CI's module imports.
Future smallest correction:reconcile the human IDE profiles with the public CLI/debugger documentation and portable selected interpreter/disposable instance root after the gate, preserving debugger versus management ownership rather than launching the private worker directly with an invented v1 invocation.
No profile was executed and no broken-runtime claim follows.

### Complete-review checkpoint — root-batch-13

#### ROOT-F075 — P2 qualified local-model cache/provenance identity divergence

InstanSegSegment._get_model keys its retained loaded model only by model_source path and device.
Each later local-bundle invocation recomputes _digest_path on current directory bytes before reusing that cached model; the resulting provenance can claim a new model_sha256 while inference still uses previously loaded weights at the same path.
The source schedule requires a reused tool instance and a local bundle changing between rows/calls; immutable named/local weights avoid it, and no changed-model inference was executed.
The three existing adapter tests create a fresh instance and check only presence/model_kind provenance, so they do not distinguish reuse after same-path content change.
Named-model metadata is also looked up separately from the cached loaded model; this remains a qualification until the pinned dependency's exact cache/load authority is established.
Input digests are computed after inference in both InstanSeg and NAGINI, and NAGINI bundle digest is computed after its model/config were loaded; concurrently changing caller-owned files can therefore misattribute bytes even without the instance-cache seam.
Preserve useful reuse, local-model support and provenance; future ownership must bind loaded model/input snapshots to the recorded digest, or explicitly enforce immutable content for the invocation lifetime.
This is model-content provenance, not evidence that normal worker recipe attestation or all model caches are defective.

#### ROOT-F076 — P2/P3 qualified InstanSeg singleton spatial-axis refusal

_instanseg_labels uses np.squeeze without selecting only prediction wrapper axes, then requires exactly two remaining dimensions.
A valid one-row or one-column selected-target YX mask loses a spatial axis and is rejected before the later expected_shape validation; other adapters preserve spatial singleton dimensions.
The public adapter declares YX with no minimum spatial extent, but actual model support for thin images was not executed or established, so the real-runtime consequence remains qualified.
The current fake returns a normal five-by-six array wrapped as [None,None], and the optional runtime uses96-by96; neither distinguishes wrapper singleton axes from legitimate spatial singleton axes.
Preserve selected-target extraction and strict spatial shape checks; future adapter contract should remove only known wrapper axes or explicitly document/enforce required minimum spatial dimensions.

#### ROOT-F077 — P3 scientific acceptance scope and misleading test-oracle names

The NAGINI optional runtime test checks constructor/inference/sampler signature names only and never performs volumetric inference, loads a real bundle or verifies surface/curvature alignment.
Its fake adapter counterpart checks archive field names and provenance-key presence, but not numeric surface contents, resolved settings, digest identity or returned curvature count.
The real InstanSeg test imports the ambient interpreter package directly, while Cellpose3/SAM/StarDist tests create actual Wetlands workflows using declared recipes; these establish different compatibility scopes.
InstanSeg/NAGINI optional files have complete/package_tools but no model_runtime marker, so a milestone selector restricted to model_runtime misses them despite their model-related names; the repository hook still skips them by complete unless explicitly enabled.
The real Cellpose/StarDist examples permit zero objects by their count/readback assertions, which is valid API output but supplies no segmentation-quality certification.
test_cellpose_sam_environment_includes_fastremap_runtime_dependency only asserts packaging==26.2; it cannot distinguish absence of the named fastremap prerequisite, though that dependency may be intentionally transitive.
The integration file globally skips after any ModuleNotFoundError in segmentation imports, including its common-package ownership test; an unavailable optional package must not be reported as proved package separation.
These are exact claim/oracle/selector limitations, not fresh runtime failures or a mandate to provision every model during feature development.
Retain focused schema, guard, cache and mocked adapter tests; preserve genuine worker tests and declare separate milestone recipe/API/inference/scientific-quality scopes with explicit skipped evidence and configured model bundles where necessary.

#### ROOT-F078 — P3 data-dependent invalid marker-setting admission

_distance_watershed returns immediately for an empty foreground before calling integer_parameter(min_distance, minimum=1).
DistanceWatershedSegment therefore succeeds on empty foreground with an invalid marker distance that the same public call refuses for nonempty foreground; SplitTouchingObjects validates before entering its own loop and does not share that admission inconsistency.
The human DistanceWatershed guide says invalid marker settings raise; its nominal example also omits min_distance when directly constructing Arguments, extending existing reviewer-F036 rather than proving class defaults are automatically resolved at process_row.
The two touching-object tests and sparse-ID split test do not distinguish empty-foreground parameter admission.
Preserve zero-object success and explicit invalid-setting diagnostics; future parameter validation should have one input-independent boundary or the accepted empty-data exception should be documented.
No test was executed and no scientific segmentation output was inferred from this static inconsistency.


### Complete-review checkpoint — B-batch-17

#### B-F133 — P3, dependency canonicalization and JSON formatter claims exceed the available library surface (documentation drift).

specs.md §3.1 explicitly promises that version spellings such as 3.0 and 3.0.0 normalize to equivalent PEP 440 cache material.
The complete cache/identity.py:_normalize_dependency_value strips string whitespace and sorts/deduplicates list encodings without parsing requirement/version strings; compute_env_hash hashes that retained spelling.
Existing tests/unit/test_cache.py normalization tests cover sorted keys, whitespace and lists; no version-equivalence oracle establishes this promise.
This is a false current specification claim rather than a proposal to equate all package strings or weaken ordered channel identity; B-F066 separately records that ordered channel priority is currently lost.
A later bounded contract/diagnostic decision should preserve actual resolver semantics and distinguish package pins from ordered channels/direct references.

§11 advertises an available JsonFormatter for structured machine-readable output without specifying an import.
Complete logging_config.py only constructs logging.Formatter split handlers, its full tests cover explicit host setup/idempotence/levels/force preservation/delegation, and source/test text inventory has no JsonFormatter implementation.
This is an unavailable advertised library helper, not evidence that application JSON logging or Wetlands logging is broken.
Future documentation reconciliation should name the actual supported formatter API if one exists in another owner/dependency or remove the unsupported library claim without weakening required logging/progress semantics.


### Complete-review checkpoint — reviewer-batch-26

#### reviewer-F054 — P3 artifact-trust oracles omit the distinguishing content/refusal boundary

The complete tests/test_update_artifact_registry.py exercises checksum syntax/name refusals, incomplete allowlisted release, stable exact latest resolution, deterministic rendering and nonmutating check.
Its FakeDownloader always returns matching calculated bytes/checksum; no test makes a fully formed artifact disagree with its pinned sidecar, or a present GitHub digest disagree with the calculated digest.
Thus tests/test_artifact_registry.py's source-string presence plus normalized embedded hashes do not establish the updater's essential wrong-bytes refusal or unchanged registry after failed generation.
Production fetch_github_hashes:315–323 and write-after-generate main:426–441 have the expected source structure; this is an unexecuted distinguishing-test gap, not a demonstrated bad download or unsafe registry mutation.
Future smallest extension:reuse the existing fake download seam to provide well-formed wrong bytes/digest and assert RegistryUpdateError, then reuse temporary REGISTRY_PATH/main to assert existing bytes survive the generation refusal.
HTTPS redirect allowlist and release-tag/draft/duplicate metadata branches should remain intact; add further oracles only where that trust boundary requires them, not a generic branch-coverage framework or live network test.

### Complete-review checkpoint — root-batch-14

#### ROOT-F079 — P2/P3 qualified LapTrack returned-row cardinality check loses duplicate identity evidence

LapTrackLink writes every returned tracked row into output_by_position[position], then compares only the set of dictionary keys to all original positions.
An extra returned row with a duplicate input_position overwrites the earlier row; if all original positions remain present, the advertised exactly-one-row-per-input refusal does not detect the duplicate.
It also accepts returned position through int conversion rather than requiring an exact integral identity and does not compare returned frame/label/coordinates with that captured input identity.
The pinned dependency's ordinary valid dataframe output preserves input_position, so this is an adapter trust/correlation boundary, not a claim that real LapTrack produces malformed duplicate rows or a newly executed tracking failure.
The existing fake returns the intact input dataframe and the actual optional fixture exercises four valid rows; neither supplies a duplicated/mutated external response.
Preserve reordering support, normalized lineage IDs, no-merges policy and public collective row correlation; future response validation should distinguish exact one-to-one identity from set coverage before an overwrite discards evidence.
Generation's recursive ancestor traversal rejects explicit cycles but can reach Python recursion depth on a sufficiently deep valid returned lineage; keep as a bounded-scale policy/diagnostic qualification, with no ordinary microscopy or pinned-runtime failure inferred.


### Complete-review checkpoint — B-batch-18

#### B-F134 — P1, the task codec flattens a typed SharedArray argument without reconstructing it (source boundary defect).

worker_protocol.py:encode_processing_task invokes dataclasses.asdict(row) before _encode_portable_value.
The row's arguments dictionary can contain a SharedArray descriptor; recursive dataclass conversion replaces it with a plain {name,shape,dtype} dictionary.
_decode_row_invocation validates only the outer arguments dictionary, and worker.py builds Arguments directly from those values without typed descriptor reconstruction.
Wetlands dispatch.py constructs RowInvocationV1 from the resolved arguments, so a SharedArray input passes through this boundary and no longer reaches load_image/open_shared_array as its declared runtime type.
load_image's isinstance branch then cannot attach the reference and its fallback Path(dictionary) is incompatible.
This is a traced source cause, not a newly executed worker failure.
The completed Direct shared-memory integration exercises actual numeric values but bypasses task encoding; Parsl explicitly refuses SharedArray inputs, so its existing refusal tests do not certify Wetlands transport.
Full test_codecs.py covers scalar values and recursive Path conversion; test_execution.py covers scalar row/batch context only.
Future exact codec and Wetlands producer→consumer diagnostic must preserve typed SharedArray descriptors, output ownership, cache rehydration and no shared-memory forwarding to remote Parsl hosts.
Do not implement reconstruction of arbitrary dataclasses or loosen strict envelope/origin validation based on this finding.

#### B-F135 — P2, several real-worker test names/assertions do not distinguish their stated contract (test oracle weakness).

Full tests/integration/test_wetlands_task_api.py contains real-worker calls but several observations are too weak:
- TestRowParallelism::test_row_ordering_preserved checks only that each file contains processed:, without comparing that file's exact input/index/order.
- TestWetlandsResourceRequirements::test_get_environment_override and ::test_workflow_level_max_workers_default assert row counts; they do not observe actual pool size, worker identities or overlap, so successful values do not prove configuration precedence.
- TestSubRowProgress::test_batch_progress_events checks completed events only, so it can pass without any task.update delivery.
- TestBranchParallelism::test_dataframe_tool_never_concurrent creates add_col as a detached node, then computes only the unrelated processing target; the DataFrameTool never runs on that target path and no thread/concurrency witness exists.
- ::test_independent_branches_concurrent measures a 7-second aggregate that includes provisioning/startup; fixture sleep comments misstate the one-worker two-branch baseline, and the threshold alone does not prove independent branch overlap.
These are source oracle gaps, not proof that the underlying engine violates row ordering, configuration or scheduling.
The successful separate-worker/process and real Parsl interval/thread oracles remain distinct and useful; do not delete entire real-worker coverage or replace it with private implementation equality.
Future focused improvements should observe the exact promised public value/worker/event/thread boundary in existing fixtures, with bounded cleanup and without duplicated broad journeys.
The GpuTool fixture merely writes ordinary files, which correctly demonstrates no synthesized worker environment state; it is not actual GPU allocation/availability certification.

#### B-F136 — P3, scoped invalidation repeats full metadata discovery for every target (source cost candidate).

workflow/invalidation.py:_invalidation_candidates runs iter_dataframe_result_metadata or iter_processing_result_metadata over the full storage root separately for each selected real-tool target.
A broad invalidate/cascade can inspect the same record namespace O(targets × stored records), after already computing a complete plan.
The historical-metadata fallback is necessary when a downstream final key is pending; test_invalidate.py::TestInvalidate::test_pending_downstream_invalidation_uses_metadata_not_logical_signature establishes that retained contract.
No growth cost was measured and no premature metadata caching is proposed.
A later measurement/one-pass indexed discovery candidate should preserve all historical result keys, scoped names, corruption diagnostics, no-cascade semantics and externally coordinated current selections.

#### B-F137 — P3, task/result encoding traverses row payloads twice (source cost/maintenance candidate).

encode_processing_task first asdict(task) recursively converts all rows/arguments, then replaces rows with a second per-row asdict plus portable path traversal.
encode_processing_result similarly asdict(result) traverses output values before replacing rows with manually built output dictionaries.
The discarded initial rows add copying/traversal cost and complicate ownership; B-F134 is the specific typed-value failure in the retained task row conversion, not merely this discarded traversal.
No payload memory/runtime cost was measured; dataclass payloads are already bounded by caller/task policy where applicable.
Future single-pass codec work must preserve exact schema/correlation, recursive path conversion, allowed worker-safe scalar/collection values and typed shared-memory semantics rather than claiming a generic JSON-only protocol.

### Complete-review checkpoint — A-batch-24

#### A-F134 — Low/Medium, normative portable grammar omission for actual node resource overrides

Unified_workflow_contract.md's tool-node example/optional-field list lists viewer additions but omits resource_overrides and the portable NodeResourceOverrides shape/policy.
Complete serialization.py159–160 emits that field, materialization resolves it through the public override parser and A21's full resources source enforces declaration floors/concurrency ceilings.
The document identifies itself as the normative library-to-host recursive wire contract and separately says unknown fields are rejected, so omission leaves hosts without the current accepted resource field authority.
This is missing normative description, not an execution failure or a proposal that resources enter viewer/cache identities.
The golden fixtures intentionally exercise legacy normalization without overrides; the resource declaration integration counterpart does not distinguish strict graph override wire shapes.
Reviewer confirms no duplicate grammar finding; reviewer-F029 concerns older emitted-schema prose instead.
Retain portable worker-resource identity and actual class declaration floors; future normative grammar should state the current accepted field and reference its strict public schema rather than handwrite an incompatible host variant.

### Existing reviewer-F038 extension — Exact current authoring drift in A-owned basic/graph guides

Basic_workflow.rst defines Segment/Measure with Outputs but omits explicit RowConsumption, so Core ProcessingTool.__init_subclass__149–174 refuses those class declarations before graph construction.
Their Inputs/Outputs and LoadImages.Inputs are plain classes rather than IOModel, so schema/constructor methods required by the actual model are also absent.
Graph.rst's LoadDicom demonstration has the same missing row_consumption and plain IO-model declarations.
Its EnvironmentSpec dependencies={'pydicom':'*'} is not the current package-index exact-pin form shown by the authoring playbook; Core only validates pip/conda sections, so no claim that this arbitrary key itself raises at construction or installs a particular dependency is made.
The basic test imports current dedicated stubs, never the prose snippets, and therefore cannot detect their drift.
Reviewer-F038 is the canonical missing RowConsumption/IOModel documentation finding; these owned pages extend its exact source scope rather than duplicate its ID.
Retain the distinction between DataFrame source main-process work and worker ProcessingTool declarations; future guide code must obey the current public authoring protocol while preserving explicit illustrative scientific-stub wording.
The shown Segment writes zeros, so printed positive count rows are illustrative hypothetical real-tool outputs rather than outputs validated by that stub; this should remain clearly labeled, not read as a scientific benchmark claim.

#### A-F135 — Low/Medium, qualified initialization-order guidance falsely couples package/graph loading to Wetlands initialization

Basic_workflow.rst34–40 says configure_wetlands must precede Workflow.load or require_tool_packages because those initialize Wetlands.
The complete public tool_loader's installation uses the current interpreter's pip and explicitly declares independence from Wetlands; ordinary graph/package materialization need not create the worker environment manager.
Actual compute using Wetlands must still configure the manager before its first initialization, and imported trusted Python could itself initialize resources, materially narrowing this finding.
No process initialization or package loading was executed here, and no broader claim that every Workflow.load branch is side-effect free is made.
Reviewer confirms no existing initialization-order ID.
Retain explicit runtime paths and the actual first-manager-initialization rule; future tutorial prerequisites should not incorrectly require unrelated package-load ordering or imply configuring Wetlands controls tool-store pip.

#### A-F136 — Low/Medium, definite basic-test oracle overclaim for shared execution and empty-root completion

Test_shared_upstream_not_reexecuted at177 only checks seg_a/seg_b dictionary keys; there is no upstream invocation count/record/PID/observable side-effect oracle.
A duplicate upstream execution can satisfy those assertions, so its title claims more than it distinguishes, independent of whether the reviewed engine actually deduplicates correctly.
Test_compute_no_args_runs_root_boundary_and_returns_empty_frame_without_outputs at160 checks only the final0x0 DataFrame, not completion of each enabled terminal branch.
Returning an empty frame without executing all branches could satisfy that selector; stronger recursive terminal/cache tests in the previously complete unified suite provide separate evidence.
These are test-oracle precision/reuse candidates, not engine defect claims or authorization to add duplicate journeys.
Retain actual column-binding/record identity regression, and future suite optimization should rely on existing distinguishing completion/deduplication assertions or strengthen the minimal owner oracle before claiming coverage from these titles.
No measured runtime gain or deletion recommendation is asserted without the full suite inventory synthesis.

#### A-F137 — Low/Medium, qualified constructor versus runtime-required storage contract discrepancy

Unified_workflow_contract.md9–20 presents storage_path as required at Workflow construction and82–84 states no default storage location.
The complete interfaces.py constructor38–65 actually defaults storage_path=None and permits a structure-only object with no storage root, while public load/session APIs require an explicit supplied root and execution separately needs valid runtime storage.
There is no evidence of silently selecting a filesystem default or executing against an unintended path; storage-free definition construction can be a sound authoring capability.
The normative surface should distinguish a permitted storage-free structure from required execution/materialization state, or explicitly enforce the declared constructor rule if that is intended.
The basic implicit-node compute test explicitly checks missing runtime storage refusal, but does not distinguish Workflow constructor omission itself.
This is a source/documentation contract qualification, not a performed runtime red or a demand to remove valid structural editing.
Retain storage independence and no serialized runtime paths; future public signature/prose must agree with accepted build-only versus execution behavior.

### Existing A-F127 extension — Existing runtime column-precedence oracle limits consequence

The complete basic stale-constant regression intentionally inserts None beside input_image's column binding and asserts returned mask paths derive from upstream cell names rather than None_mask.
It corroborates a defensive runtime precedence rule, so the cached Session conflict must not be described as inevitably overriding connected values or wrong scientific computation.
Its distinguishing unresolved boundary remains wire mutual-exclusion/reload consistency and nested port/value ownership, not failure of that existing runtime mitigation.


### Complete-review checkpoint — A-batch-25

#### A-F138 — Medium/High, qualified local worker-module boundary violation: ProcessingTool entry modules import orchestrator/tool packages at module load

NaginiSurfaceSummary is defined in example_workflows/nagini3d_caps_segmentation/workflow.py, whose top-level imports7/18 require bioimageflow.Workflow and bioimageflow_segmentation_tools.
Its declared GENERAL_ENV adds scientific dependencies and authoritative Core; B's complete environment/worker preparation trace confirms no supported guarantee that it installs the orchestrator BioImageFlow or arbitrary tool-package distribution.
Core public source/archive origin loading executes the entire selected module before class extraction, so delaying numpy inside process_row does not avoid those top-level imports.
The same already complete A20 entry-module pattern affects RestorationPreview (low_snr_restoration workflow.py imports Workflow/common/restoration package) and BBBC reference/preparation/benchmark ProcessingTools (entry imports BioImageFlow/common/segmentation packages).
This violates the complete authoring playbook's stdlib+Core worker-module declaration boundary unless the explicitly declared worker environment separately supplies those modules.
Direct execution in the orchestrator environment and a deployment with additional accidental installs can succeed; no isolated worker import failure was executed, and merely accessing the source root does not prove its other packages are importable.
The current factory inventory test only builds/validates in the orchestrator and does not materialize these local helpers through the worker origin protocol; generic package tool tests cannot stand in for the entry-module import boundary.
Retain fresh factory capture, explicit public worker origins and main-process graph construction.
Future bounded diagnosis should distinguish actual isolated whole-module loading of a tiny local helper from graph validation/direct main-process execution before proposing relocation/dependency changes.
This is a declaration/executable module boundary, distinct from portable source-ID cache A-F026, raw package classifier A-F031 and result-cache B-F067.
No repair or diagnostic execution is authorized by this record.

### Existing A-F111 extension — Additional published-interface versus documentation output claims

Cell lineage's central page says canonical output includes migration/track-quality metrics, but the root publishes only five track/label fields; those metrics are computed detached tables, not returned columns by default compute().
NAGINI package overview promises summary centers, while root publishes only surface_index/mean_abs_curvature from the local summary; center_z/y/x remain its explicit terminal-node fields.
The wider tables exist and can be queried by explicit target; this is the same output-description distinction as A-F111, not missing scientific computation or an automatic failure to execute detached branches.
B confirms boundary output alignment supports exact/ancestor-index broadcasting before ordered-index equality, so mixing per-object and per-image providers is not blindly classified as incompatible.
Exact producer index conventions/scientific adapters remain root/B authorities; no mismatched multi-output execution is asserted from row counts alone.
Retain deliberate root publication and full terminal outputs; future pages should specify the actual returned interface or an explicit wider target.

### Existing A-F113 extension — Additional declarative scientific invariants remain unexecuted by factory inventory

These manifests assert lineage relationships, harmonic/frequency preservation, label-count/mask-shape agreement and surface-count consistency.
Full factory-only public loading/validate/export assertions do not establish those executed results, external bytes/hashes/models or provider indexes.
The declared public_data/model_runtime markers are acceptance requirements, not passing evidence or permission to run them during freeze.
No duplicate generic tests are proposed; full suite synthesis must identify actual distinguishing package/integration counterparts and qualified external limits.


### Complete-review checkpoint — reviewer-batch-27

#### reviewer-F055 — P3 bounded-management timeout is a readiness deadline, not demonstrated complete-frame deadline

management.py:27–30/74–80/140–152 polls readiness then calls blocking Connection.recv_bytes/recv after detaching a blocking socket.
There is no remaining-deadline enforcement around that full receive or the corresponding send.
A ready incomplete authenticated frame could therefore hold a debugger management call beyond its stated bounded timeout; actual public-worker frame size/order/reachability needs a controlled diagnostic after the gate.
This is not a demonstrated default-client hang, unauthenticated endpoint attack or failure of identity/authentication.
Current test_management_connect_timeout_is_wrapped_as_public_runtime_error only injects a connect exception; test_management_identity_mismatch_fails_closed correctly retains the independent identity oracle.
Future action:establish partial-frame versus no-readiness behavior with owned transport teardown first, then clarify or enforce the actual advertised deadline without weakening authentication/protocol checks or inventing a global async coordinator.

#### reviewer-F056 — P3 editor-launcher exceptional cleanup loses explicit completion ownership

cli.py:147–153 catches reaper acceptance failure and calls process.kill then wait(timeout=5), with no enclosing fallback if either cleanup action raises.
The success case appropriately reaps the immediate launcher; tests/test_cli.py:43–57 proves only successful fallback cleanup and preservation of its original thread-start exception.
On kill/wait failure this wrapper has no explicit retained retry owner and cannot claim physical completion; secondary errors may replace the originally raised launcher-ownership failure.
Normal subprocess/platform cleanup may later reap a process, so no permanent orphan or real VSCode leak is asserted.
Future smallest diagnosis:extend this existing controlled fallback test with cleanup failure, then retain/describe the same immediate-child ownership and primary/cleanup details; no editor automation or whole process-framework rewrite is justified.
CLI manager-construction and final close errors also sit outside its friendly error-return catch; preserve strict cleanup failure rather than suppressing it, and consider message/exit consistency only if a concrete public failure requires it.

#### reviewer-F057 — P2 public host exception conversion lacks the worker producer's recursion bounds

RemoteExceptionInfo.from_exception:38–48 recursively walks both __cause__ and __context__ with no active identity/depth budget; from_payload/to_payload similarly recurse unbounded graphs supplied directly to this public utility.
ExecutionFailure.from_exception:156–175 calls that converter, and ExecutionTask._set_failed:355–364 normalizes a BaseException before setting terminal status.
An explicitly cyclic host exception chain can prevent structured normalization, and ordinary shared cause/context chains duplicate traversal; no runtime reproduction was run.
Existing TestExecutionFailureDiagnostics.test_exception_from_chained_exception_preserves_cause checks one short acyclic chain and remains useful.
Important mitigation:module_executor._remote_exception_payload:295–330 already has active/depth protection, and root-owned worker-protocol tests reject recursive/excessively deep received payloads.
This finding is the host/public normalization seam, not a claim default remote reporting is unbounded or an unauthenticated injection vulnerability.
After the gate, extend the existing public diagnostic oracle for cycle/deep/shared chains and preserve the typed failure/traceback/cause-context contract with bounded explicit truncation rather than dropping diagnostics.

#### reviewer-F058 — P3 failed-provisioning recovery prose overstates cleanup success

how-to/errors.md:46–47 says incomplete environments are removed before terminal state and corrected calls can therefore reuse the same name.
Canonical provisioner:2690–2725 attempts owned cleanup but can terminally raise a ProvisioningError carrying cleanup_error when detach/removal itself fails.
Successful logical detach also differs from later physical quarantine reclamation; the stronger unconditional prose should not imply reclaimed disk or same-name success after cleanup refusal.
The current real example and reference/errors.md already distinguish structured cleanup_error and safe task retry.
Smallest future documentation clarification:qualify successful owned cleanup/logical removal, require inspection of cleanup_error or state before same-name recovery, and retain actual no-overwrite/ownership/force-Recreate essentials.
No product behavior is narrowed, no hidden cleanup exception is suppressed, and no selected-generation rollback promise is added.

### Complete-review checkpoint — root-batch-15

#### ROOT-F080 — P2 qualified scientific grouping authority: root lineage is different from the immediate image parent

SpotSummary and SpotColocalization default grouping both take the prefix before the first ::.
B's complete engine/dataframe trace confirms successive list expansions preserve the entire parent prefix and append ::child; a root0 yielding independent images0::0 and0::1 then spots0::0::spot and0::1::spot is supported.
The default prefix therefore merges those immediate image groups at0; SpotSummary can combine same-label counts, and SpotColocalization can refuse repeated per-image spot IDs or match across images if IDs happen to be unique.
The human tool pages explicitly describe lineage-root grouping, while PLATFORM_CONTEXT claims immediate parent image grouping; this is an actual contract/context discrepancy plus a qualified deeper-expansion capability limitation, not a claim every single-level workflow or current Fish Analysis is incorrect.
Existing default tests use first::spot/second::spot only; explicit group_by image IDs already provide a supported mitigation.
Explicit grouping stringifies values, so distinct typed values with the same textual spelling share authority; preserve this as a public grouping-policy qualification, not a claim ordinary string image IDs collide.
Future synthesis must choose/document the intended source identity and match root versus immediate-parent policy coherently before changing calculations, retaining explicit grouping, recursive index lineage and valid existing single-level results.
No grouping or scientific result was executed during review.

#### ROOT-F081 — P2 empty RenderSpots bypasses the ordinary source/output/configuration admission

RenderSpots.process_batch immediately renders every anchor independently when no row has either coordinate, before grouping and output_sources collision checks.
Two distinct blank reference images can therefore write the same output_image sequentially and each returned row names the last written bytes; ordinary nonempty/mixed groups refuse that collision.
The same early path skips radius validation and consistent same-source shape/label_mode policy, so empty-data admission differs from ordinary rendering.
The test for cross-reference collision supplies coordinates, and the two-anchor blank test supplies different output paths; neither distinguishes two differently shaped blank references targeting one path.
Core staged result ownership still protects committed workflow records on a raised error, and no actual immutable publication failure was reproduced; this source issue can also occur through the directly documented public process_batch seam.
Preserve blank artifacts, per-input cardinality, source separation and visible-label/binary modes; future empty handling should share the same source/output/configuration admission before rendering.
Do not remove zero-row support or infer that all aggregate repeated artifact paths are forbidden: one valid collective source intentionally shares its path.

#### ROOT-F082 — P2/P3 unbalanced colocalization memory cost candidate

SpotColocalization._match_group first allocates an R-by-Q distance matrix, then an additional (R+Q)-by-(R+Q) dense assignment matrix with dummy unmatched rows/columns.
For highly unbalanced nonempty spot counts, the latter is quadratic in the larger side even when the useful distance problem is nearly linear; this is a source allocation bound, not a measured slowdown or executed memory failure.
NearestNeighborLink already expresses valid-link cardinality priority with a rectangular penalized assignment, but scientific matching semantics, thresholds, unmatched policy and deterministic order must be proven equivalent before any reuse.
The existing tiny adversarial two-by-two colocalization fixture is an essential correctness oracle and supplies no scale evidence.
Future focused measurement should use representative balanced and unbalanced tables, then preserve maximum-cardinality/minimum-distance matching and explicit grouping; no speedup, runtime budget or generic caching is asserted now.


### Complete-review checkpoint — reviewer-batch-28

#### reviewer-F059 — P3 example background ownership is incomplete on exceptional paths

examples/minimal_example.py:6–21 closes the manager only after successful provisioning/start/call/print, whereas the primary getting-started example and user tutorial correctly use manager contexts on all paths.
Its worker pool context protects an entered pool, so this is not evidence every error leaks a live worker; manager completion is simply not explicitly owned after early failure.
examples/async_example.py:24–30 creates a report Task but only awaits it after successful operation await; provisioning failure or caller cancellation can leave its outcome unconsumed while manager final cleanup runs.
Ordinary operation terminal events may finish that reporter promptly; no unexecuted reporter leak, real unhandled exception or claim cancellation automatically cancels provisioning is made.
B confirms no existing canonical finding for these files; B-F008's await-cancellation lifetime is a separate operation owner.
Future smallest correction:teach the same manager context/finally discipline in the minimal example and retain/consume the reporter in a structured exceptional path, preserving original failures and actual operation/physical-close ownership.
Reuse appropriate existing documentation-example acceptance oracles if a meaningful failure distinction is added after the gate; do not build a new example framework or execute examples during review.

### Complete-review checkpoint — B-batch-19

#### B-F138 — P3, public constant decoder coerces malformed envelopes instead of preserving/refusing their claimed type (public helper validation candidate).

constants.py:deserialize_constant directly indexes the envelope and calls bool/int/float/str on the payload without checking exact keys or payload shape/type.
A bool envelope carrying string false becomes True; an int envelope carrying a fractional float truncates it; malformed containers can fail with incidental built-in errors.
The serializer produces well-typed values, so its own supported finite ordinary roundtrips are sound.
Strict graph parsing is a separate authority reviewed by A; no portable graph bypass or accepted untrusted workflow mutation is inferred from this public helper alone.
The curated API explicitly exposes these helpers for host encodings outside graph code paths, making consistent public misuse diagnostics a candidate.
Future bounded malformed-envelope tests should first establish intended direct-helper strictness while retaining strict graph format and lossless Path/list/tuple/dict serialization.
No new test ran; current workflow roundtrips cover valid envelopes rather than malformed direct helper calls.

#### B-F139 — P2, metadata under an optional wrapper is lost by schema extraction (source schema/compatibility risk).

extract_image_spec checks only a top-level Annotated, and schema serialization also calls Core extract_gui_meta on the original annotation before optional unwrapping.
Optional[Annotated[Path, ImageSpec(...), GUIMeta(...)]] therefore has a Union at that extraction boundary and loses image/GUI facts.
_display_type_name's image branch runs before generic optional unwrapping; after that branch misses, generic unwrapping labels it Path rather than ImageFile.
Scalar Optional[Annotated[int, ...]] display is explicitly covered in test_primitives.py, but the inner image/GUI variation is absent across the complete input/output/helper test group.
is_path_type separately unwraps the optional and can still identify its Path, so this is not a claim that every optional path becomes non-path or runtime IO necessarily fails.
The consequence is missing display/connection/compatibility metadata for supported resolved annotations, qualified by which wrapper ordering the author uses; top-level Annotated[Path | None, ...] works at the metadata boundary.
Future paired annotations should retain required/nullability orthogonality and equivalent effective image/GUI facts, without inventing thirdparty worker interface types.

#### B-F140 — P3, curated validation/error/constant guidance retains obsolete guarantees (documentation/API contract drift).

models.py and reference/api/validation.rst describe SchemaSerializationError being raised when serializers cannot instantiate Inputs/Outputs.
The complete serializers do not instantiate those models and have no SchemaSerializationError raise site; annotation/default/template failures propagate their original exceptions.
The existing test_schema_serialization_error_exists proves class availability only, not promised failure mapping.
The API constant section says unsupported values stringify lossily and lists an older scalar/list/tuple set; current serialize_constant supports None/Path/dict recursively and explicitly raises TypeError for unsupported values.
live_validation.rst unconditionally calls Workflow.validate and check_type_compat non-raising, but declaration introspection/Pydantic model construction can fail outside error-list conversion.
Actionable declaration errors are intentional in the current Core contract; this is a scope/wording or diagnostic mapping decision, not a request to silently replace malformed annotations with Any.
The old five-check list also omits newer Core/source/environment validation; its capture example uses JoinOnColumn(..., column=...) rather than join_column and describes a different expected failure.
Future reconciliation should state the precise supported declaration/failure scope, supported constants and class-based no-constructor introspection; retain existing structured graph diagnostics.
The general converter overstatement remains reviewer-F026, not another B finding.

#### B-F141 — P3, some split validation tests overlap or have misleading names/weak sub-oracles (test strategy candidate).

TestIntegration::test_I3_plan_parity_under_dev_mode never passes dev_mode=True; actual true/false hashing is independently covered by TestPlan::test_plan_parity_dev_mode.
::test_I1_full_round_trip only compares the first node's key set after a multi-stage roundtrip, whereas TestFromDictToDict separately covers valid constants/node sets and strict matrix behavior.
::test_I2_broken_graph_survey's comment promises more error kinds than its fixture/assertions distinguish; it checks unknown_tool and parameter_invalid only.
No-Wetlands constructor spies are substantially equivalent in TestIntegration::test_I4_no_wetlands_under_plan and TestPlan::test_plan_does_not_launch_wetlands.
Unit metadata tests and integration introspection tests repeat source/ProcessingTool/merge metadata and resolved/unresolved Generate facts without adding an actual GUI transport or worker boundary in those repeated cases.
The shared _canonical helper sorts every list; current ConnectedComponents golden only has set-valued constraints, so no present ordered-choice corruption is claimed, but future ordered defaults/choices would be invisible to that canonical comparison.
The repeated broad unused import lists and F401 suppressions are split-file maintenance debt, not measured runtime bottlenecks.
These are concrete candidates for role clarification/consolidation after the audit, not deletion authorization or a demonstrated global suite speed gain.
Actual cache lifecycle, cycle diagnostics, partial-load matrix, full wire shape, nullability, template failure and per-field helper oracles remain useful independent contracts.

#### B-F142 — P2, compatibility checks ignore resolved inherited image metadata (source type-safety gap).

schema.py:check_type_compat and Node._check_type_compat inspect only upstream_tool.Outputs._get_all_annotations.
For a Passthrough DataFrameTool or dynamic merge, a column inherited from an upstream image may be absent from those raw declarations even when Node.get_output_schema exposes its exact resolved image_spec.
Both checks return without validating its producer metadata, so a resolvable inherited LABEL image can bypass a strict INTENSITY consumer check through that intermediate tool.
The complete specification says Passthrough uses the upstream schema for construction validation; column existence does consult resolved schema, but semantic compatibility does not.
This is a traced source gap, not an executed scientific wrong-output claim; unresolved dynamic metadata must remain honestly unknown, and runtime image contents are not independently certified by annotations.
Current raw and wire tests distinguish direct image declarations and resolved column names but do not join inherited image metadata to a negative consuming binding.
Future precise direct→Passthrough/merge→consumer negative should preserve intentionally overlapping ImageSpec sets/asymmetric wildcards and avoid imposing a guaranteed-subset semantics the contract never promises.
No repair, metadata synthesis redesign or test execution is authorized yet.

### Complete-review checkpoint — A-batch-26

#### A-F139 — Low/Medium, source-established descriptor ownership leak on early cleanup parent failure

Gateway_archive.py212–227 opens/appends root_descriptor and then opens the namespace before entering the component-walk try/finally ownership cleanup at240–263.
If the namespace open raises (missing/refused/replaced component), the root descriptor remains open and is not returned to the caller.
The callers cleanup_state324/379 assign their descriptor list only after a successful helper return, so their surrounding cleanup cannot close the leaked root handle.
The normal validated namespace exists and unsafe-mode checks after both successful opens explicitly close handles; no arbitrary filesystem escape is asserted.
Repeated failures can accumulate process descriptors, but no descriptor count or actual exhaustion was reproduced.
Relevant current cleanup selectors cover changed/unsafe/symlink candidates and identity refusal, not this helper's early namespace-open handle lifetime; reviewer complete counterpart review remains pending.
Retain descriptor-relative no-follow traversal and close only handles this operation acquired; future error handling must cover every acquisition before transferring ownership.

#### A-F140 — Medium, qualified extraction rollback deletes a destination it did not acquire

Gateway_archive.py454 destination.mkdir occurs inside the encompassing extraction try, while493–495 unconditionally rmtree(destination) on any failure.
If mkdir refuses because the destination already exists, cleanup can remove that pre-existing tree even though this invocation created nothing.
Run_state397–399's existence guard mitigates normal repeated submission; an overlapping direct/helper call or another creator between the guard and mkdir remains the distinguishing ownership risk.
Actual gateway serialization/locking may exclude that cross-call race in its supported public path, and the helper is private; reviewer will trace complete run-state/admission ownership before any universal data-loss or severity escalation.
The existing archive drift selector uses fresh independent destinations and asserts their absence, so it cannot distinguish unowned rollback.
Retain exact archive inventory/hash checks and cleanup of partially created owned extraction; future rollback must condition deletion on acquired destination ownership, without weakening immutable-object or idempotent-run boundaries.
No extraction/deletion or race reproduction occurred.

#### A-F141 — Low/Medium, qualified archive refusal diagnostic normalization gap

Gateway_archive.py353–357/421–425 wraps ZipFile constructor errors as deployment-tampered, but later archive.open/stream.read/CRC/decompression errors365–395/466–486 are not converted locally to that structured failure.
Extraction removes its destination and reraises the raw exception; validation likewise leaves a raw ZIP/OS stream error rather than the helper's advertised tamper category.
A complete public gateway catch boundary may intentionally normalize it, and corrupt streams can refuse safely even with a less useful diagnostic; actual caller/handler classification is pending reviewer full trace.
Tampered byte-content/missing/extra fixtures remain valid safety checks but do not corrupt the ZIP compressed stream/CRC itself.
Retain refusal, exact byte validation and retry identity; future error ownership should consistently classify source corruption versus transient IO at the actual public boundary, not catch all failures as a misleading generic success or retry.
No corrupt archive or public failure was executed.


### Complete-review checkpoint — reviewer-batch-29

#### reviewer-F060 — P2 CI never selects the transport-specific physical lease oracles

All five tests in test_v2_transport_integration.py are marked integration (three also agent_integration).
The sole .github/workflows/ci.yml fast matrix:67 excludes integration; its sole real-Pixi command:110 selects only test_v2_pixi_integration.py, and weekly/manual triggers reuse the same jobs.
Compat selects only compat; no collection hook silently selects these transport tests.
The real-Pixi release test:434–443 proves actual array copy-in/out and independence, but does not assert segment unlink/empty lease ledger after cancellation/death or predispatch missing-NumPy codec refusal as the separate transport tests do.
The manual release checklist's full suite can include them; this is automatic-CI selection/oracle debt, not a claim they never ran locally or all integration tests must run on every push.
Fake Pixi skips real provisioning but starts actual workers and tests physical shared-memory ownership; it is distinct from real-download provisioning acceptance.
Future action:inspect retained cost and make an explicit owner decision to select the existing bounded transport file/appropriate cases at a proportionate CI or scheduled boundary, reporting its POSIX-only NumPy Windows skip and missing-prerequisite outcomes.
No new test is needed merely to repair selection and no broad suite rerun or measured speedup is established here.

#### reviewer-F061 — P3 DAP acceptance helper has no total expected-message deadline

_DAPClient._wait_for:112–120 repeatedly reads and saves unrelated messages until its predicate matches.
The socket has30s per-I/O timeout, but continued unrelated events can keep the expected response/event absent indefinitely while _pending grows.
The CI job30minute timeout limits the whole job, not this request's diagnostic bound; no actual hang or adversarial DAP claim is made.
Future smallest correction:give the existing helper a total request/event deadline and bounded useful pending diagnostics, while preserving exact response sequence/success and real debugger reconnect/disconnect oracles and client teardown.
Do not weaken expected messages, retry away a failure or fragment the coherent real environment setup into redundant download fixtures.
