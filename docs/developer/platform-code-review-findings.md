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
Current checkpoint: 1,799 inputs / 1792 complete (1643 reviewed / 149 classified) / 7 pending, with 573 identified findings.
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

### Complete-review checkpoint — B-batch-20

#### B-F143 — P2 source defect: accepted repeated selected columns break scalar projection

`models/data_table.py:DataTableSource.columns` accepts repeated names.
`data_table_projection.py:186–202` selects with `dataframe.loc[:, source.columns]` without uniqueness validation, then the actual ResultStore type helper calls `_infer_series_type(df[column])`; duplicate column lookup returns a DataFrame rather than the required Series, and its `.dtype` path is invalid.
Even a fake type helper that bypasses this failure leaves `_build:331–333` obtaining a Series from `row[column]` rather than a scalar; stable column IDs also repeat.
The router catches only declared projection/not-ready errors, so this accepted selection can escape the advertised typed failure contract.
A supported GUI producer can generate this shape: `DataTablePanel.vue:entriesForNestedWorkflow` appends each exposed source column, while the public Workflow output declaration guards unique port names/IDs but permits two ports to expose the same source column.
The alias dictionary then retains only the last name, while the column-filter list contains duplicates.
This is a source-traced causal path, not an executed failure.
Existing selectors `test_parent_values_expand_to_finest_selected_lineage`, `test_merged_columns_use_retained_viewer_snapshot`, and router `test_query_validates_sources_and_resolves_workflow_storage` do not distinguish repeated internal columns or two exposed aliases.
Future decision: define whether same-column exposure yields one consolidated field or distinct alias fields, and guard repeated direct selections with a typed refusal or explicit scalar-safe representation.
Retain legal repeated interface exposure, captured identities, source-row mapping and ordinary lossless fallback.

#### B-F144 — P3 presentation/export risk: collision qualification can still leave identical CSV headers

`data_table_projection.py:298–310` qualifies colliding base labels with caller-provided source labels, which are not unique.
Two distinct nodes sharing a display label and column name still produce identical final labels; two aliases within one source may do the same.
`csv:143` replaces stable internal IDs with those labels and exports ambiguous headers, despite the JSON response retaining unique source IDs for ordinary distinct columns.
The actual panel uses node display names and nested parent labels, so equal labels are plausible; no guarantee of unique display names was found in this boundary.
`test_colliding_labels_are_qualified_and_sort_happens_before_paging` uses different labels Input/Result and cannot distinguish this case.
Future action: specify final unique human-readable headers using a stable source discriminator while preserving ordinary chosen aliases.
No claim of data-row loss or wrong result identity is made.

#### B-F145 — P2 lifecycle source risk: settings continuation registers after panel unmount

`DataTablePanel.vue:276–287` awaits settings, then changes preferred page size, initiates projection/stacked fetches and registers the Dockview visibility callback.
`onBeforeUnmount:302–305` disposes only the listener that already exists; if unmount happens while settings are pending, a later callback is installed after cleanup without an alive/registration fence.
The dataTable store has per-canvas release/request fences for already-started HTTP responses, which are sound and mitigate stale commits; those do not dispose a newly installed panel listener or bind this late continuation to the mount-time canvas.
The continuation reads active target state after the await, so it may initiate an unnecessary request on a newly active context.
This is not an executed registration leak or proven cross-workflow data overwrite.
The panel's owned test is import-only; eventual distinguishing coverage must defer settings until after unmount and assert no registration/refresh.
Future action: preserve current visibility refresh and per-canvas store fences, add only the panel lifetime/target guard needed by the asynchronous continuation.

#### B-F146 — P3 scalability/test-design candidate: pagination bounds payload, not projection work

Both async routes invoke synchronous source loading, full projection and filtering/sorting directly, and CSV serialization runs on that event-loop thread.
`_build:277–279` compares each anchor row against candidate rows; same-level large anchors can require quadratic lineage work before a page is selected.
All projected cells are rebuilt before pagination; collision counting also rescans the label list.
This is an unmeasured responsiveness/cost risk, not a benchmark result or permission to impose new semantic row limits.
The default-page route oracle uses 300 rows and proves a 250-row response, not bounded CPU, file loading or event-loop progress.
Future investigation should measure representative large data and preserve safe alignment, full CSV semantics, captured records and stable sorting; optimize only demonstrated cost.

#### B-F147 — P2 test-oracle gap: named recursive panel test asserts import only

`frontend/src/components/panels/__tests__/DataTablePanel.test.ts` is fully read: eight lines import the component and assert truthiness.
It has no recursive output graph, mount, request, scope, alias or lifecycle assertion despite its describe/test names.
Backend service tests strongly distinguish exact identity capture and no-loss lineage fallback; route tests use MagicMock legacy fallback and verify endpoint projection/error contracts, not actual immutable-record verification.
Those tiers remain useful distinct oracles and are not redundant merely because sample rows overlap.
Rename the import smoke to its actual guarantee if retained; defer targeted recursive/lifetime/alias coverage until implementation/test execution is released.
No overall suite runtime gain is claimed.


### Complete-review checkpoint — B-batch-21

#### B-F148 — P3 maintenance/test-architecture candidate: retain branch distinctions while consolidating repetitive setup

The source and column-bound SHM modules repeat durable manifest, cache execution counter, fresh segment, corrupt asset and invalidate scaffolding.
Those branches are not interchangeable: source invocation normalization, mapped input/index handling, and Path|SharedArray union ownership need independent coverage.
Likewise source/DataFrame cache/progress cases test different engine publication paths and should not be removed merely because their assertions resemble each other.
A future table-driven helper could share manifest/identity assertions while retaining explicit test IDs and branch-specific entry/oracles.
No runtime measurement or authorized deletion accompanies this candidate.
`tests/testkit/runtime_cache.py` retains broad F401-suppressed imports formerly used by monolithic tests, repetitive blank lines, and many exported private helpers; narrow fixture responsibilities may reduce maintenance ambiguity.
The source-processing module's opening 'split from' text names itself rather than its real historical parent, a low-priority provenance/comment correction.
The `test_dataframe_tool_parameter_change_creates_distinct_result_record` nonempty-set assertion adds little to two unique current paths; strengthen intended key distinction if retaining the assertion rather than claiming a new behavior defect.

### Existing B-F117 — explicit SHM ownership remains absent from these test lifetimes

The fully reviewed helpers call Core `create_shared_output`, whose public contract closes the local handle but deliberately does not unlink the segment.
The reviewed source/column tests open and close descriptors, create additional segments on cache rehydration and never explicitly unlink their resulting descriptor names.
Root/integration fixture inventory already traced has no per-test SHM owner cleanup for this group.
Python's process resource tracker may remove registered segments at process shutdown; that is different from bounded per-test lifetime and can accumulate resources during a long suite.
This is an extension of the existing B117 test cleanup finding, not an executed leak count or a proposal to invalidate user-owned results automatically.
Future tests should explicitly own cleanup of the names they create, including assertion-failure paths, while preserving the product's descriptor lifetime contract.

### Existing B-F134 — Direct shared-memory success does not exercise external task encoding

`test_source_shared_array_processing_tool_publishes_durable_asset_and_rehydrates_hits` and its column counterpart actually consume a rehydrated descriptor, assert array content and a deliberately failing file-reader fallback.
They correctly prove the Direct pipeline retains typed descriptor values and persistent NPY assets.
Every workflow in these two modules explicitly uses `engine='direct'`; their successful downstream consumption bypasses the public external `encode_processing_task` `asdict` seam underlying B134.
Do not discard these tests or turn their guarantees into a Wetlands worker/codec certification claim.
A future exact external typed-SHM diagnostic belongs to the recorded repair gate, not this audit.

### Other existing risks remain scoped

The coordinated DataFrame publisher tests use Barrier(2), two futures, bounded barrier waits and bounded result calls, and assert actual installed records, selected winner and conflicts.
These are stronger race oracles than timing-only equality tests.
B012's executor context can still await an unexpectedly stuck worker when unwinding a timeout; no actual hang was executed here.
B067 module/qualified-class identity equality is not distinguished by these sample tools and parameters; source hashes already participate, as corrected in B19.
B068/A-F030 external pointer coordination remains separate: recursive provenance deliberately removes a provider selection within trusted Direct tool code, then asserts explicit nonreusable semantics rather than attempting concurrent replacement ownership.
B083 durable-directory fsync/crash semantics are not established by normal file assertions.
B079 transient finalizer correlation/reterminal guards remain separate from tested ordinary failure diagnostics.


### Complete-review checkpoint — B-batch-22

#### B-F149 — P2 documentation/source-contract gap: shared-memory guide overstates zero-copy and understates durable caching

`docs/source/how-to/shared_memory.rst:4–6` presents inter-tool shared memory as avoiding intermediate disk writes and markedly faster.
The current reusable ProcessingTool path materializes returned SharedArray contents into owned NPY assets, persists the record, and rehydrates a newly allocated segment on cache load; full Direct runtime-cache tests actually assert both physical assets and fresh segment names.
The guide's final recommendation to prefer files for results that persist across runs/caching is therefore misleading if read as lack of durable SHM cache support.
Zero-copy attachment remains true for a live descriptor view, not an unconditional description of every publication/transport/cache transition.
No speed comparison has been measured in this audit.
The guide explicitly says the block persists after producer context exit, but does not describe who unlinks it or how an application should bound descriptor lifetime; this reinforces existing B117 rather than proving every retained descriptor is leaked.
Its default Wetlands workflow example also does not warn about the currently source-traced typed input encoding B134; successful Direct examples/tests do not certify external codec behavior.
Future documentation should keep supported typed shared arrays and durable caching, distinguish zero-copy attachment from durable materialization and actual transport, and document ownership without inventing auto-unlink behavior or weakening required compatibility.
Existing exact oracles: `runtime_cache/test_source_shared_memory.py::test_source_shared_array_processing_tool_publishes_durable_asset_and_rehydrates_hits`, column-bound counterpart, and Core worker-protocol execution tests; these distinguish Direct behavior and codec seams separately.


### Complete-review checkpoint — A-batch-27

#### A-F142 — Medium, source-established stale rescan authority; qualified ordinary refresh impact

Tool_registry.py67–176 optionally replaces the library registry and iterates current disk packages, but never clears absent platform _tools/_packages/_sources; missing store returns with all old platform metadata retained.
A removed package/class or switch to an empty store can therefore leave advertised metadata whose class binding no longer exists in the fresh library registry.
Package installer no-watcher install/uninstall fallback calls this rescan; normal uninstall explicitly forgets its requested package first and startup scans a fresh service, mitigating those ordinary paths.
Same-version loader caching also means scan alone does not execute changed source; test_scan_tool_store_refreshes_existing_entries explicitly pre-unloads and cannot assert that broader contract.
Retain intentional active/newest catalog policy, failed-version diagnostics and workspace custom entries; future reconciliation should establish authoritative scanned package scope and remove only absent entries it owns.
No removed-store/rescan reproduction or execution result is claimed.

#### A-F143 — Medium, source-established inactive reload restoration lies outside rollback boundary

Tool_registry.py697–740 restores prior state for errors in changed-version load/index, but active-version re-registration at746–768 occurs after that try and catches FileNotFoundError only.
If an inactive reload succeeds and restoring the active class/schema raises a different error, the operation fails after replacement metadata/classes have already been published, without restoring the previous active snapshot.
If the active directory is absent, the warning path can return a successful inactive reload while PackageInfo still names the original active version.
Current test_active_version_preserved_across_inactive_reload supplies a valid unchanged active package, and test_reload_failure_rolls_back_to_prior_snapshot fails the edited version before this restoration phase.
Retain genuine syntax-failure rollback/public resolver identity and intentional inactive package loading; future transactional authority must encompass restoration or explicitly report/retain an unavailable active state.
This is a traced failure boundary, not an executed failure or universal corruption claim.

#### A-F144 — Low/Medium, qualified multiple executions/reads of one custom source are not a captured batch

Tool_registry.py308–311/408–431 first executes a source to discover classes, then320–363 reads/executes it again independently for every class.
reload_custom_tool434–461 uses the same sequence in a staged registry.
Trusted source import side effects therefore run repeatedly even on one discovery/reload, and a file edited between these reads can produce discovered names and class metadata from different byte revisions.
The stage prevents publication on ordinary earlier failure and GUI templates usually define one class; no dynamic edit or harmful source side effect was reproduced.
Current custom tests use stable single-class sources and distinguish timestamp freshness, not one immutable multi-class byte snapshot.
Retain exact-byte compile and all-class staging; future capture should own one source revision/module plus discovered class identities before publication, without broad import/source redesign during this held audit.

#### A-F145 — Low/Medium, source-established custom sys.modules lifetime leak; retained class dependencies qualify cleanup

Tool_registry.py328–339 publishes a content/path-qualified module; it removes it only when exec itself fails.
The missing requested class at340–342 and later metadata serialization/registration failure leave that module published, and successful repeated source edits accumulate distinct hash-named modules without a retire protocol.
Discovery modules do have finally cleanup, so that path is sound.
Retained class/module globals and already captured workflows can legitimately need prior origins; blindly deleting all old modules would violate those lifetimes.
The gap is no ownership/retirement boundary and failure cleanup after execution, not a claim every retained historical class is garbage or that small normal edits exhaust memory.
No current custom selector inspects sys.modules after missing-class/metadata failure or a released owner sequence; future cleanup must separate failed unpublished state from intentionally retained captured classes.

#### A-F146 — Medium, qualified catalog active-version acknowledgment can diverge from usable class authority

set_active_version537–602 records requested active_version on FileNotFoundError despite an unsuccessful class refresh; this production branch is explicitly justified by fake tests rather than a supported unavailable-source state.
forget_package798–826 removes a selected installed version but does not pick/clear active_version when other versions remain; its display metadata and library binding may instead be absent or from another remaining class.
Successful switch tests and installer explicit forget mitigate common operations; no actual uninstall/public UI consequence is claimed until B reconciles package lifecycle callers.
Retain versioned captured-workflow authority separately from the ordinary palette choice.
Future acknowledgment must describe actual usable/unavailable active identity rather than imply a class changed because only a preference string changed.

#### A-F147 — Low, private registry bridge and partial environment wire are maintenance/contract debt

Tool_registry.py828–865 directly writes library private _key/_classes/_metadata, duplicating canonical LibToolMetadata construction and module-key conventions alongside register_package.
The class-only platform palette and four-part library registry are distinct useful authorities; collapsing them or rewriting source identity is not authorized.
Environment metadata223–230 carries name/dependencies but excludes allow_flexible_versions, while the snapshot test intentionally drops environment entirely.
Actual engine receives the resolved class environment, so this omission alone does not establish wrong execution policy.
Future contract work should document palette environment summary versus full execution authority and prefer a public already-imported-class registration API if one becomes available, with strict tests for required display fields.
No broad refactor or new environment compatibility claim follows from this debt.

#### A-F148 — Low, source-established weak snapshot test oracle and implementation-coupled overlap candidate

Test_tool_registry.py638–652 accepts GaussianSmooth in either version snapshot and conditionally asserts each package_version; it can accept the wrong selected version or simultaneous entries despite the fixture expecting newest-only metadata.
Test_no_leaked_sys_path_after_repeated_reloads asserts at most one entry although its prose says exactly one; other real class loads mitigate this weakened presence oracle.
Test_reload_package_uses_unload_then_load_primitives asserts internal call choreography, overlapping but not identical to actual class/schema/public-resolution tests.
Prefer tightening/reusing the expected catalog/identity assertions before adding duplicate end-to-end journeys; deleting the internal spy remains a measured-suite decision, not immediate authorization.
No test was run and no currently failing result is claimed.


### Complete-review checkpoint — A-batch-28

#### A-F149 — Medium, source-established in-flight watcher reload ownership gap across stop/suppress

Tool_hot_reload.py381–392 creates _do_reload tasks without a retained task set; _do_reload399–404 checks _stopped only before executor work, and reload_and_broadcast412–464 broadcasts after that await without another shutdown/suppression ownership check.
stop137–193 cancels polling and pending TimerHandles and stops the observer, but neither waits for nor retires an already-running registry reload task.
suppress197–229 cancels timers and records snapshots but does not acquire/drain _reload_lock or block an already-started executor mutation.
Thus timer cancellation alone cannot establish that stop has ended registry mutation/broadcasts, or that installer suppression excludes concurrent source reload against its disk publication.
The package install operation lock serializes install operations with each other, not this watcher lock; B owns complete installer/caller reconciliation before any universal mutation conflict claim.
Ordinary ASGI shutdown may drain some application tasks, but these are private create_task background tasks rather than explicit request-owned work; no process crash or reproduced race is claimed.
Current test_stop_cancels_pending_timer stops before firing, test_stop_returns_when_observer_stop_blocks controls only Observer.stop, and suppress tests use no held in-flight executor.
Retain the bounded native observer wait, serialized watcher reload and synchronous fresh-package acknowledgment; future lifetime contract must separate physical executor completion from admission and event publication, not blindly cancel a future and assume its worker stopped.

#### A-F150 — Medium, source-established arbitrary FileNotFound reload error misclassified as full package removal

Tool_hot_reload.py416–439 catches every FileNotFoundError from registry.reload_package as absence of the package/version, forgets that package and broadcasts tool_removed for prior names.
A trusted package module can raise FileNotFoundError for a missing auxiliary input/resource during import even while the package directory exists.
ToolRegistryService reload first restores its prior class/meta on load failure; the watcher subsequently discards that retained catalog as if the package were deleted, defeating the intended load-failure preservation.
The private helper's filename category does not identify which resource is absent; no required disk-presence verification or structured PackageMissing discriminator occurs here.
Current test_full_package_removal_emits_tool_removed_per_class fakes precisely a missing-package exception, whereas test_reload_failure_broadcasts_system_error uses RuntimeError; no existing distinction covers a still-existing package with a missing internal dependency.
Retain genuine deleted-package removal and useful syntax/system diagnostics; future classification should follow the actual package directory/source authority rather than broad exception type.
No package import or failure was executed.

#### A-F151 — Low/Medium, qualified accumulated source-root ownership and polling retirement debt

Tool_registry.py484–496 adds workflow source root→tool-name sets but has no remove/replace operation when graph/workflow/source identity changes or workflows are deleted.
Hot_reload.py118–134 periodically hashes all remembered owned source roots, and319–335 emits names for any file under those roots before Python-only package filtering.
A previous tool name can remain in a source-change notification, and repeated live workspace changes accumulate watched roots/schedules; app.py current-workspace cache intentionally retains stores but no explicit source-watch owner retirement is established.
Catalog/frontend revalidation may ignore absent names or correctly reconcile active projections, so no stale execution result or unintended graph mutation is asserted here.
Current tests cover source-only root recovery and deletion, but no removal of an owned workflow/source reference and subsequent old-root edit; source roots are not identical to dataset paths and the scan exclusions are retained.
Future ownership should link watch subscriptions to retained workflow/draft/session identities and replace/remove only retired registrations, preserving historical captured sources still in use.
No memory/runtime measurement or native watcher was run.

#### A-F152 — Low/Medium, source-established concurrent-suppression test claims more than its oracle

Test_tool_hot_reload.py840–883 joins the bouncer and asserts only not t.is_alive; it does not retain worker-thread exceptions, capture asyncio unhandled task errors or issue a final positive event and await response.
The prose says no RuntimeError and service responsive, but async/thread exception reporting can occur separately while that final assertion still succeeds.
Existing deterministic suppress/resume tests retain positive event/batch oracles, so this test is supplemental stress rather than sole basic behavior coverage.
A future correction should reuse a held/captured boundary and positive final response instead of adding generic repeated sleeps or another opaque stress journey.
No assertion failure or flakiness was reproduced.

#### A-F153 — Low, loaded-source tests are textual preconditions, not executable/cache provenance oracles

Test_dev_mode_source_change_observable_in_loaded_class947–1012 compares inspect.getsource strings before/after file edit, and sibling-helper test1015–1073 compares unchanged class text while editing an unused helper.
inspect.getsource reads source text from the module file; it does not establish the new class executes edited bytecode, that an invoked sibling dependency changed or that a compute/cache admission hash changed.
The tests explicitly present themselves as preconditions, so their narrow source-text oracle is valid; comments implying authoritative CACHED status and frontend reconciliation exceed what they execute.
B owns actual source/signature/cache authority and A-F026 separately records timestamp/size stale pyc paths; no new duplicate runtime cache defect is created here.
Future evidence should label these as textual-source boundaries and extend an existing actual cache/source test only if executable provenance is required, retaining source-only construction without external environment provisioning.


### Complete-review checkpoint — reviewer-batch-30

#### reviewer-F062 — P2 convenience/loader coercion bypasses original public input refusal

ClusterEnvironment.from_uv_project:181–183 and from_pylock:217–219 call tuple on groups/extras before __post_init__/_string_tuple can reject scalar strings.
A mistaken string such as gpu becomes three valid character selections; later adapter preflight may reject nonexistent names, but that does not restore the intended local shape refusal and could select different existing groups/extras.
ParslConfiguration.from_file:488–490 similarly applies truthy defaults and iterates include before validating its original shape; a scalar path string becomes character paths and a dot character can become a broad cwd include.
Falsey invalid kwargs/ref containers are silently replaced with {}, so convenience factories differ from their stricter direct value constructors.
No incorrect install, sensitive archive or remote action was executed; downstream complete snapshot/deployment review is pending and may further mitigate capture scope.

The strict from_dict loaders also convert root/results_root/cluster setup/existing Python paths to PurePosixPath before normalized_cluster_path checks the original string, erasing dot/repeated-slash noncanonical spelling; .. and double-leading slash remain refused.
This is wire-canonical/refusal drift, not a claimed containment escape.
Existing test_cluster_environment_round_trip_rejects_non_array_selections protects the wire list shape but does not pass scalar groups/extras/include to convenience factories; existing normalized path test exercises the direct factory, not these loader paths.
Future smallest action:preserve and validate original types/spelling before normalization, extend those existing oracles, and retain supported tuple/list, Path/PurePosixPath, adapter and exact-schema round trips.
Do not restrict legitimate includes/adapters or invent a new config schema just to repair pre-coercion validation.

#### reviewer-F063 — P2 setup snapshot can block before rejecting a replaced special file

SetupScript.from_file:96–104 checks a path is regular/nonsymlink, then opens it O_RDONLY (plus optional O_NOFOLLOW), and only afterward checks descriptor identities.
If a same-user filesystem change replaces it with a FIFO between stat and open, the open may wait before reaching fstat/final identity refusal.
The64KiB read budget and final identity comparison do not protect this earlier blocking point; a before-open symlink is correctly refused on nofollow hosts.
This is an unexecuted local snapshot concurrency risk, not a remote attack, hostile-code isolation promise or actual hang.
Existing test_setup_script_rejects_unsafe_local_sources tests already-present FIFO/symlink only.
After the full gate, establish a bounded controlled source-swap oracle with explicit descriptor/process cleanup, then preserve exact source bytes/identity and regular-file refusal without private deletion or weakening trusted-code boundaries.

#### reviewer-F064 — P4 cluster value fixture assumes POSIX FIFO capability

The same test_values.py:152–162 unconditionally creates os.mkfifo and a symlink.
It has no local capability/OS guard, so its fixture requires POSIX FIFO and permitted link creation even though the tested shape/source refusal is otherwise an ordinary fast unit contract.
No non-POSIX test run or supported-platform failure is claimed; the library CI's existing host scope and any cross-platform release selection must be reconciled before requiring a portability change.
Future proportionate decision:make special-file capability explicit or split only that fixture precondition while retaining actual refusal assertions; do not classify a missing FIFO fixture as a passed refusal.


### Complete-review checkpoint — reviewer-batch-31

### Existing B-F089 corroboration — invalid-input errors can escape their advertised stable protocol category

protocol._decode_json:130–141 invokes json.loads before checking depth/value budgets and catches only UnicodeDecodeError/JSONDecodeError; parser RecursionError/deep-integer conversion errors can precede its own structured tree refusal.
GatewayResponse's diagnostic enum membership:336–339 likewise assumes hashable scalar input before category wrapping, so malformed JSON array/object values can raise raw TypeError.
Strict UUID/request-version/shape/finite/duplicate checks still fail closed before operation admission, and current request bool-version is explicitly rejected; do not transfer the looser B DTO bool claim to this constructor.
This extends the existing canonical B-F089 malformed/deep JSON exception seam, not a new finding or demonstrated accepted unsafe command.
Existing test_request_decoder_rejects_ambiguous_json and complete diagnostic refusal are meaningful; future smallest extension is to their missing structured depth/enum distinction after the gate, while tracing actual client error translation before asserting end-to-end impact.

### Existing reviewer-F062 extension — public report collection loaders erase original shapes

ClusterValidationReport.from_dict:327 tuple-coerces verified/declared/unverified facts before the constructor validates strings; a scalar distinct-character string becomes multiple facts.
ClusterCleanupReport.from_dict:429 similarly converts a scalar removed identity into character identities, and ClusterCleanupCandidate.from_dict:370 does the same for reasons/consequences.
These strict JSON-safe values preserve unknown-key refusal and typed booleans/digests, but do not prove original wire-array shape; downstream gateway/client admission is still pending review.
GatewayRequest.create:245 also silently defaults a falsey request ID before strict UUID validation; operation_id and stable mutation digest remain separate, so no replay or exactly-once failure is inferred from that default alone.
Future action remains original-shape validation before convenience coercion using existing value round-trip/refusal tests; avoid new schemas or removing supported collection inputs.

#### reviewer-F065 — P3 advertised RFC3339 validation uses a broader ISO parser

reports._utc_timestamp:80–91 requires only string suffixZ plus datetime.fromisoformat and UTC tz identity.
That parser accepts forms such as a space date/time separator or compact ISO date not matching the advertised RFC3339 grammar; actual expiry arithmetic still uses the parsed UTC time.
Existing test_reports_reject_inconsistent_or_malformed_state checks tomorrow, not a well-formed broader ISO spelling.
No expiry bypass, clock race, accepted scheduler allocation or malformed-time runtime result is asserted without execution.
Smallest future reconciliation:preserve valid UTC RFC3339/fractional timestamps and enforce their original grammar, extending the existing report refusal/round-trip assertion; do not narrow valid timestamps or remove expiry semantics merely to match a parser.

### Complete-review checkpoint — root-batch-16

#### ROOT-F083 — P2 source-established global automatic-name reset can replace an outer graph node

Node._get_next_name uses a process-global dictionary protected only during increment; _reset_name_counters replaces that dictionary on every Workflow.__enter__.
Workflow.__exit__ restores the active outer workflow but does not restore that outer counter dictionary.
Node.__init__ checks duplicate names only when the caller supplied name explicitly, and Workflow._register_node assigns directly into _nodes[node.name].
Thus an unnamed Foo_1 in an outer context, an entered/exited inner context without a Foo, and a second unnamed outer Foo produce the same Foo_1 key and replace the first map entry.
References to the first object can survive outside the authoritative node map; concurrent independent workflow contexts also share the reset authority despite their context-local active workflow.
This is a source-traced ordinary supported-context sequence, not an executed graph/result failure.
Full plan-status and dataframe/source counterparts verify fresh sequential workflows and explicit nested names, not outer unnamed identity after an inner context reset.
A confirmed no exact existing canonical naming finding.
Future smallest repair must give counters the actual workflow identity and enforce unique registration for generated names while retaining deterministic reconstruction, explicit names, graph references and nested contexts; do not change compute/cache semantics merely to rename collisions.

#### ROOT-F084 — P2 Core requirement name recognition misses accepted extras/channel-qualified dependencies

_core_dependency._dependency_name manually removes operators/markers/direct-reference separator but not a pip extras bracket or Conda channel prefix.
The canonicalized names bioimageflow-core[extra] and channel::bioimageflow-core therefore fail _is_core_dependency.
Core EnvironmentSpec permits such exact-version requirement spelling under its version guard, so core_requirement_conflict misses the explicit incompatible pip requirement and prohibited channel-qualified Conda Core declaration.
EnvManager._augment_dependencies uses that same predicate for conflict checking and removing existing pip/local Core declarations, then injects the configured Core dependency; the missed requirement survives beside that dependency.
Later resolution/exact recipe attestation may refuse this inconsistent recipe; no claim of silently installed wrong Core or actual worker failure is made.
Full494-line metadata and61-line dependency-floor counterparts omit this original-name classification case.
This is distinct from B-F130's specifier grammar and from known published/local Core version checks, which remain sound.
Future focused correction should parse backend-appropriate package identity before conflict/injection decisions and extend existing metadata/environment refusal oracles while preserving valid extras, exact configured Core and explicit channel semantics.

#### ROOT-F085 — P2 legacy public config-validation helper loses physical cleanup ownership on exceptional start/timeout

integration.validate_parsl_config_ref starts its spawned process before entering the pipe/process finally block, so process.start failure skips explicit parent/child pipe cleanup.
The timeout and finalizer use terminate plus bounded joins, without escalation or retained physical owner if the trusted child ignores termination or process cleanup raises.
A reported validation-timeout therefore does not establish the spawned validator stopped; no DFK allocation is needed to expose that lifetime seam.
The public helper is distinct from the managed validator B-F126 and no claim the current platform uses this legacy helper is made.
Parent.poll then blocking recv also needs the shared bounded-frame deadline policy qualification already recorded for other trusted-peer pipes, rather than a new unsafe-command claim.
Full distributed counterpart checks actual valid factory labels, missing-secret refusal and sanitized failure text, but never holds a validator/start-cleanup fault through the ownership boundary.
Future bounded fault oracle and ownership repair must preserve nonallocating trusted-factory validation, secret sanitization and honest logical-versus-physical timeout reporting; do not execute arbitrary factories or promise an OS sandbox.

#### ROOT-F086 — P2 default DataFrame merge deletes genuine columns matching its private duplicate suffix

DataFrameTool.merge_dataframes inner-joins with rsuffix=__bif_dup, then filters every output column ending in that suffix.
That removes not only newly suffixed right duplicates but also an original left column or noncolliding right user column with the same legitimate name.
Dynamic DataFrame schemas and source-generated column names have no reserved suffix refusal at this public boundary; no user-column merge was executed during this audit.
The complete dataframe integration counterpart distinguishes passthrough/dynamic columns but supplies no two-input literal-suffix fixture; default left-wins duplicate policy remains intentional.
This is distinct from B-F055's frontend absoluteRow overwrite and declared explicit catalog merge policies.
Future smallest correction should track precisely which duplicate columns the merge owns while preserving inner-index alignment, existing left-wins behavior and all genuine user columns.

### Existing A-F041 extension — positional symbolic field refusal occurs after registration outside rollback

Node registers into its workflow before processing positional arguments.
A field-kind WorkflowInputRef supplied positionally raises BindingError before the keyword-binding try/except removes the node, leaving the rejected node registered.
Earlier positional table refs can also attach workflow input targets before a later rejection; existing keyword rollback removes the node map only and does not restore already published targets.
The full dataframe binding counterpart strongly asserts atomic invalid-column keyword refusal including table refs, which occurs in an earlier precheck; it does not distinguish this positional or later-target boundary.
This corroborates the existing canonical register/publish-before-final-admission issue, not a new duplicate finding.
Future correction must retain intentional invalid-edit capture mode and make ordinary rejected invocation restore every mutation it owns.

### Qualified maintenance/test/doc candidates and retained structures

The nominal integration type-compatibility file does not construct a workflow despite its opening coverage claim; several annotations/layout/wildcard assertions duplicate unit cases, while unit frozen GUIMeta/scalar-group/extraction assertions remain distinct.
Consolidation is a future selector/oracle-preserving candidate with no measured runtime gain or automatic deletion.
The timestamp template test checks only the number of underscore components, not numeric timestamp expansion, and several broad exception assertions could mask incidental failures; tighten an existing oracle after the gate rather than add another opaque journey.
Template substitution runs multiple passes, so inserted brace-valued data can be interpreted on a later pass; literal-data versus recursive-template policy should be specified before treating it as a defect, and Core output containment is separate.
Public planning/capability/diagnostic DTO loaders have weaker scalar/boolean/collection validation than strict gateway values; classify consumer trust and intentional compatibility before imposing a new schema or asserting execution admission bypass.
The metadata-unavailable Core fallback explicitly warns that it installs latest, and empty home override policy is not an actual absolute-path runtime failure.
Actual Direct template/source/cache-plan/relative-path subprocess tests, exact constructor side effects, and structured resource/failure contracts are preserved as distinct boundaries.
Python3.9 AST/annotation guard is a useful syntax precondition, not a real Python3.9 dependency import certificate; CLI mocks prove forwarding while storage tests own physical export behavior.
M1 remains OPEN; repairs, new diagnostics and all application acceptance phases remain held.

Twenty-six complete owned inputs / 5631 lines.


### Complete-review checkpoint — B-batch-23

### Existing findings reconciled against complete normative authority

B-F085's documentation distinctions are retained: the scalar identity implementation's missing-value branch maps NaN rather than representing a separate advertised NaN sentinel; B075 numeric category label restoration and B076 NFC column naming remain source mismatches, not mathematical Infinity defects.
The scratch paragraph permits returned work artifacts while the path-canonicalization chapter rejects any mutable attempt workspace outside assets and current implementation/tests enforce that stricter confinement.
Future wording must choose the actual owned-assets authority clearly rather than authorize arbitrary scratch-path publication.
Legacy fixture run names distinguish safe reader compatibility from UUID grammar for generated execution IDs; no new traversal flaw is inferred.

Reviewer-F042 is corroborated again by the recommended planning status list in the storage document, which omits CORRUPT even though the corruption prose and implementation handle it explicitly.
This is the same canonical documentation family, not a new B finding.
The current remote guide's golden factory explicitly adds the tool environment's exact dependency/Core attestation alongside the runtime deployment binding.
It therefore demonstrates the supported explicit workaround and correct refusal boundary for reviewer-F040; the simplified experience/golden runtime-only seam remains separately qualified.
No wrong-worker dispatch or real scheduler failure was proved.

B067's narrowed logical identity omission conflicts with the normative inclusion of tool identity/output contract; already captured source-content hashes are not omitted.
B074/075/076 challenge exact logical scalar/schema preservation in separate ways; generic file equality does not replace their intended canonical value contract.
B068/A-F030 are explicitly limited by the storage specification's permission to coordinate externally: invalidate must use guarded updates or external coordination with active compute.
A plan is a storage snapshot and legitimately changes if upstream current selection changes before compute; that is not evidence for mandatory frozen-plan dispatch.
B079 transient terminal metadata guards, B083 directory durability, B080 external replace admission, and B131/132 deterministic retry replay remain bounded source findings against these intended guarantees.
The document does not promise universal filesystem atomic directory replacement; it expressly promises failure-safe current output restoration, so do not widen B084 cleanup/failed-ack into an unsupported universal atomicity claim.


### Complete-review checkpoint — reviewer-batch-32

#### reviewer-F066 — P3 failed local snapshot cleanup loses explicit retry ownership

PreparedClusterInvocation.close:222–232 sets _closed before TemporaryDirectory.cleanup and clears references only after that call returns.
If cleanup raises, the root/temporary references remain, but a subsequent public close returns immediately because _closed is already true; the public owner cannot explicitly retry physical reclamation through that method.
This is a qualified local cleanup-failure source candidate, not a reproduced leftover, permanent leak or remote run damage:TemporaryDirectory finalization and external filesystem recovery may still remove bytes.
The active plan lease correctly refuses close before any destructive action, and successful close removes only the owned temporary root; neither invariant should be weakened.
Existing test_close_is_idempotent_and_removes_only_owned_snapshot covers successful cleanup, not failure/retry.
A future bounded diagnosis should distinguish logical closure from retained physical cleanup ownership using that same test family before changing close state semantics; no runtime action is released.

### Existing findings corroborated without new admission claims

reviewer-F062 extends to PreparedInvocationManifest targets and from_dict collection coercion:tuple('ab') becomes individual target strings before shape validation; exact-key refusal and deep-frozen inputs/overrides remain intact.
RemoteNodePlan's requirement mapping is shallow-frozen, but RemoteExecutionPlan.to_dict/submit verify the complete confirmation digest, so no silent accepted changed plan is claimed.
The public plan uses the same suffixZ plus broader fromisoformat timestamp parser as reviewer-F065; actual UTC expiry checks remain effective.
RemoteExecutionPlan.submit keeps one stable attempt/run identity, verifies prepared bytes and digest, revalidates before sealing, and refuses release of a sealed uncertain snapshot.
Concurrent submission and the client/gateway's durable acknowledgment consumer remain assigned for later complete review; no inferred duplicate allocation or speculative private-attribute security finding is added here.
The owned preparation enforces finite positive lifetime, unlike the separate older launcher prepared TTL canonical B-F087.

M1, fixes and all runtime checks remain held.


### Complete-review checkpoint — A-batch-29

#### A-F154 — Medium, qualified stale catalog GET can overwrite a newer event or newer fetch

ToolRegistry.ts90–110 replaces whole tools/packages after each GET with no request epoch, captured event revision or merge barrier.
applyToolReload290–323/applyToolRemoved325–350 and install event135–139 can update the catalog while an earlier GET remains pending.
A late older response can therefore reintroduce removed metadata or erase a newer schema/version until another event/refresh; a GET serving authoritative state after the event is sound, and actual server response order determines the distinguishing schedule.
Same browser connection events are ordered, but that does not order their retained mutations against independent HTTP completions.
Both full store test families use immediately resolved GETs and synchronous events; no held older GET versus newer read/reload/remove oracle exists.
Retain array replacement reactivity and ordinary active catalog semantics; future reconciliation should own accepted snapshot/event revisions at the actual API boundary rather than indiscriminately drop all refreshes.
No timing reproduction, wrong execution or portable rebind result is claimed.

#### A-F155 — Low/Medium, source-established busy and refresh acknowledgment ownership gaps

Custom actions224–287 share one customToolBusy boolean without cojoin/admission or operation-owned finalizers; two direct concurrent calls let the first finally set false while the second is still pending.
Package installation has a per-key set and duplicate coalescing, so it already avoids that exact same-key busy collision; caller GUI prevention may mitigate ordinary custom double clicks but the store itself exposes all actions.
fetchTools/fetchPackages swallow read failures, so create/rename/delete/install Promise.all refresh completes successfully even when a read failed; the outer action then clears error and returns success despite stale read models.
The write may genuinely have succeeded and must not be replayed as if uncommitted; the defect is indistinguishable refresh/acknowledgment state and diagnostic clearing, not an assertion the backend write failed.
Current custom error tests reject the write itself, and install busy test releases POST then immediately resolves GETs; neither distinguishes failed postcommit refresh or two held custom operations.
Future ownership should retain write success separately from refresh failure and operation-specific busy finalization, reusing these focused selectors rather than another full user journey.

#### A-F156 — Medium, qualified compound custom operation loses workflow context between usage/confirmation and action/result consumers

