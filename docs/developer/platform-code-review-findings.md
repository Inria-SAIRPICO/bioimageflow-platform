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
The newly authored findings register adds one pending current-document input: 1,799 total / 121 complete / 1,678 pending.
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
Command-facade excerpts show zero-options active-canvas lookup; A will finish its full facade/session review to establish the actual stale-target consequence.
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

#### A-F031 — Medium potential impact, qualified scientific-package classifier omission

Library `custom_sources.py:33–45,51–73` enumerates built-in scientific package prefixes but omits bioimageflow_phasor_tools.
Raw public classes without `_bif_package`/version stamps therefore may be treated as workflow custom classes and embedded as individual source files, unlike the other scientific packages.
Off-owner `test_tool_package_export.py::test_all_tool_packages_are_not_workflow_custom_classes` omits phasor too.
Actual phasor class metadata/loader stamping is root's pending scientific review, so this is qualified rather than an executed incorrect export claim.
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
