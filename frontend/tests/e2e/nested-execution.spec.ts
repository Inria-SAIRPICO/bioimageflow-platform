import { expect, test } from '@playwright/test'
import type { Locator, Page } from '@playwright/test'
import type { GraphState } from '../../src/api/types'
import type { WorkflowDraftResponse } from '../../src/api/workflowDrafts'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

function workflowId(prefix: string): string {
  return `${prefix}_${test.info().project.name}_${Date.now()}`.replace(/[^a-zA-Z0-9_-]/g, '_')
}

function nestedExecutionGraph(name: string, displayName: string, fail = false): GraphState {
  const child: GraphState = {
    schema_version: 1,
    name: 'stable_child',
    display_name: 'Stable child',
    nodes: [{
      type: 'tool',
      id: 'nested_increment',
      name: 'Nested increment',
      tool_name: fail ? 'ControlledDirectNumbers' : 'IncrementNumbers',
      position: [260, 160],
      parameters: fail ? { fail: true } : { number: 1 },
    }],
    edges: [],
    interface: {
      inputs: [{
        id: 'stable-table-input',
        name: 'Source rows',
        kind: 'dataframe',
        schema: { type: 'DataFrame' },
        targets: [{ node: 'nested_increment', port: { kind: 'positional', index: 0 } }],
      }],
      outputs: [{
        id: 'stable-increment-output',
        name: 'number_plus_one',
        schema: { type: 'int' },
        source: { node: 'nested_increment', column: 'number_plus_one' },
      }],
    },
    config: { engine: 'direct', execution: 'sequential' },
  }

  return {
    schema_version: 1,
    name,
    display_name: displayName,
    nodes: [{
      type: 'tool',
      id: 'root_seed',
      name: 'Root seed',
      tool_name: 'SeedNumbers',
      position: [80, 180],
      parameters: {},
    }, {
      type: 'workflow',
      id: 'nested_step',
      name: 'Stable child',
      position: [410, 180],
      workflow: child,
      bindings: {},
    }, {
      type: 'tool',
      id: 'root_increment',
      name: 'Root downstream',
      tool_name: 'IncrementAgainNumbers',
      position: [750, 180],
      parameters: { number_plus_one: 1 },
    }],
    edges: [{
      type: 'dataframe',
      id: 'root-to-child',
      source_node: 'root_seed',
      target_node: 'nested_step',
      target_input: 'stable-table-input',
    }, {
      type: 'dataframe',
      id: 'child-to-root',
      source_node: 'nested_step',
      target_node: 'root_increment',
      target_position: 0,
    }],
    interface: { inputs: [], outputs: [] },
    config: { engine: 'direct', execution: 'sequential' },
  }
}

function siblingGraph(name: string, displayName: string): GraphState {
  return {
    schema_version: 1,
    name,
    display_name: displayName,
    nodes: [{
      type: 'tool', id: 'sibling_seed', name: 'Sibling seed', tool_name: 'SeedNumbers',
      position: [180, 160], parameters: {},
    }],
    edges: [],
    interface: { inputs: [], outputs: [] },
    config: { engine: 'direct', execution: 'sequential' },
  }
}

async function createSavedWorkflow(page: Page, graph: GraphState): Promise<void> {
  const created = await page.request.post(`${API_BASE}/api/v1/workflows`, {
    data: { name: graph.name, display_name: graph.display_name },
  })
  expect(created.status(), await created.text()).toBe(201)
  const saved = await page.request.put(`${API_BASE}/api/v1/workflows/${graph.name}`, {
    data: { graph },
  })
  expect(saved.ok(), await saved.text()).toBeTruthy()
}

async function openWorkflow(page: Page, name: string, displayName: string): Promise<void> {
  await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
  await page.getByTestId('workflow-search').fill(displayName)
  await page.getByTestId(`workflow-row-${name}`).dblclick()
  await expect(page.getByTestId('workflow-title')).toHaveText(displayName)
}

