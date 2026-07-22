# Repository instructions

## Testing

Use `scripts/test` as the authoritative test entry point and see `docs/testing.md` for lane definitions and focused-test examples.

During implementation:

- Run `scripts/test focus ...` after localized changes.
- Run `scripts/test quick` after a coherent coding increment.
- Run `scripts/test check` before completing or committing an ordinary task.
- Run `scripts/test full` after large plans, releases, or changes affecting cross-browser behavior, package loading, or external tool compatibility.
- Use `scripts/test certification` when validating published common-tools compatibility.

Do not run the full lane after every small edit.
Do not describe `quick` or `check` as the full suite.
Report any skipped, deselected, flaky, or externally blocked phase explicitly.

## Worktrees

Do not share `backend/.venv`, `frontend/node_modules`, `.bioimageflow`, build output, or runtime state between worktrees; create or install them per worktree when needed.
The ignored `specs.md` and `external/wetlands-src` links are optional and only need to be recreated when a task uses them.
