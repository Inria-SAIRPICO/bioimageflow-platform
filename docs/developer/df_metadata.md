---
orphan: true
---

# Proposal: preserve DataFrame column metadata and asset references

Status: proposed design, not implemented behavior or a replacement for the normative platform and library specifications.
This document proposes a bounded mechanism for preserving typed image columns through ordinary table operations.
Implementation would require coordinated public library contracts and platform integration; this documentation task changes neither runtime behavior nor existing specifications.

For a standalone introduction, proposed tool APIs, runtime schema completion and platform change estimates, read [Typed DataFrame transformations](dataframe-output-contracts.md).
That guide owns the author-facing API; this proposal owns the asset propagation and storage safeguards.

## Problem and motivating example

In the Synthetic Cells feature-test workflow, the raw segmentation branch produces a `labels` column declared as `ImageFile`, with label-image semantics and a usable asset reference.
The Node Data panel displays the image as an asset with a readable record-relative path such as `assets/cells_raw_threshold_labels_split.tif`.
A `SelectColumns` node selects that column and renames it to `tile` before stacking several label images for `Mosaic`.
Its displayed output becomes a string containing an absolute private cache path, and the image actions disappear.
Similar degradation can occur in the summary and merge tables.

The selection node was intended to standardize the column name before concatenation, not to change the image, copy its bytes, or convert it into text.
Using `labels` and a name such as “Select Labels for Mosaic” would make the workflow clearer, but changing names alone cannot restore lost metadata.

The inspected platform result reader takes types and viewer declarations from the captured producer declaration and falls back to value inference for undeclared dynamic outputs.
`SelectColumns` has a dynamic output schema, so a path represented by a string can consequently be presented as `str`.
The relevant presentation code is in `backend/src/bioimageflow_server/services/result_store.py`, with table projection in `services/data_table_projection.py` and image-action gating in `frontend/src/components/panels/NodeDataTable.vue`.
The repair should preserve captured-result authority rather than borrow metadata from the current tool registry.

## Existing contracts and scope

The design must extend these contracts rather than assume they already preserve dynamic metadata:

- The library's `DataFrameTool` lifecycle has two stages: `merge_dataframes` followed by `transform`; the default merge is an inner join on index, not an identity operation.
  Its existing `Outputs`, `Passthrough`, `resolve_outputs`, and `resolve_merge_schema` facilities provide construction-time declarations, but do not by themselves prove runtime cell provenance.
- The current library storage specification treats `DataFrameTool` path outputs as external references and prohibits mixing owned assets and external paths within one logical column.
  Propagating references to upstream owned assets therefore requires an explicit versioned library storage extension, not merely attaching more schema information in the platform.
- The platform pins inspection to `(run_id, node_key, result_key, record_id)` and resolves owned paths through the selected record's public manifest API.
  A transformed table needs to preserve that inspection identity while resolving each referenced cell through its admitted origin.
- The platform's workflow-and-results export is currently an export artifact; importing that outer bundle is explicitly unsupported in platform specification v2 Section 12.
  Library bundle round-trip tests do not imply a new platform import feature.

These constraints come from the library specification Sections 3.5, 5.3, 6 and 7 and its `reference/output_cache_storage.md`, plus `platform_specs_v2.md` Sections 12 and 13.
The optional library source checkout is useful design evidence; implementation must verify the public APIs against the dependency versions selected by the platform lockfile.

The first release should cover scalar file-backed image cells passed through selection and renaming within one workflow storage authority.
It should preserve existing ordinary table values, ordering, indices, nulls, and numerical results.
Shared arrays, images nested inside containers, aggregation, automatic semantic inference, and references across independent workflow stores are outside that first slice.
Existing behavior for those values must remain supported; they do not gain the new preservation guarantee until their ownership rules are separately specified and tested.
Later joins and concatenation use the same contract once their additional acceptance gates pass.

## Desired invariant

Selecting, renaming, filtering, reordering, joining, or stacking existing columns should preserve their known meaning and the identity of referenced assets according to explicit operation rules.
A column becoming unknown after arbitrary computation is legitimate; selecting or renaming a known column must not make it unknown.
Execution success alone is insufficient acceptance: intermediate Node Data tables must retain image previews and actions without exposing private storage paths as ordinary cell text.

## Keep column descriptions separate from values