async function acceptedDraft(page: Page, name: string): Promise<WorkflowDraftResponse> {
  return expect.poll(async () => {
    const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)
    if (!response.ok()) return null
    return await response.json() as WorkflowDraftResponse
  }).not.toBeNull().then(async () => {
    const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)
    expect(response.ok()).toBeTruthy()
    return await response.json() as WorkflowDraftResponse
  })
}

async function expectExactTable(
  panel: Locator,
  columns: string[],
  rows: string[][],
): Promise<void> {
  const table = panel.locator('.p-datatable')
  await expect(table).toBeVisible()
  await expect.poll(async () => (
    await table.locator('.p-datatable-thead [aria-label^="Sort "]')
      .evaluateAll(buttons => buttons.map(button => button.getAttribute('aria-label')?.slice(5)))
  ), { timeout: 15_000 }).toEqual(columns)
  const bodyRows = table.locator('.p-datatable-tbody tr')
  await expect(bodyRows).toHaveCount(rows.length)
  for (let row = 0; row < rows.length; row++) {
    const cells = bodyRows.nth(row).locator('td')
    await expect(cells).toHaveCount(columns.length)
    for (let column = 0; column < columns.length; column++) {
      await expect(cells.nth(column)).toHaveText(rows[row]![column]!)
    }
  }
}

async function inspectNodeData(
  page: Page,
  nodeId: string,
  dataNodeId: string,
  columns: string[],
  rows: string[][],
) {
  const projectionRequest = page.waitForRequest(request => (
    request.url().endsWith('/api/v1/data-table/query') && request.method() === 'POST'
  ))
  await page.locator(`.vue-flow__node[data-id="${nodeId}"]`).click()
  await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
  expect((await projectionRequest).postDataJSON()).toMatchObject({
    sources: [expect.objectContaining({ node_id: dataNodeId })],
  })
  await expectExactTable(page.getByTestId('data-table-panel'), columns, rows)
}

