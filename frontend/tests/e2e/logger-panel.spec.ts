import { test, expect } from '@playwright/test'

const selectionTest = test.extend({ trace: 'retain-on-failure' })

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

  selectionTest('selects text across log rows and copies it with the keyboard', async ({ page, context, browserName }, testInfo) => {
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
    let firstFailedDrag: unknown
    try {
      await expect(async () => {
        const first = await messages.nth(0).boundingBox()
        const second = await messages.nth(1).boundingBox()
        expect(first && second).toBeTruthy()
        await page.mouse.move(first!.x + 2, first!.y + first!.height / 2)
        await page.mouse.down()
        await page.mouse.move(second!.x + second!.width - 2, second!.y + second!.height / 2, { steps: 8 })
        await page.mouse.up()
        const observed = await page.evaluate(({ first, second, capture }) => {
          const selection = window.getSelection()
          const text = selection?.toString() ?? ''
          const markers = ['first selection marker', 'second selection marker']
          if (!capture || markers.every(marker => text.includes(marker))) return { text }
          const rect = (element: Element) => element.getBoundingClientRect().toJSON()
          const attributes = (element: Element | null) => {
            if (!element) return null
            const testId = element.getAttribute('data-testid')
            return {
              tag: element.tagName,
              testId: testId && ['log-message', 'log-entry', 'log-list', 'panel-logger'].includes(testId)
                ? testId : testId ? 'other' : null,
              role: element.getAttribute('role'),
            }
          }
          const textFacts = (value: string) => ({
            markers: markers.filter(marker => value.includes(marker)), length: value.length,
          })
          const point = (x: number, y: number) => ({
            x, y, hit: attributes(document.elementFromPoint(x, y)),
            message: attributes(document.elementFromPoint(x, y)?.closest('[data-testid="log-message"]') ?? null),
          })
          const anchor = (node: Node | null | undefined, offset: number | undefined) => ({
            element: attributes(node instanceof Element ? node : node?.parentElement ?? null),
            text: textFacts(node?.textContent ?? ''), offset,
          })
          const elements = [...document.querySelectorAll('[data-testid="log-message"]')]
          const clippingAncestors = []
          for (let element = elements[0]?.parentElement; element; element = element.parentElement) {
            const style = getComputedStyle(element)
            if (!/(auto|scroll|hidden|clip)/.test(`${style.overflowX} ${style.overflowY}`)) continue
            clippingAncestors.push({
              ...attributes(element), rect: rect(element),
              overflowX: style.overflowX, overflowY: style.overflowY,
              clientLeft: element.clientLeft, clientTop: element.clientTop,
              clientWidth: element.clientWidth, clientHeight: element.clientHeight,
              scrollLeft: element.scrollLeft, scrollTop: element.scrollTop,
              scrollWidth: element.scrollWidth, scrollHeight: element.scrollHeight,
            })
          }
          const headline = document.querySelector('[data-testid="execution-banner-headline"]')
          return { text, diagnostics: {
            measured: { first, second }, current: elements.map(rect), clippingAncestors,
            start: point(first.x + 2, first.y + first.height / 2),
            end: point(second.x + second.width - 2, second.y + second.height / 2),
            viewport: { width: window.innerWidth, height: window.innerHeight, scrollX: window.scrollX, scrollY: window.scrollY },
            selection: {
              text: textFacts(text), anchor: anchor(selection?.anchorNode, selection?.anchorOffset),
              focus: anchor(selection?.focusNode, selection?.focusOffset), rangeCount: selection?.rangeCount,
            },
            banner: headline && {
              rect: rect(headline), state: ['Execution complete', 'Executing workflow…', 'Execution failed']
                .find(label => headline.textContent?.includes(label)) ?? 'other',
            },
            layout: [...document.querySelectorAll('.dv-view.visible')].map(element => ({
              rect: rect(element), active: !!element.querySelector('.dv-active-group'),
            })),
          } }
        }, { first: first!, second: second!, capture: firstFailedDrag === undefined })
        if (observed.diagnostics) firstFailedDrag = observed.diagnostics
        const selection = observed.text
        expect(selection).toContain('first selection marker')
        expect(selection).toContain('second selection marker')
      }).toPass()
      const selected = await page.evaluate(() => window.getSelection()?.toString() ?? '')
      await page.evaluate(() => document.addEventListener('copy', () => {
        document.body.dataset.nativeCopy = 'seen'
      }, { once: true }))
      await page.keyboard.press('ControlOrMeta+C')
      await expect(page.locator('body')).toHaveAttribute('data-native-copy', 'seen')
      if (browserName === 'chromium') {
        expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(selected)
      }
    } finally {
      if (firstFailedDrag !== undefined) await testInfo.attach('first-failed-native-drag', {
        body: JSON.stringify(firstFailedDrag, null, 2), contentType: 'application/json',
      })
    }
  })

  test('copies visibly filtered global and execution logs without changing attribution', async ({ page, context, browserName }) => {
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
      logger.addEntry({ level: 'INFO', nodeId: null, timestamp: 2, message: 'needle global' })
      logger.addEntry({ level: 'WARNING', nodeId: 'n1', timestamp: 3.125, message: 'needle first\ncontinuation', executionId: 'run-a', workflowId: 'workflow-a', draftRevision: 3 })
      logger.addEntry({ level: 'ERROR', nodeId: 'n1/child', timestamp: 4.5, message: 'needle second', executionId: 'run-b', workflowId: 'workflow-b', draftRevision: 7 })
      logger.addEntry({ level: 'WARNING', nodeId: 'n1', timestamp: 5, message: 'unmatched search', executionId: 'run-a', workflowId: 'workflow-a', draftRevision: 3 })
      logger.addEntry({ level: 'ERROR', nodeId: 'n2', timestamp: 6, message: 'needle other node', executionId: 'run-c', workflowId: 'workflow-c', draftRevision: 2 })
    })
    await page.getByTestId('log-level-DEBUG').click()
    await page.getByTestId('log-search').fill('needle')
    await expect(page.getByTestId('log-entry')).toHaveCount(4)
    await page.getByTestId('log-node-filter').click()
    await page.getByRole('option', { name: 'n1', exact: true }).click()
    await expect(page.getByTestId('log-message')).toHaveText(['needle first\ncontinuation', 'needle second'])
    await page.getByTestId('log-node-filter').click()
    await page.getByRole('option', { name: 'All nodes', exact: true }).click()
    await expect(page.getByTestId('log-message')).toHaveText([
      'needle global', 'needle first\ncontinuation', 'needle second', 'needle other node',
    ])
    await expect(page.getByTestId('log-entry')).toHaveCount(4)
    expect(await page.getByTestId('log-entry').evaluateAll((rows) => rows.map((row) =>
      row.querySelector('[data-testid="log-node-name"]')?.textContent?.trim() ?? '',
    ))).toEqual(['', 'n1', 'n1/child', 'n2'])
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
    expect(copiedText).toBe([
      `${stamps[0]}  INFO  needle global`,
      `${stamps[1]}  WARNING  n1  needle first\ncontinuation`,
      `${stamps[2]}  ERROR  n1/child  needle second`,
      `${stamps[3]}  ERROR  n2  needle other node`,
    ].join('\n'))
    expect(await page.evaluate(async () => {
      const { useLoggerStore } = await import('/src/stores/logger.ts')
      const logger = useLoggerStore()
      return {
        identities: logger.entries.map(({ executionId, workflowId, draftRevision, nodeId }) =>
          [executionId, workflowId, draftRevision, nodeId]),
        levels: [...logger.filter.levels],
        nodeId: logger.filter.nodeId,
        searchText: logger.filter.searchText,
      }
    })).toEqual({
      identities: [
        [null, null, null, 'n1'],
        [null, null, null, null],
        ['run-a', 'workflow-a', 3, 'n1'],
        ['run-b', 'workflow-b', 7, 'n1/child'],
        ['run-a', 'workflow-a', 3, 'n1'],
        ['run-c', 'workflow-c', 2, 'n2'],
      ],
      levels: ['INFO', 'WARNING', 'ERROR'], nodeId: null, searchText: 'needle',
    })

    await page.evaluate(() => {
      Object.defineProperty(navigator.clipboard, 'writeText', {
        configurable: true,
        value: () => Promise.reject(new Error('clipboard denied')),
      })
    })
    await copy.click()
    await expect(page.getByTestId('log-copy-error')).toHaveText('Could not copy logs')
    await expect(page.getByTestId('log-copy-success')).toHaveCount(0)

    await page.getByTestId('log-search').fill('no matches')
    await expect(page.getByTestId('log-entry')).toHaveCount(0)
    await expect(page.getByTestId('log-empty')).toHaveText('No log messages')
    await expect(copy).toBeDisabled()
  })
})
