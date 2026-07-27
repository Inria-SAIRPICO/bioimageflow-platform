# Install and Launch BioImageFlow

BioImageFlow is distributed through a small launcher.
The launcher downloads a verified BioImageFlow release, prepares its Python environment, starts the platform, and checks for application updates on later launches.

## Install the launcher

1. Open the [BioImageFlow releases page](https://github.com/Inria-SAIRPICO/bioimageflow-platform/releases).
2. Find the launcher download for your operating system in the release notes.
3. Download and extract the launcher package, following any platform-specific instructions included with that release.
4. Move the launcher to a stable location appropriate for your system, such as the Applications folder on macOS, before opening it.

Launcher packages and supported systems can change independently from the application version.
Use the links in the current release notes instead of choosing a source-code archive or an application archive manually.

## First launch

Open the launcher while connected to the internet.
On its first run, the launcher:

1. checks the latest published BioImageFlow release;
2. verifies the signed release information;
3. downloads the platform sources;
4. creates an isolated application environment and installs its dependencies;
5. starts BioImageFlow in a desktop window.

This preparation can take several minutes.
Keep the launcher open while it displays download or environment progress.
Later launches reuse the prepared environment and are normally faster.
The launcher starts BioImageFlow in production desktop mode, with frontend hot reload and browser developer tools disabled.

BioImageFlow also uses the internet when it installs tool packages or tool environments and when an example workflow downloads its public input data.

## Updates

Continue opening BioImageFlow through the same launcher.
When a newer application release is available, the launcher verifies and installs it before starting the application.
You do not need to download a new launcher unless the release notes specifically publish a launcher update.

## Your local data

The application keeps workflows, datasets, settings, tool packages, environments, caches, and outputs outside the downloaded application sources.
Updating the application does not intentionally replace this user-owned data.

The default desktop workspace is `~/BioImageFlow/workspace/`, and the default output-data folder is `~/bioimageflow_data/`.
You can inspect or change these locations under **Edit → Preferences… → Storage**.

If the launcher cannot start the application, see [Launcher or startup problems](troubleshooting.md#launcher-or-startup-problems).
