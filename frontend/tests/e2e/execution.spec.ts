import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import type { ExecutionPresentation, ExecutionPresentationPage } from '../../src/api/types'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

type ToolMetadata = {
  name: string
  display_name: string
  tool_type: string
  accepts_upstream?: boolean
  inputs: Record<string, { required?: boolean }>
}

type GraphState = {
  schema_version: 1
  name: string
  display_name: string
  nodes: Array<Record<string, unknown>>
  edges: Array<Record<string, unknown>>
  interface: { inputs: []; outputs: [] }
  config: { engine: string; execution: string }
}

function uniqueDisplayName(prefix: string): string {
  const project = test.info().project.name.replace(/[^a-zA-Z0-9_-]/g, '_')
  return `${prefix} ${project} ${Date.now()} ${Math.floor(Math.random() * 10000)}`
}

function deriveWorkflowId(value: string): string {
  return value
    .trim()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .replace(/_+/g, '_')
    .toLowerCase()
}

async function seedTools(page: Page) {
  const response = await page.request.post(`${API_BASE}/api/v1/dev/seed`)
  expect(response.ok()).toBeTruthy()
}

async function sourceTool(page: Page): Promise<ToolMetadata> {
  const response = await page.request.get(`${API_BASE}/api/v1/tools`)
  expect(response.ok()).toBeTruthy()
  const tools = (await response.json()) as ToolMetadata[]
  const tool = tools.find((candidate) => candidate.name === 'SeedNumbers')
  expect(tool, '/api/v1/dev/seed must register executable SeedNumbers').toBeTruthy()
  expect(tool?.tool_type).toBe('DataFrameTool')
  expect(tool?.accepts_upstream).toBe(false)
  expect(
    Object.values(tool?.inputs ?? {}).every((input) => input.required !== true),
  ).toBe(true)
  return tool!
}

async function openWorkflowItem(page: Page, label: string) {
  await page
    .getByRole('menuitem', { name: 'Workflow', exact: true })
    .click()
  await page.getByRole('menuitem', { name: label, exact: true }).click()
}

async function createWorkflowInGui(page: Page, displayName: string) {
  await openWorkflowItem(page, 'New')
  await expect(page.locator('[data-testid="workflow-dialog"]')).toBeVisible()
  await page.locator('[data-testid="workflow-display-name-input"]').fill(displayName)
  await page.locator('[data-testid="workflow-dialog-submit"]').click()
  await expect(page.locator('[data-testid="workflow-dialog"]')).not.toBeVisible()
  await expect(page.locator('[data-testid="workflow-title"]')).toContainText(displayName)
}