A result should carry its DataFrame together with an immutable, serializable description of its columns.
The following is illustrative notation, not a new wire format:

```yaml
columns:
  labels:
    type: ImageFile
    image:
      semantics: [label]
      layouts: [YX]
    viewer: null
```

Reuse the existing canonical type descriptors, `ImageSpec`, and portable viewer declarations instead of inventing parallel definitions.
The column description should retain applicable nullability and other declared field facts as well as the image and viewer information.
Field presence and cell nullability are distinct: an outer join can keep a required output column while introducing null cells.
An empty or all-null result retains its known declaration; lack of observed values is not evidence of a different type.
Distinguish unavailable metadata from a known ordinary string type and from a known absence of optional viewer requirements.
A missing description must not be silently upgraded to an image declaration because a value ends in `.tif`.

Here, image metadata means the declared image contract, including semantics, supported layouts, dtypes, and formats where available.
Measured dimensions, physical pixel sizes, and other file-specific facts remain the responsibility of the image reader and its existing metadata facilities.
They need not be duplicated in every result column description.

Store the effective column descriptions with the exact immutable result, including dynamic outputs resolved for that execution.
Cache hits, reopening, retained inspections, and result-bundle export/import should use that captured description.
Changing or uninstalling a tool later must not reinterpret an old result.
Do not make pandas dtype inference or incidental propagation of `DataFrame.attrs` the authority for this contract.

## Use explicit propagation rules

Standard table tools should describe how their outputs relate to their inputs.
The execution layer can apply a small set of metadata transformations alongside the existing value operations.
It does not need to analyze pandas code or inspect image bytes.

| Operation | Column metadata rule | Asset-reference rule |
| --- | --- | --- |
| Select columns | Retain descriptions for the selected columns. | Retain references for the selected cells. |
| Rename columns | Apply the same rename map to description keys. | Preserve references unchanged. |
| Filter, sort, or reorder rows | Preserve the column descriptions. | Apply the same row selection or permutation to references. |
| Join or cross join | Carry descriptions from both inputs, using the actual collision and suffix rules. | Carry or duplicate references according to the resulting rows. |
| Concatenate rows | Reconcile descriptions for each output column. | Retain each cell's original asset identity. |
| Pass-through table writer | Preserve descriptions for unchanged returned columns. | Preserve references; serialize file exports through a separate export policy. |
| New or replaced column | Use a declared or explicitly derived description; otherwise mark it unknown. | Require an explicitly supported reference for asset-valued outputs. |

For `labels → tile`, the metadata operation is simply to move the existing description from the key `labels` to the key `tile`.
The image remains the same asset.
A semantic change, such as converting labels into an intensity image, requires a new output declaration rather than blind metadata inheritance.

### Alignment and declaration precedence

Propagation must cover both lifecycle stages, using the actual operation's input slots, resolved output names and row mapping.
Do not replay a pandas join independently to reconstruct references, match equal path strings, or assume that equal index labels establish provenance.
For each preserved output cell, the operation must identify the corresponding input cell, or explicitly indicate an introduced null; many-to-many joins duplicate that mapping along with the values.
A null cell has no asset reference.
Join-key coalescing needs the same per-cell origin rule as payload columns, including right-only rows in outer joins.
Unsupported duplicate or non-string column labels must follow existing table validation, never collapse silently when metadata keys are stringified.

Use the captured explicit output declaration for a newly computed or replaced column; inherit only for columns the operation explicitly preserves.
When an explicit declaration contradicts a claimed preservation rule, report a contract violation rather than arbitrarily choosing one.
Validate output names, mapping bounds, null positions and reference shape against the actual returned table before publication.
This verifies structural consistency, not the truth of arbitrary custom scientific code.
The existing `Passthrough` marker alone must not authorize references for values that a custom transform replaces.
Construction-time projection and execution-time propagation must share the same declarative rules, and unknown static schemas must remain unresolved until execution provides evidence.

### Concatenation and conflicts

Concatenation needs an explicit compatibility policy, but not a general inference engine.
Initially preserve canonically equivalent descriptions and widen nullability only when the operation introduces missing values; other widenings require their own specified compatibility rules and tests.
For example, differing image layout constraints could eventually have a documented common representation, but such widening must not assert facts that are false for some rows.
Absent columns introduce nullability according to the table operation's existing behavior.

