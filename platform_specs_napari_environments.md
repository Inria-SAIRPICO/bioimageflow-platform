# Multiple napari environments and portable viewer requirements

Status: Phase A specification complete; the backend environment registry, inventory probe, per-environment launcher/lifecycle, portable viewer metadata, exact-result provenance, compatibility resolver, favorite store, managed creation/copy/removal lifecycle, environment settings UI, passive readiness report, and exact-result output chooser are implemented; native desktop smoke certification remains incomplete.
This document specifies the delivered extension to the implemented [v1 viewer and settings contracts](platform_specs_v1.md) and [v2 recursive workflow, import/export, and result contracts](platform_specs_v2.md).
It does not change their implemented status; the portable viewer metadata it relies on is defined and exported by the released `bioimageflow-core` 0.4.0 package.
The portable workflow and frontend examples below describe implemented behavior unless their implementation status is stated explicitly.

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
| Viewing requirements | Output `tracks` requires distribution `example-track-reader` | Tool/workflow author; travels with the workflow |
| Environment inventory | “Tracking” contains napari and those Python distributions | Local platform user; never travels with the workflow |
| Selection preferences | Favor “Tracking” for one structural output identity, or prefer it for matching filenames | Local platform user; never travels with the workflow |

The developer describes what is needed to view the data.
The user chooses which local installation supplies it.
Viewing requirements are independent of the packages and environments needed to execute a tool.
Missing viewer dependencies must not prevent importing, editing, exporting, or executing an otherwise valid workflow.

Recommended first release includes attaching existing environments, creating managed environments, output requirements, automatic selection, one exclusive toggleable favorite per structural output identity, filename associations with extension shortcuts, and import diagnostics.
A general plugin marketplace, arbitrary install scripts, automatic upgrades, and shared environment synchronization are outside this feature.

## 2. Environment registration and ownership

### 2.1 Attach an existing environment

**Add existing environment** accepts an environment directory or its Python executable through a path field and native Browse action.
The backend resolves and records the actual interpreter, environment kind, canonical environment root, and supported launch strategy.
Support Conda environments and Python virtual environments on the supported desktop operating systems.
Detect duplicate canonical installations and offer the existing entry rather than registering the same interpreter twice.
Moving an installation requires **Locate environment** and a fresh probe; replacing the interpreter at the same path also invalidates its observed inventory.

**Check environment** runs a bounded subprocess using that interpreter and reports Python, napari, Qt, and installed Python distribution metadata.
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
- Required Python distributions, prefilled when opened from an output or workflow compatibility report.
- Optional recommended distributions, visibly separate and opt-in.
- An advanced section for the supported napari/Python/Qt matrix and PyPI resolution details.

The default managed recipe creates a Conda environment containing Python 3.12, then installs napari 0.9.1, PyQt6, and requested Python distributions from PyPI.
The older supported smoke recipe creates Python 3.12 through Conda, then installs napari 0.6.6, PyQt5, and requested Python distributions from PyPI.
These are the initial explicit tested matrices; the creation API defaults to the first and advanced requests require an exact napari version and an explicit PyQt5/PyQt6 choice.
Resolve requested package constraints against the selected tested matrix.
Do not offer “latest” as a promise that arbitrary plugin combinations will work.
The implementation must publish these tested napari/Python/Qt and bridge matrices; supporting both does not imply supporting other releases.
Users who need unsupported combinations can manage an external installation, but an unsupported bridge remains explicitly unverified or unavailable.

Use one documented provisioning strategy through public Wetlands APIs.
Conda supplies only Python for these managed recipes; napari, Qt, the bridge, and requested packages are Python distributions installed from PyPI.
Package distribution names and napari plugin IDs are not shell commands or Conda package mappings, and the platform does not maintain Conda-name translations for requested packages.
For automatic installation, resolve reviewed Python distribution requirements from PyPI.
Constraints requiring unavailable builds, system libraries, or incompatible Python/Qt versions produce a solvability error with the affected packages.
The durable backend recipe stores its Python-3.12-only constraint as PEP 440, while the Wetlands `EnvironmentSpec` receives the equivalent Pixi/Conda `3.12.*` version specifier, empty `conda`, PyPI `napari==<exact version>`, the selected Qt distribution, normalized requested PEP 508 distributions, and the `conda-forge` channel.
Provisioning diagnostics preserve Pixi's UTF-8 stdout and stderr on Windows, including live operation messages and structured failure tails.
Direct URLs, environment markers, duplicate normalized names, and requests for recipe-controlled napari, Qt, Python, BioImageFlow, or Wetlands distributions are rejected before provisioning.

