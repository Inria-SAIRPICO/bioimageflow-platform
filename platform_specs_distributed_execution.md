# Managed Distributed Execution Platform Specification

**Status:** Implemented normative delta to [`platform_specs_v2.md`](platform_specs_v2.md).

This document defines the platform integration with BioImageFlow's managed distributed-execution API.
It supersedes the platform's former attached-Parsl, submitted-local, SSH transport, cluster-agent, importable factory, staging-root, and manually coordinated directory contracts.
Where this document changes execution behavior described by v1 or v2, this document is authoritative.

## 1. Product Model

The platform exposes two execution target families:

- **Local**, which preserves Direct and Wetlands execution through the existing local admission path;
- **Managed remote**, which delegates deployment, validation, Parsl orchestration, scheduler submission, durable observation, retry, result transfer, and cleanup to `bioimageflow.cluster`.

The managed remote journey is:

```text
describe cluster → build workflow → submit → save run ID → reconnect → download result
```

The platform does not provide attached Parsl or submitted-local targets.
It does not construct `SSHSubmissionTransport`, `PSIJLaunchConfig`, `ParslConfigRef`, `PreLaunchScript`, transport staging paths, shared-runtime paths, or private cluster-agent requests.

An execution target is run intent and application preference, not portable workflow state.
Changing a target never dirties `GraphState`.
`GraphState.config.execution` remains the workflow's sequential or parallel scheduling policy.

## 2. Supported Library Boundary

The platform depends on the published BioImageFlow release that provides the managed cluster API through the `cluster` extra.
The backend uses public imports from `bioimageflow.cluster`, including `RemoteCluster`, `ClusterEnvironment`, `ParslConfiguration`, `SchedulerJob`, `SetupScript`, `LocalUpload`, and `RemoteWorkflowRun`.

The backend uses public methods and reports for capability discovery, connection checking, cluster description, direct submission, attachment by durable run ID, snapshots, sequence-based progress, structured diagnostics, cancellation, retry, verified result download, and cleanup.
The platform must not read remote launcher files, infer cluster-agent state, inspect Parsl internals, or parse logs to recover status or failure structure.
Managed runs do not expose a platform **Open logs** action because the public managed-run contract does not provide run logs.

Optional-runtime absence disables only managed remote targets.
Local Direct and Wetlands execution must continue to start and run when cluster support is unavailable.

## 3. Trusted Cluster Configuration

### 3.1 Configuration script

A desktop user selects one trusted local Python script.
The script must define a top-level value named `cluster` whose value is a configured `RemoteCluster`.

For example:

```python
from datetime import timedelta

from bioimageflow.cluster import (
    ClusterEnvironment,
    ParslConfiguration,
    RemoteCluster,
    SchedulerJob,
    SetupScript,
)

cluster = RemoteCluster(
    host="my-hpc",
    root="/cluster/project/alice/bioimageflow",
    environment=ClusterEnvironment.from_existing_python(
        "/shared/apps/bioimageflow/2026.08/bin/python"
    ),
    parsl=ParslConfiguration.from_file(
        "parsl.py",
        kwargs={"account": "BIOIMAGE"},
    ),
    orchestrator=SchedulerJob(
        scheduler="slurm",
        queue="compute",
        project="BIOIMAGE",
        walltime=timedelta(hours=4),
        cpu=4,
    ),
    setup=SetupScript.from_file("setup.sh"),
)
```

Reusable templates resolve companion paths from `Path(__file__).resolve().parent`, so `parsl.py` and `setup.sh` remain relative to their `cluster.py` even when the platform process has another working directory.
The platform does not change the process working directory or rewrite arbitrary relative paths in trusted code.
The backend imports a fresh module for each describe or submit operation so a stale `sys.modules` entry cannot silently define the target.
The selected script and every executable file it names are trusted code, not sandboxed configuration.

The platform does not split genuine site-owned facts into a second configuration authority.
SSH host, scheduler, project or account, queue, writable root, and optional Modules or Spack setup remain in the selected script and its reusable site template.

### 3.2 Persisted profile

A managed remote profile persists schema version, stable profile ID and revision, display name, enabled state, selected script path, the observed SHA-256 digest, and the non-secret cluster host and normalized root observed when the profile is saved.
Host and root are immutable observations used for target presentation and run attachment rather than separately editable site configuration.
The platform does not persist the imported live object, script bytes, resolved secret values, private keys, passwords, SSH options, scheduler credentials, or environment-variable contents.
The digest is an observation and confirmation aid, not a replacement for rereading and validating the selected trusted script at submit time.

