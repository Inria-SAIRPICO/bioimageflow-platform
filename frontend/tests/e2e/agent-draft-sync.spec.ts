import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

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

function ownedNumbersSource(toolName: string, offset: number): string {
  return `from bioimageflow import DataFrameTool
from bioimageflow_core import IOModel
import pandas as pd

class Outputs(IOModel):
    value: int

class ${toolName}(DataFrameTool):
    accepts_upstream = False
    Outputs = Outputs

    def transform(self, df, arguments):
        return pd.DataFrame({"value": [n + ${offset} for n in [1, 2, 3]]})
`
}

async function importOwnedWorkflow(
  page: Page,
  builderName: string,
  destinationName: string,
): Promise<Record<string, any>> {
  const exported = await page.request.post(`${API_BASE}/api/v1/workflows/${builderName}/export`)
  expect(exported.ok(), await exported.text()).toBeTruthy()
  const imported = await page.request.post(`${API_BASE}/api/v1/workflows/import`, {
    multipart: {
      name_override: destinationName,
      file: {
        name: `${destinationName}.bioimageflow.zip`,
        mimeType: 'application/zip',
        buffer: await exported.body(),
      },
    },
  })
  expect(imported.ok(), await imported.text()).toBeTruthy()
  return (await page.request.get(`${API_BASE}/api/v1/workflows/${destinationName}`)).json()
}

function ownedSourcePath(workflow: Record<string, any>, sourceId: string): string {
  const root = join(dirname(workflow.info.results_path), 'tools', sourceId)
  const manifest = JSON.parse(readFileSync(join(root, 'module.json'), 'utf8'))
  return join(root, manifest.filename)
}

async function rememberLastOpenedWorkflow(page: Page, name: string) {
  await page.evaluate(async (workflowName) => {
    const { useAutoSave } = await import('/src/composables/useAutoSave.ts')
    await useAutoSave().setLastOpenedWorkflow(workflowName)
  }, name)
}

async function installDraftWebSocketProbe(page: Page) {
  await page.addInitScript(() => {
    type DraftProbeWindow = Window & {
      __agentDraftSyncMessages?: unknown[]
      __agentDraftSyncWsOpenCount?: number
    }
    const probeWindow = window as DraftProbeWindow
    probeWindow.__agentDraftSyncMessages = []
    probeWindow.__agentDraftSyncWsOpenCount = 0

    const NativeWebSocket = window.WebSocket
    window.WebSocket = class InstrumentedWebSocket extends NativeWebSocket {
      constructor(url: string | URL, protocols?: string | string[]) {
        super(url, protocols)
        this.addEventListener('open', () => {
          probeWindow.__agentDraftSyncWsOpenCount =
            (probeWindow.__agentDraftSyncWsOpenCount ?? 0) + 1
        })
        this.addEventListener('message', (event) => {
          if (typeof event.data !== 'string') return
          try {
            const parsed = JSON.parse(event.data) as unknown
            probeWindow.__agentDraftSyncMessages?.push(parsed)
          } catch {
            /* Non-JSON messages are not relevant to draft sync. */
          }
        })
      }
    }
  })
}

test.describe('agent draft sync', () => {
  test('backend operation edits appear on the active clean canvas through WebSocket', async ({ page }) => {
    const workflowName = uniqueName('agent_sync')
    await installDraftWebSocketProbe(page)
    await deleteWorkflowIfExists(page, workflowName)

    const seed = await page.request.post(`${API_BASE}/api/v1/dev/seed`)
    expect(seed.ok()).toBeTruthy()
    await createServerWorkflow(page, workflowName, emptyGraph(workflowName))

    try {
      await page.goto('/')
      await expect(page.locator('#bioimageflow-app')).toBeVisible()
      await rememberLastOpenedWorkflow(page, workflowName)
      await page.reload()
      await expect(page.locator('[data-testid="workflow-title"]')).toContainText(workflowName)
      await expect(page.locator('.workflow-draft-conflict')).toHaveCount(0)
      await expect.poll(
        () => page.evaluate(() => window.__agentDraftSyncWsOpenCount ?? 0),
      ).toBeGreaterThan(0)

      let navigationsAfterOperation = 0
      page.on('framenavigated', (frame) => {
        if (frame === page.mainFrame()) navigationsAfterOperation += 1
      })

      const response = await page.request.post(
        `${API_BASE}/api/v1/workflow-draft-operations/${workflowName}`,
        {
          data: {
            expected_revision: 0,
            operations: [
              {
                type: 'create_tool_node',
                node_id: 'agent_seed_1',
                tool_name: 'SeedNumbers',
                name: 'Agent Seed',
                position: [160, 120],
                parameters: {},
              },
            ],
          },
        },
      )
      expect(response.ok()).toBeTruthy()

      await expect.poll(
        () => page.evaluate((id) => {
          const messages = window.__agentDraftSyncMessages ?? []
          return messages.some((message) => {
            if (typeof message !== 'object' || message === null) return false
            const draftMessage = message as {
              type?: unknown
              workflow_id?: unknown
              updated_by?: unknown
            }
            return draftMessage.type === 'workflow_draft_changed' &&
              draftMessage.workflow_id === id &&
              draftMessage.updated_by === 'agent'
          })
        }, workflowName),
      ).toBe(true)
      await expect(page.locator('.vue-flow__node[data-id="agent_seed_1"]')).toBeVisible({
        timeout: 5000,
      })
      await expect(page.locator('.workflow-draft-conflict')).toHaveCount(0)
      expect(navigationsAfterOperation).toBe(0)
    } finally {
      await deleteWorkflowIfExists(page, workflowName)
    }
  })
})