currentWorkflowRequestConfig80–87 captures the current name independently in getToolUsage240–246 and deleteTool267–287; it does not return a context-bearing usage token to subsequent delete.
Borrowed ToolsPanel requestDeleteCustomTool607–649 awaits usage, shows confirmation and later calls deleteTool using whichever workflow is then current.
The warned usage/source can belong to workflowA while confirmation executes a same-name tool action under workflowB if selection changes between those steps.
Creation similarly captures a request workflow, but response lacks owner identity and borrowed onToolCreated327–337 opens that name in the then-current workflow.
Normal immediate stable selection works, and backend exact source resolution/conflict guards may refuse a missing same-name tool; distinct same-name workflow-owned sources are the distinguishing case, not every palette operation.
Complete ToolsPanel review is pending, so UI gating mitigation remains qualified until its full lifecycle/judgment.
Store custom tests run with no current workflow and no context switch; mounted dialog test observes only the emitted name/path.
Retain per-request captured query and backend ownership/refusal; future compound flow should pass captured workflow/source identity across warning, acknowledgment and editor continuation without replaying writes.

#### A-F157 — Low/Medium, source-established submitted form completion has no visibility/recipe owner

CreateToolDialog.vue65–77 checks only current createDisabled, starts a store action and later emits created and clears form fields without a submission token or visibility/unmount/cancel check.
The Create button127–132 is not disabled by customToolBusy and onCreate does not guard an existing pending submission.
After cancel/reopen/new edits while a request is retained, the previous completion can emit an old result and clear the new form; duplicate calls can also send the same write, normally refused by backend conflict rather than creating two same-name tools.
POST rejection propagates to Vue event error handling without a local form presentation; store.error exists for parent use, so no completely invisible error claim is made.
Current tests invoke exposed onCreate with immediate success and onCancel separately; no pending form ownership/failed click oracle.
Retain valid name normalization/backend conflict authority and postcommit write success; future finalizers need submitted form ownership independent of live edited recipe/current selection.

#### A-F158 — Medium for display correctness, declared/effective resource floor UI has no canonical producer

NodeResourcesTab.vue38–58 expects tool.environment.resources, but fully read ToolRegistryService223–230 emits environment name/dependencies only; environment is not the class's independent resources requirement authority.
Root complete NodePanel confirms1202–1205 directly passes nodeData.tool, no enrichment; ordinary registry/owned-class metadata production therefore displays a dash for real declared floors.
The Effective column69–74 simply shows override-or-declared; a proposed below-floor override is displayed as effective before authoritative preflight later refuses it, with no local floor distinction.
The execution engine/library public resource validator still enforces actual resolved class floors/caps, so this is inaccurate/missing user guidance, not wrong worker admission or proof distributed execution ignores requirements.
The test invents environment.resources and does not assert the real declared/effective numbers; actual Core model/schema source boundaries must supply the future GUI oracle.
Retain sparse node overrides, strict resource grammar, no invented native/engine limits and actual preflight refusal.
This is the precise UI consequence of A-F147's partial environment summary; avoid treating environment summary as a new execution authority.

#### A-F159 — Low, specific fixture/oracle drift and duplication candidates

Historical store mockTools20–61 omit current required ToolMetadata flags/row consumption/source_kind/editable, and mockPackages64–81 reverse tools membership keys.
The generated schema confirms mandatory fields and version→names shape; these targeted fake tests remain useful search/event checks but cannot be cited as current schema compatibility.
Create dialog Button stub32–36 uses attrs.disabled after declaring disabled as prop, so real button-disabled DOM behavior is untested there.
Resource test title16 promises declared/override/effective display but assertions22–25 cover headings/local/reset only.
Fix fixture authority/strengthen existing assertions before adding duplicate tests; retain distinct custom API action versus search/environment behavior, and evaluate behavioral overlap of the two membership families before consolidation.
No frontend type check/test was run; no claim the current harness necessarily fails type checking or UI gestures is made.

### Complete-review checkpoint — B-batch-24

#### B-F150 — P2 declaration/recipe risk: sampling four versions cannot prove a Python3.12-only constraint

`models/napari_environments.py:_validated_python_constraint` accepts a SpecifierSet by testing3.12.0,3.12.99,3.11.99 and3.13.0.
The predicate cannot establish that every accepted version is3.12 or that the requested set exactly matches its realization.
For example, a constraint permitting>=3.12 while explicitly excluding3.13.0 can pass these four checks but still permit3.13.1 and later minors.
Likewise a3.12-only constraint can exclude an intermediate patch while passing the two required endpoints.
This is a static PEP440 set/point reasoning example, not a new executed model test.
The actual service `_environment_spec:1295–1302` hardcodes `python='3.12.*'` and does not pass the stored constraint to Wetlands, mitigating any claim of provisioned wrong-minor Python.
Its comment says recipe validation proved exact Python3.12, but accepted exclusions can differ from the actual wildcard recipe.
Existing `test_advanced_recipe_requires_exact_napari_and_qt` rejects plain>=3.12 and correct advanced cases, while managed service translation tests expect stored constraint plus wildcard realization; they do not distinguish disjoint holes or an excluded neighboring endpoint.
Future action: define whether the declaration denotes supported minor family only or an actual patch restriction, then validate/normalize that contract precisely while retaining the supported3.12 environment matrix.
Do not claim actual incompatible runtime provisioning from this predicate alone.

#### B-F151 — P3 private protocol robustness: malformed authenticated command can escape typed parser

`_external/napari_manager.py:_validate_command` evaluates `action not in {'open','shutdown'}` before a string/type guard.
An authenticated decoded object with list/dict action raises TypeError instead of returning the documented typed command error.
The extra-field path also sorts arbitrary dict keys and joins them as strings; malformed nonstring/mixed keys can escape similarly.
The Listener loop invokes this parser outside a catch for validation exceptions, so that command can terminate the IPC listener thread and leave the GUI without a response.
Ordinary launcher commands use string actions and field names, and the caller has a response timeout/outcome-unknown boundary, mitigating any default valid command failure claim.
No unauthorized network access, exploit, actual listener crash or native outcome was executed.
Existing exact selectors `test_handle_command_non_dict_returns_error` and `test_validate_command_rejects_unknown_fields` cover nonobject commands and an ordinary extra string, not malformed nested/container action or key shape.
Future action: make this parser total for its authenticated wire domain, retaining exact strict fields, request correlation and no unsafe retry after uncertain opens.

### Existing test isolation/lifetime findings extended

B056 extends to the manager test loader: `sys.modules.setdefault` permanently registers napari/napari.qt/napari.qt.threading stubs with no restoration.
The standalone source delays native imports until main, so those stubs are unnecessary for pure parser calls and can contaminate later import/capability expectations in a shared test process.
This is source isolation risk, not an observed order-dependent failure.
The historical docstring still references thread_worker despite the current Qt Signal/Slot implementation, and helper stubs reproduce that obsolete mechanism without exercising it.
B012 applies to the completion test: callback waits without timeout and release is not in finally; assertion failure before release can leave non-daemon waiter/callback threads alive.
Its ordinary success-path event ordering is meaningful, but a Python Thread invoking helper completion is not native Qt/Listener integration credit.

### Complete-review checkpoint — reviewer-batch-33

#### reviewer-F067 — P2 declared package-root selection can capture an entire repository

_deployment_snapshot._package_directories:286–333 accepts setuptools package-dir values and Hatch wheel package roots directly; a declared value '.' nominates project_root itself.
_capture_project_inputs:337–361 then passes that root to _copy_tree, which recursively copies all regular non-symlink files up to the limits, rather than selecting distribution members through their declared build metadata.
A common flat-layout setuptools package-dir {'':'.'} is therefore a source-proven selection candidate for unrelated notes, VCS/configuration files or local runtime material, or an avoidable quota refusal.
This contradicts the normative explicit selected-project-source boundary in remote_cluster_technical_spec:46/198–199, which excludes recursively uploading an entire repository.
No actual credential inclusion, upload or unsafe execution has been demonstrated; local build metadata and trusted user code remain explicit trust boundaries.
Existing test_declared_local_project_sources_are_snapshotted_but_unrelated_files_are_not tests the named inferred package directory, not a valid root-level package-dir declaration.
Future diagnosis should extend that existing source-selection oracle with valid flat-layout metadata and prove required package files remain included while unrelated root files remain excluded; preserve essential local-project support rather than simply refusing common metadata.
The exact public entry is prepare_deployment's uv/Pixi/pylock project-input capture; managed Pixi/pylock end-to-end capability flags remain unsupported and must not gain runtime credit.

### Retained capture and boundedness distinctions

reviewer-F063 extends to _copy_regular:the regular-file precheck precedes potentially blocking os.open; a same-user replacement FIFO can block before its post-open fstat/identity check. No remote attacker or reproduced stall is asserted.
Its stream loop also detects final mutation/bundle limits after copying; all-POSIX installer capture and registry wheel capture accumulate before the final aggregate manifest check. This corroborates B-F093's post-copy resource-budget seam, not bypass of eventual refusal.
_run_uv captures subprocess PIPE output wholly before its caller considers failure; canonical B-F098's output-memory concern applies to this local trusted-build subprocess too. Timeouts and sanitized/offline environment remain real controls.
The exact build helper checks sdist/wheel identity and universal wheel tags; main tests intentionally replace it and installer capture with deterministic fixtures, while test_local_distribution_build_is_offline_non_editable_and_hashed is the separate real helper oracle.
Current capability tests explicitly keep managed Pixi, pylock and wheelhouse end-to-end support false; their local snapshot implementation is not runtime certification.
PreparedDeployment verifies captured bytes, frozen metadata, identity entries and manifest digest. Its cleanup remains directly retryable, unlike reviewer-F066's early-closed invocation owner.

### Complete-review checkpoint — root-batch-17

#### ROOT-F087 — P2/P3 broad integration tests overclaim cache, pruning and version/binding distinctions

TestCacheHit.test_second_run_uses_cache compares equal DataFrames from deterministic constant stubs without an execution counter; wrong recomputation can satisfy that equality.
The cached-status sibling checks any cached event, so source caching alone does not establish the segment's no-execution promise.
TestCacheMiss.test_different_upstream_invalidates_cache adds a file before the first compute and asserts four rows, never observing an old upstream selection or changed-key/reexecution transition.
Dev-mode source miss changes StubSegmenter to ModifiedSegmenter, hence class/auto node name, while the environment miss changes ToolV1 to ToolV2, environment name and method/output too; neither isolates source/dependency-only invalidation.
The basic dev-mode hash test computes once and counts rows without checking a source contribution to identity.
Branch pruning checks absence of results/data/branch_b, a legacy path outside current canonical immutable record storage; it uses no throwing/counted dead tool or actual record selection to distinguish unintended execution.
Versioned cache miss filters events with lowercase alpha although generated node names are AlphaTool_1; its empty cached list is vacuous even if the named versioned node emitted cached.
The title promising versioned column bindings supplies a constant value and never connects its _raw loader; stronger actual version-specific value and export/load tests remain meaningful.
Reenable cache uses equal deterministic frames only, and the broad partial-rerun pipeline counts two cached events rather than identifying the claimed segment and stats nodes.
These are exact static test-oracle distinctions, not executed failures or proof the corresponding product behavior is wrong.
B confirmed existing split validation/task/data-table oracle findings do not cover these selectors; the strong runtime_cache suite separately asserts actual execution counters, bytes and identities and must remain.
Future optimization should strengthen or rename these existing selectors and reuse the smallest counter/identity fixtures before adding new broad journeys; consolidation requires an explicit branch/oracle map and measured cost, not wholesale deletion of composed Direct coverage.

#### ROOT-F088 — P2/P3 progress tests can pass without their claimed node/row events

TestProgressCallback.test_status_transitions only enters its assertions if seg_events is nonempty, so complete loss of segment events can pass.
Test_row_complete_reports_progress loops whatever row events exist but never asserts their presence, exact row set or per-node ownership; zero row events satisfy it.
Test_progress_event_fields also loops potentially empty events, while the single-node callback test only proves FileLoader-like naming.
The multi-node test checks two distinct names without specifically requiring segment/stats or any actual interleaving despite the opening claim.
The real typed resource/parallel terminal-diagnostic tests and cached-status tests preserve separate guarantees, so no blanket rejection of the progress suite is warranted.
Future smallest change should make expected events non-vacuous and correlated per node, retaining any contract that intentionally does not emit row_complete for some tool modes; do not force unsupported intermediate telemetry merely to match a stale title.
No callback run, missing event reproduction or timing result was produced during review.

### Existing A-F121 extension — versioned fixture cleanup does not cover loader store authority

The complete versioned test fixture removes matching sys.modules and sys.path entries after each test, but does not reset the loader's cached package/version entry whose store-root omission is A121.
Its fixtures use the same dummy_tools package/version and equivalent implementations across different temporary roots, so successful value assertions do not distinguish stale store origin.
Source-local actual scoped-module tests elsewhere remain authoritative for their specific origin/class expectations; do not assume these host tests certify separate managed worker stores.

### Existing B-F117 extension — broad integration SHM stub retains external unlink ownership

StubSharedMemoryTool uses create_shared_output and returns its descriptor after the context closes the local handle, without an explicit unlink owner in this fixture group.
The present broad files do not invoke that stub themselves, so this is a fixture ownership qualification extending the exact runtime SHM tests, not a new observed leak or segment count.

### Retained architecture and proportionate suite candidates

Default-empty, opted-in empty reduction, immediate-parent anchor and partially empty expansion tests distinguish real cardinality/data/artifact policies; existing four-row numerical/scientific and immutable zero-row tests remain separate.
Edge-ID and postponed-annotation tests assert strict structural/error identity and module/class resolution without external dependencies; they are useful focused-development guards.
Actual version-specific output bytes/value, canonical selected-pointer invalidation and graph enabled export/load tests retain real state oracles.
Host fixtures write synthetic image text and run Direct, so declarations of Cellpose/Stardist/GPU environments are no actual binary/model/hardware certificate.
WorkerException test rethrows a local Direct ValueError and does not assert an external original stack trace; broad exception regex cases merit exact-category tightening within their existing families.
The deterministic primary-failure test biases fast/slow completion using delays but does not explicitly witness completion order; keep the compiled-order promise and investigate a bounded event-controlled oracle if needed.
Comparison pipeline documentation claims suffix-handled retention but actually drops one mask and includes an unused JoinOnColumn; clarify what comparison data the intended acceptance scenario preserves before changing its feature scope.
Repeated chain setup across count/path/cache/monitoring cases is a maintenance candidate; preserve each unique structural/artifact/ownership assertion and avoid claiming an unmeasured speedup.
All fixes/new tests/execution remain held and M1 remains OPEN.

Sixteen complete inputs / 3463 lines.

### Complete-review checkpoint — A-batch-30

### Existing A-F156 extension — full compound source/tool consumer confirms no captured-context handoff

Entire ToolsPanel script and both action templates contain no captured workflow/source owner or active-context check between usage607–625 and confirm.accept628–649.
Current store captures workflow query only when each request begins; a later confirm uses later currentName.
Entire onToolCreated327–338 likewise closes showCreateDialog and invokes managed editor with the then-current workflow.
Normal stable action tests remain valid and backend missing-source/conflict checks may refuse an inapplicable name; same-name distinct owned sources plus selection change are the specific risk.
The rename/delete CustomEvent payload also carries only names/results rather than workflow generation/source identity; Canvas listeners reconcile by name, with actual draft validation/owned-source rules retained and no universal wrong-graph mutation alleged.
Future repair must preserve the existing request/source authority and successful write independently of subsequent view/editor presentation; no repair authorized during this audit.

### Existing A-F155/A-F159 extensions — consumer refresh and fixture authority

Panel install/uninstall/use/recreate/source-install success paths inherit swallowed fetchTools/fetchPackages errors and can show successful metadata refresh after a committed write while views remain stale.
The broader fake package fixtures still reverse version→tool-name membership, while current ToolMetadata main fixtures now include all capability/row-consumption/source flags; do not extend the missing-flag critique from older store tests to these corrected mocks.
Busy-only package fixture likewise reverses membership; empty-store tools{} is correct and should remain.

### New findings backlog

#### A-F160 — Low/Medium, source-established late mount listener survives unmount

ToolsPanel.vue802–805 awaits Promise.all catalog reads before document.addEventListener; onBeforeUnmount807–809 removes the listener synchronously.
Unmount while either read remains pending removes an as-yet-unregistered listener; the later mount continuation still registers it with no unmounted/token check and retains panel closure/state.
Normal completed mount/unmount removes it correctly; tests exercise immediate reads and no held GET through unmount.
The listener only closes version dropdown state, so this is retained lifetime/possible duplicate handling debt rather than arbitrary data loss or security bypass.
Retain outside-click close behavior and watcher-owned selection fencing; future admission must check mount owner before registration and pair acquired listener cleanup, not add a fixed timing wait.

#### A-F161 — Low/Medium, source-established version-selection guidance misstates scope and captured-binding authority

ToolsPanel.vue480–495 says there is one active version per package for this workflow and every node will use its new schema.
Actual use_package_version router478–503 takes no workflow id/name, updates the shared ToolRegistryService plus catalog and returns an active preference acknowledgment.
That palette choice can affect ordinary unbound/new nodes across callers; correctly captured portable existing nodes must retain their carried source/module/package/version authority rather than accept this claimed every-node override.
A-F001 is the separate current consumer violation, not justification for normative misleading UI text.
Current useVersionInWorkflow posts /use and refreshes when the user confirms checks the request only with immediate auto-accept and does not assert scope/retained portable identity.
Retain ordinary catalog active choice and failed-version refusal; future guidance should name actual palette scope and distinguish supported explicit workflow rebinding from merely choosing a registry version.
Backend full tools route is B-owned; this report takes only the cross-owner exact entry context.

#### A-F162 — Low/Medium, source-established sidebar environment control omits updating ownership gate

Manage template1266–1274 disables power during isEnvironmentBusy, but sidebar962–966 disables only isRunning or unavailable.
toggleToolEnvironment714–741 checks executionStore.isRunning and unavailable, not isEnvironmentBusy or a retained pending operation.
A source-recreate/updating environment can therefore still receive sidebar start/stop requests while its Manage controls are disabled; authoritative backend operation/admission refusal can mitigate physical conflict and is owned by B.
The full shared-updating test asserts manage controls only, and the sidebar test checks the running class after a status event, not updating disabled behavior.
Retain shared environment-name busy ownership and actual provider lifecycle/refusal; future client parity should reuse the existing control test rather than duplicate provisioning/browser journeys.
No destructive worker/environment concurrency or failure was executed.

#### A-F163 — Low/Medium, source-established panel test lifetime/oracle gaps and bounded redundancy candidates

Most ToolsPanel.test.ts mounted wrappers are never unmounted; afterEach288–291 resets command/persistence registries only, while busy/empty suites also leave wrappers mounted.
Borrowed current frontend/tests/setup.ts supplies PrimeVue providers/matchMedia and no automatic wrapper unmount; the full test runner/config belongs reviewer and any additional teardown must be reconciled before a universal cross-file leak claim.
Ordinary onMounted eventually installs document listeners; retained wrappers can therefore leave watchers/listeners in the test document and make later behavior less isolated.
Loading-event/prompt tests restore globals/listeners only at their successful end in several cases, unlike the two explicit finally cleanup cases; assertion failure can leave global contamination.
Test titles 'showManageDialog toggles via manage tools button' only assign vm.showManageDialog and 'installVersion calls POST and refreshes packages' only assert POST after initial mount GETs; current toggleEnvironment refresh title asserts any GET including mount, not a post-call cardinality/order.
Busy-file install/error cases overlap store+main coverage, but rendered main spinner/logger, held uninstall and clean-store tree/version flags are distinct useful contracts.
Future suite work should strengthen exact existing post-action/cleanup oracles and consolidate repeated fixture setup without growing journey counts or deleting distinct consumer evidence; no measured performance claim or test run is made.


### Complete-review checkpoint — A-batch-31

#### A-F164 — Low/Medium, qualified export error presentation and retirement lack accepted owner checks

WorkflowExportDialog.vue149–154 checks abort before awaiting actionError, but actionError/responseData can await Blob.text; after that await it sets shared errorMessage without rechecking controller/visibility/target ownership.
Close/reopen or a newer action during that parse can receive the prior failure's late message, while its finally correctly avoids clearing a newer controller.
The accepted response/presentation owner is therefore distinct from the already-sound operation finalizer.
The component has no onBeforeUnmount abort/dispose; a retained prepare/folder-picker/export promise can continue after actual component retirement unless its parent closes visible first or transport/page teardown stops it.
Normal close watcher aborts and save/picker checkpoints check signal, so no universal unmount write, actual canceled-copy loss or retargeted export is claimed.
Parent captured exportDialogTarget mitigates ordinary canvas switches, and backend operation may already be committed when client cancels; never replay or assume physical rollback solely from AbortSignal.
Current Blob error test completes parsing before cancel and later holds a different unresolved export, so it cannot distinguish old parse versus new presentation.
Future ownership correction should guard accepted error/result presentation and retire only this component's admitted client owner while retaining successful server operation identity and useful conflict/refusal behavior.
No asynchronous reproduction/native action occurred.

#### A-F165 — Low, source-established new workflow guide asks for a field the dialog no longer has

Docs/user/build-workflows.md10 asks workflow name, display name and description.
Complete WorkflowDialog exposes one readable Name input, derives the ID, and its actual DOM test explicitly asserts no workflow-name-input exists.
The current single-readable-name convenience and backend suggested ID behavior are sound; future guide should explain that the filesystem ID is generated rather than require a nonexistent second field.
No change to backend naming/identity contracts is authorized here.

### Existing A-F161 documentation extension — data/tool guide inherits shared palette scope mismatch

Docs/user/data-and-tools.md22–23 says a workflow uses one selected version and changing it asks before updating existing outputs.
Complete ToolsPanel confirmation modifies shared catalog /use and promises every node's schema; actual captured portable node bindings must stay independent unless explicitly rebound.
No actual output-file rewrite is performed by that selection request; current consumer schema-reconciliation defects A-F001/A-F066 remain separate.
Future documentation should identify palette version selection versus explicit installed alternatives/portable binding mutation and preserve exact version install/refusal.

#### A-F166 — Low, coverage inventory generic duplication and revision provenance debt

Docs/developer/coverage-workflows.md7 introduces an audit at fcb4408, but body rows include later historical source/evidence updates and revision-specific certification references.
Exact citations and explicit current dashboard states mitigate misleading blanket historical claims, yet the heading does not explain which content belongs to the original snapshot versus subsequently reconciled composition.
Dozens of S/R/F/P/B cells repeat generic 'exercise row boundary' prose rather than the exact oracle; some rows already use better concrete scoped wording.
This repetition increases review/maintenance surface while the linked dashboard is declared state authority, without adding a new architectural or runtime contract.
Future consolidation should keep stable feature IDs, exact selector/identity/negative oracle and historical evidence limits once, linking actual delta authority rather than broad test-count obligations.
No false all-suite pass is inferred, and the current full audit still precedes every repair/campaign execution decision.

### Existing A-F072 extension — exact Open dialog list action transports no selected generation

OpenWorkflowDialog exposes name-only open events despite each WorkflowInfo carrying identity_generation, and onOpen only checks selectedName truthiness, not current membership/generation.
Its visible watcher is not immediate; standalone initially-visible mount starts with no selection, while the normal persistent MenuBar opens by false→true transition and is mitigated.
A removed/recreated selected item or first invocation owner race is the existing A-F072 contract, not a new reproduced issue or claim ISSUE-022 cause was established.
Full67line tests click a currently valid row and prove full ids/search only.

#### A-F167 — Low, Open dialog initial/filtered selection oracle qualification

Filtered list changes do not reconcile selectedName and Open remains enabled for a selected hidden or removed workflow; the backend can refuse a missing name, and retaining a filtered-out selection may be deliberate design.
Standalone visible=true initialization has no default because the visibility watcher runs only on transition; persistent parent mount normally transitions and supplies valid rows.
Current tests mount visible=true but immediately click, bypassing both default/current selection and list-change behavior; a search test verifies rows but not which id submit would open afterward.
Future requirement clarification should decide retained selection semantics and strengthen an existing exact component assertion, without inventing general stale-name generation behavior already owned A-F072.
No invalid Open request or application failure was executed.


### Complete-review checkpoint — B-batch-25

#### B-F152 — P2 physical subprocess source risk: probe bounds retire only the immediate process

`napari_environments.py:_bounded_run:117–177` starts a subprocess and pipe readers, applies output/timeout bounds, then kills/reaps only the immediate Popen process.
Conda-run or a selected interpreter can create descendants which retain stdout/stderr descriptors; no process-tree ownership or retained retry handle exists in this helper.
After bounded reader joins, closing a buffered pipe while a reader is still blocked can itself wait on that reader's internal lock, so the advertised timeout is not a proven total physical bound for a descendant pipe-holder schedule.
Reader-thread start happens before the process cleanup try; failure creating/starting a reader can likewise leave the child without the usual ownership cleanup.
The real existing `test_probe_runner_enforces_time_and_output_bounds` checks a simple sleeping interpreter and simple oversized print, not descendants or thread-start failure.
This is source-only and does not assert ordinary metadata probes actually hang or leak.
Future diagnostic should distinguish exact child/tree completion and pipe ownership while retaining bounded metadata-only probing; no broad native supervisor rewrite is authorized.

#### B-F153 — P2 live-operation adoption gap between public provisioning and owned completion task

`_begin_new_managed` persists a creating entry/operation, then calls `_start_provisioning`.
`_start_provisioning:623–649` obtains the manager outside its exception conversion, starts the public operation, records it in `_wetlands_operations`, then awaits a settings transition before attaching listener and registering `_complete_provisioning` in `_operation_tasks`.
A manager-provider failure after durable admission leaves a nonterminal creating record without a typed terminal operation.
A failure or route-task cancellation after public provision but during awaited `_update_operation` can leave a real operation with no service completion task; `close` cancels map operations but only waits its task map, and does not drain these orphaned physical operations itself.
Public cancellation may request Wetlands cancellation but no registered continuation converts its completion into registry state in this path.
Startup reconciliation provides later recovery, which mitigates durable restart confusion but not current ownership/drain or automatic live completion.
Removal begins inside an already owned task and has a different adoption boundary; do not conflate it with this public-start window.
Existing FakeManager tests cover normal errors/cancellation after task registration and use immediate fake cancellation, not these exact failure windows.
B024 raw task cancellation also affects bare asyncio.to_thread wait/probe boundaries and cancellation of service close/gather; normal close requests cancellation and waits tasks, so no blanket normal shutdown failure is inferred.
Event listener tasks are separately untracked, see B156.
Future approach should ensure physical operation ownership is established before fallible/awaiting publication and preserve typed failure/restart recovery/public progress semantics.

#### B-F154 — P2 source lost update: validating publication replaces a newer display name

`update` permits renaming an environment while it is creating.
`_complete_provisioning` retains the initial environment object across provisioning, then `_publish_validating_environment:722–748` derives a replacement from that original object.
`_replace_environment_internal` builds its list from current settings but substitutes that whole stale replacement, overwriting a successfully committed concurrent name change.
The later `_finish_environment_operation` intentionally preserves current fields outside runtime metadata, a sound mitigation for later phases that does not undo the earlier whole-object replacement.
Normal ready recovery similarly accepts an earlier environment snapshot.
Global registry CAS protects ordinary request mutations; the internal mutator's lock does not merge this stale object's non-runtime fields.
Existing create/copy/restart tests assert original names and generation paths, not a rename between admitted creation and completion.
Future repair should preserve current user metadata when publishing runtime fields, without freezing all name edits or altering scientific generation ownership.
No scheduled race was executed.

#### B-F155 — P2 cancellation semantics candidate: recovered-ready operation records a request it never consumes

Retry of a failed entry whose public generation is already READY starts `_recover_ready_environment` in `_operation_tasks` without a Wetlands operation.
`cancel_managed_operation` then adds its ID to `_cancellation_requested` and reports waiting for the current step.
The recovery method never checks that flag and normally validates/probes and publishes completed, despite the acknowledged request; the flag is also not discarded in its finally.
The same local flag is explicitly consumed for remove while the viewer is stopping, with a meaningful existing event-gated test.
No user loss or dangerous force cancellation is claimed; this is a distinction between unavailable physical cancellation and an API promise to stop after a current step.
`test_retry_reuses_failed_entry_and_recovers_published_generation` and `test_remove_can_be_cancelled_while_viewer_is_stopping` do not combine recovery with cancellation during its probe.
Future contract should either admit/observe cancellation at safe recovery boundaries or honestly declare it too late, while draining physical probe work before terminalization.

#### B-F156 — P3 lifecycle/maintenance: untracked event updates and retained coordination entries

Wetlands receive callbacks schedule separate asyncio tasks for registry progress/logging without tracking/draining them in close.
A late callback can enqueue work after owner task maps empty; callback scheduling after loop closure is not guarded here.
Environment lock entries persist after removed UUIDs, and recovery cancellation flags remain retained as above.
This is a qualified shutdown/bookkeeping source risk, not observed memory growth, an event ordering failure or proof that a valid terminal state is overwritten: `_update_operation` correctly refuses changes to completed/failed/cancelled records.
The operation history prunes terminal entries beyond200 but deliberately retains active entries.
Future measured lifetime diagnostics should preserve terminal guards and progress visibility, with bounded owner bookkeeping rather than a new global coordinator.

#### B-F157 — P2 pending cross-store admission candidate: favorite forget intent precedes registry CAS

Full `ViewerPreferenceStore.prepare_environment_forget:133–158` persists `registry_revision` but neither apply nor the registry recovery caller uses it as an admission predicate.
`NapariEnvironmentService.forget:1085–1134` validates an observed revision, changes preferences through this forward journal, then awaits `_patch`/SettingsStore locking and CAS.
An internal registry progress/settings mutation holding or awaiting SettingsStore admission may therefore make the request stale at CAS after its favorites were removed; the durable intent remains and recovery later removes the selected UUID using the current registry revision.
This is distinct from the sound intentionally forward-completed cleanup after a successfully committed destructive managed removal.
The selected external/adopted installation itself is preserved by forget.
The qualified issue is acceptance/acknowledgment and authority of the cross-store intent under contention, not a demand for two-store atomic rollback or a claim of physical deletion.
The journal verifies target digest and preference source revision, which protects independent preference changes during forward application; it does not protect the registry admission boundary.
`test_environment_forget_journal_is_forward_recoverable` proves sequential target persistence/reopening only; existing stale registry route requests fail before a journal is created.
A future exact contention diagnostic should distinguish admitted versus stale intent and preserve crash-forward recovery once admission has occurred.
Ordinary same-app registry mutating HTTP is serialized by workspace request middleware, so that HTTP-only schedule is mitigated; internal callbacks and public/direct/multiple-app writers are the remaining qualified admission directions.
No schedule or loss reproduction ran.

### Complete-review checkpoint — reviewer-batch-34

#### reviewer-F068 — P3 unchanged gateway artifact cannot own a distinct setup-bound publication

Gateway artifact embedded installer (fully read in batch33) uses publication_id=artifact_digest[7:] and reuses that directory only when both artifact and setup digests match.
BootstrapClient.install:304–361 is an actual public explicit entry that accepts any new bounded setup and invokes the installer after upload; the bootstrap counterpart only uses true\n for one publication.
A later explicit install with identical gateway bytes and different setup must hit the existing publication setup-digest refusal instead of obtaining a new immutable setup-bound publication.
Normative remote_cluster_technical_spec:419–428 binds each publication to setup/Python/artifact identity and permits guarded compatible upgrades without changing retained runs.
This is a qualified public upgrade/recovery support gap, not wrong setup reuse:the digest check correctly fails closed.
Ordinary publish_deployment does not bootstrap again when a trusted gateway already exists; do not claim every deployment with changed setup fails.
Smallest future distinguishing extension is the existing installed-artifact bootstrap test with two setup identities, verifying each retained publication/entry binding and old run identity after the gate.
The setup may execute trusted code; its arbitrary output and OS bootstrap prerequisite portability remain separate source review qualifications, not an untrusted shell injection claim.
The transport publication helper docstring also promises one operation ID across allocation/commit/publication, while implementation intentionally allocates three IDs; source comment should describe actual within-call phase identities and content-addressed publication rather than claim an unimplemented cross-call retry handle.

#### reviewer-F069 — P3 public connection check omits common structured failure translation

RemoteCluster.check_connection:233–237 calls the transport directly and parses its report without the _raise_transport_failure boundary used by the other public lifecycle operations.
GatewayClientTransport.check_connection:284–302 can raise GatewayTransportError for malformed capabilities or mismatched/missing trusted artifact digest; those exceptions reach this public method without a ClusterDiagnostic carrying phase/allocation/retry/next-action fields.
Reachable/missing-gateway transport failures already return complete connection report diagnostics; do not claim all connection failures lose structure or that incompatible gateways execute.
The strict trust identity refusal itself remains essential and effective.
Existing connection lifecycle tests cover valid/fresh-root reports; malformed attach/progress and result errors are covered separately and cannot prove connection translation.
Future smallest extension is those existing connection/report oracles for an exact artifact-identity mismatch/malformed report, preserving source-safe sanitized errors and explicit bootstrap-required semantics.

### Existing controls and findings retained

RemoteCluster._remote_storage and plan use copied recursive workflow definitions; current routing receives exact requirement/binding fields and all orchestrator/processing nodes, rather than claiming mocked empty-planner lifecycle tests prove real routing.
Public submission retains one preallocated run/attempt ID and live plan on uncertain acknowledgment; successful repeated submit returns the same run without another mutation.
Transport submission deterministically builds and verifies invocation archive bytes before first contact and retains stable attempt:allocate/commit operation IDs on retries.
The older prepared launcher cross-call replay B-F088 is not transferred to this managed planned-submission owner.
The complete protocol raw malformed/depth exception seam B-F089 still applies because transport catches GatewayProtocolError specifically; correlation, supported-version and trust refusals remain fail-closed.
Bootstrap oversized/invalid mutating responses have incomplete ambiguity flags, corroborating the B-F096 uncertainty family for remote bootstrap state rather than scheduler duplication.
Connection timeout is reused as total command/SFTP timeout (B-F097); PIPE output capture precedes caps (B-F098). Both retain explicit timeout/cap eventual refusal and are unexecuted here.
The plan close/pre-submission cancellation lease-release seam remains held for the complete gateway run-state/receipt consumer; attachment alone does not transfer the original local lease owner.
Managed versus legacy constructor/instance compatibility is explicit; no v1 run-ID/schema mismatch or blanket worker-drain defect is inferred.

M1 and all repairs/runtime remain held.


### Complete-review checkpoint — reviewer-batch-35

#### reviewer-F070 — P3 child response caps do not bound temporary capture volume

_gateway_support._run_json_child:419–477 redirects stdout/stderr to TemporaryFile, waits for child completion or timeout, and only then reads output_limit+1 stdout and a bounded stderr prefix.
This protects response parsing/returned data and avoids PIPE memory growth, but the temporary disk capture itself has no volume cap; a trusted factory/build/helper producing rapid output may consume substantial temporary filesystem space before timeout.
Normative remote_cluster_technical_spec:960 promises hard captured-subprocess-output limits; returning an oversized-response failure afterward is not a bound on physical capture.
No disk exhaustion, secret disclosure or orphaned child has been reproduced. The process group timeout kill/wait and sanitized output refusal remain intact and essential.
This is distinct from B-F098's PIPE whole-memory capture family and should retain the actual TemporaryFile owner/resource qualification.
Future diagnosis should use the existing child/validation counterpart family to distinguish bounded physical capture from bounded returned prefix without running arbitrary helpers or weakening diagnostic/privacy guarantees.

### Retained filesystem and parsing boundaries

Atomic record/byte writers handle partial os.write counts and fsync current private namespaces; no universal short-write defect is inferred.
Published regular files are opened with O_NOFOLLOW and checked ownership/mode/single-link/digest; the pre-open special-file replacement risk extends F063 as same-user filesystem mutation, not a remote untrusted-code exploit.
Deployment archive limits, canonical identity and complete extracted file inventory remain separate checks. Auxiliary json.loads still lacks strict duplicate/nonfinite/depth handling (B-F091/B-F089), but canonical digest and wire admission remain important refusal controls; no accepted unsafe executable archive is claimed.
Existing-Python attestation binds requested/resolved interpreter stats, required runtime metadata and selected scheduler; module/factory code remains explicitly trusted, and validation evidence correctly labels compute-node/network/quota facts unverified.
File and module factory sources differ intentionally; runtime-only managed attestation still does not substitute a captured processing recipe identity (canonical reviewer-F040).

### Complete-review checkpoint — root-batch-18

#### ROOT-F089 — P3 advisory documentation edit selector always couples full quality configuration and docs builds

Affected_tests._commands_for_path selects CI_QUALITY_CONFIG_COMMAND plus DOCS_BUILD_COMMAND for every README/docs path at edit and precommit stages, with no distinction between small prose edits and changed documentation navigation/tooling/API contracts.
The quality command includes development workflow, release tooling and the full parametrized pytester complete/external marker hook suite; the docs command builds all Sphinx content.
Those are valuable stable behavior/structure gates, but their mandatory-looking per-edit output exceeds the intended focused edit loop when unchanged configuration and ordinary prose are the only delta.
The helper labels all output advisory and does not replace CI gates, so this is an exact selector/cost-policy candidate rather than a broken authoritative validation command.
No runtime or speedup was measured, and Sphinx can detect prose links/reference changes; do not suppress required structural/fragment/API checks or assert every small edit is safely check-free.
Future suite synthesis should specify which document deltas invalidate quality configuration, link/structure/API examples and full build results, retaining required gates at coherent milestones and conservative fallback for unknown changes.
Platform scripts/test already has a distinct campaign-record versus structural-doc lane; reconcile library selection proportionately rather than copy that lane blindly to every document.

### Existing reviewer-F003 extension — advisory exact-file external tests omit the required opt-in

For an existing tests/integration/test_wetlands_cancellation.py or other external-marked Python test path, edit selection returns uv run pytest exact.py plus FAST_TEST_COMMAND, without --run-complete.
The complete marker hook tests establish that explicit exact files still skip those tests without the opt-in; -m not complete for package paths likewise does not enable other external markers.
The default external skip is intentional and must remain; the advisory command should describe prerequisites/actual selected guarantee instead of being reported as executed real runtime validation.
This corroborates the existing external-enable CI/README selector finding at a new exact producer, not a new duplicated runtime defect or permission to provision external resources for every edit.

### Existing B-F012 extension — real Wetlands cancellation regression fault paths lack complete release ownership

The complete mapped cancellation test admits compute before accepting all worker control sockets; a failed accept/read/assertion can enter ThreadPoolExecutor.__exit__ with an active submitted workflow.
Its finally closes only already accepted controls and does not always request workflow cancellation/release a second unaccepted connected worker; that worker can still wait while the executor context waits unboundedly.
The batch test performs accept before its control try/finally and has the same exceptional setup lifetime qualification.
On the successful path, the probe protocol explicitly observes cancellation and asserts compute remains incomplete until finish/ack, a strong real physical-writer drain oracle that must remain.
A future controlled failure-path extension should own cancellation, all accepted/unaccepted worker release and physical join; merely adding result(timeout=10) does not bound executor context shutdown.
No hang, child leak or regression run was executed in this audit.