Incompatible known column types should produce an actionable metadata diagnostic and an unresolved effective description instead of silently becoming strings.
A metadata conflict alone must not turn an otherwise valid existing concatenation into an execution failure.
Preserve the values and independently valid references, but withhold actions requiring a proven column contract.
An explicit output contract violation, invalid reference, or existing downstream type-validation failure remains an error; compatibility does not permit publishing corrupt authority.
When an input's description is unknown, retain that uncertainty rather than treating another input's declaration as proof about its values.
Unknown columns must not acquire authoritative image actions until their asset and type contracts are established.

Optional viewer declarations can be reconciled independently of the image type.
Equivalent known requirements can be preserved.
If viewer requirements differ or cannot be established for the whole column, keep the compatible image type and asset references but mark viewer requirements unresolved, with an explanation.
Do not silently take the first declaration or union package and reader requirements that may be incompatible.
Per-row viewer declarations can remain outside the initial scope.

## Preserve asset identity independently of the column name

Knowing that a column is `ImageFile` is necessary but does not identify the owner of a relative path.
A concatenated column may contain images produced by several different result records, all with an `assets/…` path.
Resolving every cell against the concatenation node's record would be incorrect.

Each asset-valued cell therefore needs an authoritative reference to the original asset.
Conceptually, that reference identifies the producing immutable result and its manifest-relative asset path:

```text
producer result: <captured result identity>
asset: assets/cells_raw_threshold_labels_split.tif
```

Reuse the library's existing public result identities, asset manifests, and resolution APIs wherever they already express this relationship.
This notation does not prescribe a new JSON cell object, storage layout, or access to private cache internals.
If a public contract is missing, extend it at the library boundary instead of teaching the platform to parse cache paths.
References may be represented by compact handles with a deduplicated origin table; copying full provenance into every cell is unnecessary.
The mechanism only needs the origin required to identify and resolve the referenced asset, not the complete ancestry of the computation.

At execution time, the library resolves the reference into the path needed by existing DataFrame and processing tools, preserving their current Python call signatures and expected value types.
Do not require tool code to accept a new handle object or add hidden columns that alter user table operations.
That private resolved path is an execution detail and must not replace the durable asset reference in the user-facing result.
Selection and joins preserve references without copying image bytes or changing asset ownership.
Stored references must participate in the library's result-retention and bundle mechanisms; existing upstream provenance alone is not proof that those mechanisms retain or export the needed assets.
The reference locator must use immutable record/asset identity within the admitted storage authority, not a run ID, node name, `current` pointer or `latest` path.
Run identity remains inspection provenance and does not enter scientific cache identity.
Deletion, unavailability, and export/import must not leave an apparently usable reference that silently resolves to another record.

The platform presents a readable filename or relative asset path and resolves image, thumbnail, Reveal, and viewer requests against the captured identity.
Resolution must preserve existing manifest admission, containment, deployment-mode restrictions, and unavailable-result behavior.
An asset reference is not permission to read arbitrary server files.
External input files retain their existing external-file policy and must not be falsely represented as owned result assets.

### Publication, cache identity and lifetime

The library must publish the DataFrame, effective descriptions, cell references and dependency declarations as one admitted immutable record.
A separate mutable metadata file written after record publication is not acceptable.
Malformed present metadata or mismatched cell references are corruption, not legacy absence or permission to fall back to inferred image types.
Concurrent publishers must return the selected winner's values and metadata together; the losing candidate's descriptions cannot decorate a cache hit.

Before implementation, specify which canonical descriptors and references participate in the logical record digest, output-contract version and result-key material.
A changed propagation rule or semantic output declaration must not select a record created under incompatible rules.
Reuse the existing cache versioning machinery; do not hash absolute paths, local viewer preferences or run IDs, and do not add runtime results to the editable graph's artifact hash.
Portable viewer requirements must retain the existing separation from scientific cache identity while remaining bound to the admitted retained result.
Old results must never be relabeled with a newer propagation contract on read.

References introduce storage dependencies even when no downstream pixel computation consumes them.
Before enabling them, demonstrate that cache invalidation and Clear remove reusable selections/disposable views without deleting assets still needed by retained downstream records.
Specify the root set and release behavior for explicit storage cleanup; this proposal does not require a background garbage collector.
Capture referenced dependencies under the library's publication and export lifetime rules so concurrent cleanup cannot publish a successful but incomplete record or bundle.
A missing, corrupt or inaccessible origin remains unavailable, even if a newer result has the same filename.

