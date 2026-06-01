import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

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
  await page.evaluate(
    (workflowName) => new Promise<void>((resolve, reject) => {
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
        const tx = db.transaction('preferences', 'readwrite')
        tx.objectStore('preferences').put(workflowName, 'last_opened_workflow')
        tx.oncomplete = () => {
          db.close()
          resolve()
        }
        tx.onerror = () => reject(tx.error)
      }
      req.onerror = () => reject(req.error)
    }),
    name,
  )
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
    await createServerWorkflow(page, workflowName, { nodes: [], edges: [] })

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
              type: 'create_node',
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

    await deleteWorkflowIfExists(page, workflowName)
  })
})
