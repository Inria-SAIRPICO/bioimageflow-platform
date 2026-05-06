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

async function addSeedNumbersNode(page: Page) {
  const source = await panelTool(page)
  await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
  await page.locator('[data-testid="tool-search"]').fill(source.name)
  const tool = page.getByTestId(`tool-item-${source.name}`)
  await expect(tool).toBeVisible({ timeout: 5000 })
  const graphResponse = page.waitForResponse(
    (resp) =>
      resp.url().includes('/api/v1/graph') &&
      resp.request().method() === 'PUT' &&
      resp.status() === 200,
  )
  await tool.dragTo(page.locator('.vue-flow'), {
    targetPosition: { x: 260, y: 180 },
  })
  const response = await graphResponse
  const node = page.locator('.vue-flow__node').first()
  await expect(node).toBeVisible({ timeout: 5000 })
  return { node, tool: source, response }
}

test.describe('Canvas interactions', () => {
  test.describe.configure({ mode: 'serial' })

  test.beforeEach(async ({ page }) => {
    await seedTools(page)
    await waitForToolsRequest(page)
  })

  test('seeded tools are loaded in the panel', async ({ page }) => {
    const source = await panelTool(page)
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    await page.locator('[data-testid="tool-search"]').fill(source.name)
    await expect(page.getByTestId(`tool-item-${source.name}`)).toBeVisible({
      timeout: 5000,
    })
    await expect(
      page.getByTestId(`tool-item-${source.name}`).locator('.tool-list-name'),
    ).toContainText(source.display_name)
  })

  test('PUT /graph returns 200', async ({ page }) => {
    const { response } = await addSeedNumbersNode(page)
    expect(response.status()).toBe(200)
  })

  test('selected node has blue border', async ({ page }) => {
    const { node } = await addSeedNumbersNode(page)
    await node.click()
    await expect(node).toHaveClass(/selected/)
  })

  test('node panel updates on selection', async ({ page }) => {
    const { node } = await addSeedNumbersNode(page)
    await node.click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const nodePanel = page.locator('[data-testid="panel-nodePanel"]')
    await expect(nodePanel).toBeVisible()
    await expect(nodePanel.locator('.node-name')).toBeVisible({ timeout: 3000 })
  })

  test('pins show single circle (no double)', async ({ page }) => {
    const { node } = await addSeedNumbersNode(page)
    await expect(node.locator('.pin-dot')).toHaveCount(0)
    const handles = node.locator('.pin-handle')
    expect(await handles.count()).toBeGreaterThan(0)
  })

  test('context menu has light theme', async ({ page }) => {
    const { node } = await addSeedNumbersNode(page)
    await node.click({ button: 'right' })
    const menu = page.locator('.node-context-menu')
    await expect(menu).toBeVisible()
    const bg = await menu.evaluate((el) => getComputedStyle(el).backgroundColor)
    expect(bg).toContain('255')
  })
})