The durable operation shows pending, resolving, installing, validating, completed, failed, or cancelled state with progress, message, structured error, and the public Wetlands operation identity where available; Wetlands output continues through the platform logging stream.
Installation happens in a new location and becomes selectable only after successful validation.
Failure or cancellation preserves all existing environments and defaults; partial installations are never marked ready.
Retry and restart recovery use the recorded platform operation and environment identities and do not create duplicate ready entries.
A restart never claims that live progress survived: a public Wetlands generation already published as ready is probed and recovered, while incomplete or unknown creation is marked failed with an explicit retry path.

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
Use the public environment manager removal operation and never recursively delete a user-provided path.
Deletion proves the recorded Wetlands name, public managed project path, and generation identity before removal; the nested `.pixi/envs/default` interpreter path is not substituted for that owned project path.
Forgetting an entry clears every output favorite, filename rule, and global-default reference to it atomically, with a summary of those changes.
Platform-created managed entries cannot use forget and must use managed deletion; adopted entries can only be forgotten.

## 3. Portable output requirements

### 3.1 Granularity and authoring

Declare requirements on an output field, alongside existing image/type metadata.
A node may produce a standard TIFF and a specialized tracks file that need different viewers.
A single node-wide package requirement would incorrectly apply to both.

Viewer requirements travel as optional library-owned viewer annotation metadata, `ViewerSpec(napari=...)`, separate from `ImageSpec` and `GUIMeta`.
The annotation does not import napari into the BioImageFlow library or affect tool input compatibility.
Its exact Python spelling and public exports are fixed by the library: `bioimageflow-core` exports `ViewerSpec`, `NapariRequirement`, and `PackageRequirement` with the `extract_viewer_spec`, `merge_viewer_specs`, and `coerce_viewer_spec` helpers, and the platform wire models mirror that contract.
The platform exposes the metadata in output schemas and a readable **Viewing requirements** section in the node's output inspector.
An explicit napari viewer declaration also enables the open action for addressable file/directory outputs such as tracks or points, even when they are not scalar images; ordinary unannotated path columns do not gain that action automatically.

Workflow authors can add portable per-output requirements to a node instance, for example when configuring a generic file-source node for a specialist format.
Such additions are explicit workflow edits and are visually separate from the local **Favorite environment** control.
Tool requirements and workflow additions are combined; additions cannot silently remove a tool's hard requirement.
Changing an incorrect tool declaration requires editing the tool or using an explicit one-time viewing override.
The first release does not add inherited node-wide defaults or arbitrary expressions over parameters and rows.

An illustrative serialized output declaration is:

```json
{
  "viewer": {
    "napari": {
      "required_packages": [
        {"distribution": "example-track-reader", "version": ">=1.2,<2"}
      ],
      "recommended_packages": [
        {"distribution": "example-track-editor", "version": ">=1"}
      ],
      "reader_id": "example-track-reader",
      "napari_version": null
    }
  }
}
```

These package names are fictional examples.
`required_packages` means every listed Python distribution must be installed at a PEP 440-compatible version in the same environment for this output.
`recommended_packages` describes optional conveniences such as editing widgets; their absence does not prevent normal opening or remove the green requirements indicator.
Authors should not require an analysis plugin merely because it produced an ordinary TIFF that napari can already read.
`reader_id`, when present, is an optional napari reader identifier passed separately at launch; it does not participate in package compatibility and need not duplicate a package requirement.
Leave it absent when normal reader discovery is appropriate.
Viewer requirements never execute a workflow-supplied widget, command, or Python function automatically.

Package compatibility uses installed Python distribution metadata, with names normalized according to Python packaging rules and versions evaluated with PEP 440 specifiers.
It is deliberately independent of npe1 or npe2 manifests, napari plugin discovery, contribution registration, and enabled/disabled flags.
The optional `reader_id` is a launch instruction, never a package identity inferred from a distribution name, display label, or Python import module.
Every required or recommended package declaration needs an explicit distribution name; a package unavailable from PyPI may still be checked when already installed in an external environment, while managed setup reports that manual installation is required.
Package version constraints, and a rarely needed napari release constraint, use validated Python package version specifiers.
These are software release constraints, not references to locally named environments.
Support a list of jointly required packages initially; alternative requirement sets can be added later if real workflows need them.
When combining tool declarations and workflow additions, deduplicate normalized distribution names and intersect constraints on the same distribution or napari release.
A required declaration takes precedence over a recommendation for the same distribution.
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
Export also carries a derived, versioned viewing-requirement manifest keyed by structural output identity so an importer can report viewer needs before all tool packages are available.
This manifest is an export snapshot, not a second editable requirement store.
After dependencies load, compare it with authoritative tool/graph metadata and report unresolved or changed declarations before declaring coverage.
Missing or unresolvable tool metadata must produce “requirements unknown,” not an empty list and a green report.

