# Distributed Execution Platform — Design Specification

**Status:** Proposed delta to [`platform_specs_v2.md`](platform_specs_v2.md).

**Goal:** Let users assign worker resource requirements, select local or Parsl execution without editing workflow data for every run, and inspect every execution through one engine-neutral Execution panel.

This document is deliberately not normative yet because `platform_specs_v2.md` describes implemented behavior.
After implementation and validation, the normative parts of this design should be merged into v2 Sections 2, 3, 8, 9, 12, 14, and 15.

## 1. Product Decisions

### 1.1 One execution model, several execution targets

The platform presents one execution model for Direct, Wetlands, attached Parsl, and submitted Parsl.
An **execution target** determines where and how a run is launched.
The built-in **Local** target automatically uses Direct for orchestrator-only work and Wetlands when worker execution is required.
Every distributed target is a named platform profile backed by Parsl configuration.
Every Parsl engine created by a platform profile uses `execution="workflow"` so `GraphState.config.execution` remains authoritative.

Users do not select Direct versus Wetlands for ordinary local runs.
That distinction is an implementation detail of the Local target.

The active target is selected next to the Run split button.
The main Run action and every split-button command use the visible target.
Changing the target is a user preference and does not dirty the workflow.

### 1.2 Scheduling belongs to the workflow

`GraphState.config.execution` remains the workflow's required `parallel` or `sequential` scheduling policy.
The platform must stop replacing that value with the legacy application setting at execution time.
The application setting becomes only the default used when creating a new workflow.

An explicit engine supplied by an execution target takes precedence over `GraphState.config.engine` for that run, matching the library's engine-precedence contract.
The graph engine value remains portable workflow preference and import/export data.
Platform execution profile IDs, Parsl configuration factories, credentials, executor bindings, routes, and launcher state never enter `GraphState`.

### 1.3 A job is an engine-neutral node attempt

In the platform UI, a **run** is one accepted workflow execution and a **job** is one compiled scoped node attempt within that run.
Examples of scoped job identities are `segment/cellpose` and `measure`.

A workflow boundary is displayed as an aggregate tree row over its descendant jobs.
A `DataFrameTool` job executes in the orchestrator.
A `ProcessingTool` job may dispatch one or more worker tasks through Wetlands or Parsl.

Individual Parsl futures, row chunks, provider blocks, and scheduler workers are **tasks**, not jobs.
Task drill-down is optional telemetry and is not required for the first platform release.
The panel must not claim that one Parsl task equals one scheduler job.

For submitted PSI/J execution, the one scheduler allocation that launches the orchestrator is shown separately as the **backend job** with its scheduler type, native ID when known, state, and message.
Parsl providers remain responsible for worker allocation and are not represented as PSI/J jobs.

### 1.4 One Execution panel for every engine

The Execution panel is not a Parsl-only surface.
Local Direct and Wetlands runs use the same run summary, job tree, node progress, error details, history, and cancellation controls as distributed runs.
Engine-specific fields are additive and hidden when unavailable.

### 1.5 Resource values are requirements, not promises

CPU, GPU, memory, and GPU memory values describe the resources required by one worker slot.
They are not presented as guaranteed limits unless the selected engine actually enforces or validates them.

Parsl validates every effective request against the selected executor slot.
Wetlands uses GPU requirements for worker GPU assignment, but the current library does not enforce CPU or memory capacity and does not use `max_concurrent`.
Direct executes no `ProcessingTool` worker jobs.

The Resources UI must explain these target-specific effects and must not call memory a hard limit.

## 2. Scope

### 2.1 Required in the first implementation increment

- Typed per-node resource overrides for `ProcessingTool` nodes.
- A Resources tab in the Nodes panel.
- A built-in Local execution target.
- Named attached Parsl profiles.
- A compact execution-target selector beside the Run split button.
- Preflight validation against the selected target.
- An engine-neutral Execution panel with per-job progress.
- One stable execution identity shared by the platform and BioImageFlow run storage.
- Execution history and reconnectable status for runs performed by the current platform process.
- Existing Run Workflow, Run Selected, retry, invalidation, recompute, and stop semantics.

### 2.2 Required in the submitted-execution increment

