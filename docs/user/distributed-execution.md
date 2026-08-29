# Managed Cluster Execution

Use a managed remote target when a workflow needs cluster resources or must continue after the application disconnects.
Use **Local** for ordinary workstation runs through Direct or Wetlands.

The remote journey is:

```text
describe cluster → build workflow → submit → save run ID → reconnect → download result
```

## Ask your site for the real cluster values

Before configuring a target, obtain these values from your cluster documentation or support team:

- an OpenSSH host or alias;
- the scheduler, such as Slurm;
- the account or project to charge;
- the queue or partition;
- a dedicated writable root visible at the same absolute path on login, orchestrator, and worker nodes;
- any Modules or Spack commands needed to expose Python, CUDA, compilers, or native libraries.

BioImageFlow can install or reuse software below your writable root.
It cannot install a scheduler, drivers, privileged libraries, or change site policy.

## Download and edit the Slurm example

In **Edit → Preferences... → Execution**, choose **Download Slurm example**, or {download}`download the same archive here <../_static/downloads/bioimageflow-managed-slurm-cluster.zip>`.
The archive contains:

- `cluster.py`, the target selected by the platform;
- `parsl.py`, the ordinary Parsl worker configuration;
- `setup.sh`, an optional Modules or Spack setup example.

Replace every placeholder with values supplied by your site.
Adjust both the orchestrator request in `cluster.py` and the separate worker requests in `parsl.py`.
Remove `setup=...` if the cluster exposes everything without `setup.sh`.

```{warning}
The selected Python and shell files are trusted executable code.
Review them before use and select files only from people you trust.
Do not put passwords, tokens, private keys, or other literal secrets in them.
```

OpenSSH handles authentication, host-key verification, agents, ports, and jump hosts through your normal SSH configuration.
The platform never stores SSH passwords or private keys.

## Add and describe the target

Add a managed remote profile in **Preferences → Execution**.
Give it a name and select `cluster.py`.
The selected script must define a top-level `cluster` value created with `RemoteCluster`.

Click **Describe cluster** before selecting it for a run.
The platform shows the observed script digest, destination, scheduler request, environment kind, setup presence, connection result, capabilities, and structured diagnostics.
Fix any disabled reason using its reported next action, then describe the target again.
Opening the target selector does not execute `cluster.py` or connect to the site; the trusted script runs only when you save or update its profile, explicitly describe it, or submit with it.

The profile stores its name, script path, enabled state, revision, observed digest, and the non-secret cluster host and root observed when it is saved.
Host and root are not separate editable settings; change them in `cluster.py` and save the profile again.
Secrets and imported Python objects are not saved.

In webapp deployments, profiles are provisioned outside the browser and appear read-only.

## Choose input locations

Select the target beside **Run Workflow**.
Changing the target affects the next run and does not change the workflow.

Before submission, BioImageFlow lists unresolved path inputs from the root workflow and nested nodes.
For each one choose:

- **Upload from this computer** to snapshot and transfer a local file or folder;
- **Already on the cluster** for a normalized absolute path already visible to cluster jobs.

BioImageFlow does not guess from local path existence.
Strings remain strings, and these invocation choices never replace saved workflow values.

Review the target, workflow snapshot, path choices, and the acknowledgement-window warning shown beside every selected managed target, then submit.
The platform delegates deployment, validation, planning, upload, scheduler launch, and Parsl startup to BioImageFlow's managed API.

## Monitor and reconnect

Open **View → Execution**.
The panel shows the durable run ID, target, state, backend allocation, scoped node progress, and structured diagnostics.
Managed remote runs do not provide an **Open logs** action.

The platform saves the host, cluster root, run ID, and progress cursor as soon as `submit()` returns.
A submitted run can remain queued or running after the application closes.
After restart, the platform attaches with those saved values and does not resubmit or require the original `cluster.py`, `parsl.py`, `setup.sh`, workflow project, or input paths.

Managed run history, recovery journals, and downloaded result bundles belong to the workspace in which the run was created.
Switching workspaces shows the selected workspace's history and sends new runs there, while a run already being monitored continues updating its original workspace safely.

There is a short residual risk between durable remote allocation and the return of the run ID.
If the application crashes in that interval, it may not know the run ID and will not guess or automatically resubmit.

## Cancel, retry, and download

**Cancel** targets the exact retained run and is safe to repeat.

**Retry** first creates and saves one exact retry plan and planned child ID.
After a restart, the platform tries to attach to that child before doing anything else.
It repeats the same retry start only when BioImageFlow definitively reports that the child does not exist.
An uncertain connection never causes a second retry allocation.

When a run succeeds, choose **Download Results** to download the verified ZIP through your browser.
BioImageFlow verifies the portable result bundle and publishes it atomically.
Run-owned assets become local, while paths declared as external cluster paths remain external references.
A download problem does not change the successful run state.
After the first verified download, BioImageFlow reuses the retained local archive on later downloads and after an application restart.
That local result remains available even if you later apply confirmed cluster cleanup, as long as you keep the original workspace files.

## Clean up retained cluster state

Deployments, uploads, run records, transfers, and results are not automatically deleted.
Use **Plan Cleanup** to inspect exact candidates, sizes, references, and consequences, then apply that exact plan after confirmation.

Removing a row from platform history is not remote cleanup.
Deleting a retained terminal run record can remove future attachment, diagnostics, retry, and run-owned result availability.

Maintainers can find the integration contract in [managed distributed runtime wiring](../distributed_execution_runtime_wiring.md).
