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

async function addSourceNode(page: Page, source: ToolMetadata) {
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
    targetPosition: { x: 300, y: 180 },
  })
  await draftResponse
  const node = page.locator('.vue-flow__node').first()
  await expect(node).toBeVisible({ timeout: 5000 })
  await expect(node.locator('.node-name')).toContainText(source.display_name)
  return node
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

  test('creates a workflow and executes a source tool through the real backend', async ({
    page,
  }) => {
    const displayName = uniqueDisplayName('Execution Workflow')
    const workflowName = deriveWorkflowId(displayName)
    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`).catch(() => undefined)

    await createWorkflowInGui(page, displayName)
    const source = await sourceTool(page)
    const node = await addSourceNode(page, source)
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

    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`).catch(() => undefined)
  })
})
