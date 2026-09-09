import { test, expect } from '@playwright/test'
import type { Locator, Page } from '@playwright/test'
import type { WorkflowDraftResponse } from '../../src/api/workflowDrafts'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

type ToolMetadata = {
  name: string
  display_name: string
  package: string
  package_version: string
  tool_type: string
  accepts_upstream?: boolean
  inputs: Record<string, { type: string; required?: boolean; connectable?: string }>
  outputs: Record<string, { type: string }>
}

async function seedTools(page: Page) {
  const response = await page.request.post(`${API_BASE}/api/v1/dev/seed`)
  expect(response.ok()).toBeTruthy()
}

async function seedNumbersTool(page: Page): Promise<ToolMetadata> {
  const response = await page.request.get(`${API_BASE}/api/v1/tools`)
  expect(response.ok()).toBeTruthy()
  const tools = (await response.json()) as ToolMetadata[]
  const tool = tools.find((candidate) => candidate.name === 'SeedNumbers')
  expect(tool, 'expected the named SeedNumbers development tool').toBeTruthy()
  expect(tool).toMatchObject({
    name: 'SeedNumbers',
    display_name: 'Seed Numbers',
    package: 'bioimageflow-dev-seed',
    package_version: '0.1.0',
    tool_type: 'DataFrameTool',
    accepts_upstream: false,
    inputs: {},
    outputs: {
      number: { type: 'int' },
      label: { type: 'str' },
    },
  })
  return tool
}

async function waitForToolsRequest(page: Page) {
  const toolsResponse = page.waitForResponse(
    (resp) => resp.url().includes('/api/v1/tools') && resp.status() === 200,
  )
  await page.goto('/')
  await toolsResponse
  await expect(page.locator('#bioimageflow-app')).toBeVisible()
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

async function createEditableWorkflow(page: Page): Promise<string> {
  const displayName = `Canvas Interactions ${Date.now()} ${Math.floor(Math.random() * 10000)}`
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: 'New', exact: true }).click()
  await page.getByTestId('workflow-display-name-input').fill(displayName)
  await page.getByTestId('workflow-dialog-submit').click()
  await expect(page.getByTestId('workflow-title')).toContainText(displayName)
  return deriveWorkflowId(displayName)
}

async function seedNumbersRow(page: Page) {
  const source = await seedNumbersTool(page)
  await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
  await page.locator('[data-testid="tool-search"]').fill(source.name)
  const tool = page.getByTestId(`tool-item-${source.name}`)
  await expect(tool).toBeVisible({ timeout: 5000 })
  await expect(tool.locator('.tool-list-name')).toHaveText(source.display_name)
  return tool
}

async function addToolNode(
  page: Page,
  toolName: string,
  position: { x: number; y: number },
) {
  await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
  await page.getByTestId('tool-search').fill(toolName)
  const tool = page.getByTestId(`tool-item-${toolName}`)
  await expect(tool).toBeVisible({ timeout: 5000 })
  const canvas = page.locator('.vue-flow')
  // dragTo presses on the source before waiting for its destination.
  // Startup can still be mounting the canvas while the tool list is visible.
  await expect(canvas).toBeVisible()
  const nodeCount = await page.locator('.vue-flow__node').count()
  await tool.dragTo(canvas, { targetPosition: position })
  const node = page.locator('.vue-flow__node').nth(nodeCount)
  await expect(node).toBeVisible({ timeout: 5000 })
  return node
}

async function connectDataFrames(page: Page, source: Locator, target: Locator) {
  const sourceHandle = source.locator('.header-outputs .vue-flow__handle')
  const targetHandle = target.locator('.header-inputs .vue-flow__handle').last()
  const sourceBox = await sourceHandle.boundingBox()
  const targetBox = await targetHandle.boundingBox()
  expect(sourceBox).not.toBeNull()
  expect(targetBox).not.toBeNull()
  await page.mouse.move(sourceBox!.x + sourceBox!.width / 2, sourceBox!.y + sourceBox!.height / 2)
  await page.mouse.down()
  await page.mouse.move(targetBox!.x + targetBox!.width / 2, targetBox!.y + targetBox!.height / 2, { steps: 8 })
  await page.mouse.up()
}

async function moveNode(page: Page, node: Locator, delta: { x: number; y: number }) {
  const box = await node.boundingBox()
  expect(box).not.toBeNull()
  const draftResponse = page.waitForResponse(
    (resp) =>
      resp.url().includes('/api/v1/workflow-drafts/') &&
      resp.request().method() === 'PUT' &&
      resp.status() === 200,
  )
  const start = {
    x: box!.x + box!.width / 2,
    y: box!.y + Math.min(24, box!.height / 2),
  }
  await page.mouse.move(start.x, start.y)
  await page.mouse.down()
  await page.mouse.move(start.x + delta.x, start.y + delta.y, { steps: 8 })
  await page.mouse.up()
  await draftResponse
}