### Existing B-F148 extension — worker/loader test scaffolding repeats monolithic import authority

The fully read four worker-timeout split files and shared kit retain many identical unused F401-suppressed engine/Workflow/Core imports and spacing from their former monolith.
The actual configuration, public timeout forwarding, local failure correlation/pickling and fake dispatch timeout branches are useful distinct tests; cleaning fixture import ownership should preserve them rather than merging away branch identities.
The loader kit and broad integration versioned fixture intentionally differ in distribution metadata, lazy exports, nested imports and dependency setup; share only truly identical builder primitives if measured maintenance/testing gains justify it.

### Retained boundaries and qualified low-priority follow-up

Worker-origin tests fail before executing a hash-mismatched marker, distinguish full root/version/archive identities and assert shared module canonical isolation; retain these stronger identity checks independently of host loader/catalog tests.
The isolated import subprocess checks forbidden sys.modules pollution and the exact canonical entry point, without claiming orchestrator packages are absent from its installation or every supported Python version imports successfully.
Its lack of a local subprocess timeout is a qualified harness-bounding follow-up; no import hang or automatic generic process supervisor refactor is asserted.
Managed config fixtures are importable trusted factories with nonallocating init_blocks0 and exact secret/DFK/retry/label refusals; legacy/managed physical cleanup findings remain distinct.
Real Parsl process/instance IDs and overlap timestamps support actual local executor tests; fake scheduler/SFTP/SSH boundaries in composition remain honest and cannot establish a site/HPC certificate.
Wetlands smoke preserves physical output bytes and actual stream routing, with explicit logger restoration; old 1.0/1.1 metadata minima are legacy wording/guard debt rather than proof lower versions satisfy the current2.x API.
Marker/package support files were read individually; empty files have no hidden lifecycle behavior, while support/testkit prose identifies fixture/import responsibilities.
Pytester external opt-in and param-level/param-id distinction tests are meaningful bounded selection contracts; obvious repeated cases can be evaluated after the whole-suite oracle map, with no unmeasured runtime saving claimed.
M1 remains OPEN and repairs/new diagnostics/all application acceptance remain held.

Twenty-six complete inputs / 2785 lines.

### Complete-review checkpoint — A-batch-32

#### A-F168 — Medium source risk, shared workflow/import dialog finalizers lack invocation ownership

MenuBar.vue319–370 captures useful New/Save As payload and target but after awaited create/duplicate/load unconditionally clears shared workflowDialogVisible/Target/SuggestedName/Folder, or writes an old conflict suggestion.
submitRename955 onward captures the request target, correctly addresses it and updates its matching canvas context, then clears shared renameDialogVisible/Target without checking which dialog invocation owns that state.
Import579–655 captures a File locally for each admitted request but finishImport clears the shared pendingImportFile; conflict and rename completion update the current shared import dialog/name with no operation token.
Global commands remain able to open/replace these shared targets while a request is pending, and the local submit handlers have no busy admission/cojoin owner; removing the component listeners does not retire their continuations.
A previous committed action or conflict can therefore clear or populate a subsequent dialog/file choice in the static reachable ordering; no runtime reproduction or wrong-workflow server mutation is claimed.
Existing selectors `keeps Save As bound to the graph captured when the dialog opens`, rename activation and delayed deletion tests distinguish originating data versus active B, but not an old finalizer/error versus a newly opened same form; `shows the import rename dialog when upload returns a conflict` resolves the conflict for one current File only.
Retain exact captured request graph/name, server conflict/CAS/generation guards and committed-operation semantics; future repair should separate response/presentation ownership from request completion and avoid replaying an already committed create/import/rename.
Frozen I1 may address advisory readiness ownership but must not be assumed to cover all dialog finalizers until its complete separate review.

### Existing A-F087 extension — Python build reset has a separate local edit/session barrier gap

MenuBar.vue516–562 captures workflowName/canvasId and accepted draft revision, obtains saved artifact hash, previews an immutable source token and explicitly confirms effects before server apply.
Those exact saved-byte/token/effect and draft-revision CAS protections are sound and must remain intact.
After preview/confirmation/apply awaits, it calls resetWorkflowDraftToSaved with the earlier accepted revision, then initializes the captured resource and dispatches replace-root-graph without rechecking its registration token, local edit epoch/current graph or retired session owner.
A locally queued edit not yet accepted by the draft server can leave accepted revision unchanged and be replaced despite the reset CAS; a disposed/recreated captured resource is likewise not covered merely by matching workflowName before the later awaits.
This is the same late-edit/session reset invariant as A-F087's Canvas source-update consumer, now a separately complete MenuBar path; no new duplicate finding or executed overwrite is asserted.
Main MenuBar tests deeply distinguish save edit ownership but contain no held Python preview/apply/reset variant; source API preview tests assert wire token/effects only.
Saved source apply can commit before later draft reset failure, so any future error handling must preserve that committed result and avoid blind replay; a whole-operation filesystem transaction is not asserted as an existing promised contract.

#### A-F169 — Low/Medium qualified source boundary, silent presentation refusal is not propagated to Open/import/create owners

MenuBar.vue245–267 applyGraph returns void and silently refuses when execution is mutation-locked or the active canvas has a lifecycle action.
Open385–404 checks execution after loading, closes the dialog, calls applyGraph and then refreshes readiness regardless of whether lifecycle presentation was admitted.
New/Save As/import callers likewise can finish server creation/import or load, invoke that silent presentation guard and continue closing forms/showing success or dependency/readiness guidance without an explicit presentation result.
The delayed-create test correctly proves no graph apply after execution begins, but does not distinguish committed-created state plus acknowledged presentation refusal or an active lifecycle transition during Open.
The earlier explicit-Open browser failure ISSUE-022 remains retained with unproved cause; this static silent-return boundary is not causal evidence of startup overwrite or that failure.
Future contract decision should expose whether presentation was accepted/refused and preserve completed server identity without replay, while retaining the execution/lifecycle mutation guard and existing readiness advisory independence.
No production change, asynchronous reproduction or new test is authorized by this backlog.

### Existing A-F164 extension — explicit export command can replace captured target during an open action

MenuBar.vue476–487 always replaces exportDialogTarget and sets visible=true, with no export-child operation busy/epoch coordination.
Thus a second explicit export command is a reachable target replacement without false→true visibility transition; the child's close watcher alone does not retire the older visible action.
This strengthens the previously qualified live-prop/picker/error ownership seam while retaining the normal active-canvas-switch mitigation and existing captured save preparation.
Actual file copy retarget/loss remains unexecuted; future correction must distinguish operation target from current dialog presentation and not assume AbortSignal physically reverses committed server work.

### Existing A-F139/A-F140 corroboration — public cluster caller guards do not acquire extraction ownership

Independent reviewer fully read _gateway_run_state.py/_gateway_cleanup_state.py and generic receipt mixin; neither provides a shared run/namespace lock around source snapshot→mkdir/extraction→phase write.
The caller's invocation_root.exists check at run_state399 mitigates ordinary already-existing roots but is not atomic ownership acquisition; concurrent same planned attempt can reach the helper before launch admission.
A-F140 cleanup after failed exclusive mkdir can therefore target the other invocation's root in that source ordering, qualified reachable rather than generic unconditional loss.
A-F139 is corroborated because caller descriptor assignment occurs only after helper tuple success, leaving the root descriptor inaccessible on intermediate namespace-open failure.
The reviewer owns these full caller files; this extension takes no duplicate coverage credit and claims no runtime race, lost files or observed descriptor leak.
Retain no-follow/private namespace/bounded extraction/hash/CRC contracts and eventual public admission identity; future repair must condition cleanup on acquired ownership and reliably close each descriptor on partial acquisition failure.


### Complete-review checkpoint — A-batch-33

#### A-F170 — Medium source-established identity collision, presentation-safe test id reused as Tree identity

WorkflowsPanel.vue84–91 testId replaces every nonalphanumeric/underscore/hyphen character with '_', and nodeKey uses that lossy result as PrimeVue Tree's actual key.
Distinct valid ids A/B and A_B therefore both become workflow-tree-workflow_A_B; A B and A_B likewise collide for folders, independently of the workflow/folder type prefix.
Key-based selection/expandedKeys and findNodePlacement552 onward can no longer distinguish these items, so a drop lookup may select the first matching placement rather than the dragged item's actual folder/index; full data ids remain correct and mitigate leaf-name confusion, but do not repair key identity.
Existing full-id duplicate leaf tests use A/nuclei and B/nuclei, which remain distinct after sanitization, and synthetic drop helper removes the first matching key; neither distinguishes slash/underscore/space collisions.
No browser action or wrong placement was executed.
Future correction should keep raw collision-free type-qualified identity (or reversible encoding) for Tree keys and reserve sanitized test hooks for presentation; retain full-id dispatch, search drag disable and alphabetic folder ordering.

#### A-F171 — Medium source risk, description editor submits retained text to the currently selected workflow

WorkflowsPanel.vue532–551 openDescriptionDialog copies selectedWorkflow.description into a shared descriptionInput but captures no workflow id/generation/form owner.
submitDescriptionDialog later reads selectedWorkflow anew and patches that id with the retained text.
A selection/currentName change while the dialog is open can submit A's edited text to B; workflow store captures request identities at submit and validly accepts B, so its postrequest generation checks do not establish the original form owner.
Modal UI mitigates ordinary underlying mouse clicks, but reactive currentName/store events and direct commands can still change selection; no executed overwriting request is claimed.
The existing `edits the selected workflow description from the detail section` test selects Beta, opens/submits immediately and checks Beta's request/display; it cannot distinguish selection change after opening.
Future repair should explicitly bind the form recipe to the workflow/incarnation chosen at open or require a deliberate transfer, while preserving trim/null normalization, metadata-only PATCH and actual server CAS/refusal.

### Existing A-F168 extension — folder continuation and panel form finalizers also share live presentation state

WorkflowsPanel.vue470–502 captures name and previous selection, but folder rename after awaiting renameWorkflowFolder reads folderDialogEditId.value again when remapping the original selection.
Opening another folder/workflow dialog during the request can replace that prefix and the old finalizer unconditionally closes the current dialog.
Folder create/description/Delete completion similarly sets selection and clears current shared forms; delete request target is correctly captured before await, so the distinct defect is subsequent presentation/finalizer ownership, not universally wrong server deletion.
runPanelAction126–133 writes a shared workflowStore.error from any late failure; a prior action can replace a later success or error with no accepted operation presentation owner.
Existing panel fixtures resolve immediately and do not distinguish these held completion/reopen cases; body modal and backend structural/generation guards mitigate ordinary paths but are not an async owner.
Future correction must retain completed server identity, exact policy/captured structural target and close-tab refusal; never replay a committed mutation solely because old presentation is discarded.

#### A-F172 — Low/Medium source-established recovery gap, stale migration says review again but retains the stale token

WorkflowsPanel.vue323–372 obtains format status only during mount; reviewFormatUpdates merely clears error and reopens the dialog using the existing pendingFormatPlanId.
confirmFormatUpdate catches a stale-preview rejection but never requests a fresh plan or changes that token; retry/review posts the same server-rejected pending_plan_id until component remount or unrelated refresh.
The public backend exact stale hash refusal is sound and protects original documents; UI must not bypass it or automatically retry a committed apply.
Existing `keeps a stale migration preview open with the server detail` asserts error visibility only, and `defers and later confirms a pending workflow format update` uses an unchanged valid plan.
Future recovery should explicitly refresh public preview/status after stale refusal and ask the user to approve the newly inspected plan, retaining defer, backup details and single admitted apply.
No migration execution or simulated stale token request was performed in this read-only audit.


### Complete-review checkpoint — A-batch-34

#### A-F173 — Low design/debt candidate, nested status projection repeats whole chain/graph work per node

useCanvasStatusProjection145–148 resolves a Map-backed chain and compares each draft/savedSnapshot document for every statusForNode invocation.
statuses213 onward calls that function for every displayed/scoped id; scopedStatusIds additionally resolves the chain, and progressForNode does so again.
resolveNestedExecutionScope builds its byId Map per call, and graphDocumentsEqual serializes complete graph documents; total projection work can scale with displayed node count multiplied by session inventory/chain graph size.
Vue computed caching mitigates repeated reads between invalidations, but does not remove repeated chain/full-document work within one recomputation.
No timing or large-graph slowdown was measured, and required exact private-versus-applied snapshot semantics are sound.
Future optimization should measure realistic recomputation and consider one reactive scope/applied-equivalence derivation per resource epoch, preserving all exact origin/revision/semantic/corruption precedence tests instead of weakening identity for speed.
Existing565line tests distinguish correctness on small graphs only; this is not authorization for blind benchmark/test growth.

### Existing A-F043/A-F094 extensions — id-only resource and lifecycle retirement

Status projection fixedFacade283–298 and canvasFixtures returned dispose unregister by canvas id rather than acquired registration token, like earlier graph/session facade lifetime risk.
canvasLifecycle.begin/finish11–18 owns operations only by id, and App removal/old async finalizers can finish that id after its current operation changes.
Normal single lifetime teardown and whole-canvas disposal are intentional; a retained old disposer/operation after same-id recreation is the qualified failure ordering, not every disposal call being wrong.
Counterpart disposal test uses A versus distinct B and cannot distinguish old A handle from newly registered A.
Future owner contract must bind retirement to its original registration/operation, retain idempotent cleanup and avoid disposing legitimate sibling resources unintentionally.
No operation/token refactor or runtime reproduction occurred.

### Existing A-F089 extension — native drop resolution continuation uses current canvas incarnation

Reviewer fully read the native helper and handed off exact CanvasView2371–2398 consumer; A's previously complete CanvasView review owns the application boundary.
The initial drop captures position/path, awaits resolveDroppedPaths, then invokes onAddNode on the retained live CanvasView without capturing workflow/session registration/edit owner at admission.
onAddNode2443 onward rechecks current isLocked, which correctly mitigates execution/lifecycle lock transitions, but then consults current registry and current nodes for insertion; it cannot prove they remain the original drop workflow/incarnation.
Ordinary canvas activation alone does not retarget a fixed CanvasView component, so do not conflate this with dynamically active shell commands; root graph replacement, reincarnation or actual component retirement are the relevant retained continuation conditions.
The helper's physical desktop path expansion/containment boundary remains sound; no native path resolution or wrong-node insertion was executed.
Existing A-F089 clipboard late context concern is extended to this independently awaited consumer, retaining its postawait lock mitigation and explicit owner qualification.
No duplicate native helper credit is taken, and remaining browser canvas-interactions full file remains pending.


### Complete-review checkpoint — A-batch-35

#### A-F174 — Low/Medium source-established accessibility gap, node context actions are mouse-only list items

NodeContextMenu.vue67–95 renders clickable li elements inside ul, with no button/menuitem semantics, tabindex, action key handler, initial focus or arrow/navigation support.
Global keydown only closes on Escape; a keyboard user cannot ordinarily focus/activate Rename/Enable/Open/source/Delete actions even when the context menu exists.
The menu may be opened through a pointer-specific canvas context action, so do not assert an independently established keyboard invocation contract for the Canvas gesture, but its exposed action controls themselves lack standard keyboard access.
Existing126line tests click each li and assert Escape closes; none distinguishes focused action Enter/Space activation or item navigation, so Escape passing does not prove keyboard accessibility.
Future correction should use actual semantic controls or an explicit accessible menu interaction pattern, retaining capture-phase outside dismissal, exact parent source/lock/admission semantics and branch-specific action labels.
No native/browser accessibility run or new implementation is authorized.

### Existing A-F163 extension — document listener test lifetimes and harness boundary

Most NodeContextMenu mounted wrappers remain alive after each test, despite registering two document listeners; only one outside propagation case explicitly unmounts.
Error/edge display wrappers have no document event handlers and their lack of explicit unmount is lower impact than these listeners; avoid treating all wrappers as the same defect severity.
Parameter harness tears down registry/timers/spies robustly, but final wrapper.unmount is in successful test bodies; failure-path retirement can be improved without indiscriminate duplicated test setup.
No current intertest failure was executed or runner-wide auto-unmount claim made; infrastructure owner retains complete runner context.

### Existing A-F012 oracle extension — synthetic parameter Files is not the actual runtime Files class

parameterEditFeedback70 onward uses name/display Files with ProcessingTool/scalar path and package Core1.0.0; actual common Files metadata/root review establishes a source DataFrameTool.
This synthetic object intentionally exercises a Path editor and actual presentation/resource acceptance, not runtime classification.
Future naming should expose the synthetic editor scope, retaining delayed accepted/rejected tests and separating actual engine/tool-class behavior; no implementation defect is inferred merely from a test mock.
The handwritten command callback also limits consumer coverage: full CanvasView source may differ while this harness remains green, so any concrete Canvas semantic regression should extend its actual consumer counterpart rather than add another copy of this harness.


### Complete-review checkpoint — A-batch-36

#### A-F175 — Low test-oracle debt, specific titles exceed distinguishing state/assertions

backend/tests/test_services/test_workflow_draft_operations.py153–224 says parent edge AND binding pruning, but constructs child.bindings={} and never inserts/asserts a removed parent binding.
It genuinely distinguishes child interface and incoming edge pruning; it cannot expose a service regression that leaves a formerly populated binding orphaned (existing source/interface finding A-F015 remains separate).
backend/tests/test_routers/test_graph.py440 onward `test_cross_join_four_columns` asserts only that three named columns are a subset, never exact four-count/schema or exclusion of extraneous fields.
The actual external schema resolution remains useful; title alone must not receive a missing exact oracle claim.
Future work should amend those existing distinguishing fixtures/assertions or accurately narrow labels, retaining stable-id atomic semantics and configured actual-package scope instead of adding duplicate broad journeys.
No runtime production failure or new test execution occurred.

### Existing A-F124 extension — actual raw install version caller strengthens target confinement scope

B fully reviewed routers/tools.py555–578 plain dict[str,str] install body and package_installer.py130–153 forwarding package/version unchanged into public ensure_installed365–422.
That public loader joins supplied names/versions into final target and rmtree(target) on install/missing-module failure without establishing confinement or owned staging; webapp known-package gate does not constrain version.
Earlier A-F124 recorded final-target publication/rollback ownership, and this actual caller strengthens the arbitrary raw-version target boundary rather than treating only ordinary valid exact pins as mitigation.
B owns distinct uninstall query-version escape B-F168; this extension receives no duplicate loader/caller review credit and no actual destructive operation/network was executed.
Future repair must establish target confinement and acquired rollback ownership before subprocess/install/delete while retaining legitimate exact version and source store authority, not rely solely on frontend trusted inputs.


### Complete-review checkpoint — B-batch-26

### Existing B-F157 refinement — P2 cross-store admission source risk, now adjacent journal authority traced

Full `ViewerPreferenceStore.prepare_environment_forget:133–158` persists `registry_revision` but neither apply nor the registry recovery caller uses it as an admission predicate.
`NapariEnvironmentService.forget:1085–1134` validates an observed revision, changes preferences through this forward journal, then awaits `_patch`/SettingsStore locking and CAS.
An internal registry progress/settings mutation holding or awaiting SettingsStore admission may therefore make the request stale at CAS after its favorites were removed; the durable intent remains and recovery later removes the selected UUID using the current registry revision.
This is distinct from the sound intentionally forward-completed cleanup after a successfully committed destructive managed removal.
The selected external/adopted installation itself is preserved by forget.
The qualified issue is acceptance/acknowledgment and authority of the cross-store intent under contention, not a demand for two-store atomic rollback or a claim of physical deletion.
The journal verifies target digest and preference source revision, which protects independent preference changes during forward application; it does not protect the registry admission boundary.
`test_environment_forget_journal_is_forward_recoverable` proves sequential target persistence/reopening only; existing stale registry route requests fail before a journal is created.
A future exact contention diagnostic should distinguish admitted versus stale intent and preserve crash-forward recovery once admission has occurred.
Ordinary same-app registry mutating HTTP is serialized by workspace request middleware, so that HTTP-only schedule is mitigated; internal callbacks and public/direct/multiple-app writers are the remaining qualified admission directions.
No schedule or loss reproduction ran.

#### B-F158 — P2 qualified multiple-writer preference and first-workspace identity authority

`ViewerPreferenceStore` uses an instance-local RLock, rereads revision then atomically replaces the file.
Two independently constructed stores sharing a path can both read revision N, independently accept expected N, and each publish N+1; atomic file publication alone does not implement a shared CAS.
The ordinary app supplies one store per app, so no same-instance race is asserted.
Multiple app instances/processes sharing per-user preference storage are not coordinated by this class; whether exclusivity is guaranteed elsewhere must be made explicit before calling this a supported-path loss defect.
`ensure_workspace_identity:40–58` has a process-local global RLock, but first creation uses replace rather than exclusive creation or cross-process locking.
Two processes first opening the same workspace can return different UUIDs while one final file wins, undermining captured workspace preference identity for the loser.
Sequential reload tests prove durability for one writer, not these schedules.
The fixed journal basename also assumes one canonical preference store per directory; alternate filenames in the same directory would share a journal, a qualified public-construction constraint rather than ordinary app evidence.
Future diagnostics should first establish the supported concurrent app/store contract and then distinguish cross-process initial UUID publication and revision admission, without introducing a universal coordinator.

#### B-F159 — P2 source target-validation/commit gap for persistent favorites

`_validate_preference_key:444–470` acquires `store.workflow_mutation`, verifies workflow generation and captures the current draft, then releases that workflow identity guard before structural validation and preference mutation.
Set/toggle keep the snapshot service lock across the complete request, which protects nested private-session mutation through that service, but does not retain the persistent workflow guard.
An accepted draft structural change between validation and preference commit can leave a favorite for a withdrawn output.
The app workspace request middleware serializes ordinary mutating HTTP including workflow deletion/move/recreate and favorite writes, so those same-app HTTP schedules are mitigated; retired-generation cleanup-before-write remains qualified for public store/direct calls or independent app writers.
Draft mutation routes intentionally bypass that middleware and rely on separate execution admission.
Set/toggle also select an environment from a registry snapshot before committing preferences without a registry-target admission guard; public/direct or independent-app forget can clear references then race a later favorite write for the same selected UUID, while ordinary same-app mutating HTTP is serialized.
Preference revision CAS protects the preference snapshot, but a no-favorites forget/cleanup need not advance its revision and cannot alone guard target liveness.
No wrong-generation favorite is applied to a recreated workflow because keys correctly include identity_generation; the qualified consequence is stale/orphan durable preference admission and misleading successful response, not cross-generation execution.
The current-draft tests establish structural output discovery and incompatible/unverified viewer policy in sequential paths, not deletion/recreate/forget contention.
Full structural output lookup still derives ordinary tool outputs from the live name-only catalog; this corroborates A-F001/A-F066 captured-tool authority rather than creating a duplicate finding.
A future exact target-contention diagnostic should retain the accepted authority through favorite commit or establish equivalent conditional admission while preserving expected preference revision and saved incompatible-favorite repair semantics.


### Complete-review checkpoint — B-batch-27

#### B-F160 — P2 responsiveness and deadline source risk: synchronous IPC inside async routes

`NapariLauncher.open:308–330` calls synchronous `_send_command` directly while holding its async launcher lock; shutdown does likewise.
`Connection.send`, `poll(timeout=10)` and `recv` therefore execute on the backend event loop.
A slow Qt open stalls unrelated backend event-loop work during the poll even though launch itself is correctly offloaded.
The10-second poll only bounds waiting for initial readable data, not send backpressure or completion of a partly received framed response.
Legacy/registered `_launch` also calls authenticated `Client` after the bounded port-line wait without an explicit connection/authentication deadline.
The helper is trusted and local/authenticated; this is not a claim of an externally reachable malicious socket or actual application hang.
Existing fake connections return immediately; `test_status_is_lock_free_while_lock_held` checks a direct status probe in a separate thread, not event-loop responsiveness while receiving a real delayed response.
Future exact diagnostics should preserve serialized IPC and request-ID/unknown-outcome no-replay semantics while distinguishing total exchange completion, event-loop progress and physical owner lifetime.
No measured latency or native action occurred.

#### B-F161 — P2 qualified UUID pool generation handoff/lifecycle admission gap

`NapariLauncherPool._launcher:781–801` serializes installation identity inspection, old shutdown and cache replacement under a per-UUID pool lock, then releases that lock before the returned launcher's `open`/`launch` begins.
A caller can retain an old launcher reference during a scheduling boundary; an identity-change caller may retire/replace it, after which the earlier caller can independently acquire the old launcher's lock and start it again.
Separate launcher locks do not guard the complete lookup-to-use handoff across generations.
Scoped shutdown does not take the pool lock, and shutdown_all snapshots cached launchers without a closing/admission state; concurrently admitted launches are not covered by that snapshot.
Normal same-launcher calls serialize, and different environments intentionally proceed independently; those sound public pool properties are tested.
The app workspace middleware serializes ordinary mutating HTTP, so concurrent same-app open versus probe/remove/shutdown POST/DELETE schedules are mitigated there; this candidate concerns public pool/direct/background or multiple-owner admission where that request fence is absent.
Managed removal publishes removing state and validates generation before public deletion, mitigating ordinary newly resolved opens, but does not itself establish an old-reference handoff lease.
The existing fake pool tests distinguish independent UUIDs and passive restart_required status only; none gates an old returned reference against generation replacement or shutdown_all admission.
Future diagnostics should first reproduce the precise old-reference schedule and retain independent environment concurrency, with bounded pool handoff coordination rather than a global viewer lock.
No duplicate viewer or deletion race was executed.

#### B-F162 — P2 retryable physical cleanup ownership is discarded after close failure

Shutdown's stale/disconnected branch clears `_process`/PID before offloaded `stale_process.close`, then logs any failure and reports stopped.
The alive branch similarly logs `proc.close` failure and clears references/status afterward.
Launch replacement detaches stale process before close, and unsuccessful launch cleanup can discard a newly spawned process if close fails; registered launch may additionally let cleanup exception replace its original startup failure.
For public Wetlands ManagedProcess, a failed physical close is not proof of completed retirement; losing the launcher reference removes this service's retry owner and truthful status even when the lower manager retains ownership.
External subprocess close can also fail, with no retained selected process map here.
This extends B002 close-failure ownership to the viewer service, not a claim that ordinary successful close leaks or that Wetlands necessarily loses its own independent owner.
Existing fake shutdown tests verify close calls but never make close fail with a live child or require repeated cleanup.
B024 also applies: raw cancellation during `asyncio.to_thread(_launch/close)` can release the async lock while physical work continues; no new execution reproduced this boundary.
Future repair selection must retain retryable physical owner/status until verified completion, without replaying ambiguous open commands or deleting unrelated environments.

#### B-F163 — P2/P3 external viewer output/physical owner boundedness candidate

`_SubprocessHandle` starts a daemon reader and places every stdout line in an unbounded queue.
After `wait_for_port` succeeds no consumer drains that queue, so logs from a long-lived registered external/adopted viewer accumulate without the16MiB cap used for public managed spawn.
A single unterminated line is likewise buffered before enqueue, so an output queue bound alone would not cap producer memory.
The wrapper closes only its immediate Popen process, does not join its reader, and closes the buffered stdout after leader exit; a descendant holding the pipe can leave a reader active and make close wait on its internal lock (same physical shape as B152, different long-lived owner).
Reader startup occurs inside handle construction after Popen exists; failure starting the thread means the caller has not yet assigned its `process` cleanup variable.
The fake Popen uses StringIO, immediately yields a port and creates no OS child; it cannot distinguish these lifetime conditions.
Future diagnostics should preserve frozen no-shell argv/per-UUID configuration and deliberate external installation ownership, then establish bounded log delivery and selected child/tree/reader cleanup.
No memory growth, native hang or process leak was measured.

#### B-F164 — P3 typed explicit-target API handling absent for legacy-only injection

Only `/napari/launch` verifies that the injected lifecycle object is a pool.
Open/status/shutdown use `cast(NapariLauncherPool, launcher)` for an explicit environment UUID but retain a real legacy launcher if no registry/pool was configured.
Cast does not change its signature: real legacy open rejects `environment_id`, and status/shutdown reject the extra target argument, producing an uncaught TypeError instead of a typed unavailable/not-found refusal.
The app deliberately supports an injected legacy-only path without SettingsStore; default production settings wiring may wrap it in a pool, so this is scoped compatibility/API robustness rather than normal deployment authorization bypass.
Router tests use `MagicMock(spec=NapariLauncher)`, whose call signature is not autospecced; explicit target assertions therefore pass while the actual legacy method would reject the call.
Future exact coverage should use a true legacy launcher or signature-enforcing double and preserve no-ID compatibility plus the typed pool selection contract.
No request was executed.

#### B-F165 — P3 suite/docs maintenance candidates, preserve essential outcome distinctions

The launcher test module introduction still says `_launch` raises NotImplementedError and covers only a skeleton, contrary to the complete source and later tests.
`test_launch_raises_when_port_line_not_found` and `test_launch_raises_when_process_exits_before_port` have the same FakeManager(port_line=None) setup and same exception assertion, so their names do not establish distinct physical failure modes.
Several unknown-outcome tests overlap in fake send failure entry, but EOF after send, broken pipe, false poll, request-ID mismatch and no automatic replay remain meaningful contract axes and must not be collapsed indiscriminately.
Tests use a fixed `/tmp/bioimageflow-napari-launcher-tests` config root and fake success does not invoke shutdown; no real subprocess is started, but shared config files/ownership are a weak isolation boundary.
The concurrent-open test calls `asyncio.Event.set` from an offload thread and waits without a deadline before its bounded gather; pool release events lack finally cleanup on failed admission, extending B012 test-lifetime risk.
No measured suite savings or executed test hang is claimed.


### Complete-review checkpoint — B-batch-28

#### B-F166 — P2 source response-order authority: registry/poll snapshots can regress frontend state

`applySnapshot`, `applyEnvironmentMutation`, `applyRuleMutation` and `applyOperationMutation` assign response revision and replace/append entries without comparing against the current accepted revision or request epoch.
An older fetchRegistry or poll response arriving after a newer accepted registry mutation can restore an older revision/state, including a previously removed UUID or superseded display name/operation phase.
The backend CAS still refuses stale subsequent requests, so this is primarily incorrect visible state, unnecessary conflicts and possible misleading selected environment availability, not bypass of server revision admission.
Different environments intentionally have independent opens and the store can have multiple active operation watchers; concurrent backend callbacks also advance one global registry revision.
Operation watch promises are correctly deduplicated by globally unique operation UUID, but their responses are not ordered against other store updates.
Chooser-local preference acceptance explicitly compares snapshot revision and captures selection epochs, a sound authority not to replace with weaker global store behavior.
Existing store tests apply sequential revisions and an immediately terminal fake watcher; none releases an older snapshot/poll after a newer accepted update.
Future exact diagnostics should distinguish full snapshot freshness from partial mutation merging so merely discarding an older partial response does not omit a legitimately accepted environment change.
Preserve backend CAS and independent environments; no scheduled response regression was executed.

#### B-F167 — P2 lifecycle event correlation: stored request ID is overwritten before comparison

`applyEnvironmentStatus:95–119` assigns any event request_id to `state.requestId`, then terminal handling compares that same event ID to the overwritten value.
Therefore an old same-environment terminal event carrying an ID is always accepted by this comparison rather than being rejected against the pending current request.
Backend viewer broadcasts omit request IDs, while `open` creates a random local ID which is not sent through its payload; a running launch-status event can clear pending before the helper's artifact open response completes.
That can hide in-progress UI state and allow another user open to be admitted to the frontend; backend launcher locking still serializes actual dispatch, so no concurrent IPC or automatic replay is inferred.
A stale event ID can also change the state ID such that the current open's finally no longer recognizes its own pending ownership; if no later terminal event arrives, the indicator can remain pending.
The tests prove per-environment attribution and matching event IDs, but do not send an old same-environment terminal ID after a new opening or gate a running event before the HTTP open response.
Future diagnostic must separate viewer process lifecycle from one artifact request completion and retain legacy event compatibility plus explicit unknown-outcome no-replay behavior.
No event race or duplicate native open was executed.


### Complete-review checkpoint — B-batch-29

#### B-F168 — P1 source-established package uninstall target escape

`routers/tools.py:582–597` accepts `version: str | None` directly from a DELETE query, then calls the injected installer.
`PypiPackageInstaller.uninstall:231–251` constructs `tool_store / package_name / version` and checks only existence before `_remove_tree` invokes send2trash or falls back to rmtree.
An absolute version string replaces the earlier Path prefix; a traversal version can escape it.
No installed-package/version registry membership, component validation or resolved confinement check intervenes.
This is a source-established selected-target authorization gap: a package uninstall request can address unrelated accessible filesystem state, rather than only the selected tool-store version.
The desktop same-account threat model and trusted Python source installation do not make arbitrary unrelated target deletion an intended package uninstall behavior.
The uninstall route has no deployment/unsafe/approved-package dependency gate, unlike ordinary install and custom-source import routes, so configured webapp does not remove this path by the explicit row-install policy.
App middleware serializes mutating requests and checks pending workflow move recovery, but does not inspect uninstall path/versions or perform filesystem ownership admission.
The default app injects this real PypiPackageInstaller; no inferred alternate installer is required for source reachability.
CORS is broad in the app; no additional global authorization/containment middleware was found in the already complete app trace.
This does not establish external network reachability, a malicious invocation or an executed deletion.
Existing `test_uninstall_removes_single_version`, `test_uninstall_all_versions_removes_package_dir` and `test_uninstall_missing_path_raises_not_found` verify safe temporary ordinary targets only.
Owned router tests `test_uninstall_package_success` and `test_uninstall_triggers_catalog_refresh` mock the installer and do not distinguish a version traversal/absolute refusal before _remove_tree.
Future exact diagnostic should preserve legitimate selected version/all-version removal and send2trash fallback while refusing absolute/traversal/symlink escapes before any side effect.
Install delegates to public library ensure_installed, whose borrowed body also joins supplied version and cleans target on failure; A owns its full source and is reconciling that analogous install boundary separately.
No diagnostic or repair is released now.

#### B-F169 — P2 backend custom usage fails on structural workflow nodes and omits descendants

`CustomToolService.usage:240–253` loops only direct saved graph nodes and reads `node.tool_name` unconditionally.
WorkflowNodeState has no tool_name field, so a saved graph containing a structural workflow node can raise AttributeError outside the narrow get_workflow exception handler.
Public usage GET and custom deletion call usage before returning/deleting; a structural saved workflow may therefore prevent a usage response/deletion rather than just omit a nested dependency warning.
Nested child tool references are not recursively visited, and draft/private-snapshot references are not included in this saved-only method.
The scope of intended usage warnings should remain explicit; do not silently invent dependency rewriting or automatic graph deletion.
A-F156 is frontend selection/confirmation owner drift and is separate; A confirmed no canonical backend node-type finding.
The full custom service tests contain no usage oracle at all; owned route tests exercise direct tool fixtures, not a WorkflowNodeState branch/descendant warning.
Future exact diagnostic should distinguish a structural root with and without a nested matching owned tool, retaining unrelated workflow reads and intended saved/draft scope.
No request or test was executed.

#### B-F170 — P2 qualified custom publication failure/rename source integrity and acknowledgment

Create atomically publishes the new source before register_custom_tool_file executes trusted module code and metadata extraction.
A registration/import failure leaves the published file without the expected successful registry acknowledgment; no rollback or typed partial-publication receipt exists.
Rename publishes rewritten destination, unlinks old source, unregisters old metadata and finally imports/registers new code.
If old unlink or new registration fails, old source/registry and new source can be inconsistent; a retry sees the destination already present or old source absent.
The lexical regex only rewrites the first class declaration and matching display name; arbitrary custom self references/qualified annotations using OldName are not renamed and may make the new import fail after the old file was removed.
This is a qualified failure schedule and arbitrary-code rename limitation, not proof that generated templates fail: generated processing return annotations use Outputs and the simple template rename tests pass their source assertions.
Delete likewise unlinks before unregister; ordinary unregister mostly mutates in-memory structures, but an unexpected failure is an acknowledgment-after-side-effect seam rather than atomic rollback.
File temp writes do not fsync file/parent, extending B083 durability rather than introducing a second new durability ID.
Same-app HTTP creation/rename/deletion is serialized by workspace mutation middleware, mitigating ordinary concurrent destination overwrite; direct service/multiple writers still use check-then-replace without a shared no-clobber primitive.
Existing custom tests prove generated source parse, metadata/path, conflict checks and successful rename/delete only; no import/registration/unlink failure oracle exists.
Preserve owned-root confinement, read-only package refusal, custom-source authority and deliberate trusted code loading while defining honest recoverable failure states.
No universal source rewriting or registry redesign is recommended.

#### B-F171 — P2 suppression and physical-operation lifetime under cancellation

Install/source-install/uninstall catch Exception to resume hot reload after failures, while CancelledError is a BaseException.
Cancellation after suppress can therefore bypass that restoration; source-install has an awaited cleanup finally, but suppression resume is not in that finally.
AnyIO run_sync protects AnyIO cancellation scopes by default, yet the held T1 raw asyncio Task.cancel evidence establishes a separate outer-future cancellation direction; no fresh test was run for these installer functions.
A raw task cancellation can release _operation_lock while the physical pip/move/remove worker continues, allowing another operation and watcher state to overlap.
The source-install cleanup may also overlap physically continuing installation into staging, or itself be interrupted before completion.
After successful installation, awaited resume_after_install/registry scan can fail or be cancelled after version publication, giving failure acknowledgment while installed state remains, with no explicit partial success receipt here.
A-F149 owns in-flight reload tasks not joined by suppression/stop; calling suppress before disk writes does not prove that an already launched reload has finished.
This is a boundary reconciliation, not a claim every AnyIO cancellation abandons its worker or ordinary suppression fails.
Existing fake suppression tests assert ordering and simple Exceptions; concurrent installs use a short sleeping worker and max_active counter for successful completion only.
Future diagnostics must distinguish CancelScope from raw/repeated task cancellation, keep the actual operation lease through physical completion and restore watcher ownership afterward without replaying installs.
No implementation, pip or cancellation test ran.

#### B-F172 — P2 conditional source-install metadata origin selection ambiguity

`_discover_source_install:292–312` sorts all installed dist-info roots, prefers every root with direct_url.json, and returns the first Name/Version pair.
It does not compare direct_url contents to the requested URL/archive or otherwise identify the primary requested distribution.
A source package whose dependencies include another direct-source distribution can have several direct_url roots; lexical order may choose the dependency rather than requested package if its normalized module exists.
Then publication/result identity follows that selected dependency's package/version while the whole staged site contains the requested source too.
Trusted source build code already executes in this path, so this is provenance/result authority correctness rather than a new arbitrary-code trust assertion.
Version-directory immutable successful no-op is explicit and should remain; a new nonce/version to force replacement is not proposed.
The full test helper publishes one dist-info and no direct_url; no multiple-primary/dependency origin distinction exists.
Future exact static/controlled diagnostic should bind the selected install receipt to primary source metadata while preserving valid namespace/import-module policy and dependency staging.
No actual source install was performed.

#### B-F173 — P2 conditional partial version publication from cross-device move

