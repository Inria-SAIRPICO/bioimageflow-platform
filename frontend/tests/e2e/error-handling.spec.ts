import { test, expect } from '@playwright/test'

/**
 * E2E coverage for the three-level error handling system (spec §3.11).
 *
 * Each test exercises one user-visible aspect of the error UI without
 * depending on a custom failing-tool mock in the backend. The Playwright
 * backend exposes the dev seed router, so these tests create their own
 * deterministic tool registry.
 */
test.describe('error handling', () => {
  test.beforeEach(async ({ page }) => {
    const seed = await page.request.post('/api/v1/dev/seed')
    expect(seed.ok()).toBeTruthy()
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
  })

  test('error indicator is hidden when no errors have occurred', async ({
    page,
  }) => {
    await expect(page.locator('.error-indicator')).toHaveCount(0)
  })

  test('graph_sync_error: indicator appears and history records the entry', async ({
    page,
  }) => {
    // Intercept the next PUT /graph and force a network failure so the
    // graph-sync layer reports a graph_sync_error.
    await page.route('**/api/v1/graph', async (route, request) => {
      if (request.method() === 'PUT') {
        await route.abort('failed')
      } else {
        await route.continue()
      }
    })

    // Trigger a sync by submitting a graph through the API client surface
    // the app uses; this mirrors what the canvas would do after a node drop.
    await page.evaluate(async () => {
      const win = window as unknown as { __bif_test_trigger?: () => void }
      // Direct drive: import the composable singleton and queue a sync.
      // This is shallower than the real drag-drop flow but exercises the
      // same error path.
      const mod = await import('/src/composables/useGraphSync.ts')
      const sync = mod.useGraphSync()
      sync.syncGraph({ nodes: [], edges: [] })
      await sync.flushNow()
      void win.__bif_test_trigger
    })

    // Indicator becomes visible after the failed sync.
    await expect(page.locator('.error-indicator')).toBeVisible({
      timeout: 5000,
    })
    // Unread badge shows 1.
    await expect(page.locator('.error-indicator .unread-badge')).toHaveText('1')

    // Open the history panel.
    await page.locator('.error-indicator').click()
    const panel = page.locator('[data-testid="error-row"]').first()
    await expect(panel).toBeVisible()
    await expect(panel).toContainText('Graph sync error')

    // Dismiss the row; unread count drops, history still has the entry.
    await page
      .locator('[data-testid="error-row-dismiss"]')
      .first()
      .click()
    await expect(page.locator('.error-indicator .unread-badge')).toHaveCount(0)
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
