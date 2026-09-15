# Multiple napari environments and portable viewer requirements

Status: proposed design for discussion; not implemented.
This document proposes a focused extension to the implemented [v1 viewer and settings contracts](platform_specs_v1.md) and [v2 recursive workflow, import/export, and result contracts](platform_specs_v2.md).
It does not change their implemented status or the library's current public API.
The examples below describe proposed schemas, not APIs available today.

## 1. Product decisions

Users configure named **napari environments**: separate Python installations containing napari and a compatible collection of plugins.
Two environments can contain the same napari release and different plugins, so the UI uses “environment,” not “napari version.”
An environment has an immutable local ID, an editable display name, and separately detected napari and Python versions.
Names such as “Microscopy,” “Tracking,” and “Legacy microscope” are useful; generate an initial name and allow editing.
Names must be nonempty and unique within the user's local registry, ignoring case and surrounding whitespace.
Renaming never changes identity, the installation directory, or saved preferences.

The feature has three independent layers:

| Layer | Example | Owner and portability |
| --- | --- | --- |
| Viewing requirements | Output `tracks` requires plugin `example-track-reader` | Tool/workflow author; travels with the workflow |
| Environment inventory | “Tracking” contains napari and those plugins | Local platform user; never travels with the workflow |
| Selection preferences | Prefer “Tracking” for this output or `.tracks` files | Local platform user; never travels with the workflow |

The developer describes what is needed to view the data.
The user chooses which local installation supplies it.
Viewing requirements are independent of the packages and environments needed to execute a tool.
Missing viewer dependencies must not prevent importing, editing, exporting, or executing an otherwise valid workflow.

Recommended first release includes attaching existing environments, creating managed environments, output requirements, automatic selection, explicit local output defaults, simple format associations, and import diagnostics.
A general plugin marketplace, arbitrary install scripts, automatic upgrades, and shared environment synchronization are outside this feature.

## 2. Environment registration and ownership

### 2.1 Attach an existing environment

**Add existing environment** accepts an environment directory or its Python executable through a path field and native Browse action.
The backend resolves and records the actual interpreter, environment kind, canonical environment root, and supported launch strategy.
Support Conda environments and Python virtual environments on the supported desktop operating systems.
Detect duplicate canonical installations and offer the existing entry rather than registering the same interpreter twice.
Moving an installation requires **Locate environment** and a fresh probe; replacing the interpreter at the same path also invalidates its observed inventory.

**Check environment** runs a bounded subprocess using that interpreter and reports Python, napari, Qt, bridge support, and discovered plugins.
Environment registration and probing never install packages.
The subprocess must run with the environment's required launch context; invoking an absolute Python path alone must not be assumed sufficient for every Conda installation.
The platform must not inherit its own Python imports, user-site packages, or Qt selection accidentally into the viewer.
Unsupported launch configurations receive an actionable error rather than a green status.
Standalone napari application bundles are outside initial support unless they expose a tested interpreter and bridge launch path.

An external environment remains user-owned.
The platform can launch it, inspect it, and forget its registration; it cannot install, update, or delete packages there.
Users manage its packages in napari or their existing package manager and then refresh the platform's inventory.
Removing the registration does not remove the installation.

### 2.2 Create a managed environment

**Create environment** uses the existing BioImageFlow/Wetlands environment infrastructure and its resolved environment root.
Each managed installation has an independent recipe and installation identity; provisioning must not reuse or replace the current singleton `napari` recipe.
Managed napari environments must also be independent of processing-tool environments.

The creation form contains:

- Name, with a useful suggested value.
- Required plugins, prefilled when opened from an output or workflow compatibility report.
- Optional recommended plugins, visibly separate and opt-in.
- An advanced section for supported napari/Python constraints and package-source details.

Offer a tested platform baseline by default and resolve it against the requested plugin constraints.
Do not offer “latest” as a promise that arbitrary plugin combinations will work.
The implementation must publish its tested napari/Python/Qt and bridge support matrix; supporting several releases does not imply supporting every historical release.
Users who need unsupported combinations can manage an external installation, but an unsupported bridge remains explicitly unverified or unavailable.