- Submitted local Parsl profiles.
- Submitted remote Parsl profiles using OpenSSH transport and PSI/J for Slurm, PBS, or LSF.
- Durable reconnection after the GUI or platform process restarts.
- Multiple concurrent submitted runs while retaining at most one attached run in the platform process.
- Backend-job status, connection-loss handling, durable cancellation, and explicit result download.
- Remote-path and explicit-upload input behavior.

### 2.3 Not in scope

- Creating or provisioning clusters, queues, Parsl providers, or worker environments.
- Accepting raw Parsl `Config`, DFK, executor, provider, callable, pickle, scheduler directive, shell fragment, SSH option, or literal secret values from workflow documents.
- Inferring uploads from strings or ordinary `Path` values.
- Automatically installing software on a remote cluster.
- Cost estimation.
- Live visualization of provider blocks or scheduler worker nodes.
- Per-task retry controls.
- Reading private Parsl or BioImageFlow storage files from the frontend.

## 3. Node Resource Model

### 3.1 Typed schema

`ToolNodeState.resources` becomes a typed value instead of `dict[str, Any]`:

```python
class NodeResourceOverrides(BaseModel):
    cpu: int | None = Field(default=None, ge=1)
    gpu: int | None = Field(default=None, ge=0)
    memory: str | None = None
    gpu_memory: str | None = None
    max_concurrent: int | None = Field(default=None, ge=0)
```

Missing fields mean **inherit the tool declaration**.
An empty object means all fields inherit.
The platform stores only explicit overrides and removes a field when the user resets it to the declared value.

Memory values use the library's canonical integral capacity grammar: `B`, `KB`, `MB`, `GB`, `TB`, `KiB`, `MiB`, `GiB`, or `TiB`.
Examples are `16GB` and `8192MiB`.
Whitespace, fractions, bare numbers, negative values, and unknown units are rejected.

### 3.2 Effective values and minimum floors

For each field, the effective value is the explicit node override when present and otherwise the tool's `ResourceSpec` declaration.
If the tool declares no `ResourceSpec`, the library defaults apply: one CPU, zero GPUs, no memory requirement, no GPU-memory requirement, and unlimited node concurrency.

CPU, GPU, memory, and GPU memory overrides may not be below the tool declaration.
`max_concurrent` is a user cap rather than a minimum requirement, so a non-zero override may be lower than the tool declaration but may not raise a non-zero tool cap.
Zero continues to mean unlimited only when both the declaration and override permit it.

The backend is the validation authority.
If a package update makes a stored override invalid, the graph receives a resource validation error rather than silently clamping or rewriting the workflow.

### 3.3 Applicability

Editable resource overrides apply only to `ProcessingTool` nodes.
`DataFrameTool` nodes run in the orchestrator and show no editable worker-resource controls.
Workflow nodes show a read-only aggregate of their internal processing requirements and an **Open workflow to edit resources** action.
Resource values are edited on the internal real tool nodes and are preserved at every recursive depth.
`WorkflowNodeState.resources` has no execution meaning and is removed from the canonical model after compatibility migration.

### 3.4 Cache semantics

Resource changes do not change result keys and do not invalidate a cached result because they describe execution placement rather than result semantics.
The Resources tab states that changes apply to the next uncached or explicitly recomputed attempt.
The existing recompute action is the way to force execution under changed resources.

### 3.5 Portable library boundary

The BioImageFlow recursive graph format must round-trip an optional resource override on each tool node, or the library must expose an equivalent public per-node override API that the platform can apply after materialization and recover during serialization.
The platform must not mutate the tool class, because two nodes using the same tool class may require different resources.
The platform must not depend on private `Node` or tool attributes to implement this contract.

Until this library boundary exists, resource editing may be prototyped in the platform graph but must not be described as portable or execution-effective.

## 4. Nodes Panel

### 4.1 Tabs

For one selected node, the Nodes panel contains three tabs:

- **Parameters** contains the current node header, documentation, input parameters, workflow-interface exposure, and output templates.
- **Resources** contains worker requirements and selected-target compatibility.
- **Execution** contains the selected job's status, progress, error, traceback, and node-scoped log view for the selected run.

The current long single-column Node panel is reorganized into these tabs without changing parameter, interface, output-template, or log semantics.
The last selected tab is remembered as a panel-level UI preference.
Multi-selection does not support bulk resource editing in the first increment.

### 4.2 Resources tab