The profile schema is `bioimageflow.platform.execution-profile.v2`.
Version-1 distributed profiles are permanently dropped during migration because their low-level modes and transport values cannot be converted safely.
They are not archived, copied, or exposed through a compatibility execution path.
Local settings, local execution history, and local results are preserved.

### 3.3 Deployment modes

Desktop mode allows trusted users to add, rename, enable, disable, remove, and describe managed remote profiles.
The profile editor contains only the name, script selector, enabled state, observed digest, **Describe cluster**, and example-template download.

Webapp mode treats managed profiles as read-only values provisioned out of band by the deployment owner.
This change does not introduce an administrator role or browser authorization model.
Ordinary webapp users cannot submit arbitrary server-side Python paths.

## 4. Describe and Capability-Driven State

**Describe cluster** loads the selected script, requires its `cluster` value to be a `RemoteCluster`, reads the public capability report, and invokes only public non-workflow checks supported by that object.
The response is a sanitized structured description of destination, scheduler request, environment kind, setup presence, configuration digest, connection observation, and capabilities.

The UI derives target availability and action enablement from the returned capability report and diagnostics.
It must not infer support from import success, scheduler strings, presence of optional packages, or exception text.

The platform distinguishes client implementation availability, cluster connection observation, configured scheduler and environment description, facts validated by the managed deployment, and facts that remain unverified until an allocation exists.
Structured diagnostics retain phase, category, sanitized message, allocation state, retry safety, next action, and related identities when supplied by BioImageFlow.
The strict public models expose a sanitized allowlist of diagnostic fields: phase, category, message, allocation state, retry safety, next action, and string identities.
Unknown or non-string diagnostic fields are not copied into platform persistence, APIs, or UI.

## 5. Workflow and Input Preparation

Remote execution starts from the exact accepted recursive graph or draft snapshot used by local execution.
The backend translates that snapshot to a storage-independent BioImageFlow workflow and supplies remote storage only through the selected `RemoteCluster`.

The platform resolves path-shaped invocation values explicitly before submission.
For each unresolved root input or invocation-only node input, the user chooses **Upload from this computer**, represented by `LocalUpload`, or **Already on the cluster**, represented by a normalized absolute cluster `Path`.
String values remain strings.
Connected fields, non-path fields, workflow boundaries, and relative unmarked cluster paths are rejected.
Invocation-only path choices never modify `GraphState` or saved workflow JSON.

The backend passes resolved root inputs, selected targets, or node-input overrides through the corresponding public `RemoteCluster.submit()` arguments.
Root inputs and explicit targets are mutually exclusive according to the public library contract.
The platform does not manufacture an unsupported selected-node plus root-input invocation.

## 6. Submission and Identity

After path resolution and explicit submit confirmation, the platform calls `cluster.submit()` directly.
It does not expose or retain a separate platform deploy, prepare, validate, or plan token and does not implement a second confirmation protocol around those library phases.

`cluster.submit()` owns source snapshotting, deployment publication or reuse, validation, planning, upload, scheduler submission, and durable remote allocation.
The platform must not reread or patch library-owned prepared state.

The platform saves the returned durable run ID immediately with the execution registry entry.
It also saves the non-secret attachment tuple: SSH host, normalized cluster root, durable run ID, and last consumed progress sequence.
The profile ID, profile revision, script path, observed script digest, sanitized target description, workflow identity, accepted draft revision, graph digest, command, and normalized presentation snapshot are retained for history and attribution.

The direct convenience call has an acknowledged crash window between remote durable allocation and receipt of the returned run handle.
If the platform process dies in that interval, it may not know the new run ID and must not guess, search private storage, or automatically resubmit.
The UI explains this residual risk before submission.

## 7. Execution Registry and Restart Recovery

The execution registry is separate from `GraphState`, workflow cache storage, and the selected configuration script.
It is an index and presentation cache; the public `RemoteWorkflowRun` observation is authoritative after attachment.

Registry writes use atomic replacement and revision compare-and-swap.
No secret or resolved credential is persisted.

At startup the platform:

