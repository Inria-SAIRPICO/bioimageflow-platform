# Iterative Review Log

## Baseline

- Item: `platform_specs_distributed_execution.md`
- Goal: Review and improve the proposed platform specification for node resources, engine selection, execution monitoring, distributed Parsl profiles, and regular-engine compatibility.
- Started: 2026-07-30
- Max iterations: 5
- Convergence rule: stop when changes are no longer meaningful or remaining work is too broad or detailed for the requested specification review.
- Constraints:
  - Preserve `platform_specs_v2.md` as the normative description of implemented behavior.
  - Keep the proposal aligned with the current platform architecture and the public BioImageFlow library contracts.
  - Review agents must edit the proposal directly.
  - Do not modify implementation code.

## Iteration 1

- Reviewer: `/root/distributed_spec_review_1`
- Meaningful: yes
- Changes:
  - Clarified that graph commands use the visible target while retries retain the captured original target unless explicitly redirected, including confirmation when targets differ.
  - Replaced invented profile type names with the public `ParslConfigRef`, `OrchestratorLaunchConfig`, `PSIJLaunchConfig`, and `SSHSubmissionTransport` contracts.
  - Required persisted library values to encode and decode through their public `to_dict()` and `from_dict()` APIs.
  - Corrected Wetlands resource wording so GPU is described as a worker-assignment signal rather than validated multi-GPU allocation, and CPU/memory are not overstated.
  - Capability-gated remote profile testing and secret availability instead of assuming current public APIs can safely dry-run remote factories and cluster state.
  - Added a required public non-submitting cluster-validation boundary.
- Rationale:
  - Prevents retrying on an unexpected target.
  - Keeps the platform design tied to real public library APIs.
  - Avoids false guarantees about local resource enforcement.
  - Prevents private cluster-agent dependencies and unsupported preflight claims.
- Deferred:
  - The public non-submitting remote validation operation belongs in the BioImageFlow library/API specification.
  - Rich per-task diagnostics remain behind a separate public library boundary.

## Iteration 2

- Reviewer: `/root/distributed_spec_review_2`
- Meaningful: yes
- Changes:
  - Required unified run IDs to contain RFC 4122 UUID4 values so attached and launcher APIs accept the same identity.
  - Separated non-allocating Parsl planning from a runtime executor probe that may acquire workers but must finish before processing submission.
  - Required public BioImageFlow APIs for non-allocating requirement/routing planning and `ParslConfigRef` resolution instead of duplicating private library logic.
  - Bound remote-upload confirmation to immutable staged bytes and a preflight-token manifest digest.
  - Defined idempotent per-job progress reduction across interleaved events and reconnects.
  - Reworked library/platform sequencing into hard prerequisites, capability-gated parallel platform work, and remote-specific prerequisites.
  - Separated existing public BioImageFlow contracts from missing blocking boundaries.
- Rationale:
  - Prevents run-ID incompatibility between attached and submitted execution.
  - Avoids treating static configuration validation as proof that workers are accessible.
  - Keeps routing, startup, and secret resolution owned by the library.
  - Ensures execution uses the exact upload content the user confirmed.
  - Makes node progress deterministic.
  - Gives implementation a realistic dependency order without blocking engine-neutral platform work.
- Deferred:
  - A public capability-report API would simplify optional dependency detection but is not blocking.
  - Public task-diagnostics listing remains optional.
  - Exact names and schemas for proposed library planning, validation, and prepared-upload APIs belong in the BioImageFlow API specification.

## Iteration 3

- Reviewer: `/root/distributed_spec_review_3`
- Meaningful: yes
- Changes:
  - Identified that public progress events name a failed node but do not provide the structured exception detail and traceback required by the proposed job details.
  - Required a public, secret-redacted per-node failure diagnostic for attached callbacks and submitted-run inspection.
  - Prohibited reconstructing diagnostics from exception strings, logs, or private launcher artifacts.
  - Added this diagnostic boundary to library-first sequencing and capability-gated structured error presentation.
  - Added an acceptance criterion for public per-node diagnostics.
- Rationale:
  - Without this boundary, the Execution panel cannot reliably meet its structured per-job error contract, especially for multiple failures under parallel execution.
  - Makes the library-first requirements and parallel platform work more complete.
- Deferred:
  - Exact failure-diagnostic API names and schemas belong in the BioImageFlow API design.
  - A public progress-event codec or status enum could reduce adapter duplication but is non-blocking.

## Iteration 4

- Reviewer: `/root/distributed_spec_review_4`
- Meaningful: yes
- Changes:
  - Expanded the BioImageFlow resource prerequisite from serialization alone to a complete execution contract.
  - Required declaration-floor and `max_concurrent` validation, public effective-resource planning, and consumption of effective values by Wetlands and Parsl dispatch.
  - Clarified that portable serialization alone is insufficient while runtime requirement derivation still reads tool-level `ProcessingTool.resources`.
  - Gated execution and portable export on the complete resource contract.
- Rationale:
  - Prevents platform overrides from round-tripping successfully while having no runtime effect.
  - Makes the BioImageFlow-first resource dependency implementable and testable.
- Deferred:
  - Exact API names and schemas belong in the BioImageFlow API design.
  - Capability reporting and task-diagnostic listing remain optional.

## Iteration 5

- Reviewer: `/root/distributed_spec_review_5`
- Meaningful: no
- Changes:
  - None.
- Rationale:
  - The proposal clearly distinguishes BioImageFlow-first blockers from platform work that can proceed in parallel.
  - The hard library gaps are covered: effective per-node resources, trusted Parsl configuration validation, non-allocating planning, remote validation, structured node failures, and immutable upload preparation.
- Deferred:
  - Exact API names and response schemas belong in a later BioImageFlow API design.
  - A consolidated capability-report API and task drill-down are non-blocking refinements.

## Convergence

- Stopped after: 5 iterations
- Reason: The final reviewer found no further meaningful changes.
- Final item: `platform_specs_distributed_execution.md`
- Residual risk: The proposed public BioImageFlow boundaries still require a separate library API design and implementation before the Parsl target and execution-effective resource features can be enabled.
- Parallel path: The engine-neutral Local target, Nodes panel structure, Execution panel, run registry, snapshots, Direct/Wetlands monitoring, profile persistence, and capability-gated frontend work can proceed without waiting for those library additions.
