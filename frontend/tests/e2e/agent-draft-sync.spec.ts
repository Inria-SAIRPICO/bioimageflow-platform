import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import type { GraphState as CanonicalGraphState } from '../../src/api/types'

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

async function expectOwnedValues(
  page: Page,
  canvasNodeId: string,
  scopedNodeId: string,
  values: string[],
) {
  const projection = page.waitForRequest(request => (
    request.url().endsWith('/api/v1/data-table/query') && request.method() === 'POST'
  ), { timeout: 10_000 })
  await page.locator(`.vue-flow__node[data-id="${canvasNodeId}"]`).click()
  await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
  expect((await projection).postDataJSON()).toMatchObject({
    sources: [expect.objectContaining({ node_id: scopedNodeId })],
  })
  const rows = page.getByTestId('data-table-panel').locator('.p-datatable-tbody tr')
  await expect(rows).toHaveCount(values.length)
  for (let index = 0; index < values.length; index += 1) {
    await expect(rows.nth(index).locator('td').last()).toHaveText(values[index]!)
  }
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
    test.setTimeout(60_000)
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

      const workflowResponse = await page.request.get(`${API_BASE}/api/v1/workflows/${workflowName}`)
      expect(workflowResponse.ok()).toBeTruthy()
      const workflow = await workflowResponse.json() as { info: { workspace_path: string } }
      const configPath = join(workflow.info.workspace_path, '.bioimageflow', 'mcp-client-config.json')
      await expect.poll(() => existsSync(configPath)).toBe(true)
      type MCPReport = {
        protocol_version: string
        final: { graph: CanonicalGraphState; draft_revision: number; dirty_against_saved: boolean }
        transcript: Array<{ tool: string; result: { ok: boolean; error?: string; status_code?: number } }>
      }
      const driveMCP = (mode: 'edit' | 'read'): MCPReport => JSON.parse(execFileSync(
        resolve('../backend/.venv/bin/python'),
        [resolve('../backend/tests/fixtures/stdio_mcp_workflow.py'),
          '--config', configPath, '--workflow', workflowName, '--mode', mode],
        { encoding: 'utf8', timeout: 25_000, maxBuffer: 4 * 1024 * 1024 },
      )) as MCPReport
      const edited = driveMCP('edit')
      expect(edited.protocol_version).not.toBe('')
      expect(edited.transcript.find(call => call.tool === 'rename_node' && !call.result.ok)?.result)
        .toMatchObject({ error: 'draft_revision_conflict', status_code: 409 })
      await test.info().attach('actual-stdio-mcp-edit', {
        body: Buffer.from(JSON.stringify(edited)), contentType: 'application/json',
      })

      await expect.poll(
        () => page.evaluate(({ id, revision }) => {
          const messages = window.__agentDraftSyncMessages ?? []
          return messages.some((message) => {
            if (typeof message !== 'object' || message === null) return false
            const draftMessage = message as {
              type?: unknown
              workflow_id?: unknown
              updated_by?: unknown
              draft_revision?: unknown
            }
            return draftMessage.type === 'workflow_draft_changed' &&
              draftMessage.workflow_id === id &&
              draftMessage.updated_by === 'agent' && draftMessage.draft_revision === revision
          })
        }, { id: workflowName, revision: edited.final.draft_revision }),
      ).toBe(true)
      await expect(page.locator('.vue-flow__node[data-id="agent_seed_1"]')).toBeVisible({
        timeout: 5000,
      })
      await expect(page.locator('.vue-flow__node[data-id="agent_increment_1"]'))
        .toContainText('MCP accepted increment')
      await expect(page.locator('.vue-flow__edge')).toHaveCount(1)
      await expect(page.locator('.workflow-draft-conflict')).toHaveCount(0)
      expect(navigationsAfterOperation).toBe(0)

      let savedResponseSeen = false
      const savedResponse = page.waitForResponse(response => {
        const matches = response.request().method() === 'PUT'
          && new URL(response.url()).pathname === `/api/v1/workflows/${workflowName}`
        if (matches) savedResponseSeen = true
        return matches
      })
      const cleanResponse = page.waitForResponse(response => savedResponseSeen
        && response.request().method() === 'PUT'
        && new URL(response.url()).pathname === `/api/v1/workflow-drafts/${workflowName}`
        && response.status() === 200)
      await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
      await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
      expect((await savedResponse).status()).toBe(200)
      const cleanDraft = await (await cleanResponse).json() as { dirty_against_saved: boolean }
      expect(cleanDraft.dirty_against_saved).toBe(false)
      await expect(page.getByTestId('workflow-title')).toHaveText(workflowName)
      await page.reload()
      await expect(page.locator('.vue-flow__node[data-id="agent_increment_1"]'))
        .toContainText('MCP accepted increment')
      await expect(page.getByTestId('workflow-title')).toHaveText(workflowName)
      const reopened = driveMCP('read')
      expect(reopened.final.graph).toEqual(edited.final.graph)
      expect(reopened.final.dirty_against_saved).toBe(false)
      const saved = await page.request.get(`${API_BASE}/api/v1/workflows/${workflowName}`)
      expect(saved.ok()).toBeTruthy()
      expect((await saved.json()).graph).toEqual(reopened.final.graph)
      await test.info().attach('actual-stdio-mcp-reopened', {
        body: Buffer.from(JSON.stringify(reopened)), contentType: 'application/json',
      })
    } finally {
      await page.goto('about:blank')
      await deleteWorkflowIfExists(page, workflowName)
    }
  })
})