Source install stages under the system temporary directory and publishes through shutil.move to the configured tool store.
shutil.move can fall back to copytree for cross-device publication rather than an atomic rename.
A failing partial copy can leave target present; subsequent source import treats any target.exists as immutable successful no-op and removes its fresh staging tree without attesting target completeness/content.
The watcher suppression path may also coexist with already in-flight reload (A149), but incomplete-retry reuse does not require that separate callback schedule.
Same-filesystem successful rename is sound and typical local deployments may take that path; this is qualified to cross-device/partial publication failures, not every source install.
Tests monkeypatch pip population and exercise successful actual move only; no failing move/residual target/retry distinction exists.
Future diagnostic should retain immutable complete version reuse, atomic/owned publication where possible and explicit incomplete-version refusal/recovery, without deleting foreign or previously complete target state.
No filesystem move fault was executed.


### Complete-review checkpoint — B-batch-30

#### B-F174 — P2 source registry action/refresh continuation bypasses scope and page-buffer guards

The registry's `applySnapshot` correctly checks loaded workflow scope and buffers received snapshots while a page load is active.
`loadRuns` uses a load generation to refuse older requests and reconcile buffered live events; existing controlled tests strongly distinguish those behaviors.
However, `refreshRun` and `cancel` await HTTP then call `upsertRun` directly, without checking captured/current loaded scope, load generation or the active page buffer.
ExecutionPanel invokes refreshRun for each active run every5seconds and independently loads a new page when scope/workflow changes.
A previously admitted refresh can therefore reinsert an old-workflow run after switching to a new workflow scope; monotonic per-run revision does not enforce workspace projection membership.
A direct refresh/cancel result arriving during a same-scope page refresh can update to revision N, then be overwritten by the older page's direct `runs = page.items`, since it was not buffered as applySnapshot events are.
`selectExecution` similarly fetches then selects without a scope guard; explicit parent/child navigation may deliberately choose another run, so that user intent must be reconciled rather than blanket-forbidden.
StartRetry applies the child with scope checking but afterward sets selectedRunId regardless of current scope; delayed action acknowledgment and current-view selection are different authorities.
No backend execution identity/admission is changed by these client projections; consequence is misleading run list/current selection and possibly stale action controls, not scheduler duplicate execution.
Exact existing tests for scope switch/same-scope refresh exercise applySnapshot only, not a deferred refreshRun/cancel response in those boundaries.
Future diagnostic should extend those fixtures to distinguish periodic/action responses and preserve workspace-wide scope, parent/child navigation and retained run identity.
No UI or response schedule was executed.

#### B-F175 — P3 qualified profile store response ordering and shared activity state

`refresh` directly assigns profiles on completion with no request generation or per-profile revision merge.
A list request admitted before create/update/remove can complete later and restore older profile state; backend CAS/editable=False still protects subsequent mutations.
`descriptions` is keyed by profile ID only, and completed descriptions are never invalidated on profile update/removal.
A delayed description may be associated with a different current revision when consumers later refer to that ID; the report itself carries profile_revision/config_digest, so displaying a deliberately captured old report can be sound if labeled/owned accordingly.
`describing` is one shared ID and every finally clears it, so completion of one concurrent description can hide another still active request.
Simple refresh loading state has the analogous shared-boolean overlap.
The section describes captured profiles explicitly; do not infer trusted script policy bypass or current run routing from this UI cache.
Existing tests cover sequential immutable ID/update revision/report/remove only.
Future diagnostics should distinguish accepted mutation versus delayed list and concurrent description ownership, keeping minimal profile fields and server-side expected revision/read-only admission.
No stale profile rendering or mutation was executed.

#### B-F176 — P2 source key authority: remote path choice object uses inherited prototype members

`preflightExecution:190–202` constructs `choices = {}` and uses `choices[resolution.node_path] ??= {}` before assigning an input field.
For a node_path equal to `__proto__`, the lookup resolves Object.prototype rather than an own empty dictionary, and the nested assignment can mutate that inherited object instead of emitting the intended own scoped choice.
`constructor`/other inherited names also bypass creation of the expected own entry.
Platform graph ToolNodeState ID is only a nonempty string, and the public UI intent type node_path is an unrestricted string; no reserved-key admission exists in this adapter.
This is source-established ordinary JavaScript dictionary-key semantics; no JavaScript execution or managed cluster action was performed.
Actual GUI generated IDs usually avoid these strings, and backend path planning retains strict public scoped input validation, mitigating wrong worker/path execution from a missing choice.
The qualified consequence is dropped/misencoded invocation override and prototype state mutation in the caller before HTTP, not server filesystem traversal or arbitrary remote code execution.
Existing API tests use ordinary `files`/`mask` keys only.
Future exact deterministic adapter diagnostic should distinguish valid reserved-looking root names/input keys without changing supported user graph identifiers or the simplified public remote override API.
Avoid an unrelated global identifier ban or alternate wire format.


### Complete-review checkpoint — reviewer-batch-36

#### reviewer-F071 — P2 generic mutation receipt admission is optional and unsynchronized

Gateway.handle_request:133–136 directly calls a default handler when operation_id is absent, including allocate_upload/commit_upload/publish_deployment/apply-cleanup; only the special submit-plan path explicitly refuses missing stable identity.
GatewayReceiptMixin.mutate:159–223 checks receipt existence and replaces intent without a cross-process lock or atomic create-and-bind admission. Two simultaneous equal requests can both observe absence and invoke the same handler; conflicting requests can also race their initial binding.
Every generic retry after completed/failed intent correctly checks the recorded digest and returns/refuses without repeating the handler, so the sequential guarantee remains meaningful.
Existing test_mutation_receipt_returns_same_result_without_repeating_handler uses sequential calls to an injected custom handler; it does not prove concurrent journal ownership or refusal of no-ID default writes.
Future exact diagnosis should extend the current receipt oracle with controlled equal/conflicting initial admission and a default mutating no-ID request, before choosing the smallest shared owner guard.
Do not infer duplicate scheduler submission from this generic path; managed planned submission and launcher launch admission have separate owners.

#### reviewer-F072 — P1 managed pre-submit cancellation can race a stale submitting owner

Complete _gateway_run_state.py contains no shared run/attempt lock or compare-and-swap transition.
submit_plan_request reads/creates a record:347–389, extracts and writes ready:399–405, validates/constructs launch:406–504, then writes scheduler-intent:505–506 from that earlier local record.
cancel_run:559–572 independently reads the record and durably writes cancelled for an unbound pre-intent phase.
A submitting owner paused after its record snapshot can therefore overwrite a cancellation completed by another gateway process and proceed to its submitter child; sequential cancelled replay at370–378 does not establish this interleaving.
Normative remote_cluster_technical_spec:802–809 promises that durable pre-submission cancellation prevents later upload/job submission.
Existing test_submit_allocates_attachable_run_before_upload_and_cancel_seals_it and test_committed_invocation_submits_once_and_reuses_scheduler_receipt are the smallest existing controlled-ordering extension points.
Borrowed exact downstream excerpts confirm LauncherRepository.allocate uses allocation_guard and refuses existing control/canonical run IDs before _submit_workflow calls _launch_prepared_control (submission:217–279; repository:445–556). These retain a strong duplicate-launch defense even if two gateway owners invoke their child; no duplicate job is claimed. That launcher guard does not read the gateway allocated-run cancellation record, so the stale pre-intent cancellation ordering remains a distinct source candidate, with no executed cancellation damage. No duplicate whole-file review credit is taken for these counterpart excerpts.
The same absent owner guard makes A's source-qualified invocation-root existence-check/extractor cleanup race reachable; retain A's canonical archive finding rather than duplicate that helper ownership.

#### reviewer-F073 — P2 compatible gateway upgrade lacks retained-run publication routing

The installer replaces the single gateway/entry with the newest publication (batch33); transport always invokes that entry and trusts only its current local artifact identity (batch34).
_read_run_record:133–145 correctly refuses when a retained record's publication/artifact differs from the active gateway and asks for attach-through-recorded-gateway-publication.
No public client/entry routing accepts a retained publication selector or dispatches a run to its recorded immutable gateway.
Thus a compatible upgrade can make prior runs unattachable through the documented stable public entry, despite retaining their old publications/records.
Normative technical spec:423–428 requires retained metadata dispatch and forbids modifying old bindings; existing binding-drift test proves fail-closed mismatch, not working compatible upgrade attachment.
Preserve that refusal and old identity; future diagnosis should extend the existing installed-artifact/retained-run tests rather than weakening binding checks or relabeling compatibility support.

#### reviewer-F074 — P2 expiry prevents proof-based recovery/release of a sealed cancelled plan

RemoteExecutionPlan.submit:353–377 rejects plan/validation expiry before contacting the gateway; close:448–465 always refuses sealed unclosed plans, and the attached run owns no originating laptop lease.
After an ambiguous pre-submit transfer, attaching and durably cancelling the remote attempt does not itself release its local lease. If its plan expires before retry, the only successful _submission_durable path cannot fetch the cancelled proof.
Existing same-live-plan recovery test uses future validation and immediate successful retry; it does not distinguish cancellation followed by expiry.
Normative technical spec:802–809 requires the original cancelled result/no new mutation and allows proof-based release, while10.4 retains expiry's prevention of new submissions. Resolve those together:read-only recovery of an already sealed attempt must not authorize new allocation or silently create another plan.
This is a source-qualified inaccessible public recovery/cleanup path, not a reproduced persistent file leak or ownership transfer to RemoteWorkflowRun.

#### reviewer-F075 — P2 gateway does not enforce the confirmed plan's finite expiry

parse_execution_plan validates digest/keys but not expiry semantics; submit_plan_request never checks expires_at before allocating a run or entering scheduler intent.
_deployment_runtime checks retained validation expiry, which can be much later than a short user-confirmed plan lifetime; that is a distinct identity/permission window.
The public plan checks expiry at the start of submit, but launch-time revalidation/transport can cross that deadline before first gateway mutation; manually sent valid wire requests also reach the same installed admission.
Technical spec10.4 promises finite plan expiry prevents submission. Durable accepted/cancelled replay must remain recoverable under F074 and must not be confused with new expired allocation.
Future smallest oracle is the existing pre-allocation gateway refusal case with a correctly digested expired confirmation and still-valid validation, plus existing durable replay cases; no expired scheduler execution has been tested or claimed.

#### reviewer-F076 — P1 cleanup reference checks do not reserve against a new managed owner

apply_cleanup:286–293 snapshots retained records/reference revision once; later candidate identity validation/rename/unlink:385–481 has no shared admission lock with run allocation/publication/transfer mutation.
A managed submission can acquire a new object/deployment reference after the cleanup snapshot but before tombstone deletion; before-call revision-change tests cover a different ordering.
Descriptor containment, candidate identity checks, HMAC confirmation and tombstone rechecks protect filesystem target identity, but do not make run/reference admission atomic with deletion.
Technical spec:940–950 requires active/retained references remain protected. Future exact diagnosis should extend test_cleanup_reference_revision_change_skips_every_candidate with a controlled reference admission after its initial snapshot, retaining all namespace/identity refusals.
No active run loss or external non-cooperating filesystem guarantee is asserted without a controlled reproduction.

#### reviewer-F077 — P2 cleanup restoration uses overwrite-capable rename

After detecting a replaced/changed tombstone, apply_cleanup:439–467 restores it with os.rename to the original name and catches FileExistsError.
For a regular file, rename can overwrite a newly reintroduced destination instead of raising FileExistsError; there is no no-replace restoration guard.
Existing test_replacement_race_is_detected_before_unlink inserts the replacement before the first move, so the original name is empty during restore; it does not cover a second writer restoring that name while tombstone verification runs.
This is a qualified same-user/local filesystem concurrency preservation risk, not an untrusted remote escape or demonstrated overwritten data.
Future extension belongs in that existing replacement oracle and must preserve newer target bytes/identity without broadening deletion or following links.

#### reviewer-F078 — P2 selected setup is not realized in validation/submitter context

Deployment setup bytes are captured/verified and applied to worker_init and orchestrator pre_launch, but gateway factory validation:680–691 and submitter/controller invocation use direct Python plus inherited _child_environment.
_FACTORY_VALIDATOR_SCRIPT constructs the selected worker initialization but does not source its setup for the trusted factory itself; _attest_existing_python similarly inherits the active gateway context.
When a trusted gateway remains from an earlier setup, a new deployment-specific module/library environment can therefore differ between declared validation context and later worker/orchestrator realization.
Technical spec10.2/ClusterValidationReport promises setup-realization evidence; current validation payload has environment/provider evidence but no distinct selected setup realization.
Existing real existing-Python and managed-uv lifecycle cases use no deployment setup, so they cannot resolve this seam.
No wrong job execution is inferred:missing context may fail closed or merely change trusted factory claims. Future bounded diagnosis should extend those existing factory validation/lifecycle cases with a setup-dependent harmless identity and exact selected source binding.
B confirms no canonical duplicate; its factory deadline/cleanup and secret-redaction findings remain distinct.

#### reviewer-F079 — P3 real uv publication/reuse boundary lacks a faithful existing oracle

The real-uv test installs metadata-only wheels and mocks attestation; the full publish/validate/submit lifecycle test explicitly uses a fake shell uv, a wrapper around the current interpreter, synthetic wheel bytes and patched scheduler.
These are meaningful source-bound routing/publication tests, but neither proves a real captured runtime survives candidate→final publication relocation, stable repeated/equal publication or exact real attestation after rename.
Normative technical spec21.1 requires equal concurrent publication and exact runtime/environment identity; no current source defect or real relocation failure is claimed from fixtures alone.
Before adding tests, use the existing helper/lifecycle split to diagnose those exact missing boundaries at the eventual allowed runtime milestone, with honest fake/real labels and no HPC/native execution credit.

All seven full judgments remain valid source reads; all static risk and oracle recommendations await the complete human-file/hash/completeness gate before any runtime or fixes.


### Complete-review checkpoint — reviewer-batch-37

#### reviewer-F080 — P4 unused legacy IndexedDB helper and fake oracles add maintenance cost

Production source search finds no import/call of useIndexedDB; only its own tests and a historical resolvedOutputs.test.ts mock refer to it.
The current recovery/persistence architecture is therefore not established by this helper's one 'current' record. Do not misattribute this dormant key to the active workflow/workspace recovery ownership finding.
Its source has success-only db.close and transaction-completion promises without explicit abort handling, but those are dormant helper qualifications rather than a demonstrated current data-loss/leak path.
The fake test DB deliberately implements only success microtasks/open errors; it cannot establish real transaction abort/retry/connection ownership.
Future optimization should either remove this verified obsolete helper/mock/test surface after confirming intended API compatibility, or explicitly retain it with honest scope. Do not repair an unused API or add mirror tests ahead of active persistence risks.

### Retained current helper boundaries

Undo/redo clones both stored and returned snapshots, resets an isolated authoritative baseline, caps default Canvas history and clears redo on new edits; server/canvas lifecycle ownership remains separate.
Column widths wait for visible geometry and fonts, measure a bounded initial sample, keep automatic widths stable across pages, persist only explicit manual choices and cancel RAF/ResizeObserver on unmount. Scope/type identity prevents ordinary unrelated-node storage reuse; no graph incarnation guarantee is inferred from width preferences.
File-drop global handling prevents navigation and copies only browser files through the managed dataset store. Desktop raw paths/folders go through the separate canvas/bridge resolver, not managed uploads.
Borrowed CanvasView:2371–2398 awaits native path resolution then calls onAddNode in the current canvas; original destination/incarnation guarding is a root-owned caller handoff, not a helper defect or native-run claim.
DataTable upstream maximum is shortest distance to any selected anchor, which matches the number of traversal levels needed to include all reachable sources; do not call it a longest-path bug from branch wording.
Graph error extraction is presentation-only detail retention, not a protocol or execution validation authority.
Keyboard helper covers current native and semantic editable descendants; plaintext-only editable would be an extension but no current such consumer is present, so no fabricated shortcut incident is added.
Node naming/colors are reversible presentation helpers with existing focused oracles; no low-value implementation-mirroring tests or broad app checks are proposed here.

M1 and all repairs/runtime remain held. Current mutable source hashes still require final consolidated review and independent global completeness acceptance.


### Complete-review checkpoint — reviewer-batch-38

No material new product defect found in this group.
The current flat ESLint9 policy is the active authority; .eslintrc.cjs is explicitly ignored, so its legacy requires do not establish an active installation failure. Removing this apparent second policy is an optional maintenance simplification, not a required repair.
The app/Node compiler and Node/DOM/IndexedDB test projects have explicit scopes. Source test inclusion and standalone E2E ownership differ intentionally; generated schema/coverage exclusions do not certify API compatibility or runtime coverage by themselves.
The OpenAPI shell generator is the exact current source producer for frontend/src/api/types.ts, using configurable server input and npx openapi-typescript. With task dependencies installed, npx resolves the installed package; the shell command itself does not pin a standalone fallback. No generation or current schema-equivalence check was run.
Campaign collection refuses missing/stale/unmarked/duplicate exclusions and zero selected tests; ordinary CI still invokes excluded handlers, while the campaign wrapper annotates and skips only when explicitly enabled.
Fixtures use deterministic cloned revision-aware in-memory persistence, controlled promises and fresh fake IndexedDB. They do not own server incarnation checks, physical cancellation or real browser DB lifetime.
Global PrimeVue toast/confirmation services are deliberately no-op setup; visible Dialog and VueFlow wrappers provide DOM/context, not native/window/dialog acceptance.
The status projection rejects contextless or revision-mismatched execution overlays, retains semantic edits, and treats exact scoped idle cache corruption separately from running execution and similarly prefixed siblings. Existing focused tests distinguish those cases without inferring execution command admission from badge output.
Popout theme listeners live for the dedicated page lifetime; missing component teardown is not an ownership defect in that bootstrap entry.
All source judgments are static. M1 and all fixes/runtime remain held.


### Complete-review checkpoint — reviewer-batch-39

#### reviewer-F081 — optional clipboard absence can publish a false copy success

P3 source-supported presentation candidate: `PathCell.vue:41–46` awaits `navigator.clipboard?.writeText` and then reports success even when the clipboard API is absent.
The active `ImageCell.vue:372–378` handler mirrors this exact behavior; its `PathCell` consumer at428 passes `show-actions=false`, so the active action is the ImageCell owner, not the hidden PathCell buttons.
An absent API thus takes the success branch without a write; present APIs rejecting are correctly surfaced.
This is conditional source evidence, not an executed clipboard incident or native-browser claim.
The path-cell essential contract preserves access to full path and a copy action (v1 path-cell clause around1301); future correction should preserve that action and truthful success/failure feedback, with the existing handler/DOM seams before new broad tests.
No unused PathCell claim is retained: an earlier clipped search was explicitly corrected after tracing its production consumer.

The sort/filter/resizer/paginator controls have coherent bounded state ownership; valid page/filter schema ownership remains with their store/API caller.
The narrow component tests do not establish a campaign coverage omission: borrowed existing `node-data-widths.spec.ts:19–104` checks actual pointer/keyboard geometry and persistence, and `canvas-interactions.spec.ts:940–967` checks between-filter admission and request/results.
Those borrowed excerpts add no whole-file review credit and no execution credit.
Avivator DOM and mocked Dockview tests demonstrate parameter/rendering/control wiring only; third-party iframe/range/session ownership and native popout acceptance remain separate.
M1/global completeness and all repairs/runtime remain held.

### Complete-review checkpoint — root-batch-19

#### ROOT-F090 — P3 README storage and viewer-environment descriptions contradict current supported behavior

frontend/README.md:81 describes execution outputs as using a configured output-data folder; actual WorkflowStore.get_storage_path derives workflow-local results, and backend/README.md:144 correctly says moves/deletes carry those results while duplicates start without them.
backend/README.md:84 says the viewer/code-server environments no longer accept user-configured paths without distinguishing default managed provisioning from explicitly supported adopted/external viewer definitions documented nearby and reviewed by B.
This is documentation scope/fidelity debt, not proof that execution writes to the wrong location or permission to remove essential adopted/external environments.
Future documentation reconciliation should state actual workflow-local storage, separate dataset configuration and default managed versus declared external ownership concisely; no new runtime test is justified by the prose correction alone.

#### ROOT-F091 — P3 obsolete hard-coded editor worktree launch configuration

.vscode/launch.json:123–154 labels Backend-worktree out of date but retains a .claude/worktrees/known-packages-installer backend/interpreter path that does not exist in this workspace.
Its update comment refers to a Build Frontend task absent from the complete tasks.json, whose task is Frontend:dev.
Normal Desktop/Backend and explicit local-Core profiles retain distinct source/environment configuration and are not claimed broken.
Future maintenance should make the optional worktree profile use documented .worktrees layout or remove a genuinely obsolete specialized example after checking intended developer usage; no Windows runtime behavior or launch execution was certified.

### Artifact and pointer judgments

launcher/launcher.svg and logo/microscope.svg were read as complete self-contained XML source; no external resource references occur.
The complete borrowed scripts/generate_desktop_icons (owned elsewhere) generates platform PNG/ICO/ICNS from logo/microscope.svg with configured transparent padding and sizes; it derives launcher ICNS from the existing portable launcher PNG, not launcher.svg.
The portable icon_128x128.png is actually a 512x512 RGBA rocket master, individually viewed; its upstream art producer is not established, so it is retained as a source asset rather than falsely credited as derived from the microscope SVG.
The platform app_icon.png is individually viewed 512x512 RGBA microscope art consistent with the source; app_icon.ico is a seven-image ICO and launcher app.icns is a typed ICNS with table of contents.
Borrowed application/distribution packaging metadata and the earlier full desktop module establish packaging/runtime icon roles, but no fresh generation, byte equivalence, cross-OS decoding or physical native rendering is claimed.
The image inspection tool cannot decode ICO/ICNS here; that tool-format limitation is not evidence the icons are corrupt.
Each binary's ledger hash addresses its actual bytes; no glob or inventory count supplies review credit.

signing is a tracked mode160000 gitlink to e5234018a031c1b89d56b65369dba4a17c910635, with identical baseline/current git ls-tree descriptor.
Its content_sha256 is the SHA256 of the canonical descriptor including mode, object ID, tab-separated path and trailing newline, replacing the earlier unavailable placeholder explicitly.
.gitmodules identifies a separate private signing repository; pointer ownership and boundary are classified, while that repository's private contents/key material are neither included in platform source-review coverage nor inspected.
The temporary merger verifies the exact descriptor against both current and frozen trees before granting classification.
This exception does not exclude or classify any other pending human input.

M1 remains open: this metadata/artifact batch closes neither application acceptance nor the complete cross-owner review.

### Complete-review checkpoint — A-batch-37

No additional chooser production defect was identified in the complete current implementation.
Retain the accepted-response versus operation-finalizer ownership distinction, current membership and exact captured payload, no conflict replay, explicit try/remove/refusal, and complete disposal barriers.
Historical N1 browser stress ISSUE-022 remains a separately retained Open issue with unproved cause; this read-only judgment does not rerun/close it or credit native interaction.
Frozen I1 and tool-binding files remain separate exact content inputs and uncompleted campaign acceptance.


### Complete-review checkpoint — A-batch-38

#### A-F176 — Medium qualified source contract gap, create-for-group carries packages but not napari version constraint into recipe

Frozen ImageViewersSection transferSetupGroup75–87 copies requested packages/recommendations/gate/group but never reads managed_create_prefill.napari_version_constraint or group.napari_version into create recipe.
createManaged135–155 chooses default/legacy fixed preset or preexisting advanced napari value independently of that captured portable version requirement.
ViewingRequirementsGuidance advertises the group napari constraint and `Create environment for this set`, so an explicitly selected group requiring a different version can produce a successfully validated recipe installation that remains incompatible with its originating outputs.
Backend managed validation verifies chosen recipe and subsequent readiness may expose incompatibility; this is no silent execution or required-package bypass claim.
Actual canonical prefill schema retains napari constraint and tests supply null, so current DOM cases cannot distinguish it being dropped.
A version range is not necessarily one installable exact version; future correction must reconcile/resolve it against preset/advanced version policy or explicitly explain/refuse incompatible chosen recipe, preserving captured source confirmation and separate groups instead of naively assigning an arbitrary range string to an exact-version recipe field.
No environment provisioning or incompatible runtime was executed; root/main section owner may reconcile this equivalent main-path clause without duplicate credit.

### Existing A-F168 extension — creation correction does not retire unrelated settings form finalizers

ImageViewersSection saveRename captures id/name and confirmRemoval captures id/managed choice correctly before awaits, but success closes/clears whichever rename/removal dialog is current, and addExisting/addRule clear live text fields after completion.
run catches any late failure into one shared error and operation watcher catch does the same, without a presentation invocation/retirement owner; main bounded server request/CAS mitigations and intentional durable polling do not identify current form presentation.
New recipe owner is correctly captured and is not evidence all other dialogs are fixed; future exact scope should link the existing shared-finalizer contract rather than broaden this frozen I1 task blindly.
Mounted tests immediately resolve the older noncreation actions and cannot distinguish cancel/reopen/new input after held submission.
No wrong server target/rollback or native action was reproduced, and committed operations must not be replayed for a discarded presentation.

### Existing B-F166/B-F167 exact frozen WIP corroboration

Frozen store380 preserves lower registry revision acceptance and incoming terminal request id overwrite before correlation.
Those are B canonical current-source findings, retained as separate exact-content corroboration; stronger new readiness owner is a sound decision rather than a general environment event fix.
No duplicate B source credit or executed recurrence.


### Complete-review checkpoint — reviewer-batch-40

#### reviewer-F082 — retained error navigation omits source workflow identity

P2 qualified source risk: `ErrorHistoryPanel.vue:14,34–35,115–123` emits only `nodeId`; borrowed `ErrorEntry`/report source carries no workflow/draft/incarnation, and `MenuBar.vue:1153–1155` selects that node ID in the current UI store.
A retained error for workflow A can therefore address an identically named node in subsequently active B; no active-origin validation is visible at this navigation seam.
The existing counterpart asserts only emitted `n42`.
This is a presentation/selection ownership candidate, not workflow mutation or reproduced wrong selection; backend execution attribution remains separate.
Future correction should preserve history/navigation and resolve the stored source identity or clearly refuse stale navigation, not clear unrelated history.
Borrowed source excerpts add no file credit.

#### reviewer-F083 — claimed close-event test can perform no assertion

P3 exact oracle defect: `ErrorHistoryPanel.test.ts:195–216` sets `visible=false` before querying the close control, then asserts the emitted event only if the now-absent control is found.
The actual template `v-if=visible` removes that control, so the named close-emission behavior can pass without exercising or asserting it.
Use the existing case/control while visible and assert the event; no new test family is necessary.

#### reviewer-F084 — parameter error ARIA describes the wrapper rather than the edited control

P3 source/accessibility candidate: `ParameterFieldError.vue:19–29` places aria-invalid and aria-describedby on its generic wrapper div; the slot is unchanged.
Borrowed active `NodePanel.vue:1020–1060` renders input/select/checkbox controls inside it without those associations, and an exact-file search finds no aria-invalid/describedby forwarding in NodePanel.
The hidden description and red-border/title contract work, but the actual interactive control does not receive this semantic association from the wrapper.
The current counterpart asserts only wrapper attributes, not the slotted input relationship.
No screen-reader/browser execution or broad accessibility certification is claimed; preserve visual tooltip/detail essentials while correcting the existing control association seam.

#### reviewer-F085 — v1 global-error dismissal prose conflicts with retained acknowledgment implementation

Documentation/contract reconciliation candidate: v1 around1440 promises individual cross-button dismissal and transient auto-dismiss; these complete source/tests deliberately retain entries and expose Mark as read/unread with an explicit no-delete/no-clear assertion.
Borrowed ErrorStore autoDismiss acknowledges rather than removes.
This discrepancy needs an explicit coherent product/spec decision preserving useful history and transient feedback; static review does not authorize narrowing an essential promise or silently adding destructive controls.

The projection uses current active-canvas status, so stale execution failure is hidden after semantic edits; displayed all-results-discarded guidance is not independent backend proof.
Optional low-impact candidate: traceback copy continuation can resolve after unmount and create its two-second reset timer after the unmount cleanup has already run; there is no stale command dispatch or demonstrated long-lived leak, so prioritize origin/selection and oracle corrections first.
All findings are held; global completeness/current-control acceptance remains open.


### Complete-review checkpoint — reviewer-batch-41

#### reviewer-F086 — demo deletion loses the identity that proved demo ownership

P2 qualified destructive-target source risk: `StorageSection.vue:147–155` refreshes demo status, then retains only each installed item's workflow_id and discards its returned identity_generation.
`captureDeletionRequest`108–115 captures whatever incarnation the workflowStore currently associates with that name.
Borrowed demo service120–122 supplies the identity of the provenance-proven installed demo; borrowed App deletion1263–1269,1317–1342 verifies only the request's captured current identity/session before sending that expected generation.
If the name is replaced and the current store observes B between the status response proving A and per-item request capture, these strong generic guards can correctly protect B while the higher-level demo action incorrectly selected it.
The confirmation promises other workflows in Demo are kept; preserve that essential promise and existing generic admission guards.
Existing component mock already supplies identity_generation but asserts only names/event counts; an existing held-status/replacement oracle is the smallest later diagnostic seam, not new broad coverage.
No deletion/data loss was executed or claimed.

#### reviewer-F087 — workspace/status refresh completions lack current-request ownership

P3 qualified stale-presentation source risk: `StorageSection.vue:78–100` refreshes overwrite demoStatus/workspaceInfo after await with no request/root/disposal tag.
SettingsPanel refreshes after retarget while mount, reopen and workflow-list watcher can also have outstanding requests.
An older root's held info/status can finish after newer root facts and replace the displayed/reveal path or demo affordances.
This is UI facts/action-affordance ownership, not a proved server root-retarget defect; normal Settings persistence and PATCH-workspace/admin restrictions retain their separate source owners.
Preserve legitimate new-root initialization/demo seeding, current Retest probing and native-last boundaries.

#### reviewer-F088 — OMERO removal confirmation retains a mutable row index

P2 qualified confirmation-target source risk: `OmeroSection.vue:132–149` builds a message from the old row but the delayed accept closure splices current rows at the captured index.
`syncRows`40–49 can replace/reorder that list when an outstanding Settings response supplies new omero_instances; the confirmation does not revalidate the confirmed instance identity.
The existing confirmation stub immediately accepts, preventing its current oracle from distinguishing that ordering.
Preserve explicit confirmation and credential-removal semantics; bind/refuse the original target before mutating the current list rather than weakening confirmation or silently selecting another row.
No real keyring operation occurred; ROOT-F001 old-credential rollback remains distinct.

#### reviewer-F089 — successful unrelated OMERO array updates can clear newer local drafts

P3 qualified local draft-loss source candidate: the watcher51 unconditionally reconstructs every row and clears every password whenever omero_instances gets a new array.
A Save request contains captured metadata and only the selected row's password; while it awaits, the form remains editable.
A successful response can therefore erase newer edits/password text entered after submission or unsaved text on another card.
Failed keyring updates are deliberately nonoptimistic in the Settings store, preserving retry text; do not conflate that good failure behavior with the late-success form reset.
The current form tests have no delayed response/continued-edit oracle; use existing prop-update/form seams after M1 before any correction.

F083 extends to `SettingsPanel.test.ts:126–144`: the named section-update forwarding case invokes store.updateSettings directly, so it cannot fail when section event wiring/onUpdate breaks.
F027 is corroborated by the pure mocked managed-control text case in SettingsSections: ordinary CI remains separate; no runtime omission or removal authorization is inferred.
The Settings shell, new-workflow preference scope and workspace read-only/native gates are otherwise coherent; current mock tests do not attest native filesystem selection, real retarget persistence or demo provisioning.
All findings remain held pending whole-audit acceptance.

### Complete-review checkpoint — root-batch-20

#### ROOT-F092 — P2 source output-schema URL fails to encode a supported node identifier

api/client.ts:29–31 directly interpolates nodeId into the URL path.
Graph ToolNodeState admits nonempty strings, and the complete library Node constructor prohibits only empty/slash names; question-mark and fragment characters are not refused there.
An identifier containing ? or # changes URL query/fragment semantics rather than addressing that exact node route; ordinary GUI-generated ids mitigate common occurrence, while imported/API-authored names retain this source boundary.
No request was executed and literal slash names are not claimed valid library node names.
The resolved-output store catches transport rejection as unresolved schema, so this can surface as misleading unresolved output rather than bad worker execution.
The complete client counterpart tests transport defaults and server detail promotion, while resolved-output counterparts replace this adapter entirely; neither distinguishes exact special-character route identity.
Future correction should encode supported path components and verify the actual transport/router contract for supported special names before broad browser coverage, preserving whole-graph schema input and current no-content-type-default behavior.

#### ROOT-F093 — P2 qualified older source propagation can supersede an independently newer target refresh

resolvedOutputs.ts:199–232 traverses the captured source graph, which correctly prevents traversal of edges introduced only after source request admission.
For a target already present in that old snapshot, it unconditionally clears the target timer and allocates a newer per-target request id when the older source completes.
A still-current source request captured graph G1 can be held while a target parameter/edge change schedules target refresh for G2; when the older source resolves first, its propagation cancels the newer target timer and resolves target against G1.
CanvasView:1943–1980 refreshes changed dynamic nodes individually, and connection/disconnection handlers refresh affected targets without automatically retiring every unchanged upstream request.
The existing strong tests distinguish an already dispatched child superseded afterward and a newly added edge absent from G1, but not an existing-edge target change before old source reaches that target.
Current request ids defend late response arrival, yet the later dispatch of old graph work wins this particular authority ordering.
This is a source-qualified stale-schema/presentation schedule, not an executed corruption or a demonstrated wrong engine run; exact graph/output compilation remains backend authority.
Future distinguishing test should extend existing held-source fixtures with an unchanged connecting edge plus newer target edit, preserving captured-edge traversal, per-canvas separation, origin retirement and dynamic metadata classification.

### Existing B-F176 extension — validation grouping also uses inherited user-key lookup

useValidationErrors.ts:23–35 groups by node/edge id into ordinary {} and then calls push on an inherited member if a key is __proto__ or constructor.
These user ids are accepted as nonempty graph identifiers; NodePanel selectedNodeErrors and Canvas edge-error projection actually consume the maps.
The inherited value is not an Array, so this consumer can throw during computed grouping rather than publish an exact error group.
This is a distinct grouping consequence of the canonical JavaScript dictionary-key authority finding, not duplicate remote preflight execution evidence; ordinary generated ids and server graph validation mitigate common paths without imposing a reserved-name contract.
Existing complete132-line tests distinguish error-kind/node/edge/global routing only with ordinary ids.
No JavaScript diagnostic was executed.

### Retained helper and counterpart judgments

FieldFocusTracker uses collision-free JSON tuple keys, copies exposed targets and scopes by canvas/node; actual NodePanel pairs focus/blur and clears tracked rows on selection/canvas change and unmount.
The already-unfocused microtask callback has no returned cancellation handle, a bounded lifetime caveat to consider with its exact caller rather than a new proven canvas leak.
The clearTracking test sets a callback but never blurs afterward/asserts noninvocation, so its comment exceeds its precise assertion; preserve useful cross-canvas and callback-once cases when tightening that existing oracle.
ErrorReporting deliberately retains history outside Vue injection scope and suppresses some background toasts; command alwaysToast does not consume background dedup, and provider exceptions cannot erase history.
The once-kind set is consumed before successful toast emission, including no-provider contexts; clarify whether once means first report or first visible toast before treating that policy as a required behavioral fix.
Its complete tests force hasInjectionContext true and preserve per-kind/command/error-history oracles, not real provider lifecycle or historical workflow origin; reviewer-F082 owns that origin seam.
useSettingsPanel current main keeps shared suggestion state without WIP owner/version; A-F168 owns actual creation finalizers and frozen I1 has separate exact credit.
useEdgeError is a pure joined tooltip/error presence projection; useValidationErrors intentionally separates cycles/global, edge and node fields, with inherited-key caveat above.
The short ColumnTypeString union and main.ts plugin/style/bootstrap wiring have no independent source finding; no runtime bootstrap/third-party version certification follows.
Fiji wrapper counterpart omits result identity and therefore proves client forwarding only, matching earlier qualified Fiji route refusal findings; it is not a real accepted viewer open.
ResolvedOutputs preserves per-canvas caches, source/child request retirement, inactive-null refusal and released-context barriers with controlled promises and fake timers.
Old disposer after same-id re-registration remains the existing acquired-lifetime question A-F043; no duplicate id-only ownership framework is proposed.
The obsolete useIndexedDB mock in the counterpart is not an active recovery dependency, corroborating reviewer-F080.
M1 remains open; no fix or test execution is released.

### Complete-review checkpoint — root-batch-21

No new canonical defect IDs.
App lifespan counterparts explicitly enter lifespan, unlike ordinary ASGI fixtures; they preserve settings loading, exact recovery-before-snapshot/catalog order, fatal ambiguous move refusal, nonfatal orphan-cleanup log and shutdown managed-service/settings calls.
The real pending move test injects a failure after physical move, restarts the actual service/app and checks journal cleared plus moved workflow identity; this is a valuable recoverability oracle, not a mocked call-order equivalent or fsync/power-loss certification.
Managed reconciliation/close tests mock service methods, so assert wiring only, not physical worker/provisioning completion.
Static counterparts distinguish root/nested SPA fallback, genuine assets, missing asset404, API precedence and no-config no-fallback; no production bundle/assets/native render is certified.
Developer fixture tests prove real metadata registration/graph validation plus actual canonical stored image result and compatibility-view readback; graph validation is not execution, and seeded ImageResultFixture storage is not a processing worker/PID witness.
Exception cases preserve typed shape/structured details, expected403/422 quiet logging and service503 diagnostics; stale docstrings about health/content-type are maintenance debt rather than the actual executed test behavior.
Filesystem reveal counterparts patch native dispatch and distinguish exact payload/OS error logging, not immutable deployment-policy enforcement (ROOT-F002) or physical file-browser acceptance.
Launch tests are source-configuration guards for published versus explicitly isolated local Core, Vite task/background readiness/loopback and packaged production arguments; they do not prove the obsolete worktree profile works (ROOT-F091) or certify Windows paths.
Node response model tests preserve exact row/column/absolute-row/type shape and Unicode rather than general data-query identity/order guarantees.
Error/validation model counterparts contain small construction/default/serialization overlaps that could be consolidated later while preserving strict extra/type refusal, structured detail schema and roundtrip distinctions; no measured cost warrants deletion now.
The short snake-case error-code test supplies examples without rejecting another code; it proves accepted examples, not a general enforced lexical schema.
Health200 and payload cases duplicate one simple request/setup seam, a low-cost optional consolidation candidate rather than a product defect or priority speed gain.
M1 remains open, no diagnostics/repairs/runtime acceptance released.

### Complete-review checkpoint — root-batch-22