This required a coordinated library schema/API change: the strict graph/archive models rejected unsupported extra fields before that change.
Do not hide the feature in unknown graph keys, environment labels, package execution requirements, or a platform-only archive that the library cannot preserve.
Version the affected wire contracts, define legacy input as having no viewer declaration, and make older readers reject unsupported newer schemas clearly rather than dropping requirements.
The coordinated library and platform graph contract is schema version 2.
Loaders accepting schema-v1 graphs recursively normalize them to schema v2 with absent viewer declarations and no instance additions before validation, persistence, or hashing.
Artifact hashes are computed from the normalized canonical schema-v2 graph and referenced owned sources, include portable viewer declarations and instance additions, and continue to exclude every local environment preference.
Workspace migration first presents a write-free preview with a content-derived plan identity; startup never confirms it on the user's behalf.
Until the user confirms, affected saved workflows, root drafts, and nested snapshots remain byte-for-byte unchanged and the affected workflows remain unavailable while unrelated current workflows continue working.
Confirmation atomically normalizes the saved graph, its saved artifact hash, the durable root draft graph, and that draft's saved-baseline graph/hash; a clean draft remains clean, while an actually divergent draft remains dirty against the migrated baseline.
Before replacement, every original authority is synchronized byte-for-byte under `<workspace>/.bioimageflow/backups/workflow-format/<plan-id>/...`; a confirmed forward journal completes after interruption, and a changed preview source rejects confirmation as stale.
The same recursive normalization applies to nested snapshots and archives, and lifecycle records or provenance that cache an affected artifact hash are updated through their existing identity-aware coordinator rather than left pointing at the pre-normalization digest.
Exports never contain environment IDs/names/paths, local selection rules, process state, credentials, or executable install commands.
Optional environment recipes or lockfiles are separate explicit exports and are not required to exchange a workflow.

Local preference changes cannot dirty a workflow or change its artifact hash or execution cache keys.
Portable requirement additions are document content and do change artifact identity.
Viewer metadata must be excluded from processing dependency resolution and semantic execution cache inputs; this does not promise to suppress existing invalidation caused by an actual tool source/version change.

## 4. Compatibility and environment selection

### 4.1 What the indicators mean

Environment health, package-requirement satisfaction, and actual reader/runtime behavior are separate facts.

| Indicator | Meaning | Normal action |
| --- | --- | --- |
| Green check, “Required packages installed” | Fresh Python distribution metadata satisfies every required package's PEP 440 constraint | Qualifies by declared package requirements; not proof that a reader or plugin will work |
| Amber warning, “Needs attention” | A required distribution is absent or its installed version is outside the constraint | Explain the cause; offer setup or an explicit one-time attempt |
| Gray question mark, “Not verified” | Distribution inventory is stale, the probe failed, or requirements could not be resolved | Refresh or inspect; no claim of compatibility |
| Unavailable | Interpreter missing, setup incomplete, unsupported launch, or known launch failure | Repair/setup; cannot launch |

A green check is a status icon, not an editable checkbox.
Use text and accessible labels as well as color.
It means only that the declared required Python distributions are installed at satisfying versions.
It is not evidence that napari discovered or enabled a plugin, that the optional reader ID is registered, that packages are mutually compatible, or that the selected artifact can be read.
For unannotated outputs, show “No declared package requirements”; do not convert discovery or manifest observations into a green compatibility claim.
Such an output may still open normally in a launchable environment using napari's standard reader handling.

Compatibility inventory records installed Python distribution names and versions, napari/Python versions, probe time, and an environment fingerprint.
Probe in the target environment, outside the backend process, with time and output bounds.
Do not import plugins into the backend to inspect them.
Refresh after creation, registration, explicit Refresh, detected package/configuration changes, and viewer restart; revalidate before launch when cached evidence is stale.
A running viewer's loaded inventory may differ from its on-disk installation after package changes; report restart required rather than claiming it can use the new packages immediately.

