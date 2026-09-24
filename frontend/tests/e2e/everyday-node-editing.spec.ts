import { expect, test } from '@playwright/test'
import type { Locator, Page } from '@playwright/test'
import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import type { GraphState } from '../../src/api/types'
import type { WorkflowDraftResponse } from '../../src/api/workflowDrafts'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`
const SOURCE_ID = 'everyday_source'
const TARGET_ID = 'everyday_target'
const EDGE_ID = 'everyday_dataframe_edge'
const E2E_ROOT = process.env.BIOIMAGEFLOW_E2E_ROOT

function selectedRecord(workflowName: string, nodeId: string) {
  expect(E2E_ROOT).toBeTruthy()
  const storageRoot = join(E2E_ROOT!, 'workflows', workflowName, 'results')
  const latestLinkPath = join(storageRoot, 'views', 'latest', `${nodeId}.bioimageflow-link.json`)
  const latestLink = JSON.parse(readFileSync(latestLinkPath, 'utf8')) as {
    kind: string
    target: string
  }
  expect(latestLink.kind).toBe('directory')
  const nodeView = resolve(dirname(latestLinkPath), latestLink.target)
  const result = JSON.parse(readFileSync(join(nodeView, 'result.json'), 'utf8')) as {
    run_id: string
    node_key: string
    result_key: string
    record_id: string
    canonical: string
  }
  expect(result.node_key).toBe(nodeId)
  const recordDir = resolve(nodeView, result.canonical)
  expect(recordDir.startsWith(join(storageRoot, 'cache', 'v1', 'results'))).toBe(true)
  expect(recordDir).toContain(result.record_id)
  return { storageRoot, result, recordDir, currentPath: join(dirname(dirname(recordDir)), 'current.json') }
}

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
    await expect(panel.getByTestId('bulk-enable-nodes')).toBeEnabled()
    await expect(panel.locator('.node-details')).toHaveCount(0)

    const baseline = await fetchDraft(page, workflowName)
    let draftWrites = 0
    const countDraftWrites = (request: import('@playwright/test').Request) => {
      if (request.method() === 'PUT' && request.url().endsWith(`/api/v1/workflow-drafts/${workflowName}`)) {
        draftWrites += 1
      }
    }
    page.on('request', countDraftWrites)
    await expectUndoDisabled(page)
    await panel.getByTestId('bulk-enable-nodes').click()
    await expectUndoDisabled(page)
    const refused = await fetchDraft(page, workflowName)
    expect(refused.draft_revision).toBe(baseline.draft_revision)
    expect(refused.graph).toEqual(baseline.graph)
    expect(draftWrites).toBe(0)
    page.off('request', countDraftWrites)

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

  test('quarantines a corrupt selected record through GUI Clear and reruns exact rows', async ({ page }) => {
    const siblingId = await addSeedNodeFromCatalog(page, workflowName)
    const baseline = await fetchDraft(page, workflowName)
    expect(baseline.graph.nodes.map(item => item.id)).toContain(siblingId)

    const firstRun = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run')
      && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-workflow-button').click()
    const firstAccepted = await firstRun
    expect(firstAccepted.status()).toBe(202)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete', { timeout: 30000 })

    const query = (id: string) => page.request.post(`${API_BASE}/api/v1/nodes/${id}/data/query`, {
      data: { workflow_name: workflowName },
    })
    const expectedRows = [
      { number: 1, label: 'one', number_plus_one: 2 },
      { number: 2, label: 'two', number_plus_one: 3 },
      { number: 3, label: 'three', number_plus_one: 4 },
    ]
    expect(await (await query(TARGET_ID)).json()).toMatchObject({ rows: expectedRows, total_rows: 3 })
    const source = selectedRecord(workflowName, SOURCE_ID)
    const target = selectedRecord(workflowName, TARGET_ID)
    const sibling = selectedRecord(workflowName, siblingId)
    expect(source.result.run_id).toBe(target.result.run_id)
    expect(source.result.run_id).toBe(sibling.result.run_id)
    const historicalRunPath = join(source.storageRoot, 'views', 'runs', source.result.run_id, 'run.json')
    const historicalRun = readFileSync(historicalRunPath)
    const historicalSibling = readFileSync(join(source.storageRoot, 'views', 'runs', source.result.run_id, 'nodes', siblingId, 'result.json'))
    const targetBytes = readFileSync(join(target.recordDir, 'dataframe.parquet'))
    const siblingBytes = readFileSync(join(sibling.recordDir, 'dataframe.parquet'))
    const runViewsBefore = readdirSync(join(source.storageRoot, 'views', 'runs')).sort()
    const retainedBefore = await (await page.request.get(`${API_BASE}/api/v1/execution/status`)).json()

    const corruptBytes = Buffer.from('corrupt selected parquet')
    writeFileSync(join(source.recordDir, 'dataframe.parquet'), corruptBytes)
    writeFileSync(join(source.recordDir, 'dataframe.csv'), 'number,label\n999,stale\n')
    await page.reload()
    const corruptDraft = await fetchDraft(page, workflowName)
    expect(corruptDraft.draft_revision).toBe(baseline.draft_revision)
    expect(corruptDraft.graph).toEqual(baseline.graph)
    expect(corruptDraft.validation).toMatchObject({
      valid: false,
      errors: [{ type: 'cache_corrupt', node: SOURCE_ID }],
      node_statuses: { [SOURCE_ID]: { status: 'failed' }, [siblingId]: { status: 'executed' } },
    })
    await expect(node(page, SOURCE_ID).locator('.status-indicator')).toHaveClass(/status-failed/)
    await expect(node(page, siblingId).locator('.status-indicator')).toHaveClass(/status-executed/)
    await node(page, SOURCE_ID).click()
    const panel = await openNodesPanel(page)
    await expect(panel.getByTestId('node-validation-errors')).toContainText('Record dataframe transport digest mismatch')
    expect((await query(SOURCE_ID)).status()).toBe(409)
    expect((await page.request.get(
      `${API_BASE}/api/v1/nodes/${SOURCE_ID}/data/csv?workflow_name=${workflowName}`,
    )).status()).toBe(409)
    const blocked = await page.request.post(`${API_BASE}/api/v1/execution/run`, {
      data: { workflow_id: workflowName, draft_revision: baseline.draft_revision },
    })
    expect(blocked.status()).toBe(422)
    expect(await blocked.json()).toMatchObject({ errors: [{ type: 'cache_corrupt', node: SOURCE_ID }] })
    await page.getByTestId('run-workflow-button').click()
    await expect(page.getByTestId('out-of-date-confirm')).toContainText('Rebuild nodes before running?')
    await page.getByTestId('out-of-date-continue').click()
    await expect(page.locator('.p-toast')).toContainText('Validation errors')
    expect(readdirSync(join(source.storageRoot, 'views', 'runs')).sort()).toEqual(runViewsBefore)
    expect((await (await page.request.get(`${API_BASE}/api/v1/execution/status`)).json()).last_result).toEqual(retainedBefore.last_result)
    expect(await (await query(TARGET_ID)).json()).toMatchObject({ rows: expectedRows, total_rows: 3 })
    expect((await query(siblingId)).ok()).toBeTruthy()

    const clearResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/clear')
      && response.request().method() === 'POST'
    ))
    await panel.getByTestId('clear-node-outputs').click()
    await page.getByTestId('node-destructive-confirm').click()
    const cleared = await clearResponse
    expect(cleared.status()).toBe(200)
    expect(cleared.request().postDataJSON()).toMatchObject({
      nodes: [SOURCE_ID], workflow_id: workflowName, draft_revision: baseline.draft_revision,
    })
    expect(await cleared.json()).toMatchObject({
      node_statuses: {
        [SOURCE_ID]: { status: 'unexecuted', cached: false },
        [TARGET_ID]: { status: 'out_of_date', cached: false },
      },
    })
    expect((await query(SOURCE_ID)).status()).toBe(404)
    const quarantine = readdirSync(join(dirname(dirname(source.recordDir)), 'quarantine'))
    expect(quarantine).toHaveLength(1)
    expect(quarantine[0]).toMatch(new RegExp(`^${source.result.record_id}\\.`))
    expect(readFileSync(join(dirname(dirname(source.recordDir)), 'quarantine', quarantine[0], 'dataframe.parquet'))).toEqual(corruptBytes)
    expect(readFileSync(join(target.recordDir, 'dataframe.parquet'))).toEqual(targetBytes)
    expect(readFileSync(join(sibling.recordDir, 'dataframe.parquet'))).toEqual(siblingBytes)
    expect(readFileSync(historicalRunPath)).toEqual(historicalRun)
    expect(readFileSync(join(source.storageRoot, 'views', 'runs', source.result.run_id, 'nodes', siblingId, 'result.json'))).toEqual(historicalSibling)
    expect((await (await page.request.get(`${API_BASE}/api/v1/execution/status`)).json()).last_result).toEqual(retainedBefore.last_result)

    await page.reload()
    await expect(node(page, SOURCE_ID).locator('.status-indicator')).toHaveClass(/status-unexecuted/)
    await expect(node(page, TARGET_ID).locator('.status-indicator')).toHaveClass(/status-out-of-date/)
    await expect(node(page, siblingId).locator('.status-indicator')).toHaveClass(/status-executed/)
    const refreshed = await fetchDraft(page, workflowName)
    expect(refreshed.draft_revision).toBe(baseline.draft_revision)
    expect(refreshed.graph).toEqual(baseline.graph)
    expect(refreshed.validation.errors).toEqual([])

    const rerunResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run')
      && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-workflow-button').click()
    await expect(page.getByTestId('out-of-date-confirm')).toContainText('Rebuild nodes before running?')
    await page.getByTestId('out-of-date-continue').click()
    const rerun = await rerunResponse
    expect(rerun.status()).toBe(202)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete', { timeout: 30000 })
    expect(await (await query(TARGET_ID)).json()).toMatchObject({ rows: expectedRows, total_rows: 3 })
    expect((await query(SOURCE_ID)).ok()).toBeTruthy()
    expect((await query(siblingId)).ok()).toBeTruthy()
    expect(readFileSync(historicalRunPath)).toEqual(historicalRun)
    expect(readFileSync(join(sibling.recordDir, 'dataframe.parquet'))).toEqual(siblingBytes)
    expect(selectedRecord(workflowName, SOURCE_ID).result.run_id).not.toBe(source.result.run_id)
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

  test('recovers failed pointer disconnect and connection writes without losing edge identity', async ({ page }) => {
    const baseline = await fetchDraft(page, workflowName)
    const edgeSelector = `.vue-flow__edge[data-id="${EDGE_ID}"]`
    const reconnectedEdge = {
      type: 'dataframe',
      id: `e-${SOURCE_ID}-bif:v1:dataframe-output-${TARGET_ID}-bif:v1:dataframe-position:0`,
      source_node: SOURCE_ID,
      target_node: TARGET_ID,
      target_input: null,
      target_position: 0,
    }
    let failNextWrite = true
    let failedWrites = 0
    await page.route(`**/api/v1/workflow-drafts/${workflowName}`, async route => {
      if (route.request().method() !== 'PUT' || !failNextWrite) return route.continue()
      failNextWrite = false
      failedWrites += 1
      await route.fulfill({ status: 500, json: { detail: 'forced edge persistence failure' } })
    })
    const failedWrite = () => page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${workflowName}`)
      && response.request().method() === 'PUT'
      && response.status() === 500
    ))
    const retry = async () => {
      await waitForAcceptedEdit(page, workflowName, () => page.getByTestId('canvas-persistence-retry').click())
      await expect(page.getByTestId('canvas-persistence-issue')).toHaveCount(0)
    }

    const disconnectFailure = failedWrite()
    await disconnectDataframeToCanvas(page)
    await disconnectFailure
    await expect(page.locator('.vue-flow__edge')).toHaveCount(0)
    await expect(page.getByTestId('canvas-persistence-issue')).toContainText('forced edge persistence failure')
    const refusedDisconnect = await fetchDraft(page, workflowName)
    expect(refusedDisconnect.draft_revision).toBe(baseline.draft_revision)
    expect(refusedDisconnect.graph).toEqual(baseline.graph)
    await retry()
    const disconnected = await fetchDraft(page, workflowName)
    expect(disconnected.draft_revision).toBe(baseline.draft_revision + 1)
    expect(disconnected.graph.nodes).toEqual(baseline.graph.nodes)
    expect(disconnected.graph.edges).toEqual([])
    expect(disconnected.validation.valid).toBe(true)

    await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+z'))
    await expect(page.locator(edgeSelector)).toHaveCount(1)
    expect((await fetchDraft(page, workflowName)).graph.edges).toEqual(baseline.graph.edges)
    await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+Shift+z'))
    await expect(page.locator('.vue-flow__edge')).toHaveCount(0)
    expect((await fetchDraft(page, workflowName)).graph.edges).toEqual([])

    failNextWrite = true
    const connectionFailure = failedWrite()
    await connectDataframes(page)
    await connectionFailure
    await expect(page.locator(`.vue-flow__edge[data-id="${reconnectedEdge.id}"]`)).toHaveCount(1)
    await expect(page.getByTestId('canvas-persistence-issue')).toContainText('forced edge persistence failure')
    const refusedConnection = await fetchDraft(page, workflowName)
    expect(refusedConnection.draft_revision).toBe(disconnected.draft_revision + 2)
    expect(refusedConnection.graph.edges).toEqual([])
    await retry()
    const connected = await fetchDraft(page, workflowName)
    expect(connected.draft_revision).toBe(refusedConnection.draft_revision + 1)
    expect(connected.graph.nodes).toEqual(baseline.graph.nodes)
    expect(connected.graph.edges).toEqual([reconnectedEdge])
    expect(connected.validation.valid).toBe(true)
    expect(failedWrites).toBe(2)

    await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+z'))
    expect((await fetchDraft(page, workflowName)).graph.edges).toEqual([])
    await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+Shift+z'))
    expect((await fetchDraft(page, workflowName)).graph.edges).toEqual([reconnectedEdge])
    await page.reload()
    await expect(page.locator(`.vue-flow__edge[data-id="${reconnectedEdge.id}"]`)).toHaveCount(1)
    expect((await fetchDraft(page, workflowName)).graph.edges).toEqual([reconnectedEdge])
  })

  test('recovers a failed connected column-input disconnect with its label and edge intact', async ({ page }) => {
    const initial = await fetchDraft(page, workflowName)
    const columnEdge = {
      type: 'column' as const,
      id: 'everyday_column_edge',
      source_node: 'image_source',
      source_output: 'output_image',
      target_node: 'image_target',
      target_input: 'input_image',
    }
    const graph: GraphState = {
      ...initial.graph,
      nodes: [{
        type: 'tool', id: 'image_source', name: 'Image source', tool_name: 'GaussianBlur',
        position: [180, 180], parameters: { input_image: '/tmp/e2e-input.tif', sigma: 1 },
        output_templates: { output_image: '' },
      }, {
        type: 'tool', id: 'image_target', name: 'Image target', tool_name: 'GaussianBlur',
        position: [520, 180], parameters: { sigma: 1 },
        output_templates: { output_image: '' },
      }],
      edges: [columnEdge],
    }
    const setup = await page.request.put(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`, {
      data: { graph, expected_revision: initial.draft_revision, updated_by: 'frontend' },
    })
    expect(setup.ok()).toBeTruthy()
    await page.reload()
    const baseline = await fetchDraft(page, workflowName)
    expect(baseline.validation.valid).toBe(true)
    expect(baseline.graph.edges).toEqual([columnEdge])
    const input = node(page, 'image_target').locator('.body-inputs')
    await expect(input.locator('.pin-label')).toHaveText('output_image of Image source')
    await expect(page.locator(`.vue-flow__edge[data-id="${columnEdge.id}"]`)).toHaveCount(1)

    let failedWrites = 0
    await page.route(`**/api/v1/workflow-drafts/${workflowName}`, async route => {
      if (route.request().method() !== 'PUT' || failedWrites > 0) return route.continue()
      failedWrites += 1
      await route.fulfill({ status: 500, json: { detail: 'forced column disconnect failure' } })
    })
    const failedWrite = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${workflowName}`)
      && response.request().method() === 'PUT'
      && response.status() === 500
    ))
    const canvasBox = await page.locator('.vue-flow').boundingBox()
    expect(canvasBox).not.toBeNull()
    await dragPointer(page, input.locator('.vue-flow__handle'), {
      x: canvasBox!.x + 30,
      y: canvasBox!.y + canvasBox!.height - 30,
    })
    await failedWrite
    await expect(page.locator('.vue-flow__edge')).toHaveCount(0)
    await expect(input.locator('.pin-label')).toHaveText('input_image')
    await expect(page.getByTestId('canvas-persistence-issue')).toContainText('forced column disconnect failure')
    const refused = await fetchDraft(page, workflowName)
    expect(refused.draft_revision).toBe(baseline.draft_revision)
    expect(refused.graph).toEqual(baseline.graph)

    await waitForAcceptedEdit(page, workflowName, () => page.getByTestId('canvas-persistence-retry').click())
    await expect(page.getByTestId('canvas-persistence-issue')).toHaveCount(0)
    const disconnected = await fetchDraft(page, workflowName)
    expect(disconnected.draft_revision).toBe(baseline.draft_revision + 1)
    expect(disconnected.graph.nodes).toEqual(baseline.graph.nodes)
    expect(disconnected.graph.edges).toEqual([])
    expect(disconnected.validation.valid).toBe(false)
    expect(failedWrites).toBe(1)
    await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+z'))
    await expect(page.locator(`.vue-flow__edge[data-id="${columnEdge.id}"]`)).toHaveCount(1)
    expect((await fetchDraft(page, workflowName)).graph.edges).toEqual([columnEdge])
    await waitForAcceptedEdit(page, workflowName, () => pressCanvasShortcut(page, 'Control+Shift+z'))
    expect((await fetchDraft(page, workflowName)).graph.edges).toEqual([])
    await page.reload()
    await expect(input.locator('.pin-label')).toContainText('input_image')
    await expect(page.locator('.vue-flow__edge')).toHaveCount(0)
    expect((await fetchDraft(page, workflowName)).graph.edges).toEqual([])
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
