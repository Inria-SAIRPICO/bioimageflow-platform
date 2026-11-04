---
orphan: true
---

# Proposal: preserve DataFrame column metadata and asset references

Status: proposed design, not implemented behavior or a replacement for the normative platform and library specifications.
This document proposes a bounded mechanism for preserving typed image columns through ordinary table operations.
Implementation would require coordinated public library contracts and platform integration; this documentation task changes neither runtime behavior nor existing specifications.

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

### Concatenation and conflicts

Concatenation needs an explicit compatibility policy, but not a general inference engine.
The first implementation can preserve equivalent descriptions, allow a small documented set of safe widenings, and report incompatible known types.
For example, differing image layout constraints could eventually have a documented common representation, but such widening must not assert facts that are false for some rows.
Absent columns introduce nullability according to the table operation's existing behavior.

Incompatible known column types should produce an actionable diagnostic instead of silently becoming strings.
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

At execution time, the library resolves the reference into the path needed by an existing processing tool.
That private resolved path is an execution detail and must not replace the durable asset reference in the user-facing result.
Selection and joins preserve references without copying image bytes or changing asset ownership.
Stored references must retain the original assets through the library's normal result-retention and bundle mechanisms.
Deletion, unavailability, and export/import must not leave an apparently usable reference that silently resolves to another record.

The platform presents a readable filename or relative asset path and resolves image, thumbnail, Reveal, and viewer requests against the captured identity.
Resolution must preserve existing manifest admission, containment, deployment-mode restrictions, and unavailable-result behavior.
An asset reference is not permission to read arbitrary server files.
External input files retain their existing external-file policy and must not be falsely represented as owned result assets.

## Preserve portable viewer requirements, not local preferences

Column transformations should carry the existing portable viewer declaration when the underlying image meaning is unchanged.
This includes supported reader information and declared package or version requirements where present.
Captured result metadata remains the authority when a viewer action is invoked.

Registered environments, installed-package inventories, favorites, and one-shot viewer choices remain platform-owned state.
They are not copied into result metadata or automatically inherited as favorites for a newly created structural output.
Preserving a portable viewer requirement does not authorize installing packages or launching a viewer during passive table inspection.

## Custom tools and unknown metadata

Automatic preservation cannot be safe for arbitrary Python code that can replace values, change column meanings, or introduce unrelated strings.
Custom dataframe tools need a small opt-in contract: identify preserved columns, provide a rename map, or declare new output columns and their metadata.
A tool that changes an existing column's meaning must replace or invalidate its old description.
For dynamically generated columns, a supported metadata callback may derive descriptions from input descriptions and parameters without scientific execution or arbitrary image inspection.
Its exact public API is an implementation decision.

A tool without such a declaration may continue to execute under the existing dynamic-output contract, but unsupported metadata remains explicitly unknown.
Do not claim to infer arbitrary transformations, and do not automatically preserve metadata solely because an output column happens to keep an input column's name.

## Ownership and implementation sequence

1. Define the finite column-description and asset-reference propagation contract in the BioImageFlow library, reusing existing public schema and storage mechanisms.
2. Implement explicit rules for `SelectColumns`, row-preserving filters, joins, `Concat`, and pass-through outputs in the common tools and execution layer that own their semantics.
3. Persist the effective result descriptions and references through normal publication, cache reuse, and result-bundle export/import.
4. Expose those captured facts through the platform result services and existing typed table APIs, regenerating frontend API types if the transport changes.
5. Keep the Node Data UI as a consumer of those facts: readable asset labels, working image actions, and clear unresolved metadata diagnostics.

Start with selection and renaming as the smallest complete vertical slice, then add the other standard operations.
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
- Conflicting known types are reported; unknown types and viewer conflicts do not silently inherit unrelated declarations.
- New ordinary string columns remain strings even when their values resemble image filenames.
- The same preserved image actions work after cache reuse, application restart, and supported result-bundle export/import.
- Changing or removing the current tool installation does not change how an existing captured result is interpreted.
- Missing or rejected assets produce the existing typed unavailable response rather than resolving another record or exposing an internal path.
- No standard selection, rename, or merge needs to inspect image bytes, copy those bytes, provision a viewer, or execute scientific callbacks to propagate metadata.
- The Synthetic Cells workflow retains image behavior in its selection, summary, join, and concatenation tables, as checked in the actual Node Data panel in addition to execution and numerical checks.

## Complexity assessment

This is a bounded engineering change if the scope stays at explicit standard-operation contracts, captured column descriptions, and existing asset identities.
Most operations are dictionary selection or renaming plus the same row mappings already used for the dataframe values.
Concatenation compatibility, cross-record asset retention, and serialization are the main design work and require focused tests.

The complexity would grow substantially if the system tried to interpret arbitrary pandas programs, recover image semantics from path strings, or reconstruct provenance from private directory names.
Those mechanisms are unnecessary for the reported problem.
The central requirement is simple: ordinary operations that preserve a column's meaning must preserve the metadata that makes that meaning usable.