No new canonical defect IDs.
Code-server tests execute an isolated installer subprocess over locally constructed tar/file URL fixtures when run; they distinguish verified extraction, retained extension reuse, digest/download failure, layout traversal and incomplete launch entry refusal plus relative prefix ownership.
They do not certify the actual released archive, native code-server launch, equal-byte regeneration or cross-process publication; run_installer has no explicit subprocess timeout, a bounded harness improvement candidate rather than an observed hang.
The constructed release root/version is fixture data and cannot establish current published compatibility.
Durability helper tests mock descriptors/fsync and correctly assert supported/no-op platform policy and closure after directory flush failure; real physical crash/power-loss semantics are outside that oracle.
Known package tests preserve bundled resource and explicit user-file-replaces-bundle semantics, comments/blanks and missing-input warning.
The default-constructor case permits machine user overrides and checks only list/string shape, so it is an honestly weak default-resolution oracle; inject a controlled user root if later tightening without removing override support.
Output template integration actually constructs a public Workflow, computes DefaultEngine/direct, compares generated asset basename/location and distinct record parents after template change; this is stronger than metadata/config-only spies and does not prove a worker PID or published package.
Managed profile counterparts execute trusted local config files in controlled temporary roots and distinguish exact RemoteCluster type, byte digest change, symlink refusal, minimal reconnectable persisted facts, obsolete profile drop/default repair and explicit-only digest refresh.
Their managed-remote campaign exclusion includes deterministic local persistence contracts, corroborating reviewer-F027 without implying default/full CI omission or authorizing remote provisioning.
Package catalog tests preserve installed/known union, upgrade availability/error fallback, active-version/load-error metadata, no PyPI lookup for custom sources, registry-only no-refresh and no extra network on active-version patch.
They use fake version lookup, and selected-version forget fixtures have different tool class names per version; they do not close live same-name captured-class authority or active-version repair findings already owned by A.
PyPI service counterparts use MockTransport, deterministic normalized URLs/ascending versions,404 versus network/timeout and latest-stable/pre-only/empty semantics; all clients close in finally, no live index evidence is implied.
Operation failure tests distinguish mojibake normalization from already-correct Unicode and structured diagnostic tail, not real Windows provisioning.
Validation boundary counterparts control actual validation thread entry/release and persist actual winning graph/revision; they preserve event-loop responsiveness, stale draft/nested CAS refusal, delete/recreate identity refusal and saved-graph reset revalidation.
Those are distinct causal admission windows, not redundant because all use two graphs; bounded worker waits and finally release are important evidence to retain.
An earlier assertion failure can bypass final awaits located after try/finally, so future harness lifetime cleanup may ensure admitted tasks are joined without replacing meaningful barriers with timing sleeps.
M1 remains open; all fixes/new diagnostics/runtime acceptance remain held.

### Complete-review checkpoint — B-batch-31

#### B-F177 — P2 source late starting snapshot bypasses terminal fencing

Execution store `applyStatusSnapshot:669–693` treats starting as a separate provisional branch before the ordinary `acceptPayloadContext` and `applyBackendPhase` fences.
After a matching execution has completed, a late starting snapshot for that same ID/workflow/draft passes the branch's idle and non-older-draft checks.
It assigns provisionalContext and changes state back to starting even though terminalExecutionIds remembers that ID and terminalFence is set.
Run and mutation controls therefore re-lock provisionally until the next successful poll returns the authoritative idle state.
Failures in that poll leave the provisional lock polling rather than restoring the known terminal phase.
This is a source-level delayed-response schedule, not an executed timing failure; successful follow-up status recovery is an existing mitigating path.
Existing exact tests `keeps a completed WebSocket run fenced when the Run response is mismatched`, `rejects late events from an older execution id`, and `handles a newer %s reconnect snapshot without prematurely committing identity` distinguish other paths but never terminal→same-ID starting.
Future diagnostic should extend the controlled snapshot ordering fixture to retain legitimate newer external starts and provisional startup recovery while distinguishing terminal identity reuse.
The existing bounded eight-ID history is intentional bounded memory; no blanket infinite-history requirement or stale worker execution is inferred.

#### B-F178 — P2 qualified disposal does not retire an in-flight provisional status response

Execution store `scheduleProvisionalStatusPoll:305–317` clears its timer handle before awaiting fetchStatus.
`onScopeDispose:319` clears provisionalContext and any currently scheduled timer, but has no disposed/request generation marker.
A GET already in flight can later call applyStatusSnapshot with starting, recreate provisionalContext, and schedule a new timer after the store's scope was disposed.
This can retain the old store and repeated status traffic; it does not by itself mutate a replacement Pinia store instance or alter backend execution admission.
The matching scope-disposal callback correctly cancels timers that have not started, which must remain supported.
Exact existing test `polls an externally observed starting identity back to backend idle` resolves the GET immediately under fake timers; newer reconnect test disposes before any held GET and cannot distinguish physical in-flight completion after disposal.
Future diagnostic should hold the GET, dispose the store, then complete the response and assert no rearmed poll, preserving active-store reconnect behavior.
No timer leak or network request was executed in this audit.

#### B-F179 — P2 qualified remote Run continuation and dialog lifetime lack the local owner barrier

RunButton's local preparation captures workflow/canvas, checks `isTargetActive` after freshness/flush/confirmation, and enters the final synchronous local lock before awaiting exec.run.
`runDistributed:242–301` instead captures a prepared request and awaits preflight, optional resolution dialog and second preflight without checking that the initiating canvas, selected target or component is still owned before applyPreparedExecution.
`runCore:355–361` checks isTargetActive only after the remote operation has already applied, when deciding whether to emit run-started.
Changing canvases or targets during the held preflight/resolution therefore does not cancel the old captured submit intent; this needs explicit intended-command lifetime reconciliation before repair, rather than forbidding all detached execution.
The request still sends the original exact workflow/draft/target/profile and token binding; backend token consumption is one-shot and strict, so this is not wrong-target worker execution or demonstrated replay.
The UI has no remote busy admission during first preflight, and local exec state does not lock this phase; repeated clicks can admit multiple independently prepared command promises, unlike same-token replay.
No duplicate scheduler submission is claimed without the registrar's full existing admission contract and an exact diagnostic.
Both confirmOutOfDate and requestRemoteResolution retain promise resolvers but the component has no on-unmount resolver/drain.
Escape/cancel correctly resolves a visible local dialog, but unmount while awaiting either dialog can strand the command continuation and references.
Late command failures also select the first validation offender/toast through the current global UI without a final owner check; local Run's earlier barriers do not cover a held transport rejection after a canvas switch.
Existing `does not redirect a confirmed run when another canvas becomes active` strongly distinguishes the local confirmation path only; managed-ready test completes both mock HTTP requests immediately and has no target/canvas switch or unmount.
Future diagnostics should extend those controlled component fixtures for held remote preflight/resolution and unmount, preserving explicit detached retained-run navigation, exact token binding and uncertain-ack attach-without-replay behavior.
This is a source/intent-lifetime risk, not a runtime or loss reproduction.

#### B-F180 — P3 scoped nested validation is filtered by direct root equality

executionSelection's selected closure follows graph root edges, then `validationErrorsForExecution:68–78` accepts an error.node only when it exactly equals a selected root or root upstream ID.
A selected nested invocation `nested` does not include its scoped leaf error `nested/leaf` in that set.
UseExecutionLock uses that filtered list to decide whether `valid=false` blocks a selected run, and RunButton uses the same filter for locally reported errors.
Thus a nonempty validation result containing only that selected nested descendant error can bypass the early client validation refusal and lose local offender details, while backend build/validation still refuses invalid execution.
Root graph_validator emits scoped plan IDs and aggregates WorkflowNode statuses separately; that aggregate mitigates nested out-of-date rebuild prompts and must not be described as universally missing.
No invalid processing admission or worker execution was demonstrated.
Existing Run Selected test distinguishes a downstream root outside the selected set, not a descendant inside a selected nested root.
Future diagnostic should add the nested selected-root/descendant-error axis to existing closure tests, retaining exclusion of unrelated branches and global errors, rather than widening all selected validation to the whole graph.


### Complete-review checkpoint — B-batch-32

#### B-F181 — P2 source terminal failure selection changes the current canvas rather than execution origin

ExecutionBanner's state watcher `49–74` finds the first failed node in exec.lastResult and calls `ui.setSelectedNodes` directly.
That method writes the current active canvas presentation, independent of exec.originCanvasId/executionWorkflowId or `appliesToCanvas`.
An execution started in A can finish while B is active, replacing B's selection with A's failed scoped node ID.
Global progress display intentionally remains independent of the open canvas, which is sound and explicitly tested; this does not authorize mutating another canvas's selection.
Scoped nested leaf paths can also be absent from the current root's direct node IDs; this needs explicit reveal/navigation semantics rather than interpreting every failed path as a root selection.
No graph mutation, wrong worker execution or runtime schedule was demonstrated.
Existing exact test `shows "Execution failed" and auto-selects failed node on failure` always keeps the execution's root active, while `counts only planned executable scoped nodes, including cached work, independently of the open canvas` checks counts but no terminal selection.
Future diagnostic should combine those existing controlled fixtures with an unrelated active canvas and retain useful failure navigation for the owning root.
Related low-priority terminal presentation qualification: when the component restores an idle lastResult without an active→idle transition, mode displays the result but never schedules auto-dismiss; restored cancelled snapshot test checks text/count only.
Reconcile the intended reconnect UX before treating persistent restored terminal banners as a defect; click dismissal still works and timer cleanup on unmount is present.

#### B-F182 — P3 qualified selector lazy-load latch and late preference authority

ExecutionTargetSelector `ensureTargets:18–33` sets loaded=true before the parallel target/settings requests.
Both store fetchers catch failures internally, so the promise normally fulfills even after a failed discovery; the selector latch never resets and reopening this dropdown does not retry loading.
An external registry refresh remains a recovery path; this is a control-local transient discovery issue, not permanently unavailable platform execution.
The completion applies a preferred remote target whenever the current selectedTargetId is local, without a captured user-selection generation or disposed marker.
A user who chooses local during the held initialization, or an unmounted old selector instance, can later have that global choice replaced by the fetched default.
A default applied during untouched initial loading can be intentional; future diagnostic must distinguish explicit user selection from initialization and preserve settings defaults.
Current tests `keeps the direct-submit acknowledgement warning visible for managed targets` and `omits unavailable managed profiles from the Run selector` prefill the registry and never trigger before-show or delayed preference fetch.
No target switch or execution was performed in this audit.
This is separate from B174 run-list scope buffering and B175 profile descriptions; no backend capability/read-only guard bypass is inferred.

#### B-F183 — P2 qualified upload-picker result has no draft/source ownership guard

RemoteExecutionDialog `chooseUpload:63–69` awaits pickFile/pickFolder and then resolves the current `draftFor(input,index)` to write its path.
The unresolved-prop watcher can replace all drafts while that picker is open; source can also change from upload to cluster, the dialog can cancel/unmount, or a second picker can supersede the first.
If a new plan reuses the same node/input/index, the old local picker path is written into that new draft or into a now-cluster choice; if the entry disappeared, the unguarded non-null lookup can throw from the late async handler.
This is a UI input-ownership risk, not a bypass of backend input validation or an actual wrong upload/cluster worker action.
usePathPicker's newest-request-wins browser dataset resolver mitigates overlapping browser picker requests, but it does not guard replacement dialog inputs or native picker completion.
The source explicitly requires every leaf's source choice and preserves list order; nullable none and absolute POSIX cluster paths remain essential supported behavior.
Existing exact test `requires an explicit source for every path leaf and preserves list order` mutates drafts directly, while the native picker mocks are never invoked.
Future diagnostic should hold one picker, replace/cancel/change source, then release it and verify no new-plan mutation, preserving ordinary upload selection and browser/desktop routing.
No native dialog was opened and no upload occurred.


### Complete-review checkpoint — B-batch-33

The full1157-line executionLock suite verifies connect/drag/edge mutation admission across starting/running/stopping, including a drag that starts before the transition and an edge-update event delivered after stopping.
Those transition tests are stronger than checking disabled UI attributes alone and must be retained.
`pasteFromClipboard is a no-op when locked` sets running before calling paste; it cannot distinguish A-F089's asynchronous clipboard-read completion after the lock changes.
`removes a repaired cache-corruption diagnostic after clearing outputs` exercises a real Canvas callback with mocked accepted revision/status response, asserting exact workflow/draft wire identity and repaired validation.
It does not hold Clear across canvas registration, workflow incarnation or unmount; A-F030 remains the canonical current-selection/consumer ownership seam.
No new duplicate finding is assigned for those absent schedules.
Pure validationAfterCacheClear intentionally removes cache_corrupt errors attributed to a repaired requested root, including a scoped descendant, while retaining unrelated semantic errors and failed roots.
Actual Canvas Clear filters requested IDs against accepted direct graph nodes and refuses nested-editor Clear, so a hypothetical arbitrary scoped-leaf helper call is not promoted to a GUI defect.
The helper does not claim to guard a delayed response's current canvas ownership; that belongs to its caller.


### Complete-review checkpoint — A-batch-39

### Existing A-F168 precise main creation-finalizer extension

Reviewer fully owns current main ImageViewersSection568 and test198; targeted cross-owner source reconciliation earns no duplicate full-file credit here.
Main createManaged104–112 captures recipe/request payload before await, but after createManagedEnvironment resolves it reads LIVE setupGroupId and consumes that group.
Submitting recipe for group A then selecting group B while pending can remove B's setup guidance even though B was not the accepted request recipe.
This is a presentation/suggestion finalizer ownership defect, not a wrong backend environment payload: the request still contains submitted A recipe and backend CAS/managed recipe validation are retained.
Existing immediate-response main form tests do not hold submission across group selection, as confirmed by the main-source reviewer; no runtime reproduction is asserted by this audit.
Frozen I1 section135–155 separately captures group and suggestion-list version before await and consumes only captured group.id with that version.
Its complete A38 held submitted-creation oracle retains replacement groups/payload, so this main creation-finalizer clause must not be falsely applied to the stronger frozen I1 content.
A-F176 missing version-constraint transfer remains in BOTH main and I1; captured suggestion identity does not reconcile the ignored napari constraint.
Future main finalizer repair must preserve accepted recipe/confirmation capture and avoid consuming newly current suggestions or replaying the committed creation.
Reviewer/root notified of canonical reconciliation; no new duplicate finding ID.


### Complete-review checkpoint — A-batch-40

Builder counterpart completely covers empty/single/mixed graphs, worker configuration, explicit positional DataFrame ordering, Processing column bindings, unavailable tool/package, disabled tracking and cleanup of globally active Workflow state.
Updated metadata fixture distinguishes actual DataFrameTool from ProcessingTool, row consumption and accepts_upstream, avoiding earlier A-F012 mislabeled metadata for this exact dirty version.
Internal _args/_column_bindings assertions are adapter shape oracles, not computations; ordinary Wetlands test checks engine/execution configuration only, not worker PID/public engine dispatch.
Owned binding diagnostic builds actual source bytes with Core-only declarations, hashes the record, materializes through actual public Workflow.from_dict control and checks Processing class, resource cpu3, actual selected Wetlands configuration and below-floor2 refusal.
It then stages/publishes the same owned bytes with actual OwnedWorkflowSources and reverse translates carried binding before constructing against same-name catalog DataFrame or unrelated Processing floor8.
Expected success/class/floor3 and below-captured-floor refusal distinguish executable-class/resource authority from display-name catalog metadata.
The source process_row returns constant1, but is not computed here; source materialization/engine classification does not provide worker invocation/PID/result or environment provisioning evidence.
Staged-source cleanup uses discard in finally; public Workflow paths and generated owned directories are fixture-temporary. No arbitrary network or pip install in the body.

Pinned package diagnostic creates two local package versions in BIOIMAGEFLOW_TOOL_STORE, supplied by existing autouse per-test isolated HOME/tool-store fixture (borrowed targeted conftest113–130, not duplicate full credit).
Version1 is an actual public-loaded Core ProcessingTool; version2 is same-name DataFrameTool. load_versioned_package returns actual modules and public Workflow.from_dict control asserts EXACT v1 class identity before catalog-v2 platform build.
Final assertion pairs exact first.BoundTool with Wetlands engine; this distinguishes public materialization/class/engine choice rather than accepting portable metadata alone.
Finally unloads both version modules; temporary store cleanup is fixture-owned. No published distribution compatibility, provisioning or actual compute/PID is claimed.
The absent processing floor/version structural checks do not weaken the exact class identity oracle; owned resource diagnostic covers that separate class/floor boundary.
Existing A-F001 captured portable authority and A-F002 wrong live resource-floor branch are the canonical causes; no duplicate codefinding or prospective repair validation.

Translator counterpart fully covers recursive one grammar, stable interface/edge IDs, schema2 viewer addition roundtrip, resource strictness/floors/DF refusal, deterministic dependency-aligned layout/disconnected/recursive/encoded-cycle remnants, package requirements/rebinding/missing/local semantics and scoped validation error category.
Carried module/class/package/version is assigned into both root and child PORTABLE graph BEFORE reverse/forward translation, then active registry is actual v2-stamped same-name class.
Exact equality to carried v1 fields and required package1.0.0 distinguishes captured binding from active catalog resolution; explicit rebind afterwards is the only expected transition to2.0.0.
This is stronger than the old test which would construct fields from whatever the adapter already selected and only assert its explicit rebind result; it does not infer every ordinary unbound/catalog node refresh is defective.
Owned source identity roundtrip remains a separate assertion over all five binding fields against same-name registry; public executable-class/floor tests provide the materialization boundary absent from shape alone.
Versioned/control tests intentionally avoid network and use public package loading; hand stamping active fixture is the adversarial catalog producer, not a promise arbitrary class labels are executable package availability.
Fixture golden test checks parent/nested type and normalized child schema2 with no adapter errors; it does not assert full canonical graph equality, known viewing snapshot, actual compute or preservation of all possible archived metadata.
Layout expectations retain exact positions because coordinates are platform materialization authority, not portable persistence; cycle remnant deterministic layout is not cycle admission.

Human-authored68line legacy1 fixture has one child Workflow binding list[7] to stable input-values, Generate declared constant column_name and stable output-value projected through root output-answer.
It intentionally has no viewer snapshot and no canvas positions; schema1 normalization to2 is supported, so its old literal is not itself an emitted-format defect.
Tool module is installed common-tools Generate, package/version null; this fixture tests ordinary module reference rather than captured installed pin, source bundle, actual archive or environment requirement contract.
Golden translator consumer was fully read here and main already reviewed; exact human fixture gets reviewed rather than generated/opaque classification.
No newly identified material defect in these added diagnostic assertions; retain controlled carried-before-roundtrip setup, real loader/class oracles and separate resource branches.


### Complete-review checkpoint — A-batch-41

#### A-F177 — Low/Medium qualified source/spec gap, ordinary saved requirement changes do not refresh current guidance

Frozen platform_specs_napari_environments Section7 requires the same passive check on requirement changes and relevant inventory changes.
Complete frozen MenuBar saveWorkflow535–555 invokes saveCurrentWorkflowGraph but never refreshes viewing manifest/readiness after accepted Save; captured root Save/export helper similarly preserves graph/dirty ownership without a guidance refresh.
Viewing owner predicate298–307 binds workflow/local-server generations and root registration, not graph/draft/saved artifact revision; ordinary semantic Save can change output viewer additions while keeping those identity fields and root registration unchanged.
Owner watcher316 subscribes active canvas/session count/active workflow/workflow list; list replacement only invalidates if identity owner ceases to match, not when accepted saved requirements differ.
Store refresh324–331 refetches saved public manifest when inventory operations invoke it, but no requirement-edit or ordinary-Save producer invokes it in these complete consumers.
Explicit Open/import and Python-source build/draft duplication refresh363/637/867 remain real mitigations: this is not a claim every source/manifest transition is stale or accepted stale sibling results leak.
Thus an already displayed readiness report and its setup suggestions can remain the old requirement set after a viewer requirement edit is saved, until Open or a relevant inventory mutation forces refresh.
Portable execution remains unaffected and exact retained-artifact resolver still checks its producer snapshot; consequence is stale advisory/setup guidance, not wrong artifact worker dispatch or native launch.
Current full mounted MenuBar tests distinguish import/Open, delayed siblings and same-workflow inventory replacement, but no selector changes viewer additions then performs ordinary Save and compares the public-manifest/report/suggestions transition.
No executed reproduction. Future diagnostic should mount accepted same-root presentation, accept old report, modify actual portable requirements, complete accepted Save and distinguish new saved-manifest refresh versus retained old guidance; do not replay Save or mutate current captured creation form to follow suggestions.
The contract for unsaved draft guidance is not resolved by this finding: even the narrower accepted saved-content transition lacks the required refresh.
No new tests/repair or release proposed while full audit is held.


### Complete-review checkpoint — reviewer-batch-42

#### reviewer-F090 — missing capability keys are treated as all-required ready

P3 source-supported report false-positive candidate: `ExecutionProfilesSection.vue:34–66` defines five required keys, but missingRequiredCapabilities filters only the keys present in the received report; template283 reports all required available whenever that result is empty.
A report omitting four required keys and supporting the fifth takes that success branch.
The exact existing component fixture advertises only durable_remote_diagnostics of the required set (plus two optional/other entries); it asserts display but not this false summary.
This is report readiness presentation, not submission admission, trusted-script security bypass or actual remote execution.
The smallest later oracle is an assertion in that existing fixture distinguishing absent/unavailable from explicitly supported required capability entries; backend normal complete discovery need not be presumed malformed.
B-F175 remains canonical for profile revisions/description cache/shared activity response ordering; no duplicate whole-store/API credit is taken here.

A-F176 is independently corroborated in current main: selectedSetupGroup watcher70–76 copies requested packages but never the carried napari_version_constraint; creation104–112 uses current fixed preset or advanced exact value.
A version range must be reconciled against supported exact/preset matrices or explicitly explained/refused, not assigned blindly to an exact recipe field and not silently discarded.
The current test group has null napari constraint, so it does not distinguish that contract omission.
No installation or incompatible runtime was executed; held I1 source improvements do not establish current-main integration credit.

A-F168 extends to current-main creation finalization: createManaged constructs the submitted recipe/name before await, but afterward consumes LIVE setupGroupId.
Changing from requirement group A to B while A creation awaits can remove B's setup guidance; request server target/recipe remain captured, so this is newer guidance/form ownership rather than provisioning another recipe or replay.
Other settings forms catch late errors/clear live fields and rename/removal dialogs with shared presentation state; preserve durable operation completion/polling instead of canceling physical committed work to hide stale presentation.
Held I1's captured new-creation owner is distinct and should retain its exact source/evidence claims.

F027 is corroborated by the fully mocked profile-description component case's whole-case managed-remote exclusion; ordinary CI/default execution remains separate, and no broad reclassification is authorized by this read-only audit.
Source/default/filename preferences do not override required compatibility, source-confirmation keeps unverified packages explicit, and managed/processing environments remain separate.
Tests prove DOM/API wiring only; native Qt/plugin/install/popup/reader behavior is held for final campaign phases.


### Complete-review checkpoint — reviewer-batch-43

F082 now has complete store-source corroboration: ErrorEntry/report retains nodeId but no workflow/draft/incarnation, so history navigation cannot validate that origin from this record.
F085 has exact complete counterpart corroboration: API deliberately exposes no dismiss/delete/clear, automatic dismissal only acknowledges, and read state is reversible without removing entries.
Parent confirmed no prior canonical ID and requires specification precedence resolution; this audit does not assume restoring destructive auto-dismiss is the correct product decision.
The current retained history/full-detail/logging behavior is meaningful and must be preserved while deciding coherent specification text and current-origin navigation.

Optional unmeasured cost candidate: all retained entries remain in memory and the complete history panel copies/sorts/renders the full array on changes.
For long sessions with many repeated events this has growing CPU/DOM/memory cost, but no benchmark or observed degradation was run.
If later prioritized, windowed presentation or efficient maintained ordering should preserve the complete selectable history and acknowledgment semantics; deleting entries solely to improve a test/count would narrow the current intentional feature.
Short finite automatic-ack timers and logger mirroring are not a demonstrated resource leak or duplicate-error bug.
Tests' fake timers/local Pinia demonstrate deterministic state transitions, not browser persistence or current-workflow selection.
M1 closure is still open; zero current-hash pending, independent completeness and mutable-controls acceptance remain required before fixes/runtime.


### Complete-review checkpoint — reviewer-batch-44

#### reviewer-F091 — intentional socket retirement leaves live callbacks outside current-socket ownership

P2 source-supported lifecycle risk: `useWebSocket.ts:537–549` disconnect cancels current pending requests, sets state.socket=null and closes the old socket, but leaves its onopen/onclose/onerror/onmessage handlers attached.
If a new connect happens before that asynchronous old close event, openSocket sees no previous pointer to detach; the old onclose445–449 can then set disconnected, cancel the new socket's ACKs and schedule a ghost reconnect because intentionallyClosed now belongs to the new connection.
Queued old messages/open/errors also refer to the mutable singleton without comparing their socket owner.
The existing mock close invokes onclose synchronously; the separate ghost regression connects while an old pointer still exists and correctly exercises openSocket's detachment, not this distinct disconnect→connect ordering.
Direct connect replacement does detach old callbacks, but it does not immediately retire existing pending ACK timers/promises; these wait to report timeout after their owner socket has been discarded.
Reconnect HTTP recovery also lacks a socket/retirement owner across its awaits and can finish after an intentional disconnect or replacement.
Future bounded ownership diagnosis should extend existing fake close/recovery/ACK seams with held old callbacks and exact connection-owner assertions, preserving bounded backoff, current-socket dispatch, visible failures and required unfiltered reconnect subscription.
No actual network ghost, missing log, native browser event or product recurrence was executed.

#### reviewer-F092 — older active-workflow event refresh can emit a newer-looking Open intent

P2 qualified causal source risk: handleActiveWorkflowChanged155–160 captures workflowId A, awaits refreshWorkflowTree, then emits canonical Open A without a producer generation/supersession owner.
A later B message can complete its refresh and Open first; the older A completion can then emit last.
A full source owner confirmed workflowStore's collection-generation refetch guard protects structural identity/list response relevance, not active-command ordering (A-F068 is related, not mitigation).
MenuBar begins its own Open intent when that event arrives, so its later Open request fencing cannot identify this older producer continuation as obsolete.
The existing test asserts a single sequential event only.
Preserve canonical Open admission/current-workflow guards and remote active selection; future exact controlled-event/refresh ordering should distinguish producer supersession before any repair, rather than weaken the Open gesture or infer cause from presentation.
This is not a reproduced failed workflow activation or proof about prior Firefox occurrences.

Execution/log payloads retain exact context checks and structural deletion generation protection; mock transport-only contextless cases do not establish current execution acceptance.
F027 is corroborated by a pure deterministic distributed-reducer case's campaign exclusion; default CI remains separate.
Optional small text precision: the disconnected tooltip always says reconnecting, including intentional disconnect where retries are stopped.
Global completeness, current-controls and repairs/runtime remain held.

### Complete-review checkpoint — root-batch-23

#### ROOT-F094 — P2 qualified retained retry/cleanup continuations lack invocation-owned presentation

ExecutionPanel previewRetry238–258 captures parentId but stores the eventual plan/error/planning finalizer in shared refs without verifying the originating parent/dialog/request.
The modal limits ordinary underlying clicks and closeRetryDialog refuses while busy, but repeated preview actions/retained-run commands or programmatic selection remain separate admission paths; no unconditional ordinary two-run race is claimed.
A superseded preview can overwrite a later plan, while confirmRetry reads the currently stored parentId; strict backend plan-digest/parent identity binding protects against accepting a wrong parent's plan and remains essential.
confirmRetry's late success/error clears shared dialog/plan or reads the current retryPlan to associate uncertain child identity rather than a captured confirmed plan object.
The mismatched uncertainty path explicitly refuses another retry, so this is misleading presentation/attachment availability, not a demonstrated duplicate scheduler submission.
previewCleanup157–173 similarly publishes old-run plan/error into current selected view; confirmCleanup captures its exact execution/digest correctly, then unconditionally clears whatever cleanupPlan is current and writes shared completion text.
The cleanup plan dialog visibly shows captured execution/digest, mitigating a hidden wrong target; the risk is obsolete plan/finalizer/error ownership and new-state withdrawal, not arbitrary artifact deletion or a demand to roll back committed cleanup.
Unmount clears interval only, leaving outstanding actions without a presentation retirement marker; durable committed run/cleanup operations must remain recoverable without replay.
Existing494-line counterpart preserves exact digest preview/confirm, explicit stale-plan repreview, unrelated409 nonreplan, exact-child uncertain attach and structured managed diagnostics, but resolves requests immediately and does not distinguish superseded preview/finalizer/unmount.
Future diagnostic should extend those controlled promises and exact plan identities before any source correction, preserving captured physical operation and user-approved no-replay policy.
B179's RunButton initiating-command lifetime is distinct; B confirmed no duplicate retained-action ID.

### Existing B-F181 extension — retained Canvas/Logs navigation also mutates current canvas by leaf only

ExecutionPanel selectOnCanvas147–151 takes the last segment of the selected job's scoped_node_path and calls ui.setSelectedNodes in whichever canvas is active.
It does not first navigate/validate the retained execution's workflow/root or nested path; workspace-wide history can therefore select an unrelated same-name node in another current canvas.
Explicit navigation may intentionally switch to that run's owning workflow, so future contract should implement/reveal or refuse the exact origin rather than forbid useful retained-run navigation.
Existing test checks Logs opens global logger only; it does not compare selected originating workflow/nested scope and source-qualified misselection is not an executed mutation.
Global history/progress and strict retained identity remain intentional; no new duplicate ID or wrong worker claim.

### Existing B-F045 extension — complete node CSV store lacks displayed result pinning

DataTable downloadCsv562–582 captures current page filters/sort but sends no cached source_identity; the API request type lacks the identity capability already recorded by B-F045.
Node pagination/sort/filter setters correctly carry the displayed source_identity, while this download rereads latest.
Thus exact displayed-record CSV export cannot be inferred from otherwise pinned query tests; latest-advance ordering remains the future distinguishing seam, with no executed changed output.
Merged projection CSV does retain source result identities returned by the projection, a stronger distinct contract that must not be weakened when repairing the node path.

### Existing B-F176 extension — data-table state dictionaries also admit inherited identifier entries

DataTable stateFor checks paginationState[nodeId] on an ordinary {}; __proto__/constructor can return inherited state rather than a newly owned default page object.
The existing reserved user-key family extends to request/cache state grouping without declaring every resulting payload invalid or executing JavaScript; actual ordinary GUI-generated identifiers mitigate common paths.
Correct encoded node-query URL is retained and contrasts with ROOT-F092's separate schema URL omission.

### Retained structures and suite judgments

DataTable full source preserves per-canvas request/controller/retry ownership, bounded409 delays, no-active fallback refusal, source identity through paging/filtering/sort and explicit captureLatest projection refresh.
Controlled counterparts distinguish independent identical node IDs, supersession versus aborted ignored response, Clear preventing old response, per-canvas retry, fixed action after activation switch and released-context refusal/re-registration.
These are distinct causal barriers; no count-based test deletion is justified.
Projection request arrays/maps are shallow copies and retries retain caller objects; mutation ownership is a scoped in-process contract to inspect before claiming arbitrary server misroute.
CSV failure finalizers write captured context without request/released guards, a narrower obsolete-error presentation candidate; deliberate downloads may continue after navigation and physical cancellation is not promised.
Counted retry statuses are HTTP409 rather than typed not-ready codes, so later synthesis should verify which server errors are actually transient before broadening/reclassifying retry policy.
Projection tests use mocked sources/responses with incomplete type shapes; they prove client request/state only, not real schema/row/source provenance or backend merge safety.
The CSV test installs URL methods with Object.defineProperty and only restores spies; runner/global restoration must be checked before claiming a reproduced pollution defect.
ExecutionPanel mount tests do not unmount wrappers that create5-second intervals, extending existing B012 fixture lifetime debt; no new leak or intertest failure was reproduced.
Their entire managed fixture group is campaignExcluded despite deterministic digest/UI/error tests, corroborating reviewer-F027 while ordinary/default CI remains separate.
Meaningful plan-digest/no-replay and exact retained-child oracle axes should stay even if setup is later shared; no native/local worker or scheduler certification follows.
M1 remains open, all repairs/new diagnostics/runtime held.

### Complete-review checkpoint — root-batch-24

### Existing B-F012 extension — held socket fixture exceptional setup can wait without a bound

test_held_worker_fixture listener.accept and messages.readline have no timeout, inside ThreadPoolExecutor context whose exit joins submitted process_row.
A fixture setup/import/connect failure can leave accept waiting indefinitely; an assertion before setting task.cancel_requested can skip the intended cooperative cancellation sequence.
Successful socket closure eventually makes recv return empty and worker raises, a relevant cleanup mitigation after acceptance rather than a bound on never-accepted control.
result(timeout=1) occurs only after those blocking steps and does not bound executor shutdown; no hang was reproduced.
This is the canonical exceptional fixture-lifetime family, not a real worker transport/PID claim: these cancellation/failure cases intentionally call process_row in a local thread and assert os.getpid.
Future existing harness correction should own bounded accept/read, cancellation/release and physical join while preserving started/observed/acknowledged/no-output distinctions.

### Retained fixture/runtime boundaries

Platform fixtures derive metadata from actual classes, use positional whole-DataFrame versus column bindings explicitly and emit named row indices plus exact values.
The direct DataFrame-only counterpart actually computes/readbacks expected rows and verifies selected engine is Direct despite portable Wetlands preference; it is separate from the externally marked actual processing worker case.
The external processing counterpart provisions an isolated managed root when run, compares child PIDs against parent and one worker, exact rows/report bytes and three distinct confined record-relative owned assets, then surfaces real close failures before reset.
Those strong worker/record/cleanup oracles must remain; this audit provides no new pass or compatibility certification.
HeldWorkerNumbers imports Core only, announces worker PID/payload through its explicit socket and cooperatively emits observed/acknowledged cancellation before no-output return; task progress and intentional multiplier-zero failure are distinct supported fixture branches.
Restarted_processing public persisted manager harness constructs actual platform adapter/engine, compares actual owned record paths/bytes and closes engine/shared manager in finally; source execution requires external resources and stays unrun.
StaleWorkerNumbers versus IncompatibleWorkerNumbers have deliberately different exact recipes; same environment name between ordinary WorkerNumbers and HeldWorkerNumbers uses equal declared recipe rather than proving arbitrary recipe alias compatibility.
Fish parallel test invokes actual AverageSpotsPerNucleus over constructed four-image nested marker branches and validates ordered image/global-summary row plus retained scoped result keys; it does not assert actual microscopy measurement values, segmentation quality, a worker PID or full released demo workflow.

E2E app uses disposable configured storage/home/tool/Wetlands roots, real application/services with explicitly registered dynamic tools and dev-only observation endpoints.
Its execution-failure route broadcasts constructed contextual log/completion through actual WS manager, so browser error journeys are real transport/presentation but synthetic worker-failure producer.
Worker/Pixi observation endpoints and actual manager adapter are separate stronger lifetime probes; no certification follows merely from their presence.
Injected offline PyPI lookup creates no real client; app ownership flag avoids closing it as an app-owned client, so the bypassed constructor is not itself a shutdown defect.
Hot-reload fixture writes a minimal Files DataFrameTool and deliberately exercises actual package loader; it is not full common Files behavior or installed compatibility.

Manual-QA producer builds deterministic images/table/local package, genuine public workflow archives with captured custom sources and nested child snapshot, deliberate corrupt ZIP and a constructed result bundle containing README rather than actual produced run records.
That result bundle is a format/import fixture, not real-output provenance; manual reviewers must not treat it as an execution/export witness.
Prepare refuses nonempty unmarked/modified roots, validates nonoverlap with repository/home roots, records generated checksums and removes generated bytecode; evidence is deliberately excluded from checksums.
Clean deliberately accepts a marked modified QA root for cleanup after interaction, not immutable fixture certification; restoring verify-before-clean would need a product decision because normal QA changes those files.
Prepare's check-then-create/rollback lacks exclusive ownership against another writer in the same root, a conditional maintainer concurrency risk to preserve before any future staging repair; no foreign files were deleted.
Marker source_revision is repository HEAD, with generated-file checksums but no dirty generator/source digest; later acceptance should record exact dirty source manifest separately rather than imply the marker attests unchanged generator code.
Public helpers accept a Path directly while CLI normalizes/expands/resolves first; supported CLI safety is distinct from arbitrary internal unnormalized calls.
Manual counterpart genuinely reimports untouched exporter archives in fresh60-second-bounded subprocess and checks reopened actual computed [2,3,4] outputs for root/nested workflows, stronger than schema-only archive mocks.
Other tests distinguish idempotent unchanged fixture, modified refusal, marker-only cleanup admission and actual fixture grammar/build/failure branches; repeated preparation may be amortized only where independence and modification/refusal axes remain intact, with no measured savings asserted.
M1 remains open; native manual work remains final M5 and all repairs/diagnostics/runtime acceptance held.

### Complete-review checkpoint — root-batch-25

#### ROOT-F095 — P3 shortcut counterpart tests copied logic rather than the production listener

frontend/tests/unit/components/AppShortcut.test.ts defines ShortcutHost replicating the App handler/listener choreography and mounts only that local component.
It can remain green if production App's shortcut predicate or listener wiring changes or is removed; its comment explicitly admits the copy, so the current guarantee must stay a helper/recipe test rather than production App behavior.
Actual App source108/204/253 has the corresponding handler and paired mount/unmount, with no production defect inferred by this oracle gap alone.
Future suite synthesis should move a useful narrow shared handler under direct tests or exercise the actual App seam already available, retaining macOS versus desktop/plain-browser distinctions without a second copied implementation.
The fixture sets navigator.platform with Object.defineProperty and does not restore that descriptor; vi.restoreAllMocks restores spies, not that explicitly defined global property.
No intertest failure was executed; successful bodies explicitly unmount, while assertion failure skips that final retirement.

### Retained producer/selector judgments

package.json retains focused/quick/all-browser/coverage scripts and frozen-lock consumer dependencies; dependency ranges alone do not prove installed compatibility, and scripts/test remains authoritative orchestration.
Playwright config selects one worker with serial full-suite execution, separate Chromium/Firefox projects, explicit backend/frontend ports and non-reused dev servers, disposable runtime root and hot-reload fixture.
Serial execution protects shared workspace/hot-reload/worker fixture lifetimes; parallelizing this whole suite without per-worker runtime/identity isolation would be a contract change, not an assumed speed optimization.
Collection imports allocate a temporary root; source does not delete it, allowing artifacts/runtime investigation at the cost of retained temporary state; no measured storage/performance issue is claimed.
CI retries plus failOnFlakyTests expose flakiness, while local retries are zero; no fresh timing/browser result follows.
Campaign reporters derive stable per-project/file/title identities, exact one annotation reason and full manifest; Vitest audit runs at end, browser audit at begin retains failure status for end.
Browser reporter loops only projects present in collected tests; empty-project/no-suite refusal depends on runner/selector rather than an explicit reporter-wide selected-count assertion, a narrow validation boundary to preserve before describing this as independently fail-closed for every input.
No default false-green run was reproduced or claimed; normal runner zero-test behavior is not redefined here.
CampaignScope counterpart explicitly distinguishes exact partition, missing collection/manifest/annotation, reason drift/invalid reason, duplicate identities and zero selected input; useful fail-closed axes should remain rather than one broad smoke assertion.
The reports do not prove runtime execution or physical external prerequisites; campaign applicability classification remains reviewer-F027 and ordinary/default suite coverage stays separate.
M1 remains open; all implementation/test/native execution held.