Actual reader acceptance may depend on napari's runtime discovery, file contents, and whether the artifact is a directory. [Napari reader contributions](https://napari.org/stable/plugins/building_a_plugin/guides.html).
Do not use npe1/npe2 manifests, discovered contributions, or enabled flags to decide declared-package compatibility.
Pass an explicit optional reader ID only for the selected open; if it is missing, disabled, incompatible, ambiguous, or rejects the artifact, report that launch-time failure without retracting the separate installed-package fact or silently selecting another environment.

### 4.2 Deterministic selection

The backend resolves the addressed artifact, requirements, and candidates and returns both the chosen environment and an explanation.
The frontend renders this result and does not implement a competing resolver.

For an output with known hard requirements, first exclude candidates that fail those requirements or cannot launch.
Rank the remaining candidates in this order:

1. The user's saved favorite for this structural output identity.
2. The first matching filename rule's preferred environment.
3. The user's global default environment.
4. Other candidates, preferring more satisfied optional recommendations, then stable registration order.

Within equal recommendation scores, stable registration order wins; renaming, starting a viewer, and transient process state do not reshuffle defaults.
An explicit reader ID in the output declaration controls the launch request when present and does not affect package eligibility.
A format preference never makes an environment with missing hard requirements eligible.
One-time environment selection bypasses this preference ranking for that open without changing stored defaults; the existing requirements check or explicit **Try opening anyway** still applies.

For an unannotated artifact, apply the same preference order among launchable environments.
Normal napari opening remains available where there is no declared requirement; lack of an annotation is not a setup error, and reader success or failure is determined at launch time.
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
Legacy viewer    napari <detected>    Environment missing   [Locate ...]

