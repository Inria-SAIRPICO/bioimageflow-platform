# BioImageFlow Platform

BioImageFlow: Streamline Your Bioimage Analysis & Make it FAIR

BioImageFlow is a workflow management system that simplifies the creation, execution, and duplication of data science experiments, with specialized features for image analysis.
Its primary goal is to make bioimage analysis truly FAIR: Findable, Accessible, Interoperable, and Reproducible.

With BioImageFlow, you can:

- **Build Workflows Your Way:** Choose a visual, node-based interface or trusted Python code to create your analysis pipelines.
- **Forget Dependency Headaches:** Access tools written in Python, Java, C++, or R that run in isolated environments. BioImageFlow handles their setup and installation so they work without conflicts.
- **Integrate & Extend Easily:** Bring your own tools into BioImageFlow or create new ones quickly from the provided Python template.
- **Visualize Complex Data:** Explore multidimensional images such as 3D+t data through the built-in Napari integration.
- **Manage Data Effectively:** Use Pandas data tables throughout your workflows and connect directly to OMERO repositories.
- **Boost Performance:** Speed up analyses with automatic parallel processing of independent workflow steps and configured distributed targets.
- **Work with Coding Agents:** Connect Codex, OpenCode, or Claude Code through MCP so an agent can inspect, edit, validate, and run the active workflow while you review its changes in BioImageFlow.
- **Get Started Instantly:** Install BioImageFlow with the launcher and receive verified application updates without managing the environment yourself.

BioImageFlow lets you focus on scientific discovery by making powerful bioimage analysis accessible, manageable, and reproducible.

![A BioImageFlow workflow open on the canvas, with tools, workflow tabs, node data, and execution controls visible.](user/images/interface-overview.png)

```{toctree}
:maxdepth: 1
:caption: Getting Started
:hidden:

user/index
user/interface
```

```{toctree}
:maxdepth: 1
:caption: Workflows
:hidden:

user/build-workflows
user/manage-workflows
user/coding-agent
```

```{toctree}
:maxdepth: 1
:caption: Tools
:hidden:

user/data-and-tools
user/create-custom-tools
```

```{toctree}
:maxdepth: 1
:caption: Data
:hidden:

user/choose-input-data
```

```{toctree}
:maxdepth: 1
:caption: Run and Results
:hidden:

user/run-and-results
```

```{toctree}
:maxdepth: 1
:caption: Settings and Help
:hidden:

user/preferences
user/troubleshooting
user/keyboard-shortcuts
```

```{toctree}
:maxdepth: 1
:caption: Advanced
:hidden:

user/nested-workflows
user/distributed-execution
user/advanced-authoring
```

```{toctree}
:maxdepth: 2
:caption: Developers
:hidden:

developer/index
```
