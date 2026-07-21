import { test, expect } from '@playwright/test'
import type { Locator, Page } from '@playwright/test'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

type ToolMetadata = {
  name: string
  display_name: string
  tool_type: string
  accepts_upstream?: boolean
  inputs: Record<string, { required?: boolean }>
}

async function seedTools(page: Page) {
  const response = await page.request.post(`${API_BASE}/api/v1/dev/seed`)
  expect(response.ok()).toBeTruthy()
}

async function panelTool(page: Page): Promise<ToolMetadata> {
  const response = await page.request.get(`${API_BASE}/api/v1/tools`)
  expect(response.ok()).toBeTruthy()
  const tools = (await response.json()) as ToolMetadata[]
  const tool =
    tools.find((candidate) => candidate.name === 'SeedNumbers') ??
    tools.find((candidate) => candidate.name === 'GaussianBlur') ??
    tools[0]
  expect(tool, 'expected at least one tool in the backend registry').toBeTruthy()
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

async function addSeedNumbersNode(page: Page) {
  const source = await panelTool(page)
  await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
  await page.locator('[data-testid="tool-search"]').fill(source.name)
  const tool = page.getByTestId(`tool-item-${source.name}`)
  await expect(tool).toBeVisible({ timeout: 5000 })
  const draftResponse = page.waitForResponse(
    (resp) =>
      resp.url().includes('/api/v1/workflow-drafts/') &&
      resp.request().method() === 'PUT' &&
      resp.status() === 200,
  )
  await tool.dragTo(page.locator('.vue-flow'), {
    targetPosition: { x: 260, y: 180 },
  })
  const response = await draftResponse
  const node = page.locator('.vue-flow__node').first()
  await expect(node).toBeVisible({ timeout: 5000 })
  return { node, tool: source, response }
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
  const nodeCount = await page.locator('.vue-flow__node').count()
  await tool.dragTo(page.locator('.vue-flow'), { targetPosition: position })
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

test.describe('Canvas interactions', () => {
  test.describe.configure({ mode: 'serial' })
  let workflowName: string

  test.beforeEach(async ({ page }) => {
    await seedTools(page)
    await waitForToolsRequest(page)
    workflowName = await createEditableWorkflow(page)
  })

  test.afterEach(async ({ page }) => {
    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`).catch(() => undefined)
  })

  test('loads a tool and persists an interactive node with panel and pins', { tag: '@critical' }, async ({ page }) => {
    const { node, tool, response } = await addSeedNumbersNode(page)
    expect(response.status()).toBe(200)
    await expect(
      page.getByTestId(`tool-item-${tool.name}`).locator('.tool-list-name'),
    ).toContainText(tool.display_name)

    await node.click()
    await expect(node).toHaveClass(/selected/)
    await expect(node.locator('.pin-dot')).toHaveCount(0)
    expect(await node.locator('.pin-handle').count()).toBeGreaterThan(0)

    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const nodePanel = page.locator('[data-testid="panel-nodePanel"]')
    await expect(nodePanel).toBeVisible()
    await expect(nodePanel.locator('.node-name')).toBeVisible({ timeout: 3000 })
  })

  test('new dynamic tools connect cleanly and expose their resolved columns', async ({ page }) => {
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

    await connectDataFrames(page, generate, crossJoin)

    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)
    await expect(page.locator('.vue-flow__connection')).toHaveCount(0)
    await expect(crossJoin.locator('.body-outputs .pin-label')).toContainText('sensitivity', {
      timeout: 5000,
    })
    await expect(nodePanel.locator('.list-input-error')).toHaveCount(0)
  })
})