for (const keepCanvasFirst of [false, true]) {
  test(`saves the agent snapshot as a copy (keep canvas first: ${keepCanvasFirst})`, async ({ page }) => {
    const name = uniqueName('agent_copy')
    await createServerWorkflow(page, name, emptyGraph(name))
    try {
      await page.goto('/')
      await expect(page.locator('#bioimageflow-app')).toBeVisible()
      await rememberLastOpenedWorkflow(page, name)
      await page.reload()
      await expect(page.locator('[data-testid="workflow-title"]')).toContainText(name)

      async function agentChange(label: string) {
        await page.evaluate(async () => {
          const { useUIStore } = await import('/src/stores/ui.ts')
          const { canvasSessionRegistry } = await import('/src/sessions/canvasSessionRegistry.ts')
          const id = canvasSessionRegistry.activeCanvasId.value
          if (id === null) throw new Error('No active canvas')
          useUIStore().markCanvasDirty(id)
        })
        const latest = await (await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)).json()
        const response = await page.request.put(`${API_BASE}/api/v1/workflow-drafts/${name}`, {
          data: {
            graph: { ...latest.graph, display_name: label },
            expected_revision: latest.draft_revision,
            updated_by: 'agent',
          },
        })
        expect(response.ok()).toBeTruthy()
        await expect(page.locator('.workflow-draft-conflict')).toBeVisible()
        return response.json()
      }

      if (keepCanvasFirst) {
        await agentChange('Earlier agent change')
        await page.getByRole('button', { name: 'Keep my canvas', exact: true }).click()
        await expect(page.locator('.workflow-draft-conflict')).toHaveCount(0)
      }
      const agent = await agentChange('Latest agent change')
      const copied = page.waitForResponse(response => (
        response.request().method() === 'PATCH'
        && response.url().endsWith(`/api/v1/workflows/${name}`)
      ))
      await page.getByRole('button', { name: 'Save agent version as copy', exact: true }).click()
      const response = await copied
      expect(response.ok()).toBeTruthy()
      const info = await response.json()
      await expect(page.locator('.workflow-draft-conflict__success')).toContainText(info.id)
      const copy = await (await page.request.get(`${API_BASE}/api/v1/workflows/${info.id}`)).json()
      expect(copy.graph).toEqual({ ...agent.graph, name: info.id, display_name: info.id })
      const original = await (await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)).json()
      expect(original.draft_revision).toBe(agent.draft_revision)
      expect(original.graph).toEqual(agent.graph)
      await expect(page.locator('[data-testid="workflow-title"]')).toContainText(name)
    } finally {
      await deleteWorkflowIfExists(page, `${name}_agent_2`)
      await deleteWorkflowIfExists(page, name)
    }
  })
}