The Resources tab displays a row for each resource with **Tool requirement**, **Override**, and **Effective** values.
Each override has an explicit Reset action.
CPU and GPU use integer spinners.
Memory and GPU memory use validated text fields with unit examples.
Max concurrent uses an integer spinner where zero is labelled **Unlimited**.

The tab also shows:

- the currently selected execution target;
- whether each field is enforced, validated, used as a hint, or ignored by that target;
- eligible executor labels after successful Parsl preflight;
- the selected executor and route reason when routing is unambiguous;
- a clear incompatibility message when no executor slot can satisfy the node.

Changing a resource value is an ordinary graph edit.
It participates in draft compare-and-swap, undo/redo, nested snapshot Save, clipboard, grouping, import/export, validation, and dirty-state behavior.
It is locked wherever other graph mutations are locked.

### 4.3 Canvas badges

A processing node whose effective GPU requirement is greater than zero shows a GPU badge.
The badge tooltip shows the effective GPU count and whether it is declared by the tool or overridden by the workflow.
No CPU badge is added because one CPU is the common default and would create visual noise.

## 5. Execution Target Selection

### 5.1 Toolbar interaction

A compact target selector appears immediately before the Run split button.
It shows **Local** or the selected distributed profile name.
If only Local is available, the selector may collapse to a non-interactive **Local** badge.

The Run split menu continues to offer:

- Run Workflow;
- Run Selected;
- Retry Failed Execution;
- Invalidate Failed Nodes and Retry;
- Recompute Workflow;
- Stop or Cancel when unambiguous.

Every command uses the visible target.
Retry commands capture the original target profile revision unless the user explicitly chooses **Retry on current target** from the execution details.
The main Run button remains one click for a locally valid workflow.

The selected target is remembered in the current UI session.
`default_execution_target_id` supplies the initial user preference.
No target profile ID is written into the workflow graph.

### 5.2 Capability and availability

The target selector shows only profiles available in the current deployment.
A disabled profile remains visible in Preferences with its reason but is not offered for a run.
Examples include missing `bioimageflow[parsl]`, unavailable PSI/J support, a missing configuration factory, invalid executor labels, or an administrator-disabled webapp profile.

Selecting a target never imports or executes its configuration factory in the frontend.
The backend resolves and validates the selected immutable profile revision during preflight.

## 6. Distributed Execution Profiles

### 6.1 Settings ownership

Distributed execution profiles are application-wide, platform-owned integration settings under **Preferences → Execution**.
They are not contributed by tool packages and are never embedded in a workflow archive.

Desktop users may create and edit trusted profiles.
In webapp mode, profiles are provisioned by the administrator and are read-only to ordinary users unless a later authorization model explicitly grants profile-management permission.
This prevents a browser user from selecting arbitrary server-side factories, SSH hosts, executables, or environment-variable names.

### 6.2 Profile schema

The persisted profile is a strict, versioned, discriminated model:

```python
class DistributedExecutionProfile(BaseModel):
    schema: Literal["bioimageflow.platform.execution-profile.v1"]
    id: str
    revision: int
    name: str
    enabled: bool = True
    mode: Literal["attached", "submitted_local", "submitted_remote"]
    parsl_config: ParslConfigReference
    executor_bindings: dict[str, ExecutorBinding]
    environment_routes: dict[str, str] = {}
    shared_runtime_root: str | None = None
    task_policy: ParslTaskPolicy = ParslTaskPolicy()
    launch: SubmittedLocalLaunch | RemoteClusterLaunch | None = None
    transport: SSHTransportProfile | None = None
    remote_workflow_root: str | None = None
```

The nested value shapes follow the library's JSON-safe public contracts for `ParslConfigRef`, `ExecutorBinding`, `ExecutorCapabilities`, `WorkerSlotCapacity`, `WorkerEnvironmentAttestation`, and `ParslTaskPolicy`.
Attached profiles require neither launch nor transport configuration.
Submitted-local profiles require a local orchestrator launch and no SSH transport.
Submitted-remote profiles require OpenSSH transport plus an explicit PSI/J launch for Slurm, PBS, or LSF.
They also require an absolute cluster workflow root.
The platform derives one workflow's cluster storage as `<remote_workflow_root>/<workflow_id>/results` after validating every workflow-ID segment.
This derived workflow storage is separate from the transport staging root and from the optional shared runtime root.