1. loads retained non-terminal managed runs;
2. constructs an attach-only `RemoteCluster` from the saved host and root;
3. calls `cluster.attach(run_id)` without importing the original configuration script;
4. refreshes the public snapshot;
5. resumes progress after the saved sequence;
6. stores the converged presentation snapshot;
7. publishes the current execution snapshot to clients.

Attachment must work after the original workflow, cluster script, setup script, Parsl file, and project directory are unavailable.
A missing or incompatible retained gateway becomes a structured observation failure and never triggers implicit bootstrap or resubmission.

Version-1 distributed registry records and their owned retry or cleanup journals are permanently removed without an archive because they cannot be attached through the managed API.
Local registry records and local result data remain intact.

## 8. Monitoring and Diagnostics

Managed remote monitoring uses `RemoteWorkflowRun.snapshot()`, `refresh()`, `progress(after_sequence=...)`, and `diagnostics()`.
The platform preserves library run states and backend job details while mapping them into the engine-neutral `ExecutionSnapshot` used for local and remote runs.

Progress is globally sequenced and reduced idempotently by scoped node path.
The registry persists the last consumed sequence only after the corresponding snapshot update is durable.
Reconnect fetches a complete snapshot before applying later progress.

Each failed node displays the structured diagnostic supplied by BioImageFlow.
Run-level diagnostics that do not name a node remain visible in the execution details.
The UI never parses traceback or log text to decide retry safety, allocation state, result availability, or recovery actions.

Connection loss is observation state and does not itself change the authoritative run state to failed or lost.
The coordinator keeps observing the retained run automatically, and the UI can reload the latest retained observation or show the structured next action.

## 9. Cancellation, Retry, Results, and Cleanup

Cancellation targets one retained execution ID and delegates to `run.cancel()`.
It is idempotent for queued, running, cancelling, and terminal runs.
The platform never constructs a scheduler command or infers a native scheduler ID.

Retry is a two-stage public-library operation.
The platform calls `run.plan_retry()` and durably journals the exact returned plan, its digest, planned child run ID, parent execution ID, and confirmation state before presenting it.
Confirmation calls `run.start_retry(plan)` with that exact plan.

Restart recovery is attach-first:

1. attach to the persisted child run ID;
2. if attachment succeeds, converge the child registry entry and do not call `start_retry()` again;
3. if the public diagnostic definitively proves that the child is absent, call `start_retry()` again with the exact persisted plan;
4. if absence is uncertain, retain the journal and follow the diagnostic next action without replaying submission.

The platform never allocates a replacement child ID, rebuilds a retry plan from the current draft, changes the target, or treats transport failure as proof of absence.

Result download delegates to `run.download_result(destination)`.
The desktop chooses a local destination through its trusted file dialog.
The browser receives a platform-managed completed artifact and never supplies an arbitrary backend filesystem destination.
The library owns verification, atomic publication, destination-conflict behavior, and preservation of external cluster paths.
A transfer failure does not change a succeeded workflow state.

Cleanup uses `cluster.plan_cleanup()` followed by explicit confirmation and `cluster.apply_cleanup(plan)`.
The UI shows exact candidates, sizes, references, and destructive consequences from the public plan.
It does not accept an arbitrary recursive path and does not broaden a plan after confirmation.
Removing a platform history row is not cluster cleanup.

## 10. Execution Panel and Target Selection

The target selector beside Run shows **Local** plus enabled managed profiles whose capability report permits submission.
Unavailable profiles remain visible in Preferences with their structured disabled reason.

The Execution panel remains the common monitor for Direct, Wetlands, and managed remote runs.
It shows run identity, target, state, duration, job tree, per-node progress, structured diagnostics, backend allocation information, reload of the latest retained observation, and server-derived availability for cancellation, retry, result download, and cleanup.

Remote actions are enabled only from current public capability and run reports.
Managed runs omit **Open logs**.
Closing or hiding the panel never cancels or forgets a run.

Ordinary graph editing may continue after a durable managed run is registered because the run owns an immutable remote submission.
Canvas status projects only when workflow identity and accepted draft revision still match.

## 11. API Surface

The platform exposes strict OpenAPI models for profiles, targets, description, execution snapshots, diagnostics, retry journals, result downloads, and cleanup reports.
OpenAPI remains the sole source of frontend API types.

The managed profile routes are:

