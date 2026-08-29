---
orphan: true
---

# Managed Distributed Execution Runtime Wiring

This reference describes how the platform consumes BioImageFlow's public managed cluster API.
The normative platform behavior is in `platform_specs_distributed_execution.md` at the repository root.

## Ownership boundary

The platform owns profile selection, accepted workflow identity, explicit path choices, durable presentation state, API transport, and UI actions.
BioImageFlow owns remote deployment, gateway and storage layout, validation, Parsl configuration, PSI/J scheduler submission, run authority, progress, diagnostics, retry, verified result transfer, and cleanup.

The integration imports managed values from `bioimageflow.cluster`.
It does not construct the superseded transport, cluster-agent, staging-path, `ParslConfigRef`, `PSIJLaunchConfig`, or `PreLaunchScript` values.

## Profile loading

A managed profile stores ID, revision, name, enabled state, trusted script path, observed SHA-256 digest, and non-secret host/root observations captured from that configuration.
The script is freshly imported for profile validation, explicit describe, and submit operations and must expose a top-level `cluster` value that is a `RemoteCluster`.

The profile store never serializes that live object or its executable source bytes.
It never resolves or persists passwords, private keys, tokens, or environment-variable values.

Desktop profile mutation is a trusted local capability.
Webapp profiles are read-only values provisioned out of band, and ordinary browser users cannot choose a server Python path.

## Description and target availability

Target discovery reads persisted enabled state and the public managed capability report without loading trusted scripts or attempting connections.
The describe service explicitly loads the trusted script, reads the public capability report, and runs only public non-workflow cluster checks.
It returns sanitized target details, connection observation, capabilities, and structured diagnostics.

The execution-target service combines the built-in Local target with enabled managed profiles.
Target availability and disabled reasons come from saved enabled state and the public capability report rather than script execution, package heuristics, or exception text.
Explicit describe and run operations use their structured diagnostics for action details.
Missing cluster support never prevents Local Direct or Wetlands execution.

## Admission and submission

Remote admission uses the same exact accepted graph or draft snapshot and recursive translator as Local execution.
Preflight validates the graph and returns any unresolved remote path inputs.
It does not create a library deployment, prepared invocation, plan, run, or scheduler job.

The user resolves each remote path as a `LocalUpload` or normalized absolute cluster `Path`.
The run service reloads the captured profile revision, verifies the current script and digest, creates a storage-independent library workflow, and calls `cluster.submit()` directly with selected `targets` and resolved `node_input_overrides` when present.
The preflight request has no `root_inputs` field because the platform does not expose a separate root-input invocation contract.

The platform issues a short-lived, one-use in-memory admission token only after graph and path resolution.
That token binds the exact profile revision, workflow revision, selected nodes, and decoded invocation values; it contains no remotely prepared deployment, validation report, execution plan, or scheduler allocation.
Consuming the token calls `cluster.submit()` directly without another plan confirmation.
The library's convenience operation owns all remote mutation and returns a `RemoteWorkflowRun` only after the run identity is durable.

The service immediately records the returned run ID and the non-secret host/root attachment tuple.
The direct call necessarily leaves a short process-crash window after remote durable allocation but before the platform receives the returned identity.
The service never compensates by searching private state or resubmitting.

## Registry and attachment

Each workspace owns registry snapshots and retry or cleanup journals below `.bioimageflow/executions`, plus deterministic managed result destinations below `.bioimageflow/execution_exports`.
The execution registry stores graph and draft attribution, sanitized profile attribution, host, root, run ID, progress sequence, retry journal, local result-bundle path, and normalized `ExecutionSnapshot` state.
It is an atomic presentation index, not remote run authority.

Listing, startup recovery, and new saves resolve the current workspace dynamically.
Once an execution ID is loaded or saved, the registry and result resolver bind that ID to its original workspace so active polling, retry or cleanup journaling, and result publication continue there after a workspace switch.

Startup recovery creates an attach-only `RemoteCluster(host=..., root=...)`, calls `attach(run_id)`, refreshes the public snapshot, consumes `progress(after_sequence=...)`, and persists the converged projection.
It never imports the original profile script or bootstraps a missing gateway.

## Snapshot reduction and diagnostics

The coordinator poller uses `snapshot()`, `refresh()`, and `progress(after_sequence=...)` and persists each converged projection, including structured node diagnostics from the public progress stream.
Structured operational diagnostics come from public cluster reports and exceptions.
The snapshot adapter retains only the known public observation fields needed for state and presentation, including state, revision, attempt phase, gateway identities, and scheduler job ID.
Unknown mapping keys and sensitive values are dropped before registry persistence, and observation failures without a public diagnostic receive a fixed generic message rather than arbitrary exception text.
The Execution panel's reload action performs `GET /executions/{execution_id}` to read that latest retained observation; it does not start a second remote refresh operation.
Progress is reduced idempotently by global sequence and scoped node path.
The stored cursor advances only with a durable registry snapshot.

Library diagnostics remain structured through the API and UI, including phase, category, sanitized message, allocation state, retry safety, next action, and related identities.
String identities remain available to exact-run recovery and error presentation.
HTTP mapping uses 503 for `ssh-*`, `sftp-*`, `protocol-incompatible`, and `gateway-unavailable`; 404 for `run-not-found` or a missing retry or cleanup plan; 422 for invalid retry input; 409 for the enumerated submission, scheduler, retry, cleanup, integrity, and result conflicts; and 500 for unexpected unmapped operation failures.
The default retryable categories are `ssh-connection`, `ssh-timeout`, `ssh-command-failed`, and `sftp-*`.
The adapter does not parse logs or tracebacks to decide actions.
Managed remote runs deliberately have no log-fetch adapter.

## Control operations

Cancellation delegates to the attached run's idempotent `cancel()`.

Retry preview delegates to `plan_retry()` and durably stores the exact plan, digest, and child run ID before confirmation.
Confirmation delegates to `start_retry(plan)`.
On recovery the coordinator attaches to the child first, repeats the exact start only after definitive child absence, and otherwise preserves uncertain state without replay.

Result retrieval delegates to `download_result(destination)`.
The backend always uses a server-owned managed destination, then the frontend downloads the completed ZIP through the browser rather than supplying an arbitrary server path.
After the first successful transfer, the registry records the result-bundle path and archive digest.
Restart and later downloads verify and reuse that retained archive before remote attachment, so confirmed remote cleanup does not discard the local result.

Run-scoped cleanup reconstructs an attach-only cluster from the execution's persisted host and root, delegates to `plan_cleanup(run_ids=(run_id,))`, and then calls `apply_cleanup(plan)` after confirmation.
The apply route accepts only the exact stored public plan and never a profile script, current profile revision, or recursive path.

## OpenAPI and events

Backend models strictly type sanitized cluster descriptions, connection reports, remote path plans, cleanup plans and reports, public diagnostics, and allowlisted observations.
They reject or discard unknown values at the appropriate trust boundary instead of passing raw library mappings to persistence or clients.
OpenAPI is the sole source of frontend types.

Execution WebSocket events accelerate delivery of versioned presentation snapshots.
Reconnect always establishes a full snapshot before later revisions are applied, so events are not the recovery authority.