The platform captures the profile ID, revision, complete sanitized profile snapshot, and non-secret digest in the run intent.
A sanitized snapshot contains secret-reference environment-variable names but never their resolved values.
A profile edit increments its revision.
A profile used by a non-terminal submitted run cannot be removed because reconnect and cancellation still depend on it.

### 6.3 Configuration factory and secrets

`ParslConfigReference` stores an importable `module:callable` factory, finite JSON-safe keyword arguments, and optional mappings from factory argument names to environment-variable names.
The settings API rejects literal credentials, secret-looking literal fields, arbitrary callables, pickle data, live Parsl objects, shell fragments, and unknown keys.

Resolved secret values are never returned by the API, written to settings, copied into a workflow, logged, or placed in execution events.
Preferences displays only whether every referenced environment variable is available on the launch host.

### 6.4 Executor cards

Each executor binding is edited as a card with:

- an exact executor label that must exist in the produced Parsl configuration;
- worker-slot CPU, GPU, memory, and GPU-memory capacities;
- supported storage modes;
- supported tool-origin modes;
- explicit environment attestations.

The UI validates duplicate labels, duplicate environment identities, invalid capacity units, unsupported storage mode, and absent attestations before saving.
The first implementation supports only `shared_fs`; `staged` is displayed as unsupported rather than silently accepted.

Node-specific routes are not persisted in application settings because scoped node paths are workflow-specific.
If several bindings are compatible and no environment route resolves the ambiguity, run preflight asks the user to choose an executor for the affected nodes.
Those choices belong to the immutable run intent and do not dirty the workflow.

### 6.5 Profile editor

The Execution preference tab contains:

- the default execution target;
- the default scheduling policy for newly created workflows;
- a read-only Local target capability summary;
- distributed profile cards with Add, Edit, Duplicate, Test, Enable/Disable, and Remove actions.

The distributed profile editor uses sections for General, Parsl configuration, Executors, Task policy, and Launch/Transport.
It expands responsively beyond the current narrow settings dialog and never requires horizontal scrolling to reach fields or actions.

**Test profile** validates the stored schema, imports and calls the trusted factory, verifies `retries=0`, compares configured executor labels to bindings, checks secret-reference availability, and closes all test-created resources.
For a remote profile, an explicit **Test connection** action may invoke the installed cluster agent through normal OpenSSH configuration.
Testing does not submit a workflow or scheduler job.

## 7. Run Preflight

### 7.1 Preflight contract

Every Run command is a command barrier that first flushes the accepted draft and then requests preflight for that exact workflow ID, draft revision, graph, selected target profile revision, execution mode, and requested node boundary.

Preflight:

1. validates and compiles the same recursive execution subgraph that the run would use;
2. resolves the effective scheduling policy and engine;
3. derives every processing worker requirement using the effective per-node resources;
4. validates the selected profile and configuration factory;
5. verifies executor labels and environment attestations;
6. resolves each node route by explicit run choice, environment route, or one unique compatible binding;
7. validates slot capacity and task-policy bounds;
8. validates shared-storage and tool-origin requirements;
9. validates submitted launch, transport, and path semantics;
10. returns an immutable preflight token and a presentation summary.

The short-lived, single-use token captures the graph digest, draft revision, workflow identity generation, profile revision and digest, selected targets, resolved routes, and destructive invalidation effects.
Run apply rechecks every captured value.
A conflict launches nothing.

### 7.2 Preflight presentation

Local preflight remains unobtrusive unless it finds an error or the existing out-of-date confirmation is required.
Distributed preflight shows a compact summary before the first run with a profile and whenever routing choices or remote uploads require confirmation.

The summary lists scheduled scoped nodes, effective resource requests, executor routes, cache hits, remote backend, and any paths interpreted as cluster paths.
An incompatibility identifies the node, requested resources, candidate executor, and each failed capacity or environment condition.

## 8. Execution Identity and State

### 8.1 One identity

The platform `execution_id`, the BioImageFlow canonical run ID, and the submitted launcher run ID are the same value.
It uses the library form `run_` followed by 32 lowercase hexadecimal characters.

Attached execution creates `WorkflowExecutionContext(run_id=execution_id)` and supplies it to `compute`.
Submitted execution uses the ID allocated by `submit_workflow`.
Platform code must not create an unrelated UUID and later guess the corresponding library run.

