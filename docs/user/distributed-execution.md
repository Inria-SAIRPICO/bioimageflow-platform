# Distributed Execution

BioImageFlow can execute a workflow locally, through an attached Parsl engine, or through a durable submitted Parsl orchestrator.
The same Execution panel presents every target.

## Choose a target

The selector beside **Run Workflow** shows **Local** or a named distributed profile.
Local automatically uses Direct for orchestrator-only work and Wetlands when processing tools require worker environments.
Selecting a target affects only the next run and does not change the workflow.

Create distributed profiles under **Preferences → Execution**.
A profile identifies its trusted Parsl configuration factory, executor capacities and environments, routing, task policy, and launch behavior.
Remote profiles additionally contain an OpenSSH host or alias, transport staging root, cluster-agent executable, workflow-storage root, and PSI/J scheduler settings.

The platform never stores SSH credentials or private keys.
OpenSSH continues to own authentication, host-key verification, agent use, and `ProxyJump` configuration.

## Initialize the orchestrator job

A remote PSI/J profile can source one pre-launch script before starting its orchestrator.
Use it for recurring setup such as loading environment modules, initializing Spack, activating Python, exporting site variables, or changing the working directory.

Choose one source:

- **Inline script** stores editable UTF-8 source in the profile and binds its exact bytes during run preparation.
- **Local script file** reads a selected file during preparation and binds its exact bytes.
- **Cluster script file** snapshots an absolute cluster path when the run is submitted; add its expected SHA-256 digest when you need confirmation to bind the expected content.

An unpinned cluster script binds only its path before submission, so BioImageFlow warns before continuing and records the bytes observed on the cluster.
Every source becomes the same read-only run-owned artifact before PSI/J receives it.

Do not put passwords, tokens, or private keys in a pre-launch script.
The script is durable plaintext and anything it prints may enter scheduler logs.
It initializes the orchestrator service node, not Parsl workers, and it does not install the cluster agent or replace initial OpenSSH setup.

## Resolve workflow data for a cluster

Before remote confirmation, BioImageFlow discovers every unconnected path-shaped tool input, including paths inside nested workflows.
For each value, choose its meaning explicitly:

- **Upload from this computer** packages the selected file or directory into immutable content-addressed cluster storage.
- **Already on the cluster** keeps a normalized absolute POSIX path without reading a local file.

Files nodes use this general mechanism rather than a special upload path.
Scalar paths, ordered file lists, model files, configuration paths, and future path-shaped tool inputs follow the same rules.

The platform never guesses upload intent from whether a local path exists.
Upload choices belong to the confirmed invocation and are not saved as `LocalUpload` values in workflow JSON.
The editable workflow is not modified.

After resolving inputs, inspect the confirmation summary.
It lists scheduled and cached nodes, executor routes, upload counts and sizes, content digests, cluster paths, and pre-launch provenance.
Submission consumes the exact prepared object shown by this summary, so changing an original local file afterward cannot change the confirmed run.

## Monitor submitted runs

Open **View → Execution** to inspect current and retained runs.
The run list shows target, state, start time, and duration.
The hierarchical job table follows nested scoped paths and shows each job's state, progress, executor, resources, and duration.

Submitted runs can remain queued or running after the application disconnects.
Restarting the platform reconnects from the saved run ID and progress cursor rather than submitting again.
Connection loss means that current state is unknown; it does not fail the cluster run.

Use the run-specific actions to cancel, retry, open filtered logs, or download verified remote results.
Result downloads always require an explicit local destination and are installed only after complete integrity verification.

## Resource requirements

Select a ProcessingTool node and open **Resources** to compare its declared, overridden, and effective CPU, GPU, memory, GPU-memory, and concurrency requirements.
An override cannot reduce a tool's declared minimum or raise a finite declared concurrency cap.

Resource changes control placement and worker capacity but do not change cached result identity.
Use **Recompute Workflow…** when you need cached work to execute again with new placement.

DataFrameTool nodes execute in the orchestrator and have no editable worker-resource override.
Workflow nodes show a read-only aggregate of their internal processing nodes.
