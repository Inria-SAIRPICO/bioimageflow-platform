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
  package: string
  package_version: string
  tool_type: string
  accepts_upstream: boolean
  dataframe_output: boolean
  inputs: Record<string, { type: string; connectable?: string | boolean }>
  outputs: Record<string, { type: string }>
  [k: string]: unknown
}

const RECOVERY_EDGE_ID = 'e-seed_numbers-increment_numbers-dataframe-0'

type GraphState = {
  schema_version: 1
  name: string
  display_name: string
  nodes: Array<Record<string, unknown>>
  edges: Array<Record<string, unknown>>
  interface: { inputs: []; outputs: [] }
  config: { engine: string; execution: string }
}

function emptyGraph(name: string): GraphState {
  return {
    schema_version: 1,
    name,
    display_name: name,
    nodes: [],
    edges: [],
    interface: { inputs: [], outputs: [] },
    config: { engine: 'direct', execution: 'parallel' },
  }
}

function uniqueName(prefix: string): string {
  const project = test.info().project.name.replace(/[^a-zA-Z0-9_-]/g, '_')
  return `${prefix}_${project}_${Date.now()}_${Math.floor(Math.random() * 10000)}`
}

async function deleteWorkflowIfExists(page: Page, name: string) {
  await page.request.delete(`${API_BASE}/api/v1/workflows/${name}`).catch(() => undefined)
}

async function fetchRecoveryTools(page: Page): Promise<{
  source: ToolMetadata
  target: ToolMetadata
}> {
  const seed = await page.request.post(`${API_BASE}/api/v1/dev/seed`)
  expect(seed.ok()).toBeTruthy()
  const response = await page.request.get(`${API_BASE}/api/v1/tools`)
  expect(response.ok()).toBeTruthy()
  const tools = (await response.json()) as ToolMetadata[]
  const source = tools.find(candidate => candidate.name === 'SeedNumbers')
  const target = tools.find(candidate => candidate.name === 'IncrementNumbers')

  expect(source, 'dev seed must register SeedNumbers').toBeTruthy()
  expect(source).toMatchObject({
    package: 'bioimageflow-dev-seed',
    package_version: '0.1.0',
    tool_type: 'DataFrameTool',
    accepts_upstream: false,
    dataframe_output: true,
    inputs: {},
    outputs: { number: { type: 'int' }, label: { type: 'str' } },
  })
  expect(target, 'dev seed must register IncrementNumbers').toBeTruthy()
  expect(target).toMatchObject({
    package: 'bioimageflow-dev-seed',
    package_version: '0.1.0',
    tool_type: 'DataFrameTool',
    accepts_upstream: true,
    dataframe_output: true,
    inputs: {
      number: { type: 'int', connectable: 'by_default' },
    },
    outputs: { number_plus_one: { type: 'int' } },
  })
  return { source: source!, target: target! }
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

function recoveryGraph(
  workflowName: string,
  source: ToolMetadata,
  target: ToolMetadata,
): GraphState {
  return {
    schema_version: 1,
    name: workflowName,
    display_name: workflowName,
    nodes: [
      {
        type: 'tool',
        id: 'src_node',
        name: 'Seed Numbers',
        tool_name: source.name,
        position: [100, 100],
        parameters: {},
      },
      {
        type: 'tool',
        id: 'tgt_node',
        name: 'Increment Numbers',
        tool_name: target.name,
        position: [500, 100],
        parameters: { number: 1 },
      },
    ],
    edges: [
      {
        type: 'dataframe',
        id: RECOVERY_EDGE_ID,
        source_node: 'src_node',
        target_node: 'tgt_node',
        target_position: 0,
      },
    ],
    interface: { inputs: [], outputs: [] },
    config: { engine: 'direct', execution: 'parallel' },
  }
}

test.describe('workflow-scoped graph recovery', () => {
  test('auto-saved graph restores nodes and edges after reload', async ({ page }) => {
    const workflowName = uniqueName('autosave_graph')
    await deleteWorkflowIfExists(page, workflowName)

    const { source, target } = await fetchRecoveryTools(page)
    const recovered = recoveryGraph(workflowName, source, target)
    const validation = await page.request.put(`${API_BASE}/api/v1/graph`, {
      data: recovered,
    })
    expect(validation.ok()).toBeTruthy()
    expect(await validation.json()).toMatchObject({ valid: true, errors: [] })
    await createServerWorkflow(page, workflowName, emptyGraph(workflowName))

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await seedWorkflowAutoSave(page, workflowName, recovered)
    const toolsReady = page.waitForResponse(
      response => response.url().includes('/api/v1/tools') && response.status() === 200,
    )
    await page.reload()
    await toolsReady

    await expect(page.locator('[data-testid="workflow-title"]')).toHaveText(`${workflowName} *`)
    await expect(page.locator('.vue-flow__node')).toHaveCount(2)
    await expect(page.locator('.vue-flow__node[data-id="src_node"] .node-name')).toHaveText('Seed Numbers')
    await expect(page.locator('.vue-flow__node[data-id="tgt_node"] .node-name')).toHaveText('Increment Numbers')
    const recoveredEdge = page.locator(`.vue-flow__edge[data-id="${RECOVERY_EDGE_ID}"]`)
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1, { timeout: 5000 })
    await expect(recoveredEdge).toHaveCount(1)

    const edgePath = recoveredEdge.locator('path.vue-flow__edge-path')
    const d = await edgePath.getAttribute('d')
    expect(d).toBeTruthy()
    expect(d!.length).toBeGreaterThan(10)
    expect(d).not.toContain('NaN')

    await deleteWorkflowIfExists(page, workflowName)
  })
})