### 8.2 Run states

The normalized platform run states are:

- `preparing`;
- `prepared`;
- `queued`;
- `starting`;
- `running`;
- `cancel_requested`;
- `finalizing`;
- `succeeded`;
- `failed`;
- `cancelled`;
- `lost`.

Local attached runs normally use `preparing`, `running`, and a terminal state.
Submitted launcher states map without losing their original value.
Backend-specific status is also retained for display.
Connection loss is observation state and never changes a run to failed or lost.

### 8.3 Job states

Job states are:

- `waiting`;
- `running`;
- `cached`;
- `succeeded`;
- `failed`;
- `cancelled`;
- `skipped`;
- `blocked`.

Validation cache state such as `unexecuted` and `out_of_date` remains separate from execution-attempt state.
This prevents a cached job from being confused with a node whose current graph is merely valid.

### 8.4 Snapshot

The platform exposes an `ExecutionSnapshot` containing:

- execution ID, workflow ID, draft revision, graph digest, workflow identity generation, and requested node boundary;
- command mode and retry parent;
- execution target ID, target name, captured profile revision, effective engine, and scheduling policy;
- normalized and backend-specific run state;
- created, started, completed, and last-observed timestamps;
- overall terminal, running, waiting, cached, failed, and total job counts;
- backend-job metadata when applicable;
- a map of `JobSnapshot` values keyed by scoped node path;
- structured run errors;
- whether cancellation and result download are currently available;
- a monotonically increasing snapshot revision.

Each `JobSnapshot` contains the scoped node path, display name, node kind, parent workflow path, state, cached flag, executor label, route reason, effective resources, completed and total rows, optional sub-row message/current/maximum, timestamps, cache identities, and structured error detail.

Parallel progress is retained independently for every job.
The current single `ProgressInfo` pointer is insufficient because events from concurrent nodes interleave and reconnect must recover all job progress.

## 9. Execution Panel

### 9.1 Docking and activation

The new `execution` Dockview panel joins Node Data and Logger in the bottom tab group.
It is available through **View → Execution**.
The panel is created in the default layout with Node Data initially active.
Accepting a run reveals and activates Execution.
Closing it hides the panel but never cancels or forgets a run.

### 9.2 Run selector and summary

The panel header selects a run from the current workflow by default and can show all workspace runs.
The history list shows state, workflow, target, start time, and duration.
Active runs sort before terminal runs and terminal runs sort newest first.

The selected run summary shows:

- workflow and exact draft revision;
- command such as full, selected, retry, or recompute;
- target profile and effective engine/scheduling;
- state and duration;
- completed/cached/failed job counts;
- backend job and connection state when applicable;
- Cancel, Retry, Download Results, and Open Logs actions when applicable.

### 9.3 Job tree

The main table is a hierarchical tree using scoped workflow paths.
Its default columns are **Job**, **Status**, **Progress**, **Executor**, **Resources**, and **Duration**.

Workflow boundary rows aggregate all internal jobs.
Expanding a boundary reveals its immediate children.
The order follows the compiled deterministic plan, not completion timing.

Overall progress is terminal scheduled jobs divided by all scheduled jobs.
The UI does not manufacture a weighted percentage from unrelated node row counts.
Each running job shows its own completed rows and, when supplied by the tool, its sub-row message and current/maximum values.
When the total is unknown, the progress indicator is indeterminate.

Selecting a job:

- selects and reveals the corresponding node on the matching canvas when that draft revision is still open;
- opens its details drawer;
- offers **Open in Nodes → Execution**;
- offers **Show logs** with execution and node filters.

The details drawer shows timestamps, effective resources, route explanation, cache identities, structured error and traceback, and optional task summary.
Logs remain owned by the Logger panel and are not duplicated as a second full log browser.

### 9.4 Engine-specific presentation

Direct and Wetlands runs populate the same job tree.
DataFrame jobs display **Orchestrator** as executor.
Wetlands processing jobs display the environment or local worker label when known.

Parsl jobs display the resolved executor label and effective slot request.
When public task diagnostics are available, a collapsed task summary may show submitted, running, succeeded, failed, and cancelled counts.
The first implementation does not enumerate task JSON files through private storage paths.

Submitted runs show the launcher state and backend job card above the job tree.
For PSI/J this includes scheduler type, native job ID when durably known, scheduler state, and uncertainty messages.
Submission uncertainty retains the prepared run and never offers automatic resubmission.