- `GET /api/v1/execution/profiles`;
- `POST /api/v1/execution/profiles`;
- `PATCH /api/v1/execution/profiles/{profile_id}` with expected revision;
- `DELETE /api/v1/execution/profiles/{profile_id}`;
- `POST /api/v1/execution/profiles/{profile_id}/describe`.

The target and execution routes are:

- `GET /api/v1/execution/targets`;
- `POST /api/v1/execution/preflight` for exact snapshot validation and remote path resolution only;
- `POST /api/v1/executions` to consume one exact short-lived managed admission intent and call `cluster.submit()`;
- `GET /api/v1/executions`;
- `GET /api/v1/executions/{execution_id}`;
- `POST /api/v1/executions/{execution_id}/cancel`;
- `POST /api/v1/executions/{execution_id}/retry/plan`;
- `POST /api/v1/executions/{execution_id}/retry`;
- `POST /api/v1/executions/{execution_id}/result`;
- `POST /api/v1/executions/{execution_id}/cleanup/plan`;
- `POST /api/v1/executions/{execution_id}/cleanup`.

The run endpoint resolves a captured server-side profile revision and never accepts a raw `RemoteCluster` object or script body.
The preflight endpoint may return explicit path-resolution requirements but does not create a remote deployment, plan, or scheduler allocation.

WebSocket execution events carry execution ID, snapshot revision, workflow ID, draft revision, and changed presentation values.
Events accelerate observation but do not replace full snapshot recovery.

## 12. Failure and Security Behavior

Every managed failure retains the structured library phase and category.
The platform preserves `allocation_state`, `retry_safety`, and `next_action` so the UI can distinguish safe retry, same-attempt recovery, unsafe replay, and non-applicable actions.

OpenSSH configuration owns keys, agents, jump hosts, ports, and host-key policy.
Profiles must not accept passwords, private-key bytes, arbitrary SSH option strings, or host-key bypass values.

The selected cluster script, Parsl source, setup script, workflow tools, package hooks, and remote site are trusted executable parties.
The platform shows source path and digest, warns before execution, and never claims to sandbox them.

Secret values are late-bound by trusted code or BioImageFlow's reference mechanisms.
They must not appear in profile files, registry files, API responses, events, exported workflows, diagnostics controlled by the platform, or example templates.

## 13. Migration and Compatibility

The settings and profile store schema increments for managed profiles.
On first load, obsolete version-1 distributed profiles are dropped without archive or conversion.
The default target falls back to Local if it referenced a removed profile.

Obsolete attached-Parsl and submitted-local code paths, low-level remote transport models, importable `module:callable` profile factories, staging-root settings, pre-launch transport values, and cluster-agent compatibility helpers are removed.
No dual wire path or deprecated alias is retained.

Existing local workflow documents, resource overrides, scheduling preferences, local execution history, cache records, and results keep their current semantics.
Portable workflow archives remain free of platform profile IDs and remote attachment state.

## 14. Acceptance Criteria

- Local Direct and Wetlands execution pass their existing validation and result tests without cluster support installed.
- A trusted script defining `cluster = RemoteCluster(...)` can be saved, described, selected, and submitted.
- A missing or wrong `cluster` value produces a structured profile error without creating a run.
- Profile persistence contains name, path, enabled state, revision, digest, and non-secret host/root observations but no secret values or serialized live objects.
- Webapp users can select provisioned profiles but cannot create or edit script paths.
- Explicit local-upload versus cluster-path decisions survive only in the immutable run invocation and never dirty the graph.
- A returned run ID is durably saved with host and root before the run is presented as reconnectable.
- Restart attaches using only host, root, and run ID and never imports the original cluster script.
- Snapshot and progress reduction are idempotent across repeated coordinator observations, UI reloads, and process restart.
- Structured capability and diagnostic fields determine action availability without log or exception-text parsing.
- Managed runs expose no log action.
- Cancellation is ID-specific and idempotent.
- Retry persists the exact plan and child ID, attaches first after restart, and replays only after definitive child absence.
- Result download delegates verification and atomic publication to `download_result()`.
- Cleanup requires a public plan and exact confirmation.
- Version-1 profiles are absent after migration while local history and results remain.
- The packaged Slurm example contains `cluster.py`, `parsl.py`, and optional `setup.sh` without secrets.
- Backend OpenAPI, generated frontend types, frontend behavior, persistence migration, restart recovery, and focused browser tests describe the same contract.
