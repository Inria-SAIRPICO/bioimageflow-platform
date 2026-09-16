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
    config: { engine: 'direct', execution: 'sequential' },
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

async function dragPointer(page: Page, source: Locator, target: { x: number, y: number }): Promise<void> {
  const sourceBox = await source.boundingBox()
  expect(sourceBox).not.toBeNull()
  await page.mouse.move(
    sourceBox!.x + sourceBox!.width / 2,
    sourceBox!.y + sourceBox!.height / 2,
  )
  await page.mouse.down()
  await page.mouse.move(target.x, target.y, { steps: 8 })
  await page.mouse.up()
}

async function connectDataframes(page: Page): Promise<void> {
  const sourceHandle = node(page, SOURCE_ID).locator('.header-outputs .vue-flow__handle')
  const targetHandle = node(page, TARGET_ID).locator('.header-inputs .vue-flow__handle').last()
  const targetBox = await targetHandle.boundingBox()
  expect(targetBox).not.toBeNull()
  await dragPointer(page, sourceHandle, {
    x: targetBox!.x + targetBox!.width / 2,
    y: targetBox!.y + targetBox!.height / 2,
  })
}

async function disconnectDataframeToCanvas(page: Page): Promise<void> {
  const targetHandle = node(page, TARGET_ID).locator('.header-inputs .vue-flow__handle').first()
  const canvasBox = await page.locator('.vue-flow').boundingBox()
  expect(canvasBox).not.toBeNull()
  await dragPointer(page, targetHandle, {
    x: canvasBox!.x + 30,
    y: canvasBox!.y + canvasBox!.height - 30,
  })
}

async function openNodesPanel(page: Page): Promise<Locator> {
  await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
  const panel = page.getByTestId('panel-nodePanel')
  await expect(panel).toBeVisible()
  return panel
}

async function addSeedNodeFromCatalog(page: Page, workflowName: string): Promise<string> {
  await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
  await page.getByTestId('tool-search').fill('SeedNumbers')
  const tool = page.getByTestId('tool-item-SeedNumbers')
  await expect(tool).toBeVisible()
  const canvas = page.locator('.vue-flow')
  const canvasBox = await canvas.boundingBox()
  expect(canvasBox).not.toBeNull()
  await waitForAcceptedEdit(page, workflowName, () => tool.dragTo(canvas, {
    targetPosition: { x: canvasBox!.width / 2, y: canvasBox!.height - 60 },
  }))
  const draft = await fetchDraft(page, workflowName)
  const added = draft.graph.nodes.find(graphNode => (
    graphNode.id !== SOURCE_ID && graphNode.id !== TARGET_ID
  ))
  expect(added).toBeDefined()
  await expect(node(page, added!.id)).toBeVisible()
  return added!.id
}

async function pressCanvasShortcut(page: Page, shortcut: string): Promise<void> {
  await page.locator('.vue-flow__pane').click({ position: { x: 20, y: 20 } })
  await page.keyboard.press(shortcut)
}

async function boxSelectNodes(page: Page, nodeIds: string[]): Promise<void> {
  const boxes = await Promise.all(nodeIds.map(async id => {
    const box = await node(page, id).boundingBox()
    expect(box).not.toBeNull()
    return box!
  }))
  const start = {
    x: Math.min(...boxes.map(box => box.x)) - 20,
    y: Math.min(...boxes.map(box => box.y)) - 20,
  }
  const end = {
    x: Math.max(...boxes.map(box => box.x + box.width)) + 20,
    y: Math.max(...boxes.map(box => box.y + box.height)) + 20,
  }
  await page.keyboard.down('Shift')
  await page.mouse.move(start.x, start.y)
  await page.mouse.down()
  await page.mouse.move(end.x, end.y, { steps: 12 })
  await page.mouse.up()
  await page.keyboard.up('Shift')
}

