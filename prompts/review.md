# Review

## Menus

## Docks

## Workflows

The workflow creation dialog must be validated when pressing enter (as if the user clicks on the "Create" button). Same thing for all dialogs of this sort in the entire platform (create tools, etc.).
Fix such modals.

The platform saves all workflows in the same workflows/ folder , as json files. All tools are saved in workflows/tools/ . Instead, I would like the platform to make one folder per workflow and a tools/ folder for each workflow. Platform workflows must follow the same structure as the workflows using the library (see the example workflows of the library). 

Same thing when exporting a workflow: it must be the same as when exporting with the library, that means it should export a .zip file with the tools/ folder and the json.

There must be a Workflows panel, just like the Tools panel. This panel will list existing workflows, like the tools panel lists tools. Workflows can be selected / opened by clicking on them, and a handle (one per workflow item) enable to drag on the canvas to create a sub-workflow. A workflow cannot be a child of itself (workflow A cannot contain workflow B if B contains A). The workflow panels should have the "New", "Save", "Duplicate", "Import", "Export", "Delete" buttons.


## Data table

Pagination should have 250 items per page by default, and up to 1000 items per page. It should also be possible to infinite scroll (no pagination).
## Tools panel

The custom tools should be removed / added when loading a workflow.

The power buttons in the tool list (and manage tools modal) are not updated when an environment starts during a workflow execution.

## Tool Creation

## Code Editor

### Manage tools dialog

## Canvas

The first tab is named "Canvas" instead of being named from the Workflow.

Default zoom is too big (or nodes too big).

No need to display the __dataframe_out label on the dataframe outputs, in the nodes.

The undo /redo is not working: deleting a node and undoing does not restore the previous state. This must be tested in the tests.

## Nodes panel

The node panel should use the Display Name, not the parameter name, for the parameter label.

When clicking the "Set value" button for a parameter (to set the parameter to a value, instead of null), the input field is empty. Instead, the default value should be set in the input field and the parameter.

## Top menu bar

## Logs

## Errors

## Others

There are two progress bar at the top. Why?

Stopping an execution does not interrupt it. It shows "Execution stop requested" but does not stop.