### 9.5 Banner

The existing canvas banner becomes a compact notification rather than the primary monitor.
For one attached run it shows state, terminal job count, running job names, **Open Execution**, and Stop.
For several submitted runs it shows the active count and **Open Execution**.
Terminal success or failure links to the retained run in the Execution panel.

## 10. Concurrency, Locking, and Status Projection

### 10.1 Attached runs

The platform permits at most one attached Direct, Wetlands, or Parsl run in its process.
The existing global mutation lock remains active for that run in the first increment.
Read-only inspection remains allowed.

### 10.2 Submitted runs

Submitted runs own immutable graph and invocation snapshots and may outlive the GUI.
After durable submission, ordinary graph editing is not locked for the duration of a remote run.

Operations that can destroy or invalidate the addressed run's workflow or storage remain locked per workflow while a submitted run is non-terminal.
These include workflow deletion or move when it changes the bound storage, cache invalidation, destructive source replacement, and removal of the execution profile needed for reconnect.
The exact lock set must be enforced by the backend rather than only disabled in the frontend.

Multiple submitted runs may coexist, including runs of the same workflow when the library's guarded storage contract accepts them.
Starting a submitted run does not consume the one attached-run slot after submission has completed.

### 10.3 Canvas projection

A run projects statuses onto a canvas only when workflow ID and accepted draft revision match.
Editing the workflow after a submitted run starts leaves the Execution panel accurate but stops that run from overriding the edited canvas's validation projection.

When several runs match a canvas revision, the newest non-terminal run is projected by default.
Selecting **Show on canvas** in Execution temporarily chooses another matching run.
This selection is presentation state and never changes workflow or cache data.

Workflow nodes continue to aggregate descendant status while preserving the failing or cancelled scoped path.

## 11. Persistence and Reconnection

### 11.1 Platform execution registry

The platform keeps a small durable execution registry separate from the canonical workflow graph and library cache.
For each run it records the workflow identity, draft revision, graph digest, command, target profile ID and revision, sanitized target snapshot, library run ID, remote storage path when applicable, last consumed progress sequence, and normalized presentation snapshot.

No credential or resolved secret is stored.
For remote execution the retained reconnect tuple follows the library handoff: transport profile, cluster storage path, run ID, and progress cursor.

Registry writes use atomic replacement and revision compare-and-swap.
The registry is an index and presentation cache, not authority for library result identity or launcher state.
On reconnect, canonical run metadata or `WorkflowRun`/`RemoteWorkflowRun` state wins and the registry converges.

### 11.2 Startup recovery

At startup the platform:

1. loads non-terminal registry entries;
2. reconnects submitted handles without resubmitting;
3. refreshes launcher and backend state;
4. resumes progress after the saved global sequence;
5. replaces the displayed remote log snapshot when logs are requested;
6. publishes current execution snapshots to connected clients.

An attached run interrupted by platform process death becomes failed or lost according to evidence available from canonical storage.
The platform must not report success merely because no process remains.

### 11.3 Retention

Execution history retention is independent of cache-record retention.
Removing a presentation-history entry does not delete cached results, canonical run views, launcher control state, or output files.
Destructive cleanup requires a separate explicit storage-management design.

## 12. Remote Input and Result Semantics

### 12.1 Paths

For a remote target, every ordinary `Path` is a cluster path.
The platform does not probe the laptop filesystem, rewrite the path, or upload its contents.
A string remains a string even when it resembles a path.

Only an explicitly selected root workflow input may become `LocalUpload(Path(...))`.
The run confirmation must label each local upload and cluster path distinctly.
Relative typed paths are rejected.

The first remote increment may require all graph-embedded paths to already address cluster-visible shared storage.
Automatic upload of node-parameter constants is out of scope.

### 12.2 Results

Remote result download always requires an explicit local destination.
The platform delegates to `RemoteWorkflowRun.result(destination=...)`, which stages privately, verifies the immutable bundle, and atomically installs it.
Record-owned and return-owned assets become local.
Declared external cluster paths remain cluster paths and are labelled unavailable locally.

Transport loss does not fail the run.
Result download is enabled only for succeeded runs with an available verified return.

## 13. API and Event Surface

### 13.1 Profile management

