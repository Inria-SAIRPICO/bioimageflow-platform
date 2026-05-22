# Workflow Panel, Workflow-Local Tools, and Library Export Plan

## Agreements

- The workflow root directory is not a Python package. Do not create a root
  `__init__.py` for saved workflows.
- The platform is a thin GUI adapter around the BioImageFlow library. Workflow
  archive import/export and recursive sub-workflow validation should be done by
  the library, not reimplemented in platform code.
- Workflow list rows stay compact: display name and last modified time only.
  Description and filesystem/API name are shown in the selected workflow detail
  area.

## Target Behavior

- Saved workflows use:

  ```text
  workflows/
    my_workflow/
      workflow.json
      tools/
  ```

- Only workflow directories containing `workflow.json` are platform workflows.
- Custom tools are workflow-local under the selected workflow's `tools/`
  directory.
- Export returns the library archive, expected as `{name}.bioimageflow.zip`.
  Import accepts the library archive and stores it in the platform layout.
- A persistent Workflows panel lists workflows, supports New, Save, Duplicate,
  Import, Export, Delete, selects workflows on click, opens workflows via
  double-click, Enter, or the Open action, and exposes a per-row drag handle for
  sub-workflow creation.
- Dropping a workflow on the canvas creates a SubWorkflowNode using the library
  build/validation path. Recursive containment errors come from library
  validation and are surfaced in the UI.

## TDD Implementation Plan

1. Backend storage tests first
   - Add failing tests for `workflows/{name}/workflow.json` creation, list, get,
     save, duplicate, and delete.
   - Assert no root `__init__.py` is created in workflow directories.
   - Assert `WorkflowInfo.path` points to `workflow.json`.

2. Backend workflow-local tools tests first
   - Add failing tests that creating a tool while workflow `A` is active writes
     to `workflows/A/tools/`, not global `workflows/tools/`.
   - Add tests for source lookup, rename/delete, usage scanning, and registry
     refresh against the selected workflow tool directory.
   - Keep package-installed tools global.

3. BioImageFlow library archive tests first
   - If the local BioImageFlow library does not yet support `.bioimageflow.zip`
     archives, add that support in the library before platform code uses it.
   - Add failing library tests that export writes an archive containing the
     workflow JSON and workflow-local `tools/` directory, and import/load reads
     that archive.
   - Add failing library validation tests for direct and indirect recursive
     workflow containment.

4. Backend library import/export adapter tests first
   - Introduce a small adapter boundary, for example `WorkflowArchiveService`,
     whose production implementation delegates to BioImageFlow library
     import/export.
   - Unit-test the platform router/store with a fake archive service so tests
     assert delegation and response headers without reimplementing the library.
   - Integration-test one real library archive round trip.

5. Frontend Workflows panel tests first
   - Add component tests for compact rows, selected workflow details, toolbar
     button states, and emitted actions.
   - Add store tests for export filename fallback changing to
     `.bioimageflow.zip` and import file picker/upload expectations.
   - Add canvas tests for workflow drag payload acceptance and SubWorkflowNode
     creation path.

6. Implement backend
   - Change `WorkflowStoreService` path helpers to use the directory layout.
   - Add workflow-root resolution for the current workflow and wire tools
     endpoints to that path.
   - Add archive adapter and update `/workflows/{name}/export` and
     `/workflows/import`.

7. Implement frontend
   - Add `WorkflowsPanel.vue` and register it in the dock layout next to/near
     Tools.
   - Reuse existing workflow store actions where possible.
   - Add drag payload `application/bioimageflow-workflow` with workflow name
     only from the row handle.
   - Extend `CanvasView` drop handling to load/build the dropped workflow as a
     sub-workflow node and surface library validation errors.

8. Verification
   - Run targeted backend tests with `uv run pytest`.
   - Run targeted frontend tests with the repo's existing test command.
   - Run lint/type checks where practical.
   - Review generated OpenAPI/frontend types if backend response types change.

## Risks / Decisions To Confirm During Implementation

- The checked-in library currently documents and implements JSON export with
  embedded `custom_tool_modules`. If zip archive support is not present in the
  local library checkout, add it to the BioImageFlow library first and keep the
  platform dependent on a narrow library adapter.
- GUI metadata may need a library-supported extension location. If the library
  cannot preserve GUI metadata yet, platform export should fail clearly or
  store only supported metadata rather than inventing an undocumented archive
  sidecar.
- Current custom-tool endpoints do not carry the active workflow name. The
  implementation must either derive it from server workflow context or add a
  small explicit workflow-scoped API.
