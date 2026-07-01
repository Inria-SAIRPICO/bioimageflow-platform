# Agent Troubleshooting

## API Offline

Read `.bioimageflow/agent-state.json`, set `API` from `api_base_url`, then call
`curl -sS "$API/health"`. The URL already includes the dynamic backend port and
`/api/v1`; do not guess or hardcode ports such as `8008`.

If the health check fails with a permission, sandbox, or connection error, the
agent may be unable to reach localhost or 127.0.0.1 from inside its sandbox.
Request permission to run the same `curl` command outside the sandbox. If that
works, continue using the same `API` value.

Do not edit `workflow.json` or `.bioimageflow/platform-source/` as a fallback.

## Backend Logs

The `python -m bioimageflow_server` entrypoint and desktop mode use the packaged `bioimageflow_server/logging.yaml` config by default.
That config makes `bioimageflow_server`, `bioimageflow`, and `wetlands` INFO logs visible, including embedded editor startup diagnostics.
If raw Uvicorn is launched directly, pass `--log-config src/bioimageflow_server/logging.yaml` or a deployment-specific logging config.

## Stale State

`agent-state.json` contains runtime pointers, not workflow data.
`current_draft_revision` is informational. MCP tools and operation REST should
use the latest draft revision before writing. For raw full-DAG fallback, always
re-read `GET /workflow-drafts/{workflow_id}` before writing.

## Frontend Did Not Update

After a successful draft write, the frontend is notified. If the user has no
local canvas edits, the canvas should update automatically. If it does not,
check that the frontend is connected and that the write returned a new
`draft_revision`.

If the user has local canvas edits, the frontend intentionally keeps the local
canvas visible and asks the user to apply agent changes, keep their canvas, or
save the agent version as a copy.

## 409 Draft Conflict

Your `expected_revision` is stale. Re-read the draft, reapply only your intended
change to the new graph, then retry with the new `draft_revision`.

## Operation Validation Error

`POST /workflow-draft-operations/{workflow_id}` returns
`operation_validation_error` with `operation_index`, `code`, and `detail`.
Fix the failing semantic operation instead of editing `workflow.json`.

## 423 Workflow Locked

Execution is running. Use `GET /execution/status`, then wait or call
`POST /execution/stop`. Retry the write only after the lock clears.

## Validation Errors

Validate with `PUT /graph` before running. Check `tool_name`, required
parameters, connection shape, and whether deleted node ids still appear in
`graph.edges`.

## Missing Tool Names

Call `GET /tools` and use exact names from the response. Do not invent tool
names from display labels or filenames.

## Stale Temp Graph Files

Files such as `/tmp/bif-draft.json` and `/tmp/bif-graph.json` are snapshots.
They become stale after frontend edits, agent writes, or conflict retries.
Refresh them from `GET /workflow-drafts/{workflow_id}` before writing.