- `GET /api/v1/execution/profiles` returns editable profile records or read-only administrator-provisioned records according to deployment authorization.
- `POST /api/v1/execution/profiles` creates a profile.
- `PATCH /api/v1/execution/profiles/{profile_id}` updates a profile using expected-revision compare-and-swap.
- `DELETE /api/v1/execution/profiles/{profile_id}` removes an unused profile.
- `POST /api/v1/execution/profiles/{profile_id}/test` validates the factory, bindings, capabilities, and secret references without launching work.
- `POST /api/v1/execution/profiles/{profile_id}/test-connection` performs the explicitly requested remote connection test when supported.

The ordinary Settings response contains `default_execution_target_id` and `new_workflow_execution`.
Profile lifecycle uses dedicated endpoints so profile revision conflicts and non-terminal-run references are not hidden inside an unrelated whole-settings patch.

### 13.2 Execution targets and preflight

- `GET /api/v1/execution/targets` returns the built-in Local target, available distributed targets, capabilities, and disabled reasons.
- `POST /api/v1/execution/preflight` validates one exact execution intent and returns the token, resolved plan summary, routing choices, and confirmation effects.
- `POST /api/v1/execution/run` accepts the existing graph/draft/command fields plus `preflight_token` and returns the complete accepted execution identity.

The run endpoint does not accept raw profile bodies.
It resolves the captured server-side profile revision from the preflight token.

### 13.3 Run inspection

- `GET /api/v1/executions` lists paginated execution summaries with optional workflow and state filters.
- `GET /api/v1/executions/{execution_id}` returns one full `ExecutionSnapshot`.
- `POST /api/v1/executions/{execution_id}/cancel` performs state-specific cancellation.
- `POST /api/v1/executions/{execution_id}/retry` creates a new preflight intent from the captured command and target.
- `POST /api/v1/executions/{execution_id}/download` prepares or performs the supported result download flow.

`POST /api/v1/execution/stop` remains a compatibility route for the single attached run.
It returns a conflict when more than one cancellable execution would make the target ambiguous.
New frontend code uses ID-specific cancellation.

`GET /api/v1/execution/status` remains a compatibility summary for the attached execution manager.
The Execution panel uses the plural run APIs.

### 13.4 Events

WebSocket execution events carry the execution ID, snapshot revision, workflow ID, draft revision, and changed run or job values.
The server may send a complete `execution_snapshot` on connection and compact `execution_update` messages afterward.
The client ignores updates whose revision is not newer than the retained snapshot.

Reconnect always fetches or receives a full snapshot before applying later updates.
Events are acceleration, not the only recovery mechanism.
OpenAPI remains the sole frontend type source.

## 14. Failure Behavior

Stable platform categories include:

- invalid workflow or draft conflict;
- unavailable execution target;
- profile revision conflict;
- invalid Parsl factory or executor labels;
- missing secret reference;
- ambiguous or incompatible executor route;
- resource capacity mismatch;
- unsupported storage or tool-origin mode;
- shared-path preflight failure;
- SSH connection, authentication, host-key, timeout, SFTP, and protocol failures;
- scheduler rejection;
- uncertain PSI/J submission;
- workflow failure, cancellation, loss, and unavailable results.

Every error retains the execution ID once one has been allocated.
Retryable observation failures keep the run in history and offer reconnect.
Authentication and host-key errors direct the user to normal OpenSSH configuration outside the application.
Uncertain submission retains the prepared run and forbids automatic resubmission.
Forced termination after a hard-cancel grace becomes `lost`, not `cancelled`.

## 15. Migration

### 15.1 Workflow documents

Existing `resources: {}` values remain valid and mean inherit.
Unknown resource keys that were previously accepted by `dict[str, Any]` become validation errors with a scoped node path.
Import and nested materialization preserve valid overrides recursively.
An existing empty `WorkflowNodeState.resources` object is accepted during migration and omitted on the next canonical write.
A non-empty workflow-boundary resource object is rejected with guidance to edit the internal processing nodes.

`WorkflowConfig.engine` expands to the library-supported `direct`, `wetlands`, and `parsl` values.
Existing `wetlands` values remain valid.
The built-in Local execution target may override the stored preference only for an explicitly selected run.

### 15.2 Settings

