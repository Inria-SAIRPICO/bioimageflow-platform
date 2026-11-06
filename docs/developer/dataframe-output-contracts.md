---
orphan: true
---

# Design proposal: typed DataFrame transformations

Status: proposed API and behavior, not a released feature.
This guide explains the design from first principles and defines an implementable direction for the BioImageFlow library, common tools and platform.
Names introduced below are proposed Python API names, not imports users can run today.
Existing mechanisms are identified explicitly; implementation must update the normative specifications before changing their contracts.

Read this guide first for the authoring model and platform experience.
The companion [DataFrame metadata and asset references proposal](df_metadata.md) defines the deeper storage, security and lifetime requirements.
This guide owns the proposed author-facing API; the companion owns asset propagation safeguards.
Neither document authorizes treating a proposal as implemented behavior.

## 1. What problem are we solving?

A workflow connects tools into a graph: each node invokes a tool, and each edge supplies data to another node.
A DataFrame is a table with named columns and indexed rows.
One row might represent an image; its columns might contain a filename, an object count, and a segmentation result.

A segmentation result is often an image whose integer pixel values identify different objects.
It is useful to know that a column contains such label images, rather than ordinary text.
That knowledge lets the editor check connections and lets Node Data offer appropriate image actions.

Consider this workflow:

```text
Segment images                  Select and rename                  Mosaic
labels: label-image file   →     tile: label-image file        →    mosaic: label-image file
```

Selection changes the table's shape and column name, but leaves each selected image unchanged.
If the middle output is described merely as strings, useful information has been lost.
Conversely, if a custom tool replaces those paths with comments, keeping the image description would be incorrect.

We need explicit contracts that preserve what is known, replace what changes, and identify what cannot yet be known.
We do not need to interpret arbitrary Python programs.

## 2. Four concepts that must stay separate

| Concept | Meaning | Example |
| --- | --- | --- |
| Value | The data in a cell | `17`, or a path supplied to a tool |
| Column schema | What values a column promises to contain | Integer count, nullable string, image file with label semantics |
| Asset reference | Which stored file a cell identifies | An immutable producing record plus its manifest-relative asset path |
| Observed file metadata | Facts measured from an actual file | Width, height, physical pixel size |

A schema is a collection of column descriptions.
An output contract is the tool author's promise about its result schema, together with any explicitly supported preservation behavior.
An immutable record is a published result that is not edited in place; newer executions publish other records.
A cache hit reuses an existing admitted record instead of recomputing it.

Two rows can both contain `assets/mask.tif` while referring to different producing records.
Their column type can be identical, but their asset references must differ.
Similarly, two different images can have the same type without containing the same pixels.
Preserving a type is not evidence that values or asset identities were preserved.

Pandas attributes can carry descriptions temporarily, but incidental copying of those attributes is not a propagation contract.
The library must explicitly derive and validate the descriptions and persist them with the result.
No hidden columns or new handle objects should be injected into the pandas tables passed to existing tools.

## 3. Three ways to describe an output

The distinction is not simply between tools that change types and tools that preserve them.
A tool can completely change its input while producing a predictable output type.

| Contract | Example | When the schema becomes known |
| --- | --- | --- |
| Fixed | Object counting produces an integer `count` | Before execution |
| Derived | Selecting `labels` and renaming it to `tile` | Once input schemas and relevant parameters are known |
| Data-dependent | A pivot creates one column for each category found in the data | Partially before execution, completed during execution |

These cases can coexist in one table.
A tool can preserve `image`, add a fixed integer `count`, and add dynamically named measurement columns.
A global `preserves_types=True` flag cannot express that combination, its input source, or its row mapping.
The existing `Passthrough` declaration remains a useful convenience for schema inheritance, but must not imply asset-reference inheritance.

