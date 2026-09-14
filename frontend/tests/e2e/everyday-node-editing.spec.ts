import { expect, test } from '@playwright/test'
import type { Locator, Page } from '@playwright/test'
import type { GraphState } from '../../src/api/types'
import type { WorkflowDraftResponse } from '../../src/api/workflowDrafts'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`
const SOURCE_ID = 'everyday_source'
const TARGET_ID = 'everyday_target'
const EDGE_ID = 'everyday_dataframe_edge'

function uniqueWorkflowName(): string {
  const project = test.info().project.name.replace(/[^a-zA-Z0-9_-]/g, '_')
  return `everyday_node_editing_${project}_${Date.now()}_${Math.floor(Math.random() * 10000)}`
}

function editingGraph(workflowName: string): GraphState {
  return {
    schema_version: 1,
    name: workflowName,
    display_name: workflowName,
    nodes: [
      {
        type: 'tool',
        id: SOURCE_ID,
        name: 'Source node',
        tool_name: 'SeedNumbers',
        position: [180, 180],
        parameters: {},
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
      },
      {
        type: 'tool',
        id: TARGET_ID,
        name: 'Target node',
        tool_name: 'IncrementNumbers',
        position: [520, 180],
        parameters: { number: 1 },
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
      },
    ],
    edges: [{
      type: 'dataframe',
      id: EDGE_ID,
      source_node: SOURCE_ID,
      target_node: TARGET_ID,
      target_position: 0,
    }],
    interface: { inputs: [], outputs: [] },
    config: { engine: 'direct', execution: 'parallel' },
  }
}

async function createAndOpenFixture(page: Page, workflowName: string): Promise<void> {
  const seeded = await page.request.post(`${API_BASE}/api/v1/dev/seed`)
  expect(seeded.ok()).toBeTruthy()

  const toolsResponse = await page.request.get(`${API_BASE}/api/v1/tools`)
  expect(toolsResponse.ok()).toBeTruthy()
  const tools = await toolsResponse.json() as Array<Record<string, unknown>>
  expect(tools.find(tool => tool.name === 'SeedNumbers')).toMatchObject({
    tool_type: 'DataFrameTool',
    accepts_upstream: false,
    dataframe_output: true,
    outputs: { number: { type: 'int' }, label: { type: 'str' } },
  })
  expect(tools.find(tool => tool.name === 'IncrementNumbers')).toMatchObject({
    tool_type: 'DataFrameTool',
    accepts_upstream: true,
    dataframe_output: true,
    inputs: { number: { type: 'int' } },
    outputs: { number_plus_one: { type: 'int' } },
  })

  const graph = editingGraph(workflowName)
  const validation = await page.request.put(`${API_BASE}/api/v1/graph`, { data: graph })
  expect(validation.ok()).toBeTruthy()
  expect(await validation.json()).toMatchObject({ valid: true, errors: [] })

  const created = await page.request.post(`${API_BASE}/api/v1/workflows`, {
    data: { name: workflowName, display_name: workflowName },
  })
  expect(created.status()).toBe(201)
  const saved = await page.request.put(`${API_BASE}/api/v1/workflows/${workflowName}`, {
    data: { graph },
  })
  expect(saved.ok()).toBeTruthy()

  await page.goto('/')
  await expect(page.locator('#bioimageflow-app')).toBeVisible()
  await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
  await page.getByTestId('workflow-search').fill(workflowName)
  const row = page.getByTestId(`workflow-row-${workflowName}`)
  await expect(row).toBeVisible()
  await row.dblclick()
  await expect(page.getByTestId('workflow-title')).toContainText(workflowName)
  await expect(page.locator('.vue-flow__node')).toHaveCount(2)
  await expectAcceptedDraft(page, workflowName, draft => draft.validation.valid)
}

async function fetchDraft(page: Page, workflowName: string): Promise<WorkflowDraftResponse> {
  const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`)
  expect(response.ok()).toBeTruthy()
  return response.json() as Promise<WorkflowDraftResponse>
}

async function expectAcceptedDraft<T>(
  page: Page,
  workflowName: string,
  projection: (draft: WorkflowDraftResponse) => T | Promise<T>,
  expected: T = true as T,
): Promise<void> {
  await expect.poll(async () => projection(await fetchDraft(page, workflowName))).toEqual(expected)
}

async function waitForAcceptedEdit(page: Page, workflowName: string, action: () => Promise<void>) {
  const accepted = page.waitForResponse(response => (
    response.url().endsWith(`/api/v1/workflow-drafts/${workflowName}`)
    && response.request().method() === 'PUT'
    && response.status() === 200
  ))
  await action()
  await accepted
}

function node(page: Page, id: string): Locator {
  return page.locator(`.vue-flow__node[data-id="${id}"]`)
}

async function openNodesPanel(page: Page): Promise<Locator> {
  await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
  const panel = page.getByTestId('panel-nodePanel')
  await expect(panel).toBeVisible()
  return panel
}