The settings envelope increments to version 2.
Legacy `execution_engine: "parsl"` continues to migrate to scheduling `parallel` and does not create a distributed profile.
Legacy `execution_engine: "sequential" | "parallel"` migrates to `new_workflow_execution`.
No Parsl profile is invented because configuration, bindings, capacity attestations, and secrets cannot be inferred safely.

### 15.3 Existing execution API

The current single execution status and WebSocket messages remain supported during frontend migration.
The new execution registry consumes existing library progress callbacks but retains per-job progress instead of one global pointer.
Once all clients use execution snapshots, the compatibility status can be deprecated in a later version.

## 16. Validation and Acceptance Criteria

### 16.1 Resources

- A CPU/GPU/memory override survives save, reopen, duplicate, group, clipboard, nested edit/apply, and workflow archive export/import.
- A Python-authored per-node resource override materializes identically once the public library authoring API supports that value.
- Two nodes using the same tool class retain independent overrides.
- Invalid units and values below tool requirements fail with scoped field errors.
- Resource changes do not invalidate cache selection and the UI explains how to recompute.
- GPU badges reflect effective rather than merely explicit requirements.

### 16.2 Target selection and preflight

- Local remains a one-click default.
- Selecting a distributed profile does not dirty the graph.
- A run uses the exact visible target revision and records it.
- Every processing node resolves to one compatible executor or preflight fails before allocation.
- Ambiguous routes require an explicit run-local choice.
- Parsl `retries` other than zero are rejected.
- No secret value appears in API responses, settings files, logs, events, or exported workflows.

### 16.3 Execution panel

- Direct, Wetlands, and Parsl runs render through the same snapshot component.
- Parallel jobs keep independent progress when their events interleave.
- Nested scoped paths render as an expandable job tree.
- Cached, failed, cancelled, skipped, and blocked jobs are distinguishable.
- Selecting a job can reveal the matching canvas node and filter Logger.
- Reconnect restores all job progress from a full snapshot.
- Closing or hiding the panel does not affect execution.

### 16.4 Submitted execution

- Restarting the platform reconnects to a submitted run without resubmission.
- Queued, running, finalizing, cancelled, failed, succeeded, lost, and uncertain states remain distinguishable.
- Connection loss does not change run state.
- Cancellation targets the exact persisted run and scheduler job.
- A late cancellation cannot displace finalizing or a terminal state.
- Result download verifies and atomically installs the selected destination.

### 16.5 Locking

- An attached run retains the current global graph-mutation lock.
- A durably submitted remote run permits ordinary graph edits but blocks destructive operations on its bound workflow and storage.
- Statuses never project onto a different workflow revision.
- Multiple submitted runs do not make ID-specific cancellation or status projection ambiguous.

## 17. Required Library and Platform Boundaries

The implementation should start only after these boundaries are confirmed:

1. BioImageFlow exposes a public, portable per-node resource-override round trip or equivalent public node API.
2. The platform can create attached runs with a caller-supplied `WorkflowExecutionContext` run ID.
3. The platform can build attached Parsl engines and submitted runs entirely from the library's public configuration values.
4. Submitted run reconnection, progress cursors, cancellation, logs, and results use `WorkflowRun` or `RemoteWorkflowRun`, not launcher storage internals.
5. If task drill-down is implemented, BioImageFlow first exposes a public task-diagnostics listing API; otherwise task detail remains summarized or unavailable.
6. The backend advertises optional Parsl and PSI/J capability without making ordinary local installation import Parsl.

## 18. Promotion into `platform_specs_v2.md`

After implementation:

- Section 2 should define typed resources, library-supported engine values, and scheduling ownership.
- Section 3 should define ProcessingTool-only overrides and workflow-boundary aggregation.
- Section 8 should add resource and execution-target preflight validation.
- Section 9 should be replaced by the run/job snapshot, target selection, Execution panel, projection, and cancellation contract.
- Section 12 should add execution registry, history, submitted reconnection, and revised locking.
- Section 14 should add target, preflight, plural execution, profile, and event APIs.
- Section 14.1 should identify distributed profiles as platform-owned integration settings.
- Section 15 should add target selection, View → Execution, ID-specific cancel, retry-on-target, and job-to-node navigation.

The v1 Resource Configuration and Execution Panel sections should be treated as superseded where they describe resources as guaranteed allocations, keep only one global progress pointer, or make Settings the effective workflow scheduling authority.
