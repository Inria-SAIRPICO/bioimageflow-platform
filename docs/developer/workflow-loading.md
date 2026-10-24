# Workflow loading performance

Published BioImageFlow 0.9.6 and Core 0.5.1 reuse admitted installation facts so workflow opening, compilation and planning do not repeatedly rediscover the Python environment or prove unchanged installed source.
The normal platform manifest and lock select these releases from the package registry.
These workflow measurements do not establish total application startup time: the HTTP fixture used an offline package index, an isolated Wetlands root and disabled source watchers, and navigation began after backend readiness.
Real startup also includes catalog discovery, network refresh, existing managed-environment metadata, debugger overhead and browser initialization.

Startup catalog reads resolve all tool environment paths from one fresh inventory per request, with filesystem enrichment off the event loop.
Workflow folder discovery stops at workflow.json boundaries instead of walking saved results and tool sources, and reuses discovered paths only within the current operation.
Neither change introduces a persistent response cache or changes scientific cache identity.

A follow-up on 24 October 2026 compared the prior platform implementation at `5f3c335` with these catalog changes using the actual local workspace: five workflows, 48 tools and ten managed environment targets.
Both implementations ran in the same normal Python 3.13 process with SDK 0.9.5/Core 0.5.1, alternating order over five unprofiled samples per operation; separate profiles counted filesystem work.
All tree, tool metadata and format-status responses were identical, and no scientific callback ran.

| Startup catalog operation | Prior median | Updated median |
| --- | ---: | ---: |
| Workflow tree | 381 ms | 13 ms |
| Tool metadata with environment paths | 686 ms | 21 ms |
| Format status | 149 ms | 12 ms |

The tree profile reduced directory enumerations from 1,699 to three; the format-status profile reduced them from 1,133 to three.
Tool metadata used one managed-environment inventory rather than 33, freshly for each request.
These are backend catalog measurements without the VS Code debugger, not a promise that complete application startup takes the same time.

## Admission lifetime

An installed generation owns the selected canonical store, package/version, accepted installation manifest, captured source and actual loaded classes.
Complete installation and dependency admission happens once for that generation.
The application dependency inventory stays fixed until process restart; changing controller dependencies requires restart.
Ordinary workflow opens reuse those facts while still deriving current parameters, declarations, upstream selections and plan statuses.

Installed files are read-only selections during that lifetime.
Editing them does not authorize automatic reload or a new scientific identity for resident classes.
Controlled retirement refuses while admitted operations own the generation.
Uninstall reserves the selected namespaces through physical removal so concurrent workflow reads cannot re-admit code awaiting removal.
A failed refresh never restores retired classes as executable authority.

Editable workflow tools retain fresh capture of their represented source set at each compilation/execution admission, with bounded reuse of unchanged source analysis.
Installed inherited owners use held installation facts; editable inherited owners remain part of that fresh capture.
Arbitrary imported helpers outside the represented source boundary retain explicit declared-version or invalidation responsibility.
There is no continuous detection promise for monkeypatching or independent changes to installed libraries.

`Workflow.from_dict(..., tool_store_path=...)` selects one store for the whole recursive graph.
Store paths and generation counters govern selection and lifetime; they are not scientific cache-key inputs.
The existing wire/cache contracts remain unchanged, and this optimization requires no workflow migration or result deletion.

## Measure backend loading

Use the checked-in `scripts/benchmark_workflow_loading.py` with prepared, separate baseline and candidate interpreters.
Give each interpreter its actual platform checkout rather than mixing a candidate library with baseline service code:

```bash
backend/.venv/bin/python scripts/benchmark_workflow_loading.py \
  --workflow-dir '/path/to/workflow' \
  --tool-store '/path/to/readonly/tool-store' \
  --baseline-python '/path/to/baseline/backend/.venv/bin/python' \
  --baseline-platform-root '/path/to/baseline' \
  --candidate-python '/path/to/candidate/backend/.venv/bin/python' \
  --candidate-platform-root '/path/to/candidate' \
  --case missing-runtime \
  --output '/private/tmp/workflow-loading.json'
```

The default comparison alternates variant order across five fresh interpreters and records ten subsequent warm operations per variant.
Phase timings are uninstrumented; separate processes collect first-operation and warm call counts.
The receipt includes runtime versions and metadata hashes, platform revisions and service hashes, medians, ranges and actual plan statuses.
Cold measurements mean a fresh Python process, without flushing the operating system's filesystem cache.

The input workflow, optional draft and contained tool sources are copied into a disposable workspace.
Original results, settings and managed environments are excluded.
The selected tool store is read-only input and bytecode writes are disabled.
The harness never runs scientific callbacks, and it rejects a workflow with definition errors rather than reporting an incomplete graph as fast.

Use `--case empty-cache` for a fixture with usable runtime or only DataFrame tools.
For `--case populated-cache`, provide explicit owned, bounded result fixtures through `--baseline-results` and `--candidate-results`; the harness requires a real cache hit.
Do not point those options at private user result trees.
A tiny generated numeric fixture is sufficient to distinguish live record-integrity cost from executable-admission overhead.

