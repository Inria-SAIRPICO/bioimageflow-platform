import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

function uniqueWorkflowName(): string {
  const project = test.info().project.name.replace(/[^a-zA-Z0-9_-]/g, '_')
  return `error_context_${project}_${Date.now()}_${Math.floor(Math.random() * 10000)}`
}

async function createAndOpenWorkflow(page: Page): Promise<string> {
  const name = uniqueWorkflowName()
  const displayName = `Error Context ${name}`
  const created = await page.request.post(`${API_BASE}/api/v1/workflows`, {
    data: { name, display_name: displayName },
  })
  expect(created.status()).toBe(201)
  const saved = await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
    data: { graph: { nodes: [], edges: [] } },
  })
  expect(saved.ok()).toBeTruthy()

  await page.goto('/')
  await expect(page.locator('#bioimageflow-app')).toBeVisible()
  await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
  await page.getByTestId('workflow-search').fill(displayName)
  await expect(page.getByTestId(`workflow-row-${name}`)).toBeVisible({ timeout: 5000 })
  await page.getByTestId(`workflow-row-${name}`).dblclick()
  await expect(page.getByTestId('workflow-title')).toContainText(displayName)
  return name
}

async function installWebSocketProbe(page: Page): Promise<void> {
  await page.addInitScript(() => {
    type WebSocketProbeWindow = Window & {
      __errorHandlingWsMessages?: unknown[]
    }
    const probeWindow = window as WebSocketProbeWindow
    probeWindow.__errorHandlingWsMessages = []

    const NativeWebSocket = window.WebSocket
    window.WebSocket = class InstrumentedWebSocket extends NativeWebSocket {
      constructor(url: string | URL, protocols?: string | string[]) {
        super(url, protocols)
        this.addEventListener('message', (event) => {
          if (typeof event.data !== 'string') return
          try {
            probeWindow.__errorHandlingWsMessages?.push(JSON.parse(event.data))
          } catch {
            /* Non-JSON frames are irrelevant to the application protocol. */
          }
        })
      }
    }
  })
}

async function waitForLogSubscription(page: Page): Promise<void> {
  await expect.poll(() => page.evaluate(() => {
    const messages = window.__errorHandlingWsMessages ?? []
    return messages.some((message) => (
      typeof message === 'object'
      && message !== null
      && (message as { type?: unknown }).type === 'ack'
    ))
  })).toBe(true)
}

/**
 * E2E coverage for the three-level error handling system (spec §3.11).
 *
 * Each test exercises one user-visible aspect of the error UI without
 * depending on a custom failing-tool mock in the backend. The Playwright
 * backend exposes the dev seed router, so these tests create their own
 * deterministic tool registry.
 */