### Complete-review checkpoint — B-batch-34

#### B-F184 — P2 source execution-log classifier retains the old engine module identity

`log_context._is_execution_record:21–33` attaches context to bioimageflow.node.* records and explicit Wetlands worker execution metadata, but its root BioImageFlow diagnostic branch requires record.name==bioimageflow and record.module==engine.
Current library engine/common.py owns that root logger and engine/scheduler.py emits actual skipped-node/disabled-target diagnostics through it.
Python LogRecord module for those current calls is scheduler, not engine; source-time factory freezes the active run, but execution_log_context_for_record discards that snapshot because the classifier returns false.
Those real diagnostic records therefore remain global despite being emitted inside the bound execution, weakening workflow/execution-scoped history.
Existing exact `test_bioimageflow_engine_diagnostic_carries_bound_execution_context` constructs a synthetic record whose pathname is `/package/bioimageflow/engine.py`, preserving the old module identity rather than exercising the actual scheduler call.
Bare BioImageFlow/environment lifecycle messages are deliberately global; do not attach every framework/environment record to the current run indiscriminately.
Future diagnostic should extend the existing fixture with actual current producer metadata or a bounded real producer and retain global nonexecution/environment records.
No worker/log action was executed here.
A separate low-priority public context-manager lifetime qualification: same-context nested binds are accepted, but the inner finally clears the global active context while the outer bind remains active because no depth/token stack exists.
Current ExecutionManager uses one outer bind, so this is direct nested-helper scope risk rather than a proven normal Run overlap or a call for a universal coordinator.

#### B-F185 — P2/P3 qualified thread-to-loop publication cleanup/backlog authority

ConnectionManager `_schedule:589–601` correctly closes an unused coroutine when its loop is None and consumes future exceptions through a dedicated internal logger.
For a stored loop that is already closed, or closes during scheduling, run_coroutine_threadsafe can raise RuntimeError; this branch neither closes the newly created coroutine nor degrades the sync publisher safely.
Ordinary app teardown sets the manager loop to None after removing log handlers, which mitigates the normal path; existing B015 early cleanup failure and direct retained publishers remain relevant qualifiers, not a claim every shutdown fails.
Logging bridge `_schedule_broadcast:114–140` has an explicit is_closed early check and catches the close-between-check-and-schedule RuntimeError, but also leaves the newly created coroutine unclosed on that race.
Its returned concurrent future is discarded, so broadcast failures are not surfaced by the ConnectionManager's existing future-diagnostic helper.
Both paths can schedule one loop callback/task per source event before the per-connection bounded queues are reached.
Those queues bound already-enqueued messages and isolate slow consumers, but do not themselves bound the cross-thread pending callback/future backlog while the event loop is blocked.
No sustained backlog, memory leak or measured performance cost was executed; this is a distinct producer/lifetime resource-bound risk, not a disproved default queue size.
Existing bridge `test_handler_does_not_crash_when_loop_closed` covers the early closed check, while sync publisher tests close a mocked scheduled coroutine themselves and do not distinguish a closed-loop scheduling race.
Future diagnostics should reuse exact sync/bridge fixtures for schedule rejection and teardown ownership; do not require blocking each worker on network sends or remove slow-consumer isolation.
Public max_queue_size<=0 also uses asyncio's intentional unbounded-queue semantics; reconcile supported configuration before treating that as an additional defect.

#### B-F186 — P2 source fresh WebSocket status omits retained intent; typed server union is incomplete

`_status_snapshot_payload:693–736` copies state/context/progress/node statuses/planned nodes but omits actual ExecutionStatus.mode, requested_nodes and retry_of_execution_id.
Frontend execution store adopts these fields when supplied; a fresh running/terminal reconnect therefore preserves execution identity but cannot restore the full selected/retry command intent from this snapshot.
The full frontend WebSocket counterpart review confirms no generic reconnect fetchStatus; only a provisional starting phase triggers status polling.
Already accepted same-context metadata can remain, and a starting poll is a conditional recovery path; those do not supply fresh running reconnect intent.
For a failed selected run, frontend retry validation uses requestedNodes if available; missing targets can change its early validation scope even though backend retry retains the original exact execution target authority.
No changed worker target or invalid processing was demonstrated.
Existing backend snapshot tests assert context/planned counts/full fixture payload without those intent fields, and the initial-provider test supplies a plain old fixture lacking them.
Future diagnostic should extend the existing fresh reconnect/status oracle with selected/retry intent while preserving terminal fences and exact backend retained retry identity.

The human-authored ServerMessage discriminated union also lacks actual execution_snapshot/execution_update, tool_source_changed, workflow_tree_changed and active_workflow_changed categories emitted by this manager.
This is five emitted event kinds; execution_snapshot and execution_update form the retained replacement family.
Models are strict extra-forbid but server emissions are constructed as raw dicts instead of validated through that union, so transport works while this advertised typed catalogue cannot validate the full current wire.
Environment request correlation remains absent in the actual backend event contract, corroborating B167 rather than creating a new request-ID defect.
Future contract reconciliation should unify the actual documented/generated catalogue and current emitters without inventing legacy compatibility behavior or narrowing essential event families.
No protocol message was sent in this audit.

#### B-F187 — P3 qualified node attribution relies on legacy/dotted logger text

Logging bridge `_extract_node_id:144–151` takes only the first dot-delimited suffix of bioimageflow.node.<name>.
Public library node names reject empty/slash but allow dots; a record for a legitimate dotted node ID is therefore attributed to a shortened different ID unless a separate naming/escaping contract supplies metadata.
Child logger suffix handling is intentional and must remain supported; the missing distinction is node ID versus logger child namespace.
The Wetlands attribution regex requires legacy `data/<node>/run` text and tracks a last parsed node per logger/channel/run context, with single-active-node fallback and exit-text clearing.
Modern library ProcessingTool context uses the private cache attempt staging directory as run_dir, not that legacy data/node/run layout.
Existing `test_wetlands_execute_path_preserves_nested_node_scope` supplies synthetic `Execute worker.run` legacy text and proves parsing that format, not actual current task-API row log attribution.
The bridge may legitimately leave ambiguous lifecycle records global; no wrong actual worker-node assignment or parallel schedule was executed.
Future diagnostic should inspect actual public worker log metadata and distinguish scoped/dotted nodes from true child logger names, preserving explicit source-time execution context and intentionally global environment logs.
Avoid inferring node authority from arbitrary message strings as a universal replacement for public metadata.


### Complete-review checkpoint — reviewer-batch-45

#### reviewer-F093 — oldest-drop counterpart proves a drop, not which entries were retained

P3 exact distinguishing-oracle candidate: test_queue_backpressure_drops_oldest1196–1221 blocks send_json, enqueues ten distinct progress messages into a three-entry queue, asserts only dropped_count>0 and disconnects.
An implementation dropping newly incoming messages could satisfy that assertion while violating the named oldest-drop behavior.
Preserve bounded queue/backpressure and independent fast consumers; the existing case can later use controlled send release and assert exact retained IDs/order, accounting for any explicitly held in-flight item.
This does not claim a production ordering bug or observed lost terminal event.

B-F186 counterpart corroboration: snapshot/context tests407–550 check execution ID, revision, planned nodes/name map and model-to-JSON serialization but no mode/requested_nodes/retry lineage; endpoint initial provider1317 supplies a plain dict lacking those fields.
The complete model/union tests verify their retained discriminants, not every manual manager event family.
The complete frontend reconnect test explicitly refuses generic REST status fetching; borrowed execution store has a genuine provisional-starting poll314, which is a conditional mitigation rather than fresh-running reconnect intent restoration.
The backend source owner keeps B186 and actual default no-await initial snapshot behavior: cancellation held by a monkeypatched snapshot method is not evidence of default pre-try sender leakage.
No duplicate backend source whole-file credit is taken.

Logging causal tests materially distinguish record-created execution A from later execution B, unattributed records from subsequently bound context, real Python thread propagation, framework/environment/thumbnail global logs and node-path fallback reset across execution identities.
Their Wetlands Execute path/stdio records are manually constructed legacy strings, not current real worker output or package/runtime compatibility evidence; B owns complete bridge/parser/source reconciliation.
Closed-loop noncrash tests do not assert newly created coroutine closure or event-future physical drain; source ownership findings remain B's.
Several unit queue tests rely on test-loop teardown instead of explicit manager disconnect, and fixed scheduling spins/small sleep polls measure only observed send completion. Optional fixture/controlled-barrier cleanup could make ownership and failure diagnosis clearer without expanding runtime lanes or claiming current leaks/flakiness.
Correction after complete current validation-model read: all_statuses exercises all six current NodeStatus values; cache_corrupt is a GraphValidationError type, not a seventh status. The earlier optional omission remark is withdrawn; no enum-coverage defect is established.
F027 is corroborated by deterministic remote-redaction-only campaign exclusion; default CI/full-suite selection remains independent and no blanket reclassification is authorized.
Global completeness and all repairs/runtime remain held.


### Complete-review checkpoint — reviewer-batch-46

#### reviewer-F094 — auto-scroll count trigger omits new messages at bounded capacity

P3 qualified source trigger gap: `LoggerPanel.vue:257–262` observes filteredEntries.length only, while borrowed logger store43,98–109 caps retained entries at5,000 and evicts from the head on append.
At capacity with the same visible count, a new message does not invoke programmatic scrollToBottom, including a longer/multiline replacement that may increase scroll height.
Actual browser anchoring/geometry may affect the result; this review has not reproduced lost following, scrolling or selection.
The existing DOM counterpart282 toggles the boolean only; existing browser logger source has actual native selection/copy assertions but no saturation-follow assertion found by targeted search.
Preserve bounded retained storage, user-paused/manual scrolling, full multiline text and local display filters; future smallest controlled append/scroll oracle belongs to existing component/browser seams, not a new broad lane.
Parent confirmed no known duplicate canonical issue.

Optional source-only cost/selection-stability candidate: visible rows466 use timestamp-plus-current-index keys.
Head eviction changes the index/key of nearly every retained distinct-timestamp row, so Vue can remove/recreate far more DOM than the one appended/evicted row; all5,000 retained visible entries are rendered rather than windowed.
No benchmark, savings, lost native selection or actual performance incident was executed.
If prioritized after M1, stable per-entry presentation identity/windowing should retain message order, selectable multiline content and complete filtered Copy logs; reducing the bounded data contract or hiding selectable data is not an approved optimization.
Optional pointer consistency: unlike the table resizer, Logger handles pointerup/cancel but not lostpointercapture; this is a small disposal/style-state candidate, not a reproduced width failure.

Copy logs captures currently displayed text before the await, preserves full level/local timestamp/current-origin label and multiline detail, and reports rejected/missing clipboard failure rather than false success.
Another workflow's retained node ID is not relabeled from the active graph; exact counterpart covers it.
The complete source uses local client filters with unfiltered WS ingestion, preserving later filter changes; no server filter replay is required for normal Logger behavior.
Mocks demonstrate flag/DOM/property mapping; no native selection/clipboard or real browser layout certification is inferred.
All assigned frozen source inputs are complete; current mutable docs and independent global completeness remain open before any fixes/runtime.

### Complete-review checkpoint — root-batch-26

### Existing B-F012 extension — bounded fixture retirement and failure ownership

Critical Save test holds the actual PUT before continuation, accepts another draft, activates a sibling and distinguishes savedA2/draftA3/siblingB9/titleB; no enclosing finally releases its gate or removes owned workflows after failed assertions.
Other critical race cases correctly release their gates and unroute in finally; delayed-feedback probe disposal below finally is bypassed after an assertion failure, with browser context teardown the eventual owner.
Node-width tests leave generated workflow cleanup outside a finally; no observed cross-test contamination or measured cost is asserted.
Failure/hot-reload cleanup swallowing and unchecked DELETE responses retain investigation artifacts but do not prove successful per-case retirement.
Any future optimization must preserve serial shared-runtime/hot-reload authority until actual isolation is introduced, and make fixture retirement precise before parallelism.

### Existing reviewer-F082/F083/F085 extension — error browser oracles

Error-handling failure uses the actual dev failure endpoint and real WebSocket envelope, exact workflow/draft/execution association and one unread-to-read log entry; it is transport/UI evidence rather than a failed Wetlands worker.
Cycle case obtains real stateless backend diagnostics but injects them into graph-sync state before asserting the banner; it does not prove gesture-to-persisted-cycle handling.
History toggle deliberately retains injected errors, corroborating the existing source/spec decision about read versus dismissal.
Go-to-node injects node-42 absent from the actual graph, clicks the button and asserts only error rows disappear: navigation/selection is not asserted.
This is precise corroboration of existing canonical error/navigation candidates, without a new duplicate test or ID.

### Retained exact file judgments and useful tests

app-shell44 checks actual Dockview menus, Tools visibility toggle and panels; full-stack28 independently checks real Vite-to-backend health plus initial console collection. Similar shell setup is a measurement/consolidation candidate, while the proxy readiness oracle remains distinct.
critical-operation-races975 uses real workflow-keyed IndexedDB after an actual transport-aborted PUT; asserts newer recovery contents, unchanged server/saved bytes, accepted recovery revision and rendered graph after reload.
Another case deletes browser fallback to prove accepted backend draft recovery, exercises actual Cancel, agent CAS, Discard409 without canvas/draft/sibling loss, Keep and reset to saved state. Its finally retires routes/owned workflows.
Run confirmation injects out_of_date into real validation and mocks execution202; after a newer actual draft change, it reasks and sends exact current revision. Immediate Run likewise verifies accepted revision and parameters, with no worker/PID credit.
Delayed feedback route.fetch commits the server PUT before holding client acknowledgement; observed DOM/status/error snapshots establish that different boundary from precommit transport refusal. Test evidence must retain that causal distinction.
hot-reload206 edits actual custom/package source bytes, receives actual watcher/registry transport and checks actual node/tool DOM updates; external editor is mocked, and the event listener accepts any tool_reload name. Exact node badge later mitigates that broad event oracle; tighten existing event identity only if needed, without inventing native or published package credit.
Package hot-reload finally restores exact original bytes, closes the separate socket and deletes owned workflow; custom source is intentionally owned and deleted rather than restored.
node-data-widths103 mocks query rows while exercising real browser geometry, pointer/keyboard sizing, sibling isolation, theme colors, saved widths, reload and reset. It is real layout/input persistence coverage, not real data/worker processing.
parameter-controls270 uses actual ProcessingParameterControls metadata and real canvas controls, typed enum/boolean/list edits, invalid list refusal with unchanged accepted draft revision, valid list validation, physical connectable pin and exact edge graph.
Actual Save200, another workflow, reopen and exact persisted/restored graph/list/checkbox controls distinguish persistence from a unit harness. Both owned workflows are deleted in finally; no compute/worker/native acceptance is inferred.
The existing meaningful cross-stack tests should remain until measured redundancy or failure-attribution evidence supports changes; this read-only audit added no tests or product fixes.


### Complete-review checkpoint — A-batch-42

### Complete contract judgment

Full base includes architectural runtime/deployment detection, accessibility/title, backend thread model and draft-backed full-state sync, tool-store paths/version/discovery/index/metadata/schema examples, all REST sections and normalized errors, workflow tree/incarnation/migration/draft/copy/dependencies, graph/interfaces/status/generated API semantics, node data/dynamic schemas, accepted execution/Clear/retained status/progress, settings/keyring/debug policy, filesystem/viewers/editor/datasets, complete WS/reconnect/hot reload/startup/shutdown, frontend layout/canvas/pins/status/panel/resource/results/logging/tree/run/viewer/errors/preferences/datasets, synchronization/recovery/undo, edge cases/shortcuts/API summary/security.
This base explicitly gives later v2/current distributed/viewer deltas precedence and OpenAPI complete surface priority; tables/examples do not become a second code generator or erase later contract overrides.
Draft versus saved artifact/private nested editor identities, accepted CAS/writer/validation frontier and exact root execution closure remain coherent with complete source authority map.
Whole selected graph compiles before diagnostics scoped to unrelated roots may be ignored; a partial/null workflow or unresolved selected target remains refusal, not permission to execute an ad-hoc pruned graph.
Immutable selected run/record/result provenance and unpinned absent-result.json compatibility remain separate; raw CSV/path fallback is not allowed for corrupt modern identity.
Ordinary Node Data/Clear affects latest projection/current status while historical successful run remains immutable; root-only Clear versus separately scoped nested admission remains explicit.
Viewer metadata/additions and all-row structural favorites use separate portable/local stores and native certification contract; new frozen captured guidance/form clauses agree with A38–41 qualified gaps.
Sources are recursively owned executable bytes, provenance not authority; catalog classes cannot replace carried qualified binding, supporting A001/A002 rather than silently redefining pins to current registry.
Hot reload promises same-size/timestamp current bytes, serialized unit reloading, inactive version preservation and noncatalog source notifications; A026/A149–153 source findings remain contradictions/qualification to reconcile, not acceptance by prose.

Frontend claims are judged against the actual caller tests, not blanket delivered status: stable handles/DataFrameTools constant-only, unexecuted provisional edits and contextual status, viewport controls, full tree no label identity, root-session close/discard/save capture, embedded source tool opening, separate filepicker/managed logical datasets, and keyboard menus have mapped full-source counterparts.
Existing A161 shared-catalog version selection conflicts with repeated workflow-specific one-version/package Use-in-workflow claim (§2.3/§3.4); retained pins must remain carried until explicit rebind, and common catalog refresh alone is not every node's version authority.
Header/body source-type distinction and ResourceSpec declaration floors are explicit, supporting already canonical A158 resource display omission and actual engine floor enforcement mitigation.
Settings deployment_mode is mutable in the illustrated live model but desktop capabilities must remain configured policy; ROOT-F002 owns actual authority bypass and configured trusted Python guard stays retained, not duplicated here.
HTTPSettings/OMERO/keyring/datasets/Clear/native implementation consequences stay root/B canonical and are not inferred solely from an illustrative schema.
Server security prose is localhost/no auth single-user, with future v3 deferred; real deployment binding origin/access policy is root-reviewed, not fresh native/network test evidence.

The base intentionally avoids a complete duplicate graph JSON transcription by referencing strict backend model/v2. Generated-only API aim explicitly acknowledges handwritten draft shape debt, A006 retained.
Other handwritten Settings/metadata/REST summaries still need synchronization; uninstall table documents optional version BODY while actual tools router uses query (B168 full route authority), and execution state field table omits stopping despite starting/stopping locks in whole MenuBar test/source. These exact stale examples extend existing API transcription debt A006 rather than new runtime contract claims.
API summary numbers repeat37, a low-priority navigation cleanup; generated OpenAPI remains the complete route authority.
Core resource requirements do not promise OS enforcement or result-key changes; scheduling is accepted graph policy rather than mutable application preference override.
Narrative says validation via Pydantic but ordinary Core IOModel declarations are not Pydantic models, reviewer-F038 source-authoring/model guidance owns that broader wording mismatch.
No historical or illustrative docs statement supplies package/tool/native runtime pass evidence.

#### A-F178 — Low documentation/source drift, workflow dependency dialog advertises no installation despite implemented install-all

Frozen v1 §2.4.2 line428 says current dependency dialog does not install missing packages, and §5.2 line1680 says installing an absent required version remains a separate Tools Panel action.
Complete frozen MenuBar760–830 implements installMissingDependencies, filters local custom tools, installs each exact missing package via tools installer, continues partial failures, refreshes catalog/workflow diagnostics and retains errors; template1340 handles dialog install-all.
Complete mounted counterpart selectors `installs every exact missing dependency and refreshes diagnostics`, `never sends workflow-local custom tools to the package installer`, and `continues bulk installation after one package fails and keeps diagnostics open` distinguish this actual supported path.
Thus human base description is inaccurate and obscures a valid dependency recovery route; it is not a missing implementation or a reason to remove the explicit action.
Existing native/pip/install validation limitations and capture/partial failure findings remain; mocks do not certify published packages/network success.
Future documentation reconciliation must describe explicit exact package installs and partial failures without implying passive import/viewer checks automatically install, or incorrectly treating __custom__ local sources as installable dependencies.
No test execution/repair or same-source main full credit here; reviewer notified for duplicate-ID reconciliation.

### Existing reviewer-F038 extension — source declaration example is missing required row consumption

v1 §2.4.1 Python CellposeSegmenter example imports ProcessingTool/IOModel and defines process_row, but neither imports RowConsumption nor declares row_consumption.
Its prose elsewhere declares mapped/collective required metadata, and the complete Core ProcessingTool subclass validator rejects a concrete row method without a RowConsumption value; illustrative undefined cellpose_env/ellipsis does not satisfy that mandatory declaration.
Corrected authoring skeleton must state mapped/collective explicitly, retain plain IOModel field declaration semantics and avoid misleading Pydantic validation advice.
The adjacent environment wire example uses legacy conda/pip lists rather than canonical requirement mappings; targeted cross-owner reviewer reconciliation pending for that precise grammar clause, so it is recorded as a qualified stale-example candidate rather than a fresh executed constructor failure.
Reviewer owns F038 and was notified; no second canonical ID or duplicated source full credit.

### Coverage

326reviewed+8classified/354,20pending main platform:9E2E browser journey files, docs/agents/workflow-editing,8historical campaign controls and2main specifications.
Next dependency-ordered browser journeys then current viewer/v2 and historical evidence/process records; full gate remains open and neither WIP is committed/released.

Reviewer reconciliation after save: reviewer confirms no existing dependency-dialog-install contradiction ID, retains A178, and accepts F038 mandatory row-consumption/dependency-map example corroboration without a new canonical ID.
This is source/documentation confirmation, not executed constructor or package validation.


### Complete-review checkpoint — A-batch-43

### Full-file judgment and test oracle boundaries

Viewport test uses actual named folder workflow/API graph plus setLastOpenedWorkflow startup reload rather than a fabricated rendered canvas.
Small and8000extent cases measure actual DOM matrix zoom, every rendered node within canvas, centered bounding extent and decoded SVG fragment points to that canvas pattern; RunSelected visibly present.
This supports exact framing/grid identity including slash-containing path, not minimum5percent scroll gesture or backend processing/PID.
Seed POST status is not checked; folder created before try can leak if subsequent setup fails, and cleanup delete responses are unchecked/live page remains, extending qualified A101 fixture lifecycle debt, not a new user-data runtime defect.
Geometry cases are distinct small/large boundary obligations; do not collapse merely because bodies share code.

Editable-import test builds real workflow-local DataFrame source, exports through actual backend, imports with name override, actually GUI opens imported workflow and clicks node-addressed editor button.
Opening uses external_editor='true', so HTTP exact imported file identity is proved but no real editor readiness/focus/native window.
Physical Run action and distinct expected CSV rows2/3/4 then21/22/23 demonstrate actual source-edit result at Direct/DataFrame boundary when executed; do not confuse saved config with worker isolation/PID.
Read checks original source remainedn+1; parent prepare-embedding actually copies edited imported bundle into new owner and accepted draft has returned source id; editing parent copied file leaves imported original unchanged.
Parent embedded edited source is not executed in this test, so source independence bytes are not nested worker result proof.
Synthetic DataTransfer dispatches drop, exercising real drop handler/backend rather than pointer drag source gesture.
Out-of-date Continue is dispatched through HTMLButtonElement.click inside polling to avoid a fading dialog, not physical Playwright user actionability/keyboard acceptance; report that separate from real main Run click.
Changed second CSV values prevent already-existing first output satisfying the edit oracle; immutable storage result/PID remains separate acceptance.
finally navigates blank, restores external editor and deletes owned workflows, with unchecked cleanup status; retain A026 hot reload/helper/pyc qualifications without claiming this narrow single-file edit proves every reload source-axis.

Imported layout starts with overlapping root/child positions, actual portable API export/import twice and exact recursive deterministic coordinate map, then rendered no-overlap/edge-count asserts and physical node drag.
Waits accepted root draft PUT, saved other graph remains byte-structurally same coordinate map, actual nested canvas visibility/separation, root Save and reload preserve user edited layout and sibling remains untouched.
It distinguishes one-time materialization from reflow and graph identity scope; source export/import is API fixture not GUI archive chooser gesture, which is acceptable for this layout seam.
No compute/cache/native claims. finally blank page plus owned delete; nested snapshot cleanup delegates actual server workflow deletion.
This layout GUI persists the coordinate authority and complements backend deterministic layout tests; repeated exact map is cross-layer evidence, not blindly redundant text.

Migration fixture writes actual saved document schema1 bytes inside explicitly isolated E2E_ROOT, leaving current workflow exact bytes as unrelated control.
Actual scan planId, UI startup defer/unavailable tree/currentOpen, then GUI confirmation verifies exact returned backup path/content, no unrelated rewrite, schema2 load and reload identity.
This is real saved-file migration UI proof when run, not typed mock; it does not cover accepted root draft baseline/nested snapshot transaction, stale preview source, crash journal or fsync ordering (separate complete backend migration counterparts).
No finally enclosing mutation/cleanup, so midassertion failure leaves legacy/backup fixture workflow and state; A101 retained. Tests do not remove backups, intentionally durable evidence but per-run root owns eventual retirement.

Graph recovery seeds actual available dev tools, stateless validates a positional complete-DataFrame graph, persists empty saved workflow, writes newer workflow-keyed IndexedDB recovery and reloads.
Asserts exact restored node labels/IDs/one exact edge and finite visible SVG path plus dirty title.
This proves recovery rendering for one existing workflow rather than old global key; no second workflow negative isolation, accepted durable draft CAS write or true browser interruption is asserted.
Manual legacy GraphState TypeScript shape is fixture-only, not new production authority; backend normalization is explicit current supported input.
Delete cleanup is end-only/no finally and live page; A101 retained.
A012 extension below distinguishes fabricated dev metadata versus canonical introspection, not a current false test failure.

Creation complete cases check actual startup shell/search/create visibility, fake pywebview settings404 fallback and absent Datasets, owned workflow grid/no minimap, no-workflow nonpersistent placeholder/Open dialog/New cancel/noimplicitPOST then actual single creation and reload without duplicatePOST, create-tool modal controls, and full Manage inventory independent of catalog search plus declared managed environment location.
Fake native API only establishes frontend desktop fallback; no native filesystem/browser control or installer acceptance.
No-workflow deletes all runtime workflows intentionally under suite-owned isolated backend root; do not claim production/user workspace safety or preserve prior unrelated fixture content. Subsequent named create cleanup is finally.
Simple Tools presence/Create cancel/grid cases overlap unit/smoke surfaces, but exact browser theme/docking/modal wiring may retain value; measure selection/runtime before future consolidation, no measured speed gain claimed.
Nonsense search oracle currently wrong, new A179.

#### A-F179 — Low/Medium test oracle defect, empty catalog search checks a nonexistent old TreeTable surface

workflow-creation.spec.ts `search filters tool list to empty on nonsense query` fills actual tool-search but asserts `.p-treetable-tbody .tool-name-cell` count0.
Complete current ToolsPanel everyday catalog renders div.tool-list-item with tool-item-* test ids and span.tool-list-name; TreeTable is only separate unopened Manage dialog, and current template does not use tool-name-cell for those catalog rows.
The asserted selector can already have zero matches before the search is applied, so regression leaving catalog tools visible still satisfies this test.
Future correction should compare a positively populated actual catalog before search and no actual tool-item rows after, while retaining empty state/query behavior and independent Manage inventory contract.
No execution or failing UI diagnosis; exact source/test oracle mismatch is statically established. Do not grow duplicate journey solely to add count.

### Existing A-F012 extension — recovery test canonizes manually seeded DataFrame column connectability

Graph persistence fetchRecoveryTools asserts IncrementNumbers (actual DataFrameTool) input number.connectable='by_default'.
Targeted root-owned dev.py259–281 manually creates that metadata; seed476–489 directly registry.register_tool rather than public serialize_input_schema, so the assertion can pass despite public schema._input_connectable97–103 always returning NEVER for DataFrameTool.
Thus this is fabricated metadata contract drift/negative-oracle omission, not an inevitable current serializer-induced test failure or evidence canonical DataFrame field pins work.
The actual recovery graph connects positionally, which is valid independent of the unused number metadata; source transform ignores its declared number constant and operates upstream rows.
Retain real typed tool classes and public metadata authority; future fixture reconciliation should not reintroduce forbidden DataFrame column pins merely to satisfy an old assertion.
Root notified; no dev full-file credit or duplicate canonical defect here.

### Coverage

332reviewed+8classified/354,14pending main:3large browser files (agentdraft504/canvas1377/crud506), docs agent361,8historical records and2current specs.
Next full browser/lifecycle counterparts; full audit and all repairs remain held.


### Complete-review checkpoint — A-batch-44

### Full-file judgments and retained test contracts

Agent sync wraps native WebSocket only to observe actual server message JSON/open count; performs real backend structured draft operation against expected revision0, checks correct workflow/agent attributed notice and exact visible node with no main-frame navigation or conflict.
This proves clean active canvas live update rather than reload; API operation is agent-boundary transport, not actual MCP client/stdio authorization/external active context operation.
Setup errors outside try can leave named fixtures; finally delete helper swallows request errors and does not blank live page, inherited A101 qualified cleanup debt.

Parameterized agent-copy variants manually mark actual canvas UI dirty to generate a conflict against a real agent draft write; one exercises Keep first then a later agent revision, the other direct copy.
Click actual conflict copy button, check real PATCH/saved copy equals exact agent graph plus new root name/display, original accepted draft remains exact same revision/graph and title stays original.
This is a precise accepted-agent versus currently edited-canvas distinction; manually dirtying an unchanged graph does not certify preservation of a complex independently edited local graph.
Cleanup assumes first free _agent_2; complete source helper1065 starts suffix2 and unique base prevents ordinary collisions, so not asserted universally wrong, but capture returned copy identity would be more robust if fixture assumptions change.
No fresh failure or additional canonical finding for that conditional cleanup debt.

Recursive copy test strengthens the same ownership boundary with actual local source file authoring/export/import twice for SAME CLASS NAME with different source hashes and prepared embedding destination ownership.
Actual agent graph remains unsaved and includes root and child bundle; copy graph exact equality, source manifest owned IDs, four distinct file paths and exact bytes, original saved document bytes and accepted draft revision unchanged provide real storage oracles when run.
Edits copied child only, opens/reloads copy even with later unrelated original recovery timestamp, executes actual Run202/completion and checks UI data-table requests root versus embedded scoped node and exact root2/3/4 versus child41/42/43 rows.
Original documents/source bytes/draft remain unchanged and no original latest output directory appears, distinguishing source aliasing or wrong runtime context from mere successful serialization.
DataFrameTool Direct fixture is actual compute/owned-source output evidence, not Wetlands worker/PID/environment isolation; public archive is actual API export/import but not GUI archive chooser or published-package compatibility.
Synthetic mark-dirty and injected future recovery are deliberate controlled setup; real conflict UI/Run/NodeData gestures remain admitted user consumers.
Result projection helper asserts scoped node but does not assert every workflow/resultkey/record field; exact output divergence and original-no-results controls substantially constrain wrong-context false positives, without claiming full immutable result provenance acceptance.
finally navigates blank and deletes captured actual copyName plus allownedsource workflows when page survives; if page alreadyclosed server cleanup is skipped, eventual fixture root remains harness-owned A101 qualification.

CRUD describe mode serial means early failure suppresses later cases, useful state isolation assumption but limits diagnostic failure independence; root owns suite selection/runtime reconciliation.
Helpers derive ids separately from actual UI and use normalized row testids; complete A170 collisions remain possible but generated unique ASCII cases do not distinguish them.
Real critical New dialog tests generated-name/API201/title/list, and invalid/occupied Create/SaveAs test exact409 plus retained input/dialog suggestion/cancel/source saved+accepted clean draft/occupied/list unchanged before and after reload.
Those are strong no-mutation oracles beyond disabled submit spies; no delayed sibling/unmount invocation owner is introduced, so A168 remains untested in these cases.
Collision import obtains actual portable export, actual filechooser uploads archive, rename dialog chooses raw path/name, actual title/tab/panel/reload and original display control verify root rename persistence rather than only returned info.
It does not assert nested-name/source-bundle/hash/viewer snapshot integrity; separate backend/library and frozen import tests own those.

SaveAs actually creates catalog node via doubleclick, waits accepted draft, saves, runs real deterministic SeedNumbers and checks exact original rows, then copies into separate root with same node structural id but different graph artifact name/hash and no copied NodeData404.
Edits copied node presentation through actual NodePanel Enter, accepted copy draft+Save, reopens base and verifies original graph+retained result available, reloads/reopens copy and checks both saved/draft/current graphs independent.
Result before copy is actual Direct seed compute rather than static seeded output, but no worker/PID; cached source preservation only checks later response availability rather than repeated exact rows after copy (initial exact values + graph unchanged mitigate).
It combines content/results independence and selection/reload in one coherent journey; split only after measured failure attribution/redundancy benefit, not automatic proliferation.

Delete dialog test Cancel preserves mounted/source, then explicit confirm and404; its title `clears server file` uses HTTP absence not direct filesystem bytes.
A/B lifecycle case observes DELETE query expected_identity_generation equals captured actual backend generation, exact A tab disappears, B remains selected+saved unchanged, reload has noA/source404 and no implicit creation POST.
Last workflow case removes all suite-owned workflows, creates one then real Delete, checks same generation query, nonpersistent placeholder/no tabs/listempty, reload source AND draft404/noPOST.
These prove normal generation-bound cleanup, not held dialog A→B replacement/raced same-ID incarnation or postcommit local cleanup failure (separate units/source findings).
Several CRUD creation/delete cases omit finally; failure can retain runtime fixture data; helper swallows errors/status and live page cleanup qualification A101/F163 retained.
No root/source lifecycle defect newly established beyond existing canonical IDs, and no browser pass executed here.

### Agent cookbook full judgment

The361line cookbook clearly distinguishes operating an active workspace through MCP from editing this repository's product source.
Requires capabilities/context/compact describe and tool metadata before graph mutation, stable structural IDs not inferred labels, coherent topology/layout plan, nonreflow existing user layout, complete batch max10 and only advertised operation types, layout-only nested scope unless broader capability supported, and revision refresh/reapply-intended-change after conflicts.
Public inputs/outputs keep immutable port ids, explicit null clear flags preserve nullable metadata, node deletion delegates backend referential cleanup, execution lock is authoritative, and explicit management/delete/source-code intent is required.
Duplicate says saved workflow/tools rather than current unsaved draft, matching complete owned copy APIs; active-workflow deletion refusal matches targeted MCP315–334 and capability117 advertised management/batch facts.
Examples are illustrative tool names/typed port schemas, not acceptance fixtures; author must derive real fields/types from describe metadata, so legacy illustrative LabelImage spelling should not silently become actual canonical metadata or guessed graph schema.
MCP route wrappers/types/draft operations remain backend authority; cookbook does not justify direct saved JSON/source editing for ordinary workflow operations or expose read-only platform-source reference as executable authoring target.
No novel blocking contradiction identified in these operating constraints; prior A source-bound/schema/identity findings and root MCP context qualifications remain, not hidden by documentation.
No actual MCP interaction or authorization mutation attempted during this read-only audit.

### Coverage

335reviewed+8classified/354,11pending main:canvas-interactions1377,8historical controls and2currentspecs.
Next complete canvas gesture/persistence cases and normative deltas, then full historical records; gate remains open and no repair plan release.


### Complete-review checkpoint — A-batch-45

### Complete fixture and gesture judgment

Full file includes metadata/seed/workflow helpers, actual drag/body handles, complete CSV reference parser, projection request/response correlation, suite setup/teardown and every catalog/graph/run/data/width/history scenario.
SeedNumbers identity/type/schema is explicitly inspected; UI creates independent named workflow each case, real sourcecatalog exactrow testids/doubleclick/documentation controls and physical drag/handle connections exercise actual canvas rather than directly invoking its mutation method.
Some waiters match any accepted draft/query response; subsequent named currentDraft graph/exact visible or source request assertions constrain false completion, but those waiters alone are not proof the intended gesture was accepted.
Serial describe suppresses remaining tests after earlier failure; root owns future runtime/failure-attribution selection audit, no automatic parallelization proposal.
AfterEach attaches screenshot/ARIA before API delete on failure; a alreadyclosed/crashed page or attach error can prevent that cleanup, while delete failures/status are swallowed and page is not retired first, existing A101/F163 bounded harness debt.
All mutations here target suite-owned isolated runtime, not production user-workspace/native actions.

Catalog click toggles actual documentation twice with no nodes, doubleclick creates one actual accepted draft node and checks unchanged viewport transform, real header/output/body pins, selected NodePanel/package and validated backend graph.
Catalog failed-write case intercepts only first PUT500 BEFORE server application, checks local exactly one node plus visible retry/error and backend baseline graph/revision unchanged, then actual retry200 increments exactlyonce, retains exact node id/valid graph and reload matches.
This is meaningful client persistence failure/retry evidence; it does not simulate ambiguous postcommit response loss or justify replaying a possibly accepted mutation.
Separate physical catalog drag asserts near exact target graph coordinates, an independent input gesture contract rather than duplicate doubleclick coverage.

Dynamic Generate→CrossJoin uses actual packages/UI parameter list+column edits and DataFrame handle gestures, checks resolved sensitivity pin, accepted valid edge/config and actual202/completion+exact resulting values0.1/0.2.
It writes execution policy through API as fixture setup; graph configwetlands is not worker execution proof, because every tool in this chain is actual DataFrameTool and effective platform engine selects Direct.
Full workflow journey uses actual SeedNumbers/IncrementNumbers menu/catalog/parameter/edge/run/NodeData/Save/Open lifecycle.
It checks immutable platform execution record backend=direct/workflow/draft revision against actual accepted Run request, then exact eachnumber/label/increment row, saved graph+parameters+edge and reopened accepted graph equality after switch.
This provides actual graph/compute/result context, not configuration-only execution evidence.
IncrementNumbers ignores its number argument and transforms upstream numbers; accepting parameter10 while resulting2/3/4 demonstrates persistence of that parameter, not semantic influence of it on compute. A012 dev-schema/fixture limitation retained.
No published-package certification, worker/PID/Core-only source module acceptance or native viewer inferred.

ControlledDirect failure actually executes chosen fail parameter, checks accepted exactdraft revision/context/backend, failed target/no publishedtarget404, successful upstream exact rows/status and detailed failure banner.
Changing parameter tofalse accepts nextrevision, second distinct execution id/context, exact complete success rows and reload retained status/result/currentgraph proves recovery without partial target publication.
Upstream immutable attempt reuse/cache identity/PID are not asserted just because upstream output remains; no stronger cache/worker credit.
This is an intentionally separate failure journey from happy graph/persistence and data query journeys; preserve causal failure isolation before any measured consolidation.

