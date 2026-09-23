# Getting Started

This walkthrough installs the desktop application and runs the bundled **Fish Analysis** demo.
See [Choose Input Data](choose-input-data.md) before adding your own files.

## Install the desktop application

1. Open the [BioImageFlow releases page](https://github.com/Inria-SAIRPICO/bioimageflow-platform/releases).
2. Find the launcher download for your operating system in the latest release notes.
3. Download and extract the launcher package, following the platform-specific instructions in those notes.
4. Move the launcher to a stable location, such as **Applications** on macOS, and open it while connected to the internet.

Do not download a source-code archive as a substitute for the launcher.

```{note}
The first launch can take several minutes while the launcher verifies the release, downloads the application, and prepares an isolated environment.
Keep the launcher open while progress is displayed.
Later launches normally reuse that environment and start faster.
```

## Open a bundled demo

BioImageFlow normally installs **Fish Analysis** and **Parameters Space Exploration** in the **Demo** folder when it creates a workspace.

1. In the **Workflows** panel, expand **Demo**.
2. Select **Fish Analysis** and read its description.
3. Click **Open workflow**.

If the **Demo** folder is missing, choose **Edit → Preferences...**, open **Storage**, and click **Install demos**.

![The Fish Analysis demo open on the workflow canvas.](images/quick-start-demo.png)

## Resolve its tools

The demo refers to separately installed tool packages.
If a dependency dialog appears, click **Install all missing packages** to install the requested versions.
You can also click **Manage tools** in the **Tools** panel to inspect packages and environments individually.

```{warning}
Tool packages contain executable code.
Install packages only from sources you trust.
The first run can take longer while BioImageFlow prepares tool environments and downloads the demo's public input data.
```

## Run and inspect the demo

1. Click **Run Workflow** in the upper-right corner.
2. Follow node status on the canvas and messages in the **Logger** panel.
3. Select a completed node.
4. Open **View → Node Data** to inspect its table, image previews, and output paths.
5. Double-click **FOLS2 Marker Spot Analysis** or **CSF1R Marker Spot Analysis**, then select an internal node to inspect that branch's intermediate results.
6. Select the saved workflow in **Workflows** and click **Open latest outputs** to reveal its latest successful files.

The latest-output folder can combine the latest successful result from different runs.
Use **Workflow → Export** when you need independent copies or one complete workflow-and-results bundle.

## Make an editable copy

Keep the bundled demo unchanged while you experiment.

1. Select **Fish Analysis** in **Workflows**.
2. Click **Duplicate workflow**, or choose **Workflow → Save As** while the demo is open.
3. Enter a new workflow name and display name.
4. Change a parameter or node, then choose **Workflow → Save**.

Continue with [Interface Tour](interface.md) or [Build a Workflow](build-workflows.md).

The launcher checks for application updates when it starts.
Launcher version information and workspace storage are covered in [Settings, Storage, and Integrations](preferences.md).
