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
  const catalogTabs = page.locator('.dv-tabs-container').filter({
    has: page.locator('.dv-tab').filter({ hasText: /^Tools$/ }),
  })
  await catalogTabs.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
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

test('Run Selected expands recursive dependencies and refuses an invalid nested boundary', async ({ page }) => {
  const rootName = workflowId('recursive_selected')
  const rootDisplayName = `Recursive selected ${rootName}`
  const graph = nestedExecutionGraph(rootName, rootDisplayName)
  const invalidChild = nestedExecutionGraph('invalid_child', 'Invalid child').nodes[1]
  if (invalidChild?.type !== 'workflow') throw new Error('Expected workflow fixture')
  invalidChild.id = 'unrelated_nested'
  invalidChild.name = 'Unrelated invalid child'
  invalidChild.position = [420, 430]
  invalidChild.workflow.name = 'unrelated_invalid_child'
  invalidChild.workflow.interface.inputs = []
  invalidChild.workflow.interface.outputs = []
  invalidChild.workflow.nodes[0]!.tool_name = 'MissingCampaignTool'
  graph.nodes.push(invalidChild)
  await page.request.post(`${API_BASE}/api/v1/dev/seed`)
  await page.goto('/')
  await expect(page.locator('#bioimageflow-app')).toBeVisible()
  await createSavedWorkflow(page, graph)
  const siblingName = workflowId('recursive_selected_sibling')
  await createSavedWorkflow(page, siblingGraph(siblingName, `Recursive selected sibling ${siblingName}`))
  const siblingBefore = await (await page.request.get(`${API_BASE}/api/v1/workflows/${siblingName}`)).json()

  try {
    await openWorkflow(page, rootName, rootDisplayName)
    const draft = await acceptedDraft(page, rootName)
    expect(draft.graph.name).toBe(rootName)
    expect(draft.graph.nodes.map(node => node.id)).toEqual([
      'root_seed', 'nested_step', 'root_increment', 'unrelated_nested',
    ])
    expect(draft.graph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({ source_node: 'root_seed', target_node: 'nested_step', target_input: 'stable-table-input' }),
      expect.objectContaining({ source_node: 'nested_step', target_node: 'root_increment', target_position: 0 }),
    ]))
    expect(draft.validation.errors).toEqual(expect.arrayContaining([
      expect.objectContaining({ type: 'missing_tool', node: 'unrelated_nested/nested_increment' }),
    ]))
    const dependencies = page.getByRole('dialog', { name: 'Workflow dependencies' })
    await expect(dependencies).toContainText('MissingCampaignTool')
    await dependencies.getByRole('button', { name: 'Close' }).last().click()

    await page.locator('.vue-flow__node[data-id="root_increment"]').click()
    const selectedRun = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-selected-button').click()
    const accepted = await selectedRun
    expect(accepted.status(), await accepted.text()).toBe(202)
    expect(accepted.request().postDataJSON()).toMatchObject({
      workflow_id: rootName, draft_revision: draft.draft_revision,
      nodes: ['root_increment'],
    })
    const executionId = (await accepted.json()).execution_id
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete', { timeout: 30_000 })
    const completed = await (await page.request.get(`${API_BASE}/api/v1/execution/status`)).json()
    expect(completed).toMatchObject({
      execution_id: executionId, workflow_id: rootName, draft_revision: draft.draft_revision,
      last_result: { success: true },
      node_statuses: {
        root_seed: { status: 'executed' },
        'nested_step/nested_increment': { status: 'executed' },
        root_increment: { status: 'executed' },
      },
    })
    expect(completed.node_statuses['unrelated_nested/nested_increment']).toBeUndefined()
    await inspectNodeData(page, 'nested_step', 'nested_step/nested_increment',
      ['number_plus_one'], [['2'], ['3'], ['4']])
    await inspectNodeData(page, 'root_increment', 'root_increment',
      ['number_plus_one', 'number_plus_two'], [['2', '3'], ['3', '4'], ['4', '5']])

    await page.locator('.vue-flow__node[data-id="unrelated_nested"]').click()
    const refusedRun = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-selected-button').click()
    const refused = await refusedRun
    expect(refused.status()).toBe(422)
    expect(refused.request().postDataJSON()).toMatchObject({
      workflow_id: rootName, draft_revision: draft.draft_revision,
      nodes: ['unrelated_nested'],
    })
    expect(await refused.text()).toContain('unrelated_nested/nested_increment')
    await expect(page.locator('.p-toast')).toContainText('Validation errors')
    await expect(page.locator('.p-toast')).toContainText('unrelated_nested/nested_increment')
    const afterRefusal = await acceptedDraft(page, rootName)
    expect(afterRefusal.graph).toEqual(draft.graph)
    expect(afterRefusal.draft_revision).toBe(draft.draft_revision)
    expect(afterRefusal.workflow_id).toBe(draft.workflow_id)
    expect(afterRefusal.base_saved_revision).toBe(draft.base_saved_revision)
    expect(await (await page.request.get(`${API_BASE}/api/v1/execution/status`)).json()).toEqual(completed)
    const unrelatedResult = await page.request.post(
      `${API_BASE}/api/v1/nodes/unrelated_nested/nested_increment/data/query`,
      { data: { workflow_name: rootName } },
    )
    expect(unrelatedResult.status()).toBe(404)
    expect(await (await page.request.get(`${API_BASE}/api/v1/workflows/${siblingName}`)).json())
      .toEqual(siblingBefore)
    const siblingResult = await page.request.post(`${API_BASE}/api/v1/nodes/sibling_seed/data/query`, {
      data: { workflow_name: siblingName },
    })
    expect(siblingResult.status()).toBe(404)
    await inspectNodeData(page, 'root_increment', 'root_increment',
      ['number_plus_one', 'number_plus_two'], [['2', '3'], ['3', '4'], ['4', '5']])
  }
  finally {
    await page.request.delete(`${API_BASE}/api/v1/workflows/${rootName}`).catch(() => undefined)
    await page.request.delete(`${API_BASE}/api/v1/workflows/${siblingName}`).catch(() => undefined)
  }
})

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
      workflow_id: rootName,
      draft_revision: draft.draft_revision,
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