test('copies an agent graph with recursively owned unsaved sources without aliasing', async ({ page }) => {
  test.setTimeout(120_000)
  const name = uniqueName('agent_recursive_copy')
  const builderName = uniqueName('agent_source_builder')
  const childName = uniqueName('agent_source_child')
  const toolName = `AgentOwnedNumbers${Date.now()}`
  let copyName: string | null = null

  try {
    await createServerWorkflow(page, builderName, emptyGraph(builderName))
    const created = await page.request.post(`${API_BASE}/api/v1/tools`, {
      params: { workflow_name: builderName },
      data: { name: toolName, tool_type: 'DataFrameTool' },
    })
    expect(created.ok(), await created.text()).toBeTruthy()
    const builderSourcePath = (await created.json()).path as string
    const rootBytes = ownedNumbersSource(toolName, 1)
    const childBytes = ownedNumbersSource(toolName, 20)
    writeFileSync(builderSourcePath, rootBytes)

    const builderGraph = emptyGraph(builderName)
    builderGraph.config.execution = 'sequential'
    builderGraph.nodes = [{
      type: 'tool', id: 'owned_numbers', name: 'Owned numbers', tool_name: toolName,
      position: [180, 140], parameters: {},
    }]
    const builderSave = await page.request.put(`${API_BASE}/api/v1/workflows/${builderName}`, {
      data: { graph: builderGraph },
    })
    expect(builderSave.ok(), await builderSave.text()).toBeTruthy()
    const savedRoot = await importOwnedWorkflow(page, builderName, name)

    writeFileSync(builderSourcePath, childBytes)
    const savedChild = await importOwnedWorkflow(page, builderName, childName)
    const rootSourceId = savedRoot.graph.nodes[0].source_module as string
    const childSourceIdBeforeEmbedding = savedChild.graph.nodes[0].source_module as string
    expect(childSourceIdBeforeEmbedding).not.toBe(rootSourceId)
    expect(readFileSync(ownedSourcePath(savedRoot, rootSourceId), 'utf8')).toBe(rootBytes)
    expect(readFileSync(ownedSourcePath(savedChild, childSourceIdBeforeEmbedding), 'utf8')).toBe(childBytes)

    const preparedResponse = await page.request.post(
      `${API_BASE}/api/v1/workflows/${name}/prepare-embedding`,
      {
        data: {
          source_workflow_id: childName,
          identity_generation: savedRoot.info.identity_generation,
        },
      },
    )
    expect(preparedResponse.ok(), await preparedResponse.text()).toBeTruthy()
    const prepared = await preparedResponse.json()
    const embeddedSourceId = prepared.graph.nodes[0].source_module as string
    expect(embeddedSourceId).not.toBe(rootSourceId)
    const embeddedGraph = {
      ...prepared.graph,
      interface: {
        inputs: [],
        outputs: [{
          id: 'embedded-owned-value', name: 'value', schema: { type: 'int' },
          source: { node: 'owned_numbers', column: 'value' },
        }],
      },
    }

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await rememberLastOpenedWorkflow(page, name)
    await page.reload()
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText(name)
    await page.evaluate(async () => {
      const { useUIStore } = await import('/src/stores/ui.ts')
      const { canvasSessionRegistry } = await import('/src/sessions/canvasSessionRegistry.ts')
      const id = canvasSessionRegistry.activeCanvasId.value
      if (id === null) throw new Error('No active canvas')
      useUIStore().markCanvasDirty(id)
    })

    const originalDocumentPath = join(dirname(savedRoot.info.results_path), 'workflow.json')
    const originalDocumentBytes = readFileSync(originalDocumentPath)
    const originalDraftBefore = await (
      await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)
    ).json()
    const agentGraph = {
      ...savedRoot.graph,
      display_name: 'Agent recursive source graph',
      nodes: [
        savedRoot.graph.nodes[0],
        {
          type: 'workflow', id: 'embedded_child', name: 'Embedded child',
          position: [480, 140], bindings: {}, workflow: embeddedGraph,
          source: {
            kind: 'workspace', workflow_id: childName,
            artifact_hash: savedChild.artifact_hash,
          },
        },
      ],
    }
    const agentResponse = await page.request.put(`${API_BASE}/api/v1/workflow-drafts/${name}`, {
      data: {
        graph: agentGraph,
        expected_revision: originalDraftBefore.draft_revision,
        updated_by: 'agent',
      },
    })
    expect(agentResponse.ok(), await agentResponse.text()).toBeTruthy()
    const agent = await agentResponse.json()
    expect(agent.validation).toMatchObject({ valid: true, errors: [] })
    await expect(page.locator('.workflow-draft-conflict')).toBeVisible()

    const copied = page.waitForResponse(response => (
      response.request().method() === 'PATCH'
      && response.url().endsWith(`/api/v1/workflows/${name}`)
    ))
    await page.getByRole('button', { name: 'Save agent version as copy', exact: true }).click()
    const copyResponse = await copied
    expect(copyResponse.ok(), await copyResponse.text()).toBeTruthy()
    const copyInfo = await copyResponse.json()
    copyName = copyInfo.id
    await expect(page.locator('.workflow-draft-conflict__success')).toContainText(copyName!)

    const copy = await (
      await page.request.get(`${API_BASE}/api/v1/workflows/${copyName}`)
    ).json()
    expect(copy.graph).toEqual({ ...agent.graph, name: copyName, display_name: copyName })
    expect(copy.graph.nodes[1].workflow).toEqual(embeddedGraph)
    expect(copy.graph.nodes[1].workflow.name).toBe(savedChild.graph.name)
    const copyDocument = JSON.parse(readFileSync(
      join(dirname(copy.info.results_path), 'workflow.json'), 'utf8',
    ))
    expect(copyDocument.owned_source_ids).toEqual([embeddedSourceId, rootSourceId].sort())

    const originalRootPath = ownedSourcePath(savedRoot, rootSourceId)
    const originalChildPath = ownedSourcePath(savedRoot, embeddedSourceId)
    const copyRootPath = ownedSourcePath(copy, rootSourceId)
    const copyChildPath = ownedSourcePath(copy, embeddedSourceId)
    expect(new Set([originalRootPath, originalChildPath, copyRootPath, copyChildPath]).size).toBe(4)
    expect(readFileSync(originalRootPath, 'utf8')).toBe(rootBytes)
    expect(readFileSync(originalChildPath, 'utf8')).toBe(childBytes)
    expect(readFileSync(copyRootPath, 'utf8')).toBe(rootBytes)
    expect(readFileSync(copyChildPath, 'utf8')).toBe(childBytes)

    const originalSavedAfter = await (
      await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)
    ).json()
    const originalDraftAfter = await (
      await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)
    ).json()
    expect(originalSavedAfter.graph).toEqual(savedRoot.graph)
    expect(readFileSync(originalDocumentPath)).toEqual(originalDocumentBytes)
    expect(originalDraftAfter.draft_revision).toBe(agent.draft_revision)
    expect(originalDraftAfter.graph).toEqual(agent.graph)
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText(name)

    writeFileSync(copyChildPath, childBytes.replace('n + 20', 'n + 40'))
    expect(readFileSync(copyChildPath, 'utf8')).toContain('n + 40')
    expect(readFileSync(originalChildPath, 'utf8')).toBe(childBytes)
    await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
    await page.getByTestId('workflow-search').fill(copyName!)
    await page.getByTestId(`workflow-row-${copyName}`).dblclick()
    await expect(page.getByTestId('workflow-title')).toContainText(copyName!)
    await page.reload()
    await expect(page.getByTestId('workflow-title')).toContainText(copyName!)

    const runResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run')
      && response.request().method() === 'POST'
    ))
    await expect(page.getByTestId('run-workflow-button')).toBeEnabled({ timeout: 10_000 })
    await page.getByTestId('run-workflow-button').click()
    expect((await runResponse).status()).toBe(202)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText(
      'Execution complete', { timeout: 30_000 },
    )

    const projection = page.waitForRequest(request => (
      request.url().endsWith('/api/v1/data-table/query') && request.method() === 'POST'
    ), { timeout: 10_000 })
    await page.locator('.vue-flow__node[data-id="embedded_child"]').click()
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    expect((await projection).postDataJSON()).toMatchObject({
      sources: [expect.objectContaining({ node_id: 'embedded_child/owned_numbers' })],
    })
    const rows = page.getByTestId('data-table-panel').locator('.p-datatable-tbody tr')
    await expect(rows).toHaveCount(3)
    await expect(rows.nth(0).locator('td').last()).toHaveText('41')
    await expect(rows.nth(1).locator('td').last()).toHaveText('42')
    await expect(rows.nth(2).locator('td').last()).toHaveText('43')
    expect(readFileSync(originalRootPath, 'utf8')).toBe(rootBytes)
    expect(readFileSync(originalChildPath, 'utf8')).toBe(childBytes)
    expect(existsSync(join(savedRoot.info.results_path, 'outputs', 'latest'))).toBe(false)
  } finally {
    if (!page.isClosed()) {
      await page.goto('about:blank')
      if (copyName !== null) await deleteWorkflowIfExists(page, copyName)
      await deleteWorkflowIfExists(page, childName)
      await deleteWorkflowIfExists(page, name)
      await deleteWorkflowIfExists(page, builderName)
    }
  }
})
