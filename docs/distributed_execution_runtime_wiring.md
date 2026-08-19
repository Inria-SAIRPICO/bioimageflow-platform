---
orphan: true
---

# Distributed execution runtime wiring

The retained runtime is deliberately independent of settings/profile persistence and the existing compatibility `ExecutionManager`.

## Application lifecycle

At application construction, create `ExecutionRegistry` with the workspace root, not a workflow storage root.

Create one `PreparedSubmissionTokenManager` and one `ExecutionCoordinator` per application process.

In the FastAPI lifespan startup, call `ExecutionCoordinator.start()` after profile and workspace stores are available.

Startup reconnects submitted runs from their public reconnect tuple and never resubmits them.

In lifespan shutdown, call `ExecutionCoordinator.close()` and then `PreparedSubmissionTokenManager.close()` so polling tasks stop and abandoned immutable preparations are removed.

Include both `bioimageflow_server.routers.executions.router` and `preflight_router` under `/api/v1` and override their four dependencies with the application-owned coordinator, preflight service, prepared-run registrar, and download-destination resolver.

The route shapes are `POST /api/v1/execution/preflight`, `POST /api/v1/executions`, `GET /api/v1/executions`, `GET /api/v1/executions/{execution_id}`, and ID-specific `cancel`, `retry`, `logs`, and `result` routes.

Keep `/api/v1/execution/run`, `/status`, `/stop`, and `/clear` wired to the existing `ExecutionManager` during migration.

## Profile and workflow boundaries

The profile layer implements `ExecutionProfileResolver.resolve_target()` and returns the immutable revision selected for that target.

Its `planning_arguments()` contains only public `plan_distributed_execution()` keyword values.

Its `submission_arguments()` contains only public `prepare_remote_submission()` keyword values, including the selected `PreLaunchScript` produced with `from_text()`, `from_local_file()`, or `from_cluster_file()`.

The returned remote profile exposes its public `SSHSubmissionTransport` as `transport`.

The workflow resolver compiles or loads the exact accepted draft revision and returns the materialized BioImageFlow workflow.

The upload resolver is the authority boundary between a user choice and a backend-readable path.

It authorizes a path selected through the native picker and rejects arbitrary paths outside that boundary.

Do not persist the decoded `LocalUpload` values or apply node overrides to the editable workflow.

## Run registration and reconnection

The prepared-run registrar receives the `RemoteWorkflowRun` returned by consuming the exact live prepared object.

It creates an `ExecutionSnapshot` with the canonical public run ID and reconnect data `{storage_path, run_id}`, wraps the handle in `SubmittedRunAdapter`, and calls `ExecutionCoordinator.register()`.

Submitted-local registration follows the same path with `WorkflowRun`.

Direct, Wetlands, and attached Parsl registration uses `AttachedRunAdapter` with a compute closure, the run-specific `WorkflowExecutionContext.request_cancel`, and the platform result exporter.

The attached compute closure installs the supplied progress callback on the materialized run snapshot and owns the `ParslEngine.from_config_ref()` context when the selected target is attached Parsl.

The coordinator reconnector must use `open_public_submitted_run()` for submitted modes and must never try to reconnect an attached run after process restart.

Profile revisions referenced by non-terminal remote runs must remain resolvable until the runs reach terminal state.

## Publication and downloads

Adapt `ConnectionManager` to `ExecutionSnapshotPublisher` by broadcasting `ExecutionUpdate(type="execution_snapshot", ...)` for initial registration and `ExecutionUpdate(type="execution_update", ...)` for later revisions.

Snapshots are full replacements keyed by their monotonic revision, so clients discard duplicate or older messages.

The download-destination resolver must confine outputs to an application-owned export directory.

It must not accept an arbitrary client-supplied filesystem path.

## Current boundary

Remote preflight returns a single-use token only after `prepare_remote_submission()` succeeds.

Consuming that token submits the exact prepared object and closes it on success or failure.

Attached and submitted-local preflight returns the public distributed plan without a token; their existing admission path should register an adapter only after the accepted draft/profile authority checks complete.
