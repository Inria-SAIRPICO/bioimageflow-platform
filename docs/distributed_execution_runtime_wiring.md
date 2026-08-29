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
The script is freshly imported for describe and submit operations and must expose a top-level `cluster` value that is a `RemoteCluster`.

The profile store never serializes that live object or its executable source bytes.
It never resolves or persists passwords, private keys, tokens, or environment-variable values.

Desktop profile mutation is a trusted local capability.
Webapp profiles are read-only values provisioned out of band, and ordinary browser users cannot choose a server Python path.

## Description and target availability

The describe service loads the trusted script, reads the public capability report, and runs only public non-workflow cluster checks.
It returns sanitized target details, connection observation, capabilities, and structured diagnostics.

The execution-target service combines the built-in Local target with enabled managed profiles.
Target availability and disabled reasons come from capability and diagnostic reports rather than package or exception-text heuristics.
Missing cluster support never prevents Local Direct or Wetlands execution.

## Admission and submission

Remote admission uses the same exact accepted graph or draft snapshot and recursive translator as Local execution.
Preflight validates the graph and returns any unresolved remote path inputs.
It does not create a library deployment, prepared invocation, plan, run, or scheduler job.

The user resolves each remote path as a `LocalUpload` or normalized absolute cluster `Path`.
The run service reloads the captured profile revision, verifies the current script and digest, creates a storage-independent library workflow, and calls `cluster.submit()` directly with the supported `inputs`, `targets`, or `node_input_overrides` shape.

The platform issues a short-lived, one-use in-memory admission token only after graph and path resolution.
That token binds the exact profile revision, workflow revision, selected nodes, and decoded invocation values; it contains no remotely prepared deployment, validation report, execution plan, or scheduler allocation.
Consuming the token calls `cluster.submit()` directly without another plan confirmation.
The library's convenience operation owns all remote mutation and returns a `RemoteWorkflowRun` only after the run identity is durable.

The service immediately records the returned run ID and the non-secret host/root attachment tuple.
The direct call necessarily leaves a short process-crash window after remote durable allocation but before the platform receives the returned identity.
The service never compensates by searching private state or resubmitting.

## Registry and attachment

The execution registry stores graph and draft attribution, sanitized profile attribution, host, root, run ID, progress sequence, retry journal, and normalized `ExecutionSnapshot` state.
It is an atomic presentation index, not remote run authority.

Startup recovery creates an attach-only `RemoteCluster(host=..., root=...)`, calls `attach(run_id)`, refreshes the public snapshot, consumes `progress(after_sequence=...)`, and persists the converged projection.
It never imports the original profile script or bootstraps a missing gateway.

## Snapshot reduction and diagnostics

The coordinator poller uses `snapshot()`, `refresh()`, `progress(after_sequence=...)`, and `diagnostics()` and persists each converged projection.
The Execution panel's reload action performs `GET /executions/{execution_id}` to read that latest retained observation; it does not start a second remote refresh operation.
Progress is reduced idempotently by global sequence and scoped node path.
The stored cursor advances only with a durable registry snapshot.

Library diagnostics remain structured through the API and UI, including phase, category, sanitized message, allocation state, retry safety, next action, and related identities.
The adapter does not parse logs or tracebacks to decide actions.
Managed remote runs deliberately have no log-fetch adapter.

## Control operations

Cancellation delegates to the attached run's idempotent `cancel()`.

Retry preview delegates to `plan_retry()` and durably stores the exact plan, digest, and child run ID before confirmation.
Confirmation delegates to `start_retry(plan)`.
On recovery the coordinator attaches to the child first, repeats the exact start only after definitive child absence, and otherwise preserves uncertain state without replay.

Result retrieval delegates to `download_result(destination)`.
Desktop mode supplies a user-selected local destination, while browser delivery uses a server-owned completed artifact rather than an arbitrary client-supplied server path.

Run-scoped cleanup reconstructs an attach-only cluster from the execution's persisted host and root, delegates to `plan_cleanup(run_ids=(run_id,))`, and then calls `apply_cleanup(plan)` after confirmation.
The apply route accepts only the exact stored public plan and never a profile script, current profile revision, or recursive path.

## OpenAPI and events

Backend models represent public reports without dropping fields needed for action gating.
OpenAPI is the sole source of frontend types.

Execution WebSocket events accelerate delivery of versioned presentation snapshots.
Reconnect always establishes a full snapshot before later revisions are applied, so events are not the recovery authority.
