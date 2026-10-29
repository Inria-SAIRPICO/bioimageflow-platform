import { expect, test } from '@playwright/test'
import type { Locator } from '@playwright/test'
import type { GraphState, ToolMetadata, WorkflowDraftResponse, WorkflowInfo } from '../../src/api/types'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`

test('column strands follow real mapped, collective, workflow and repaired target metadata', async ({ page }) => {
  const name = `edge_geometry_${test.info().project.name}_${Date.now()}`
  let info: WorkflowInfo | null = null
  let primaryOccurred = false
  let cleanupFailed = false
  let cleanupFailure: unknown
  let runRequests = 0
  page.on('request', request => {
    if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/v1/execution/run') runRequests += 1
  })
  const child: GraphState = {
    schema_version: 2, name: 'geometry_child', display_name: 'Geometry child',
    nodes: [{ type: 'tool', id: 'inner', name: 'Inner mapped', tool_name: 'ParameterControls', parameters: {}, position: [100, 100] }],
    edges: [],
    interface: {
      inputs: [{ id: 'public-number', name: 'Published number', kind: 'field', schema: { type: 'int' },
        targets: [{ node: 'inner', port: { kind: 'field', name: 'connected_number' } }] }],
      outputs: [],
    },
    config: { engine: 'direct', execution: 'sequential' },
  }
  const graph: GraphState = {
    schema_version: 2, name, display_name: name,
    nodes: [
      { type: 'tool', id: 'source', name: 'Number source', tool_name: 'SeedNumbers', parameters: {}, position: [50, 230] },
      { type: 'tool', id: 'mapped', name: 'Mapped target', tool_name: 'ParameterControls', parameters: {}, position: [450, 40] },
      { type: 'tool', id: 'collective', name: 'Collective target', tool_name: 'CollectiveNumbers', parameters: {}, position: [450, 200] },
      { type: 'workflow', id: 'workflow', name: 'Workflow target', workflow: child, bindings: {}, position: [450, 360] },
      { type: 'tool', id: 'unknown', name: 'Unavailable target', tool_name: 'UnavailableGeometryTool', parameters: {}, position: [450, 520] },
    ],
    edges: [
      { type: 'column', id: 'edge-mapped', source_node: 'source', source_output: 'number', target_node: 'mapped', target_input: 'connected_number' },
      { type: 'column', id: 'edge-collective', source_node: 'source', source_output: 'number', target_node: 'collective', target_input: 'number' },
      { type: 'column', id: 'edge-workflow', source_node: 'source', source_output: 'number', target_node: 'workflow', target_input: 'public-number' },
      { type: 'column', id: 'edge-unknown', source_node: 'source', source_output: 'number', target_node: 'unknown', target_input: 'connected_number' },
    ],
    interface: { inputs: [], outputs: [] },
    config: { engine: 'direct', execution: 'sequential' },
  }
  const paths = (id: string) => page.locator(`.vue-flow__edge[data-id="${id}"] .vue-flow__edge-path`)
  const geometry = async (id: string) => paths(id).evaluateAll(elements => elements.map(element => {
    const path = element as SVGPathElement
    const transform = path.getScreenCTM()
    if (!transform || path.getTotalLength() <= 0) throw new Error('Expected a rendered column path')
    const start = path.getPointAtLength(0).matrixTransform(transform)
    const end = path.getPointAtLength(path.getTotalLength()).matrixTransform(transform)
    return { start: { x: start.x, y: start.y }, end: { x: end.x, y: end.y } }
  }))
  const inputAnchor = async (locator: Locator) => {
    const bounds = await locator.boundingBox()
    expect(bounds).not.toBeNull()
    return { x: bounds!.x, y: bounds!.y + bounds!.height / 2 }
  }
  const distance = (a: { x: number; y: number }, b: { x: number; y: number }) => Math.hypot(a.x - b.x, a.y - b.y)
  try {
    expect((await page.request.post(`${API}/dev/seed`)).ok()).toBe(true)
    const catalogResponse = await page.request.get(`${API}/tools`)
    expect(catalogResponse.ok(), await catalogResponse.text()).toBe(true)
    const catalog = await catalogResponse.json() as ToolMetadata[]
    expect(catalog.find(tool => tool.name === 'ParameterControls')).toMatchObject({ row_consumption: 'mapped' })
    expect(catalog.find(tool => tool.name === 'CollectiveNumbers')).toMatchObject({ row_consumption: 'collective' })
    expect(catalog.some(tool => tool.name === 'UnavailableGeometryTool')).toBe(false)
    const created = await page.request.post(`${API}/workflows`, { data: { name, display_name: name } })
    expect(created.status(), await created.text()).toBe(201)
    info = await created.json() as WorkflowInfo
    const saved = await page.request.put(`${API}/workflows/${name}`, { data: { graph } })
    expect(saved.ok(), await saved.text()).toBe(true)
    // Startup may already open this graph. Capture that real response before
    // navigation instead of waiting for an unnecessary second Open request.
    const startup = page.waitForResponse(response => response.ok() && response.request().method() === 'GET'
      && new URL(response.url()).pathname.startsWith('/api/v1/workflow-drafts/'))
    await page.goto('/')
    let openedResponse = await startup
    const initialDraft = await openedResponse.json() as WorkflowDraftResponse
    await expect(page.getByTestId('workflow-title')).toContainText(initialDraft.graph.display_name)
    const dependencies = page.getByTestId('missing-package-dialog')
    if (initialDraft.workflow_id !== name) {
      if (await dependencies.isVisible()) await dependencies.locator('.p-dialog-footer').getByRole('button', { name: 'Close', exact: true }).click()
      await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
      await page.getByTestId('workflow-search').fill(name)
      const opened = page.waitForResponse(response => response.request().method() === 'GET'
        && new URL(response.url()).pathname === `/api/v1/workflow-drafts/${name}`)
      await page.getByTestId(`workflow-row-${name}`).dblclick()
      openedResponse = await opened
    }
    expect(openedResponse.ok(), await openedResponse.text()).toBe(true)
    const accepted = await openedResponse.json() as WorkflowDraftResponse
    expect(accepted.validation.valid).toBe(false)
    expect(accepted.validation.errors).toEqual(expect.arrayContaining([expect.objectContaining({ type: 'missing_tool', node: 'unknown' })]))
    await expect(page.getByTestId('workflow-title')).toHaveText(name)
    await expect(dependencies).toBeVisible()
    await expect(dependencies).toContainText('UnavailableGeometryTool')
    await dependencies.locator('.p-dialog-footer').getByRole('button', { name: 'Close', exact: true }).click()
    await expect(page.locator('.vue-flow__node')).toHaveCount(5)
    for (const [id, count] of [['edge-mapped', 3], ['edge-collective', 3], ['edge-workflow', 1], ['edge-unknown', 1]] as const) {
      await expect(paths(id)).toHaveCount(count)
    }
    const mapped = await geometry('edge-mapped')
    const collective = await geometry('edge-collective')
    for (const strands of [mapped, collective]) {
      expect(distance(strands[0]!.start, strands[2]!.start)).toBeGreaterThan(0.5)
    }
    expect(distance(mapped[0]!.end, mapped[2]!.end)).toBeGreaterThan(0.5)
    expect(distance(collective[0]!.end, collective[1]!.end)).toBeLessThan(0.01)
    expect(distance(collective[1]!.end, collective[2]!.end)).toBeLessThan(0.01)
    const mappedPin = page.locator('.vue-flow__node[data-id="mapped"] [data-handleid="bif:v1:tool-input:connected_number"]')
    const collectivePin = page.locator('.vue-flow__node[data-id="collective"] [data-handleid="bif:v1:tool-input:number"]')
    const workflowPin = page.locator('.vue-flow__node[data-id="workflow"] [data-handleid="bif:v1:workflow-input:public-number"]')
    expect(distance(mapped[1]!.end, await inputAnchor(mappedPin))).toBeLessThan(1.5)
    expect(distance(collective[1]!.end, await inputAnchor(collectivePin))).toBeLessThan(1.5)
    const workflowBefore = await geometry('edge-workflow')
    expect(distance(workflowBefore[0]!.end, await inputAnchor(workflowPin))).toBeLessThan(1.5)
    const unknownNode = page.locator('.vue-flow__node[data-id="unknown"]')
    await expect(unknownNode.getByText('Missing', { exact: true })).toBeVisible()
    await expect(unknownNode.locator('.body-inputs .vue-flow__handle')).toHaveCount(0)
    const unknownBounds = await unknownNode.boundingBox()
    expect(unknownBounds).not.toBeNull()
    const unknown = await geometry('edge-unknown')
    expect(distance(unknown[0]!.end, { x: unknownBounds!.x + unknownBounds!.width / 2, y: unknownBounds!.y })).toBeLessThan(1.5)

    // A normal accepted external draft repairs the unavailable class. The
    // frontend must derive the new strands from that node's real metadata.
    const repairedGraph = structuredClone(accepted.graph)
    const repairedNode = repairedGraph.nodes.find(node => node.id === 'unknown')!
    if (repairedNode.type !== 'tool') throw new Error('Expected a tool target')
    repairedNode.tool_name = 'ParameterControls'
    const repairResponse = await page.request.put(`${API}/workflow-drafts/${name}`, {
      data: { graph: repairedGraph, expected_revision: accepted.draft_revision, updated_by: 'agent' },
    })
    expect(repairResponse.ok(), await repairResponse.text()).toBe(true)
    const repaired = await repairResponse.json() as WorkflowDraftResponse
    expect(repaired.validation).toMatchObject({ valid: true, errors: [] })
    const acceptedTarget = repaired.graph.nodes.find(node => node.id === 'unknown')
    expect(acceptedTarget).toEqual(repairedNode)
    expect(catalog.find(tool => acceptedTarget?.type === 'tool' && tool.name === acceptedTarget.tool_name))
      .toMatchObject({ name: 'ParameterControls', row_consumption: 'mapped' })
    await expect(unknownNode.getByText('Missing', { exact: true })).toHaveCount(0)
    await expect(paths('edge-unknown')).toHaveCount(3)
    const repairedPaths = await geometry('edge-unknown')
    expect(distance(repairedPaths[0]!.end, repairedPaths[2]!.end)).toBeGreaterThan(0.5)
    expect(distance(repairedPaths[1]!.end, await inputAnchor(unknownNode.locator('[data-handleid="bif:v1:tool-input:connected_number"]')))).toBeLessThan(1.5)
    await expect(paths('edge-workflow')).toHaveCount(1)
    const workflowAfter = await geometry('edge-workflow')
    const sourcePin = page.locator('.vue-flow__node[data-id="source"] [data-handleid="bif:v1:tool-output:number"]')
    const sourceBounds = await sourcePin.boundingBox()
    expect(sourceBounds).not.toBeNull()
    expect(distance(workflowAfter[0]!.start, {
      x: sourceBounds!.x + sourceBounds!.width, y: sourceBounds!.y + sourceBounds!.height / 2,
    })).toBeLessThan(1.5)
    expect(distance(workflowAfter[0]!.end, await inputAnchor(workflowPin))).toBeLessThan(1.5)
    const finalResponse = await page.request.get(`${API}/workflow-drafts/${name}`)
    expect(finalResponse.ok(), await finalResponse.text()).toBe(true)
    const finalDraft = await finalResponse.json() as WorkflowDraftResponse
    expect(finalDraft.graph).toEqual(repairedGraph)
    expect(finalDraft.draft_revision).toBe(repaired.draft_revision)
    expect((await (await page.request.get(`${API}/workflows/${name}`)).json()).graph).toEqual(accepted.graph)
    expect(runRequests).toBe(0)
  } catch (error) {
    primaryOccurred = true
    throw error
  } finally {
    for (const cleanup of [
      () => page.goto('about:blank'),
      async () => {
        if (!info) return
        const response = await page.request.delete(`${API}/workflows/${name}`, { params: { expected_identity_generation: info.identity_generation } })
        expect(response.ok(), await response.text()).toBe(true)
      },
    ]) {
      try { await cleanup() } catch (error) {
        if (primaryOccurred) console.error('Edge geometry cleanup failed while preserving the primary:', error)
        else if (!cleanupFailed) { cleanupFailed = true; cleanupFailure = error }
      }
    }
  }
  if (cleanupFailed) throw cleanupFailure
})
