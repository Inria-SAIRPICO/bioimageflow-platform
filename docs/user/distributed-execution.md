# Distributed Execution

> **Available in:** Desktop and browser when distributed profiles have been configured. Desktop users can edit profiles; browser users can be limited to administrator-provided profiles.

Use distributed execution when a workflow needs cluster resources or should continue as a submitted job after the application disconnects.
Use local execution for ordinary workstation runs.

## Choose a target

The selector beside **Run Workflow** shows **Local** and any configured distributed targets.
Selecting a target affects the next run; it does not change the workflow.

Create or edit a target under **Edit → Preferences... → Execution**.
A remote target needs a trusted Parsl configuration, tool routing and resource limits, an OpenSSH host or alias, remote storage locations, and scheduler settings supplied by your site.

```{note}
BioImageFlow does not store SSH passwords or private keys.
OpenSSH handles authentication, host verification, agents, and jump hosts.
```

## Add startup commands when required

A remote scheduler profile can run one startup script before its coordinator begins.
Use it for site requirements such as loading modules, activating Python, or exporting environment variables.

Choose an inline script, a local script file, or an absolute script path already on the cluster.
When the profile supports a checksum, add it to ensure that the expected cluster file is used.

```{warning}
Do not put passwords, tokens, or private keys in a startup script.
The script is stored as plain text, and anything it prints can enter scheduler logs.
Install and review cluster setup only with people you trust.
```

## Prepare input paths

Before a remote run, BioImageFlow lists path inputs from the root workflow and every nested workflow.
For each path, choose:

- **Upload from this computer** when the local file or folder must be copied for the run;
- **Already on the cluster** when the value is an absolute path available to workers there.

BioImageFlow does not guess based on whether a path exists locally.
Your choices apply to this run and do not replace the editable workflow's values.

Review the confirmation summary for target nodes, cached work, routes, uploads, sizes, and cluster paths before submitting.

## Monitor and retrieve a run

Open **View → Execution**.
The run list shows the target, state, start time, and duration, while the job table shows status and resources for each node.

A submitted run can remain queued or running after BioImageFlow disconnects.
Restarting the application reconnects to the recorded run instead of submitting it again.

Use run actions to cancel, retry, open filtered logs, or download completed remote results.
Choose a local destination for every download and wait for verification to finish.

## Request resources

Select a Processing Tool node and open **Resources**.
Compare its declared needs with any workflow override for CPU, GPU, memory, GPU memory, and concurrency.
An override cannot reduce a tool's minimum or exceed its declared concurrency limit.

Changing resources affects placement, not whether a previous result can be reused.
Choose **Recompute Workflow...** when you need unchanged steps to execute again with the new placement.

Maintainers can find implementation details in [distributed runtime wiring](../distributed_execution_runtime_wiring.md).