Bundle export must include the referenced dependency closure, including assets from upstream cache hits produced in older runs, and validate it before destination publication.
Import or relocation through supported library APIs must preserve logical identity without retaining source-machine paths or consulting the original store.
Reject cycles or unsupported reference chains at admission; prefer direct original-asset locators to repeated resolution through every intermediate table.
Directory-backed images require the existing complete directory-asset manifest checks; supporting them is a separate gate if the first slice supports files only.
External files keep their current non-self-contained export policy and cannot be silently promoted to bundle-owned data.

### Selected-cell resolution and table presentation

The browser should address a cell by the displayed table's pinned result, output key and source-row position.
The backend derives its origin from that admitted table; accepting an arbitrary origin locator from the client would bypass the table's authority.
Sorting, filtering, pagination, continuous scrolling and merged projections must retain that source-cell mapping.
Keep the selected output's viewer requirements and preference identity separate from the original asset's storage location: opening `tile` does not inherit favorites from `labels`.
The existing projection alignment rules remain unchanged; metadata preservation does not justify merging tables whose row lineage is ambiguous.

Readable asset labels must be derived without rewriting the scientific values supplied to tools.
All image actions must use the same reference resolver, including thumbnails, browser image access, desktop Reveal and external viewers.
A descriptive filename is not an actionable path, and unresolved viewer requirements must not be serialized as known `null` requirements.
Plain CSV needs an explicit documented policy for reference labels or materialized assets; human-readable labels alone are not a portable round trip.

## Preserve portable viewer requirements, not local preferences

Column transformations should carry the existing portable viewer declaration when the underlying image meaning is unchanged.
This includes supported reader information and declared package or version requirements where present.
Captured result metadata remains the authority when a viewer action is invoked.

Registered environments, installed-package inventories, favorites, and one-shot viewer choices remain platform-owned state.
They are not copied into result metadata or automatically inherited as favorites for a newly created structural output.
Preserving a portable viewer requirement does not authorize installing packages or launching a viewer during passive table inspection.

## Custom tools and unknown metadata

Automatic preservation cannot be safe for arbitrary Python code that can replace values, change column meanings, or introduce unrelated strings.
Custom dataframe tools need a small opt-in contract: identify preserved columns and their row mapping, provide a rename map, or declare new output columns and their metadata.
A tool that changes an existing column's meaning must replace or invalidate its old description.
For dynamically generated columns, a supported metadata callback may derive descriptions from input descriptions and parameters without scientific execution or arbitrary image inspection.
Normalize existing `resolve_outputs` and `resolve_merge_schema` contracts through the unified schema adapter described in the companion guide.
A new `resolve_schema` opt-in must reject competing declarations rather than create a second authority; callbacks retain the pure, deterministic, no-I/O contract and participate in executable/output-contract versioning.

A tool without such a declaration may continue to execute under the existing dynamic-output contract, but unsupported metadata remains explicitly unknown.
Do not claim to infer arbitrary transformations, and do not automatically preserve metadata solely because an output column happens to keep an input column's name.

## Ownership and implementation sequence

1. Define the finite column-description and asset-reference propagation contract in the BioImageFlow library, reusing existing public schema and storage mechanisms.
2. Implement explicit rules for `SelectColumns`, row-preserving filters, joins, `Concat`, and pass-through outputs in the common tools and execution layer that own their semantics.
3. Persist the effective result descriptions and references through normal publication, cache reuse, and result-bundle export/import.
4. Expose those captured facts through the platform result services and existing typed table APIs, regenerating frontend API types if the transport changes.
5. Keep the Node Data UI as a consumer of those facts: readable asset labels, working image actions, and clear unresolved metadata diagnostics.

Start with selection and renaming as the smallest complete vertical slice, including cold execution, cache reuse, publication, lifetime, export and the actual Node Data actions.
Do not ship image-action enablement before durable reference admission and resolution are complete.
Keep the feature gated until the library/Core, common-tools and platform dependency versions implement the same contract; old tools remain executable with their existing metadata limitations.
Then add the other standard operations independently, with evidence for each operation's value and reference mapping.
If retention or portable export cannot support cross-record references safely, defer release of that preservation guarantee rather than add untracked paths or silently copy bytes during ordinary table operations.
Do not implement separate frontend schema inference or a platform-only metadata sidecar with an independent lifecycle.
Construction-time output schemas may project facts already known from the same rules, but scientific execution must not run merely to discover a schema.

