import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

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
