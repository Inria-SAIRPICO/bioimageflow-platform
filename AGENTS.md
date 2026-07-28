# Repository instructions

## Testing

Use `scripts/test` as the authoritative test entry point and see `docs/testing.md` for lane definitions and focused-test examples.

During implementation:

- Run `scripts/test focus ...` after localized changes.
- Reproduce a failing test with its exact selector and browser before running a broader lane.
- After a fix, run the exact test once; use `--repeat-each=5` only for a suspected timing or race defect.
- Run `scripts/test quick` after a coherent coding increment when development will continue.
- Do not run `quick` immediately before a completion check that subsumes it.
- Before completing or committing, run the smallest applicable scoped check documented in `docs/testing.md`.
- Use `scripts/test check app` for cross-stack API, schema, dependency, or runtime changes.
- Use `scripts/test check all` only for broad architectural, browser, or test-infrastructure changes.
- Use `scripts/test check cross-browser-smoke` for localized cross-browser behavior and `scripts/test check browser-all` for broad browser or E2E-infrastructure changes.
- Run `scripts/test full` only after large plans, for releases, for package-loading or external-compatibility changes, when explicitly requested, or when complete local certification is otherwise required.
- Use `scripts/test certification` when validating published common-tools compatibility.

Do not run the full lane after every small edit.
Do not run a browser project or the full lane until the exact failing browser test passes.
Do not stack `quick`, scoped checks, and `full` when a later command subsumes the earlier results.
When a late phase fails, retain successful results for unchanged phases and rerun only the exact failure plus checks invalidated by subsequent edits.
Do not describe `quick` or a scoped `check` as the full suite.
Report each completion command, result, duration, and source revision, plus any skipped, deselected, flaky, or externally blocked phase.

## Worktrees

Do not share `backend/.venv`, `frontend/node_modules`, `.bioimageflow`, build output, or runtime state between worktrees; create or install them per worktree when needed.
The ignored `specs.md` and `external/wetlands-src` links are optional and only need to be recreated when a task uses them.
