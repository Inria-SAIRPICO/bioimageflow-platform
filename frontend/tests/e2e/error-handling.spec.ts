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
    const seed = await page.request.post(`${API_BASE}/api/v1/dev/seed`)
    expect(seed.ok()).toBeTruthy()
    workflowName = await createAndOpenWorkflow(page)
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

  test('contextual execution failure is recorded once in history and logger', async ({
    page,
  }) => {
    const draftResponse = await page.request.get(
      `${API_BASE}/api/v1/workflow-drafts/${workflowName}`,
    )
    expect(draftResponse.ok()).toBeTruthy()
    const draftRevision = (await draftResponse.json()).draft_revision as number

    const result = await page.evaluate(
      async ({ workflowId, revision }) => {
        const { useExecutionStore } = await import('/src/stores/execution.ts')
        const { useLoggerStore } = await import('/src/stores/logger.ts')
        const execution = useExecutionStore()
        const logger = useLoggerStore()
        const executionId = `error-e2e-${Date.now()}`
        const nodeId = 'failed_node'

        // Worker logs are intentionally unscoped. A matching log can arrive
        // before the contextual completion event, which must not duplicate it.
        logger.addEntry({
          level: 'ERROR',
          message: 'boom\ntraceback-e2e',
          nodeId,
          timestamp: Date.now() / 1000,
        })
        execution.applyStatusSnapshot({
          state: 'running',
          last_result: null,
          progress: null,
          node_statuses: {},
          execution_id: executionId,
          workflow_id: workflowId,
          draft_revision: revision,
        })
        execution.applyExecutionComplete({
          success: false,
          errors: [],
          node_statuses: {
            [nodeId]: {
              node_id: nodeId,
              status: 'failed',
              cached: false,
              error: 'boom',
              traceback: 'traceback-e2e',
            },
          },
          execution_id: executionId,
          workflow_id: workflowId,
          draft_revision: revision,
        })
        return logger.entries.filter(
          (entry) => entry.level === 'ERROR' && entry.nodeId === nodeId,
        ).length
      },
      { workflowId: workflowName, revision: draftRevision },
    )
    expect(result).toBe(1)

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
      .locator('[data-testid="error-row-dismiss"]')
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

  test('error history "Clear all" wipes the history', async ({ page }) => {
    await page.evaluate(async () => {
      const errors = await import('/src/stores/errors.ts')
      const store = errors.useErrorStore()
      store.report({ kind: 'graph_sync_error', detail: 'first' })
      store.report({ kind: 'execution_failed', detail: 'second', nodeId: 'n1' })
    })

    await expect(page.locator('.error-indicator')).toBeVisible()
    await page.locator('.error-indicator').click()

    await expect(page.locator('[data-testid="error-row"]')).toHaveCount(2)
    await page.locator('[data-testid="error-history-clear"]').click()
    await expect(page.locator('[data-testid="error-row"]')).toHaveCount(0)
    await expect(page.locator('[data-testid="error-history-empty"]')).toBeVisible()
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