async function addSourceNode(page: Page, source: ToolMetadata, workflowName: string) {
  // The fixture updates the saved workflow directly. Unmount the active canvas
  // first so its debounced draft writer cannot race the reset-to-saved CAS.
  await page.goto('about:blank')
  const current = await page.request.get(`${API_BASE}/api/v1/workflows/${workflowName}`)
  expect(current.ok()).toBeTruthy()
  const document = await current.json()
  document.graph.nodes = [{
    type: 'tool',
    id: 'seed_1',
    name: source.display_name,
    tool_name: source.name,
    position: [300, 180],
    parameters: {},
  }]
  const saved = await page.request.put(`${API_BASE}/api/v1/workflows/${workflowName}`, {
    data: { graph: document.graph },
  })
  expect(saved.ok()).toBeTruthy()
  const draft = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`)
  expect(draft.ok()).toBeTruthy()
  const draftRevision = (await draft.json()).draft_revision
  const reset = await page.request.post(
    `${API_BASE}/api/v1/workflow-drafts/${workflowName}/reset-to-saved`,
    { data: { expected_revision: draftRevision, updated_by: 'frontend' } },
  )
  expect(reset.ok()).toBeTruthy()
  await page.goto('/')
  const node = page.locator('.vue-flow__node[data-id="seed_1"]')
  await expect(node).toBeVisible({ timeout: 5000 })
  await expect(node.locator('.node-name')).toContainText(source.display_name)
  return node
}

async function replaceWithSelectedRunFixture(
  page: Page,
  workflowName: string,
  displayName: string,
) {
  await page.goto('about:blank')
  const graph: GraphState = {
    schema_version: 1,
    name: workflowName,
    display_name: displayName,
    nodes: [
      {
        type: 'tool', id: 'seed_valid', name: 'Valid seed', tool_name: 'SeedNumbers',
        position: [120, 140], parameters: {},
      },
      {
        type: 'tool', id: 'increment_valid', name: 'Selected increment', tool_name: 'IncrementNumbers',
        position: [460, 140], parameters: { number: 1 },
      },
      {
        type: 'tool', id: 'unrelated_invalid', name: 'Unrelated invalid branch', tool_name: 'MissingCampaignTool',
        position: [280, 390], parameters: {},
      },
    ],
    edges: [{
      type: 'dataframe',
      id: 'valid-dataframe-edge',
      source_node: 'seed_valid',
      target_node: 'increment_valid',
      target_position: 0,
    }],
    interface: { inputs: [], outputs: [] },
    config: { engine: 'direct', execution: 'sequential' },
  }
  const saved = await page.request.put(`${API_BASE}/api/v1/workflows/${workflowName}`, {
    data: { graph },
  })
  expect(saved.ok()).toBeTruthy()
  const currentDraft = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`)
  expect(currentDraft.ok()).toBeTruthy()
  const reset = await page.request.post(
    `${API_BASE}/api/v1/workflow-drafts/${workflowName}/reset-to-saved`,
    {
      data: {
        expected_revision: (await currentDraft.json()).draft_revision,
        updated_by: 'frontend',
      },
    },
  )
  expect(reset.ok()).toBeTruthy()
  const acceptedDraft = await reset.json()
  expect(acceptedDraft.validation.valid).toBe(false)
  expect(acceptedDraft.validation.errors).toEqual(expect.arrayContaining([{
    type: 'missing_tool',
    node: 'unrelated_invalid',
    detail: "Tool 'MissingCampaignTool' not found in registry",
    edge_id: null,
    field: null,
  }]))
  expect(acceptedDraft.validation.errors.every(
    (error: { type: string; node: string }) => (
      error.type === 'missing_tool' && error.node === 'unrelated_invalid'
    ),
  )).toBe(true)
  await page.goto('/')
  return acceptedDraft.draft_revision as number
}

async function waitForExecutionComplete(page: Page, nodeId: string) {
  await expect
    .poll(
      async () => {
        const response = await page.request.get(`${API_BASE}/api/v1/execution/status`)
        expect(response.ok()).toBeTruthy()
        const status = await response.json()
        return {
          state: status.state,
          success: status.last_result?.success ?? null,
          nodeStatus: status.node_statuses?.[nodeId]?.status ?? null,
        }
      },
      { timeout: 10000 },
    )
    .toEqual({ state: 'idle', success: true, nodeStatus: 'executed' })
}