File opening rules (optional; first match wins)            [Add rule]
Filename pattern        Preferred environment       Reader (optional)
*_labels.tif            Microscopy                  Selected reader
*.ome.zarr              Multiscale                  Selected reader
*.tif                   Microscopy                  Automatic
```

Version placeholders and format examples illustrate the layout, not guaranteed package support.
Details show path, ownership (“Managed by BioImageFlow” or “External”), detected versions, installed Python distributions, last check, and relevant actions.
The **Launch empty viewer** action uses a dedicated environment launch request and does not emulate launch by sending an empty artifact list to `viewer.open()`.
Provide Refresh and Launch empty viewer; managed entries also offer Create modified copy.
Long paths collapse without hiding their full selectable text, and actions remain usable in a narrow settings window.

### 5.2 Filename rules and extension shortcuts

Keep associations because they serve standalone images, generic file-source outputs, and old workflows without annotations.
A rule contains one filename pattern, one environment ID, an enabled flag defaulting to true, and an optional reader ID to attempt in that environment; its position in the saved list defines its priority.
Reader is optional because choosing an environment and choosing a reader within it are distinct operations.
Napari already supports reader preferences and explicit reader selection; pass an explicit reader only when the resolved request calls for one. [Napari viewer API](https://napari.org/dev/api/napari.Viewer.html).

The Add rule form defaults to **Extension**, accepting `tif` or `.tif` and showing the resulting `*.tif` pattern before saving.
Compound extensions such as `.ome.tif`, `.nii.gz`, and `.ome.zarr` remain intact.
An optional **Filename pattern** mode accepts patterns such as `*_labels.tif`, `experiment-??.czi`, or an exact extensionless basename.
Both modes produce the same canonical rule type; do not persist parallel extension and glob maps or require users to fill two matching fields.
Adding several extensions is a convenience that creates separate adjacent rules with the same target; users can then reorder or edit them independently.

Match the entire file or directory basename, case-insensitively and independently of the host OS.
The initial pattern language supports literals, `*` for zero or more characters, `?` for one character, and bracket character classes including `[!...]` negation.
Bracket forms such as `[*]` and `[?]` match literal wildcard characters; reject malformed classes.
Leading dots are ordinary characters, not a special hidden-file exclusion.
Do not support path separators, recursive `**`, brace expansion, regular expressions, or filesystem traversal; patterns select among already addressed artifacts and never enumerate files.
Directory names such as `sample.ome.zarr` are eligible, but the reader must still accept directories.
Full-path and workspace-relative patterns are deferred because moves and platform differences would change their meaning.

Evaluate enabled rules from top to bottom; the first matching rule wins.
Provide Move up/down actions and a “Test filename” field that shows every matching rule and identifies the winner.
Show the first-match rule beside the table and preview overlaps for the edited example or currently selected artifact; do not claim exhaustive detection of overlapping glob languages.
Reject duplicate normalized patterns, including an extension shorthand and its equivalent simple glob.
For example, place `*_labels.tif` and `*.ome.tif` above `*.tif`; there is no additional implicit longest-suffix or glob-specificity ranking.
When authoring a rule for an actual image, preview its effective winner before saving so an earlier broad rule cannot silently hide the new rule.
Only the winning rule participates in environment selection; if its environment is unavailable or incompatible, explain that and continue to the global/default candidate fallback rather than trying hidden lower-priority matching rules.
Paths with no matching rule fall back to output requirements and normal environment/reader selection.

Environment details may show reader formats observed during an actual viewer session and optionally suggest rules, but those observations never affect package compatibility; never install broad `*` associations automatically.
Warn when a user creates a catch-all `*` rule that would hide later rules; a global default is normally clearer.
A filename match is a preference, not proof that a reader supports every variant of a format.
An optional reader rule applies only when the selected environment is the rule's environment and no hard reader declaration conflicts.
Otherwise show why it was ignored and use the hard reader or normal discovery.
Raw JSON import/export of local configuration may be a later advanced convenience; normal configuration and validation must work without it.

### 5.3 Open button and dropdown

The existing **Open in napari** becomes a split button.
Its main action opens in the resolved environment; its tooltip/accessibility label includes that environment and selection reason.
The arrow opens a popover showing all registered environments with status, detected napari version, and a short reason when requirements are unmet.
Keep unavailable entries visible with disabled launch controls so users can understand or repair them; removing an existing favorite remains available.

Always show the selected output name and its structural output identity context.
There is no favorite-scope selector: one favorite applies to all rows and future results of that structural output identity.

Use one exclusive, toggleable star beside each environment for the addressed structural output identity:

- Click an empty star to set that environment as the sole favorite, atomically replacing any previous favorite for that output identity.
- Click the filled star to unset the favorite and resume selection from the first matching filename rule, then the global default, then another qualifying environment.
- At most one star is filled in the visible list, and no star is filled when the output identity has no explicit favorite.
- Clicking the environment row or its open control opens the currently selected artifact once in that environment without saving a preference; clicking a star never launches anything.

The green check describes installed package requirements; the star describes the explicit favorite; a separate **Will open in …** line shows the effective environment and reason.
Never fill a star merely because an environment was selected by a filename rule, the global default, or fallback ranking.
Use accessible labels such as **Set favorite for this output** and **Unset favorite for this output**; star buttons expose their pressed state to assistive technology.

Provide **Unset favorite**, **Manage environments**, and **Create environment for these requirements**.
An incompatible saved favorite remains visible with its warning and can always be unset; setting a new incompatible persistent favorite is disallowed under the normal requirements contract.
Do not embed a button inside another button or a menuitem with conflicting keyboard semantics; use a popover list with independently focusable launch and preference controls.

The structural output identity covers the entire output column, including filtered/off-screen rows and future results, subject to a fresh compatibility check for each artifact.
Opening one cell still opens only that selected artifact; favorite coverage is not a bulk-open operation.
Filename rules and the global default in Settings are the other persisted selection preferences; neither creates another favorite scope.
Node-wide defaults, workflow-wide defaults, and batch-setting selected rows are deferred until a concrete need justifies their additional interaction and inheritance rules.
The existing Ctrl+Click replace action clears layers only in the selected environment's viewer.
Expose an explicit **Replace layers and open** action as well so replacement does not depend solely on a modifier key.
Setup, failure, or a menu selection must not clear another environment's viewer.

## 6. Local preference persistence

Environment registrations, the global default, and format rules belong to the existing per-user application settings store.
The single favorite mapping keyed by structural output identity belongs to a separate versioned per-user `viewer-preferences.json` store alongside the application settings store.
Keeping favorites separate lets workflow identity remaps and snapshot overlays use their own revision-checked lifecycle without rewriting environment registrations or filename rules.
Browser local storage may cache this state but is never its authority.

Use these logical keys:

```text
output key = (workspace identity, root workflow identity generation,
              structural node-instance path,
              output field key or stable public output ID)

