import { test, expect, type Response } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { basename, dirname, join } from 'node:path'
import type { NodeDataResponse, ResultArtifactIdentity } from '../../src/api/types'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`

test('imported node opens its own script and immediately executes saved edits', { tag: '@critical' }, async ({ page }) => {
  const suffix = `${Date.now()}`
  const original = `source_${suffix}`
  const imported = `imported_${suffix}`
  const parent = `parent_${suffix}`
  const toolName = `EditableImport${suffix}`
  const settings = await (await page.request.get(`${API}/settings`)).json()
  const oldEditor = (settings.settings ?? settings).external_editor
  const source = `from bioimageflow import DataFrameTool
from bioimageflow_core import IOModel
import pandas as pd
class Outputs(IOModel):
    number_plus_one: int
class ${toolName}(DataFrameTool):
    accepts_upstream = False
    Outputs = Outputs
    def transform(self, df, arguments):
        return pd.DataFrame({"number_plus_one": [n + 1 for n in [1, 2, 3]]})
`
  let primaryOccurred = false
  let cleanupFailed = false
  let cleanupFailure: unknown
  try {
    expect((await page.request.patch(`${API}/settings`, { data: { external_editor: 'true' } })).ok()).toBeTruthy()
    expect((await page.request.post(`${API}/workflows`, { data: { name: original } })).ok()).toBeTruthy()
    const created = await page.request.post(`${API}/tools`, {
      params: { workflow_name: original }, data: { name: toolName, tool_type: 'DataFrameTool' },
    })
    expect(created.ok()).toBeTruthy()
    const originalPath = (await created.json()).path
    writeFileSync(originalPath, source)
    const { graph } = await (await page.request.get(`${API}/workflows/${original}`)).json()
    graph.config = { engine: 'direct', execution: 'sequential' }
    graph.nodes = [{ type: 'tool', id: 'increment', name: 'Increment', tool_name: toolName, position: [200, 140], parameters: {} }]
    expect((await page.request.put(`${API}/workflows/${original}`, { data: { graph } })).ok()).toBeTruthy()
    const exported = await page.request.post(`${API}/workflows/${original}/export`)
    expect(exported.ok(), await exported.text()).toBeTruthy()
    const response = await page.request.post(`${API}/workflows/import`, { multipart: {
      name_override: imported,
      file: { name: 'reference.bioimageflow.zip', mimeType: 'application/zip', buffer: await exported.body() },
    } })
    expect(response.ok(), await response.text()).toBeTruthy()
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
    await page.getByTestId('workflow-search').fill(imported)
    await page.getByTestId(`workflow-row-${imported}`).dblclick()
    const node = page.locator('.vue-flow__node[data-id="increment"]')
    await expect(node).toBeVisible()
    await node.click()
    const opened = page.waitForResponse(response => response.url().endsWith('/editor/open-node'))
    await page.getByTestId('open-tool-script').click()
    const openResponse = await opened
    expect(openResponse.ok(), await openResponse.text()).toBeTruthy()
    const path = (await openResponse.json()).path
    expect(path).not.toBe(originalPath)
    expect(path).toContain(imported)
    const query = async (resultIdentity?: ResultArtifactIdentity) => {
      const data = await page.request.post(`${API}/nodes/increment/data/query`, {
        data: { workflow_name: imported, ...(resultIdentity ? { result_identity: resultIdentity } : {}) },
      })
      expect(data.ok(), await data.text()).toBeTruthy()
      return await data.json() as NodeDataResponse
    }
    const run = async (values: number[]) => {
      const responses: Response[] = []
      const observeRun = (response: Response) => {
        if (response.url().endsWith('/execution/run') && response.request().method() === 'POST') responses.push(response)
      }
      page.on('response', observeRun)
      try {
        await expect(page.getByTestId('run-workflow-button')).toBeEnabled()
        await page.getByTestId('run-workflow-button').click()
        await expect.poll(async () => {
          // Source validation may require the ordinary stale-result confirmation.
          // A fading dialog must not make us wait for a disappearing button.
          if (await page.getByTestId('out-of-date-confirm').isVisible()) {
            await page.getByTestId('out-of-date-continue').evaluateAll(buttons => {
              for (const button of buttons) (button as HTMLButtonElement).click()
            })
          }
          return responses.length
        }, { timeout: 15_000 }).toBe(1)
        const response = responses[0]!
        expect(response.status(), await response.text()).toBe(202)
        const execution = await response.json()
        expect(execution).toMatchObject({ status: 'started', workflow_id: imported, execution_id: expect.any(String) })
        expect(response.request().postDataJSON()).toMatchObject({ workflow_id: imported, draft_revision: execution.draft_revision })
        await expect.poll(async () => {
          const status = await (await page.request.get(`${API}/execution/status`)).json()
          return { execution_id: status.execution_id, state: status.state, success: status.last_result?.success }
        }, { timeout: 15_000 }).toEqual({ execution_id: execution.execution_id, state: 'idle', success: true })
        const result = await query()
        expect(result.rows).toEqual(values.map(number_plus_one => ({ number_plus_one })))
        expect(result.identity_status).toBe('captured')
        expect(result.source_identity).toMatchObject({ node_key: 'increment', run_id: expect.any(String), result_key: expect.any(String), record_id: expect.any(String) })
        if (!result.source_identity) throw new Error('Accepted execution did not publish a captured result identity')
        return { execution, result, identity: result.source_identity }
      } finally {
        page.off('response', observeRun)
      }
    }
    const first = await run([2, 3, 4])
    const validSource = readFileSync(path, 'utf8')
    const badge = node.locator('.updated-badge')
    if (await badge.isVisible()) await badge.click()
    await expect(badge).toHaveCount(0)

    // Owned-source watcher validation has its own visible error contract;
    // it does not use the installed-package tool_reload_failed transport.
    writeFileSync(path, 'invalid Python !!!\n')
    // A source import failure is a global compilation diagnostic, before
    // any node metadata is projected. The canvas displays that exact error.
    const sourceErrors = page.getByTestId('canvas-error-row')
    await expect(sourceErrors).toBeVisible()
    await expect(sourceErrors).toContainText('invalid syntax')
    await expect(sourceErrors).toContainText(basename(path))
    const invalidDraft = await (await page.request.get(`${API}/workflow-drafts/${imported}`)).json()
    expect(invalidDraft.validation.valid).toBe(false)
    const beforeRefusal = await (await page.request.get(`${API}/execution/status`)).json()
    const refused = await page.request.post(`${API}/execution/run`, {
      data: { workflow_id: imported, draft_revision: invalidDraft.draft_revision },
    })
    expect(refused.status(), await refused.text()).toBe(422)
    const refusal = await refused.json()
    expect(refusal.error).toBe('validation_error')
    expect(JSON.stringify(refusal.errors)).toContain(basename(path))
    const afterRefusal = await (await page.request.get(`${API}/execution/status`)).json()
    expect(afterRefusal).toMatchObject({ state: 'idle', execution_id: first.execution.execution_id, workflow_id: imported })
    expect(afterRefusal.last_result).toEqual(beforeRefusal.last_result)
    const unchangedDraft = await (await page.request.get(`${API}/workflow-drafts/${imported}`)).json()
    expect(unchangedDraft.draft_revision).toBe(invalidDraft.draft_revision)
    expect(unchangedDraft.graph).toEqual(invalidDraft.graph)
    for (const retained of [await query(), await query(first.identity)]) {
      expect(retained.source_identity).toEqual(first.identity)
      expect(retained.rows).toEqual(first.result.rows)
    }

    writeFileSync(path, validSource.replace('n + 1', 'n + 20'))
    await expect(sourceErrors).toHaveCount(0)
    await expect(badge).toBeVisible()
    const second = await run([21, 22, 23])
    expect(second.execution.execution_id).not.toBe(first.execution.execution_id)
    expect(second.identity.run_id).not.toBe(first.identity.run_id)
    expect(second.identity).not.toEqual(first.identity)
    const pinned = await query(first.identity)
    expect(pinned.source_identity).toEqual(first.identity)
    expect(pinned.rows).toEqual(first.result.rows)
    expect(readFileSync(originalPath, 'utf8')).toContain('n + 1')

    await expect(page.getByTestId('run-workflow-button')).toBeEnabled()
    const parentResponse = await page.request.post(`${API}/workflows`, { data: { name: parent } })
    expect(parentResponse.ok()).toBeTruthy()
    const parentInfo = await parentResponse.json()
    await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
    await page.getByTestId('workflow-search').fill(parent)
    await page.getByTestId(`workflow-row-${parent}`).dblclick()
    await expect(page.getByTestId('workflow-title')).toContainText(parent)
    await expect(page.getByTestId('run-workflow-button')).toBeEnabled()
    await expect(page.locator('.vue-flow')).toBeVisible()
    await page.getByTestId('workflow-search').fill(imported)
    const embedding = page.waitForResponse(response => response.url().endsWith('/prepare-embedding'), { timeout: 10_000 })
    const transfer = await page.evaluateHandle((id) => {
      const transfer = new DataTransfer()
      transfer.setData('application/bioimageflow-workflow', id)
      return transfer
    }, imported)
    await page.locator('.vue-flow').dispatchEvent('drop', {
      dataTransfer: transfer, clientX: 450, clientY: 280,
    })
    await transfer.dispose()
    const embeddedResponse = await embedding
    expect(embeddedResponse.ok(), await embeddedResponse.text()).toBeTruthy()
    const embedded = await embeddedResponse.json()
    const sourceId = embedded.graph.nodes[0].source_module
    const sourceRoot = join(dirname(parentInfo.results_path), 'tools', sourceId)
    const manifest = JSON.parse(readFileSync(join(sourceRoot, 'module.json'), 'utf8'))
    const embeddedPath = join(sourceRoot, manifest.filename)
    expect(embeddedPath).not.toBe(path)
    expect(readFileSync(embeddedPath, 'utf8')).toContain('n + 20')
    await expect.poll(async () => {
      const draft = await (await page.request.get(`${API}/workflow-drafts/${parent}`)).json()
      return draft.graph.nodes[0]?.workflow?.nodes[0]?.source_module
    }).toBe(sourceId)
    writeFileSync(embeddedPath, readFileSync(embeddedPath, 'utf8').replace('n + 20', 'n + 40'))
    expect(readFileSync(path, 'utf8')).toContain('n + 20')
  } catch (error) {
    primaryOccurred = true
    throw error
  } finally {
    const cleanups = [
      async () => { await page.goto('about:blank') },
      async () => { expect((await page.request.patch(`${API}/settings`, { data: { external_editor: oldEditor } })).ok()).toBeTruthy() },
      ...[imported, original, parent].map(name => async () => {
        const response = await page.request.delete(`${API}/workflows/${name}`)
        expect([200, 204, 404]).toContain(response.status())
      }),
    ]
    for (const cleanup of cleanups) {
      try { await cleanup() } catch (error) {
        if (primaryOccurred) console.error('Editable-source cleanup failed while preserving the primary:', error)
        else if (!cleanupFailed) { cleanupFailed = true; cleanupFailure = error }
      }
    }
  }
  if (cleanupFailed) throw cleanupFailure
})
