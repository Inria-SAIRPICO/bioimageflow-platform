# Repository instructions

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
