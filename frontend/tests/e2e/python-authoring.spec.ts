import { test, expect, type Dialog, type Page, type Request, type Response } from '@playwright/test'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import type { NodeDataResponse, WorkflowFile, WorkflowInfo, WorkflowSourcePreview } from '../../src/api/types'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`

async function savedWorkflow(page: Page, name: string): Promise<WorkflowFile> {
  const response = await page.request.get(`${API}/workflows/${name}`)
  expect(response.ok(), await response.text()).toBeTruthy()
  return await response.json() as WorkflowFile
}

async function openWorkflow(page: Page, name: string, label: string): Promise<void> {
  await page.goto('/')
  await expect(page.locator('#bioimageflow-app')).toBeVisible()
  await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
  await page.getByTestId('workflow-search').fill(name)
  await page.getByTestId(`workflow-row-${name}`).dblclick()
  await expect(page.getByTestId('workflow-title')).toContainText(label)
  await expect(page.getByTestId('run-workflow-button')).toBeEnabled()
}

test('trusted Python Build cancels, rejects a stale preview, and Run uses the materialized graph', async ({ page }) => {
  const suffix = `${test.info().project.name}_${Date.now()}`
  const name = `python_authored_${suffix}`
  const helperName = `authoring_helper_${suffix}`
  const firstLabel = `First authored ${suffix}`
  const freshLabel = `Rebuilt authored ${suffix}`
  let primaryOccurred = false
  let cleanupFailed = false
  let cleanupFailure: unknown
  let pendingDialog: Dialog | null = null
  const applyRequests: string[] = []
  const observeApply = (request: Request) => {
    if (request.method() === 'POST' && new URL(request.url()).pathname === `/api/v1/workflows/${name}/source-operations/apply`) {
      applyRequests.push(request.postData() ?? '')
    }
  }
  try {
    const seed = await page.request.post(`${API}/dev/seed`)
    expect(seed.ok(), await seed.text()).toBeTruthy()
    const created = await page.request.post(`${API}/workflows`, { data: { name } })
    expect(created.status(), await created.text()).toBe(201)
    const info = await created.json() as WorkflowInfo
    expect(info.id ?? info.name).toBe(name)
    const root = dirname(info.path)
    expect(dirname(info.results_path)).toBe(root)
    const entry = join(root, 'workflow.py')
    const helper = join(root, `${helperName}.py`)
    const calls = join(root, 'factory-calls.log')
    expect(existsSync(calls)).toBe(false)
    const authoringSource = `from pathlib import Path
from bioimageflow import Workflow
from bioimageflow_dev_tools.tools import SeedNumbers
from ${helperName} import LABEL

def build_workflow(*, storage_path):
    with Path(${JSON.stringify(calls)}).open('a', encoding='utf-8') as log:
        log.write(LABEL + '\\n')
    with Workflow(name=${JSON.stringify(name)}, display_name=LABEL, engine='direct', execution='sequential', storage_path=storage_path) as workflow:
        seed = SeedNumbers()(name='seed')
        workflow.output('number', seed['number'])
        workflow.output('label', seed['label'])
    return workflow