Use one documented provisioning strategy through public Wetlands APIs.
Package distribution names and napari plugin IDs are not shell commands or Conda package mappings.
For automatic installation, resolve reviewed Python distribution requirements from approved package sources; use explicit platform-maintained mappings where a Conda package name differs.
Constraints requiring unavailable builds, system libraries, or incompatible Python/Qt versions produce a solvability error with the affected plugins.
Exact backend recipe syntax and the initial supported release matrix require an implementation feasibility check before coding the installer.

The operation shows resolving, downloading/installing, validating, ready, failed, or cancelled, with progress and accessible logs.
Installation happens in a new location and becomes selectable only after successful validation.
Failure or cancellation preserves all existing environments and defaults; partial installations are never marked ready.
Retry and restart recovery use the recorded operation identity and do not create duplicate ready entries.

### 2.3 Add plugins and update managed environments

Provide **Create modified copy** from a managed environment's details, using the same creation form with its declared recipe prefilled.
Adding, removing, or updating plugins produces a new installation and entry; the original remains usable and keeps its existing defaults.
Describe this as a recipe-based recreation, not a byte-for-byte clone of every manual change.
After validation, users may explicitly change their defaults to the new environment.
Automatic in-place upgrades are not part of this feature.

Napari's own plugin manager remains available, but changes made there are external changes from the platform's perspective.
Detect inventory drift, display “Modified outside BioImageFlow,” and evaluate the observed installation rather than its old recipe.
Never silently reinstall the recipe to undo those changes.
Offer a refreshed inventory and a new managed copy containing supported observed requirements; unrepresentable local packages must be reported before creation.

**Remove from list** and **Delete managed installation** are distinct actions.
Deletion is available only for a platform-owned installation, reports affected defaults, and requires closing its running viewer first.
Use the environment manager's ownership-aware cleanup API and never recursively delete a user-provided path.
Forgetting an entry clears its local defaults and format references atomically, with a summary of those changes.

## 3. Portable output requirements

### 3.1 Granularity and authoring

Declare requirements on an output field, alongside existing image/type metadata.
A node may produce a standard TIFF and a specialized tracks file that need different viewers.
A single node-wide plugin requirement would incorrectly apply to both.

Introduce optional library-owned viewer annotation metadata, conceptually `ViewerSpec(napari=...)`, separate from `ImageSpec` and `GUIMeta`.
This annotation must not import napari into the BioImageFlow library or affect tool input compatibility.
The exact Python spelling and public exports belong to the library implementation.
The platform exposes the metadata in output schemas and a readable **Viewing requirements** section in the node's output inspector.
An explicit napari viewer declaration also enables the open action for addressable file/directory outputs such as tracks or points, even when they are not scalar images; ordinary unannotated path columns do not gain that action automatically.

Workflow authors can add portable per-output requirements to a node instance, for example when configuring a generic file-source node for a specialist format.
Such additions are explicit workflow edits and are visually separate from **My preferred environment**.
Tool requirements and workflow additions are combined; additions cannot silently remove a tool's hard requirement.
Changing an incorrect tool declaration requires editing the tool or using an explicit one-time viewing override.
The first release does not add inherited node-wide defaults or arbitrary expressions over parameters and rows.

An illustrative serialized output declaration is:

```json
{
  "viewer": {
    "napari": {
      "required_plugins": [
        {"plugin_id": "example-track-reader", "distribution": "example-track-reader", "version": ">=1.2,<2"}
      ],
      "recommended_plugins": [
        {"plugin_id": "example-track-editor", "distribution": "example-track-editor", "version": ">=1"}
      ],
      "reader_plugin": "example-track-reader",
      "napari_version": null
    }
  }
}
```

These package names are fictional examples.
`required_plugins` means every listed plugin must be available in the same environment for this output.
`recommended_plugins` describes optional conveniences such as editing widgets; their absence does not prevent normal opening or remove the green requirements indicator.
Authors should not require an analysis plugin merely because it produced an ordinary TIFF that napari can already read.
`reader_plugin`, when present, identifies the required reader and must reference a required plugin.
Leave it absent when normal reader discovery is appropriate.
Viewer requirements never execute a workflow-supplied widget, command, or Python function automatically.

