import { test, expect } from '@playwright/test'
import type { WebSocket as PlaywrightWebSocket } from '@playwright/test'
import type { GraphState, WorkflowDraftResponse, WorkflowInfo } from '../../src/api/types'

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

test('reconnects with an acknowledged unfiltered subscription while preserving local logger filters', async ({ page }) => {
  const api = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`
  const name = `logger_reconnect_${test.info().project.name}_${Date.now()}`
  const nodeId = 'logger_source'
  const nodeLabel = 'Logger reconnect source'
  const marker = `logger-reconnect-${Date.now()}`
  let runRequests = 0
  page.on('request', request => {
    if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/v1/execution/run') runRequests += 1
  })
  type Frame = Record<string, unknown>
  const transports: Array<{ socket: PlaywrightWebSocket; sent: Frame[]; received: Frame[] }> = []
  await page.addInitScript(() => {
    const NativeWebSocket = window.WebSocket
    window.WebSocket = class extends NativeWebSocket {
      constructor(url: string | URL, protocols?: string | string[]) {
        super(url, protocols)
        if (new URL(url, window.location.href).pathname === '/ws') {
          ;(window as unknown as { campaignLoggerSocket: WebSocket }).campaignLoggerSocket = this
        }
      }
    }
  })
  page.on('websocket', socket => {
    if (new URL(socket.url()).pathname !== '/ws') return
    const transport = { socket, sent: [] as Frame[], received: [] as Frame[] }
    transports.push(transport)
    socket.on('framesent', frame => {
      try { transport.sent.push(JSON.parse(frame.payload.toString()) as Frame) } catch { /* Non-JSON frame. */ }
    })
    socket.on('framereceived', frame => {
      try { transport.received.push(JSON.parse(frame.payload.toString()) as Frame) } catch { /* Non-JSON frame. */ }
    })
  })
  const acknowledgedSubscription = (transport: typeof transports[number]) => {
    const subscription = transport.sent.filter(frame => frame.type === 'subscribe_logs').at(-1)
    return subscription && transport.received.some(frame => frame.type === 'ack' && frame.ref === subscription.message_id)
      ? subscription : null
  }
  const graph: GraphState = {
    schema_version: 2, name, display_name: name,
    nodes: [{ type: 'tool', id: nodeId, name: nodeLabel, tool_name: 'SeedNumbers', parameters: {}, position: [200, 160] }],
    edges: [], interface: { inputs: [], outputs: [] },
    config: { engine: 'direct', execution: 'sequential' },
  }
  let info: WorkflowInfo | null = null
  let primaryOccurred = false
  let cleanupFailed = false
  let cleanupFailure: unknown
  try {
    expect((await page.request.post(`${api}/dev/seed`)).ok()).toBe(true)
    const created = await page.request.post(`${api}/workflows`, { data: { name, display_name: name } })
    expect(created.status(), await created.text()).toBe(201)
    info = await created.json() as WorkflowInfo
    const saved = await page.request.put(`${api}/workflows/${name}`, { data: { graph } })
    expect(saved.ok(), await saved.text()).toBe(true)

    await page.goto('/')
    await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
    await page.getByTestId('workflow-search').fill(name)
    await page.getByTestId(`workflow-row-${name}`).click()
    await expect(page.getByRole('region', { name: 'Selected workflow details' }).getByRole('heading')).toHaveText(name)
    const openedRequest = page.waitForRequest(request => request.method() === 'GET'
      && new URL(request.url()).pathname === `/api/v1/workflow-drafts/${name}`)
    const [opened] = await Promise.all([
      page.waitForResponse(async response => response.request() === await openedRequest),
      page.getByRole('button', { name: 'Open workflow', exact: true }).click(),
    ])
    expect(opened.ok(), await opened.text()).toBe(true)
    const accepted = await opened.json() as WorkflowDraftResponse
    expect(accepted.workflow_id).toBe(name)
    await expect(page.getByTestId('workflow-title')).toHaveText(name)
    await page.locator('.dv-tab').filter({ hasText: /^Logger$/ }).click()
    await expect(page.getByTestId('panel-logger')).toBeVisible()
    await expect.poll(() => transports.length).toBe(1)
    const initial = transports[0]!
    await expect.poll(() => acknowledgedSubscription(initial)).toMatchObject({
      type: 'subscribe_logs', node_id: null, level: null, message_id: expect.any(String),
    })
    const initialSubscriptions = initial.sent.filter(frame => frame.type === 'subscribe_logs').length
    const debug = page.getByTestId('log-level-DEBUG')
    await expect(debug).toHaveAttribute('aria-pressed', 'true')
    await debug.click()
    await page.getByTestId('log-search').fill(marker)
    await page.getByTestId('log-node-filter').click()
    await page.getByRole('option', { name: nodeLabel, exact: true }).click()

    // This existing dev publisher emits real contextual log/completion frames;
    // it does not start scientific execution or produce durable run history.
    const publish = async (phase: 'before' | 'after') => {
      const context = {
        execution_id: `${name}-${phase}`, workflow_id: name,
        draft_revision: accepted.draft_revision, node_id: nodeId,
      }
      const error = `${marker}-${phase}`
      const traceback = `${marker}-trace-${phase}`
      const response = await page.request.post(`${api}/dev/e2e/execution-failure`, {
        data: { ...context, error, traceback },
      })
      expect(response.ok(), await response.text()).toBe(true)
      const expected = { type: 'log', level: 'ERROR', message: `${error}\n${traceback}`, ...context }
      await expect.poll(() => transports.flatMap(transport => transport.received)
        .filter(frame => frame.type === 'log' && frame.execution_id === context.execution_id)).toEqual([
        { ...expected, timestamp: expect.any(Number) },
      ])
      const row = page.getByTestId('log-entry').filter({ hasText: error })
      await expect(row).toHaveCount(1)
      await expect(row.getByTestId('log-message')).toHaveText(expected.message)
      await expect(row.getByTestId('log-node-name')).toHaveText(nodeLabel)
      return error
    }
    const before = await publish('before')
    expect(initial.sent.filter(frame => frame.type === 'subscribe_logs')).toHaveLength(initialSubscriptions)

    await test.step('Close the actual socket and acknowledge the new unfiltered subscription', async () => {
      const closed = new Promise<void>(resolve => initial.socket.once('close', resolve))
      const connected = page.waitForEvent('websocket', socket => new URL(socket.url()).pathname === '/ws')
      await page.evaluate(() => {
        const socket = (window as unknown as { campaignLoggerSocket: WebSocket }).campaignLoggerSocket
        if (socket.readyState !== WebSocket.OPEN) throw new Error('Logger socket must be open before disconnect')
        socket.close(4001, 'Logger reconnect control')
      })
      await closed
      const reconnected = await connected
      expect(reconnected).not.toBe(initial.socket)
      await expect.poll(() => transports.length).toBe(2)
      expect(transports[1]!.socket).toBe(reconnected)
      await expect.poll(() => acknowledgedSubscription(transports[1]!)).toMatchObject({
        type: 'subscribe_logs', node_id: null, level: null, message_id: expect.any(String),
      })
    })

    await expect(page.getByTestId('log-entry').filter({ hasText: before })).toHaveCount(1)
    await expect(debug).toHaveAttribute('aria-pressed', 'false')
    await expect(page.getByTestId('log-search')).toHaveValue(marker)
    await expect(page.getByTestId('log-node-filter')).toContainText(nodeLabel)
    const after = await publish('after')
    await expect(page.getByTestId('log-message')).toHaveText([
      `${before}\n${marker}-trace-before`, `${after}\n${marker}-trace-after`,
    ])
    for (const phase of ['before', 'after']) {
      expect(transports.flatMap(transport => transport.received)
        .filter(frame => frame.type === 'log' && frame.execution_id === `${name}-${phase}`)).toHaveLength(1)
    }
    const finalDraft = await page.request.get(`${api}/workflow-drafts/${name}`)
    expect(finalDraft.ok(), await finalDraft.text()).toBe(true)
    expect(await finalDraft.json()).toEqual(accepted)
    expect(runRequests).toBe(0)
  } catch (error) {
    primaryOccurred = true
    throw error
  } finally {
    const cleanup: Array<() => Promise<unknown>> = [() => page.goto('about:blank')]
    if (info) {
      const generation = info.identity_generation
      cleanup.push(async () => {
        const removed = await page.request.delete(`${api}/workflows/${name}`, {
          params: { expected_identity_generation: generation },
        })
        expect(removed.ok(), await removed.text()).toBe(true)
      })
    }
    for (const action of cleanup) {
      try { await action() } catch (error) {
        if (primaryOccurred) console.error('Logger reconnect cleanup failed while preserving the primary:', error)
        else if (!cleanupFailed) { cleanupFailed = true; cleanupFailure = error }
      }
    }
  }
  if (cleanupFailed) throw cleanupFailure
})
