/**
 * End-to-end test for workflow-scoped auto-save recovery.
 *
 * Regression coverage for the old global IndexedDB key (`bioimageflow/current`):
 * recovery now uses `bioimageflow-autosave`, keyed by workflow name, after the
 * server workflow is loaded.
 */
import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

type ToolMetadata = {
  name: string
  inputs: Record<string, { type: string; connectable?: string | boolean }>
  outputs: Record<string, { type: string }>
  [k: string]: unknown
}

type GraphState = {
  nodes: Array<Record<string, unknown>>
  edges: Array<Record<string, unknown>>
}

function uniqueName(prefix: string): string {
  const project = test.info().project.name.replace(/[^a-zA-Z0-9_-]/g, '_')
  return `${prefix}_${project}_${Date.now()}_${Math.floor(Math.random() * 10000)}`
}

async function deleteWorkflowIfExists(page: Page, name: string) {
  await page.request.delete(`${API_BASE}/api/v1/workflows/${name}`).catch(() => undefined)
}

async function fetchAnyTool(page: Page): Promise<{
  tool: ToolMetadata
  outputName: string
  inputName: string
}> {
  const response = await page.request.get(`${API_BASE}/api/v1/tools`)
  expect(response.ok()).toBeTruthy()
  const tools = (await response.json()) as ToolMetadata[]
  const tool = tools.find(
    (candidate) =>
      Object.keys(candidate.outputs).length > 0 &&
      Object.values(candidate.inputs).some((field) => field.connectable !== 'never'),
  )
  if (!tool) {
    throw new Error('No tool found with both a connectable input and an output')
  }
  const [outputName] = Object.keys(tool.outputs)
  const inputEntry = Object.entries(tool.inputs).find(
    ([, field]) => field.connectable !== 'never',
  )!
  return { tool, outputName, inputName: inputEntry[0] }
}

async function createServerWorkflow(page: Page, name: string, graph: GraphState) {
  const create = await page.request.post(`${API_BASE}/api/v1/workflows`, {
    data: { name, display_name: name },
  })
  expect([201, 409]).toContain(create.status())
  const save = await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
    data: { graph },
  })
  expect(save.ok()).toBeTruthy()
}

async function seedWorkflowAutoSave(page: Page, name: string, graph: GraphState) {
  await page.evaluate(
    ({ workflowName, workflowGraph }) => new Promise<void>((resolve, reject) => {
      const req = indexedDB.open('bioimageflow-autosave', 1)
      req.onupgradeneeded = () => {
        const db = req.result
        if (!db.objectStoreNames.contains('workflows')) {
          db.createObjectStore('workflows', { keyPath: 'name' })
        }
        if (!db.objectStoreNames.contains('preferences')) {
          db.createObjectStore('preferences')
        }
      }
      req.onsuccess = () => {
        const db = req.result
        const tx = db.transaction(['workflows', 'preferences'], 'readwrite')
        tx.objectStore('workflows').put({
          name: workflowName,
          graph: workflowGraph,
          timestamp: Date.now(),
        })
        tx.objectStore('preferences').put(workflowName, 'last_opened_workflow')
        tx.oncomplete = () => {
          db.close()
          resolve()
        }
        tx.onerror = () => reject(tx.error)
      }
      req.onerror = () => reject(req.error)
    }),
    { workflowName: name, workflowGraph: graph },
  )
}

function graphWithEdge(tool: ToolMetadata, outputName: string, inputName: string): GraphState {
  return {
    nodes: [
      {
        id: 'src_node',
        name: 'Source',
        tool_name: tool.name,
        position: [100, 100],
        parameters: {},
      },
      {
        id: 'tgt_node',
        name: 'Target',
        tool_name: tool.name,
        position: [500, 100],
        parameters: {},
      },
    ],
    edges: [
      {
        type: 'column_ref',
        id: `e-src_node-${outputName}-tgt_node-${inputName}`,
        source_node: 'src_node',
        target_node: 'tgt_node',
        source_output: outputName,
        target_input: inputName,
      },
    ],
  }
}

test.describe('workflow-scoped graph recovery', () => {
  test('auto-saved graph restores nodes and edges after reload', async ({ page }) => {
    const workflowName = uniqueName('autosave_graph')
    await deleteWorkflowIfExists(page, workflowName)

    const { tool, outputName, inputName } = await fetchAnyTool(page)
    await createServerWorkflow(page, workflowName, { nodes: [], edges: [] })

    await page.goto('/')
    await seedWorkflowAutoSave(
      page,
      workflowName,
      graphWithEdge(tool, outputName, inputName),
    )
    await page.reload()

    await expect(page.locator('[data-testid="workflow-title"]')).toContainText('*')
    await expect(page.locator('.vue-flow__node[data-id="src_node"]')).toBeVisible()
    await expect(page.locator('.vue-flow__node[data-id="tgt_node"]')).toBeVisible()
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1, { timeout: 5000 })

    const edgePath = page.locator('.vue-flow__edge path.vue-flow__edge-path').first()
    const d = await edgePath.getAttribute('d')
    expect(d).toBeTruthy()
    expect(d!.length).toBeGreaterThan(10)
    expect(d).not.toContain('NaN')

    await deleteWorkflowIfExists(page, workflowName)
  })
})