Filter/sort/page/CSV case actually runs ResultTableFixture, not arbitrary seeded dataframe; tests exact starts_with filter request/count/chip, two sort transitions and exact sorted values/index/source_rows, physical paginator sizes/next/directEnter and allfiltered CSV bytes parsed into expected rows/header.
Expected deterministic60row reference is independently derived from simple declared formula, so source consumer response and rendered rows/CSV all constrain ordering/index/filter false positives.
Reference CSV parser supports escaped quotes/newlines/CRLF, but selected fixture has uncomplicated strings; this case does not independently certify every CSV escaping edge (backend tests own those).
Numeric range incomplete Apply remains disabled with60rows, secondbound enables and actual filter exactsource indexes, Clear restores full60; this verifies rejection/recovery with no false data disappearance.
First/last paging, every nullable/filtertype, malformed backend responses and stale result projection are not all tested here; B source/counterpart coverage owns those omissions.

Merged/stacked journey actually runs related Seed+Increment and independent60row tool; source exactdata/absolute_rows controls, real Shiftselection obtains backend workflow/source labels/merged columns and exact index provider alignment, checks visible values and path label.
Keyboard separator5Right produces explicit50px width and one persisted key; independent selection checks real fallback and exact stacked2/3columns+3/60rows, then reselection/reload restores merged width and stackedrows, Reset returns original content width/deletesmanualkey.
Second identity journey intentionally reuses the SAME node id in another workflow with DIFFERENT source schema, asserts widths donotleak and workflow/source key contains expectedidentities, actual distinctfilter/sort response/rows, restoresfirst width/no secondfilters and resets onlyfirstkey while secondkey remains.
Reload/reopensecond retains explicitsecond40px width but transient filter/sort resets; exact ascending rows/request confirms temporary query state correctly distinguished from persisted widths.
These cover actual workflow/table/source identity rather than merely samepage dimensions; inherited root generation versus path-only width keys remains respective source-owner qualification and not proved by this no-delete-recreate case.
No user resize cancellation/hiddenfontmeasurement/pointerdrag assertion here; separate column-width source/tests remain authoritative.

Undo reloadbaseline test saves real twoGenerate nodes, physically moves each with accepted PUT wait, real CtrlZ twice compares first/second renderedpositions to loadedbaseline and nodecount preserved.
Redo is onlycount2 after two shortcuts, new A180 below; backend accepted undo draft content/revision and full metadata/control-field integrity are not asserted by DOMpositions alone.
Physical DOM positions meaningful through same viewport; helper10px tolerance is explicit no exactgraph-coordinate claim.
No newly established production defect; identified shortcomings are exact test oracle/lifecycle scope, not reason to replace actual strong result/persistence checks with mocks.

#### A-F180 — Low test oracle gap, redo shortcuts can no-op without failing the undo journey

`repeated undo returns moved nodes to the loaded workflow baseline` physically moves two nodes, asserts positions after Undo, then issues CtrlShiftZ twice and asserts only nodecount2 (canvas-interactions1359–1375).
A redo regression that leaves both nodes at the undo baseline still satisfies final assertion because node creation/deletion was never the history action.
The test title accurately promises Undo, so this is an unasserted adjacent gesture/coverage gap rather than evidence the claimed Undo contract is false.
Future bounded repair should record moved graph/positions and assert actual redo positions or remove unsupported incidental redo-credit claims; reuse this currentjourney rather than add another lengthy run/data fixture.
No browser/test execution or production repair. Full history source already inspected; this report does not claim a failing redo implementation.

### Coverage

336reviewed+8classified/354,10pending main:8historical campaign records and current viewer566/v2spec486.
Next complete normative current deltas then historical evidence/progress/process controls; no whole audit closure or repairs until root final gate.


### Complete-review checkpoint — B-batch-35

#### B-F188 — P3 source Clear response differs from authoritative no-output projection

Execution `commit_node_cache_clear:1769–1778` first computes refreshed statuses with the retained-latest predicate, then rewrites every downstream unexecuted status to out_of_date unconditionally.
For a never-run chain with no retained downstream output, the Clear response therefore marks dependents out of date while later authoritative draft GET reports them unexecuted.
The context explicitly documents the authoritative GET distinction: pending upstream is out of date only with a retained latest output.
`test_clear_derives_downstream_statuses_from_submitted_graph` and `test_clear_propagates_out_of_date_to_downstream` use empty temporary storage and assert the forced response status.
`test_draft_status_before_any_run_has_no_false_downstream_staleness` calls Clear on a never-run chain then asserts the restarted/read projection is unexecuted, but never compares the Clear response.
The frontend cache-clear merge consumes that immediate response, so it can temporarily advertise rebuild/out-of-date status and prompt for rebuilding never-produced outputs before a subsequent authoritative refresh changes it.
This is a two-projection consistency/design seam, not a corrupted record, wrong worker target or observed data loss.
Existing retained downstream output must still remain deliberately out of date after clearing its upstream; no blanket conversion of all downstream states to unexecuted is proposed.
Future bounded diagnostic should extend the existing before-any-run test to compare immediate Clear and authoritative read, then retain the existing executed-chain/historical-output case to establish intended consistency.
No new diagnostic was executed.

#### B-F189 — P3 qualified suite/oracle precision for cache parity and subprocess integration

Cache parity's full207-line module accurately checks validator projection against cache seeded by actual Direct compute under both dev modes.
Its prose says cached flags match what the engine would observe, but the tests never execute the second unchanged/changed workflow or assert a tool call counter; they establish successful seed→plan projection rather than actual second dispatch avoidance/recompute.
Existing runtime_cache counter/throwing/selected-record tests and real API two-run flags remain complementary stronger execution oracles, so this is a precision/consolidation candidate rather than a demonstrated cache defect or demand for duplicate broad successful journeys.
The exact selectors are `test_seeded_cache_reports_executed`, `test_constant_change_invalidates_downstream`, and `test_unrelated_node_stays_cached`.
Future suite reconciliation should either label the projection scope accurately or add the missing execution distinction to an existing meaningful fixture only when it closes an uncovered invariant.
No measured runtime gain or test deletion recommendation follows from line count or similar setup.

The761-line real-execution module has only an anyio module marker, despite `test_draft_status_after_clear_survives_backend_restart` creating a new subprocess/app with full library imports.
That subprocess has check=True/captured output but no timeout, extending B012's bounded-failure/cleanup debt with an exact selector.
This process/reopen case is a concrete candidate for integration lane classification, while small local DataFrame/cache/compile-race cases need individual applicability judgments; do not blanket move the whole module based on its filename.
Existing ASGITransport app callers omit lifespan, so API authority/cache tests are meaningful but do not establish startup worker/service teardown (B011 qualification).
No timing cost or lane speedup was measured here; campaign applicability and ordinary default/full execution remain separate.

### Sound structures and evidence distinctions

Real DataFrame tests run actual host-side transform/cache persistence through library-backed ExecutionManager and routes, rather than mocked successful results.
Exact source/offset values, row indexes and shifted outputs, cached flags, error/traceback propagation and context identity distinguish those boundaries.
The selected valid branch retains a missing unrelated tool and asserts that unrelated latest output is absent, strongly distinguishing pruning from silently making the whole graph valid.
Accepted parameter change uses the same source/offset IDs and actual changed data, unlike the confounded class/path miss fixtures root separately reviewed.
Draft projection compile-race tests inject intervening accepted revision, same-ID recreation and storage relocation and require a retried correct authority.
Reopening in a separate OS process establishes persisted draft/cache projection independently of the prior live execution service; no lifespan/native claim is made.
Autouse fixture resets active Workflow context before/after, but is not shared-manager/log-handler lifespan teardown.

Clear tests seed a public canonical current selection and require its removal, not a legacy directory-name check.
Corruption test alters logical dataframe content while updating transport digest, proving logical corruption rather than only transport-byte mismatch.
It asserts safely identified corrupt immutable record quarantine preserves exact corrupt bytes, and historical/sibling/other-workflow healthy records and selections remain isolated.
Historical current selections for the cleared node are invalidated deliberately while immutable historical record values remain readable.
Invalid graph/missing tool, semantic bad parameter and compiler failure tests retain the preexisting current selection before any effects.
Unknown nodes and empty cache clearing are idempotent, explicit selected roots take priority over downstream status, and positional/column dependency axes are distinct.
The tests do not coordinate an external selection advance during invalidate; A-F030 remains the existing qualified current-pointer race authority.

Stale environment test is explicitly external/integration/serial/slow and uses `run_worker`'s actual Workflow.compute(engine=external adapter) dispatch.
It asserts exact three values and owned report contents, worker PID distinct from orchestrator, one worker for mapped rows, actual public manager recipe/generation inventory, injected Pixi install failure77, no retained retired workers, successful retry and later matching reuse.
The injected forwarder failure is labeled fault injection through an actual public provisioning operation; it is not an invented install success.
Unrelated managed codeserver inventory and an explicitly foreign/unmanaged directory's exact bytes remain unchanged, with refused adoption.
Restart closes the prior manager, checks no workers/prior PID, launches a new OS process with180second timeout, and compares the preserved ready generation/digest against a new worker PID.
Normal matching reuse and stale recipe replacement are established; force-rebuilding an already matching generation remains B001's held T1 defect and plan-only repair boundary.
No nonce/private-directory deletion or force contract weakening is introduced.
Finally cleanup calls shutdown_all before singleton reset; if the former raises, reset is bypassed, an existing B012 cleanup-chain qualification rather than newly executed contamination.
Tests' actual worker and public manager evidence remains distinct from GUI progress, desktop/native viewing or complete package compatibility certification.

### Next group

Remaining execution/cancellation/failure/nested/export/stale E2E files, public launcher input and cancellation counterparts, then frozen T1/spec/installed-seam exact content.
All57 pending inputs remain open; read-only review and repair/test freeze continue.

### Complete-review checkpoint — root-batch-27

### Existing A-F180 reconciliation — actual mixed history has distinguishing redo coverage

The canvas moved-position journey's incidental redo assertion remains weak for position history, but this separate everyday suite explicitly verifies accepted draft nodes, edges, constants and exact revisions through Undo and Redo.
Bulk enabled-state Undo/Redo also distinguishes both actual accepted booleans; atomic deletion restores exact baseline graph and then redone empty nodes/edges with incremented revision.
Therefore do not claim global redo coverage is absent, add another broad fixture or erase these meaningful assertions; A180 is a bounded moved-position oracle improvement only.
Workflow switch test deliberately closes/saves then reopens roots and asserts history reset/no accepted PUT/unchanged draft. It does not establish history retention for concurrently open independent canvases, which belongs to the separate source/session tests.

### Existing B-F188 reconciliation — downstream stale status here is appropriate for retained outputs

Actual first Direct compute produces source/target rows; clearing only upstream preserves readable retained target rows and graph/revision while source404 and dependent out_of_date survive reload.
GUI rebuild explicitly lists target, accepted rerun keeps exact draft revision and restores exact rows/statuses.
This is the retained-output case that must remain when resolving the never-run immediate Clear versus authoritative GET distinction; blanket conversion to unexecuted would weaken the supported feature.

### Retained full-file judgments and qualified fixture debt

Helpers inspect actual SeedNumbers/IncrementNumbers metadata, create/statelessly validate/save/open real graphs and poll accepted drafts; legacy schema1 is supported fixture normalization, not new source emission.
Physical click/shift-click/box selection, catalog drag, dataframe disconnect/reconnect and column pin gestures operate actual browser controls; accepted draft assertions preserve structural IDs/edge semantics and reject column-to-DataFrame no-op with unchanged graph/revision after600ms debounce observation.
Bulk-enable when already enabled verifies no history entry, no accepted write and unchanged revision/graph; cancellation of destructive actions likewise checks exact unchanged server state, not merely dialog closure.
Clear refused after an injected precommit draft500 sends zero Clear requests and preserves current output and accepted graph. It does not simulate ambiguous accepted-then-response-lost mutation.
Rename uses Unicode display label while retaining immutable node/edge identity; duplicate label refusal preserves exact accepted revision/edge and reload. Collapse/enabled persisted booleans remain separate UI fields.
Failed pointer edge writes expose provisional local graph plus baseline accepted server graph; Retry accepts each exactlyonce, then actual Undo/Redo/reload asserts exact edge identity. Connected column-input failure separately checks label-to-pin behavior against typed image metadata; no image engine runs.
Corruption journey physically alters the actual selected parquet/CSV, checks cache_corrupt diagnostic and409 query/CSV, API and GUI Run refusal, unchanged immutable run views and retained status.
Actual GUI Clear request carries nodes/workflow/revision; quarantine exact corrupt bytes survive, healthy target/sibling parquet and historical run/sibling metadata remain byte-equal, reload clears refusal, rerun creates distinct run identity with exact rows while history/sibling stay unchanged.
Transport-digest corruption here complements the backend logical-corruption case; neither replaces the other. Prefix startsWith in test selectedRecord is a fixture assertion, not proof of production path containment for sibling prefixes.
These actual Direct compute/record/file checks do not claim Wetlands worker/PID, published package certification or native desktop execution.
AfterEach DELETE suppresses failures and does not blank the live page; setup for second/inactive roots occurs before try, so an early setup failure can leave owned fixture state. B012 remains qualified harness retirement debt, with no newly executed contamination or measured timing savings.
Root's complete owned frozen source/test slice is now read; other owners and mutable audit controls remain open, followed by synthesis and independent completeness gate.

### Complete-review checkpoint — A-batch-46

### Current napari specification judgment

The complete ten-section contract separates library/Core portable output requirements from local environment registrations, candidate evaluation, structural preferences and native process ownership.
Carried v2 snapshots including explicit unknown declarations are authoritative independent of live catalog metadata; legacy normalization does not invent viewer declarations, local installation/default/favorite state remains absent from graph/archive/cache identities.
Actual library serializer/manifests and exact retained artifact/table/resolver boundaries already fully reviewed supply corresponding source evidence; captured declaration/provider identity is sound, while carried executable dispatch/resource precedence remains A001/A002 and is not made correct merely by a coherent viewer manifest.
Managed recipes use public Wetlands environment contracts and registration UUID/revision identity rather than private folder guessing; inventory/readiness is passive and does not provision, launch or favorite implicitly.
Candidate selection preserves independent output requirements, deterministic ranking and registered capability validation, with refusal/retry/foreground explicit launch ownership and no replay across stale identities.
Per-output preference identity uses workspace UUID/workflow generation/scoped node/output, exclusive atomic favorite CAS and move journal recovery; current backend persistence tests independently distinguish actual storage reopen from intercepted GUI reload.
Current chooser accepted-response versus operation-finalizer ownership barriers are sound under the reviewed client contract; B166 registry revision and B167 request-event correlation gaps belong to those distinct store boundaries, not another chooser rebinding finding.
Visible Node Data focus preservation has actual event/DOM browser assertions and a narrow fixed source callback boundary; mocked gestures do not prove native reader/Qt launch correctness.
The default managed recipe and final real desktop acceptance are explicitly unfinished, which is an honest deferred boundary rather than false compatibility certification.
OS/application permissions, launcher restart, reader/Qt actual initialization, config and selected-environment process proof require later native evidence; headless mocked API launch counts cannot grant that credit.

A177 requirement-change guidance omission applies to current main too: Section7 calls for compatibility checks after requirement changes, but fully read main MenuBar ordinary Save does not refresh the readiness manifest/report when identities remain the same.
Held I1 adds stronger import/Open ownership clauses and captured creation form transfer; those improve sibling/superseded guidance ownership but do not supply an ordinary accepted requirement-Save refresh producer.
The consequence remains stale advisory guidance/prefill, not compute or exact retained-result resolution; no new runtime failure is asserted.
A176 captured requirement-group transfer omits napari version constraint in current and held forms; reviewer-owned current ImageViewers completion consumes the live selected group after await, A168 exact main-only finalizer extension, whereas frozen I1 captures submitted group/prefill version.
No second canonical finding is created for these already recorded source/spec disagreements.

### Current v2 specification judgment

The full recursive document defines one canonical graph, immutable structural ports, explicit field/DataFrame endpoint kinds, dynamic DataFrame positions, private nested snapshots, source preparation and explicit application to parents.
Schema1 input normalization versus schema2 emitted authority, strict unknown-field refusal and library-owned ViewerSpec are coherent with actual model/serializer tests; allowing known-schema ViewerSpec=None remains explicit unknown metadata, not arbitrary malformed-type acceptance.
Embedded graph owns execution, workspace provenance is descriptive and independently preview/apply guarded, source directory IDs remain stable across edits while actual captured content hashes isolate executable imports.
Source staging under captured identities before graph insertion, no execution lease for fresh unreferenced files, and execution admission at eventual graph mutation are defensible distinct authorities; existing snapshot/source rollback and incarnation findings remain qualified against real owner/failure paths rather than blanket locks.
Cross-workflow clipboard promises atomically staged local sources; A096 actual source transport omission and A066 live-catalog hydration/pruning disagree with that intended captured-binding boundary, while same-name unbound ordinary catalog nodes legitimately follow catalog authority.
Nested compatible bindings, atomic destructive-effect confirmation and late parent identity conflicts are essential behavior; A039 required field fanout admission and A040 mixed fallback findings retain exact source-versus-universal-execution qualifications.

Selected Run compiles the full accepted graph and only filters diagnostics with proven unrelated root ownership; unknown/empty/unresolved/global errors remain blocking, avoiding a hidden partial-graph rebuild.
Declared worker requirements are floors, concurrency is a cap and neither becomes cache identity; engine selection requires actual compiled tool capability, not metadata/config alone.
Ordinary DataFrame tools execute in the orchestrator even when graph configuration says Wetlands; actual ProcessingTool process/output evidence is required for worker credit.
Attached execution snapshots/scoped leaf plans and fixed progress denominators are coherent source contracts, but raw cancellation/physical-worker admission issues belong B/root rather than inferred from this prose.
Graph/cache/live retained status are separate from historical execution records, and draft GET cache reprojection explicitly preserves durable revision/content; A030 current-selection Clear continuation is a distinct frontend owner gap.

Modern table/result/viewer identity binds public run/node/result/record before projection; explicit legacy unpinned fallback is limited to absent provenance, malformed-present/corrupt records refuse without raw file/CSV fallback.
Latest is a disposable per-node projection potentially mixing runs; workflow-with-results pins one successful run and is intentionally a non-importable platform bundle with nested importable workflow archive.
Workflow-only export save barriers versus results-only read behavior, staged marked desktop folder replacement, workflow-local results path and definition-only duplication retain distinct safe contracts.
A164 late export continuation and generation-deferred lifecycle A004 are client ownership omissions despite the correct intended invariant, not evidence these export format distinctions are unnecessary.

