---
orphan: true
---

# Release Process

BioImageFlow Platform is distributed with [`wetlands-launcher`](https://github.com/arthursw/launcher).
The [`wetlands-launcher` packaging guide](https://github.com/arthursw/launcher/blob/main/docs/packaging.md) is the comprehensive reference for one-time signing setup and generic command behavior.
This page is the BioImageFlow-specific application and launcher release checklist.

The exact static version in `backend/pyproject.toml` is the release tag.
Do not add a `v` prefix: version `0.1.21` produces Git tag `0.1.21`, release assets containing `0.1.21`, and no `v0.1.21` alias.
The `RELEASE_TAG` variable below only makes filenames readable; launcher commands independently infer and verify the same value from `pyproject.toml`.

## Prepare and validate the release commit

Set `[project].version` in `backend/pyproject.toml`, set `RELEASE_TAG` to the same value, and regenerate the lockfile:

```bash
export RELEASE_TAG="X.Y.Z"

cd backend
uv lock
uv sync --group dev --frozen
cd ..
```

Commit every intended source, version, lockfile, configuration, and submodule change before releasing.
If the version bump is the only uncommitted release preparation, commit it with:

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "Prepare release ${RELEASE_TAG}"
```

Run the release-level validation on that exact commit:

```bash
scripts/test full
git status --short --untracked-files=no
```

Run the [complete manual platform test plan](manual-testing.md#complete-test-plan) on the same revision and retain its operating-system and blocker record with the release evidence.

The tracked worktree and index must be clean.
If validation requires a fix, commit it and rerun the full lane.
Push the validated release commit to `main` before creating its tag:

```bash
git push origin main
```

## Rebuild launchers only when the launcher changed

Every release publishes a new application archive.
Rebuild, sign, and upload platform launcher packages only when the launcher executable or a bundled input changed, including a `wetlands-launcher` upgrade, `application.yml`, icons, PyInstaller inputs, or signing behavior.
For an application-only release, skip this phase and the launcher-upload phase; existing launcher downloads remain valid and install the new application update.

When a rebuild is required, check out the same clean release commit on every target operating system and build from `backend/`:

```bash
export RELEASE_TAG="X.Y.Z"

cd backend
uv sync --group dev --frozen
uv run --with pyinstaller launcher build
uv run launcher build package
cd ..
```

PyInstaller must be installed in the same `uv run` environment as Launcher.
Icons are generated with `scripts/generate_desktop_icons`.
The generator keeps the Windows and Linux launcher artwork full-size and creates an inset `backend/packaging/launcher/app.icns` for the macOS launcher bundle.
Standard package names include the inferred release tag:

```text
backend/dist/BioImageFlow-launcher-X.Y.Z-macos-arm64.zip
backend/dist/BioImageFlow-launcher-X.Y.Z-windows-x64.zip
```

Do not upload unsigned macOS or Windows packages publicly.
Submit them to the Inria signing pipeline from the [`signing/`](https://github.com/Inria-SAIRPICO/bioimageflow-platform/tree/main/signing) submodule.
The helper waits for signing and, on macOS, notarization, then downloads the verified result to `signing/signed/`:

```bash
cd signing
export GITLAB_TOKEN="<token>"

uv run python scripts/submit_launcher.py \
  --file "../backend/dist/BioImageFlow-launcher-${RELEASE_TAG}-macos-arm64.zip" \
  --project-id "474" \
  --ref main \
  --platform macos
cd ..
```

On Windows PowerShell, set the token with `$env:GITLAB_TOKEN="<token>"`.
Use `--platform windows` with the `windows-x64` ZIP on Windows.
The helper infers the release tag from the standard package filename and rejects a platform or explicit-tag mismatch.
Linux launcher packages bypass the Inria operating-system signing pipeline.

## Create the tag and GitHub release

Authenticate once with `gh auth login`.
From `backend/`, create the raw version tag at the current commit, push it, and create the provider release:

```bash
cd backend
uv run launcher release create \
  --tag \
  --push \
  --notes-text "<release notes>"
```

For longer notes, replace `--notes-text` with `--notes ../RELEASE_NOTES.md`.
Create the provider release only once.

## Publish the signed application update

Still from `backend/`, create the application archive while the inferred release tag resolves to `HEAD`, then sign, verify, and upload it:

```bash
uv run launcher release archive
uv run launcher release sign
uv run launcher release verify
uv run launcher release upload
```

The upload publishes the versioned application ZIP together with `launcher-manifest.yml` and `launcher-manifest.yml.sig`.
These three assets are mandatory for every release.

## Upload rebuilt launcher packages

Skip this phase for an application-only release.
When launchers were rebuilt, gather the signed packages in one checkout when practical and upload each one from `backend/`:

```bash
uv run launcher build upload \
  --asset "../signing/signed/BioImageFlow-launcher-${RELEASE_TAG}-macos-arm64.zip"
```

The command infers the tag and platform from project metadata and the package filename, uploads the exact asset, and updates `packaging/launcher/distribution.yml` after success.
If platforms upload from separate machines, commit and push `distribution.yml` after each upload and pull that commit before the next upload so entries are not overwritten.

After every platform package is recorded, update the existing release notes once:

```bash
uv run launcher release update-notes \
  --notes-text "<release notes>"
```

Commit the final distribution metadata:

```bash
cd ..
git add backend/packaging/launcher/distribution.yml
git commit -m "Record ${RELEASE_TAG} launcher downloads"
git push origin main
```

## Verify the published release

Open the release and inspect its tag and assets:

```bash
gh release view "${RELEASE_TAG}" --web
```

Confirm that:

- the release tag is exactly `${RELEASE_TAG}`, without `v`;
- the application ZIP, `launcher-manifest.yml`, and `launcher-manifest.yml.sig` are present;
- every rebuilt launcher ZIP has the expected platform suffix and is linked from the release notes;
- the final `distribution.yml` change is committed and pushed;
- an existing installed launcher can discover, verify, install, and start the new application release;
- every newly rebuilt launcher starts successfully on a clean target system.
