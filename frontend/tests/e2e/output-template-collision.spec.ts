import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import type { GraphState } from '../../src/api/types'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

async function status(page: Page) {
  const response = await page.request.get(`${API_BASE}/api/v1/execution/status`)
  expect(response.ok()).toBeTruthy()
  return response.json()
}

async function draft(page: Page, name: string) {
  const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)
  expect(response.ok()).toBeTruthy()
  return response.json()
}

test('explains an output collision, cancels unchanged and explicitly updates the draft before a cached restart', async ({ page }) => {
  test.setTimeout(300_000)
  const relativePath = `output_collision_${test.info().project.name}_${Date.now()}`
  expect((await page.request.post(`${API_BASE}/api/v1/dev/seed`)).ok()).toBeTruthy()
  const graph: GraphState = {
    schema_version: 2, name: relativePath, display_name: relativePath,
    nodes: [
      { type: 'tool', id: 'numbers', name: 'Numbers', tool_name: 'SeedNumbers', position: [100, 180], parameters: {}, output_templates: {}, resources: {}, enabled: true, collapsed: false },
      { type: 'tool', id: 'writer', name: 'Write number file', tool_name: 'WriteNumberFile', position: [450, 180], parameters: {}, output_templates: { report: 'result.txt' }, resources: {}, enabled: true, collapsed: false },
    ],
    edges: [{ type: 'column', id: 'numbers-to-writer', source_node: 'numbers', source_output: 'number', target_node: 'writer', target_input: 'number' }],
    interface: { inputs: [], outputs: [] }, config: { engine: 'wetlands', execution: 'sequential' },
  }
  const created = await page.request.post(`${API_BASE}/api/v1/workflows`, { data: { name: relativePath, display_name: relativePath } })
  expect(created.status()).toBe(201)
  const name = (await created.json()).id as string
  expect((await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, { data: { graph } })).ok()).toBeTruthy()
  await page.goto('/')
  await page.getByTestId('workflow-search').fill(relativePath)
  await page.getByTestId(`workflow-row-${name}`).dblclick()
  await expect(page.getByTestId('workflow-title')).toContainText(relativePath)
  await expect(page.locator('.vue-flow__node')).toHaveCount(2)
  await page.getByTestId('run-workflow-button').click()
  const dialog = page.getByTestId('output-planning-dialog')
  await expect(dialog).toBeVisible({ timeout: 120_000 })
  await expect(dialog).toContainText('writer')
  await expect(dialog).toContainText('result.txt')
  await expect(dialog.getByTestId('output-template-expansion').first()).toContainText('literal text')
  await expect(dialog).toContainText('One file per input row')
  await expect(dialog).toContainText('downstream tools that interpret')
  const failed = await status(page)
  expect(failed.state).toBe('idle')
  expect(failed.last_result.success).toBe(false)
  expect(failed.last_result.output_planning_reports[0].code).toBe('output_path_collision')
  const failedDraft = await draft(page, name)
  const sourceRecord = failed.node_statuses.numbers.record_id

  await dialog.getByTestId('collision-template-report').fill('still_shared.txt')
  await dialog.getByTestId('apply-output-correction').click()
  await expect(dialog.getByTestId('output-planning-error')).toBeVisible()
  await expect(dialog.getByTestId('collision-template-report')).toHaveValue('still_shared.txt')
  expect((await draft(page, name)).graph).toEqual(failedDraft.graph)
  await dialog.getByTestId('cancel-output-correction').click()
  await expect(dialog).not.toBeVisible()
  expect((await draft(page, name)).draft_revision).toBe(failedDraft.draft_revision)
  await page.reload()
  await expect(page.getByTestId('workflow-title')).toContainText(relativePath)
  await expect(dialog).not.toBeVisible()

  await page.getByTestId('run-workflow-button').click()
  await expect(dialog).toBeVisible()
  const secondFailure = await status(page)
  expect(secondFailure.execution_id).not.toBe(failed.execution_id)
  await dialog.getByTestId('collision-template-report').fill('result_{row_index}.txt')
  const restarted = page.waitForResponse(response => response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST')
  await dialog.getByTestId('apply-output-correction').click()
  const restart = await restarted
  expect(restart.status()).toBe(202)
  const accepted = await restart.json()
  expect(accepted.execution_id).not.toBe(secondFailure.execution_id)
  expect(accepted.draft_revision).toBeGreaterThan(secondFailure.draft_revision)
  expect(restart.request().postDataJSON().mode).toBe('normal')
  await expect(dialog).not.toBeVisible()
  await expect.poll(async () => (await status(page)).last_result?.success, { timeout: 180_000 }).toBe(true)
  const completed = await status(page)
  expect(completed.node_statuses.numbers.record_id).toBe(sourceRecord)
  expect(completed.node_statuses.numbers.cached).toBe(true)
  const corrected = await draft(page, name)
  expect(corrected.graph.nodes.find((node: { id: string }) => node.id === 'writer').output_templates.report).toBe('result_{row_index}.txt')
  expect(corrected.dirty_against_saved).toBe(true)
  const saved = await (await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)).json()
  expect(saved.graph.nodes.find((node: { id: string }) => node.id === 'writer').output_templates.report).toBe('result.txt')
  await expect.poll(async () => Promise.all([0, 1, 2].map(async index => {
    try { return await readFile(join(saved.info.results_path, 'outputs', 'latest', 'writer', `result_${index}.txt`), 'utf8') }
    catch { return null }
  }))).toEqual(['1', '2', '3'])
})