async function openWorkflowFromPanel(page: Page, workflowName: string): Promise<void> {
  await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).first().click()
  await page.getByTestId('workflow-search').fill(workflowName)
  const row = page.getByTestId(`workflow-row-${workflowName}`)
  await expect(row).toBeVisible()
  await row.dblclick()
  await expect(page.getByTestId('workflow-title')).toHaveText(workflowName)
}

async function expectUndoDisabled(page: Page): Promise<void> {
  await page.getByRole('menuitem', { name: 'Edit', exact: true }).click()
  await expect(page.getByRole('menuitem', { name: 'Undo', exact: true })).toBeDisabled()
  await page.keyboard.press('Escape')
}

async function closeWorkflowTab(
  page: Page,
  workflowName: string,
  saveChanges = false,
): Promise<void> {
  const tab = page.getByTestId('canvas-tab').filter({ hasText: workflowName })
  await tab.getByTestId('canvas-tab-close').click()
  if (saveChanges) {
    await expect(page.getByTestId('root-workflow-close-dialog')).toBeVisible()
    await page.getByTestId('root-workflow-close-save').click()
  }
  await expect(tab).not.toBeVisible()
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

    await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+z'))
    await expect(source.locator('.tool-node')).not.toHaveClass(/disabled/)
    await expect(target.locator('.tool-node')).not.toHaveClass(/disabled/)
    await expectAcceptedDraft(
      page,
      workflowName,
      draft => draft.graph.nodes.map(graphNode => graphNode.enabled),
      [true, true],
    )

    await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+Shift+z'))
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

  test('box-selects and atomically deletes nodes with their incident edge', async ({ page }) => {
    const inactiveWorkflowName = `${workflowName}_inactive`
    const inactiveGraph = editingGraph(inactiveWorkflowName)
    const created = await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name: inactiveWorkflowName, display_name: inactiveWorkflowName },
    })
    expect(created.status()).toBe(201)
    expect((await page.request.put(`${API_BASE}/api/v1/workflows/${inactiveWorkflowName}`, {
      data: { graph: inactiveGraph },
    })).ok()).toBeTruthy()

    try {
      const baseline = await fetchDraft(page, workflowName)
      const inactiveBaseline = await page.request.get(
        `${API_BASE}/api/v1/workflows/${inactiveWorkflowName}`,
      )
      expect(inactiveBaseline.ok()).toBeTruthy()
      const inactiveDocument = await inactiveBaseline.json()

      await boxSelectNodes(page, [SOURCE_ID, TARGET_ID])
      await expect(node(page, SOURCE_ID)).toHaveClass(/selected/)
      await expect(node(page, TARGET_ID)).toHaveClass(/selected/)
      const panel = await openNodesPanel(page)
      await expect(panel.locator('.multi-select')).toContainText('2 nodes selected')

      await panel.getByTestId('bulk-delete-nodes').click()
      await expect(page.getByTestId('node-destructive-dialog')).toBeVisible()
      await page.getByTestId('node-destructive-cancel').click()
      await expect(page.getByTestId('node-destructive-dialog')).not.toBeVisible()
      const afterCancel = await fetchDraft(page, workflowName)
      expect(afterCancel.draft_revision).toBe(baseline.draft_revision)
      expect(afterCancel.graph).toEqual(baseline.graph)

      await panel.getByTestId('bulk-delete-nodes').click()
      await waitForAcceptedEdit(page, workflowName, () => (
        page.getByTestId('node-destructive-confirm').click()
      ))
      await expect(page.locator('.vue-flow__node')).toHaveCount(0)
      await expect(page.locator('.vue-flow__edge')).toHaveCount(0)
      const deleted = await fetchDraft(page, workflowName)
      expect(deleted.draft_revision).toBe(baseline.draft_revision + 1)
      expect(deleted.graph.nodes).toEqual([])
      expect(deleted.graph.edges).toEqual([])
      expect(deleted.validation).toMatchObject({ valid: true, errors: [] })

      await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+z'))
      const restored = await fetchDraft(page, workflowName)
      expect(restored.draft_revision).toBe(deleted.draft_revision + 1)
      expect(restored.graph).toEqual(baseline.graph)
      await expect(page.locator(`.vue-flow__edge[data-id="${EDGE_ID}"]`)).toHaveCount(1)

      await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+Shift+z'))
      const redone = await fetchDraft(page, workflowName)
      expect(redone.draft_revision).toBe(restored.draft_revision + 1)
      expect(redone.graph.nodes).toEqual([])
      expect(redone.graph.edges).toEqual([])

      await page.reload()
      await expect(page.locator('.vue-flow__node')).toHaveCount(0)
      expect((await fetchDraft(page, workflowName)).graph).toEqual(redone.graph)
      const inactiveAfter = await page.request.get(
        `${API_BASE}/api/v1/workflows/${inactiveWorkflowName}`,
      )
      expect(await inactiveAfter.json()).toEqual(inactiveDocument)
    } finally {
      await page.request.delete(`${API_BASE}/api/v1/workflows/${inactiveWorkflowName}`).catch(() => undefined)
    }
  })

  test('clears selected outputs only after confirmation without mutating the graph', async ({ page }) => {
    const runResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run')
      && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-workflow-button').click()
    expect((await runResponse).status()).toBe(202)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText(
      'Execution complete',
      { timeout: 30000 },
    )
    const resultBefore = await page.request.post(
      `${API_BASE}/api/v1/nodes/${TARGET_ID}/data/query`,
      { data: { workflow_name: workflowName } },
    )
    expect(resultBefore.ok()).toBeTruthy()

    await node(page, SOURCE_ID).click()
    await node(page, TARGET_ID).click({ modifiers: ['Shift'] })
    const panel = await openNodesPanel(page)
    const baseline = await fetchDraft(page, workflowName)

    await panel.getByTestId('bulk-clear-node-outputs').click()
    await page.getByTestId('node-destructive-cancel').click()
    const afterCancel = await fetchDraft(page, workflowName)
    expect(afterCancel.draft_revision).toBe(baseline.draft_revision)
    expect(afterCancel.graph).toEqual(baseline.graph)
    expect((await page.request.post(
      `${API_BASE}/api/v1/nodes/${TARGET_ID}/data/query`,
      { data: { workflow_name: workflowName } },
    )).ok()).toBeTruthy()

    const clearResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/clear')
      && response.request().method() === 'POST'
    ))
    await panel.getByTestId('bulk-clear-node-outputs').click()
    await page.getByTestId('node-destructive-confirm').click()
    expect((await clearResponse).status()).toBe(200)
    await expect(page.getByTestId('node-destructive-dialog')).not.toBeVisible()
    const afterClear = await fetchDraft(page, workflowName)
    expect(afterClear.draft_revision).toBe(baseline.draft_revision)
    expect(afterClear.graph).toEqual(baseline.graph)
    expect((await page.request.post(
      `${API_BASE}/api/v1/nodes/${TARGET_ID}/data/query`,
      { data: { workflow_name: workflowName } },
    )).status()).toBe(404)

    await page.reload()
    expect((await fetchDraft(page, workflowName)).graph).toEqual(baseline.graph)
    expect((await page.request.post(
      `${API_BASE}/api/v1/nodes/${TARGET_ID}/data/query`,
      { data: { workflow_name: workflowName } },
    )).status()).toBe(404)
  })

  test('clearing an upstream result stales its dependent and rerun restores current rows', async ({ page }) => {
    const runResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run')
      && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-workflow-button').click()
    expect((await runResponse).status()).toBe(202)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete', { timeout: 30000 })

    const query = async (id: string) => page.request.post(
      `${API_BASE}/api/v1/nodes/${id}/data/query`,
      { data: { workflow_name: workflowName } },
    )
    const originalSource = await query(SOURCE_ID)
    const originalTarget = await query(TARGET_ID)
    expect(originalSource.ok()).toBeTruthy()
    expect(originalTarget.ok()).toBeTruthy()
    expect(await originalTarget.json()).toMatchObject({
      rows: [
        { number: 1, label: 'one', number_plus_one: 2 },
        { number: 2, label: 'two', number_plus_one: 3 },
        { number: 3, label: 'three', number_plus_one: 4 },
      ],
      total_rows: 3,
    })

    await node(page, SOURCE_ID).click()
    const panel = await openNodesPanel(page)
    const baseline = await fetchDraft(page, workflowName)
    const clearResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/clear')
      && response.request().method() === 'POST'
    ))
    await panel.getByTestId('clear-node-outputs').click()
    await page.getByTestId('node-destructive-confirm').click()
    const cleared = await clearResponse
    expect(cleared.status()).toBe(200)
    expect(await cleared.json()).toMatchObject({
      node_statuses: {
        [SOURCE_ID]: { status: 'unexecuted', cached: false },
        [TARGET_ID]: { status: 'out_of_date', cached: false },
      },
    })
    await expect(node(page, SOURCE_ID).locator('.status-indicator')).toHaveClass(/status-unexecuted/)
    await expect(node(page, TARGET_ID).locator('.status-indicator')).toHaveClass(/status-out-of-date/)
    expect((await fetchDraft(page, workflowName)).draft_revision).toBe(baseline.draft_revision)
    expect((await fetchDraft(page, workflowName)).graph).toEqual(baseline.graph)
    expect((await query(SOURCE_ID)).status()).toBe(404)
    expect((await query(TARGET_ID)).ok()).toBeTruthy()

    await page.reload()
    await expect(node(page, SOURCE_ID).locator('.status-indicator')).toHaveClass(/status-unexecuted/)
    await expect(node(page, TARGET_ID).locator('.status-indicator')).toHaveClass(/status-out-of-date/)
    expect((await fetchDraft(page, workflowName)).draft_revision).toBe(baseline.draft_revision)
    expect((await fetchDraft(page, workflowName)).graph).toEqual(baseline.graph)
    expect((await query(SOURCE_ID)).status()).toBe(404)
    expect((await query(TARGET_ID)).ok()).toBeTruthy()

    const rerun = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run')
      && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-workflow-button').click()
    const rebuild = page.getByTestId('out-of-date-confirm')
    await expect(rebuild).toContainText('Rebuild nodes before running?')
    await expect(rebuild.locator('li')).toHaveText([TARGET_ID])
    await page.getByTestId('out-of-date-continue').click()
    const rerunAccepted = await rerun
    expect(rerunAccepted.status()).toBe(202)
    expect(await rerunAccepted.json()).toMatchObject({
      status: 'started',
      workflow_id: workflowName,
      draft_revision: baseline.draft_revision,
      execution_id: expect.any(String),
    })
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete', { timeout: 30000 })
    await expect(node(page, SOURCE_ID).locator('.status-indicator')).toHaveClass(/status-executed/)
    await expect(node(page, TARGET_ID).locator('.status-indicator')).toHaveClass(/status-executed/)
    expect((await query(SOURCE_ID)).ok()).toBeTruthy()
    const restored = await query(TARGET_ID)
    expect(restored.ok()).toBeTruthy()
    expect(await restored.json()).toMatchObject({
      rows: [
        { number: 1, label: 'one', number_plus_one: 2 },
        { number: 2, label: 'two', number_plus_one: 3 },
        { number: 3, label: 'three', number_plus_one: 4 },
      ],
      total_rows: 3,
    })
    expect((await fetchDraft(page, workflowName)).draft_revision).toBe(baseline.draft_revision)
    expect((await fetchDraft(page, workflowName)).graph).toEqual(baseline.graph)
  })

  test('refuses to clear outputs when the pending draft cannot be accepted', async ({ page }) => {
    const runResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run')
      && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-workflow-button').click()
    expect((await runResponse).status()).toBe(202)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText(
      'Execution complete',
      { timeout: 30000 },
    )
    expect((await page.request.post(
      `${API_BASE}/api/v1/nodes/${TARGET_ID}/data/query`,
      { data: { workflow_name: workflowName } },
    )).ok()).toBeTruthy()

    await node(page, TARGET_ID).click()
    const panel = await openNodesPanel(page)
    const baseline = await fetchDraft(page, workflowName)
    let clearRequests = 0
    page.on('request', request => {
      if (
        request.url().endsWith('/api/v1/execution/clear')
        && request.method() === 'POST'
      ) clearRequests += 1
    })
    await page.route(`**/api/v1/workflow-drafts/${workflowName}`, async route => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({ status: 500, json: { detail: 'forced draft persistence failure' } })
      } else {
        await route.continue()
      }
    })

    await panel.locator('.param-number input').fill('2')
    await panel.getByTestId('clear-node-outputs').click()
    await page.getByTestId('node-destructive-confirm').click()
    await expect(page.getByTestId('node-destructive-error')).toBeVisible()
    expect(clearRequests).toBe(0)
    const afterRefusal = await fetchDraft(page, workflowName)
    expect(afterRefusal.draft_revision).toBe(baseline.draft_revision)
    expect(afterRefusal.graph).toEqual(baseline.graph)
    expect((await page.request.post(
      `${API_BASE}/api/v1/nodes/${TARGET_ID}/data/query`,
      { data: { workflow_name: workflowName } },
    )).ok()).toBeTruthy()
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

  test('disconnects and reconnects a DataFrame edge with pointer gestures and persists the accepted graph', async ({ page }) => {
    const baseline = await fetchDraft(page, workflowName)

    await waitForAcceptedEdit(page, workflowName, () => disconnectDataframeToCanvas(page))
    await expect(page.locator('.vue-flow__edge')).toHaveCount(0)
    await expectAcceptedDraft(page, workflowName, draft => ({
      valid: draft.validation.valid,
      nodeIds: draft.graph.nodes.map(graphNode => graphNode.id),
      edges: draft.graph.edges,
    }), {
      valid: true,
      nodeIds: [SOURCE_ID, TARGET_ID],
      edges: [],
    })

    await page.reload()
    await expect(page.locator('.vue-flow__node')).toHaveCount(2)
    await expect(page.locator('.vue-flow__edge')).toHaveCount(0)

    await waitForAcceptedEdit(page, workflowName, () => connectDataframes(page))
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)
    await expectAcceptedDraft(page, workflowName, draft => ({
      valid: draft.validation.valid,
      nodeIds: draft.graph.nodes.map(graphNode => graphNode.id),
      edge: draft.graph.edges[0],
    }), {
      valid: true,
      nodeIds: [SOURCE_ID, TARGET_ID],
      edge: {
        type: 'dataframe',
        id: `e-${SOURCE_ID}-bif:v1:dataframe-output-${TARGET_ID}-bif:v1:dataframe-position:0`,
        source_node: SOURCE_ID,
        target_node: TARGET_ID,
        target_input: null,
        target_position: 0,
      },
    })

    await page.reload()
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)
    const reloaded = await fetchDraft(page, workflowName)
    expect(reloaded.graph.nodes).toEqual(baseline.graph.nodes)
    expect(reloaded.graph.edges).toEqual([{
      type: 'dataframe',
      id: `e-${SOURCE_ID}-bif:v1:dataframe-output-${TARGET_ID}-bif:v1:dataframe-position:0`,
      source_node: SOURCE_ID,
      target_node: TARGET_ID,
      target_input: null,
      target_position: 0,
    }])
  })

  test('refuses a column-to-DataFrame connection without replacing the accepted edge', async ({ page }) => {
    const baseline = await fetchDraft(page, workflowName)
    const columnOutput = node(page, SOURCE_ID).locator('.body-outputs .vue-flow__handle').first()
    const freeDataframeInput = node(page, TARGET_ID).locator('.header-inputs .vue-flow__handle').last()
    await expect(columnOutput).toBeVisible()
    await expect(freeDataframeInput).toBeVisible()
    await expect(node(page, TARGET_ID).locator('.header-inputs .vue-flow__handle')).toHaveCount(2)

    const targetBox = await freeDataframeInput.boundingBox()
    expect(targetBox).not.toBeNull()
    await dragPointer(page, columnOutput, {
      x: targetBox!.x + targetBox!.width / 2,
      y: targetBox!.y + targetBox!.height / 2,
    })

    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)
    await expect(node(page, TARGET_ID).locator('.header-inputs .vue-flow__handle')).toHaveCount(2)
    await page.waitForTimeout(600) // Allow the draft persistence debounce to expose an unintended edit.
    const refused = await fetchDraft(page, workflowName)
    expect(refused.draft_revision).toBe(baseline.draft_revision)
    expect(refused.graph).toEqual(baseline.graph)

    await page.reload()
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)
    const reloaded = await fetchDraft(page, workflowName)
    expect(reloaded.graph).toEqual(baseline.graph)
  })

  test('undoes and redoes mixed node, edge, and parameter edits one action at a time', async ({ page }) => {
    const baseline = await fetchDraft(page, workflowName)
    const addedNodeId = await addSeedNodeFromCatalog(page, workflowName)

    await waitForAcceptedEdit(page, workflowName, () => disconnectDataframeToCanvas(page))
    await node(page, TARGET_ID).click()
    const panel = await openNodesPanel(page)
    const numberInput = panel.locator('.param-number input')
    await expect(numberInput).toHaveValue('1')
    await waitForAcceptedEdit(page, workflowName, async () => {
      await numberInput.fill('7')
      await numberInput.press('Enter')
    })
    await expectAcceptedDraft(page, workflowName, draft => ({
      nodeIds: draft.graph.nodes.map(graphNode => graphNode.id),
      edgeIds: draft.graph.edges.map(edge => edge.id),
      number: draft.graph.nodes.find(graphNode => graphNode.id === TARGET_ID)?.parameters.number,
    }), {
      nodeIds: [SOURCE_ID, TARGET_ID, addedNodeId],
      edgeIds: [],
      number: 7,
    })

    await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+z'))
    await expectAcceptedDraft(page, workflowName, draft => ({
      nodeIds: draft.graph.nodes.map(graphNode => graphNode.id),
      edgeIds: draft.graph.edges.map(edge => edge.id),
      number: draft.graph.nodes.find(graphNode => graphNode.id === TARGET_ID)?.parameters.number,
    }), {
      nodeIds: [SOURCE_ID, TARGET_ID, addedNodeId],
      edgeIds: [],
      number: 1,
    })

    await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+z'))
    await expect(page.locator(`.vue-flow__edge[data-id="${EDGE_ID}"]`)).toHaveCount(1)
    await expectAcceptedDraft(page, workflowName, draft => ({
      nodeIds: draft.graph.nodes.map(graphNode => graphNode.id),
      edge: draft.graph.edges[0],
    }), {
      nodeIds: [SOURCE_ID, TARGET_ID, addedNodeId],
      edge: baseline.graph.edges[0],
    })

    await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+z'))
    await expect(node(page, addedNodeId)).toHaveCount(0)
    await expectAcceptedDraft(page, workflowName, draft => draft.graph, baseline.graph)

    await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+Shift+z'))
    await expect(node(page, addedNodeId)).toBeVisible()
    await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+Shift+z'))
    await expect(page.locator('.vue-flow__edge')).toHaveCount(0)
    await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+Shift+z'))
    await expectAcceptedDraft(page, workflowName, draft => ({
      valid: draft.validation.valid,
      nodeIds: draft.graph.nodes.map(graphNode => graphNode.id),
      edges: draft.graph.edges,
      number: draft.graph.nodes.find(graphNode => graphNode.id === TARGET_ID)?.parameters.number,
    }), {
      valid: true,
      nodeIds: [SOURCE_ID, TARGET_ID, addedNodeId],
      edges: [],
      number: 7,
    })

    const accepted = await fetchDraft(page, workflowName)
    await page.reload()
    await expect(node(page, addedNodeId)).toBeVisible()
    await expect(page.locator('.vue-flow__edge')).toHaveCount(0)
    expect((await fetchDraft(page, workflowName)).graph).toEqual(accepted.graph)
  })

  test('keeps undo history isolated when switching between workflows', async ({ page }) => {
    const secondWorkflowName = `${workflowName}_second`
    const secondGraph = editingGraph(secondWorkflowName)
    const secondTarget = secondGraph.nodes.find(graphNode => graphNode.id === TARGET_ID)
    expect(secondTarget?.type).toBe('tool')
    if (secondTarget?.type === 'tool') secondTarget.parameters.number = 11

    const created = await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name: secondWorkflowName, display_name: secondWorkflowName },
    })
    expect(created.status()).toBe(201)
    const saved = await page.request.put(`${API_BASE}/api/v1/workflows/${secondWorkflowName}`, {
      data: { graph: secondGraph },
    })
    expect(saved.ok()).toBeTruthy()

    try {
      const firstBaseline = await fetchDraft(page, workflowName)
      await node(page, TARGET_ID).click()
      const firstPanel = await openNodesPanel(page)
      const firstNumberInput = firstPanel.locator('.param-number input')
      await waitForAcceptedEdit(page, workflowName, async () => {
        await firstNumberInput.fill('7')
        await firstNumberInput.press('Enter')
      })
      await expectAcceptedDraft(
        page,
        workflowName,
        draft => draft.graph.nodes.find(graphNode => graphNode.id === TARGET_ID)?.parameters.number,
        7,
      )
      const firstEdited = await fetchDraft(page, workflowName)
      expect(firstEdited.graph).not.toEqual(firstBaseline.graph)
      await closeWorkflowTab(page, workflowName, true)

      await openWorkflowFromPanel(page, secondWorkflowName)
      const secondBaseline = await fetchDraft(page, secondWorkflowName)
      expect({
        valid: secondBaseline.validation.valid,
        nodeIds: secondBaseline.graph.nodes.map(graphNode => graphNode.id),
        edgeIds: secondBaseline.graph.edges.map(edge => edge.id),
        number: secondBaseline.graph.nodes.find(graphNode => graphNode.id === TARGET_ID)?.parameters.number,
      }).toEqual({
        valid: true,
        nodeIds: [SOURCE_ID, TARGET_ID],
        edgeIds: [EDGE_ID],
        number: 11,
      })
      await node(page, TARGET_ID).click()
      const secondPanel = await openNodesPanel(page)
      await expect(secondPanel.locator('.param-number input')).toHaveValue('11')

      await expectUndoDisabled(page)
      await pressCanvasShortcut(page, 'Control+z')
      await expectUndoDisabled(page)
      const afterSecondUndo = await fetchDraft(page, secondWorkflowName)
      expect(afterSecondUndo.draft_revision).toBe(secondBaseline.draft_revision)
      expect(afterSecondUndo.graph).toEqual(secondBaseline.graph)

      await closeWorkflowTab(page, secondWorkflowName)
      await openWorkflowFromPanel(page, workflowName)
      const firstReloaded = await fetchDraft(page, workflowName)
      expect(firstReloaded.graph).toEqual(firstEdited.graph)
      await expectUndoDisabled(page)
      await pressCanvasShortcut(page, 'Control+z')
      await expectUndoDisabled(page)
      const afterFirstReloadUndo = await fetchDraft(page, workflowName)
      expect(afterFirstReloadUndo.draft_revision).toBe(firstReloaded.draft_revision)
      expect(afterFirstReloadUndo.graph).toEqual(firstReloaded.graph)
      await page.reload()
      expect((await fetchDraft(page, workflowName)).graph).toEqual(firstEdited.graph)
    } finally {
      await page.request.delete(`${API_BASE}/api/v1/workflows/${secondWorkflowName}`).catch(() => undefined)
    }
  })
})
