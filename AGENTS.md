# Repository instructions

## Testing

Use `scripts/test` as the authoritative test entry point and see `docs/testing.md` for lane definitions and focused-test examples.

During implementation:

- Run `scripts/test focus ...` after localized changes.
- Run `scripts/test quick` after a coherent coding increment when development will continue.
- Do not run `quick` immediately before a completion check that subsumes it.
- Before completing or committing, run the smallest applicable scoped check documented in `docs/testing.md`.
- Use `scripts/test check app` for cross-stack API, schema, dependency, or runtime changes.
- Use `scripts/test check all` only for broad architectural, browser, or test-infrastructure changes.
- Run `scripts/test full` after large plans, releases, or changes affecting cross-browser behavior, package loading, or external tool compatibility.
- Use `scripts/test certification` when validating published common-tools compatibility.

Do not run the full lane after every small edit.
Do not describe `quick` or a scoped `check` as the full suite.
Report any skipped, deselected, flaky, or externally blocked phase explicitly.

## Worktrees

Do not share `backend/.venv`, `frontend/node_modules`, `.bioimageflow`, build output, or runtime state between worktrees; create or install them per worktree when needed.
The ignored `specs.md` and `external/wetlands-src` links are optional and only need to be recreated when a task uses them.