`
    writeFileSync(entry, authoringSource)
    writeFileSync(helper, `LABEL = ${JSON.stringify(firstLabel)}\n`)
    const recordedCalls = () => readFileSync(calls, 'utf8').trimEnd().split('\n')
    page.on('request', observeApply)
    await openWorkflow(page, name, name)

    const startBuild = async () => {
      await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
      const build = page.getByRole('menuitem', { name: 'Build from Python source', exact: true })
      await expect(build).toBeEnabled()
      const previewResponse = page.waitForResponse(response => response.request().method() === 'POST'
        && new URL(response.url()).pathname === `/api/v1/workflows/${name}/python-source/preview`)
      const confirmation = page.waitForEvent('dialog')
      const clicked = build.click()
      const dialog = await confirmation
      pendingDialog = dialog
      expect(dialog.type()).toBe('confirm')
      expect(dialog.message()).toContain('replaces the saved graph')
      const response = await previewResponse
      // Renderer response-body completion can be held by window.confirm.
      // Keep the original handle and inspect it after releasing the dialog.
      return { dialog, clicked, response }
    }
    const readPreview = async (response: Response): Promise<WorkflowSourcePreview> => {
      expect(response.status(), await response.text()).toBe(200)
      const preview = await response.json() as WorkflowSourcePreview
      expect(preview.operation).toBe('python_rebuild')
      expect(preview.workflow_id).toBe(name)
      return preview
    }

    // Build saves the current canvas before preview. Cancel preserves this
    // accepted post-save baseline, rather than claiming that no Save occurred.
    const cancelled = await startBuild()
    const cancelBaseline = await savedWorkflow(page, name)
    const cancelBytes = readFileSync(info.path)
    expect(cancelBaseline.graph.nodes).toEqual([])
    expect(cancelBaseline.authoring_source).toBeNull()
    expect(recordedCalls()).toEqual([firstLabel])
    await cancelled.dialog.dismiss()
    pendingDialog = null
    await cancelled.clicked
    const cancelledPreview = await readPreview(cancelled.response)
    expect(cancelledPreview.parent_artifact_hash).toBe(cancelBaseline.artifact_hash)
    expect(cancelledPreview.replacement.display_name).toBe(firstLabel)
    // Let the actual dialog continuation finish before checking zero Apply.
    await page.evaluate(() => Promise.resolve())
    expect(applyRequests).toEqual([])
    const afterCancel = await savedWorkflow(page, name)
    expect(afterCancel.graph).toEqual(cancelBaseline.graph)
    expect(afterCancel.artifact_hash).toBe(cancelBaseline.artifact_hash)
    expect(afterCancel.authoring_source).toEqual(cancelBaseline.authoring_source)
    expect(readFileSync(info.path)).toEqual(cancelBytes)
    expect(readFileSync(entry, 'utf8')).toBe(authoringSource)
    expect(recordedCalls()).toEqual([firstLabel])

    const stale = await startBuild()
    const staleBaseline = await savedWorkflow(page, name)
    const staleBytes = readFileSync(info.path)
    expect(recordedCalls()).toEqual([firstLabel, firstLabel])
    writeFileSync(helper, `LABEL = ${JSON.stringify(freshLabel)}\n`)
    const refusedResponse = page.waitForResponse(response => response.request().method() === 'POST'
      && new URL(response.url()).pathname === `/api/v1/workflows/${name}/source-operations/apply`)
    await stale.dialog.accept()
    pendingDialog = null
    await stale.clicked
    const stalePreview = await readPreview(stale.response)
    expect(stalePreview.parent_artifact_hash).toBe(staleBaseline.artifact_hash)
    const refused = await refusedResponse
    expect(refused.status(), await refused.text()).toBe(409)
    expect(await refused.json()).toMatchObject({ detail: 'Python authoring source changed after preview' })
    expect(refused.request().postDataJSON()).toMatchObject({ token: stalePreview.token, confirm_effects: stalePreview.destructive_effects })
    await expect(page.locator('.p-toast')).toContainText('Python authoring source changed after preview')
    const afterRefusal = await savedWorkflow(page, name)
    expect(afterRefusal.graph).toEqual(staleBaseline.graph)
    expect(afterRefusal.artifact_hash).toBe(staleBaseline.artifact_hash)
    expect(afterRefusal.authoring_source).toEqual(staleBaseline.authoring_source)
    expect(readFileSync(info.path)).toEqual(staleBytes)
    expect(recordedCalls()).toEqual([firstLabel, firstLabel])
    expect(applyRequests).toHaveLength(1)

    const fresh = await startBuild()
    expect(recordedCalls()).toEqual([firstLabel, firstLabel, freshLabel])
    const acceptedResponse = page.waitForResponse(response => response.request().method() === 'POST'
      && new URL(response.url()).pathname === `/api/v1/workflows/${name}/source-operations/apply`)
    await fresh.dialog.accept()
    pendingDialog = null
    await fresh.clicked
    const freshPreview = await readPreview(fresh.response)
    expect(freshPreview.source_artifact_hash).not.toBe(stalePreview.source_artifact_hash)
    expect(freshPreview.replacement.display_name).toBe(freshLabel)
    const accepted = await acceptedResponse
    expect(accepted.status(), await accepted.text()).toBe(200)
    expect(accepted.request().postDataJSON()).toMatchObject({ token: freshPreview.token, confirm_effects: freshPreview.destructive_effects })
    await expect(page.getByTestId('workflow-title')).toContainText(freshLabel)
    await expect(page.locator('.vue-flow__node[data-id="seed"]')).toBeVisible()
    const materialized = await savedWorkflow(page, name)
    expect(materialized.graph).toEqual(freshPreview.replacement)
    expect(materialized.authoring_source).toMatchObject({ source_id: 'workflow.py', factory: 'build_workflow', source_hash: freshPreview.source_artifact_hash })
    expect(materialized.artifact_hash).not.toBe(staleBaseline.artifact_hash)
    expect(recordedCalls()).toEqual([firstLabel, firstLabel, freshLabel])
    expect(applyRequests).toHaveLength(2)
    const materializedBytes = readFileSync(info.path)

    // No authoring import is permitted during reopen or ordinary execution.
    writeFileSync(entry, "raise AssertionError('authoring source must not be imported by Run')\n")
    await openWorkflow(page, name, freshLabel)
    const reopened = await savedWorkflow(page, name)
    expect(reopened.graph).toEqual(materialized.graph)
    expect(reopened.authoring_source).toEqual(materialized.authoring_source)
    expect(reopened.artifact_hash).toBe(materialized.artifact_hash)
    expect(recordedCalls()).toEqual([firstLabel, firstLabel, freshLabel])
    const running = page.waitForResponse(response => response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/execution/run')
    await page.getByTestId('run-workflow-button').click()
    const response = await running
    expect(response.status(), await response.text()).toBe(202)
    const execution = await response.json() as { execution_id: string; draft_revision: number; status: string; workflow_id: string }
    expect(execution).toMatchObject({ status: 'started', workflow_id: name, execution_id: expect.any(String) })
    expect(response.request().postDataJSON()).toMatchObject({ workflow_id: name, draft_revision: execution.draft_revision })
    await expect.poll(async () => {
      const status = await (await page.request.get(`${API}/execution/status`)).json() as {
        execution_id: string; state: string; last_result?: { success: boolean };
      }
      return { execution_id: status.execution_id, state: status.state, success: status.last_result?.success }
    }, { timeout: 15_000 }).toEqual({ execution_id: execution.execution_id, state: 'idle', success: true })
    const data = await page.request.post(`${API}/nodes/seed/data/query`, { data: { workflow_name: name } })
    expect(data.ok(), await data.text()).toBeTruthy()
    const result = await data.json() as NodeDataResponse
    expect(result.rows).toEqual([{ number: 1, label: 'one' }, { number: 2, label: 'two' }, { number: 3, label: 'three' }])
    expect(result.identity_status).toBe('captured')
    expect(result.source_identity).toMatchObject({ node_key: 'seed', run_id: expect.any(String), record_id: expect.any(String), result_key: expect.any(String) })
    expect(recordedCalls()).toEqual([firstLabel, firstLabel, freshLabel])
    expect(readFileSync(info.path)).toEqual(materializedBytes)
    expect(applyRequests).toHaveLength(2)
  } catch (error) {
    primaryOccurred = true
    throw error
  } finally {
    page.off('request', observeApply)
    for (const cleanup of [
      async () => { if (pendingDialog) await pendingDialog.dismiss() },
      async () => { await page.goto('about:blank') },
      async () => {
        const response = await page.request.get(`${API}/execution/status`)
        expect(response.ok(), await response.text()).toBeTruthy()
        const status = await response.json() as { workflow_id: string | null; state: string }
        if (status.workflow_id !== name || status.state === 'idle') return
        const stopped = await page.request.post(`${API}/execution/stop`)
        expect(stopped.ok(), await stopped.text()).toBeTruthy()
        await expect.poll(async () => {
          const current = await (await page.request.get(`${API}/execution/status`)).json() as { state: string }
          return current.state
        }, { timeout: 15_000 }).toBe('idle')
      },
      async () => {
        const removed = await page.request.delete(`${API}/workflows/${name}`)
        expect([200, 204, 404]).toContain(removed.status())
      },
    ]) {
      try { await cleanup() } catch (error) {
        if (primaryOccurred) console.error('Python authoring cleanup failed while preserving the primary:', error)
        else if (!cleanupFailed) { cleanupFailed = true; cleanupFailure = error }
      }
    }
  }
  if (cleanupFailed) throw cleanupFailure
})
