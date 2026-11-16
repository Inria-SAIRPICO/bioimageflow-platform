import { createHash } from 'node:crypto'
import { cpSync, lstatSync, readFileSync, readdirSync, readlinkSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { expect, test } from '@playwright/test'
import type { ExecutionStatus, WorkflowFile, WorkflowFormatStatus, WorkflowInfo } from '../../src/api/types'
import type { WorkflowDraftResponse } from '../../src/api/workflowDrafts'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

function fileSnapshot(root: string): Record<string, string> {
  const files: Record<string, string> = {}
  const visit = (directory: string, prefix: string) => {
    for (const name of readdirSync(directory).sort()) {
      const path = join(directory, name)
      const key = `${prefix}${name}`
      const stat = lstatSync(path)
      if (stat.isSymbolicLink()) files[key] = `link:${readlinkSync(path)}`
      else if (stat.isDirectory()) visit(path, `${key}/`)
      else files[key] = createHash('sha256').update(readFileSync(path)).digest('hex')
    }
  }
  visit(root, '')
  return files
}

test('reviews an external workflow copy before assigning an independent identity', { tag: '@critical' }, async ({ page }) => {
  const relativePath = `copy_review_${test.info().project.name}_${Date.now()}`
  const copiedPath = `${relativePath}_external_copy`
  const label = 'Measurements retained after copying'
  const created = await page.request.post(`${API_BASE}/api/v1/workflows`, {
    data: { name: relativePath, display_name: label },
  })
  expect(created.status()).toBe(201)
  const originalInfo = await created.json() as WorkflowInfo
  const originalId = originalInfo.id
  let independentId: string | undefined
  try {
    expect((await page.request.post(`${API_BASE}/api/v1/dev/seed`)).ok()).toBeTruthy()
    const originalResponse = await page.request.get(`${API_BASE}/api/v1/workflows/${originalId}`)
    expect(originalResponse.ok(), await originalResponse.text()).toBeTruthy()
    const original = await originalResponse.json() as WorkflowFile
    original.graph.nodes = [{
      type: 'tool', id: 'seed', name: 'Measurements', tool_name: 'SeedNumbers',
      position: [180, 140], parameters: {},
    }]
    expect((await page.request.put(`${API_BASE}/api/v1/workflows/${originalId}`, {
      data: { graph: original.graph },
    })).ok()).toBeTruthy()
    const draftResponse = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${originalId}`)
    expect(draftResponse.ok(), await draftResponse.text()).toBeTruthy()
    const savedDraft = await draftResponse.json() as WorkflowDraftResponse
    savedDraft.graph.nodes[0]!.position = [240, 140]
    const pendingResponse = await page.request.put(`${API_BASE}/api/v1/workflow-drafts/${originalId}`, {
      data: { graph: savedDraft.graph, expected_revision: savedDraft.draft_revision, updated_by: 'frontend' },
    })
    expect(pendingResponse.ok(), await pendingResponse.text()).toBeTruthy()
    const draft = await pendingResponse.json() as WorkflowDraftResponse
    expect(draft.dirty_against_saved).toBe(true)
    const run = await page.request.post(`${API_BASE}/api/v1/execution/run`, {
      data: { workflow_id: originalId, draft_revision: draft.draft_revision },
    })
    expect(run.status(), await run.text()).toBe(202)
    const { execution_id: executionId } = await run.json() as { execution_id: string }
    await expect.poll(async () => {
      const statusResponse = await page.request.get(`${API_BASE}/api/v1/execution/status`)
      expect(statusResponse.ok()).toBeTruthy()
      const status = await statusResponse.json() as ExecutionStatus
      return status.execution_id === executionId && status.state === 'idle' && status.last_result?.success
    }, { timeout: 15_000 }).toBe(true)

    // Copy the actual directory, including completed scientific results, outside the platform.
    const originalDirectory = dirname(originalInfo.path)
    const copiedDirectory = join(dirname(originalDirectory), copiedPath)
    const originalFiles = fileSnapshot(originalDirectory)
    const resultsBefore = fileSnapshot(originalInfo.results_path)
    expect(Object.keys(resultsBefore).length).toBeGreaterThan(0)
    cpSync(originalDirectory, copiedDirectory, { recursive: true, verbatimSymlinks: true })
    const copiedDocument = JSON.parse(readFileSync(join(copiedDirectory, 'workflow.json'), 'utf8'))
    const copiedDraft = JSON.parse(readFileSync(join(copiedDirectory, '.bioimageflow', 'draft.json'), 'utf8'))
    const blocked = await page.request.get(`${API_BASE}/api/v1/workflows/${originalId}`)
    expect(blocked.status()).toBe(409)
    expect(await blocked.text()).toContain('workflow_identity_conflict')

    await page.goto('/')
    await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).first().click()
    const warning = page.getByTestId('workflow-identity-copies-warning')
    await expect(warning).toBeVisible()
    await expect(page.getByTestId(`workflow-row-${originalId}`)).toHaveCount(0)
    await warning.getByRole('button', { name: 'Review copies', exact: true }).click()
    const dialog = page.getByTestId('workflow-identity-copies-dialog')
    await expect(dialog).toBeVisible()
    const resolve = page.getByTestId('workflow-identity-copy-resolve')
    await expect(resolve).toBeDisabled()
    await page.getByTestId('workflow-identity-copy-path').selectOption(copiedPath)
    await expect(resolve).toBeEnabled()
    const resolution = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/workflows/identity-copies/resolve')
      && response.request().method() === 'POST'
    ))
    await resolve.click()
    const accepted = await resolution
    expect(accepted.ok(), await accepted.text()).toBeTruthy()
    expect(accepted.request().postDataJSON()).toMatchObject({
      relative_path: copiedPath, expected_workflow_id: originalId,
      expected_document_hash: expect.stringMatching(/^sha256:/),
    })
    expect(accepted.request().headers()['x-bioimageflow-workspace']).toBe(originalInfo.workspace_path)
    const independent = await accepted.json() as WorkflowInfo
    independentId = independent.id
    expect(independentId).not.toBe(originalId)
    expect(independent.relative_path).toBe(copiedPath)
    await expect(dialog).not.toBeVisible()
    await expect(warning).toHaveCount(0)
    for (const id of [originalId, independentId]) {
      await expect(page.getByTestId(`workflow-row-${id}`)).toContainText(label)
    }
    await page.getByTestId(`workflow-row-${independentId}`).dblclick()
    await expect(page.getByTestId('workflow-title')).toContainText(label)
    await expect(page.getByTestId('workflow-title')).not.toContainText(independentId)
    await expect(page.locator('.vue-flow__node[data-id="seed"]')).toBeVisible()

    const current = await page.request.get(`${API_BASE}/api/v1/workflows/${originalId}`)
    expect(current.ok(), await current.text()).toBeTruthy()
    expect((await current.json() as WorkflowFile).info.relative_path).toBe(relativePath)
    expect(fileSnapshot(originalDirectory)).toEqual(originalFiles)
    expect(fileSnapshot(independent.results_path)).toEqual(resultsBefore)
    expect(JSON.parse(readFileSync(join(copiedDirectory, 'workflow.json'), 'utf8'))).toEqual({
      ...copiedDocument, workflow_id: independentId,
    })
    expect(JSON.parse(readFileSync(join(copiedDirectory, '.bioimageflow', 'draft.json'), 'utf8'))).toEqual({
      ...copiedDraft, workflow_id: independentId,
    })
    const statusResponse = await page.request.get(`${API_BASE}/api/v1/workflows/format-status`)
    expect(statusResponse.ok()).toBeTruthy()
    expect((await statusResponse.json() as WorkflowFormatStatus).identity_conflicts).toEqual([])
  } finally {
    await page.goto('about:blank')
    if (independentId) await page.request.delete(`${API_BASE}/api/v1/workflows/${independentId}`)
    await page.request.delete(`${API_BASE}/api/v1/workflows/${originalId}`)
  }
})
