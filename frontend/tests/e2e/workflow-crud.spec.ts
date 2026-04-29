import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

const API_BASE = 'http://127.0.0.1:8000'

function uniqueName(prefix: string, page: Page): string {
  const project = test.info().project.name.replace(/[^a-zA-Z0-9_-]/g, '_')
  return `${prefix}_${project}_${Date.now()}_${Math.floor(Math.random() * 10000)}`
}

async function openWorkflowMenu(page: Page) {
  await page.getByRole('menuitem', { name: 'Workflow' }).click()
}

async function chooseWorkflowItem(page: Page, label: string) {
  await openWorkflowMenu(page)
  await page.getByRole('menuitem', { name: label }).click()
}

async function deleteWorkflowIfExists(page: Page, name: string) {
  await page.request.delete(`${API_BASE}/api/v1/workflows/${name}`).catch(() => undefined)
}

test.describe('workflow CRUD dialogs', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await expect(page.locator('[data-testid="workflow-title"]')).toBeVisible()
  })

  test('creates a workflow from the polished dialog', async ({ page }) => {
    const name = uniqueName('dialog_create', page)
    await deleteWorkflowIfExists(page, name)

    await chooseWorkflowItem(page, 'New')
    await expect(page.locator('[data-testid="workflow-dialog"]')).toBeVisible()
    await page.locator('[data-testid="workflow-name-input"]').fill(name)
    await page.locator('[data-testid="workflow-display-name-input"]').fill('Dialog Create')
    await page.locator('[data-testid="workflow-description-input"]').fill('Created from Playwright')
    await page.locator('[data-testid="workflow-dialog-submit"]').click()

    await expect(page.locator('[data-testid="workflow-dialog"]')).not.toBeVisible()
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText('Dialog Create')

    const response = await page.request.get(`${API_BASE}/api/v1/workflows`)
    expect(response.ok()).toBeTruthy()
    const workflows = await response.json()
    expect(workflows.some((workflow: { name: string }) => workflow.name === name)).toBe(true)

    await deleteWorkflowIfExists(page, name)
  })

  test('save-as creates a copy and open dialog can switch workflows', async ({ page }) => {
    const base = uniqueName('dialog_base', page)
    const copy = `${base}_copy`
    await deleteWorkflowIfExists(page, base)
    await deleteWorkflowIfExists(page, copy)

    await chooseWorkflowItem(page, 'New')
    await page.locator('[data-testid="workflow-name-input"]').fill(base)
    await page.locator('[data-testid="workflow-display-name-input"]').fill('Dialog Base')
    await page.locator('[data-testid="workflow-dialog-submit"]').click()
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText('Dialog Base')

    await chooseWorkflowItem(page, 'Save As')
    await page.locator('[data-testid="workflow-name-input"]').fill(copy)
    await page.locator('[data-testid="workflow-display-name-input"]').fill('Dialog Copy')
    await page.locator('[data-testid="workflow-dialog-submit"]').click()
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText('Dialog Copy')

    await chooseWorkflowItem(page, 'Open')
    await expect(page.locator('[data-testid="open-workflow-dialog"]')).toBeVisible()
    await page.locator('[data-testid="workflow-open-search"]').fill(base)
    await page.locator(`[data-testid="workflow-open-option-${base}"]`).click()
    await page.locator('[data-testid="workflow-open-submit"]').click()
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText('Dialog Base')

    await deleteWorkflowIfExists(page, base)
    await deleteWorkflowIfExists(page, copy)
  })

  test('delete workflow uses confirmation dialog and clears server file', async ({ page }) => {
    const name = uniqueName('dialog_delete', page)
    await deleteWorkflowIfExists(page, name)

    await chooseWorkflowItem(page, 'New')
    await page.locator('[data-testid="workflow-name-input"]').fill(name)
    await page.locator('[data-testid="workflow-display-name-input"]').fill('Dialog Delete')
    await page.locator('[data-testid="workflow-dialog-submit"]').click()
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText('Dialog Delete')

    await chooseWorkflowItem(page, 'Delete')
    await expect(page.locator('[data-testid="delete-workflow-dialog"]')).toBeVisible()
    await page.locator('[data-testid="delete-workflow-confirm"]').click()
    await expect(page.locator('[data-testid="delete-workflow-dialog"]')).not.toBeVisible()

    const deleted = await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)
    expect(deleted.status()).toBe(404)
  })
})
