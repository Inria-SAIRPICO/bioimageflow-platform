# Execution For Agents

Execution uses the graph in the request body. It does not implicitly run the
current backend draft, the saved `workflow.json`, or a workflow id alone. To run
the latest draft, first read the draft and send that graph.

Disabled nodes (`enabled: false`) are skipped when the submitted graph is built
for execution.

The frontend blocks run actions while a user-visible draft conflict is
unresolved. Agents that run through the HTTP API should still re-read the draft
immediately before execution so they submit the intended graph.

## Run Latest Draft

```sh
STATE=.bioimageflow/agent-state.json
API=$(jq -r .api_base_url "$STATE")
WF=$(jq -r .active_workflow_id "$STATE")

curl -s "$API/workflow-drafts/$WF" > /tmp/bif-run-draft.json

jq -n   --argjson graph "$(jq .graph /tmp/bif-run-draft.json)"   --arg workflow "$WF"   '{graph: $graph, workflow_name: $workflow}'   | curl -s -X POST "$API/execution/run"       -H 'Content-Type: application/json'       --data-binary @-
```

The run graph is the body you sent. Later draft edits do not alter an already
started run.

## Run Selected Nodes

Send the full graph plus `nodes`. The backend builds execution from the
submitted full graph and runs the selected node ids according to current
execution rules. The request still needs the complete graph.

```json
{
  "graph": {},
  "workflow_name": "wf",
  "nodes": ["blur_1", "segment_1"]
}
```

## Locks

While execution is running, draft writes and graph-editing validation may return
`423 workflow_locked`. Poll status or stop execution before writing. After the
lock clears, re-read the draft before retrying any write.

## Status

```sh
curl -s "$API/execution/status" | jq .
```

Status includes state, progress, last result, and per-node statuses when
available.

## Stop

```sh
curl -s -X POST "$API/execution/stop"
```

Stop returns `stopping`. It is cooperative; keep polling status until execution
is no longer running.