Backend measurements cover saved loading, projected draft loading, compilation, validation/planning, discovery and process start through the first projection.
They exclude HTTP transport, browser rendering and actual Run setup.
Measure those separately against the same frontend source, observing the actual projected response and visible nodes, and use a disposable numeric workflow for real Run rather than executing an analysis workflow merely to time startup.

## Measured candidate performance

On 23 October 2026, Python 3.13.2 and Wetlands 2.6.1 were held constant while the baseline SDK 0.9.4/Core 0.5.0 interpreter was compared with SDK 0.9.5/Core 0.5.1 wheels built from library revision `57dba0f`.
The interpreters had the same 93-distribution inventory apart from those two versions.
Each used its own platform service implementation and isolated runtime state.
The Fish copy contained 12 tools and two embedded workflows and used the missing-runtime case; the one-node numeric DataFrame fixture used values `[1, 2, 3]` and required no worker.
Every case used five fresh processes, ten warm operations and separate profile processes.

Values below are medians with observed ranges.

| Operation | Baseline | Candidate |
| --- | ---: | ---: |
| Fish saved plus projected draft, warm | 13.710 s (12.835–14.524) | 65.6 ms (58.6–78.7) |
| Fish compilation, warm | 4.899 s (4.388–5.270) | 20.8 ms (17.7–24.1) |
| Fish validation and planning, warm | 5.831 s (5.417–6.693) | 23.0 ms (20.1–29.3) |
| Fish process start through first projection | 16.784 s (16.332–17.707) | 3.267 s (3.020–3.740) |
| Numeric DataFrame, empty cache, warm | 2.737 s (2.538–3.189) | 8.1 ms (6.8–9.2) |
| Numeric DataFrame, populated cache, warm | 3.002 s (2.852–3.343) | 24.8 ms (20.9–41.6) |

Candidate medians were below the baseline's minimum in every measured phase, including cold first projection.
Warm Fish projected-draft profiling reduced global package-map scans from 22 to zero, dependency validations from 28 to zero, installation admissions from eight to zero and source-callable attestations from 278 to zero.
Initial discovery still performed the four installation admissions; the optimization did not omit that boundary.
Opening and planning invoked no scientific callback.

The numeric fixture produced exactly `[1, 2, 3]` and retained identical scientific result and immutable record identities across baseline and candidate.
Its populated case reported a genuine cache hit while retaining live record validation.
The larger populated-cache time reflects that remaining work; these tiny-fixture timings do not establish a bound for large result tables or network storage.

The premeasurement engineering targets were a warm saved-plus-projected median below one second, compilation and planning each below 0.5 seconds, and process start through first projection below five seconds.
All three fixture cases met those targets.
Raw receipts remain temporary benchmark artifacts rather than portable workflow data.

## Canvas and Run measurements

A separate real HTTP and headless Chromium comparison used one constant pristine frontend and the two actual backend implementations.
Vite and browser startup were excluded, and the server was ready before navigation.
Five fresh Generate processes and ten warm operations per variant exercised real projected responses, visible nodes and actual Runs.

| Measurement | Baseline median | Candidate median |
| --- | ---: | ---: |
| Generate fresh canvas, five samples | 5.097 s | 0.533 s |
| Generate warm canvas, ten samples | 5.600 s | 0.408 s |
| Uncached Run request through first started progress, five samples | 7.977 s | 48.2 ms |
| Cached Run request through cached progress, ten samples | 7.579 s | 132.1 ms |

Candidate warm canvas observations ranged from 0.384 to 0.468 seconds; baseline observations ranged from 5.078 to 12.290 seconds.
All 30 Runs produced exactly `[1, 2, 3]`, with cache hits retaining the exact immutable result identity, and all 32 canvas loads were valid with no browser errors.
One additional Fish navigation control per variant took 15.097 seconds versus 0.619 seconds; that is a single observation, and Fish was never executed.

Run setup is measured through public SDK started/cached progress, without instrumenting callback entry.
Processing environment provisioning and model startup are outside these timings.
Server startup itself remained a separate cost: median time through health readiness was 4.790 seconds versus 4.377 seconds.
These results support keeping the synchronous opening flow; an additional response cache or asynchronous canvas redesign is unnecessary for these fixtures.

## Candidate verification

Scientific identity and installation integrity remain separate.
Warm lookup avoids repeated global ownership scans, installed RECORD admission and installed callable attestation, while cache planning still reads current records and detects corruption.
The deterministic gates cover source/parameter changes, exact package/store binding, retirement, editable source capture, numeric results, real worker dispatch and cache reuse.

The normal published-worker certifications still require the selected Core version to be available from the package index.
Prepublication validation of an exact candidate wheel in a real worker is separate evidence and does not turn an unavailable published dependency into a successful normal installation.
Publication, exact-commit CI and normal platform dependency adoption remain explicit release gates.
