import { expect, test, type Page, type Request, type Response } from '@playwright/test'
import { readFileSync } from 'node:fs'
import type { GraphState, WorkflowFile, WorkflowInfo } from '../../src/api/types'
import type { WorkflowDraftResponse } from '../../src/api/workflowDrafts'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`

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

function resourceValues(graph: GraphState): Record<string, number | string> {
  const node = graph.nodes.find(candidate => candidate.id === 'write')
  if (node?.type !== 'tool') throw new Error('Accepted graph has no processing node')
  return Object.fromEntries(Object.entries(node.resources ?? {}).filter(([, value]) =>
    typeof value === 'number' || typeof value === 'string')) as Record<string, number | string>
}

function withoutWriteResources(graph: GraphState): GraphState {
  const copy = structuredClone(graph)
  const node = copy.nodes.find(candidate => candidate.id === 'write')
  if (node?.type !== 'tool') throw new Error('Accepted graph has no processing node')
  delete node.resources
  return copy
}

function draftResponse(page: Page, name: string, status: number): Promise<Response> {
  return page.waitForResponse(response => response.request().method() === 'PUT'
    && new URL(response.url()).pathname === `/api/v1/workflow-drafts/${name}`
    && response.status() === status)
}

async function openResources(page: Page, name: string, label: string): Promise<void> {
  await page.goto('/')
  await expect(page.locator('#bioimageflow-app')).toBeVisible()
  const panel = page.getByTestId('workflows-panel')
  if (!await panel.isVisible()) {
    const catalogGroup = page.locator('.dv-groupview').filter({
      has: page.locator('.tools-panel, .datasets-panel, [data-testid="workflows-panel"]'),
    })
    await expect(catalogGroup).toHaveCount(1)
    await catalogGroup.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
  }
  await expect(panel).toBeVisible()
  await panel.getByTestId('workflow-search').fill(name)
  await panel.getByTestId(`workflow-row-${name}`).dblclick()
  await expect(page.getByTestId('workflow-title')).toHaveText(label)
  await page.locator('.vue-flow__node[data-id="write"]').click()
  await page.locator('.dv-tab').filter({ hasText: /^Nodes$/ }).click()
  await expect(page.getByTestId('panel-nodePanel').locator('.tool-name')).toHaveText('TemplateReport')
  await page.getByTestId('node-tab-resources').click()
  await expect(page.getByTestId('node-resources-tab')).toBeVisible()
}

async function save(page: Page, name: string): Promise<void> {
  let savedResponseSeen = false
  const response = page.waitForResponse(candidate => {
    const matches = candidate.request().method() === 'PUT'
      && new URL(candidate.url()).pathname === `/api/v1/workflows/${name}`
    if (matches) savedResponseSeen = true
    return matches
  })
  const postSaveDraft = page.waitForResponse(candidate => savedResponseSeen
    && candidate.request().method() === 'PUT'
    && new URL(candidate.url()).pathname === `/api/v1/workflow-drafts/${name}`
    && candidate.status() === 200)
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
  const accepted = await response
  expect(accepted.status(), await accepted.text()).toBe(200)
  const cleanDraft = await (await postSaveDraft).json() as WorkflowDraftResponse
  expect(cleanDraft.dirty_against_saved).toBe(false)
  await expect(page.getByTestId('workflow-title')).toHaveText(cleanDraft.graph.display_name)
}

test('processing resources persist, reset and recover from a refused capacity without running', async ({ page }) => {
  // Four complete Save/reopen phases share this case budget; individual UI,
  // HTTP and cleanup waits remain unchanged and no worker is provisioned.
  test.setTimeout(60_000)
  const name = `node_resources_${test.info().project.name}_${Date.now()}`
  const label = `Node resources ${name}`
  const graph: GraphState = {
    schema_version: 2, name, display_name: label,
    nodes: [
      {
        type: 'tool', id: 'write', name: 'Write report', tool_name: 'TemplateReport',
        enabled: true, collapsed: false,
        tool_module: 'platform_template_test_tools', tool_class: 'TemplateReport',
        position: [220, 160], parameters: {}, output_templates: { result: 'retained_{row_index}.txt' },
      },
      {
        type: 'tool', id: 'seed', name: 'Unexecuted scalar source', tool_name: 'SeedNumbers',
        enabled: true, collapsed: false,
        tool_module: 'bioimageflow_dev_tools.tools', tool_class: 'SeedNumbers',
        position: [500, 160], parameters: {},
      },
    ],
    edges: [],
    interface: {
      inputs: [],
      outputs: [{ id: 'published-report', name: 'report', schema: { type: 'Path' }, source: { node: 'write', column: 'result' } }],
    },
    config: { engine: 'wetlands', execution: 'sequential' },
  }
  let primaryOccurred = false
  const cleanupErrors: unknown[] = []
  const runRequests: string[] = []
  const observeRun = (request: Request) => {
    if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/v1/execution/run') {
      runRequests.push(request.postData() ?? '')
    }
  }
  page.on('request', observeRun)
  try {
    const created = await page.request.post(`${API}/workflows`, { data: { name, display_name: label } })
    expect(created.status(), await created.text()).toBe(201)
    const info = await created.json() as WorkflowInfo
    const installed = await page.request.put(`${API}/workflows/${name}`, { data: { graph } })
    expect(installed.status(), await installed.text()).toBe(200)
    const initial = await draft(page, name)
    expect(initial.validation).toMatchObject({ valid: true, errors: [] })
    expect(initial.validation.node_tools?.write).toMatchObject({
      name: 'TemplateReport', tool_type: 'ProcessingTool', outputs: { result: { type: 'Path' } },
    })
    expect(initial.validation.node_tools?.seed).toMatchObject({
      name: 'SeedNumbers', tool_type: 'DataFrameTool', outputs: { number: { type: 'int' }, label: { type: 'str' } },
    })
    const unaffected = withoutWriteResources(initial.graph)
    const seedMetadata = initial.validation.node_tools?.seed
    await openResources(page, name, label)
    const cpu = page.getByTestId('resource-override-cpu').locator('input')
    const memory = page.getByTestId('resource-override-memory')
    await expect(cpu).toHaveValue('')
    await expect(memory).toHaveValue('')
    await expect(page.getByTestId('resource-reset-all')).toBeDisabled()

    const cpuAccepted = draftResponse(page, name, 200)
    await cpu.fill('2')
    await cpu.press('Tab')
    await cpuAccepted
    const memoryAccepted = draftResponse(page, name, 200)
    await memory.fill('16GB')
    await memoryAccepted
    const edited = await draft(page, name)
    expect(resourceValues(edited.graph)).toEqual({ cpu: 2, memory: '16GB' })
    expect(withoutWriteResources(edited.graph)).toEqual(unaffected)
    expect(edited.validation.node_tools?.seed).toEqual(seedMetadata)
    await save(page, name)
    const savedEdited = await saved(page, name)
    expect(resourceValues(savedEdited.graph)).toEqual({ cpu: 2, memory: '16GB' })
    await openResources(page, name, label)
    await expect(cpu).toHaveValue('2')
    await expect(memory).toHaveValue('16GB')
    expect((await draft(page, name)).graph).toEqual(savedEdited.graph)

    const resetAccepted = draftResponse(page, name, 200)
    await page.getByTestId('resource-reset-all').click()
    await resetAccepted
    expect(resourceValues((await draft(page, name)).graph)).toEqual({})
    await save(page, name)
    await openResources(page, name, label)
    await expect(cpu).toHaveValue('')
    await expect(memory).toHaveValue('')
    await expect(page.getByTestId('resource-reset-all')).toBeDisabled()
    const beforeRefusal = await draft(page, name)
    const savedBeforeRefusal = await saved(page, name)
    const fileBeforeRefusal = readFileSync(info.path)
    expect(withoutWriteResources(beforeRefusal.graph)).toEqual(unaffected)

    const refused = draftResponse(page, name, 422)
    await memory.fill('invalid')
    const refusal = await refused
    expect(await refusal.text()).toContain('integral capacity')
    await expect(page.getByTestId('canvas-persistence-issue')).toBeVisible()
    expect(await draft(page, name)).toEqual(beforeRefusal)
    expect(await saved(page, name)).toEqual(savedBeforeRefusal)
    expect(readFileSync(info.path)).toEqual(fileBeforeRefusal)
    // The visible invalid edit is unsaved. Repair it instead of invoking Run
    // against the still-valid accepted draft or assuming an implicit rollback.
    const repaired = draftResponse(page, name, 200)
    await memory.fill('8GiB')
    await repaired
    await expect(page.getByTestId('canvas-persistence-issue')).not.toBeVisible()
    const acceptedRepair = await draft(page, name)
    expect(resourceValues(acceptedRepair.graph)).toEqual({ memory: '8GiB' })
    expect(withoutWriteResources(acceptedRepair.graph)).toEqual(unaffected)
    expect(acceptedRepair.validation.node_tools?.seed).toEqual(seedMetadata)
    await save(page, name)
    await openResources(page, name, label)
    await expect(memory).toHaveValue('8GiB')
    await expect(cpu).toHaveValue('')
    expect((await draft(page, name)).graph).toEqual((await saved(page, name)).graph)

    await page.locator('.vue-flow__node[data-id="seed"]').click()
    await page.getByTestId('node-tab-resources').click()
    await expect(page.getByTestId('node-resources-unavailable')).toHaveText('Worker resource overrides apply only to processing tools.')
    await expect(page.getByTestId('node-resources-tab')).toHaveCount(0)
    expect(withoutWriteResources((await saved(page, name)).graph)).toEqual(unaffected)
    const status = await page.request.get(`${API}/execution/status`)
    expect(status.ok(), await status.text()).toBeTruthy()
    expect((await status.json()).state).toBe('idle')
    expect(runRequests).toEqual([])
  } catch (error) {
    primaryOccurred = true
    throw error
  } finally {
    try { await page.goto('about:blank') } catch (error) { cleanupErrors.push(error) }
    let detail = ''
    try {
      await expect.poll(async () => {
        const response = await page.request.delete(`${API}/workflows/${name}`)
        detail = await response.text()
        if ([200, 204, 404].includes(response.status())) return true
        if (response.status() !== 423) throw new Error(`Workflow cleanup ${response.status()}: ${detail}`)
        return false
      }, { timeout: 15_000, message: 'Owned workflow cleanup must settle its exact pending mutation' }).toBe(true)
    } catch (error) { cleanupErrors.push(new Error(`${String(error)}; last cleanup response: ${detail}`)) }
    page.off('request', observeRun)
    if (cleanupErrors.length) {
      await test.info().attach('node-resource-cleanup-errors', {
        body: Buffer.from(cleanupErrors.map(String).join('\n')), contentType: 'text/plain',
      }).catch(() => undefined)
    }
  }
  if (!primaryOccurred && cleanupErrors.length) throw cleanupErrors[0]
})
