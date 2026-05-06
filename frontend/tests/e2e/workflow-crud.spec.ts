import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

function uniqueName(prefix: string, page: Page): string {
  const project = test.info().project.name.replace(/[^a-zA-Z0-9_-]/g, '_')
  return `${prefix}_${project}_${Date.now()}_${Math.floor(Math.random() * 10000)}`
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

async function openWorkflowMenu(page: Page) {
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
}

async function chooseWorkflowItem(page: Page, label: string) {
  await openWorkflowMenu(page)
  await page.getByRole('menuitem', { name: label, exact: true }).click()
}

async function deleteWorkflowIfExists(page: Page, name: string) {
  await page.request.delete(`${API_BASE}/api/v1/workflows/${name}`).catch(() => undefined)
}

test.describe('workflow CRUD dialogs', () => {
  test.describe.configure({ mode: 'serial' })

  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await expect(page.locator('[data-testid="workflow-title"]')).toBeVisible()
  })

  test('creates a workflow from the polished dialog', async ({ page }) => {
    const displayName = uniqueName('Dialog Create', page)
    const name = deriveWorkflowId(displayName)
    await deleteWorkflowIfExists(page, name)

    await chooseWorkflowItem(page, 'New')
    await expect(page.locator('[data-testid="workflow-dialog"]')).toBeVisible()
    await page.locator('[data-testid="workflow-display-name-input"]').fill(displayName)
    await expect(page.locator('[data-testid="workflow-generated-name"]')).toContainText(name)
    await page.locator('[data-testid="workflow-dialog-submit"]').click()

    await expect(page.locator('[data-testid="workflow-dialog"]')).not.toBeVisible()
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText(displayName)

    const response = await page.request.get(`${API_BASE}/api/v1/workflows`)
    expect(response.ok()).toBeTruthy()
    const workflows = await response.json()
    expect(
      workflows.some(
        (workflow: { name: string; display_name: string }) =>
          workflow.name === name && workflow.display_name === displayName,
      ),
    ).toBe(true)

    await deleteWorkflowIfExists(page, name)
  })

  test('save-as creates a copy and open dialog can switch workflows', async ({ page }) => {
    const baseDisplayName = uniqueName('Dialog Base', page)
    const copyDisplayName = `${baseDisplayName} Copy`
    const base = deriveWorkflowId(baseDisplayName)
    const copy = deriveWorkflowId(copyDisplayName)
    await deleteWorkflowIfExists(page, base)
    await deleteWorkflowIfExists(page, copy)

    await chooseWorkflowItem(page, 'New')
    await page.locator('[data-testid="workflow-display-name-input"]').fill(baseDisplayName)
    await page.locator('[data-testid="workflow-dialog-submit"]').click()
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText(baseDisplayName)

    await chooseWorkflowItem(page, 'Save As')
    await page.locator('[data-testid="workflow-display-name-input"]').fill(copyDisplayName)
    await expect(page.locator('[data-testid="workflow-generated-name"]')).toContainText(copy)
    await page.locator('[data-testid="workflow-dialog-submit"]').click()
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText(copyDisplayName)

    await chooseWorkflowItem(page, 'Open')
    await expect(page.locator('[data-testid="open-workflow-dialog"]')).toBeVisible()
    await page.locator('[data-testid="workflow-open-search"]').fill(baseDisplayName)
    await page.locator(`[data-testid="workflow-open-option-${base}"]`).click()
    await page.locator('[data-testid="workflow-open-submit"]').click()
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText(baseDisplayName)

    await deleteWorkflowIfExists(page, base)
    await deleteWorkflowIfExists(page, copy)
  })

  test('delete workflow uses confirmation dialog and clears server file', async ({ page }) => {
    const displayName = uniqueName('Dialog Delete', page)
    const name = deriveWorkflowId(displayName)
    await deleteWorkflowIfExists(page, name)

    await chooseWorkflowItem(page, 'New')
    await page.locator('[data-testid="workflow-display-name-input"]').fill(displayName)
    await page.locator('[data-testid="workflow-dialog-submit"]').click()
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText(displayName)

    await chooseWorkflowItem(page, 'Delete')
    await expect(page.locator('[data-testid="delete-workflow-dialog"]')).toBeVisible()
    await page.locator('[data-testid="delete-workflow-confirm"]').click()
    await expect(page.locator('[data-testid="delete-workflow-dialog"]')).not.toBeVisible()

    const deleted = await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)
    expect(deleted.status()).toBe(404)
  })
})