test.describe('execution lifecycle', () => {
  test.beforeEach(async ({ page }) => {
    await seedTools(page)
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
  })

  test('Execution panel shows local setup text before numeric job progress, then refreshes', async ({ page }) => {
    const workflowId = deriveWorkflowId(uniqueDisplayName('Local Setup'))
    const runId = 'run_0123456789abcdef0123456789abcdef'
    const setup: ExecutionPresentation = {
      revision: 1,
      execution_id: runId,
      workflow_id: workflowId,
      draft_revision: 1,
      command: 'run',
      backend: 'wetlands',
      target_id: 'local',
      target_label: 'Local',
      target_mode: 'local',
      state: 'running',
      jobs: {
        held_worker: {
          scoped_node_path: 'held_worker',
          state: 'running',
          row: 0,
          total_rows: 0,
          current: null,
          maximum: null,
          message: 'Installing execution environment',
        },
      },
      progress_cursor: 0,
      actions: {
        cancel: { available: true, reason: null },
        retry: { available: false, reason: 'Run is active.' },
        recompute: { available: false, reason: 'Run is active.' },
        download_results: { available: false, reason: 'Run is active.' },
        cleanup: { available: false, reason: 'Local run.' },
      },
      observation: { reachable: true },
      created_at: '2026-09-24T10:00:00Z',
      updated_at: '2026-09-24T10:00:00Z',
    }
    const processing: ExecutionPresentation = {
      ...setup,
      revision: 2,
      jobs: {
        held_worker: {
          ...setup.jobs!.held_worker!,
          row: 0,
          total_rows: 3,
          current: 1,
          maximum: 3,
          message: 'Processing row 1/3',
        },
      },
    }
    let current = setup
    await page.route(/\/api\/v1\/executions(?:\?.*)?$/, route => {
      const response: ExecutionPresentationPage = {
        items: [current], total: 1, offset: 0, limit: 50,
      }
      return route.fulfill({ status: 200, contentType: 'application/json', json: response })
    })
    let detailRequests = 0
    await page.route(`**/api/v1/executions/${runId}`, route => {
      detailRequests += 1
      return route.fulfill({ status: 200, contentType: 'application/json', json: current })
    })

    await page.locator('.dv-tab').filter({ hasText: /^Execution$/ }).click()
    const panel = page.getByTestId('panel-execution')
    await panel.getByRole('button', { name: 'Workspace', exact: true }).click()
    await expect(panel).toContainText(runId)
    const job = panel.getByRole('row').filter({ hasText: 'Installing execution environment' })
    await expect(job).toContainText('Installing execution environment')
    await expect(job.getByRole('progressbar')).toHaveCount(0)
    await expect(job).toContainText('—')

    current = processing
    await expect.poll(() => detailRequests, { timeout: 10_000 }).toBeGreaterThan(0)
    const progressingJob = panel.getByRole('row').filter({ hasText: 'Processing row 1/3' })
    await expect(progressingJob.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '33')
    await expect(progressingJob).toContainText('Processing row 1/3')
  })

  test('creates a workflow and executes a source tool through the real backend', { tag: '@critical' }, async ({
    page,
  }) => {
    const displayName = uniqueDisplayName('Execution Workflow')
    const workflowName = deriveWorkflowId(displayName)
    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`).catch(() => undefined)

    await createWorkflowInGui(page, displayName)
    const source = await sourceTool(page)
    const node = await addSourceNode(page, source, workflowName)
    const nodeId = await node.getAttribute('data-id')
    expect(nodeId).toBeTruthy()

    const runResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes('/api/v1/execution/run') &&
        resp.request().method() === 'POST',
    )
    const runButton = page.locator('[data-testid="run-workflow-button"]')
    await expect(runButton).toBeEnabled({ timeout: 5000 })
    await runButton.click()
    expect((await runResponse).status()).toBe(202)

    await waitForExecutionComplete(page, nodeId!)
    await expect(node.locator('.tool-node')).toHaveClass(/status-executed/)
    await expect(page.locator('[data-testid="execution-banner-headline"]')).toContainText(
      'Execution complete',
      { timeout: 5000 },
    )

    await node.click()
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    const nodeDataPanel = page.locator('[data-testid="data-table-panel"]')
    const paginator = page.locator('[data-testid="node-data-paginator"]')
    await expect(nodeDataPanel).toBeVisible()
    await expect(paginator).toBeVisible()
    await expect(page.getByRole('separator', { name: /^Resize / }).first()).toBeVisible()
    const panelBox = await nodeDataPanel.boundingBox()
    const paginatorBox = await paginator.boundingBox()
    expect(panelBox).toBeTruthy()
    expect(paginatorBox).toBeTruthy()
    expect(paginatorBox!.y + paginatorBox!.height).toBeLessThanOrEqual(
      panelBox!.y + panelBox!.height + 1,
    )

    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`).catch(() => undefined)
  })

  test('Run Selected executes a valid branch while an unrelated invalid branch remains unexecuted', async ({
    page,
  }) => {
    const displayName = uniqueDisplayName('Selected Branch Workflow')
    const workflowName = deriveWorkflowId(displayName)
    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`).catch(() => undefined)

    await createWorkflowInGui(page, displayName)
    const draftRevision = await replaceWithSelectedRunFixture(page, workflowName, displayName)

    await expect(page.getByTestId('workflow-title')).toHaveText(displayName)
    await expect(page.locator('.vue-flow__node')).toHaveCount(3)
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)
    const source = page.locator('.vue-flow__node[data-id="seed_valid"]')
    const selected = page.locator('.vue-flow__node[data-id="increment_valid"]')
    const unrelated = page.locator('.vue-flow__node[data-id="unrelated_invalid"]')
    await expect(source.locator('.node-name')).toHaveText('Valid seed')
    await expect(selected.locator('.node-name')).toHaveText('Selected increment')
    await expect(unrelated.locator('.node-name')).toHaveText('Unrelated invalid branch')
    const dependencies = page.getByRole('dialog', { name: 'Workflow dependencies' })
    await expect(dependencies).toContainText('Missing tools')
    await expect(dependencies).toContainText('MissingCampaignTool')
    await expect(dependencies).toContainText('Node: unrelated_invalid')
    await dependencies.getByRole('button', { name: 'Close' }).last().click()

    await unrelated.click()
    await page.locator('.dv-tab').filter({ hasText: /^Nodes$/ }).click()
    await expect(page.getByTestId('node-validation-errors')).toHaveText(
      /Validation errors\s*Tool 'MissingCampaignTool' not found in registry/,
    )

    await selected.click()
    await expect(page.getByTestId('run-selected-button')).toBeEnabled()
    const runRequest = page.waitForRequest(request => (
      request.url().endsWith('/api/v1/execution/run') && request.method() === 'POST'
    ))
    const runResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-selected-button').click()
    const request = await runRequest
    expect(request.postDataJSON()).toMatchObject({
      workflow_id: workflowName,
      draft_revision: draftRevision,
      nodes: ['increment_valid'],
    })
    expect(request.postDataJSON()).not.toHaveProperty('graph')
    const firstAcceptedResponse = await runResponse
    expect(firstAcceptedResponse.status()).toBe(202)
    const firstAccepted = await firstAcceptedResponse.json()
    expect(firstAccepted).toMatchObject({
      execution_id: expect.stringMatching(/^run_/),
      workflow_id: workflowName,
      draft_revision: draftRevision,
      planned_node_ids: ['seed_valid', 'increment_valid'],
      planned_node_names: {
        seed_valid: 'Valid seed',
        increment_valid: 'Selected increment',
      },
    })

    await waitForExecutionComplete(page, 'increment_valid')
    await expect(source.locator('.tool-node')).toHaveClass(/status-executed/)
    await expect(selected.locator('.tool-node')).toHaveClass(/status-executed/)
    await expect(unrelated.locator('.tool-node')).toHaveClass(/status-unexecuted/)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete')
    await expect(page.getByTestId('execution-banner-node-count')).toHaveText('2/2 nodes complete')
    await expect(page.getByTestId('execution-banner-overall-progress')).toHaveAttribute('aria-valuenow', '100')
    await expect(page.getByTestId('execution-banner-row-progress')).toHaveCount(0)

    const result = await page.request.post(
      `${API_BASE}/api/v1/nodes/increment_valid/data/query`,
      { data: { workflow_name: workflowName } },
    )
    expect(result.ok()).toBeTruthy()
    expect(await result.json()).toMatchObject({
      columns: ['number', 'label', 'number_plus_one'],
      rows: [
        { number: 1, label: 'one', number_plus_one: 2 },
        { number: 2, label: 'two', number_plus_one: 3 },
        { number: 3, label: 'three', number_plus_one: 4 },
      ],
      total_rows: 3,
    })

    const statusResponse = await page.request.get(`${API_BASE}/api/v1/execution/status`)
    expect(statusResponse.ok()).toBeTruthy()
    const status = await statusResponse.json()
    expect(status).toMatchObject({
      state: 'idle',
      execution_id: firstAccepted.execution_id,
      workflow_id: workflowName,
      draft_revision: draftRevision,
      planned_node_ids: ['seed_valid', 'increment_valid'],
      planned_node_names: firstAccepted.planned_node_names,
      last_result: { success: true },
    })
    expect(status.node_statuses.seed_valid).toMatchObject({ status: 'executed', cached: false })
    expect(status.node_statuses.increment_valid).toMatchObject({ status: 'executed', cached: false })
    expect(status.node_statuses.unrelated_invalid).toBeUndefined()

    const unrelatedResult = await page.request.post(
      `${API_BASE}/api/v1/nodes/unrelated_invalid/data/query`,
      { data: { workflow_name: workflowName } },
    )
    expect(unrelatedResult.status()).toBe(404)

    const cachedRunResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST'
    ))
    await selected.click()
    await page.getByTestId('run-selected-button').click()
    const cachedAcceptedResponse = await cachedRunResponse
    expect(cachedAcceptedResponse.status()).toBe(202)
    const cachedAccepted = await cachedAcceptedResponse.json()
    expect(cachedAccepted).toMatchObject({
      execution_id: expect.stringMatching(/^run_/),
      workflow_id: workflowName,
      draft_revision: draftRevision,
      planned_node_ids: ['seed_valid', 'increment_valid'],
      planned_node_names: firstAccepted.planned_node_names,
    })
    expect(cachedAccepted.execution_id).not.toBe(firstAccepted.execution_id)
    await waitForExecutionComplete(page, 'increment_valid')
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete')
    await expect(page.getByTestId('execution-banner-node-count')).toHaveText('2/2 nodes complete')
    await expect(page.getByTestId('execution-banner-overall-progress')).toHaveAttribute('aria-valuenow', '100')
    const cachedStatusResponse = await page.request.get(`${API_BASE}/api/v1/execution/status`)
    expect(cachedStatusResponse.ok()).toBeTruthy()
    const cachedStatus = await cachedStatusResponse.json()
    expect(cachedStatus).toMatchObject({
      state: 'idle',
      execution_id: cachedAccepted.execution_id,
      workflow_id: workflowName,
      draft_revision: draftRevision,
      planned_node_ids: ['seed_valid', 'increment_valid'],
      planned_node_names: firstAccepted.planned_node_names,
      last_result: { success: true },
      node_statuses: {
        seed_valid: { status: 'executed', cached: true },
        increment_valid: { status: 'executed', cached: true },
      },
    })
    expect(cachedStatus.node_statuses.unrelated_invalid).toBeUndefined()
    const cachedResult = await page.request.post(
      `${API_BASE}/api/v1/nodes/increment_valid/data/query`,
      { data: { workflow_name: workflowName } },
    )
    expect(cachedResult.ok()).toBeTruthy()
    expect(await cachedResult.json()).toMatchObject({
      columns: ['number', 'label', 'number_plus_one'],
      rows: [
        { number: 1, label: 'one', number_plus_one: 2 },
        { number: 2, label: 'two', number_plus_one: 3 },
        { number: 3, label: 'three', number_plus_one: 4 },
      ],
      total_rows: 3,
    })
    expect((await page.request.post(
      `${API_BASE}/api/v1/nodes/unrelated_invalid/data/query`,
      { data: { workflow_name: workflowName } },
    )).status()).toBe(404)

    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`).catch(() => undefined)
  })
})
