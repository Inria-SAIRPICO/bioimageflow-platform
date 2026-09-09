---
orphan: true
---

# Platform test campaign issues

Use the [campaign escalation protocol](platform-test-plan.md).
Statuses: `open`, `sol-investigating`, `astra-review`, `safe-to-fix`, `needs-owner`, `externally-blocked`, `resolved`, or `not-a-defect`.
Record the actual specialist model/reasoning and disposition; an unassigned queue entry is not completed Astra review.
Owner decisions and product intent take precedence over an agent's proposed fix.

## ISSUE-001 — Source-update preview and replaced workflow identity

Status: open, queued for Astra/high in the next session.
Observed evidence: source inspection only at platform `fcb4408`; no reproduction or product/test edit performed.
The earlier immediate-owner pause is superseded by the revised protocol; bounded Astra investigation is the next authorized action, not an assumed repair.
Dependent work: source-update/Python rebuild acceptance and any fix relying on preview ownership; unrelated audits can continue only if demonstrably independent.

The v2 specification's Source Updates section requires preview to capture destination identity and Apply to recheck captured values; its identity section defines durable generations for same-ID recreation.
See `platform_specs_v2.md` around lines 237–240 and 282–284, `backend/src/bioimageflow_server/services/workflow_sources.py` (`_PreparedSourceOperation`, `preview_source_update`, `_apply_source`), and `workflow_store.py::workflow_mutations`.
The prepared operation appears to store paths and content hashes without destination generation.
Apply's mutation lock captures generation at Apply entry, not at Preview time.
Hypothesis: deleting and recreating the parent at the same path with the original graph may let an old preview modify the replacement because its content hash still matches.
This hypothesis is not a confirmed failure and must not be turned into a passing test by asserting the observed outcome.

### Bounded Astra task

Read the source-update and identity specifications and the existing `backend/tests/test_services/test_workflow_sources.py::test_source_refresh_is_previewed_and_applied_explicitly` fixture.
Use a disposable store, no tools or workflow execution:

1. Save a parent embedding a saved child; change the child's label and obtain a source-update preview.
2. Preserve the parent's graph, hash, and generation.
3. Delete/recreate that parent through supported lifecycle APIs at the same path; restore its exact original graph.
4. Apply the old token and record the response, generations, hashes, and before/after graph.

Determine whether other lifecycle invalidation already prevents the hypothesis.
If it reproduces, assess whether existing specifications unambiguously require rejection and whether a bounded generation check under the existing locking protocol is sufficient.
Consider related source identity, workspace identity, and Python rebuild only as necessary to establish the repair boundary; these are not already established defects.
Return `safe-to-fix`, `not-a-defect`, or `needs-owner` with evidence, exact selectors, and implementation/validation boundaries.
Recommended intent for assessment: reject an old preview for a deleted/recreated destination with a conflict and no mutation, even when content matches.
No repair has been attempted and no new semantics are authorized; an Astra `safe-to-fix` disposition permits a bounded repair preserving the established contract without another owner approval.

Disposition / reproduction / artifacts / specialist / fix commit: pending.
Resume condition: Astra establishes the safe contract and repair, disproves the concern, or the owner answers the remaining question after `needs-owner`.

## ISSUE-002 — Logging specification versus contextual-log tests

Status: open audit discrepancy; no product change or validation performed.
At `fcb4408`, the v1 WebSocket log-event table around line 910 describes logs as intentionally unscoped without execution/canvas context.
The audit reports deliberate contextual execution-log behavior in the logging bridge and `frontend/tests/e2e/error-handling.spec.ts`, while environment logs remain global.
Read the actual bridge, payload models, tests, and later authoritative specification sections before deciding which statement is stale.
Do not change the specification merely to bless existing implementation or rewrite test expectations merely to match old prose.
Sol may reconcile demonstrably stale wording if authoritative intent is established; otherwise send one focused packet to Astra/high.
Disposition / decisive references / affected files / validation / commit: pending.

## New issue record template

Use a stable ISSUE-NNN heading with status, task/dependency scope, source revision and packages, observed versus expected behavior, authoritative references, exact reproduction/selector/browser, evidence paths, attempted changes, and unresolved question.
Add specialist model/reasoning, disposition and rationale, owner decision if needed, implementation/test/specification files, completion evidence, commit, and resume condition.
For resolved issues, retain the decision and commit references without carrying full logs into the master checkpoint.
