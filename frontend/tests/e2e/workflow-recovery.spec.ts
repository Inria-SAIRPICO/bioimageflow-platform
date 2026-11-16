import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import type { GraphState, WorkflowFile, WorkflowInfo } from '../../src/api/types'
import type { WorkflowDraftResponse } from '../../src/api/workflowDrafts'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

async function legacySnapshot(page: Page, name: string) {
  return page.evaluate(snapshotName => new Promise<unknown>((resolve, reject) => {
    // Open the current schema; the old workflows store remains a recovery source.
    const request = indexedDB.open('bioimageflow-autosave')
    request.onerror = () => reject(request.error)
    request.onsuccess = () => {
      const db = request.result
      const tx = db.transaction('workflows', 'readonly')
      const read = tx.objectStore('workflows').get(snapshotName)
      tx.oncomplete = () => { db.close(); resolve(read.result ?? null) }
      tx.onerror = () => { db.close(); reject(tx.error) }
    }
  }), name)
}

async function draft(page: Page, id: string): Promise<WorkflowDraftResponse> {
  const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${id}`)
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json()
}

test('restores ambiguous legacy browser edits only into an explicitly chosen unsaved draft', { tag: '@critical' }, async ({ page }) => {
  const suffix = `${test.info().project.name}_${Date.now()}`
  const legacyPath = `Legacy/reused_${suffix}`
  const entries: WorkflowInfo[] = []
  for (const [name, display_name] of [
    [legacyPath, 'Current workflow at former path'],
    [`active_${suffix}`, 'Unrelated active workflow'],
    [`destination_${suffix}`, 'Chosen recovery destination'],
  ]) {
    const response = await page.request.post(`${API_BASE}/api/v1/workflows`, { data: { name, display_name } })
    expect(response.status()).toBe(201)
    entries.push(await response.json() as WorkflowInfo)
  }
  const [reused, active, destination] = entries as [WorkflowInfo, WorkflowInfo, WorkflowInfo]
  try {
    expect((await page.request.post(`${API_BASE}/api/v1/dev/seed`)).ok()).toBeTruthy()
    const originalResponse = await page.request.get(`${API_BASE}/api/v1/workflows/${reused.id}`)
    expect(originalResponse.ok()).toBeTruthy()
    const original = await originalResponse.json() as WorkflowFile
    const recovered: GraphState = {
      ...original.graph,
      name: legacyPath,
      display_name: 'Recovered microscope measurements',
      nodes: [{ type: 'tool', id: 'recovered_measurements', name: 'Recovered measurements', tool_name: 'SeedNumbers', position: [220, 160], parameters: {} }],
    }
    const savedBytes = entries.map(info => readFileSync(info.path))
    await page.goto('/')
    await expect(page.getByTestId('workflow-title')).toBeVisible()
    await page.evaluate(({ name, graph, activeId }) => new Promise<void>((resolve, reject) => {
      const request = indexedDB.open('bioimageflow-autosave')
      request.onerror = () => reject(request.error)
      request.onsuccess = () => {
        const db = request.result
        const tx = db.transaction(['workflows', 'preferences'], 'readwrite')
        tx.objectStore('workflows').put({ name, graph, timestamp: Date.now() + 60_000 })
        tx.objectStore('preferences').put(activeId, 'last_opened_workflow')
        tx.oncomplete = () => { db.close(); resolve() }
        tx.onerror = () => { db.close(); reject(tx.error) }
      }
    }), { name: legacyPath, graph: recovered, activeId: active.id })
    const captured = await legacySnapshot(page, legacyPath)
    const recoveredWrites: string[] = []
    page.on('request', request => {
      if (request.method() !== 'PUT' || !request.url().includes('/api/v1/workflow-drafts/')) return
      const body = request.postDataJSON() as { graph?: GraphState }
      if (body.graph?.nodes.some(node => node.id === 'recovered_measurements')) recoveredWrites.push(new URL(request.url()).pathname)
    })
    await page.reload()
    await expect(page.getByTestId('workflow-title')).toContainText(active.display_name)
    const warning = page.getByTestId('workflow-recovery-conflict')
    await expect(warning).toBeVisible()
    expect(recoveredWrites).toEqual([])
    for (const info of entries) expect((await draft(page, info.id)).graph.nodes).toEqual([])
    expect(await legacySnapshot(page, legacyPath)).toEqual(captured)

    await warning.getByRole('button', { name: 'Review recovery', exact: true }).click()
    const dialog = page.getByTestId('workflow-recovery-dialog')
    await expect(dialog).toBeVisible()
    const source = page.getByTestId('workflow-recovery-source')
    const legacyOption = source.locator('option').filter({ hasText: legacyPath })
    await source.selectOption((await legacyOption.getAttribute('value'))!)
    const restore = page.getByTestId('workflow-recovery-restore')
    await expect(restore).toBeDisabled()
    await page.getByTestId('workflow-recovery-target').selectOption(destination.id)
    expect(recoveredWrites).toEqual([])

    // Race the reviewed destination with a real backend CAS write, rather than mocking a conflict response.
    let injectedConflict = false
    await page.route(`**/api/v1/workflow-drafts/${destination.id}`, async route => {
      if (route.request().method() === 'PUT' && !injectedConflict) {
        injectedConflict = true
        const current = await draft(page, destination.id)
        const newer = await page.request.put(`${API_BASE}/api/v1/workflow-drafts/${destination.id}`, {
          data: { graph: { ...current.graph, display_name: 'Newer destination draft' }, expected_revision: current.draft_revision, updated_by: 'agent' },
        })
        expect(newer.ok(), await newer.text()).toBeTruthy()
      }
      await route.continue()
    })
    const refused = page.waitForResponse(response => response.url().endsWith(`/api/v1/workflow-drafts/${destination.id}`)
      && response.request().method() === 'PUT' && response.status() === 409)
    await restore.click()
    await refused
    await expect(dialog.getByRole('alert')).toBeVisible()
    await expect(restore).toBeEnabled()
    expect(await legacySnapshot(page, legacyPath)).toEqual(captured)
    expect((await draft(page, destination.id)).graph.display_name).toBe('Newer destination draft')
    const retryBase = await draft(page, destination.id)
    const acceptedResponse = page.waitForResponse(response => response.url().endsWith(`/api/v1/workflow-drafts/${destination.id}`)
      && response.request().method() === 'PUT' && response.ok())
    await restore.click()
    const accepted = await acceptedResponse
    expect(accepted.request().postDataJSON()).toMatchObject({ expected_revision: retryBase.draft_revision })
    expect(accepted.request().headers()['x-bioimageflow-workspace']).toBe(destination.workspace_path)
    const acceptedDraft = await accepted.json() as WorkflowDraftResponse
    expect(acceptedDraft.workflow_id).toBe(destination.id)
    expect(acceptedDraft.draft_revision).toBe(retryBase.draft_revision + 1)
    expect(acceptedDraft.dirty_against_saved).toBe(true)
    expect(acceptedDraft.graph.nodes).toMatchObject(recovered.nodes)
    expect(acceptedDraft.graph.name).toBe(retryBase.graph.name)
    expect(acceptedDraft.graph.display_name).toBe(recovered.display_name)
    await expect(dialog).not.toBeVisible()
    await expect(warning).toHaveCount(0)
    await expect(page.getByTestId('workflow-title')).toContainText(destination.display_name)
    await expect(page.getByTestId('workflow-title')).toContainText('*')
    await expect(page.locator('.vue-flow__node[data-id="recovered_measurements"]')).toContainText('Recovered measurements')
    await expect.poll(() => legacySnapshot(page, legacyPath)).toBeNull()
    for (const [index, info] of entries.entries()) expect(readFileSync(info.path)).toEqual(savedBytes[index])
    for (const info of [reused, active]) expect((await draft(page, info.id)).graph.nodes).toEqual([])
    expect(recoveredWrites).toEqual([
      `/api/v1/workflow-drafts/${destination.id}`,
      `/api/v1/workflow-drafts/${destination.id}`,
    ])
  } finally {
    await page.goto('about:blank')
    for (const info of entries) await page.request.delete(`${API_BASE}/api/v1/workflows/${info.id}`)
  }
})
