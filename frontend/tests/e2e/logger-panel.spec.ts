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

    const failure = await page.evaluate(() => fetch(
      '/api/v1/dev/e2e/execution-failure',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          execution_id: 'logger-filter-execution',
          workflow_id: 'logger-filter-workflow',
          draft_revision: 0,
          node_id: 'logger-filter-node',
          error: 'logger-filter-sentinel',
          traceback: 'logger-filter-traceback',
        }),
      },
    ).then((response) => response.ok))
    expect(failure).toBe(true)
    const sentinel = page.getByTestId('log-entry').filter({
      hasText: 'logger-filter-sentinel',
    })
    await expect(sentinel).toBeVisible()

    const before = wsMessages.filter((msg: any) => msg?.type === 'subscribe_logs').length
    await page.locator('[data-testid="log-level-DEBUG"]').click()
    const search = page.locator('[data-testid="log-search"]')
    await search.fill('needle')
    await expect(search).toHaveValue('needle')
    await expect(sentinel).toHaveCount(0)
    const after = wsMessages.filter((msg: any) => msg?.type === 'subscribe_logs').length

    expect(after).toBe(before)
  })

  test('selects text across log rows and copies it with the keyboard', async ({ page, context, browserName }) => {
    if (browserName === 'chromium') await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    await page.goto('/')
    await page.locator('.dv-tab').filter({ hasText: 'Logger' }).click()
    await page.evaluate(async () => {
      const { useLoggerStore } = await import('/src/stores/logger.ts')
      const logger = useLoggerStore()
      logger.clearEntries()
      logger.addEntry({ level: 'INFO', nodeId: null, timestamp: 1, message: 'first selection marker' })
      logger.addEntry({ level: 'ERROR', nodeId: null, timestamp: 2, message: 'second selection marker' })
    })

    const messages = page.getByTestId('log-message')
    await expect(messages).toHaveCount(2)
    const first = await messages.nth(0).boundingBox()
    const second = await messages.nth(1).boundingBox()
    expect(first && second).toBeTruthy()
    await page.mouse.move(first!.x + 2, first!.y + first!.height / 2)
    await page.mouse.down()
    await page.mouse.move(second!.x + second!.width - 2, second!.y + second!.height / 2, { steps: 8 })
    await page.mouse.up()

    const selected = await page.evaluate(() => window.getSelection()?.toString() ?? '')
    expect(selected).toContain('first selection marker')
    expect(selected).toContain('second selection marker')
    await page.evaluate(() => document.addEventListener('copy', () => {
      document.body.dataset.nativeCopy = 'seen'
    }, { once: true }))
    await page.keyboard.press('ControlOrMeta+C')
    await expect(page.locator('body')).toHaveAttribute('data-native-copy', 'seen')
    if (browserName === 'chromium') {
      expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(selected)
    }
  })

  test('copies exactly the filtered logs and reports clipboard failures', async ({ page, context, browserName }) => {
    if (browserName === 'chromium') await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    await page.goto('/')
    await page.locator('.dv-tab').filter({ hasText: 'Logger' }).click()
    const copy = page.getByTestId('log-copy')
    await expect(copy).toBeDisabled()
    await page.evaluate(async () => {
      const { useLoggerStore } = await import('/src/stores/logger.ts')
      const logger = useLoggerStore()
      logger.clearEntries()
      logger.addEntry({ level: 'DEBUG', nodeId: 'n1', timestamp: 1, message: 'needle hidden level' })
      logger.addEntry({ level: 'INFO', nodeId: 'n2', timestamp: 2, message: 'needle hidden node' })
      logger.addEntry({ level: 'WARNING', nodeId: 'n1', timestamp: 3.125, message: 'needle first\ncontinuation' })
      logger.addEntry({ level: 'ERROR', nodeId: 'n1/child', timestamp: 4.5, message: 'needle second' })
      logger.addEntry({ level: 'WARNING', nodeId: 'n1', timestamp: 5, message: 'unmatched search' })
      logger.setFilter({ levels: new Set(['WARNING', 'ERROR']), nodeId: 'n1', searchText: 'needle' })
    })
    await expect(page.getByTestId('log-entry')).toHaveCount(2)
    await expect(copy).toBeEnabled()
    const stamps = await page.getByTestId('log-timestamp').allTextContents()
    if (browserName === 'firefox') {
      await page.evaluate(() => Object.defineProperty(navigator.clipboard, 'writeText', {
        configurable: true,
        value: (text: string) => {
          document.body.dataset.copiedLogs = text
          return Promise.resolve()
        },
      }))
    }
    await copy.click()
    await expect(page.getByTestId('log-copy-success')).toHaveText('Logs copied')
    const copiedText = browserName === 'chromium'
      ? await page.evaluate(() => navigator.clipboard.readText())
      : await page.locator('body').getAttribute('data-copied-logs')
    expect(copiedText).toBe(`${stamps[0]}  WARNING  n1  needle first\ncontinuation\n${stamps[1]}  ERROR  n1/child  needle second`)
    expect(await page.evaluate(async () => {
      const { useLoggerStore } = await import('/src/stores/logger.ts')
      const logger = useLoggerStore()
      return {
        count: logger.entries.length,
        levels: [...logger.filter.levels],
        nodeId: logger.filter.nodeId,
        searchText: logger.filter.searchText,
      }
    })).toEqual({ count: 5, levels: ['WARNING', 'ERROR'], nodeId: 'n1', searchText: 'needle' })

    await page.evaluate(() => {
      Object.defineProperty(navigator.clipboard, 'writeText', {
        configurable: true,
        value: () => Promise.reject(new Error('clipboard denied')),
      })
    })
    await copy.click()
    await expect(page.getByTestId('log-copy-error')).toHaveText('Could not copy logs')
    await expect(page.getByTestId('log-copy-success')).toHaveCount(0)

    await page.evaluate(async () => {
      const { useLoggerStore } = await import('/src/stores/logger.ts')
      useLoggerStore().setFilter({ searchText: 'no matches' })
    })
    await expect(page.getByTestId('log-entry')).toHaveCount(0)
    await expect(copy).toBeDisabled()
  })
})