The general lesson from typed workflow systems is to declare contracts at operation boundaries and validate their use.
Galaxy's explicit input-derived output formats and metadata, and Flyte's declared structured-dataset columns, are useful precedents; neither is evidence that arbitrary scientific Python can be understood automatically.
See [Galaxy tool authoring](https://docs.galaxyproject.org/en/release_26.1/dev/user_defined_tools_authoring.html) and [Flyte structured datasets](https://docs-flyte-legacy.union.ai/en/v1.13.1/user_guide/data_types_and_io/structureddataset.html).
This proposal applies that principle to BioImageFlow's existing recursive graph and immutable results.

## 4. Existing foundations and actual gaps

The inspected platform checkout selects published BioImageFlow 0.10.0 and Core 0.6.0.
The local library source is design evidence; package compatibility must be verified against the versions actually selected by the backend lockfile during implementation.

Existing facilities include `Outputs(IOModel)`, `Outputs(Passthrough)`, pure `resolve_outputs` and `resolve_merge_schema` callbacks, and the library's resolved output schema representation.
DataFrame tools currently execute `merge_dataframes(dfs, arguments)` and then `transform(df, arguments)`.
The default merge combines inputs by index; it is not generally an identity operation.
Processing tools have their own declared output model and do not automatically carry upstream columns forward.

In the inspected library, `ResolvedSchema` can hold known ports with a dynamic state, but its `to_wire()` returns `None` for that state.
The platform's `NodeOutputSchemaResponse` exposes `resolved` and `columns`, so preserving partial information and explaining uncertainty needs an explicit transport contract.
Modern result inspection already uses captured producer metadata rather than the current tool catalog, which is the correct authority to extend.

Core 0.6 also distinguishes exact writable templates, returned path references and generated file families.
The proposed schema helpers must preserve these distinctions: inheriting a path column does not grant permission to write to the original file or create a new template owner.
A transformed output's description of a readable reference is separate from the original producer's write-time ownership declaration.

The missing work is coherent partial-schema propagation, optional runtime schema completion, supported value/reference-preserving operations, and durable publication of their effective contracts.
This is more than adding a flag to the frontend.

## 5. Schema model and precise rules

Introduce an immutable `TableSchema` public facade over the existing canonical descriptors, not a second type system.
`ColumnSpec` below is a convenient author-facing wrapper around the current type, image, nullability and viewer descriptors.
The wire encoding must reuse those descriptors and use strict versioned models; it must never serialize executable Python annotations or callbacks as code.

A schema contains ordered named columns and an `open` flag:

- A closed schema (`open=False`) lists every possible output column; an absent name is known to be absent.
- An open schema (`open=True`) lists guaranteed or explicitly optional known columns but permits additional columns; an unlisted name is unresolved.
- A listed column may have an explicitly unknown type while its name and presence remain known.
- A known `Any` declaration deliberately accepts unrestricted values; unknown means insufficient information, not permission to claim compatibility.

Presence and nullability are independent.
An optional column may be absent; a nullable column may be present with missing cells.
A closed schema with zero columns is a known empty schema, not an unknown schema.
An empty table with declared columns retains those column types even when no values can be sampled.
Diagnostics such as “missing parameter”, “input schema unresolved”, and “incompatible concatenated declarations” accompany uncertainty without becoming scientific values.
Malformed declarations and callback failures are errors, not ordinary uncertainty.

Schema helpers return detached schemas and never mutate an upstream schema:

| Helper | Contract |
| --- | --- |
| `select(names)` | Output order follows `names`; known-absent names fail; unresolved names remain explicit unknown columns with deferred presence checks. The result has a closed set of names. |
| `rename(mapping)` | Renames descriptions with exactly the value operation's rules; collisions fail before publication. Known-absent source names fail; unresolved names create deferred checks. |
| `with_columns(mapping)` | Adds or replaces descriptions; replacement discards the old column's semantic claims and preservation mapping. |
| `TableSchema.closed(mapping)` | Declares an exact set of columns, including an empty set. |
| `TableSchema.open(mapping)` | Declares known columns while allowing more; default listed columns are required. |

Nullability is widened only when the value operation can introduce nulls.
Types use the library's existing compatibility rules; do not introduce implicit conversions or silently coerce output values to make a contract pass.
For concatenation, initially retain equivalent canonical descriptions and necessary nullability widening only.
A conflict becomes unresolved metadata with a diagnostic if the underlying table operation is otherwise valid.
It becomes an execution error only when a required explicit output or downstream contract cannot be satisfied.
Image/viewer conflicts never select the first input's declaration arbitrarily.

## 6. Author API for fixed and derived schemas

Fixed outputs continue to use the existing model style:

```python
class CountObjects(DataFrameTool):
    class Outputs(IOModel):
        count: int

    # Existing merge_dataframes / transform implementations produce the values.
```

Changing an image into a count does not need a type-transfer callback: `Outputs` already states the result.

For custom transformations whose schema depends on upstream schemas, propose this callback:

```python
@classmethod
def resolve_schema(cls, upstream, parameters) -> TableSchema:
    ...
```

The signature above denotes one whole-invocation callback: `upstream` is an ordered tuple of schemas for positional DataFrame inputs, and `parameters` contains validated constants or an explicit missing-parameter marker.
A missing parameter is different from an explicit `None`.
The callback sees no DataFrame values and performs no file access, scientific execution, environment provisioning or mutation.
It must be deterministic for the admitted tool code, schemas and parameters.
Trusted tool code is still trusted code; a purity requirement is not a Python sandbox.

For example, a custom single-input transform that returns the input columns plus an integer measurement declares:

```python
@classmethod
def resolve_schema(cls, upstream, parameters):
    require_input_count(upstream, 1)
    return upstream[0].with_columns({"count": ColumnSpec(int)})
```

This promises the final schema after both merge and transform.
It does not execute either stage, and it does not claim that `image` still references the same file.
A tool overriding both stages must describe their combined result; there is no automatic application of a default merge schema on top of this callback.
Fixed input arity in these examples is checked during graph validation as well as execution.

Only one schema authority is active per tool:

1. A structural operation tool described below derives its schema from its operation.
2. A custom tool opting into `resolve_schema` uses that callback and may not also define a competing `Outputs` or legacy schema override.
3. Unmodified tools retain the current `Outputs`, `Passthrough` and legacy callback resolution order through one adapter.

Ambiguous new declarations are rejected at tool admission, not resolved by silent precedence.
Keep legacy source compatibility during adoption; the adapter normalizes to `TableSchema` and does not create a parallel stored schema format.
Later deprecation of legacy callbacks is a separate release decision.

## 7. Structural operations: describe the work once

A schema callback and an independent pandas implementation can disagree.
For selection, renaming and other supported structural operations, the library should own both implementations from a single operation description.

Propose an opt-in `StructuralDataFrameTool` subclass with a pure `operation(parameters)` builder:

```python
class SelectAndRename(StructuralDataFrameTool):
    class Inputs(IOModel):
        columns: list[str]
        rename: dict[str, str]

    @classmethod
    def operation(cls, parameters):
        return SelectColumns(
            input_slot=0,
            columns=parameters.columns,
            rename=parameters.rename,
        )
```

This example requires exactly one upstream input.
The operation accepts a tuple of library-owned input result envelopes internally; an envelope contains the table, schema and admitted references.
It is not a new object passed to existing pandas tools.
The library uses the same operation to project schemas during editing and transform values, schemas and references during execution.
Incomplete parameters yield an unresolved projection without executing the operation; execution requires complete validated parameters.

This subclass deliberately replaces the old two-stage lifecycle for opted-in tools.
It must not also override `merge_dataframes`, `transform`, `resolve_schema`, or `Outputs`; admission rejects such combinations.
The operation consumes the original positional inputs directly, so no implicit inner join runs before it.
Existing DataFrameTool subclasses keep their lifecycle unchanged.
The operation is derived from admitted code and parameters rather than persisted as a second editable graph language.

For `columns=["labels"]` and `rename={"labels": "tile"}`, execution:

1. Selects the `labels` values and retains their existing order and index.
2. Names the output column `tile` and transfers its readable image contract.
3. Maps every non-null output cell to the original asset reference.
4. Publishes the output table and its effective schema/reference information together.

No image is read or copied to perform these transformations.
Subsequent filters use one selection vector for values and references; joins use one output-to-input mapping from the actual join, including duplicated and unmatched rows.
Do not perform a second join to reconstruct provenance.
The first implementation supports selection and renaming only; filter, join and concat operation constructors follow after their mapping and nullability tests pass.

A custom pandas tool can declare an accurate image type without being eligible to inherit asset references.
Initially, such a tool must use supported structural operations for preservation, or retain its existing reference limitations.
A general user-supplied provenance-map API is deferred; structural consistency checks cannot prove that arbitrary custom Python preserved the claimed values.

## 8. Data-dependent schemas and runtime completion

Suppose a pivot groups observations by sample and turns category names into columns.
Before reading observations, the tool knows it will return `sample: str`, but does not know whether the other columns will be `red`, `green`, or something else.
Its proposed static contract is:

```python
@classmethod
def resolve_schema(cls, upstream, parameters):
    return TableSchema.open({"sample": ColumnSpec(str)})
```

For this opted-in tool, the existing `transform` callback may return a proposed `TableResult` instead of a bare DataFrame:

```python
# Inside transform, after computing output_df and validating generated names:
actual_schema = TableSchema.closed({
    "sample": ColumnSpec(str),
    **{name: ColumnSpec(float, nullable=True) for name in category_columns},
})
return TableResult(dataframe=output_df, schema=actual_schema)
```

The example declares measurement columns as floating-point values; the implementation must actually produce compatible values.
Category names must be deterministic, unique, valid column names and must not collide with `sample`; reject collisions rather than overwrite a declaration.
No asset references are claimed by this example.
Validation can establish supported value types and admitted file ownership, but cannot prove an arbitrary author's scientific claim that pixel values represent labels without additional domain-specific checks.
Such checks remain the tool's responsibility; schema propagation must not read image bytes merely to discover a type.
`TableResult` is an execution return wrapper consumed by the engine, never a replacement for DataFrames supplied to existing tool callbacks.
Bare DataFrame returns remain valid for legacy tools and for new tools whose declared contracts can be checked without an explicit runtime schema.

Runtime completion follows strict rules:

1. The engine recomputes the custom schema callback using the actual admitted upstream schemas and the same captured tool code and parameters.
2. The returned schema must refine that contract: required names remain present, known types remain compatible, and a closed schema permits no extra columns.
3. Runtime declarations are checked against the actual column names, supported values, nullability and any required asset admission before immutable publication.
4. Concrete unknown portions may be completed; a contradictory known promise fails the producer with a scoped contract error.
5. Downstream consumers are checked against the completed schema before their scientific callbacks run.

An effective result has an exact set of column names, but some semantic descriptions may remain unknown.
Ordinary scalar dtype inference may assist presentation; it does not establish image semantics or owned-file identity.
Empty/all-null undeclared columns remain unknown unless the author supplies a declaration.
A downstream input requiring a semantic image contract refuses unresolved semantics before science; an unrestricted consumer may proceed.
Preserve legacy tools' existing validation behavior during migration instead of silently strengthening every old dynamic tool's runtime requirements.

This feature does not change graph topology during a run.
The user can name a prospective output column such as `red` in an edge; if it does not exist at runtime, that consumer fails validation before execution while successful upstream results remain inspectable.
Creating new nodes or edges automatically for discovered columns is outside scope.

## 9. What a platform user would see

When editing, the platform displays known columns immediately and marks data-dependent output sets as “Additional columns available after execution”.
Known incompatible connections remain rejected; unresolved compatibility is displayed as “Checked when upstream data is available”.
This is distinct from missing tools, invalid parameters, unavailable source code or broken graphs, which remain blocking errors.

A dynamic source needs an explicit “Connect named output” action accepting a column name and showing its deferred status.
This action creates an ordinary column edge, not a fabricated declared output.
The backend validates the endpoint, graph cycles and all known constraints as usual.
After execution, discovered names can be offered as suggestions qualified with the selected run; they do not become promises about a changed graph.
Existing edges remain present through refresh and Undo/Redo even when schema knowledge changes.

Run validates all statically decidable constraints first.
At each dependency boundary, the library resolves deferred constraints from that run's selected results before dispatching the consumer.
A cache hit supplies the same captured effective schema as a cold result and must pass the same consumer checks.
A runtime failure names the producer, consumer, column and expected/actual contract without silently dropping the edge or substituting another output.

Node Data uses the selected immutable result's effective schema, including when the graph or installed tool has since changed.
The editor uses the current accepted graph's schema projection.
These are different views with different owners; neither overwrites the other.
Nested workflows use the same rules through stable interface IDs and scoped node paths.
Pending responses remain bound to their originating graph revision, workflow generation and canvas/session.

Image actions require both an appropriate readable image contract and an admitted asset reference.
Unknown viewer requirements are different from a known absence of special requirements.
Thumbnails, browser viewing, desktop Reveal and external viewers resolve the selected cell server-side, retaining existing deployment restrictions and action-only viewer setup.

## 10. Storage and cache requirements

Type propagation alone can improve editor feedback, but it cannot safely restore all image actions.
A preserved image cell must retain its original record and manifest asset identity within the same workflow storage authority.
The selected output owns its schema and viewer preference identity; the original result owns the asset bytes.
Neither node labels nor private absolute cache paths can serve as durable origin identities.

Publish values, effective semantic descriptions, admitted reference mappings and dependencies as one validated immutable result.
Canonical semantic descriptors and references belong in logical record validation and identity under a versioned format.
Changes to propagation behavior must participate in executable/output-contract cache compatibility so old records cannot be silently reinterpreted.
Local viewer preferences and run IDs stay outside scientific cache identity; portable viewer declarations retain their existing separately captured viewing contract.
Concurrent publication returns the selected winner's complete result, never its values combined with the loser's schema.

Clear removes reusable selections and disposable latest views without breaking retained downstream references.
Export must include the referenced closure, even when an upstream cache hit came from an older run.
Supported library bundle relocation must work without the original storage root.
The platform's outer workflow-and-results bundle remains an export artifact, not a newly supported import format.
Missing or malformed origins fail closed; no same-filename fallback is permitted.
Older records retain their documented limitations and are not rewritten in place.

These requirements, including cleanup concurrency, containment and per-cell mappings, are detailed in the [asset proposal](df_metadata.md).
They are release prerequisites for reference preservation, not optional improvements after enabling image actions.

## 11. Change size and risk assessment

Sizes below describe engineering scope, not calendar estimates: small means a localized component, medium means several cooperating components, and large means a cross-layer contract or persistent format with lifecycle tests.
The complete feature is large; platform presentation alone is not the dominant cost.
A reliable schedule requires prototyping the immutable reference representation and export closure first.

| Work package | Size | Main changes | Main risk and control |
| --- | --- | --- | --- |
| Library schema model and adapters | Medium | Extend resolved schemas, retain partial fields, canonical helpers and callback admission | Divergent authorities or legacy regressions; normalize all paths into one model and test existing declarations. |
| Structural operation runtime | Medium for select/rename; large with joins/concat | Opt-in lifecycle, table/schema/reference mappings | Wrong image associated with a row; assert exact source mappings and unchanged values/index behavior. |
| Runtime completion and scheduling | Large | Admit TableResult, validate refinement, resolve deferred edges before dispatch | Science runs on incompatible inputs; exercise cold/cache paths, nested interfaces and actual worker boundaries. |
| Record format, retention and exports | Large, highest uncertainty | Logical identity, dependency retention, relocation and cleanup | Lost assets or falsely reusable results; prove ownership and export closure before release. |
| Platform backend and API | Medium | Extend schema responses and graph diagnostics; read effective result descriptions; resolve referenced cells | Stale graph/result confusion and arbitrary file access; maintain captured identities and server-side admission. |
| Frontend editor and Node Data | Medium | Partial/deferred states, named dynamic-output connection action, generated API types, preserved actions | Misleading green connections or stale pins; separate prospective and captured schemas and test edits/reloads. |
| Tool-package adoption | Small per simple tool, medium/large across common tools | Convert structural tools; document custom opt-in | Changed join, suffix, index or dtype semantics; compare results with existing behavior. |
| Distribution and release | Medium locally; additional large scope if remote transport changes | Coordinated Core/library/tools/platform versions and capability checks | Mixed-version corruption; reject unsupported contracts/formats before execution or import. |

Concrete platform entry points include `models/graph.py` (`NodeOutputSchemaResponse`), graph validation/compilation services, `services/result_store.py`, `services/data_table_projection.py`, generated `frontend/src/api/types.ts`, canvas connection handling and `NodeDataTable.vue`.
Library entry points include `dataframe_tool.py`, `node.py`, `validation/resolved.py`, execution validation and storage publication/export APIs.
These are an impact map, not an exhaustive file inventory or evidence that only these files need changes.

No new editable graph field is required for the initial feature: schemas are derived, and deferred edges already carry output names.
Any transport extension must be backend-model-first with regenerated frontend types.
New tool/API versions remain explicit dependencies; do not silently rebind existing workflows to upgraded tool behavior.
The design does not require a new persisted platform metadata sidecar, graph migration, automatic viewer installation, general pandas analysis or global garbage collector.
If implementation discovers a required graph-format change, it needs a separate migration design before that change ships.

## 12. Implementation stages and release evidence

1. **Schema foundation:** implement the facade, partial/open representation, refinement rules and legacy adapter; test fixed, passthrough and dynamic declarations without enabling new image actions.
2. **Select/rename end to end:** implement the operation and durable reference format together, including cache reuse, retention, exports and platform result actions.
3. **Runtime completion and editor support:** introduce opt-in TableResult and deferred named edges, preserving all earlier known-constraint validation.
4. **Additional operations:** add filters, joins and concatenation separately, preserving their exact established table semantics.
5. **Broader values and deployment:** qualify directory assets, containers, arrays and remote result transfer independently; unsupported combinations receive explicit capability errors rather than degraded authority.

Schema-only improvements can ship independently when they do not claim asset preservation.
Reference-preserving operations cannot ship with only the schema half implemented.
Use explicit supported contract/format versions rather than a mutable preference that can make the same stored result mean different things.
Rollback means returning to compatible readers and retaining new-format records untouched; an older reader must refuse unsupported records, not reinterpret them as legacy.

Minimum acceptance includes empty/all-null tables, partial parameters, replacement of same-named columns, invalid callbacks, deterministic schema serialization, concat conflicts, outer/many-to-many joins, cache winners, cleanup/export races, same-filename assets from different records, and nested dynamic outputs.
A custom transform that returns ordinary text instead of admissible image references must fail contract admission; a transform with no preservation declaration must not inherit asset identities.
Test cold execution and cache hits against the same expected values, column order, index, nulls and references.
Measure metadata size and publication/load time on large tables; origin deduplication must prevent full ancestry duplication and visible-page rendering must not cause a storage read for every cell.

Use library and common-tool unit/integration tests for the contracts, then platform focused service and browser tests through `scripts/test`.
Cross-stack implementation requires the documented `check app` completion scope; browser changes also require their applicable browser checks.
Published dependency adoption and package-loading changes require the documented full/compatibility validation, with actual Wetlands consumers for worker evidence.
Distributed behavior requires explicitly selected distributed tests; local completion cannot certify remote transfer.
A documentation-only change runs `scripts/test check docs` and proves rendering and documentation checks only.

Before runtime implementation, update the normative library tool/type/execution/cache/storage specifications, platform v1/v2 validation and result contracts, viewer specifications if their wire authority changes, and distributed specifications if new transport is enabled.
Update `PLATFORM_CONTEXT.md` when adoption changes its architectural summary.
This proposal does not itself change those runtime contracts.

## 13. Decisions to settle in the first prototype

The proposed semantic API, opt-in lifecycle, authority order and validation rules above are the design baseline.
The first prototype must select the exact versioned storage encoding for references and demonstrate its publication, retention and export behavior.
It must also identify all legacy schema callers and verify that partial-schema transport can be added without losing their known-field behavior.
The Python spelling and module placement of new facade types can then be finalized against the released public API.

Defer broad operation adoption if those proofs fail.
Do not compensate with filename inference, a second frontend type system, or new mutable metadata attached to old immutable results.
