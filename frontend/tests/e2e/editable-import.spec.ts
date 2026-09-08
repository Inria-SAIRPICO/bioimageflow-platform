import { test, expect } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'

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
    const info = (await response.json()).info
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
    await page.getByTestId('workflow-search').fill(original)
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
    const csv = join(info.results_path, 'outputs/latest/increment/dataframe.csv')
    const run = async (values: string[]) => {
      await expect(page.getByTestId('run-workflow-button')).toBeEnabled()
      await page.getByTestId('run-workflow-button').click()
      await expect.poll(async () => {
        // A source notification can arrive before or after Run. If validation
        // already marked the cached result stale, honor the normal confirmation.
        const confirmation = page.getByTestId('out-of-date-confirm')
        if (await confirmation.isVisible()) {
          // The dialog can still be fading out after an earlier confirmation.
          // Do not wait for actionability on a button that is being removed.
          await page.getByTestId('out-of-date-continue').evaluateAll(buttons => {
            for (const button of buttons) (button as HTMLButtonElement).click()
          })
        }
        try { return readFileSync(csv, 'utf8').trim().split('\n').slice(1).map(row => row.split(',').at(-1)) }
        catch { return [] }
      }, { timeout: 15_000 }).toEqual(values)
    }
    await run(['2', '3', '4'])
    writeFileSync(path, readFileSync(path, 'utf8').replace('n + 1', 'n + 20'))
    await run(['21', '22', '23'])
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
    await page.getByTestId('workflow-search').fill(original)
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
  } finally {
    await page.goto('about:blank')
    await page.request.patch(`${API}/settings`, { data: { external_editor: oldEditor } })
    await page.request.delete(`${API}/workflows/${imported}`)
    await page.request.delete(`${API}/workflows/${original}`)
    await page.request.delete(`${API}/workflows/${parent}`)
  }
})
