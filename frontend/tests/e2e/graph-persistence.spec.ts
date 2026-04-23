/**
 * End-to-end test for graph persistence across page reloads.
 *
 * Guarantees that both nodes AND edges saved to IndexedDB are restored
 * and rendered after the page reloads. Regression coverage for the bug
 * where edges were present in storage but absent from the DOM on reload.
 */
import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

type ToolMetadata = {
  name: string
  inputs: Record<string, { type: string; connectable?: boolean }>
  outputs: Record<string, { type: string }>
  [k: string]: unknown
}

async function clearWorkflowDB(page: Page) {
  await page.evaluate(() => {
    return new Promise<void>((resolve) => {
      const req = indexedDB.deleteDatabase('bioimageflow')
      req.onsuccess = () => resolve()
      req.onerror = () => resolve()
      req.onblocked = () => resolve()
    })
  })
}

async function seedWorkflow(
  page: Page,
  workflow: { nodes: unknown[]; edges: unknown[] },
) {
  await page.evaluate((wf) => {
    return new Promise<void>((resolve, reject) => {
      const req = indexedDB.open('bioimageflow', 1)
      req.onupgradeneeded = () => {
        const db = req.result
        if (!db.objectStoreNames.contains('workflows')) {
          db.createObjectStore('workflows')
        }
      }
      req.onsuccess = () => {
        const db = req.result
        const tx = db.transaction('workflows', 'readwrite')
        tx.objectStore('workflows').put(wf, 'current')
        tx.oncomplete = () => {
          db.close()
          resolve()
        }
        tx.onerror = () => reject(tx.error)
      }
      req.onerror = () => reject(req.error)
    })
  }, workflow)
}

async function fetchAnyTool(page: Page): Promise<{
  tool: ToolMetadata
  outputName: string
  inputName: string
}> {
  const tools = await page.evaluate(async () => {
    const r = await fetch('/api/v1/tools')
    return (await r.json()) as ToolMetadata[]
  })
  const tool = tools.find(
    (t) =>
      Object.values(t.outputs).length > 0 &&
      Object.values(t.inputs).some((f) => f.connectable),
  )
  if (!tool) {
    throw new Error('No tool found with both a connectable input and an output')
  }
  const [outputName] = Object.keys(tool.outputs)
  const inputEntry = Object.entries(tool.inputs).find(
    ([, f]) => f.connectable,
  )!
  return { tool, outputName, inputName: inputEntry[0] }
}

function buildNode(
  id: string,
  name: string,
  x: number,
  tool: ToolMetadata,
  opts: {
    connectedInputs?: Record<string, string>
    pinnedInputs?: Record<string, boolean>
  } = {},
) {
  return {
    id,
    type: 'tool',
    position: { x, y: 100 },
    data: {
      name,
      toolName: tool.name,
      tool,
      status: 'unexecuted',
      parameters: {},
      resources: {},
      output_templates: {},
      collapsed: false,
      enabled: true,
      connectedInputs: opts.connectedInputs ?? {},
      pinnedInputs: opts.pinnedInputs ?? {},
    },
  }
}

