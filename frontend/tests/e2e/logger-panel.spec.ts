import { test, expect } from '@playwright/test'

test.describe('logger panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/execution/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          state: 'idle',
          last_result: null,
          progress: null,
          node_statuses: {},
        }),
      })
    })
  })

  test('renders logger controls and keeps display filters local', async ({ page }) => {
    const wsMessages: unknown[] = []
    page.on('websocket', (ws) => {
      ws.on('framesent', (event) => {
        try {
          wsMessages.push(JSON.parse(event.payload))
        } catch {
          /* non-JSON frame */
        }
      })
    })

    await page.goto('/')
    await page.locator('.dv-tab').filter({ hasText: 'Logger' }).click()
    await expect(page.locator('[data-testid="panel-logger"]')).toBeVisible()

    for (const level of ['DEBUG', 'INFO', 'WARNING', 'ERROR']) {
      await expect(page.locator(`[data-testid="log-level-${level}"]`)).toBeVisible()
    }
    await expect(page.locator('[data-testid="log-node-filter"]')).toBeVisible()
    await expect(page.locator('[data-testid="log-search"]')).toBeVisible()
    await expect(page.locator('[data-testid="log-auto-scroll"]')).toBeVisible()
    await expect(page.locator('[data-testid="log-header"] [role="columnheader"]')).toHaveText([
      'Timestamp',
      'Level',
      'Node',
      'Message',
    ])

    const before = wsMessages.filter((msg: any) => msg?.type === 'subscribe_logs').length
    await page.locator('[data-testid="log-level-DEBUG"]').click()
    await page.locator('[data-testid="log-search"]').fill('needle')
    await page.waitForTimeout(350)
    const after = wsMessages.filter((msg: any) => msg?.type === 'subscribe_logs').length

    expect(after).toBe(before)
  })
})