for (const keepCanvasFirst of [false, true]) {
  test(`saves the agent snapshot as a copy (keep canvas first: ${keepCanvasFirst})`, async ({ page }, testInfo) => {
    const name = uniqueName('agent_copy')
    let copyName: string | null = null
    let releaseWrite: (() => void) | undefined
    let mainFailed = false
    const cleanupErrors: unknown[] = []
    try {
      const seed = await page.request.post(`${API_BASE}/api/v1/dev/seed`)
      expect(seed.ok(), await seed.text()).toBeTruthy()
      const graph = emptyGraph(name)
      graph.config.execution = 'sequential'
      graph.nodes = [
        { type: 'tool', id: 'seed', name: 'Seed Numbers', tool_name: 'SeedNumbers', position: [180, 180], parameters: {} },
        { type: 'tool', id: 'increment', name: 'Increment Numbers', tool_name: 'IncrementNumbers', position: [520, 180], parameters: { number: 1 } },
      ]
      graph.edges = [{ type: 'dataframe', id: 'seed-increment', source_node: 'seed', target_node: 'increment', target_position: 0 }]
      await createServerWorkflow(page, name, graph)
      const savedResponse = await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)
      expect(savedResponse.ok()).toBeTruthy()
      const saved = await savedResponse.json()
      const savedBytes = readFileSync(saved.info.path)
      await installDraftWebSocketProbe(page)
      await page.goto('/')
      await expect(page.locator('#bioimageflow-app')).toBeVisible()
      await rememberLastOpenedWorkflow(page, name)
      await page.reload()
      await expect(page.locator('[data-testid="workflow-title"]')).toContainText(name)
      await expect.poll(() => page.evaluate(() => window.__agentDraftSyncWsOpenCount ?? 0)).toBeGreaterThan(0)
      await page.locator('.vue-flow__node[data-id="increment"]').click()
      await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
      const numberInput = page.getByTestId('panel-nodePanel').locator('.param-row')
        .filter({ hasText: 'Number column to increment' }).locator('input.p-inputnumber-input')
      await expect(numberInput).toBeVisible()
      await expect(numberInput).toHaveValue('1')

      async function agentChange(label: string, localNumber: number) {
        const path = `/api/v1/workflow-drafts/${name}`
        let entered!: () => void
        const started = new Promise<void>(resolveStarted => { entered = resolveStarted })
        const held = new Promise<void>(resolveHeld => { releaseWrite = resolveHeld })
        let intercepted = false
        let outgoing: Record<string, any> | null = null
        const handler = async (route: import('@playwright/test').Route) => {
          if (route.request().method() === 'PUT' && !intercepted) {
            intercepted = true
            outgoing = route.request().postDataJSON()
            entered()
            await held
          }
          await route.continue()
        }
        await page.route(`**${path}`, handler)
        const staleWrite = page.waitForResponse(response => (
          new URL(response.url()).pathname === path && response.request().method() === 'PUT'
        ))
        // Real visible mutation, held before backend admission. The independent
        // agent API request remains free to publish its revision and WebSocket event.
        await numberInput.fill(String(localNumber))
        await numberInput.press('Tab')
        await started
        expect(outgoing).not.toBeNull()
        expect(outgoing!.updated_by).toBe('frontend')
        expect(outgoing!.graph.nodes.find((node: Record<string, any>) => node.id === 'increment').parameters.number).toBe(localNumber)
        await expect(numberInput).toHaveValue(String(localNumber))
        const latestResponse = await page.request.get(`${API_BASE}${path}`)
        expect(latestResponse.ok()).toBeTruthy()
        const latest = await latestResponse.json()
        expect(latest.validation).toMatchObject({ valid: true, errors: [] })
        const response = await page.request.put(`${API_BASE}${path}`, {
          data: {
            graph: { ...latest.graph, display_name: label },
            expected_revision: latest.draft_revision,
            updated_by: 'agent',
          },
        })
        expect(response.ok(), await response.text()).toBeTruthy()
        const accepted = await response.json()
        expect(accepted.validation).toMatchObject({ valid: true, errors: [] })
        await expect(page.locator('.workflow-draft-conflict')).toBeVisible()
        releaseWrite!()
        releaseWrite = undefined
        expect((await staleWrite).status()).toBe(409)
        await page.unroute(`**${path}`, handler)
        await expect(numberInput).toHaveValue(String(localNumber))
        return accepted
      }

      if (keepCanvasFirst) {
        await agentChange('Earlier agent change', 10)
        const kept = page.waitForResponse(response => (
          response.request().method() === 'PUT'
          && new URL(response.url()).pathname === `/api/v1/workflow-drafts/${name}`
        ))
        await page.getByRole('button', { name: 'Keep my canvas', exact: true }).click()
        const keptResponse = await kept
        expect(keptResponse.ok(), await keptResponse.text()).toBeTruthy()
        const keptDraft = await keptResponse.json()
        expect(keptDraft.graph.nodes.find((node: Record<string, any>) => node.id === 'increment').parameters.number).toBe(10)
        await expect(page.locator('.workflow-draft-conflict')).toHaveCount(0)
      }
      const localNumber = keepCanvasFirst ? 20 : 10
      const agent = await agentChange('Latest agent change', localNumber)
      const copied = page.waitForResponse(response => (
        response.request().method() === 'PATCH'
        && response.url().endsWith(`/api/v1/workflows/${name}`)
      ))
      await page.getByRole('button', { name: 'Save agent version as copy', exact: true }).click()
      const response = await copied
      expect(response.ok()).toBeTruthy()
      const info = await response.json()
      copyName = info.id
      await expect(page.locator('.workflow-draft-conflict__success')).toContainText(info.id)
      const copy = await (await page.request.get(`${API_BASE}/api/v1/workflows/${info.id}`)).json()
      expect(copy.graph).toEqual({ ...agent.graph, name: info.id, display_name: info.id })
      const original = await (await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)).json()
      expect(original.draft_revision).toBe(agent.draft_revision)
      expect(original.graph).toEqual(agent.graph)
      await expect(numberInput).toHaveValue(String(localNumber))
      expect(agent.graph.nodes.find((node: Record<string, any>) => node.id === 'increment').parameters.number)
        .toBe(keepCanvasFirst ? 10 : 1)
      expect(copy.info.id).not.toBe(name)
      const originalSaved = await (await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)).json()
      expect(originalSaved.graph).toEqual(saved.graph)
      expect(readFileSync(saved.info.path)).toEqual(savedBytes)
      await expect(page.locator('[data-testid="workflow-title"]')).toContainText(name)
    } catch (error) {
      mainFailed = true
      throw error
    } finally {
      releaseWrite?.()
      async function cleanup(operation: () => Promise<unknown>) {
        try { await operation() } catch (error) { cleanupErrors.push(error) }
      }
      await cleanup(() => page.unrouteAll({ behavior: 'wait' }))
      await cleanup(() => page.goto('about:blank'))
      for (const owned of [copyName, name]) {
        if (owned === null) continue
        await cleanup(async () => {
          const removed = await page.request.delete(`${API_BASE}/api/v1/workflows/${owned}`)
          expect([200, 404]).toContain(removed.status())
        })
      }
      if (cleanupErrors.length) await cleanup(() => testInfo.attach('agent-copy-cleanup-errors', {
        body: cleanupErrors.map(String).join('\n'), contentType: 'text/plain',
      }))
    }
    if (!mainFailed && cleanupErrors.length) throw cleanupErrors[0]
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
          viewer_addition: null,
        }],
      },
    }

    await installDraftWebSocketProbe(page)
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    // Use the real named Open intent rather than racing startup with a direct
    // preference-store write. Later assertions still exercise copy restoration.
    await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
    await page.getByTestId('workflow-search').fill(name)
    await page.getByTestId(`workflow-row-${name}`).dblclick()
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText(name)
    await expect.poll(() => page.evaluate(() => window.__agentDraftSyncWsOpenCount ?? 0)).toBeGreaterThan(0)
    const ownedNode = page.locator('.vue-flow__node[data-id="owned_numbers"]')
    await expect(ownedNode).toBeVisible()
    const nodeBox = await ownedNode.boundingBox()
    expect(nodeBox).not.toBeNull()
    const localWrite = page.waitForResponse(response => (
      new URL(response.url()).pathname === `/api/v1/workflow-drafts/${name}`
      && response.request().method() === 'PUT'
      && response.request().postDataJSON().updated_by === 'frontend'
      && JSON.stringify(response.request().postDataJSON().graph.nodes[0].position)
        !== JSON.stringify(savedRoot.graph.nodes[0].position)
    ))
    // A real graph edit establishes local semantic ownership. Setting only a
    // presentation dirty flag can be cleared by the initial same-graph response.
    const dragStart = {
      x: nodeBox!.x + nodeBox!.width / 2,
      y: nodeBox!.y + Math.min(24, nodeBox!.height / 2),
    }
    await page.mouse.move(dragStart.x, dragStart.y)
    await page.mouse.down()
    await page.mouse.move(dragStart.x + 60, dragStart.y + 40, { steps: 8 })
    await page.mouse.up()
    const localResponse = await localWrite
    expect(localResponse.ok(), await localResponse.text()).toBeTruthy()
    const localDraft = await localResponse.json()
    expect(localDraft).toMatchObject({ updated_by: 'frontend', dirty_against_saved: true })
    expect(localDraft.graph.nodes[0].position).not.toEqual(savedRoot.graph.nodes[0].position)

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
    await expect(page.locator('.vue-flow__node')).toHaveCount(1)
    await expect(page.locator('.vue-flow__node[data-id="embedded_child"]')).toHaveCount(0)

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
    await expect.poll(() => page.evaluate(async () => {
      const { useAutoSave } = await import('/src/composables/useAutoSave.ts')
      return useAutoSave().getLastOpenedWorkflow()
    })).toBe(copyName)
    await page.evaluate(async ({ originalName, graph }) => {
      const { writeAutoSaveEntry } = await import('/src/composables/useAutoSave.ts')
      await writeAutoSaveEntry({
        name: originalName,
        graph: graph as Parameters<typeof writeAutoSaveEntry>[0]['graph'],
        timestamp: Date.now() + 60_000,
      })
    }, { originalName: name, graph: agent.graph })
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

    await expectOwnedValues(page, 'owned_numbers', 'owned_numbers', ['2', '3', '4'])
    await expectOwnedValues(
      page,
      'embedded_child',
      'embedded_child/owned_numbers',
      ['41', '42', '43'],
    )

    const originalSavedAfterRun = await (
      await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)
    ).json()
    const originalDraftAfterRun = await (
      await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)
    ).json()
    expect(originalSavedAfterRun.graph).toEqual(savedRoot.graph)
    expect(readFileSync(originalDocumentPath)).toEqual(originalDocumentBytes)
    expect(originalDraftAfterRun.draft_revision).toBe(agent.draft_revision)
    expect(originalDraftAfterRun.graph).toEqual(agent.graph)
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