test('executes nested Direct work and preserves scoped results after save and reopen', async ({ page }) => {
  const rootName = workflowId('nested_execution')
  const rootDisplayName = `Nested execution ${rootName}`
  const siblingName = workflowId('nested_execution_sibling')
  const siblingDisplayName = `Nested sibling ${siblingName}`
  await page.request.post(`${API_BASE}/api/v1/dev/seed`)
  await createSavedWorkflow(page, nestedExecutionGraph(rootName, rootDisplayName))
  await createSavedWorkflow(page, siblingGraph(siblingName, siblingDisplayName))

  try {
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await openWorkflow(page, rootName, rootDisplayName)

    const draft = await acceptedDraft(page, rootName)
    expect(draft.graph.name).toBe(rootName)
    expect(draft.graph.display_name).toBe(rootDisplayName)
    expect(draft.validation).toMatchObject({ valid: true, errors: [] })
    expect(draft.graph.config).toMatchObject({ engine: 'direct', execution: 'sequential' })
    expect(draft.graph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'root-to-child', source_node: 'root_seed', target_node: 'nested_step',
        target_input: 'stable-table-input',
      }),
      expect.objectContaining({
        id: 'child-to-root', source_node: 'nested_step', target_node: 'root_increment',
        target_position: 0,
      }),
    ]))
    const nestedNode = draft.graph.nodes.find(node => node.id === 'nested_step')
    expect(nestedNode?.type).toBe('workflow')
    if (nestedNode?.type !== 'workflow') throw new Error('Expected nested workflow node')
    expect(nestedNode.workflow.interface.inputs[0]).toMatchObject({
      id: 'stable-table-input',
      targets: [{ node: 'nested_increment', port: { kind: 'positional', index: 0 } }],
    })
    expect(nestedNode.workflow.interface.outputs.map(output => output.id)).toEqual([
      'stable-increment-output',
    ])

    const siblingBefore = await (await page.request.get(
      `${API_BASE}/api/v1/workflows/${siblingName}`,
    )).json()
    const runRequest = page.waitForRequest(request => (
      request.url().endsWith('/api/v1/execution/run') && request.method() === 'POST'
    ))
    const runResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-workflow-button').click()
    expect((await runRequest).postDataJSON()).toMatchObject({
      workflow_name: rootName,
      draft_revision: draft.draft_revision,
      graph: { name: rootName },
    })
    expect((await runResponse).status()).toBe(202)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText(
      'Execution complete', { timeout: 30000 },
    )

    const rootRows = [['2', '3'], ['3', '4'], ['4', '5']]
    await inspectNodeData(
      page, 'nested_step', 'nested_step/nested_increment',
      ['number_plus_one'], [['2'], ['3'], ['4']],
    )
    await inspectNodeData(
      page, 'root_increment', 'root_increment',
      ['number_plus_one', 'number_plus_two'], rootRows,
    )

    const status = await (await page.request.get(`${API_BASE}/api/v1/execution/status`)).json()
    expect(status).toMatchObject({
      state: 'idle', workflow_id: rootName, draft_revision: draft.draft_revision,
      last_result: { success: true },
      node_statuses: {
        root_seed: { status: 'executed' },
        'nested_step/nested_increment': { status: 'executed' },
        root_increment: { status: 'executed' },
      },
    })

    const saveResponse = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflows/${rootName}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await saveResponse
    await expect(page.getByTestId('workflow-title')).not.toContainText('*')

    await page.reload()
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await openWorkflow(page, siblingName, siblingDisplayName)
    await expect(page.locator('.vue-flow__node')).toHaveCount(1)
    await expect(page.locator('.vue-flow__node[data-id="sibling_seed"]')).toBeVisible()
    await openWorkflow(page, rootName, rootDisplayName)
    await expect(page.locator('.vue-flow__node')).toHaveCount(3)
    await expect(page.locator('.vue-flow__edge')).toHaveCount(2)
    const reopenedDraft = await acceptedDraft(page, rootName)
    expect(reopenedDraft.validation).toMatchObject({ valid: true, errors: [] })
    expect(reopenedDraft.graph).toEqual(draft.graph)

    await inspectNodeData(
      page, 'nested_step', 'nested_step/nested_increment',
      ['number_plus_one'], [['2'], ['3'], ['4']],
    )
    await inspectNodeData(
      page, 'root_increment', 'root_increment',
      ['number_plus_one', 'number_plus_two'], rootRows,
    )

    const siblingAfter = await (await page.request.get(
      `${API_BASE}/api/v1/workflows/${siblingName}`,
    )).json()
    expect(siblingAfter.graph).toEqual(siblingBefore.graph)
    expect(siblingAfter.artifact_hash).toBe(siblingBefore.artifact_hash)
    expect(siblingAfter.identity_generation).toBe(siblingBefore.identity_generation)
    const siblingResult = await page.request.post(
      `${API_BASE}/api/v1/nodes/sibling_seed/data/query`,
      { data: { workflow_name: siblingName } },
    )
    expect(siblingResult.status()).toBe(404)
  }
  finally {
    await page.request.delete(`${API_BASE}/api/v1/workflows/${rootName}`).catch(() => undefined)
    await page.request.delete(`${API_BASE}/api/v1/workflows/${siblingName}`).catch(() => undefined)
  }
})

