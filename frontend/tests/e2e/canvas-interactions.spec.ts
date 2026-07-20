import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

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
})
