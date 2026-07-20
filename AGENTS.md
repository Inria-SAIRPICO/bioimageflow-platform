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

After creating a worktree, recreate the ignored source links required by the backend before running `uv` commands.
Run this from the primary checkout, replacing `<worktree_name>`:

```bash
root="$(git rev-parse --show-toplevel)"
worktree="$root/.worktrees/<worktree_name>"

ln -s "$(realpath "$root/bioimageflow")" "$worktree/bioimageflow"
[ -e "$root/.worktrees/launcher" ] || ln -s "$(realpath "$root/../launcher")" "$root/.worktrees/launcher"
[ -e "$root/.worktrees/wetlands" ] || ln -s "$(realpath "$root/../wetlands")" "$root/.worktrees/wetlands"
```

`launcher` and `wetlands` are shared links used by every worktree, so do not use those names for worktrees or delete the links while worktrees exist.
Do not share `backend/.venv`, `frontend/node_modules`, `.bioimageflow`, build output, or runtime state between worktrees; create or install them per worktree when needed.
The ignored `specs.md` and `external/wetlands-src` links are optional and only need to be recreated when a task uses them.