Trusted Python authoring is a materialization operation with immutable-byte preview/apply, not Run-time import; the ordinary webapp guard is enforced from configured mode (root's corrected ROOT002 scope), so mutable settings does not establish a Python staging bypass.
Editor mode A106 is a separate route boundary; no conflation with the retained Python guard.
Integration settings remain platform-owned and no package executable frontend schema is introduced; generated OpenAPI is normative, acknowledged handwritten draft debt is transitional rather than legitimate second authority (A006).
Demo install is explicitly new-root/idempotent/canonical-provenance based; no implicit package install or overwrite of user-edited recognized templates, actual scientific/package owners supply separate capabilities.
Files desktop paths remain local references and webapp selections resolve explicit managed files, with mutual exclusion and one graph edit; ROOT024 late canvas owner and ROOT026 name-versus-class authority qualify actual consumers without declaring native picker behavior executed.

### Coverage and next dependency batch

338reviewed+8classified/354; all8remaining rows are human-authored archived campaign evidence/issues/plans/progress/start controls and will be read, not excluded merely because historical.
Review historical chronology and exact prospective/passing/deferred/native evidence distinctions next, preserving current comprehensive freeze and all held source hashes.
This is owned-scope progress only; final whole audit and repair gate remain root-owned and open.


### Complete-review checkpoint — B-batch-36

### B012 existing suite-lifetime extension and consolidation candidates

Execution lifecycle source/selected tests clean workflows only at successful fallthrough and suppress deletion failures.
An earlier assertion failure retains the created workflow; unique per-browser timestamp names mitigate collision but not accumulated state/cleanup review.
The stale environment replacement test holds real provisioning at a controlled release boundary and has no test-local finally that releases the gate, drains execution and cleans its workflow when a screenshot/status assertion fails.
The failure/retry and incompatible recipe journeys also leave their created workflows; runner/backend teardown may clean the disposable root, but that is separate from per-case physical-lifecycle release and must be made explicit before stronger isolation credit.
These are existing B012 cleanup-chain/controlled-fixture extensions, not new product lifecycle failure reproductions.
The cancellation WorkerControl nextStart waiter has no per-wait deadline, while the failure-rerun copy has a60second deadline and removes timed-out waiters.
Both local server listeners are acquired before the main try/finally, and socket JSON callbacks assume complete valid trusted worker protocol without bounded pending text/parse failure handling.
Trusted test-only loopback workers and the global Playwright timeout mitigate normal reachability; a failed worker/listener can still produce less bounded failure/cleanup than the explicit polls imply.
Main cancellation/failure bodies do release, drain, delete and close under nested finally, which is materially stronger than the stale fixture and must be retained.
Future suite cleanup should reconcile one controlled worker helper with explicit ownership/timeouts rather than merging away distinct failure/cancel/progress oracles.
No runtime cost or measured speed improvement is claimed.

### Sound witnesses and precise acceptance boundaries

Execution lifecycle's first local setup test deliberately intercepts retained execution HTTP list/detail with setup and numeric progress snapshots.
It proves UI setup text/no false numeric progress, periodic detail refresh and correctly rendered numeric33percent, not actual installation or real worker progress.
Its critical source test performs real GUI workflow creation and API-seeded executable source, actual GUI Run202, backend success/node executed and visible node-data geometry; it does not assert source values itself.
The selected-branch test supplies the complementary stronger data oracle: accepted invalid unrelated missing-tool branch, exact selected request with accepted draft/no inline graph, exact planned IDs/names, exact three rows and no unrelated record404.
A second selected run must have a distinct execution ID, all cached flags and unchanged exact values; this is not merely an empty-success assertion.
The source-only runtime remains host DataFrame computation, not an isolated ProcessingTool PID witness.

Cancellation test actually holds a sequential mapped ProcessingTool through a loopback control event, verifies worker PID differs from backend, genuine task/row progress and partial1/2 node count.
It reloads while running and restores exact execution/workflow/draft identity and counts; injected stale/malformed events are explicitly browser dispatch tests, with a matching event positive control.
It checks Save/Clear mutation controls and accepted draft equality while held, then requires both cancellation-observed and acknowledged signals before idle and worker record404.
No failed/cancelled partial worker record is credited merely from a UI stopped banner.
The rerun reuses completed source cache, requires distinct execution identity and actual scoped running/progress/completion messages, exact worker values/files and rendered table cells.
Those literal worker outputs independently support the later table projection, rather than comparing two only-derived arbitrary displays.
Reload restores successful planned counts and identity, but the ordinary normal whole-workflow mode/requested-target fixture does not cover B186's selected/retry intent omission on fresh reconnect.
Physical callback/writer drain and manager ownership source remain separately reviewed; no general arbitrary-cancellation or native certification is inferred from a cooperative worker acknowledgment.

Failure-rerun test exercises actual remote tool failure, exact preserved traceback/error category, one unread error history row, one attributed backend log, and absence of a partial worker record.
GUI correction must persist a higher accepted draft revision with multiplier4, and subsequent GUI Run must use that accepted revision/no inline graph and a new execution ID.
Exact row values/PID set/files and cleared runtime error distinguish successful recovery from a merely hidden failure.
The second case combines an exposed root output with Group/Delete refusal during the real run, no draft mutation, later Group/Undo/delete/save/reopen graph equality and removed interface/edges.
This adds accepted graph editing/undo persistence, not duplicate successful worker execution without an independent contract.
No parallel scheduling, native viewer launch or desktop bridge is exercised by these sequential web journeys.

Stale recipe journey invokes actual public fixture provisioning, then GUI Run into a managed existing stale generation with visible update screenshot and browser reload while setup remains held.
It requires new generation and recipe digest, exactly one update event and replace authorization, retired old worker set no longer alive, actual Pixi installed progress step and exact owned files/values/PID inventory agreement.
A Clear forces real later processing rather than cache-only success, and the second Run must retain the exact same environment identity/worker list and no additional replacement.
Injected Pixi replacement failure is explicitly fault injection through actual public provisioning, with failed result/no worker record, visible logs and explicit GUI retry recovery.
Separate incompatible Core fixture verifies GUI refuses submission, direct API422 identifies environment_incompatible, and full environment inventory/preparations remain unchanged.
Current authoritative Core recipe compatibility remains strict; no old Core seed or changing the essential force-Recreate requirement is inferred.
These files establish test witnesses for stale replacement, current reuse and failure recovery, not B001's still-held forced rebuild of a matching recipe.
No newly executed acceptance, desktop/native GUI credit or whole-codebase completion is claimed.

### Next group

Nested execution, result exports and managed UI E2E with public launcher input/cancellation counterparts, then installed authority and frozen held T1/spec inputs.
All53 remaining B inputs remain pending; audit and all repairs/tests are held.

### Complete-review checkpoint — root-batch-28

#### ROOT-F096 — P2 qualified download asset identity/publication risk in both shipped example implementations

All four platform/library DownloadImages bodies derive the destination from raw URL last slash segment and skip download whenever that path exists, without verifying which URL/bytes published it.
Two different URLs with the same basename therefore share one artifact: the second returned row advertises its own URL but the first URL's bytes/path.
A failed local write can leave partial existing bytes; a later invocation skips that destination and treats them as downloaded. Parameter implementation writes while response context is open; Fish reads fully first, but local write failure remains possible.
The shipped demo URLs have distinct uncomplicated TIFF basenames, which materially mitigates their normal default recipes; this is public adapted-source capability/failure recovery debt, not an executed wrong shipped microscopy result or wrong worker record.
Raw query/fragment components become filenames rather than parsed URL path; special dot segments may resolve to already-existing directory paths and are not validated as nonempty regular image basenames. No general slash traversal or destructive network diagnostic is claimed.
The full library test_example_download_tools.py only supplies one sample URL/fake bytes and checks managed-assets location/context refusal; it does not distinguish URL collisions or failed-write existing output.
Future bounded diagnostic should extend that existing fake response/write seam and establish URL-to-artifact identity plus failure publication semantics before deciding a collision/digest naming policy; retain managed execution context, actual source URL metadata and self-contained examples.
No test or repair is released.

### Existing A-F114/A-F115 source extensions

The platform-maintained ParameterSweepResults exactly repeats ordinal reset/concat and first-mosaic broadcast; normal six-way parameter source lineage mitigates the conditional changed-order/cardinality risk already canonical in A114.
Its plain string mosaic_path declaration remains known schema without image/viewer declaration, A115; do not guess image requirements from path-looking strings or remove the output.
The generated graph explicitly publishes four narrow fields, while intermediate table includes wider values; root versus terminal output distinction A111 remains applicable and no scientific values are lost merely by the narrow interface.

### Retained producer and scientific judgments

Default known packages contains three explicitly selected discovery seeds, not an exhaustive installed-tool inventory. Comments claim missing-file-only fallback; actual KnownPackagesService/refusal policy remains reviewer ownership, not a second parser.
Manifest identifies both bundle_version5 templates, explicit source recipe and installed Demo paths; complete JSONs bind portable package versions, recursive marker input/output immutable IDs, display names, schema2 graph and document1 metadata with no owned-source IDs before installation materializes its owned tools.
Fish has four input URLs, explicit CYX channel2 nuclei and separate marker channels0/1, two scoped nested overlap pipelines and ordered two-table summary. Parameter has2 sensitivities times3 sizes, actual CrossJoin inputs/typed parameter edges and row_index-aware ATLAS output template, scoped measurement/mosaic/summary lineage.
These are full source/configuration judgments, not regenerated artifact hash equality, model quality or current released package compatibility.
FishLabelOverlaps validates exact2D/numeric/finite/nonnegative/integer/range-compatible labels before uint64 conversion, equal shapes and sparse cooccurrence; includes background associations to preserve nuclei with no marker, explicit original image basename and mapped output rows.
Average summary requires exactlytwo tables/requiredcolumns, groups by immediate parent expansion index, distinct spot labels per nucleus, counts zero-marker nuclei, weighted total denominators and named global row.
Existing complete weighted numerical test explicitly establishes four source origins,0.5/2/1/0 per-image values and weighted global0.8/1 with five total nuclei; parallel integration uses constructed marker data and cannot certify external microscopy quality.
An all-background overlap body returns[] and absent-row images cannot be recovered solely by this aggregator; whether to preserve a zero-image row or refuse empty mapped output is a public cardinality/scientific contract question, not an established silently omitted default image without reconciling engine empty-output policy.
SpotMaskMetrics explicitly counts axis-adjacent foreground components (4-neighbor2D,2n in nD), not distinct preexisting label IDs; zero-size fraction guarded and no shape/finite check beyond declared input semantics. Python flood fill and two full-size boolean buffers are an unmeasured large-mask cost candidate; do not infer speedup or alter connectivity without a scientific contract decision.
Maintained curated platform sources are actual exporter inputs, even though JSONs are derived; reviewer047's publication gap must preserve those authorities rather than treating the whole directory as disposable output.
No duplicate source credit, new test growth, runtime/native pass or full review gate closure is claimed.

### Complete-review checkpoint — B-batch-37

### Findings and refinements

B-F180 is refined by the existing exact test `nested-execution.spec.ts::Run Selected expands recursive dependencies and refuses an invalid nested boundary`.
It deliberately submits the invalid selected nested root and expects HTTP 422 carrying the scoped leaf error, with prior completed execution status, accepted draft revision/base hash/graph, sibling artifacts and absent invalid results unchanged.
Thus the frontend root-versus-scoped-leaf early guard is an early UX consistency candidate, not missing overall refusal coverage or evidence of invalid compute admission.
There is no requirement inferred here to suppress that POST; the backend refusal floor and tested behavior must be preserved.

B-F012 receives precise test-lifetime corroboration: nested setup creates workflows before the main finally; an intermediate creation failure can leave an earlier test workflow, while deletion failures are suppressed.
The export and managed journeys perform deletion only on successful fallthrough.
These are fixture cleanup qualifications, not demonstrated leaked runtime processes or failures of the parent runner's isolated runtime teardown.
No new production defect ID is introduced.

### Per-file judgments

`nested-execution.spec.ts` fully traces actual Direct sequential GUI work through saved/draft graph admission and scoped result lookup.
The distinct invocation test uses identical internal node IDs with different literal inputs and asserts separate literal values, scoped statuses and stable result identity after reload.
The selected test proves dependency expansion and pruning of an invalid unrelated nested branch, then the exact invalid selected boundary refusal above.
The failure/repair test retains the successful source record, rejects failed nested/downstream results, leaves sibling artifacts unchanged, edits a private nested snapshot without changing the parent accepted draft, applies it through GUI and runs a new execution with exact successful rows.
These are strong invocation, admission and persistence oracles; host Direct results do not establish isolated worker or native GUI compatibility.

`result-exports.spec.ts` traces genuine local workflow execution and downloaded archives, including a later selected run and a separate workflow becoming global latest.
It checks exact CSV values, per-node execution provenance, archive member names, bundle manifest and nested archive digest, and verifies repeat downloads remain byte-identical while the unrelated run remains active history.
A single intercepted 409 is explicitly a controlled export conflict, followed by actual retry/download; it does not prove a real concurrent filesystem failure.
The ZIP helper is a trusted-test archive reader rather than an untrusted ingestion security oracle, and this test does not decode parquet or validate nested graph contents beyond digest.
Those limits do not diminish its workflow-versus-global-latest and per-node run provenance assertions.

`managed-execution.spec.ts` uses actual local workflow creation and UI but intercepts every remote target, preflight, submit, list, result and cleanup request.
It precisely asserts profile revision, two-stage path choice, submit token, one submission, retained run/scheduler/progress rendering after reload, cleanup digest and one plan/apply call.
The result body is literal text labeled ZIP; the succeeded snapshot is constructed by the test.
This is a protocol/UI integration oracle and gives no real remote provisioning, scheduler, worker PID or validated result-archive evidence.
Its explicit campaign exclusion is accurate; ordinary/full default applicability remains separate as established by the shared test-runner review.

### Retain / defer

Retain the distinct invocation literal-data oracle, invalid selected boundary no-side-effect oracle, workflow-bound export provenance, real retry after controlled conflict, and managed token/digest request assertions.
Do not collapse these into one generic execution test or claim each witnesses external workers.
Defer fixture cleanup strengthening and B-F180 UX policy decisions until the complete audit gate closes.
No tests were executed and no repair is released.


### Complete-review checkpoint — B-batch-38

`tests/integration/launcher/test_node_input_uploads.py` exercises genuine local bundle preparation and public agent allocate/commit/submit materialization, with orchestrator launch explicitly monkeypatched.
The first test changes original bytes after preparation, then verifies the nested Files constant points to the immutable object and retains prepared bytes; a failed-parent planned retry retains that same installed path and content.
The second test resolves two root list uploads sharing a basename in original order, with distinct object paths and exact bytes.
These are strong staging authority, ordering and retry snapshot oracles; they do not execute a scheduler or prove worker routing, despite supplied executor/launch metadata.
The old Core attestation fixture is not a current worker compatibility witness; the Files-only bundle path does not imply a public processing recipe acceptance defect.
No new source finding is identified.

`tests/unit/test_wetlands_cancellation.py` injects fake task/manager implementations into the actual tracker/dispatch boundary.
It distinguishes cancellation before registration, terminal callback removal, partial submission failure retaining the already-created task, a cleanup KeyboardInterrupt followed by a second drain attempt, cancellation stopping further submission, and cancellation winning over coincident completion/failure/timeout.
Exact submit/cancel/wait counts make these more meaningful than status-only assertions and preserve the primary submission exception.
The fake task's wait method itself marks terminal; it cannot attest physical worker retirement, public Wetlands cleanup failure behavior or actual task await cancellation.
Those remain separate source/runtime findings and stronger existing external tests rather than reasons to discard these focused deterministic cases.
No new defect or redundant test deletion is proposed.

Retain both suites and their distinct oracle scopes.
The audit remains open and no repair is authorized by this checkpoint.


### Complete-review checkpoint — B-batch-39

#### B-F190 — saved-versus-draft user guide authority

P3 documentation defect: `docs/user/run-and-results.md:3` says the active saved workflow is validated before every run.
The actual local GUI Run captures and validates the latest accepted draft, including unsaved edits; the complete Run, backend execution and draft-derived GUI tests reviewed in earlier batches establish this distinction.
`docs/agents/execution.md` correctly describes latest draft capture.
The misleading opening may cause a user to expect Save is necessary or believe unsaved edits cannot execute.
Future correction should name the accepted active draft without weakening immutable captured-run, validation or conflict-refusal requirements.
No application behavior defect or missing save action is inferred.

### Existing findings / compatibility

The shipped `parsl.py` calls `runtime.executor_binding` without an explicit processing environment identity.
This corroborates reviewer-F040: ordinary exact routing can refuse a GENERAL_ENV ProcessingTool recipe when only the runtime/gateway attestation is supplied.
It is not evidence of a wrong-environment worker execution, nor permission to relax exact recipe/Core admission.
The optional site setup and explicit trusted script warning remain necessary; setup execution/validation context belongs the reviewer's public gateway findings.
B-F088 acknowledgement-window ambiguity remains distinct from repeated same-request receipt behavior and the guide explicitly warns about allocation before returned ID.

### Specific no-finding judgments

The agent guide consistently names MCP tools, captured draft semantics, selected upstream dependencies, cooperative stop polling, locks and frontend conflicts.
Its warning qualification is bounded by capability allowance and does not grant hard-validation bypass.
The distributed guide distinguishes site facts from installed software, trusted executable files from persisted nonsecret metadata, explicit describe/save/submit from opening a selector, exact planned retry child from uncertain allocation, and run-owned workspace/result retention from current workspace selection.
The result guide otherwise accurately describes scoped progress, retained cell identity, explicit one-time viewer choice, structural favorites, no automatic environment retry and per-node latest exports.
Its local filesystem actions must retain existing immutable deployment policy guards; source findings ROOT-F002/B-F042 are separate from editorial availability claims.

The shipped `cluster.py` is explicitly a site-owned placeholder with separate orchestrator and worker requests, existing Python, shared root and optional setup.
`setup.sh` intentionally contains `CHANGE_ME` module values; it is not claimed usable before editing, and no secrets are embedded.
No scheduler operation was attempted.

All eight package image-directory READMEs were fully read as human-written maintenance policy, not classified away.
Common/IO/measurement/restoration/spot/tracking explain generated numerical fixtures versus optional illustrations, segmentation suggests tiny masks, and SAIRPICO states package asset ownership.
Their narrow prose makes no unsupported worker, numerical accuracy or full-test certification claim.
Scientific source/test review belongs the root and visual asset provenance belongs the documentation reviewer; no new contradiction was identified in these files.

Retain guide acknowledgement, exact retry/identity and trusted-site boundaries.
Defer B-F190 correction until the full audit gate closes.


### Complete-review checkpoint — reviewer-batch-47

#### reviewer-F095 — captured catalog refresh can overwrite later accepted active/environment updates

P2 qualified read-model race: package_catalog.refresh60–75 captures installed registry metadata before awaited PyPI fanout, then98–105 publishes the entire snapshot from that old capture.
Concurrent update_active_version106–120/update_environment_status122–132 can patch the current snapshot while lookup awaits, then be replaced by the older active/environment state.
Borrowed tools router499–500 publishes accepted active selection directly into this read model; startup/manual/post-install refresh callers are real.
Root's complete counterpart test_catalog_refresh_preserves_active_version and test_catalog_update_active_version_patches_snapshot are sequential, not held lookup/update completion distinctions.
Preserve registry authority, current active badge, offline no-network list fallback and per-name network isolation; a bounded existing fake-lookup barrier is the later diagnosis seam.
B-F016 package-level environment granularity is separate; no actual selected tool/worker binding change was executed or alleged.

#### reviewer-F096 — known-list unreadable-text failure falls outside existing fallback/error policy

P3 qualified operational failure source candidate: known_packages45–57 catches OSError around UTF8 read, but UnicodeDecodeError from a present user file escapes that policy.
Catalog refresh reads known names before its per-name broad isolation, so this can reject the refresh; app startup has a broader logged fallback, and raw installed list/current snapshot can keep the app usable.
Root's complete known-list tests cover valid override/comments/missing files, not malformed encoding.
Future smallest existing user-file fixture should establish coherent visible refusal or warned fallback while preserving the explicit user-file override; the audit does not assume silently replacing an invalid override is the only valid policy.
No malformed file or refresh was executed.

#### reviewer-F097 — syntactically valid malformed PyPI JSON escapes typed lookup failures

P3 qualified external-response failure source candidate: pypi_versions56–63 calls response.json().get and releases.keys while catching ValueError only.
A valid JSON list/scalar root or nonmapping releases raises AttributeError rather than PackageNetworkError.
Catalog's broad per-name exception catch correctly isolates lookup failure to installed fallback, but public get_latest_stable is called by PackageInstaller.install130 before the installation try-block, so that caller has no equivalent shape isolation.
No install side effect occurs before that lookup in the traced caller.
Root MockTransport tests distinguish404/network/timeout and normal body only; use those existing seams for typed malformed-data diagnostics after M1.
No live index or installation was accessed.

#### reviewer-F098 — invalid release label can be chosen as latest stable

P3 qualified malformed-upstream source candidate: pypi_versions79–90 sorts InvalidVersion strings after parsed versions and treats them as not prerelease; get_latest_stable70–75 then chooses the last such label as stable.
This can pass a non-PEP440 release label into the default installer despite valid stable releases being present.
Keep unknown/local installed versions visible where the catalog requires them and retain the explicitly tested pre-only fallback; latest install selection has a different authority than display sorting.
Root's complete stable/pre-only/empty MockTransport cases do not distinguish invalid release keys; their existing fixture is the smallest later seam.
No actual invalid release, command or install failure was observed.

F086 now has complete demo producer/schema corroboration: installed status explicitly returns identity_generation; current frontend removal discards it.
Demo missing-only publication preserves edited existing demos/conflicts and legitimate missing-root initialization; no seeding or ownership feature is narrowed.
Actual is_running includes _starting and idle mutation reservations, and the install route's post-check body has no await, so the preliminary missing-start-admission hypothesis is withdrawn rather than elevated into a defect.
Native reveal's actual deployment policy remains ROOT002; success means process spawn, not completed native reveal. Health means server liveness/version, not readiness or worker certification.
The six-status enumeration is correct: cache_corrupt is an error type, and batch45's earlier optional seventh-state inference was explicitly corrected before acceptance.
Unverified compatibility question only: ErrorResponse uses Field(exclude_if) while backend declares pydantic>=2.0; introduction/support at that floor was not established from local primary evidence, so no incompatibility claim or defect ID is added.
Operation failure text repair/tail rendering preserves specific details and relies on the library's structured redaction contract; mocked platform portability checks are not real Windows/crash evidence.
Global closure/current controls and all repair/runtime remain held.

### Complete-review checkpoint — A-batch-47

### Full historical record judgments

### Evidence before September30 —87lines

Full ledger preserves expanded source inventory obligations, real worker progress versus controlled setup, confirmed schema migration, recursive imported layout, Logger text/copy, registered viewer controls and strict corrupt-cache reads.
Commands identify source or patch-equivalent revision, duration, selected counts, unrun/deselected phases, original failed broad commands, exact recoveries and post-final change invalidation.
Examples correctly retain backend socket failures as original red/composite evidence, refuse same-revision app certification after the final link guard, distinguish real file-backed registration from controlled manager/browser registry and exclude native Qt provisioning.
Migration public GUI saved document plus recursive backend snapshot/restart/crash-injection are explicitly separate from OS crash/packaged restart.
Logger store-seeded GUI content/Chromium actual clipboard versus Firefox captured write cannot establish WebSocket provenance or every native permission behavior.
Imported layout browser test's actual graph/DOM/persisted position controls, fully reviewed in A43, justify one-time deterministic materialization and no-reflow/sibling isolation rather than generic layout snapshots.
No new finding in this file; the catalog-add broad failure and missing causal breadcrumbs are honestly recorded here and must retain their own task attribution below.

### Evidence through Tier1B —289lines

All heading entries, long completed-feature bullets, tables, release metadata and handoff text fully read.
The exact BasicUse collection has56tests/28perbrowser,73stable applicable cells and one clean evaluated SHA; collection-only proof, actual independent browser execution, backend/frontend/docs checks and headed confidence are distinct.
The original snapshot specifically leaves owner acceptance/continuation undecided; later progress records dated owner continuation, which is chronology rather than an active contradiction.
Excluded managed/distributed/parallel scope, external package runs, sequential worker PID/outputs and mocked orchestrator cases are named; actual cooperative Stop admission/drain proof is stronger than simply HTTP200.
A deliberately non-cooperative fixture was rejected rather than weakened into fake Stop evidence, and selected worker claims include distinct actual process/result identity.
Source-preview recreation, selected compiler boundaries, nested conflict/Apply/copy and table/export bytes preserve precise observable outcomes with residual gaps.
Current fully reviewed main browser fixtures corroborate actual source/copy rows, atomic baseline/failure/retry identities and direct-engine records; A012 fixture catalog type/default/unused argument flaws and A009/A166 possible test overlap remain source-oracle limitations, not reasons to erase valid historic outcomes.

Broad runs retain first failure, passing prefix/unrun tail and independent exact green followups without relabelling the original command green; repeated milestones were eventually stopped by owner and source causal Open repair remained separate.
The evidence discloses initial sandbox/network/port restrictions and corrected authoring assumptions, not product failures; future execution should request expected privileges first under current AGENTS rather than repeat predictable restrictions.
Its early retained uncommitted-tree evidence explicitly lacks per-run tree hashes and prior temporary broad exclusions are not reproducible complete certification; durable applicability must be re-established from paths or rerun later when authorized.
Release/CI/PyPI URLs and historical package versions are human records here, not independently fetched or reverified by this static audit.
No blanket modern release/native/whole-suite claim follows; temporary logs are explicitly unnecessary for restart and old unfinished runner drafts must not be revived.
No new finding; revision-specific limitations are a sound decision to retain.

### Issues through Tier1B —233lines

All001–017 decisions and template fully read with corresponding owned source/test and cross-owner entry contracts already inspected.
Historical generation-1 preview applying to recreated generation3 motivated captured destination generation inside mutation lease, not artifact hash alone.
Ordinary mutation reservations and actual execution activity require different queue/refusal behavior; delayed writer/physical cancellation is a distinct current B boundary and does not make the earlier ordinary-mutation fix unjustified.
Run Selected compiles the intact complete graph and scopes only attributable diagnostics, retains global/unresolved/unknown errors and total dangling endpoint traversal.
Rejected nested overwrite controls lacked generation/surrounding ports/newer private/lifecycle/accepted durable fences; correct refusal/private dirty retention and explicit Discard/reopen remain a defensible not-a-defect decision.
Private snapshot CAS UseLatest/KeepMyChanges described in later evidence is a different accepted-authority conflict, not authorization to overwrite changed parent content.

Cooperative Wetlands Stop drains submitted possible writers and historical public cancellation/PID/no-partial-output proof is strong; current raw-wrapper cancellation/physical admission debt is independently B/root-owned, not falsely declared resolved by this previous release.
Nested Save's omitted default:null versus backend canonical graph comparison, one contextual enriched terminal error, graph-owned SaveAs destination identity and cache-status projection preserve focused causes rather than broad arbitrary timing waits.
Clear backend restart proof uses a separate actual backend process plus HTTP and same-process GUI reload; the archive explicitly does not claim one live GUI spans process restart.
Open014/017 observations remain cause-unproved, exact-green does not clear original broad red and actual click/command/request/lock/tab breadcrumbs are requested on recurrence; ISSUE018/022 must not be conflated.
Paths/line selectors and discoverability hints are historical and require current collection/path reconciliation before future reproduction; do not rewrite old results to modern line numbers or create new tests merely because old selectors moved.
No new canonical source defect; historical decision boundaries remain useful constraints.

### Wave1 resolved ISSUE018 —22lines

Complete controlled event timings, original source/diff/library identity, independently unmodified-latency green diagnostic, reviewed owner plan and exact/stress/composite validation are recorded.
Observed accepted Open/startup mount/child activation/late explicit Open return establishes that specific root-presentation cause; corrected App startup fence and speculative nonprojecting draft read match full A main source judgments.
No correction inferred for earlier014/017 or later022 lacking the same causal record, and no native/worker/package/excluded-engine credit.
Deferred saved-load metadata reset had its own red unit and additional guard, not an unperformed generic review.
No new finding; retain source-specific causality and bounded original evidence.

### Archived plan —341lines

Complete orchestration, tier ordering, exact73cell BasicUse table/gate, reachability/severity, complete scenario families/dashboard, realistic fixture and exact-first repair ladder, explicit specialist review, lane reuse/invalidation, final certification and durable restart rules read.
Finished correct user outcome and owned durable state rather than raw test counts is the proper unit of progress; stronger existing journeys should be reused when adequate, but unrelated failure isolation should not become one monolithic suite chain.
Owner pause requires an explicit decision and leaves systematic campaign incomplete; gate cannot silently erase native/external/lower-tier obligations, rejected Cartesian explosion still retains meaningful scenario boundaries.
Task-specific reviewers/independent worktrees/dependency isolation/browser resource serialization and per-run revision/artifact records are defensible process decisions.
The historical routine/refactor execution authorization is superseded by current explicit whole-audit-first freeze; this file's prominent historical wrapper is essential and was obeyed.
At most one broad milestone attempt and exact recovery preserve honest reds and unchanged phases; this is workflow efficiency, not measured suite-wide runtime/redundancy improvement (A009/A166).
Do not resurrect historical explicit model names/release baseline as current runtime selection or launch extra agents from the archived prompt.
No new finding in its normative historical strategy, subject to the user-approved current strategy and full-audit gate.

### Progress before September30 —45lines

Full header/counters/closure paragraphs/next3actions/working-set read.
Historical50c1af4 BasicUse and primary GUI obligation closure remain revision-limited; expanded500denominator includes new obligations and no current full-suite certification.
Progress/source inventory dates and later integrated feature entries are historical layers, not proof every visible new case passed on the latest current source.
Native provisioning/Qt/OS restart and legacy result limitations are explicitly retained.
One definite low-priority attribution ambiguity is A181 below: catalog-add broad attempt belongs to imported-layout evidence, while immediate pronoun attaches it to corrupt-cache task.
Archived next-actions N1/import/environment work and unrelated user presentation path are not instructions to resume or alter anything during this audit.

### Progress through Tier1B —131lines

All state/milestone table/gate, every long integration/ownership/worktree bullet and final restart rules read.
Owner continuation after the gate is explicit and systematic coverage stays incomplete despite219/219primary cells; broad browser red/interrupted commands/remaining obligations survive separately.
Issue017 focused green5+sequence3 with no speculative repair is correctly distinct from cause-unproved full Firefox failure; fixture Open-prerequisite replacement does not erase ordinary doubleclick contract coverage.
Startup-precedence source repair, nested/write/worker/copy/result/layout tasks preserve integrated versus patch-equivalent evidence and no post-merge broader lane where absent.
Worktree archival paths/branch states record historical ownership; no current existence/process state inferred or cleanup performed.
Important milestone table records earlier179/220 versus currenthistorical219/219 in their dates, not a present denominator conflict.
Root's complete Everyday1211 corroborates real mixed edit, bulk enable and atomic deletion Redo; A180 is solely the moved-position final oracle gap in canvas-interactions, not global absence of Redo coverage.
No new finding in this archive beyond possible future concision after retaining exact revision decisions.

### Archived restart —85lines

The entire prompt includes bounded packets/context, disjoint writes, source reconciliation, priority versus final scope, stale/refactor plan/review, real GUI and known expected rows, exact-first/completion ladder and no full-lane chase.
Model selection is explicitly a runtime setting, not activated by reading text; historical command prompts are retained audit material only.
Worker source/spec edits and integration commits are old authorized campaign procedures, not an exception to the current explicit no-repair freeze.
Native/manual/external owner limitations remain visible and unpassed; existing release evidence is retained, hypothetical agent absence cannot be credited as a review and owner status questions do not cancel a task.
No new finding; historical wrapper avoids accidental replay but current orchestration remains root's authority.

#### A-F181 — Low archived evidence attribution ambiguity after the corrupt-cache closure

`docs/developer/archive/platform-test-progress-before-2026-09-30.md:22` closes RT-EXE-017 at e58b8f1 and the immediately following line23 says "Its broad Chromium completion attempt" failed catalog-add with103unrun.
The detailed evidence record places that exact eight-pass/catalog-add/103unrun broad attempt in GUI-EDT-014 imported layout at38ac552 (`platform-test-evidence-before-2026-09-30.md:64–68`), while e58b8f1's entry82–87 explicitly reports app success before final link guard plus exact affected checks and no same-final app certificate.
The original broad red/unrun count is honest, but the pronoun misleadingly attributes that run to the wrong task/revision and can distort invalidation or the reason for selecting a future diagnostic.
Future documentation-only correction should name the imported-layout task/revision rather than change any observed pass/fail/skip record.
No current product defect, invented missing evidence or new test is implied; preserve the original exact failure and no proven catalog-add cause.

### Owned coverage and remaining gate

354/354assigned frozen records now have individual judgments:346human-authored complete reviews and8explicit generated/asset classifications; no pending A rows.
221platform records (220reviewed/1classified),118library (111reviewed/7classified),13heldI1 and2heldtoolbinding separately hashed and reviewed.
Metadata-only reconciliation verified354manifest members/frozen hashes and no current content drift across their four source roots.
The first metadata hash command used an incorrect repo-label mapping and failed before the final all-hash scan; its correction used the actual `library` label and completed without drift. This was audit bookkeeping, not test execution or product evidence.
Root must still reconcile these reports, other owners' scopes/current control updates, opaque classifications and prioritized canonical findings before the whole-audit gate can close.
Application code, tests, runtime state and WIP remain unchanged; no repair or campaign completion claim.


### Complete-review checkpoint — B-batch-40

#### B-F191 — contradictory Clear action description

P3 internal specification defect: v1 Section3.5.2 says Clear sets Unexecuted and removes output data.
The same specification Sections2.4.5/4.6 and the full runtime/storage source distinguish invalidating current cache selection and removing disposable latest views from deleting retained record bytes; downstream status also depends on retained output availability.
This short action description can imply disk reclamation or loss of historical results, and is inherited by frozen T1 v1.
Future editorial reconciliation should describe invalidation/latest-view withdrawal while retaining corrupt-record quarantine, immutable historical records, selected-root scope and existing retained downstream semantics.
B-F188's never-run downstream response-versus-GET distinction is separate and qualified; the parent's full everyday-node-editing test corroborates the strong real retained downstream Clear/reload/rerun contract.

#### B-F192 — always-development-mode wording versus live supported setting

P3 specification drift: v1 Section2.7 says the GUI always runs with dev_mode=True and has no toggle.
The no-UI-toggle statement may be accurate, but the unconditional runtime claim conflicts the live SettingsStore provider at app.py431–434, execution.py658/739/761 and graph validation's forwarded dev_mode.
The settings model/API accept this ordinary field, and the complete cache parity test deliberately checks both values.
This is not a request to forbid the existing setting or to weaken source identity requirements.
Future reconciliation must distinguish default/UI policy from supported runtime settings and preserve meaningful both-mode cache tests.

### Existing source findings mapped to explicit requirements

The explicit Create/recreate force-rebuild requirement remains essential, despite the observed matching-generation actual red B-F001 and PLAN-ONLY public wrapper proposal.
The automatic stale path, matching reuse, public API boundary, unrelated/unmanaged owner isolation, recipe/Core policy and progress observation must remain intact.
Main v1 accurately describes the accepted E1 shared preparation guard; the frozen T1 delta additionally claims manual full-physical-operation admission, alias/exact-name precedence and full declared recipe protection.
Those claims map to the complete held route/service/tests under B-F013/B-F014, not integrated production certification.
The snapshot's historical campaign-running prose is frozen WIP, not current audit gate status.

Other requirements remain binding rather than silently erased by gaps: scoped log context B-F184, reconnect intent restoration B-F186, exact Fiji result addressing B-F049, desktop policy ROOT-F002/B-F042, source/catalog authority A-F001/A-F066 and catalog version semantics A-F156.
The v1 typed WS union note lists two compatibility events but the complete backend source identifies additional emitted events absent from that union (B-F186); future schema work should reconcile the whole authoritative event surface.
The specification itself distinguishes normative base, cumulative implemented deltas and future v3; no proposed multiuser/authentication behavior is inferred as implemented.

### No-finding/retained structures

The full specification coherently preserves one recursive graph, accepted root/private nested revisions, complete compilation for selected scope, descendant-owned/global blocking errors, no request-history authority, captured immutable result reading, deliberate unpinned legacy compatibility, resource floors/site allocation separation and independent row/task progress.
It distinguishes disposable per-node latest exports from a pinned successful-run bundle, shared local run locking from immutable managed submissions, explicit trusted-site setup from credentials, viewer unknown-outcome no-replay from retry, and dataset logical identity from physical paths.
These remain valuable boundaries; repetition across endpoint, frontend and data-flow sections invites coordinated editorial maintenance but is not grounds to merge unrelated product specifications.

The complete held E2E app separates synthetic WS failure injection from actual PID/environment generation/Pixi fault evidence.
It fixes isolated roots, freezes the public shared manager before platform configuration, uses offline package-index queries, and registers distinct selected/unrelated/external/protected tools.
Its added isolation/evidence routes call the already fully reviewed public lifecycle fixture helpers.
The `worker_manager()` observed-wrapper lazy mutation is not protected against concurrent first dev-endpoint access; current serial fixture use mitigates that instrumentation ownership limitation (B-F012), and it is not a production Run-manager finding.
No force rebuild, scheduler or native evidence is supplied merely by these dev endpoints.

All T1 bytes and the force-wrapper plan remain preserved.
The full audit gate remains open; no repair is released.

### Complete-review checkpoint — root-batch-29

#### ROOT-F097 — P3 qualified embedded opener liveness and diagnostic ownership candidate

extension.ts creates one fixed127.0.0.1:60351 server without registering a server error callback; a failed bind has no opener-owned structured readiness/error reporting path.
Source alone cannot establish the extension host's global error disposition, so no host crash or executed port collision is claimed.
All non-OPTIONS requests enter one promise chain and await VSCode openTextDocument/showTextDocument/openFolder without an internal operation deadline or aborted-response/disposal owner.
One indefinitely held editor API request therefore holds later opens, while server.close on disposal does not explicitly retire queued/in-flight operation state.
The normal one-managed-editor application, trusted loopback requests and platform caller readiness/retry timeout materially mitigate ordinary use; platform correctly refuses false opened success and does not launch a second editor after control failure.
The fully reviewed Python editor tests inject fake openers/readiness and inspect packaged text markers; they do not execute Node server error/queue/disposal behavior.
Future bounded existing-source harness should distinguish bind refusal and held/aborted request ownership only when improving this supported bridge; retain ordered opens, unchanged file workspace, explicit readiness refusal and no automatic replay of ambiguous successful native/editor work.
No runtime liveness failure or security exploit was reproduced, and no new test is authorized by this review.

### Individual producer/classification and retained judgments

Owned TypeScript77 and compiled JS102 were fully read; runtime logic agrees, with TS helper erasure/CommonJS import boilerplate explicit. Compiler targetES2022/Node16 and strict source ownership are configured; no current recompilation equality is claimed.
VSIX is a valid six-member ZIP with no CRC error. Each member's exact bytes equal its owned package.json, compiledJS, README, CHANGELOG, extension.vsixmanifest or content-types source counterpart.
Manifest engine/publisher/name/version/activation and entrypoint match package0.1.0; XML declares precisely JSON/Markdown/JS/manifest content types. Both are packaging-derived metadata, not independent product business logic.
.vscodeignore excludes TS/source, dependencies, lockfiles and maps from VSIX; scripts first compile then package. No new build/toolchain or published extension compatibility evidence follows from static inspection.
The human source docs distinguish owned source from old Galaxy reference, startup activation, loopback control and ordered request intent; old absolute reference is historical provenance, not a runtime import/dependency.
File request awaits text open/focus and never Explorer reveal; explicit folder/workspace handling may change the editor workspace, while normal Python manager folders use editorURL navigation and only files invoke this endpoint.
OPTIONS handles CORS directly; unsupported path400/404 and caught API errors500 are explicit, but non-OPTIONS method admission is not enforced beyond route parsing and loopback trust policy. No remote authentication or untrusted-network deployment is claimed.
Existing test_default_opener_extension_matches_source_package checks package/name/openQueue/no-reveal markers rather than exact full byte parity; the static archive parity check strengthens artifact provenance without replacing future actual editor readiness/native validation.
Root source/package slice is complete; other owners/current controls/independent method gate remain open.

### Complete-review checkpoint — reviewer-batch-48

### Complete dependency judgments

The171-line semantic request grammar forbids unknown fields, discriminates each operation, bounds batches1–10 and supports stable workflow-node scopes, exposed port IDs, distinct column/DataFrame endpoints and explicit validate alias.
It carries expected revision but no expected root incarnation, corroborating A-F004; subsequent backend generation capture is material protection for replacement during an operation, not a client first-admission guard.
The426-line transform clones the input, processes operations in order, reparses the full recursive graph after every step and returns indexed semantic errors; the111-line route holds an actual idle lease through asynchronous snapshot/commit and publishes only the accepted draft.
Pure transform atomicity, transport admission and real persisted revision/one-publication counterparts are distinct obligations; remove neither merely because they share operation names.
Missing/unresolved tool state may be accepted as an editing graph, while execution compilation remains independent.
Port metadata lookup in _validate_tool_targets347–383 uses the live catalog by tool_name even for carried module/package/version/source nodes, extending A-F001's bound-versus-unbound authority seam; newly catalog-created unbound tools legitimately use the live catalog.
Shared-input pruning and enclosing-exposure transitions have the material differences below.

Graph router253 lines clones request-local input, owns validation admission through worker completion, captures named workflow generation/storage under its workflow lock and rechecks before returning.
A move changing storage restarts validation; a same-path generation failure refuses it.
Legacy custom managers without the lease retain a weaker compatibility fallback, whereas the actual production manager supplies the lease; do not weaken or relabel that distinction.
The output-schema endpoint uses the real builder and unresolved fallback for transient invalid graph states; ROOT-F019 compiled-result failure and ROOT-F020 private workflow._nodes access remain canonical separate issues.
No fresh private-access finding or worker/scientific/runtime success is claimed.
The65-line workflow-status projection traverses enabled selected executable descendants using scoped structural IDs, preserves failed-before-running/out-of-date/executed priority and propagates one failed child detail.
The actual NodeStatus enumeration remains six values; cache_corrupt is an error type, not a seventh node state.
No new projection-local defect is established by this read.

Nested snapshot router375 lines retains execution leases around Open/PUT/DELETE, revision/dependent refusal, exact accepted child graph comparison before favorite remap and durable root generation checks.
It serializes finalization under the snapshot guard then root workflow guard where required, preserving accepted server authority rather than replaying parent mutation.
A-F072 requested stale root admission, A-F073 unlink durability, A-F074 ordinary corrupt record identity, A-F075 malformed unrelated scan and A-F076 cleanup ownership belong the complete service owner; the route does not close those service findings.
_structural_output_exists120–146 decides captured tool favorite survival from live catalog outputs plus carried viewer additions/templates, corroborating A-F001/A-F066; the accepted graph comparison itself remains strong.
Existing root/nested favorite finalization tests establish real ASGI persistence, exact accepted graph/revision, remap hierarchy and idempotent retry, but use an existing declared static output; they do not distinguish carried/live output-schema mismatch or missing session error normalization.

Move journal147 lines is strict, frozen, canonical relative-path constrained, rejects duplicate affected identities and demands exact once generation advances/direct path correspondence and immediate promotion-child topology.
Recovery coordinator98 lines uses snapshot then structure ownership, checks durable generations/topology, performs idempotent forward artifact/snapshot/preference phases and clears the journal only after the ordered phases.
The model's merged expected-after dictionary cannot silently overwrite a normal duplicate affected identity because model validation refuses it.
A-F079 omitted provenance move rewrite remains canonical; actual stored graph definition is independent from that provenance.
Peer complete direct/folder/promotion/restart/fault tests preserve generation gaps, snapshots/preferences and actual filesystem bytes; they are not power-loss or multi-process evidence.
Optional absence of the preference store is a supported configuration, not established favorite loss.
Model-local folder prefix validation questions remain subordinate to the saved-store admission owner, not newly promoted malformed-journal damage claims.

Legacy format387 lines keeps lossless captured metadata/config/defaults where representable, refuses ambiguous legacy nested/published interfaces, uses content-addressed byte backups and staged fsynced replacements and exposes isolated diagnostics for invalid persisted documents.
A-F086 retains the exact semantic-authority mismatch: normalized legacy draft valid=True/errors=[] is assigned without semantic validation; execution admission is separate, so this is accepted-editing/read-model truth rather than unvalidated compute.
Backup publication's absent directory fsync corroborates A-F080 only as a qualified durability-policy seam; current process restart cannot prove power-loss persistence.
Store-level confirmed schema migration concurrency/source availability remain A-F082/A-F084, with existing unauthorized/stale-preview/partial-publication oracles preserved.
Do not collapse automatic compatibility conversion, confirmed migration and forward recovery into one happy-path test.

Export398 lines uses temporary owning roots, exact latest/successful-run selection, copy materialization, symlink refusal, safe parent boundaries, marked replacement and staged backup rollback.
The run bundle pins one successful run ID and hashes the captured workflow archive bytes; it does not promise that a later edited saved graph is the historical compute graph.
Complete peer counterparts distinguish mocked adapter bytes from actual canonical Storage materialization, owned assets/provenance and source-surviving copied results; seeded Direct labels are not actual engine/worker evidence.
Final external folder admission has the B-F080 extension below.
Same-workflow mutation ownership is a real mitigation; no blanket race among ordinary same-ID requests is alleged.

Dev router544 lines is explicitly conditionally mounted test tooling: deterministic source/transform DataFrame fixtures, deliberately limited processing/schema-only classes, synthetic package catalog entries and a real canonical seeded image record/run pointer.
A-F012 fixture metadata/port-policy mismatch remains canonical; simulated catalog processing availability or seeded run metadata must not receive actual released-tool/scientific/worker credit.
GaussianBlur's declared mapped strategy satisfies current Core class admission but its process_row returns a placeholder path; it is a schema fixture rather than a scientific blur implementation.
The PNG seed can exercise backend conversion/result resolution but does not certify Avivator/Qt/Fiji/native launch.
ImageResultFixture writes a process-named temporary directory outside the managed runtime; its no-local-removal lifetime is an optional harness hygiene candidate, not evidence of user-result loss or an ordinary worker leak.
Preserve deployment mounting gates and synthetic fixture labels rather than making development routes part of production acceptance.

#### reviewer-F099 — missing nested finalization session bypasses typed not-found boundary

P3 narrow API failure candidate: finalize_nested_viewer_preferences266–278 calls service.get_snapshot for the submitted child/parent without a FileNotFoundError mapping.
Neighboring GET207–209, PUT242–245 and DELETE373–374 explicitly return404, and app's registered exception handlers map HTTPException/validation/move-recovery rather than raw FileNotFoundError.
A valid nonexistent or already removed session can therefore escape the normal typed response on this finalization route.
No missing-session request was executed and no preference/snapshot loss is alleged.
Existing finalization success/revision/parent-acceptance/idempotent-retry fixture is the smallest later missing-session extension; preserve exact accepted graph, owner generation and no replay of the committed parent.
Root confirmed no canonical duplicate; A-F075 malformed inventory scans is a different service boundary.

#### reviewer-F100 — semantic node deletion drops shared exposed input's surviving targets

P2 source-established semantic mismatch: _apply_local159–166 retains a workflow input only when ALL its targets avoid the deleted node, so one removed target drops the entire input even when unrelated targets survive.
The active frontend removeNodesFromWorkflowInterface25–37 filters only removed targets and drops an input only when none remain; v1§3.15 and PLATFORM_CONTEXT57 explicitly preserve shared surviving targets in a graph snapshot.
The semantic endpoint persists the transformed graph through the same recursive draft authority, and structural validation permits the resulting absent public input; it cannot reconstruct the unintentionally removed surviving exposure.
This is a declared agent mutation path, not a claim that the already-correct frontend deletion helper has regressed.
Complete semantic service counterpart covers scoped input deletion/edge pruning but contains no DeleteNodeOperation case; A's actual exposed-delete browser oracle goes through full-graph frontend PUT and does not exercise this separate transform.
Future diagnosis should extend the existing semantic operation fixture with one input targeting removed A and surviving B, retaining the input's immutable ID/name/schema/default and exact B target; no new broad journey is needed.
No operation/test executed or repair authorized.

### Existing A-F015 extension — scoped semantic port removal leaves enclosing interface exposures

_apply_scoped105–130 repairs parent bindings and direct incoming/outgoing column edges after a child's interface changes, but leaves parent.interface.inputs.targets and parent.interface.outputs pointing at the removed child port.
The complete GraphState reparsing64–66 then refuses that stale recursive graph rather than persisting corruption, so a legitimate scoped port removal with an enclosing exposure can remain unappliable.
This is the same enclosing-referential-integrity family as A-F015's source-refresh transform, with a separate concrete semantic owner.
Existing nested-input counterpart constructs an empty parent interface and bindings={}, so it cannot distinguish this branch or the separately canonical A-F175 claimed-binding oracle gap.
Preserve structural refusal, stable IDs, cascading target-level pruning and exact confirmation policy; do not bypass model validation to obtain a green result.

### Existing B-F080 extension — platform folder final publication repeats no replacement authorization

Initial export_latest_results_folder267–281 enforces replace=False and matching identity marker before materialization.
After materialization,299–311 moves any now-existing destination to backup without repeating that policy, installs the staged folder, then removes the backup.
A newcomer created during export can therefore be replaced even for replace=False or without a matching marker; parent/target symlink identity can also change after the early parent check.
The same-ID workflow lock serializes ordinary cooperating service calls, and trusted selected local export parents constrain reachability; qualified external writers or independently colliding generated destination names remain the relevant scope.
safe_workflow_export_stem uses a readable hash for nested names, which is collision-resistant rather than a namespace-wide exclusive reservation; no hash collision or concurrent export was executed.
Peer B explicitly accepts this separate platform-owner evidence as an extension of canonical public-library B-F080, avoiding duplicate defect IDs.
Existing marker/replace/rollback tests initialize destination state before the call; their injected staged-install fault correctly proves original backup restoration but does not create a newcomer during materialization.
After the full gate, use that existing exporter seam to distinguish final replace=False/no-marker admission and ownership before deciding a cooperative target lock or stronger publication policy; retain portability and owned-stage cleanup.

### Architecture/cost dispositions for parent synthesis

Prioritize durable authority and physical completion ownership above test-count growth: dataset staged publication, captured tool/module/recipe binding, client first-admission incarnation, keyring rollback and managed deployment root boundaries have concrete entry paths or existing held diagnostics.
Force-rebuild semantics remain an existing real-red task on the same injected library/Wetlands manager; preserve explicit force, fail-closed close/removal, admission through physical completion and honest non-atomic destructive failure/retry.
Treat changed read-model/presentation owners (F091/F092/F095/A168/B175), bounded parser/type refusal (F096–099) and essential recursive interface integrity (A015/F100) as smaller coherent packets, using the exact existing owner seams before additional suites.
Refactor only demonstrably shared authority/lifetime/serialization rules; preserve separate saved/root/private, captured/unbound, active/retired, committed/acknowledged and mock/actual/native boundaries.
Spec/tutorial concision and selector/oracle debt should be reconciled with producer source, preserving required controls and honest evidence; F003/F027 marker applicability and A175/F083 weak assertions are not permission to run every full lane on each edit or remove essential external/native certification.
Optional UI churn, unused legacy helper cleanup and duplicate fixture setup remain deferred/unmeasured, with no claimed suite savings or runtime failure.
All candidate repairs, new diagnostics, application execution and global completeness acceptance remain held pending the user's complete review gate and final current-control reconciliation.

### Complete-review checkpoint — B-batch-41

### Installed provenance and authority

The three installed files come from `backend/.venv/lib/python3.13/site-packages/wetlands` with published 2.4.2 metadata.
Their original reconnaissance rows lacked hashes; the parent recorded these current read-only snapshot identities explicitly, not historical baseline equality:

- `_internal/environment_management.py`: `236fec4fdbea6c5362c859a118506709c280f28319017562bc68c8a35fb9d077`.
- `_internal/provisioning.py`: `4360a7712b74598adaaa1fb93da13d6c4a25e36da4da96965e3dceb28ca1778c`.
- `environment_manager.py`: `63e3c9d3f641f69b16dc6dc361ceb1b34d94af0174f6be3a90d95d36cc665bd7`.

Each was read completely and is byte-for-byte equal to its checkout counterpart at the declared Wetlands source revision.
The source comparison does not substitute checkout dependencies for installed authority or prove historical test artifacts used these exact bytes.

Public remove first holds the canonical cross-process environment gate, refuses alias/unmanaged targets, checks cached generation resources and real persistent/nonpersistent workers, seals cancellation at quarantine commit and increments the cached epoch only after detachment.
Normal provision renders the complete recipe and checks current readiness/manifest/Pixi/optional supplied lock before the replace flag; a matching generation is deliberately reused.
This corroborates B-F001's actual force-current red and the PLAN-ONLY same-injected-wrapper public remove→provision direction.
Wrapper close/removal failure must prevent provisioning; a selected destructive rebuild may require explicit retry and carries no atomic old-generation rollback promise.
No directory deletion or nonce recipe is authorized.

Full runner/Pixi/manifest/local-source/descriptor-identity/journal/readiness/cancellation/failure branches corroborate ROOT-F069's retained failed physical cleanup owner gap and ROOT-F071's final supplied-lock reattestation gap, without duplicate IDs.
The channel-qualified renderer branch remains unreachable for supported EnvironmentSpec input, as the parent's full spec/dependency guide review established.
The exact manager close registration/thread-start rollback, current-generation worker lookup, bounded serialized deadline and operation-listener close refusal remain useful structures to preserve.

#### B-F193 — P2/P3 qualified installer staging/publication ownership

`data/code_server_install.py::main` constructs staging/download paths from the PID, and `extract` starts with `staging.mkdir(parents=True)`.
The outer finally unconditionally removes staging, including when an existing staging directory made that mkdir fail before the invocation acquired ownership.
Direct same-process concurrent helper calls, reused PID leftovers or a pre-existing conventional staging name therefore lack an explicit acquired-target distinction.
After successful verified extraction, main removes the destination before `os.replace(staging, destination)`; a publication failure can lose an earlier destination without a retained backup.
These are qualified helper ownership/failure semantics, not a demonstrated deletion or untrusted HTTP target exploit.
The real editor caller supplies a fixed relative destination inside a newly provisioned generation, uses pinned release bytes and the Wetlands lifecycle gate; these materially limit the normal path.
Root's complete installer tests cover verified extraction, reuse, bad digest/download/layout/missing entrypoint and normal relative prefix resolution, without an existing staging collision or failed final publication oracle.
Future policy should decide whether this standalone helper promises prior-runtime preservation and acquire its staging explicitly; preserve the normal destructive selected-generation semantics and do not impose universal rollback.

#### B-F194 — P3 conditional installer reuse health/oracle gap

`already_installed` requires package.json plus a stamp matching only the archive digest, then main reports successful reuse before checking the actual launch entrypoint.
A direct helper invocation with the same digest and a missing launch file can therefore report already installed; changing only installer-revision does not affect that predicate either.
The normal platform matching-generation path may skip post-install entirely, so this is a narrow helper health/metadata policy, not proof of a currently broken code-server deployment or a requirement to re-download every launch.
The current reuse test preserves a marker after an initially valid install and does not remove the entrypoint or change only the installer revision.
Retain genuine extension-preserving reuse; clarify required installation-stamp/health guarantees before any diagnostic or repair.

#### B-F195 — P2 qualified public manager reverse-epoch resource ownership

`EnvironmentManager.provision` captures `initial_epoch` before starting its operation, and after real provisioning returns skips caching the returned environment when removal changed that epoch.
That protects a late old-generation result, as the complete `test_removal_epoch_prevents_late_provision_cache_publication` oracle deliberately demonstrates with a monkeypatched delayed provision returning the removed old generation.
The reverse legitimate sequence differs: a provision captured the old epoch but is delayed before taking the lifecycle gate; remove completes; real provision then creates a fresh current generation; its returned valid handle is omitted from `_environments` because the original epoch differs.
`ManagedEnvironment.start/spawn` validate the current generation under the lifecycle gate and track pools/processes on that handle, while manager.close snapshots only cached environments.
A resource created through that valid returned handle can consequently lack the manager's close-owned cache membership, even though the public worker registry still protects subsequent removal.
No physical survivor, worker start or concurrent schedule was executed; this is a source-derived conditional public ownership candidate.
The platform/BioImageFlow shared lifecycle guard mitigates ordinary same-wrapper calls; it is not a default Run failure claim or argument for a universal coordinator.
Future distinguishing oracle must preserve late-old-generation nonpublication while checking fresh-post-remove handle resources and manager close ownership; investigate ownership registration rather than simply deleting the epoch guard.
Targeted ManagedEnvironment caller tracing adds no duplicate full-file credit to the parent's checkout source judgment.

### Explicit asset classification

`assets/app_icon.icns` is an opaque generated platform artwork container, not human-authored application code.
Static inspection verified the 140,190-byte ICNS declared length, table of contents and all eight PNG chunk bounds through exact EOF.
The ic10 payload declares 1024×1024 and was copied unchanged to a temporary PNG for visual inspection: inset microscope artwork with transparent margin.
The complete borrowed `scripts/generate_desktop_icons` producer names `logo/microscope.svg` as source and writes/validates the 1024-square inset macOS artifact; desktop.py's targeted Darwin consumer loads this resource through NSImage, and backend packaging explicitly includes it.
Root's complete desktop counterpart selects the platform-specific format; no native icon launch or generator regeneration was run, and byte reproducibility is not claimed.
The generator and desktop source retain their separate full-file owners.

All T1 WIP, historical runtime artifacts and force-wrapper plan remain preserved.
M1 remains OPEN, and all implementation, diagnostics and runtime acceptance remain held.

## Final frozen-source reconciliation, pending current-control acceptance

All source owners have completed their assigned frozen inputs; no product fixes, new tests or application/native execution occurred during this full-review phase.
The architecture audit contains the cross-subsystem prioritized decision backlog and proportionate test/docs workflow, preserving every canonical candidate and its uncertainty here.
A dedicated independent reviewer samples other owners' sources/oracles and classification/method; B cross-checks A independently to avoid self-acceptance.
Seven current controls, including the changed audit and this register, still require exact final-content acceptance; source completion alone does not close M1.
The generated ledger self-input uses its explicitly documented canonical self-cell placeholder SHA256, and the late installed Wetlands identity is current evidence rather than retrospective baseline equality.

## M1 terminal review acceptance — 2026-10-01

All 1,799 agreed-scope inputs are accepted: 1,649 complete human reviews, 150 justified classifications and zero pending/unmatched/current-hash mismatches.
The nine current human controls were read fully against exact snapshots and every terminal delta; the generated ledger was classified through complete membership/producer reconciliation and its documented self-cell hash convention.
Independent method/completeness acceptance samples other owners, with B separately cross-checking A; it does not claim a second full human read of all inputs or independent reproduction of every candidate.
The 573 canonical candidates remain qualified future actions, with cross-subsystem priority/dependency decisions in the architecture audit and the next retrospective/M2 queue in the checkpoint.
M1 review is COMPLETE; no product or runtime certification, blanket fix approval or desktop acceptance follows from it, and native execution stays final M5.
