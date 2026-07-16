# Repository instructions

## Git

After completing a task that changes project files, commit only the changes made for that task unless told otherwise.
Do not stage or commit pre-existing unrelated changes.
Do not commit temporary agent-authored artifacts such as implementation plans, progress reports, or working notes unless explicitly requested.
Project documentation created as an intended deliverable should be committed normally.

## Markdown

Do not hard-wrap Markdown prose at 80 columns.
Use one line per sentence or semantic unit, preserving line breaks required by Markdown syntax.

## Project workflow

Use the validation commands documented in the README, choosing checks proportionate to the change.
If a manually created worktree is useful or explicitly requested, place it under `.worktrees/<worktree_name>`.
After its branch has been merged, remove it by moving it to Trash with `mv`, run `git worktree prune`, and delete the merged branch.
Do not use `git worktree remove`, because it is too slow for this repository.

## Worktrees

Keep `.worktrees/` in the primary checkout's `.git/info/exclude`.
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