favorite: output key -> environment ID
```

Use existing stable workspace identity where available, otherwise define a persisted local workspace identity as part of implementation; do not hash a mutable display name or raw workflow path as identity.
Workflow path can be retained as a lookup/display index, with the generation guarding against delete-and-recreate collisions.
Structural node paths use node IDs, never node labels or nesting positions.
Tool output field names are schema identities until the library offers stable field IDs; a tool-field rename invalidates that preference.
Public workflow output labels can change while their stable IDs preserve preferences.
An exposed workflow output has its own user preference key; it inherits viewing requirements from its provider, not the provider's local preference.

No result snapshot, record, DataFrame index, displayed row, filename, or row offset participates in the favorite key.
There are no row favorites, row exceptions, or result-row preference records to store, prune, copy, remap, or migrate.
The backend still resolves a merged-table cell to its structural provider output so the same favorite applies across sorting, filtering, pagination, retained results, and future results.
Direct and merged table responses expose each column's viewer declaration from the exact retained result snapshot, with an explicit legacy-unpinned status when no immutable identity exists; the frontend never substitutes mutable current graph or tool metadata for specialized action visibility.

Local rules survive restart, table sorting/pagination, workflow display renaming, and moves within the same workspace through the normal identity-aware lifecycle coordinator.
Deletion drops that workflow generation's rules.
Reimport, duplicate, Save as copy, paste, and independent embeddings start without copied output preferences.
Source update preserves rules only for surviving structural output identities and rechecks them against changed requirements.
Environment deletion clears references; an incompatible but still registered environment retains its preference for repair.

Private nested edits use a session-scoped preference overlay tied to the snapshot UUID.
Apply remaps surviving entries to the accepted parent instance; discard drops the overlay.
After parent persistence succeeds, the client finalizes the child snapshot through an idempotent backend endpoint that derives the destination from the stored owner and verifies that the current parent snapshot or root draft embeds the exact accepted child graph.
The endpoint remaps into the parent session for nested owners and into the current workflow generation for saved root owners; it rejects unsaved root owners, so the UI must not offer durable output favorites before a workflow has persistent identity.
Preference writes bind to the captured workspace/generation/session so a delayed request cannot target a replacement workflow or another workspace.
The resolver returns the exact server-derived persistent preference key for the addressed structural output, including the durable workspace UUID, so a client can create the first favorite without inventing or inferring workspace identity.
They use revision-checked set/unset actions so a stale toggle cannot accidentally clear a favorite changed in another window.
Each structural output identity stores zero or one environment ID, with no independent per-environment boolean favorites.
Preference changes are atomic local UI state and do not acquire a graph execution lock or prevent viewing during execution.

## 7. Workflow import and setup guidance

After import, show a non-blocking **Viewing requirements** report with coverage per structural output identity, including nested nodes.
Run the same check on workflow open, requirement changes, and relevant environment inventory changes, without reopening a modal repeatedly.
Include inactive nodes in the report, marked inactive, but preselect only the active workflow's unmet output requirements in setup.
Imported workflows with no declarations continue to work through automatic readers and local format rules.

Report precise compatibility failures: missing distribution, installed version outside the PEP 440 constraint, unknown distribution metadata, unsupported viewer, or required packages split across environments.
Two required packages installed in different environments do not satisfy one output that needs both.
Conversely, two incompatible package sets used by different outputs are acceptable when separate environments cover them.
Reader IDs, manifest discovery, enabled flags, and actual plugin loading do not participate in this passive report; any resulting failure is reported when napari handles the selected open request.
Summaries should say “2 outputs need viewer setup,” rather than claiming that the workflow cannot run.

For each uncovered requirement set, offer:

- Use a satisfying registered environment, or attach an existing installation.
- Refresh/restart or repair packages through the environment's own configuration.
- Create a new managed environment, with requirements prefilled.
- Continue and configure later.

Group identical requirement sets for convenience.
Do not assume all missing packages can be installed together: solving a combined environment is an optional explicit choice, with per-output alternatives available if it fails.
If the required set for a single output is itself unsatisfiable, report its conflicting constraints and point to the declaration; splitting that set cannot repair it.
The creation preview identifies requested distributions, constraints, source, and new environment name before installation starts.
Import and passive checks never download/install packages or execute workflow-provided installation instructions.
Unknown or private packages require manual installation in an external environment in the first release; do not guess URLs from reader IDs, add archive-provided package sources, or copy credentials into a workflow.

The implemented desktop-only `POST /api/v1/napari/viewing-readiness` endpoint accepts the portable viewing-requirement manifest itself, so an import success response can be evaluated without rereading mutable workflow state.
It returns every structural output identity, its retained viewer or unknown reason, per-environment package-only candidate status and issues, an effective compatible environment when one exists, and covered/not-covered/unknown summary counts suitable for setup guidance.
Identical compatibility sets receive a stable normalized SHA-256 group ID, explicit member identities, and managed-create prefill whose package source remains `unverified`; different groups are never implicitly unioned.
Known entries with no viewer or no napari declaration remain normally covered, while unknown entries and all of their launchable candidates remain unknown rather than green.
Inventory freshness gates only required distributions and an explicit napari version constraint: a reader-only or recommended-only declaration remains covered in a launchable environment, and stale metadata does not invent missing recommendations.

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
Viewer configuration isolation must use the same configuration that the launched viewer will use; it does not turn manifest discovery or enabled state into package-compatibility evidence.
If an external environment's ordinary napari configuration is imported, make that an explicit one-time copy; subsequent platform launches use their own configuration.

The backend exposes typed desktop-only managed mutation routes for create, recipe-based copy, retry, operation polling/cancellation, and owned removal alongside the registry, probe, and per-environment lifecycle contracts.
Initiating mutations use the registry revision compare-and-swap contract, every environment has at most one active mutation, and unrelated environment operations use independent locks.
Operations remain in the durable registry history after completion; a removed entry therefore remains pollable with `environment: null`.
Successful owned removal first stops only that environment's launcher, then waits for public Wetlands removal, and finally clears the registry entry/default/filename rules in one settings mutation while invoking an injected idempotent favorite-cleanup seam.
If reference or registry finalization fails after Wetlands removal, the operation remains durably `removing` so startup can replay finalization instead of leaving an unrecoverable terminal tombstone.
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

Delivery advanced in three independently verifiable increments:

1. Registry, environment probes, isolated launcher/configuration state, settings list, split button, and one-time selection; existing opening was preserved and the singleton migrated.
2. Coordinated schema-v2 library annotation/archive support, recursive normalization and artifact-hash/draft-baseline migration, output provenance, compatibility resolver, one favorite per structural output identity, filename rules with extension shortcuts, and import report.
3. Managed environment creation and Create modified copy using the same requirements report and resolver.

The feature is complete only when all three increments are available, and all three are now delivered.
The Phase B increment delivered the persistent registry, immutable registration and launch-context identity, package-only inventory probes, typed desktop-only registry/settings routes, singleton adoption, and ordered filename rules from increment 1.
Phase C replaced the explicit-ID launch path with independently locked, UUID-keyed processes that use each entry's persisted argv prefix and configuration file, carry optional reader IDs as napari's `plugin=` argument, acknowledge only after Qt-thread completion, expose per-environment status/events, and never replay an open whose outcome may be unknown.
External venv and Conda entries use direct argv-only subprocesses. Recipe-created managed entries resolve their recorded Wetlands name with the public `EnvironmentManager.environment(name)` API and call that generation's public `ManagedEnvironment.spawn(argv, env=...)`; an adopted legacy Wetlands 1 pixi workspace may fall back narrowly to its persisted interpreter when no matching current Wetlands generation exists.
The no-ID open/status/shutdown routes retain the legacy managed-singleton compatibility path, while explicit registered IDs never provision or mutate their environment.
The Phase C backend advanced canonical graphs to schema v2 and now migrates saved/draft/nested authorities and hashes only after an explicit preview confirmation, with byte-preserving backups and a forward journal.
It also captured immutable public run/node/result/record identities for result pages, read retained viewer metadata through public storage APIs, resolved package-only compatibility, stored favorites in a separate revisioned file, and remapped them through workflow move/delete and nested-session lifecycles.
The same resolver candidate evaluator powers the passive manifest readiness endpoint and retained-artifact resolution, so required-package co-location, PEP 440 checks, freshness, unavailable-state handling, recommendations, and reader independence cannot drift; passive evaluation reads only the registered inventory snapshot and never probes, installs, launches, reads workflow state, or executes archive content.
The managed backend uses only public Wetlands 2 environment and operation APIs; it does not install a bridge distribution because the platform launches its standalone helper script inside the selected environment.
The managed-environment API provides durable create/copy/retry/cancel/delete operations with restart reconciliation.
The frontend settings panel consumes those operations, displays per-environment inventory and lifecycle state, manages defaults and ordered filename rules, and launches an addressed empty viewer.
The output split action resolves an exact retained artifact through the backend, keeps one exclusive toggleable structural-output favorite, supports one-shot environment selection and replace-layers dispatch, and exposes honest incompatible, unknown, and unavailable candidates.
The passive report evaluates imported or currently saved workflow requirements without provisioning or launching an environment and can prefill managed setup from one normalized requirement group.
The product decisions above do not depend on a new general-purpose environment manager or a complex association editor.

The affected v1 viewer/settings/API sections, v2 graph/inspection/archive/lifecycle contracts, library specifications and public contract references, and `PLATFORM_CONTEXT.md` were updated together with this implementation; further implementation of this feature updates them together as well.
Native desktop certification is still required before declaring the feature complete: the earlier local attempt did not leave a reliable completion artifact and therefore is not acceptance evidence.
The existing normative documents continue to govern unaffected implementation.

## 10. Acceptance criteria

1. Two environments with the same napari version and different plugins appear as distinct named entries and run concurrently without shared layers or reader preferences.
2. Renaming an environment preserves every reference; attaching the same canonical interpreter twice does not create duplicates.
3. Different outputs of one node resolve independently, including published outputs through nested workflows and two embeddings of one child.
4. Required packages must all be satisfied in one environment for one output; requirements for different outputs can be covered by different environments.
5. Missing recommended packages do not block opening; absent, version-incompatible, stale, and unknown required distributions produce distinct explanations without consulting npe1/npe2 manifests, discovery, or enabled flags.
6. A matching filename rule cannot override a hard package requirement or an explicit output reader ID; extension shortcuts, compound suffixes, directory names, case-insensitive patterns, duplicates, and overlapping rules obey the documented first-match order and preview.
7. Choosing an environment row opens the selected artifact exactly once and leaves preferences unchanged; one keyboard-accessible star is exclusive and toggleable per structural output identity, another star replaces it, the filled star unsets it, and star actions never launch a viewer.
8. Output favorites survive restart, label changes, same-workspace moves, all rows, and future results, but do not leak through export/import, copy, delete-and-recreate, discarded nested edits, or workspace switches; no row favorite, exception, or result-row preference state exists or is migrated.
9. Export/import preserves recursive requirements and contains no local environment references or credentials; missing tool metadata yields an incomplete report rather than false coverage.
10. An imported workflow with unmet viewer needs can still run; setup can create separate installations for incompatible requirements on different outputs.
11. Existing-environment checks make no package changes; managed creation uses Python 3.12 from Conda plus PyPI-installed napari 0.9.1/PyQt6 by default or the explicit napari 0.6.6/PyQt5 smoke matrix; failed or cancelled creation leaves old environments/defaults usable, and recipe changes create a separate installation.
12. Package/configuration drift and pending viewer restart invalidate stale compatibility claims; green means only that required distributions and PEP 440 constraints are satisfied, while actual reader/plugin failures are reported after dispatch.
13. A launch race starts one viewer per environment; a failure in one does not block another; ambiguous command completion is not automatically replayed.
14. Result selection survives table sorting, pagination, active-tab changes, and later graph edits; retained results use their captured requirements and representation.
15. Webapp endpoints reject local environment operations, and the import check never triggers installation or runs archive-provided commands.
16. Native smoke checks on each supported desktop OS cover an external Conda environment, a virtual environment, paths with spaces, managed creation, a missing plugin, explicit reader choice, and configuration isolation.
17. Selection precedence is favorite for the structural output identity, first matching filename rule, global default, then another qualifying environment; an unavailable or incompatible candidate falls through with an explanation.
18. No favorite scope selector or row-level favorite/exception control appears anywhere in the opening UI or persistence/API contract.
19. Schema-v1 graphs normalize recursively to schema v2 before hashing; a write-free preview and explicit confirmation preserve exact backups before saved documents, root draft baselines, and nested snapshots migrate atomically, so deferral changes no authority, clean/dirty state remains truthful, portable viewer metadata affects artifact identity, and local favorites never do.

Use `scripts/test` for implementation checks proportionate to each increment, following [Test lanes](docs/testing.md).
The bridge and native napari behavior additionally require real desktop checks; mocked unit tests and headless browser tests do not certify Qt startup or third-party plugin compatibility.