Plugin identity uses a stable napari registration/manifest ID, never a display label or Python import-module name.
The distribution name supplies installation and version metadata; normalize package names for comparison but preserve the napari ID according to its registration rules.
Current npe2 manifests require their name to match Python package metadata; keep the fields explicit for installation provenance and legacy adapters, and validate their relationship rather than guessing it. [Napari manifest reference](https://napari.org/stable/plugins/technical_references/manifest.html).
Distribution is optional when there is no supported automatic installation source; checking an already installed plugin remains possible and setup reports manual installation required.
Plugin version constraints, and a rarely needed napari release constraint, use validated Python package version specifiers.
These are software release constraints, not references to locally named environments.
Support a list of jointly required plugins initially; alternative requirement sets can be added later if real workflows need them.
When combining tool declarations and workflow additions, deduplicate by plugin ID and intersect constraints on the same distribution or napari release.
A required declaration takes precedence over a recommendation for the same plugin.
Conflicting hard reader IDs or unsatisfiable version intersections produce a viewing-requirement diagnostic attributed to the contributing declarations, without turning viewer setup into an execution dependency.

### 3.2 Propagation and provenance

Published workflow outputs inherit the resolved internal output's requirements recursively through stable interface IDs.
Renaming an output's display label must not lose its annotation or local preference.
An explicit requirement addition on an exposed workflow output augments its source requirement.
Two embeddings of one workflow remain independent node instances for local preferences.
Do not propagate requirements through arbitrary downstream transformations: the downstream output declaration is authoritative for its own representation.

Generic images without annotations use format rules and reader discovery.
The output declaration is a column-level contract; mixed-format rows still resolve using each selected artifact's actual format.
Conditional plugin declarations and non-file layer payloads are deferred.
Supported directory images must be actionable even when thumbnail generation cannot read them.
A missing thumbnail must not disable **Open in napari** for a valid addressable artifact.

Opening retained results resolves requirements against their producer snapshot and actual representation, not just the currently edited node schema.
The latest-output projection can combine results from different runs, so the backend must preserve each selected result's own provenance.
Converting or materializing an artifact for viewing must identify the new format and its requirements; do not retain an incompatible original reader requirement or silently convert specialized data.
Remote results must first become locally accessible through the existing result-transfer contract.

### 3.3 Library and archive contract

The portable library contract must preserve viewer annotations and per-instance additions through recursive serialization, materialization from Python, tool introspection, and archive round trips.
Tool declarations have one authoritative owner in tool metadata; instance additions have one owner in the canonical graph.
Export also carries a derived, versioned viewing-requirement manifest keyed by scoped output identity so an importer can report viewer needs before all tool packages are available.
This manifest is an export snapshot, not a second editable requirement store.
After dependencies load, compare it with authoritative tool/graph metadata and report unresolved or changed declarations before declaring coverage.
Missing or unresolvable tool metadata must produce “requirements unknown,” not an empty list and a green report.

This requires a coordinated library schema/API change: today's strict graph/archive models reject unsupported extra fields.
Do not hide the feature in unknown graph keys, environment labels, package execution requirements, or a platform-only archive that the library cannot preserve.
Version the affected wire contracts, define legacy input as having no viewer declaration, and make older readers reject unsupported newer schemas clearly rather than dropping requirements.
Exports never contain environment IDs/names/paths, local selection rules, process state, credentials, or executable install commands.
Optional environment recipes or lockfiles are separate explicit exports and are not required to exchange a workflow.

Local preference changes cannot dirty a workflow or change its artifact hash or execution cache keys.
Portable requirement additions are document content and do change artifact identity.
Viewer metadata must be excluded from processing dependency resolution and semantic execution cache inputs; this does not promise to suppress existing invalidation caused by an actual tool source/version change.

## 4. Compatibility and environment selection

### 4.1 What the indicators mean

Environment health, requirement satisfaction, and reader support are separate facts.

| Indicator | Meaning | Normal action |
| --- | --- | --- |
| Green check, “Requirements met” | Fresh inventory satisfies all hard plugin/version constraints, required plugins are enabled, and the launch bridge is supported | Eligible for automatic selection |
| Amber warning, “Needs attention” | Missing/disabled required plugin or version mismatch | Explain the cause; offer setup or an explicit one-time attempt |
| Gray question mark, “Not verified” | Inventory is stale, probe failed, unsupported discovery, or requirements could not be resolved | Refresh or inspect; no claim of compatibility |
| Unavailable | Interpreter missing, setup incomplete, unsupported launch, or known launch failure | Repair/setup; cannot launch |

A green check is a status icon, not an editable checkbox.
Use text and accessible labels as well as color.
It means the declared prerequisites are met, not that every installed plugin is mutually compatible or that the file is valid.
For unannotated outputs, label the state “Reader available” only when a reader check supplies evidence; otherwise show “No declared requirements; reader not verified.”
Such an output may still open normally in a healthy environment using napari's standard reader handling.

Inventory records installed distribution versions, registered/enabled plugins, reader contributions, napari/Python versions, probe time, and an environment fingerprint.
Probe in the target environment, outside the backend process, with time and output bounds.
Do not import plugins into the backend to inspect them.
Refresh after creation, registration, explicit Refresh, detected package/configuration changes, and viewer restart; revalidate before launch when cached evidence is stale.
A running viewer's loaded inventory may differ from its on-disk installation after package changes; report restart required rather than claiming it can use the new packages immediately.

Reader filename patterns are hints; actual reader acceptance may depend on file contents and whether the artifact is a directory. [Napari reader contributions](https://napari.org/stable/plugins/building_a_plugin/guides.html).
Run potentially expensive reader checks only for the selected artifact, not every cell in a table or every output during workflow import.
If reader choice is ambiguous, request a reader choice for this open; do not arbitrarily choose the first plugin.

### 4.2 Deterministic selection

The backend resolves the addressed artifact, requirements, and candidates and returns both the chosen environment and an explanation.
The frontend renders this result and does not implement a competing resolver.

For an output with known hard requirements, first exclude candidates that fail those requirements or cannot launch.
Rank the remaining candidates in this order:

1. The user's saved preference for this output instance.
2. A matching format rule's preferred environment.
3. The user's global default environment.
4. Other candidates, preferring more satisfied optional recommendations, then stable registration order.

Within equal recommendation scores, stable registration order wins; renaming, starting a viewer, and transient process state do not reshuffle defaults.
Required reader declarations take precedence over optional local reader preferences during normal selection.
A format preference never makes an environment with missing hard requirements eligible.

For an unannotated artifact, apply the same preference order among healthy environments, preferring evidence of reader support when falling through to other candidates.
Normal napari opening remains available where there is no declared requirement and no known reader failure; lack of an annotation is not a setup error.
For unresolved requirements caused by unavailable metadata, ask the user to choose explicitly and show the uncertainty.

If a saved preference becomes incompatible, retain it for repair but show the fallback and reason before the next open.
The button tooltip and dropdown identify both “Saved preference unavailable” and the currently selected fallback.
If no qualifying environment exists, the primary button opens the compatibility/setup panel; it does not start a known incompatible environment automatically.
An explicit **Try opening anyway** is available for a runnable environment that fails the declared requirements.
That attempt does not rewrite requirements or become a remembered incompatible default; a conflicting reader override is scoped to that attempt too.
Never automatically retry a failed read in another environment, where it could create unwanted windows or duplicate layers.

For multi-artifact opens, combine the artifacts' requirements and intersect their eligible environment sets only for artifacts deliberately requested in one viewer.
If none can host that group, offer separate windows grouped by a satisfying environment.
Never union every requirement in a workflow into a mandatory single installation.
Existing multi-path API behavior must remain explicit during migration; adding a new multi-selection UI is not required for the first release.

## 5. Settings and opening UI

### 5.1 Preferences → Image Viewers → napari

Use a compact environment list with expandable details and an optional format-association section.
Keep Fiji within the existing Image Viewers page.
The basic interaction needs forms and a short table, not a JSON editor.

```text
napari environments                    [Add existing] [Create environment]

Default: [Microscopy v]

Microscopy       napari <detected>    Ready                 [Details ...]
Tracking         napari <detected>    Running               [Details ...]
Legacy scope     napari <detected>    Environment missing   [Locate ...]

File format preferences (optional)                         [Add rule]
Extensions              Preferred environment       Reader (optional)
.czi, .lif              Microscopy                  Automatic
.ome.zarr               Multiscale                  Selected reader
```

Version placeholders and format examples illustrate the layout, not guaranteed package support.
Details show path, ownership (“Managed by BioImageFlow” or “External”), detected versions, plugin list with enabled/error status, last check, and relevant actions.
Provide Refresh and Launch empty viewer; managed entries also offer Create modified copy.
Long paths collapse without hiding their full selectable text, and actions remain usable in a narrow settings window.

### 5.2 Format preferences

Keep associations because they serve standalone images, generic file-source outputs, and old workflows without annotations.
A rule contains one or more literal suffixes, one environment ID, and an optional reader plugin ID available in that environment.
Reader is optional because choosing an environment and choosing a reader within it are distinct operations.
Napari already supports reader preferences and explicit reader selection; pass an explicit reader only when the resolved request calls for one. [Napari viewer API](https://napari.org/dev/api/napari.Viewer.html).

Normalize suffixes to a leading dot and compare case-insensitively against the artifact basename.
The longest matching suffix wins: `.ome.tif` before `.tif`, `.nii.gz` before `.gz`, and `.ome.zarr` before `.zarr`.
Reject duplicate suffix assignments instead of introducing hidden rule priorities.
Support directory suffixes such as `.zarr`; a directory still needs a reader that accepts directories.
Paths without recognized suffixes fall back to output requirements and reader discovery.
Do not initially expose regular expressions, arbitrary glob ranking, MIME registries, or content-sniffing rules.

Show reader-advertised formats in environment details and optionally suggest rules, but never install broad `*` associations automatically.
An extension match is a preference, not proof that a reader supports every variant of a format.
An optional reader rule applies only when the selected environment is the rule's environment and no hard reader declaration conflicts.
Otherwise show why it was ignored and use the hard reader or normal discovery.
Raw JSON import/export of local configuration may be a later advanced convenience; normal configuration and validation must work without it.

### 5.3 Open button and dropdown

The existing **Open in napari** becomes a split button.
Its main action opens in the resolved environment; its tooltip/accessibility label includes that environment and selection reason.
The arrow opens a popover showing all registered environments with status, detected napari version, and a short reason when requirements are unmet.
Keep unavailable entries visible and disabled so users can understand or repair them.

Use a separate star or pin action **Always use for this output**, with a tooltip that explicitly states its scope.
The green check describes requirements; the star describes the user's saved default; a “Selected automatically” label identifies the resolver's choice.
Clicking an environment opens it once and does not save a preference.
Clicking its star saves a preference and does not launch it.
Provide **Reset to automatic**, **Manage environments**, and **Create environment for these requirements**.
Do not embed a button inside another button or a menuitem with conflicting keyboard semantics; use a popover list with independently focusable launch and preference controls.

Preferences apply to the output column across rows, not a filename or a single table cell.
The first release has no node-wide preference, avoiding another inheritance level.
The existing Ctrl+Click replace action clears layers only in the selected environment's viewer.
Expose an explicit **Replace layers and open** action as well so replacement does not depend solely on a modifier key.
Setup, failure, or a menu selection must not clear another environment's viewer.

## 6. Local preference persistence

Environment registrations, the global default, and format rules belong to the existing per-user application settings store.
Backend-persisted per-output preferences belong in a separate versioned `viewer-preferences.json` alongside that settings file, because they can grow independently of settings.
Browser local storage may cache this state but is never its authority.

Use this logical key:

```text
(workspace identity, root workflow identity generation,
 structural node-instance path, output field key or stable public output ID)
    -> environment ID
```

Use existing stable workspace identity where available, otherwise define a persisted local workspace identity as part of implementation; do not hash a mutable display name or raw workflow path as identity.
Workflow path can be retained as a lookup/display index, with the generation guarding against delete-and-recreate collisions.
Structural node paths use node IDs, never node labels or nesting positions.
Tool output field names are schema identities until the library offers stable field IDs; a tool-field rename invalidates that preference.
Public workflow output labels can change while their stable IDs preserve preferences.
An exposed workflow output has its own user preference key; it inherits viewing requirements from its provider, not the provider's local preference.

Local rules survive restart, table sorting/pagination, workflow display renaming, and moves within the same workspace through the normal identity-aware lifecycle coordinator.
Deletion drops that workflow generation's rules.
Reimport, duplicate, Save as copy, paste, and independent embeddings start without copied output preferences.
Source update preserves rules only for surviving structural output identities and rechecks them against changed requirements.
Environment deletion clears references; an incompatible but still registered environment retains its preference for repair.

Private nested edits use a session-scoped preference overlay tied to the snapshot UUID.
Apply remaps surviving entries to the accepted parent instance; discard drops the overlay.
Unsaved root workflows similarly use temporary session identity until saved.
Preference writes bind to the captured workspace/generation/session so a delayed request cannot target a replacement workflow or another workspace.
Preference changes are atomic local UI state and do not acquire a graph execution lock or prevent viewing during execution.

## 7. Workflow import and setup guidance

After import, show a non-blocking **Viewing requirements** report with coverage per scoped output, including nested nodes.
Run the same check on workflow open, requirement changes, and relevant environment inventory changes, without reopening a modal repeatedly.
Include inactive nodes in the report, marked inactive, but preselect only the active workflow's unmet output requirements in setup.
Imported workflows with no declarations continue to work through automatic readers and local format rules.

Report precise failures: missing plugin, installed version outside the constraint, disabled plugin, unknown metadata, unsupported viewer, or required plugins split across environments.
Two plugins installed in different environments do not satisfy one output that needs both.
Conversely, two incompatible plugin sets used by different outputs are acceptable when separate environments cover them.
Summaries should say “2 outputs need viewer setup,” rather than claiming that the workflow cannot run.

For each uncovered requirement set, offer:

- Use a satisfying registered environment, or attach an existing installation.
- Refresh/restart or enable a disabled plugin through the environment's own configuration.
- Create a new managed environment, with requirements prefilled.
- Continue and configure later.

Group identical requirement sets for convenience.
Do not assume all missing plugins can be installed together: solving a combined environment is an optional explicit choice, with per-output alternatives available if it fails.
If the required set for a single output is itself unsatisfiable, report its conflicting constraints and point to the declaration; splitting that set cannot repair it.
The creation preview identifies requested distributions, constraints, source, and new environment name before installation starts.
Import and passive checks never download/install packages or execute workflow-provided installation instructions.
Unknown/private packages require a separately configured trusted source or manual installation; do not guess URLs from plugin IDs or copy credentials into a workflow.

## 8. Backend and process contract

Replace the singleton launcher with an environment registry and launchers keyed by immutable environment ID and installation identity.
Allow one platform-owned viewer process per registered environment per application session, with independent lifecycle, locks, requests, and status.
Reuse a running viewer only for the exact environment installation; a recreated environment must not inherit an old process connection.
Concurrent open requests to the same environment share one launch, while another environment remains responsive.
Keep authenticated local IPC and use request IDs to distinguish accepted, opening, succeeded, and failed operations.
Report success only after `viewer.open()` completes on the Qt thread; the current helper acknowledges queueing before opening, which is insufficient for reliable reader-error reporting.
An ambiguous disconnect after dispatch is “outcome unknown”; do not replay automatically and risk duplicate layers or another clear operation.

Pass the selected reader to the helper rather than always calling `viewer.open(..., plugin=None)`.
If napari reports multiple readers, expose a concrete choice or invoke its supported reader chooser; do not turn ambiguity into a silent success.
Clear-layers behavior and partial multi-file failure must be explicit; do not promise rollback of arbitrary plugin side effects.
Close or restart only the process owned by the addressed launcher; never attach to, kill, or control a separately launched napari session implicitly.

Separate Python environments may still share user configuration or inherit host state.
Give platform-launched environments separate napari configuration locations, scoped by environment ID, using a supported mechanism for each tested napari release.
Validate that mechanism during the bridge feasibility check; package isolation alone is not acceptance evidence for settings isolation.
Inventory and disabled-plugin checks must use the same configuration that the viewer will use.
If an external environment's ordinary napari configuration is imported, make that an explicit one-time copy; subsequent platform launches use their own configuration.

Extend the API with typed registry, probe, compatibility-resolution, local-preference, environment-creation operation, and per-environment lifecycle contracts.
Exact route names are an implementation detail, but requests must bind to environment and artifact identities, and responses must carry revisions and actionable diagnostic codes.
Environment status/events include the environment ID; a global `napari` status cannot describe concurrent viewers.
Long setup/probe operations must not block status reads or unrelated viewers.
The frontend consumes generated OpenAPI types and refreshes on inventory/preferences events.

Workflow opens use backend-resolved result identities including retained run/record context where available, scoped node, stable column identity, and selected row identity.
Do not rely on a mutable table row offset or the active tab to rediscover a previously selected artifact.
Existing raw-path callers need an explicitly documented desktop-only compatibility path during migration; they cannot supply trusted workflow requirements or silently bypass output identity validation.
Dataset opens likewise resolve through the dataset/artifact authority.
All registration, probing, installation, local-path, and GUI-launch operations are desktop-only and enforced on the backend.
Portable metadata survives webapp import/export, but webapp mode never probes server environments or offers a misleading local installation action.

## 9. Migration and delivery

Preserve the current managed napari installation as one registered entry named “Default napari” and select it as the initial global default.
Migration inspects and adopts the actual installation without recreating it or discarding user-installed plugins.
If it does not exist, register a setup-needed default recipe; first use presents setup and installation progress.
Changing settings alone must not provision it.
Legacy outputs with no viewer annotations retain normal opening behavior once a healthy default is available.

Implement in independently verifiable increments:

1. Registry, environment probes, isolated launcher/configuration state, settings list, split button, and one-time selection; preserve existing opening and migrate the singleton.
2. Coordinated library annotation/archive support, output provenance, compatibility resolver, local output defaults, simple format rules, and import report.
3. Managed environment creation and Create modified copy using the same requirements report and resolver.

The intended feature is complete only when all three increments are available.
Before implementation, settle the supported bridge/version matrix, configuration-isolation mechanism, and public Wetlands recipe capabilities with small feasibility checks.
The product decisions above do not depend on a new general-purpose environment manager or a complex association editor.

At implementation time, update the affected v1 viewer/settings/API sections, v2 graph/inspection/archive/lifecycle contracts, library specifications and public contract references, and `PLATFORM_CONTEXT.md` together.
Until then this file is a proposal, and the existing normative documents continue to describe the current implementation.

## 10. Acceptance criteria

1. Two environments with the same napari version and different plugins appear as distinct named entries and run concurrently without shared layers or reader preferences.
2. Renaming an environment preserves every reference; attaching the same canonical interpreter twice does not create duplicates.
3. Different outputs of one node resolve independently, including published outputs through nested workflows and two embeddings of one child.
4. Required plugins must all be satisfied in one environment for one output; requirements for different outputs can be covered by different environments.
5. Missing recommended plugins do not block opening; absent, disabled, incompatible, stale, and unknown required plugins produce distinct explanations.
6. A matching format rule cannot override a hard plugin/reader requirement; compound suffixes and directory images resolve correctly.
7. Choosing once leaves preferences unchanged; starring changes only local output preference; reset restores automatic selection; each control is keyboard accessible.
8. Preferences survive restart, label changes, and same-workspace moves, but do not leak through export/import, copy, delete-and-recreate, discarded nested edits, or workspace switches.
9. Export/import preserves recursive requirements and contains no local environment references or credentials; missing tool metadata yields an incomplete report rather than false coverage.
10. An imported workflow with unmet viewer needs can still run; setup can create separate installations for incompatible requirements on different outputs.
11. Existing-environment checks make no package changes; failed or cancelled managed creation leaves old environments/defaults usable; recipe changes create a separate installation.
12. Package/configuration drift and pending viewer restart invalidate stale compatibility claims; actual reader exceptions are reported after dispatch.
13. A launch race starts one viewer per environment; a failure in one does not block another; ambiguous command completion is not automatically replayed.
14. Result selection survives table sorting, pagination, active-tab changes, and later graph edits; retained results use their captured requirements and representation.
15. Webapp endpoints reject local environment operations, and the import check never triggers installation or runs archive-provided commands.
16. Native smoke checks on each supported desktop OS cover an external Conda environment, a virtual environment, paths with spaces, managed creation, a missing plugin, explicit reader choice, and configuration isolation.

Use `scripts/test` for implementation checks proportionate to each increment, following [Test lanes](docs/testing.md).
The bridge and native napari behavior additionally require real desktop checks; mocked unit tests and headless browser tests do not certify Qt startup or third-party plugin compatibility.