The implementation must decide how retained older results without dynamic column descriptions remain readable.
Keep their current limitations explicit; do not rewrite immutable records or retrospectively invent image semantics from filenames or the current catalog.
Any new stored or transported representation needs the library's normal versioning and compatibility treatment.
CSV exports are an interchange surface and need a deliberate asset-export policy; a CSV alone does not preserve typed image references.
A plain table export should not silently bake private cache locations into a supposedly portable deliverable.

## Acceptance criteria

- Selecting and renaming a label-image column preserves its type, declared image contract, compatible portable viewer requirements, and original asset identity.
- Filtering, reordering, and joining rows retain the correct reference for every resulting cell, including duplicated rows.
- Concatenating assets from two different records with the same relative filename still opens the correct image in each row.
- Conflicting known types produce explicit unresolved metadata without failing otherwise valid table operations; unknown types and viewer conflicts do not silently inherit unrelated declarations.
- New ordinary string columns remain strings even when their values resemble image filenames.
- The same preserved image actions work after cache reuse and application restart; supported library bundle round trips preserve the descriptors and asset resolution after relocation without access to the original store.
- Platform result export preserves referenced assets; the existing refusal to import the outer workflow-and-results bundle remains unchanged.
- Changing or removing the current tool installation does not change how an existing captured result is interpreted.
- Missing or rejected assets produce the existing typed unavailable response rather than resolving another record or exposing an internal path.
- No standard selection, rename, or merge needs to inspect image bytes, copy those bytes, provision a viewer, or execute scientific callbacks to propagate metadata.
- The Synthetic Cells workflow retains image behavior in its selection, summary, join, and concatenation tables, as checked in the actual Node Data panel in addition to execution and numerical checks.

### Regression and release gates

The implementation tests must establish both preservation and unchanged behavior:

| Area | Required evidence |
| --- | --- |
| Table semantics | Compare actual values, dtypes, order and indices before/after the change; cover empty/all-null inputs, introduced nulls, suffix collisions, many-to-many joins and concat with missing columns. |
| Lifecycle | Exercise default merge followed by transform, merge-only tools, custom replacements and unknown outputs; no reference inheritance by column name alone. |
| Record authority | Cold publication and cache hits agree; incompatible contract versions cannot reuse stale metadata; concurrent publication uses the winner's metadata; malformed present metadata fails closed. |
| Asset lifetime | Clear/invalidate an origin, reopen retained downstream output, export cached origins from older runs, relocate the bundle, and verify explicit cleanup behavior and failed-export recovery. |
| Security and UI | Reject forged origins, traversal and symlink escape; test both deployment modes and pinned cells after sorting, filtering, pagination and merged projection. No passive viewer provisioning. |
| Compatibility | Old records remain readable with documented limitations; old/custom tools keep their table behavior; declared new outputs still use existing runtime validation. |
| Cost | Measure representative large tables and repeated references for metadata size, publication/load time and visible-page reads; avoid per-cell storage reads, whole-file image inspection and unbounded provenance duplication. |

Use library storage/contract tests and common-tool operation tests first, then focused platform service and browser tests through `scripts/test`.
A real Wetlands processing consumer must receive the correct paths for cells from different origins; Direct-only evidence does not certify the worker boundary.
If managed distributed execution can encounter the new format, explicitly run its result-transfer tests or refuse that unsupported format before dispatch; local tests alone do not certify remote portability.
Record the tested versions and scope; a documentation build validates this proposal's rendering, not its implementation safety.

## Complexity assessment

The schema-selection rules are small, but this is not solely a metadata or UI fix.
Cross-record references extend storage ownership, logical identity, export and cleanup behavior, and row mappings must be supplied by the operation rather than reconstructed from its result.
The scope is manageable only if the initial operation set stays narrow and the storage, compatibility and lifecycle gates are met before expanding it.
These gates reduce regression risk; they do not prove the absence of all possible defects.

The complexity would grow substantially if the system tried to interpret arbitrary pandas programs, recover image semantics from path strings, or reconstruct provenance from private directory names.
Those mechanisms are unnecessary for the reported problem.
The central requirement is simple: ordinary operations that preserve a column's meaning must preserve the metadata that makes that meaning usable.