test.describe('everyday node editing', () => {
  let workflowName: string

  test.beforeEach(async ({ page }) => {
    workflowName = uniqueWorkflowName()
    await createAndOpenFixture(page, workflowName)
  })

  test.afterEach(async ({ page }) => {
    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`).catch(() => undefined)
  })

  test('selects, toggles a multiselection, deselects, and persists bulk enablement', async ({ page }) => {
    const source = node(page, SOURCE_ID)
    const target = node(page, TARGET_ID)
    await source.click()
    await expect(source).toHaveClass(/selected/)
    await expect(target).not.toHaveClass(/selected/)

    const panel = await openNodesPanel(page)
    await expect(panel.locator('.node-name')).toHaveText('Source node')

    await target.click({ modifiers: ['Shift'] })
    await expect(source).toHaveClass(/selected/)
    await expect(target).toHaveClass(/selected/)
    await expect(panel.locator('.multi-select')).toContainText('2 nodes selected')
    await expect(panel.getByTestId('bulk-disable-nodes')).toBeVisible()
    await expect(panel.locator('.node-details')).toHaveCount(0)

    await waitForAcceptedEdit(page, workflowName, () => panel.getByTestId('bulk-disable-nodes').click())
    await expect(source.locator('.tool-node')).toHaveClass(/disabled/)
    await expect(target.locator('.tool-node')).toHaveClass(/disabled/)
    await expectAcceptedDraft(
      page,
      workflowName,
      draft => draft.graph.nodes.map(graphNode => graphNode.enabled),
      [false, false],
    )

    await page.reload()
    await expect(source.locator('.tool-node')).toHaveClass(/disabled/)
    await expect(target.locator('.tool-node')).toHaveClass(/disabled/)
    await source.click()
    await target.click({ modifiers: ['Shift'] })
    await waitForAcceptedEdit(page, workflowName, () => panel.getByTestId('bulk-enable-nodes').click())
    await expect(source.locator('.tool-node')).not.toHaveClass(/disabled/)
    await expect(target.locator('.tool-node')).not.toHaveClass(/disabled/)

    await page.locator('.vue-flow__pane').click({ position: { x: 20, y: 20 } })
    await expect(source).not.toHaveClass(/selected/)
    await expect(target).not.toHaveClass(/selected/)
    await expect(panel).toContainText('Select a node to view its properties')
  })

  test('renames without changing node or edge identity and refuses a duplicate name', async ({ page }) => {
    const source = node(page, SOURCE_ID)
    await source.click()
    const panel = await openNodesPanel(page)
    const original = await fetchDraft(page, workflowName)

    await panel.locator('.node-name').dblclick()
    const nameInput = panel.locator('.name-input')
    await nameInput.fill('Renamed source α')
    await waitForAcceptedEdit(page, workflowName, () => nameInput.press('Enter'))
    await expect(source.locator('.node-name')).toHaveText('Renamed source α')
    await expect(page.locator(`.vue-flow__edge[data-id="${EDGE_ID}"]`)).toHaveCount(1)
    await expectAcceptedDraft(page, workflowName, (draft) => ({
      valid: draft.validation.valid,
      source: draft.graph.nodes.find(graphNode => graphNode.id === SOURCE_ID)?.name,
      nodeIds: draft.graph.nodes.map(graphNode => graphNode.id),
      edge: draft.graph.edges[0],
    }), {
      valid: true,
      source: 'Renamed source α',
      nodeIds: [SOURCE_ID, TARGET_ID],
      edge: original.graph.edges[0],
    })

    const acceptedRename = await fetchDraft(page, workflowName)
    await panel.locator('.node-name').dblclick()
    await nameInput.fill('Target node')
    await nameInput.press('Enter')
    await expect(panel.getByTestId('node-name-error')).toHaveText('A node named “Target node” already exists.')
    await expect(nameInput).toHaveValue('Target node')
    await expect(source.locator('.node-name')).toHaveText('Renamed source α')
    await expectAcceptedDraft(page, workflowName, draft => ({
      revision: draft.draft_revision,
      source: draft.graph.nodes.find(graphNode => graphNode.id === SOURCE_ID)?.name,
      edge: draft.graph.edges[0],
    }), {
      revision: acceptedRename.draft_revision,
      source: 'Renamed source α',
      edge: acceptedRename.graph.edges[0],
    })

    await page.reload()
    await expect(source.locator('.node-name')).toHaveText('Renamed source α')
    await expect(page.locator(`.vue-flow__edge[data-id="${EDGE_ID}"]`)).toHaveCount(1)
  })

  test('persists collapse and the single-node enabled toggle across reload', async ({ page }) => {
    const source = node(page, SOURCE_ID)
    await expect(source.locator('.node-body')).toBeVisible()
    await waitForAcceptedEdit(page, workflowName, () => source.locator('.node-header').dblclick())
    await expect(source.locator('.tool-node')).toHaveClass(/collapsed/)
    await expect(source.locator('.node-body')).toBeHidden()

    await source.click()
    const panel = await openNodesPanel(page)
    await waitForAcceptedEdit(page, workflowName, () => panel.getByTestId('node-enabled-toggle').click())
    await expect(source.locator('.tool-node')).toHaveClass(/disabled/)
    await expectAcceptedDraft(page, workflowName, (draft) => {
      const graphNode = draft.graph.nodes.find(candidate => candidate.id === SOURCE_ID)
      return { valid: draft.validation.valid, collapsed: graphNode?.collapsed, enabled: graphNode?.enabled }
    }, { valid: true, collapsed: true, enabled: false })

    await page.reload()
    await expect(source.locator('.tool-node')).toHaveClass(/collapsed/)
    await expect(source.locator('.tool-node')).toHaveClass(/disabled/)
    await expect(source.locator('.node-body')).toBeHidden()
  })
})
