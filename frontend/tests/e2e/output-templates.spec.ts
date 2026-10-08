import { expect, test, type Page, type Response } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { basename, dirname, isAbsolute, relative, resolve, sep } from 'node:path'
import type { GraphState, NodeDataResponse, ResultArtifactIdentity, WorkflowFile, WorkflowInfo } from '../../src/api/types'
import type { WorkflowDraftResponse } from '../../src/api/workflowDrafts'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`
const MODULE = 'platform_template_test_tools'

function resolveCapturedAsset(root: string, identity: ResultArtifactIdentity, locator: string): string {
  return execFileSync(resolve('../backend/.venv/bin/python'), ['-c', `
import json, sys
from pathlib import Path
from bioimageflow.storage import Storage
identity = json.loads(sys.argv[2])
store = Storage(Path(sys.argv[1]))
retained = store.read_run_node_result(identity['run_id'], identity['node_key'])
if (retained.result_key, retained.record_id) != (identity['result_key'], identity['record_id']):
    raise ValueError('Captured run/node result does not match its immutable record identity')
print(store.resolve_record_asset(identity['result_key'], identity['record_id'], sys.argv[3]))
`, root, JSON.stringify(identity), locator], { encoding: 'utf8' }).trim()
}

async function draft(page: Page, name: string): Promise<WorkflowDraftResponse> {
  const response = await page.request.get(`${API}/workflow-drafts/${name}`)
  expect(response.ok(), await response.text()).toBeTruthy()
  return await response.json() as WorkflowDraftResponse
}

async function saved(page: Page, name: string): Promise<WorkflowFile> {
  const response = await page.request.get(`${API}/workflows/${name}`)
  expect(response.ok(), await response.text()).toBeTruthy()
  return await response.json() as WorkflowFile
}

async function open(page: Page, name: string, label: string): Promise<void> {
  await page.goto('/')
  await expect(page.locator('#bioimageflow-app')).toBeVisible()
  await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
  await page.getByTestId('workflow-search').fill(name)
  await page.getByTestId(`workflow-row-${name}`).dblclick()
  await expect(page.getByTestId('workflow-title')).toContainText(label)
  await expect(page.locator('.vue-flow__node[data-id="write"]')).toBeVisible()
}

async function query(page: Page, name: string, identity?: ResultArtifactIdentity): Promise<NodeDataResponse> {
  const response = await page.request.post(`${API}/nodes/write/data/query`, {
    data: { workflow_name: name, ...(identity ? { result_identity: identity } : {}) },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  return await response.json() as NodeDataResponse
}

test('output template edits persist and publish distinct files without replacing a pinned result', async ({ page }) => {
  // Public ProcessingTool execution uses the real managed provider. Match the
  // existing two-run worker journeys' provisioning and completion budgets.
  test.setTimeout(180_000)
  const name = `output_templates_${test.info().project.name}_${Date.now()}`
  const label = `Output templates ${name}`
  const graph: GraphState = {
    schema_version: 2, name, display_name: label,
    nodes: [{
      type: 'tool', id: 'write', name: 'Write report', tool_name: 'TemplateReport',
      tool_module: MODULE, tool_class: 'TemplateReport',
      position: [200, 160], parameters: {}, output_templates: { result: 'initial_{row_index}.txt' },
    }],
    edges: [],
    interface: {
      inputs: [],
      outputs: [{ id: 'published-report', name: 'report', schema: { type: 'Path' }, source: { node: 'write', column: 'result' } }],
    },
    config: { engine: 'wetlands', execution: 'sequential' },
  }
  let primaryOccurred = false
  let cleanupFailed = false
  let cleanupFailure: unknown
  try {
    const created = await page.request.post(`${API}/workflows`, { data: { name, display_name: label } })
    expect(created.status(), await created.text()).toBe(201)
    const info = await created.json() as WorkflowInfo
    const installed = await page.request.put(`${API}/workflows/${name}`, { data: { graph } })
    expect(installed.ok(), await installed.text()).toBeTruthy()
    const initial = await draft(page, name)
    expect(initial.validation).toMatchObject({ valid: true, errors: [] })
    expect(initial.validation.node_tools?.write).toMatchObject({
      name: 'TemplateReport', tool_type: 'ProcessingTool', outputs: { result: { type: 'Path' } },
    })
    expect(initial.graph.nodes[0]).toMatchObject({ id: 'write', tool_module: MODULE, tool_class: 'TemplateReport' })
    await open(page, name, label)

    const editAndSave = async (pattern: string) => {
      const beforeEdit = await saved(page, name)
      const beforeNode = beforeEdit.graph.nodes.find(candidate => candidate.id === 'write')
      if (beforeNode?.type !== 'tool' || typeof beforeNode.output_templates?.result !== 'string') {
        throw new Error('Saved workflow has no captured output template')
      }
      await page.locator('.vue-flow__node[data-id="write"]').click()
      await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
      const panel = page.getByTestId('panel-nodePanel')
      await expect(panel.locator('.tool-name')).toHaveText('TemplateReport')
      const input = panel.locator('.output-row').filter({ hasText: 'result' }).getByTestId('output-template')
      await expect(input).toBeEnabled()
      await expect(input).toHaveValue(beforeNode.output_templates.result)
      await input.fill(pattern)
      await expect.poll(async () => {
        const current = await draft(page, name)
        const node = current.graph.nodes.find(candidate => candidate.id === 'write')
        return node?.type === 'tool' ? node.output_templates?.result : null
      }).toBe(pattern)
      const response = page.waitForResponse(candidate => candidate.request().method() === 'PUT'
        && new URL(candidate.url()).pathname === `/api/v1/workflows/${name}`)
      await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
      await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
      const accepted = await response
      expect(accepted.status(), await accepted.text()).toBe(200)
      const document = await saved(page, name)
      expect(document.graph.nodes[0]).toMatchObject({
        id: 'write', tool_module: MODULE, tool_class: 'TemplateReport', output_templates: { result: pattern },
      })
      expect(document.graph.interface).toEqual(initial.graph.interface)
      await open(page, name, label)
      expect((await draft(page, name)).graph).toEqual(document.graph)
      await page.locator('.vue-flow__node[data-id="write"]').click()
      await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
      await expect(input).toHaveValue(pattern)
      return document
    }

    const run = async (filename: string) => {
      const responses: Response[] = []
      const observe = (response: Response) => {
        if (response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/v1/execution/run') responses.push(response)
      }
      page.on('response', observe)
      try {
        await expect(page.getByTestId('run-workflow-button')).toBeEnabled()
        await page.getByTestId('run-workflow-button').click()
        await expect.poll(async () => {
          if (await page.getByTestId('out-of-date-confirm').isVisible()) {
            await page.getByTestId('out-of-date-continue').evaluateAll(buttons => {
              for (const button of buttons) (button as HTMLButtonElement).click()
            })
          }
          return responses.length
        }, { timeout: 15_000 }).toBe(1)
        const response = responses[0]!
        expect(response.status(), await response.text()).toBe(202)
        const execution = await response.json() as { execution_id: string; workflow_id: string; draft_revision: number }
        expect(execution).toMatchObject({ execution_id: expect.any(String), workflow_id: name })
        expect(response.request().postDataJSON()).toMatchObject({ workflow_id: name, draft_revision: execution.draft_revision })
        await expect.poll(async () => {
          const status = await (await page.request.get(`${API}/execution/status`)).json() as {
            execution_id: string; state: string; last_result?: { success: boolean };
          }
          return { id: status.execution_id, state: status.state, success: status.last_result?.success }
        }, { timeout: 60_000 }).toEqual({ id: execution.execution_id, state: 'idle', success: true })
        const data = await query(page, name)
        expect(data.identity_status).toBe('captured')
        expect(data.source_identity).toMatchObject({ node_key: 'write', run_id: expect.any(String), record_id: expect.any(String), result_key: expect.any(String) })
        expect(data.columns).toEqual(['result'])
        expect(data.rows).toHaveLength(1)
        const locator = data.rows[0]!.result
        if (typeof locator !== 'string' || !data.source_identity) throw new Error('Missing captured output locator or identity')
        expect(locator).toBe(`assets/${filename}`)
        const path = resolveCapturedAsset(info.results_path, data.source_identity, locator)
        expect(isAbsolute(path)).toBe(true)
        const withinResults = relative(info.results_path, path)
        expect(withinResults).not.toBe('..')
        expect(withinResults.startsWith(`..${sep}`)).toBe(false)
        expect(isAbsolute(withinResults)).toBe(false)
        expect(basename(path)).toBe(filename)
        expect(basename(dirname(path))).toBe('assets')
        expect(readFileSync(path, 'utf8')).toBe('ok')
        return { data, identity: data.source_identity, locator, path, execution }
      } finally {
        page.off('response', observe)
      }
    }

    await editAndSave('first_{row_index}.txt')
    const first = await run('first_0.txt')
    expect(await query(page, name, first.identity)).toEqual(first.data)
    const secondSaved = await editAndSave('second_{row_index}.txt')
    const second = await run('second_0.txt')
    expect(second.execution.execution_id).not.toBe(first.execution.execution_id)
    expect(second.identity.run_id).not.toBe(first.identity.run_id)
    expect(second.identity.result_key).not.toBe(first.identity.result_key)
    expect(second.identity.record_id).not.toBe(first.identity.record_id)
    expect(dirname(second.path)).not.toBe(dirname(first.path))
    expect(await query(page, name, first.identity)).toEqual(first.data)
    expect(readFileSync(first.path, 'utf8')).toBe('ok')
    expect(readFileSync(second.path, 'utf8')).toBe('ok')
    expect((await saved(page, name)).graph).toEqual(secondSaved.graph)
  } catch (error) {
    primaryOccurred = true
    throw error
  } finally {
    for (const cleanup of [
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
        }, { timeout: 60_000 }).toBe('idle')
      },
      async () => {
        let status = 423
        let detail = ''
        try {
          await expect.poll(async () => {
            const removed = await page.request.delete(`${API}/workflows/${name}`)
            status = removed.status()
            detail = await removed.text()
            return status
          }, { timeout: 15_000 }).not.toBe(423)
          expect([200, 204, 404], detail).toContain(status)
        } catch (error) {
          console.error('Owned output-template workflow deletion failed:', { status, detail })
          throw error
        }
      },
    ]) {
      try { await cleanup() } catch (error) {
        if (primaryOccurred) console.error('Output-template cleanup failed while preserving the primary:', error)
        else if (!cleanupFailed) { cleanupFailed = true; cleanupFailure = error }
      }
    }
  }
  if (cleanupFailed) throw cleanupFailure
})
