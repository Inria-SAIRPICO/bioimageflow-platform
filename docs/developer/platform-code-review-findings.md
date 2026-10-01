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
Current checkpoint: 1,799 inputs / 374 complete (373 reviewed / 1 classified) / 1425 pending, with 206 identified findings.
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