async function expectNodeNear(
  node: Locator,
  expected: { x: number; y: number },
) {
  await expect.poll(async () => {
    const box = await node.boundingBox()
    return box !== null
      && Math.abs(box.x - expected.x) <= 10
      && Math.abs(box.y - expected.y) <= 10
  }).toBe(true)
}

test.describe('Canvas interactions', () => {
  test.describe.configure({ mode: 'serial' })
  let workflowName: string

  test.beforeEach(async ({ page }) => {
    await seedTools(page)
    await waitForToolsRequest(page)
    workflowName = await createEditableWorkflow(page)
  })

  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== testInfo.expectedStatus) {
      await testInfo.attach('canvas-before-cleanup', {
        body: await page.screenshot(),
        contentType: 'image/png',
      })
      await testInfo.attach('page-before-cleanup', {
        body: await page.locator('body').ariaSnapshot(),
        contentType: 'text/plain',
      })
    }
    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`).catch(() => undefined)
  })

  test('clicks a named catalog tool and persists an interactive node with panel and pins', { tag: '@critical' }, async ({ page }) => {
    const tool = await seedNumbersRow(page)
    await expect(page.locator('.vue-flow')).toBeVisible()
    const transformationPane = page.locator('.vue-flow__transformationpane')
    const initialTransform = await transformationPane.evaluate(
      element => window.getComputedStyle(element).transform,
    )
    const draftResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes('/api/v1/workflow-drafts/') &&
        resp.request().method() === 'PUT' &&
        resp.status() === 200,
    )
    await tool.click()
    expect((await draftResponse).status()).toBe(200)

    const node = page.locator('.vue-flow__node')
    await expect(node).toHaveCount(1)
    await expect(node).toBeVisible({ timeout: 5000 })
    await expect.poll(() => transformationPane.evaluate(
      element => window.getComputedStyle(element).transform,
    )).toBe(initialTransform)
    await expect(node.locator('.header-inputs .vue-flow__handle')).toHaveCount(0)
    await expect(node.locator('.header-outputs .vue-flow__handle')).toHaveCount(1)
    await expect(node.locator('.header-outputs .pin-label')).toHaveText('DataFrame')
    await expect(node.locator('.body-inputs .vue-flow__handle')).toHaveCount(0)
    await expect(node.locator('.body-outputs .pin-label')).toHaveText(['number', 'label'])

    await node.click()
    await expect(node).toHaveClass(/selected/)

    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const nodePanel = page.locator('[data-testid="panel-nodePanel"]')
    await expect(nodePanel).toBeVisible()
    await expect(nodePanel.locator('.node-name')).toHaveText('Seed Numbers 1')
    await expect(nodePanel.locator('.tool-name')).toHaveText('SeedNumbers')
    await expect(nodePanel.locator('.package-info')).toHaveText('bioimageflow-dev-seed v0.1.0')

    await expect.poll(async () => {
      const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`)
      expect(response.ok()).toBeTruthy()
      const draft: WorkflowDraftResponse = await response.json()
      return {
        validation: draft.validation,
        nodes: draft.graph.nodes.map(node => ({
          type: node.type,
          name: node.name,
          tool_name: node.type === 'tool' ? node.tool_name : undefined,
          parameters: node.type === 'tool' ? node.parameters : undefined,
        })),
      }
    }).toMatchObject({
      validation: { valid: true, errors: [] },
      nodes: [{ type: 'tool', name: 'Seed Numbers 1', tool_name: 'SeedNumbers', parameters: {} }],
    })
  })

  test('drags a named catalog tool to the requested canvas position', async ({ page }) => {
    const tool = await seedNumbersRow(page)
    const draftResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes('/api/v1/workflow-drafts/') &&
        resp.request().method() === 'PUT' &&
        resp.status() === 200,
    )
    await tool.dragTo(page.locator('.vue-flow'), {
      targetPosition: { x: 260, y: 180 },
    })
    expect((await draftResponse).status()).toBe(200)

    const node = page.locator('.vue-flow__node')
    await expect(node).toHaveCount(1)
    await expect(node).toBeVisible({ timeout: 5000 })
    await expect.poll(async () => {
      const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`)
      expect(response.ok()).toBeTruthy()
      const draft: WorkflowDraftResponse = await response.json()
      const created = draft.graph.nodes[0]
      return {
        validation: draft.validation,
        nodeCount: draft.graph.nodes.length,
        toolName: created?.type === 'tool' ? created.tool_name : undefined,
        position: created?.position,
      }
    }).toMatchObject({
      validation: { valid: true, errors: [] },
      nodeCount: 1,
      toolName: 'SeedNumbers',
      position: [260, 180],
    })
  })

  test('new dynamic tools connect cleanly and expose their resolved columns', async ({ page }) => {
    // Execution policy is fixture setup; the journey below creates the nodes and edge in the GUI.
    await page.goto('about:blank')
    const initialResponse = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`)
    expect(initialResponse.ok()).toBeTruthy()
    const initial: WorkflowDraftResponse = await initialResponse.json()
    const configured = await page.request.put(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`, {
      data: {
        expected_revision: initial.draft_revision,
        updated_by: 'frontend',
        graph: { ...initial.graph, config: { ...initial.graph.config, engine: 'wetlands', execution: 'sequential' } },
      },
    })
    expect(configured.ok()).toBeTruthy()
    await page.goto('/')
    await expect(page.getByTestId('workflow-title')).toContainText(initial.graph.display_name)
    const generate = await addToolNode(page, 'Generate', { x: 220, y: 180 })
    const crossJoin = await addToolNode(page, 'CrossJoin', { x: 520, y: 180 })

    await generate.click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const nodePanel = page.getByTestId('panel-nodePanel')
    const columnNameRow = nodePanel.locator('.param-row').filter({ hasText: 'column_name' })
    await columnNameRow.locator('input').fill('sensitivity')
    await nodePanel.getByTestId('list-input-values').fill('[0.1, 0.2]')
    await nodePanel.getByTestId('list-input-values').press('Tab')
    await expect(nodePanel.locator('.list-input-error')).toHaveCount(0)
    await expect(generate.locator('.body-inputs .vue-flow__handle')).toHaveCount(0)

    await connectDataFrames(page, generate, crossJoin)

    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)
    await expect(page.locator('.vue-flow__connection')).toHaveCount(0)
    await expect(crossJoin.locator('.body-outputs .pin-label')).toContainText('sensitivity', {
      timeout: 5000,
    })

    const sourceId = await generate.getAttribute('data-id')
    const targetId = await crossJoin.getAttribute('data-id')
    expect(sourceId).toBeTruthy()
    expect(targetId).toBeTruthy()
    await expect.poll(async () => {
      const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`)
      expect(response.ok()).toBeTruthy()
      const draft: WorkflowDraftResponse = await response.json()
      return {
        validation: draft.validation,
        config: { engine: draft.graph.config.engine, execution: draft.graph.config.execution },
        edges: draft.graph.edges.map(({ id: _id, ...edge }) => edge),
      }
    }).toMatchObject({
      validation: { valid: true, errors: [] },
      config: { engine: 'wetlands', execution: 'sequential' },
      edges: [{ type: 'dataframe', source_node: sourceId, target_node: targetId, target_position: 0 }],
    })

    const runResponse = page.waitForResponse(response =>
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST',
    )
    await page.getByTestId('run-workflow-button').click()
    expect((await runResponse).status()).toBe(202)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete', { timeout: 30000 })
    const result = await page.request.post(`${API_BASE}/api/v1/nodes/${targetId}/data/query`, {
      data: { workflow_name: workflowName },
    })
    expect(result.ok()).toBeTruthy()
    expect(await result.json()).toMatchObject({
      columns: ['sensitivity'],
      rows: [{ sensitivity: 0.1 }, { sensitivity: 0.2 }],
      total_rows: 2,
    })
  })

  test('repeated undo returns moved nodes to the loaded workflow baseline', async ({ page }) => {
    await addToolNode(page, 'Generate', { x: 220, y: 180 })
    await addToolNode(page, 'Generate', { x: 520, y: 260 })
    const saveResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes(`/api/v1/workflows/${workflowName}`) &&
        resp.request().method() === 'PUT' &&
        resp.status() === 200,
    )
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await saveResponse

    await page.reload()
    await expect(page.getByTestId('workflow-title')).toBeVisible()
    const nodes = page.locator('.vue-flow__node')
    await expect(nodes).toHaveCount(2)
    const first = nodes.nth(0)
    const second = nodes.nth(1)
    const firstInitial = await first.boundingBox()
    const secondInitial = await second.boundingBox()
    expect(firstInitial).not.toBeNull()
    expect(secondInitial).not.toBeNull()

    await moveNode(page, first, { x: 70, y: 45 })
    await moveNode(page, second, { x: -55, y: 65 })

    await page.locator('.canvas-view').press('Control+z')
    await expect(nodes).toHaveCount(2)
    await expectNodeNear(second, secondInitial!)

    await page.locator('.canvas-view').press('Control+z')
    await expect(nodes).toHaveCount(2)
    await expectNodeNear(first, firstInitial!)
    await expectNodeNear(second, secondInitial!)

    await page.locator('.canvas-view').press('Control+Shift+z')
    await page.locator('.canvas-view').press('Control+Shift+z')
    await expect(nodes).toHaveCount(2)
  })
})