test.describe('error handling', () => {
  let workflowName = ''

  test.beforeEach(async ({ page }) => {
    await installWebSocketProbe(page)
    const seed = await page.request.post(`${API_BASE}/api/v1/dev/seed`)
    expect(seed.ok()).toBeTruthy()
    workflowName = await createAndOpenWorkflow(page)
    await waitForLogSubscription(page)
  })

  test.afterEach(async ({ page }) => {
    if (workflowName) {
      await page.request
        .delete(`${API_BASE}/api/v1/workflows/${workflowName}`)
        .catch(() => undefined)
    }
  })

  test('error indicator is hidden when no errors have occurred', async ({
    page,
  }) => {
    await expect(page.locator('.error-indicator')).toHaveCount(0)
  })

  test('contextual execution failure is recorded once in history and logger', { tag: '@critical' }, async ({
    page,
  }) => {
    const draftResponse = await page.request.get(
      `${API_BASE}/api/v1/workflow-drafts/${workflowName}`,
    )
    expect(draftResponse.ok()).toBeTruthy()
    const draftRevision = (await draftResponse.json()).draft_revision as number

    const executionId = `error-e2e-${Date.now()}`
    const failure = await page.request.post(
      `${API_BASE}/api/v1/dev/e2e/execution-failure`,
      {
        data: {
          execution_id: executionId,
          workflow_id: workflowName,
          draft_revision: draftRevision,
          node_id: 'failed_node',
          error: 'boom',
          traceback: 'traceback-e2e',
        },
      },
    )
    expect(failure.ok()).toBeTruthy()

    await expect.poll(() => page.evaluate((id) => {
      const messages = window.__errorHandlingWsMessages ?? []
      const logIndex = messages.findIndex((message) => (
        typeof message === 'object'
        && message !== null
        && (message as { type?: unknown; message?: unknown }).type === 'log'
        && (message as { message?: unknown }).message === 'boom\ntraceback-e2e'
      ))
      const completionIndex = messages.findIndex((message) => (
        typeof message === 'object'
        && message !== null
        && (message as { type?: unknown; execution_id?: unknown }).type
          === 'execution_complete'
        && (message as { execution_id?: unknown }).execution_id === id.executionId
      ))
      if (logIndex < 0 || completionIndex <= logIndex) return false
      const log = messages[logIndex] as {
        execution_id?: unknown
        workflow_id?: unknown
        draft_revision?: unknown
      }
      return log.execution_id === id.executionId
        && log.workflow_id === id.workflowId
        && log.draft_revision === id.draftRevision
    }, { executionId, workflowId: workflowName, draftRevision })).toBe(true)

    await expect(page.locator('.error-indicator')).toBeVisible({
      timeout: 5000,
    })
    await expect(page.locator('.error-indicator .unread-badge')).toHaveText('1')

    await page.locator('.error-indicator').click()
    const panel = page.locator('[data-testid="error-row"]').first()
    await expect(panel).toBeVisible()
    await expect(panel).toContainText('Execution failed')
    await expect(panel).toContainText('failed_node: boom')

    await page
      .locator('[data-testid="error-row-read-toggle"]')
      .first()
      .click()
    await expect(page.locator('.error-indicator .unread-badge')).toHaveCount(0)

    await page.getByTestId('error-history-close').click()
    await page.locator('.dv-tab').filter({ hasText: 'Logger' }).click()
    const failureLog = page.getByTestId('log-entry').filter({ hasText: 'boom' })
    await expect(failureLog).toHaveCount(1)
    await expect(failureLog).toContainText('failed_node')
  })

  test('cycle detection produces a global banner above the canvas', async ({
    page,
  }) => {
    // Drive the same graph-sync singleton used by CanvasView so this covers
    // both backend validation and the UI banner fed by the validation result.
    const validation = await page.evaluate(async () => {
      const mod = await import('/src/composables/useGraphSync.ts')
      const sync = mod.useGraphSync()
      sync.syncGraph({
        nodes: [
          {
            id: 'a',
            position: { x: 0, y: 0 },
            data: {
              name: 'Increment Numbers A',
              toolName: 'IncrementNumbers',
              parameters: {},
            },
          },
          {
            id: 'b',
            position: { x: 220, y: 0 },
            data: {
              name: 'Increment Numbers B',
              toolName: 'IncrementNumbers',
              parameters: {},
            },
          },
        ],
        edges: [
          {
            id: 'e1',
            source: 'a',
            target: 'b',
            sourceHandle: 'number_plus_one',
            targetHandle: 'number',
          },
          {
            id: 'e2',
            source: 'b',
            target: 'a',
            sourceHandle: 'number_plus_one',
            targetHandle: 'number',
          },
        ],
      })
      await sync.flushNow()
      return sync.validationResult.value
    })

    expect(validation?.valid).toBe(false)
    expect(validation?.errors ?? []).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: 'cycle_detected' }),
      ]),
    )
    await expect(page.locator('.canvas-error-banner')).toBeVisible()
    await expect(page.getByTestId('canvas-error-row').first()).toContainText(
      /cycle/i,
    )
    const hasCycle = (validation?.errors ?? []).some(
      (e: { type: string }) => e.type === 'cycle_detected',
    )
    expect(hasCycle).toBe(true)
  })

  test('error history read toggles retain every error', async ({ page }) => {
    await page.evaluate(async () => {
      const errors = await import('/src/stores/errors.ts')
      const store = errors.useErrorStore()
      store.report({ kind: 'graph_sync_error', detail: 'first' })
      store.report({ kind: 'execution_failed', detail: 'second', nodeId: 'n1' })
    })

    await expect(page.locator('.error-indicator')).toBeVisible()
    await page.locator('.error-indicator').click()

    await expect(page.locator('[data-testid="error-row"]')).toHaveCount(2)
    await expect(page.locator('[data-testid="error-history-clear"]')).toHaveCount(0)
    await expect(page.locator('[data-testid="error-history-dismiss-all"]')).toHaveCount(0)

    const firstRow = page.locator('[data-testid="error-row"]').first()
    const readToggle = firstRow.locator('[data-testid="error-row-read-toggle"]')
    await expect(readToggle).toHaveAttribute('aria-label', 'Mark as read')
    await readToggle.click()

    await expect(page.locator('[data-testid="error-row"]')).toHaveCount(2)
    await expect(firstRow).toHaveClass(/acknowledged/)
    await expect(readToggle).toHaveAttribute('aria-label', 'Mark as unread')

    await readToggle.click()
    await expect(page.locator('[data-testid="error-row"]')).toHaveCount(2)
    await expect(firstRow).not.toHaveClass(/acknowledged/)
  })

  test('error history "Go to node" emits navigation', async ({ page }) => {
    await page.evaluate(async () => {
      const errors = await import('/src/stores/errors.ts')
      const store = errors.useErrorStore()
      store.report({
        kind: 'execution_failed',
        detail: 'broke',
        nodeId: 'node-42',
      })
    })

    await expect(page.locator('.error-indicator')).toBeVisible()
    await page.locator('.error-indicator').click()
    await expect(page.locator('[data-testid="error-row-navigate"]')).toBeVisible()
    await page.locator('[data-testid="error-row-navigate"]').click()

    // After navigation, the panel should close.
    await expect(page.locator('[data-testid="error-row"]')).toHaveCount(0)
  })
})
