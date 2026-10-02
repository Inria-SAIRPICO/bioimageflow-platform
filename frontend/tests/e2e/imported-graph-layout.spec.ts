import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`

function graph(name: string) {
  const tool = (id: string, toolName: string) => ({
    type: 'tool', id, name: id, tool_name: toolName, position: [90, 90],
    parameters: toolName === 'IncrementNumbers' ? { number: 1 } : {},
  })
  const edge = (id: string, source: string, target: string) => ({
    type: 'dataframe', id, source_node: source, target_node: target, target_position: 0,
  })
  const child = {
    schema_version: 2, name: 'child', display_name: 'Child layout',
    nodes: [tool('branch_a', 'IncrementNumbers'), tool('orphan', 'SeedNumbers'), tool('source', 'SeedNumbers')],
    edges: [edge('child-edge', 'source', 'branch_a')],
    interface: { inputs: [], outputs: [] },
    config: { engine: 'direct', execution: 'parallel' },
  }
  return {
    schema_version: 2, name, display_name: name,
    nodes: [
      tool('branch_b', 'IncrementNumbers'), tool('source', 'SeedNumbers'), tool('branch_a', 'IncrementNumbers'),
      { type: 'workflow', id: 'nested', name: 'Child layout', position: [90, 90], workflow: child, bindings: {} },
    ],
    edges: [edge('source-b', 'source', 'branch_b'), edge('source-a', 'source', 'branch_a')],
    interface: { inputs: [], outputs: [] },
    config: { engine: 'direct', execution: 'parallel' },
  }
}

type LayoutGraph = ReturnType<typeof graph>

function positions(value: { nodes: Array<{ id: string; position: number[]; workflow?: { nodes: Array<{ id: string; position: number[] }> } }> }) {
  return {
    root: Object.fromEntries(value.nodes.map(node => [node.id, node.position])),
    child: Object.fromEntries(value.nodes.find(node => node.id === 'nested')!.workflow!.nodes.map(node => [node.id, node.position])),
  }
}

async function saved(page: Page, name: string): Promise<{ graph: LayoutGraph }> {
  const response = await page.request.get(`${API}/workflows/${name}`)
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json()
}

async function expectVisibleNodesSeparated(page: Page, count: number) {
  const nodes = page.locator('.vue-flow__node:visible')
  await expect(nodes).toHaveCount(count)
  const boxes = await nodes.evaluateAll(elements => elements.map(element => {
    const { left, top, right, bottom } = element.getBoundingClientRect()
    return { left, top, right, bottom }
  }))
  for (let first = 0; first < boxes.length; first++) {
    for (let second = first + 1; second < boxes.length; second++) {
      const a = boxes[first]!
      const b = boxes[second]!
      expect(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top).toBe(true)
    }
  }
}

test('portable recursive layout materializes once and keeps graph identities separate', async ({ page, request }) => {
  const suffix = `${test.info().project.name}_${Date.now()}`.replace(/[^a-zA-Z0-9_-]/g, '_')
  const source = `layout_source_${suffix}`
  const imported = `layout_imported_${suffix}`
  const other = `layout_other_${suffix}`
  let bodySucceeded = false
  try {
    expect((await page.request.post(`${API}/dev/seed`)).ok()).toBeTruthy()
    expect((await page.request.post(`${API}/workflows`, { data: { name: source } })).status()).toBe(201)
    const original = graph(source)
    const seeded = await page.request.put(`${API}/workflows/${source}`, { data: { graph: original } })
    expect(seeded.ok(), await seeded.text()).toBeTruthy()
    const exportResponse = await page.request.post(`${API}/workflows/${source}/export`)
    expect(exportResponse.ok(), await exportResponse.text()).toBeTruthy()
    const archive = await exportResponse.body()
    for (const name of [imported, other]) {
      const response = await page.request.post(`${API}/workflows/import`, { multipart: {
        name_override: name,
        file: { name: `${source}.bioimageflow.zip`, mimeType: 'application/zip', buffer: archive },
      } })
      expect(response.status(), await response.text()).toBe(201)
    }
    const first = (await saved(page, imported)).graph
    const untouched = (await saved(page, other)).graph
    expect(positions(first)).toEqual(positions(untouched))
    expect(positions(first)).toEqual({
      root: { branch_b: [320, 0], source: [0, 110], branch_a: [320, 220], nested: [0, 660] },
      child: { branch_a: [320, 0], orphan: [0, 440], source: [0, 0] },
    })
    expect(positions(first)).not.toEqual(positions(original))

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
    await page.getByTestId('workflow-search').fill(imported)
    await page.getByTestId(`workflow-row-${imported}`).dblclick()
    await expect(page.getByTestId('workflow-title')).toContainText(imported)
    await expectVisibleNodesSeparated(page, 4)
    await expect(page.locator('.vue-flow__edge:visible')).toHaveCount(2)
    const branch = page.locator('.vue-flow__node[data-id="branch_b"]')
    await expect(branch).toBeVisible()
    const box = await branch.boundingBox()
    expect(box).not.toBeNull()
    const start = { x: box!.x + box!.width / 2, y: box!.y + Math.min(24, box!.height / 2) }
    const accepted = page.waitForResponse(response => response.url().endsWith(`/workflow-drafts/${imported}`)
      && response.request().method() === 'PUT' && response.ok())
    await page.mouse.move(start.x, start.y)
    await page.mouse.down()
    await page.mouse.move(start.x + 55, start.y + 35, { steps: 8 })
    await page.mouse.up()
    await accepted
    const draftResponse = await page.request.get(`${API}/workflow-drafts/${imported}`)
    expect(draftResponse.ok()).toBeTruthy()
    const edited = (await draftResponse.json()).graph
    expect(edited.nodes.find((node: { id: string }) => node.id === 'branch_b').position).not.toEqual([320, 0])
    expect(positions(edited).child).toEqual(positions(first).child)
    expect(positions((await saved(page, other)).graph)).toEqual(positions(untouched))

    // Selection opens docks; fit the current canvas before the nested gesture.
    await page.locator('.vue-flow__controls-fitview').click()
    await page.locator('.vue-flow__node[data-id="nested"]').dblclick()
    await expect(page.locator('.nested-workflow-editor')).toBeVisible()
    await expectVisibleNodesSeparated(page, 3)
    await expect(page.locator('.vue-flow__edge:visible')).toHaveCount(1)
    await page.getByTestId('canvas-tab').filter({ hasText: imported }).click()
    const save = page.waitForResponse(response => response.url().endsWith(`/workflows/${imported}`)
      && response.request().method() === 'PUT' && response.ok())
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await save
    expect(positions((await saved(page, imported)).graph)).toEqual(positions(edited))

    await page.reload()
    await expect(page.getByTestId('workflow-title')).toContainText(imported)
    await expect(page.locator('.vue-flow__node')).toHaveCount(4)
    await expect(page.locator('.vue-flow__edge')).toHaveCount(2)
    const reopened = await page.request.get(`${API}/workflow-drafts/${imported}`)
    expect(reopened.ok()).toBeTruthy()
    expect(positions((await reopened.json()).graph)).toEqual(positions(edited))
    expect(positions((await saved(page, other)).graph)).toEqual(positions(untouched))
    bodySucceeded = true
  } finally {
    // Detach autosave even after timeout; cleanup must not mask the body failure.
    await page.close().catch(() => undefined)
    const cleanup = await Promise.allSettled([imported, other, source].map(name => request.delete(`${API}/workflows/${name}`)))
    if (bodySucceeded) {
      for (const outcome of cleanup) {
        expect(outcome.status).toBe('fulfilled')
        if (outcome.status === 'fulfilled') expect(outcome.value.ok() || outcome.value.status() === 404).toBeTruthy()
      }
    }
  }
})