test('opened nested canvases inspect the results of their own instance', async ({ page }) => {
  const rootName = workflowId('nested_instance_results')
  const rootDisplayName = `Nested instance results ${rootName}`
  const graph = nestedExecutionGraph(rootName, rootDisplayName)
  const first = graph.nodes.find(node => node.id === 'nested_step')
  if (first?.type !== 'workflow') throw new Error('Expected nested workflow node')
  first.name = 'First marker analysis'
  first.workflow.interface.inputs = []
  first.workflow.nodes.push({
    type: 'tool',
    id: 'internal_seed',
    name: 'Unpublished intermediate',
    tool_name: 'SeedNumbers',
    position: [40, 160],
    parameters: {},
  })
  first.workflow.edges.push({
    type: 'dataframe',
    id: 'internal-seed-to-increment',
    source_node: 'internal_seed',
    target_node: 'nested_increment',
    target_position: 0,
  })
  graph.edges = graph.edges.filter(edge => edge.target_node !== 'nested_step')
  const second = structuredClone(first)
  second.id = 'second_nested_step'
  second.name = 'Second marker analysis'
  second.position = [410, 410]
  graph.nodes.push(second)
  await page.request.post(`${API_BASE}/api/v1/dev/seed`)
  await createSavedWorkflow(page, graph)

  try {
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await openWorkflow(page, rootName, rootDisplayName)
    const runResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run')
      && response.request().method() === 'POST'
      && response.status() === 202
    ))
    await page.getByTestId('run-workflow-button').click()
    const acceptedRun = await (await runResponse).json() as { execution_id: string }
    await expect.poll(async () => {
      const response = await page.request.get(`${API_BASE}/api/v1/execution/status`)
      const status = await response.json()
      return [status.execution_id, status.workflow_id, status.state, status.last_result?.success]
    }, { timeout: 30_000 }).toEqual([acceptedRun.execution_id, rootName, 'idle', true])
    await expect(page.getByTestId('execution-banner-headline')).toHaveText(
      'Execution complete', { timeout: 30_000 },
    )

    for (const instance of [
      { id: 'nested_step', name: 'First marker analysis', rows: [['1', 'one', '2'], ['2', 'two', '3'], ['3', 'three', '4']] },
      { id: 'second_nested_step', name: 'Second marker analysis', rows: [['1', 'one', '2'], ['2', 'two', '3'], ['3', 'three', '4']] },
    ]) {
      await page.locator(`.vue-flow__node[data-id="${instance.id}"]:visible`).dblclick()
      await expect(page.locator('.dv-tab').filter({ hasText: instance.name })).toBeVisible()
      const internal = page.locator('.vue-flow__node[data-id="nested_increment"]:visible')
      await expect(internal.locator('.status-indicator')).toHaveClass(/status-executed/)
      const projectionRequest = page.waitForRequest(request => (
        request.url().endsWith('/api/v1/data-table/query')
        && request.method() === 'POST'
        && request.postDataJSON()?.sources?.some((source: { node_id: string }) => (
          source.node_id === `${instance.id}/nested_increment`
        ))
      ))
      await internal.click()
      await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
      await projectionRequest
      await expectExactTable(page.getByTestId('data-table-panel'), ['number', 'label', 'number_plus_one'], instance.rows)
      const intermediate = page.locator('.vue-flow__node[data-id="internal_seed"]:visible')
      await expect(intermediate.locator('.status-indicator')).toHaveClass(/status-executed/)
      const intermediateRequest = page.waitForRequest(request => (
        request.url().endsWith('/api/v1/data-table/query')
        && request.method() === 'POST'
        && request.postDataJSON()?.sources?.some((source: { node_id: string }) => (
          source.node_id === `${instance.id}/internal_seed`
        ))
      ))
      await intermediate.click()
      await intermediateRequest
      await expectExactTable(page.getByTestId('data-table-panel'),
        ['number', 'label'], [['1', 'one'], ['2', 'two'], ['3', 'three']])
      await page.locator('.dv-tab').filter({ hasText: rootDisplayName }).click()
    }
    await page.reload()
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await openWorkflow(page, rootName, rootDisplayName)
    await page.locator('.dv-tab').filter({ hasText: rootDisplayName }).click()
    await page.locator('.vue-flow__node[data-id="second_nested_step"]:visible').dblclick()
    await expect(page.locator('.nested-workflow-editor:visible')).toBeVisible()
    const reopened = page.locator('.vue-flow__node[data-id="nested_increment"]:visible')
    await expect(reopened.locator('.status-indicator')).toHaveClass(/status-executed/)
    await reopened.click()
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    await expectExactTable(page.getByTestId('data-table-panel'),
      ['number', 'label', 'number_plus_one'],
      [['1', 'one', '2'], ['2', 'two', '3'], ['3', 'three', '4']])
  } finally {
    await page.request.delete(`${API_BASE}/api/v1/workflows/${rootName}`).catch(() => undefined)
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
      workflow_id: rootName, draft_revision: initial.draft_revision,
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
    const nestedIncrement = page.locator('.vue-flow__node[data-id="nested_increment"]:visible')
    await expect(nestedIncrement.locator('.status-indicator')).toHaveClass(/status-failed/)
    await nestedIncrement.click()
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
      workflow_id: rootName, draft_revision: corrected.draft_revision,
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
    await page.locator('.dv-tab').filter({ hasText: 'Stable child' }).click()
    await expect(nestedIncrement.locator('.status-indicator')).toHaveClass(/status-executed/)
    await nestedIncrement.click()
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    await expectExactTable(page.getByTestId('data-table-panel'),
      ['number', 'label', 'number_plus_one'],
      [['1', 'one', '2'], ['2', 'two', '3'], ['3', 'three', '4']])
    await page.locator('.dv-tab').filter({ hasText: rootDisplayName }).click()
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