test('recovers a failed nested Direct child through an applied GUI correction', async ({ page }) => {
  const rootName = workflowId('nested_direct_recovery')
  const rootDisplayName = `Nested recovery ${rootName}`
  const siblingName = workflowId('nested_direct_sibling')
  const siblingDisplayName = `Independent sibling ${siblingName}`
  await page.request.post(`${API_BASE}/api/v1/dev/seed`)
  await createSavedWorkflow(page, nestedExecutionGraph(rootName, rootDisplayName, true))
  await createSavedWorkflow(page, siblingGraph(siblingName, siblingDisplayName))

  try {
    const siblingBefore = await (await page.request.get(`${API_BASE}/api/v1/workflows/${siblingName}`)).json()
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await openWorkflow(page, rootName, rootDisplayName)
    const initial = await acceptedDraft(page, rootName)
    expect(initial.validation).toMatchObject({ valid: true, errors: [] })
    expect(initial.graph.nodes.find(node => node.id === 'nested_step')).toMatchObject({
      type: 'workflow', workflow: { nodes: [{ id: 'nested_increment', parameters: { fail: true } }] },
    })

    const firstRunPromise = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-workflow-button').click()
    const firstRun = await firstRunPromise
    expect(firstRun.status()).toBe(202)
    expect(firstRun.request().postDataJSON()).toMatchObject({
      workflow_name: rootName, draft_revision: initial.draft_revision, graph: initial.graph,
    })
    const firstExecutionId = (await firstRun.json()).execution_id
    expect(await (await page.request.get(`${API_BASE}/api/v1/executions/${firstExecutionId}`)).json())
      .toMatchObject({ backend: 'direct', workflow_id: rootName, draft_revision: initial.draft_revision })
    await expect.poll(async () => {
      const status = await (await page.request.get(`${API_BASE}/api/v1/execution/status`)).json()
      return [status.state, status.last_result?.success, status.node_statuses?.['nested_step/nested_increment']?.status]
    }, { timeout: 30_000 }).toEqual(['idle', false, 'failed'])
    const failed = await (await page.request.get(`${API_BASE}/api/v1/execution/status`)).json()
    expect(failed).toMatchObject({
      execution_id: firstExecutionId, workflow_id: rootName, draft_revision: initial.draft_revision,
      node_statuses: {
        root_seed: { status: 'executed' },
        'nested_step/nested_increment': { status: 'failed', error: expect.stringContaining('Controlled Direct failure') },
      },
      last_result: { success: false },
    })
    expect(failed.node_statuses.root_increment?.status).not.toBe('executed')
    await expect(page.getByTestId('execution-banner-headline')).toContainText('Controlled Direct failure')
    for (const nodeId of ['nested_step/nested_increment', 'root_increment']) {
      const result = await page.request.post(`${API_BASE}/api/v1/nodes/${nodeId}/data/query`, {
        data: { workflow_name: rootName },
      })
      expect(result.status(), `${nodeId} must not publish a result after child failure`).toBe(404)
    }
    const source = await page.request.post(`${API_BASE}/api/v1/nodes/root_seed/data/query`, {
      data: { workflow_name: rootName },
    })
    expect((await source.json()).rows).toEqual([
      { number: 1, label: 'one' }, { number: 2, label: 'two' }, { number: 3, label: 'three' },
    ])
    const siblingDuringFailure = await (await page.request.get(`${API_BASE}/api/v1/workflows/${siblingName}`)).json()
    expect(siblingDuringFailure).toEqual(siblingBefore)
    const siblingResult = await page.request.post(`${API_BASE}/api/v1/nodes/sibling_seed/data/query`, {
      data: { workflow_name: siblingName },
    })
    expect(siblingResult.status()).toBe(404)

    await page.locator('.vue-flow__node[data-id="nested_step"]').dblclick()
    await expect(page.locator('.nested-workflow-editor')).toBeVisible()
    await page.locator('.vue-flow__node[data-id="nested_increment"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: /^Nodes$/ }).click()
    const failRow = page.getByTestId('panel-nodePanel').locator('.param-row')
      .filter({ hasText: 'Raise a controlled execution error' })
    await expect(failRow.locator('.p-checkbox')).toBeEnabled()
    const privateWrite = page.waitForResponse(response => (
      response.url().includes('/api/v1/nested-workflow-snapshots/')
      && response.request().method() === 'PUT' && response.status() === 200
    ))
    await failRow.locator('.p-checkbox').click()
    const privateSnapshot = await (await privateWrite).json()
    expect(privateSnapshot.graph.nodes[0].parameters.fail).toBe(false)
    expect((await acceptedDraft(page, rootName)).graph).toEqual(initial.graph)
    const applyPromise = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${rootName}`)
      && response.request().method() === 'PUT' && response.status() === 200
    ))
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await applyPromise
    const corrected = await acceptedDraft(page, rootName)
    const correctedNode = corrected.graph.nodes.find(node => node.id === 'nested_step')
    expect(correctedNode).toMatchObject({
      type: 'workflow', workflow: { nodes: [{ id: 'nested_increment', parameters: { fail: false } }] },
    })
    expect(corrected.graph.edges).toEqual(initial.graph.edges)

    await page.locator('.dv-tab').filter({ hasText: rootDisplayName }).click()
    const rerunPromise = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-workflow-button').click()
    const rerun = await rerunPromise
    expect(rerun.status()).toBe(202)
    expect(rerun.request().postDataJSON()).toMatchObject({
      workflow_name: rootName, draft_revision: corrected.draft_revision, graph: corrected.graph,
    })
    const secondExecutionId = (await rerun.json()).execution_id
    expect(secondExecutionId).not.toBe(firstExecutionId)
    expect(await (await page.request.get(`${API_BASE}/api/v1/executions/${secondExecutionId}`)).json())
      .toMatchObject({ backend: 'direct', workflow_id: rootName, draft_revision: corrected.draft_revision })
    await expect.poll(async () => {
      const status = await (await page.request.get(`${API_BASE}/api/v1/execution/status`)).json()
      return [status.state, status.last_result?.success, status.node_statuses?.['nested_step/nested_increment']?.status]
    }, { timeout: 30_000 }).toEqual(['idle', true, 'executed'])
    expect(await (await page.request.get(`${API_BASE}/api/v1/execution/status`)).json()).toMatchObject({
      execution_id: secondExecutionId, workflow_id: rootName, draft_revision: corrected.draft_revision,
      node_statuses: { root_seed: { status: 'executed' }, 'nested_step/nested_increment': { status: 'executed' }, root_increment: { status: 'executed' } },
    })
    await inspectNodeData(page, 'nested_step', 'nested_step/nested_increment',
      ['number_plus_one'], [['2'], ['3'], ['4']])
    await inspectNodeData(page, 'root_increment', 'root_increment',
      ['number_plus_one', 'number_plus_two'], [['2', '3'], ['3', '4'], ['4', '5']])

    const savePromise = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflows/${rootName}`)
      && response.request().method() === 'PUT' && response.status() === 200
    ))
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await savePromise
    const saved = await (await page.request.get(`${API_BASE}/api/v1/workflows/${rootName}`)).json()
    expect(saved.graph).toEqual(corrected.graph)
    await page.reload()
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await openWorkflow(page, siblingName, siblingDisplayName)
    await expect(page.locator('.vue-flow__node[data-id="sibling_seed"]')).toBeVisible()
    await openWorkflow(page, rootName, rootDisplayName)
    expect((await acceptedDraft(page, rootName)).graph).toEqual(corrected.graph)
    await inspectNodeData(page, 'nested_step', 'nested_step/nested_increment',
      ['number_plus_one'], [['2'], ['3'], ['4']])
    await inspectNodeData(page, 'root_increment', 'root_increment',
      ['number_plus_one', 'number_plus_two'], [['2', '3'], ['3', '4'], ['4', '5']])
    const siblingAfter = await (await page.request.get(`${API_BASE}/api/v1/workflows/${siblingName}`)).json()
    expect(siblingAfter).toEqual(siblingBefore)
    const siblingAfterResult = await page.request.post(`${API_BASE}/api/v1/nodes/sibling_seed/data/query`, {
      data: { workflow_name: siblingName },
    })
    expect(siblingAfterResult.status()).toBe(404)
  }
  finally {
    await page.request.delete(`${API_BASE}/api/v1/workflows/${rootName}`).catch(() => undefined)
    await page.request.delete(`${API_BASE}/api/v1/workflows/${siblingName}`).catch(() => undefined)
  }
})