test.describe('graph persistence across reloads', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await expect(page.locator('.canvas-view')).toBeVisible()
    await clearWorkflowDB(page)
  })

  test('edges are restored and visible in the DOM after reload', async ({
    page,
  }) => {
    const { tool, outputName, inputName } = await fetchAnyTool(page)

    const source = buildNode('src_node', 'Source', 100, tool)
    const target = buildNode('tgt_node', 'Target', 500, tool, {
      connectedInputs: { [inputName]: `Source.${outputName}` },
      pinnedInputs: { [inputName]: true },
    })
    const edge = {
      id: `e-src_node-${outputName}-tgt_node-${inputName}`,
      source: 'src_node',
      target: 'tgt_node',
      sourceHandle: outputName,
      targetHandle: inputName,
      type: 'column_ref',
    }

    await seedWorkflow(page, { nodes: [source, target], edges: [edge] })
    await page.reload()
    await expect(page.locator('#bioimageflow-app')).toBeVisible()

    // Both nodes must be rendered.
    await expect(page.locator('.vue-flow__node')).toHaveCount(2, {
      timeout: 5000,
    })
    await expect(page.locator('.vue-flow__node[data-id="src_node"]')).toBeVisible()
    await expect(page.locator('.vue-flow__node[data-id="tgt_node"]')).toBeVisible()

    // The edge must exist AND have a valid SVG path (non-empty `d` attribute).
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1, {
      timeout: 5000,
    })
    const edgePath = page.locator('.vue-flow__edge path.vue-flow__edge-path').first()
    await expect(edgePath).toBeVisible()
    const d = await edgePath.getAttribute('d')
    expect(d).toBeTruthy()
    // A real bezier path is long; a broken one is empty, "M 0 0" or "M NaN NaN".
    expect(d!.length).toBeGreaterThan(10)
    expect(d).not.toContain('NaN')
  })

  test('multi-edge workflow reloads intact', async ({ page }) => {
    const { tool, outputName, inputName } = await fetchAnyTool(page)

    const n1 = buildNode('a', 'A', 100, tool)
    const n2 = buildNode('b', 'B', 400, tool, {
      connectedInputs: { [inputName]: `A.${outputName}` },
      pinnedInputs: { [inputName]: true },
    })
    const n3 = buildNode('c', 'C', 700, tool, {
      connectedInputs: { [inputName]: `B.${outputName}` },
      pinnedInputs: { [inputName]: true },
    })
    const edges = [
      {
        id: `e-a-${outputName}-b-${inputName}`,
        source: 'a',
        target: 'b',
        sourceHandle: outputName,
        targetHandle: inputName,
        type: 'column_ref',
      },
      {
        id: `e-b-${outputName}-c-${inputName}`,
        source: 'b',
        target: 'c',
        sourceHandle: outputName,
        targetHandle: inputName,
        type: 'column_ref',
      },
    ]

    await seedWorkflow(page, { nodes: [n1, n2, n3], edges })
    await page.reload()
    await expect(page.locator('#bioimageflow-app')).toBeVisible()

    await expect(page.locator('.vue-flow__node')).toHaveCount(3, {
      timeout: 5000,
    })
    await expect(page.locator('.vue-flow__edge')).toHaveCount(2, {
      timeout: 5000,
    })

    // All edge paths must have valid geometry.
    const paths = page.locator('.vue-flow__edge path.vue-flow__edge-path')
    const count = await paths.count()
    for (let i = 0; i < count; i++) {
      const d = await paths.nth(i).getAttribute('d')
      expect(d).toBeTruthy()
      expect(d!.length).toBeGreaterThan(10)
      expect(d).not.toContain('NaN')
    }
  })

  test('round-trip: create graph in-app, reload, edges still rendered', async ({
    page,
  }) => {
    const { tool, outputName, inputName } = await fetchAnyTool(page)

    // Seed directly — simulates state that was previously saved by the app
    // without relying on drag-connect (which is fragile in headless).
    const source = buildNode('round_src', 'Source', 100, tool)
    const target = buildNode('round_tgt', 'Target', 500, tool, {
      connectedInputs: { [inputName]: `Source.${outputName}` },
      pinnedInputs: { [inputName]: true },
    })
    const edge = {
      id: `e-round_src-${outputName}-round_tgt-${inputName}`,
      source: 'round_src',
      target: 'round_tgt',
      sourceHandle: outputName,
      targetHandle: inputName,
      type: 'column_ref',
    }

    await seedWorkflow(page, { nodes: [source, target], edges: [edge] })
    await page.reload()
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1, {
      timeout: 5000,
    })

    // Now reload again — the first post-reload save-cycle (syncGraph → sendNow)
    // must preserve edges in IndexedDB. If the save path strips edges, the
    // second reload would come back with zero edges.
    await page.waitForTimeout(800) // past the 300ms syncGraph debounce
    await page.reload()
    await expect(page.locator('.vue-flow__node')).toHaveCount(2, {
      timeout: 5000,
    })
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1, {
      timeout: 5000,
    })
  })
})
