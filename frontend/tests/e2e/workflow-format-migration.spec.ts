import { readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`
const E2E_ROOT = process.env.BIOIMAGEFLOW_E2E_ROOT

test('defers and later confirms a workflow format update with visible backups', async ({ page }) => {
  expect(E2E_ROOT).toBeTruthy()
  const workflowId = `format_update_${Date.now()}`
  const created = await page.request.post(`${API_BASE}/api/v1/workflows`, {
    data: { name: workflowId, display_name: 'Format update example' },
  })
  expect(created.status()).toBe(201)
  const workflowPath = join(E2E_ROOT!, 'workflows', workflowId, 'workflow.json')
  const document = JSON.parse(await readFile(workflowPath, 'utf8'))
  document.graph.schema_version = 1
  await writeFile(workflowPath, JSON.stringify(document))

  const preview = await page.request.get(`${API_BASE}/api/v1/workflows/format-status`)
  expect(preview.ok(), await preview.text()).toBeTruthy()
  expect((await preview.json()).pending_plan_id).toMatch(/^sha256:/)

  await page.goto('/')
  await expect(page.locator('#bioimageflow-app')).toBeVisible()
  const dialog = page.getByTestId('workflow-format-dialog')
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText(workflowId)

  await page.getByTestId('workflow-format-not-now').click()
  await expect(dialog).not.toBeVisible()
  await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).first().click()
  await expect(page.getByTestId('workflow-format-warning')).toContainText(
    'unavailable until it is updated',
  )
  await expect(page.getByTestId(`workflow-row-${workflowId}`)).toHaveCount(0)

  await page.getByTestId('workflow-format-review').click()
  await expect(dialog).toBeVisible()
  const appliedResponse = page.waitForResponse(response => (
    response.url().endsWith('/api/v1/workflows/format-migrations/apply')
    && response.request().method() === 'POST'
  ))
  await page.getByTestId('workflow-format-update').click()
  const applied = await appliedResponse
  expect(applied.ok(), await applied.text()).toBeTruthy()
  const payload = await applied.json()
  const backupPaths = payload.notices.flatMap(
    (notice: { backup_paths: string[] }) => notice.backup_paths,
  )
  expect(backupPaths.length).toBeGreaterThan(0)

  await expect(dialog).not.toBeVisible()
  await expect(page.getByTestId(`workflow-row-${workflowId}`)).toBeVisible()
  const warning = page.getByTestId('workflow-format-warning')
  await expect(warning).toContainText('A backup was preserved')
  for (const backupPath of backupPaths) {
    await expect(warning).toContainText(backupPath)
  }

  await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowId}`)
})
