import { createServer, type Server, type Socket } from 'node:net'
import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import type { Locator, Page, WebSocket as PlaywrightWebSocket } from '@playwright/test'
import type { GraphState, NodeDataResponse } from '../../src/api/types'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`
const SOURCE_ID = 'held_source'
const WORKER_ID = 'held_worker'

type WorkerEvent = {
  event: 'started' | 'cancellation_observed' | 'cancellation_acknowledged'
  process_id?: number
  value?: number
}

type WorkerStart = WorkerEvent & {
  event: 'started'
  process_id: number
  value: number
}

class WorkerControl {
  private server: Server | null = null
  private sockets = new Set<Socket>()
  private starts: WorkerStart[] = []
  private waiters: Array<(start: WorkerStart) => void> = []
  private observedCancellation = false
  private acknowledgedCancellation = false
  releaseImmediately = false

  async listen(): Promise<number> {
    this.server = createServer((socket) => {
      this.sockets.add(socket)
      socket.on('close', () => this.sockets.delete(socket))
      let message = ''
      socket.on('data', (chunk) => {
        message += chunk.toString()
        let newline = message.indexOf('\n')
        while (newline >= 0) {
          const event = JSON.parse(message.slice(0, newline)) as WorkerEvent
          message = message.slice(newline + 1)
          if (event.event === 'started') {
            const start = event as WorkerStart
            const waiter = this.waiters.shift()
            if (waiter) waiter(start)
            else this.starts.push(start)
            if (this.releaseImmediately) socket.write('1')
          } else if (event.event === 'cancellation_observed') {
            this.observedCancellation = true
          } else if (event.event === 'cancellation_acknowledged') {
            this.acknowledgedCancellation = true
          }
          newline = message.indexOf('\n')
        }
      })
    })
    await new Promise<void>((resolve, reject) => {
      this.server!.once('error', reject)
      this.server!.listen(0, '127.0.0.1', resolve)
    })
    const address = this.server.address()
    if (address === null || typeof address === 'string') throw new Error('Missing control port')
    return address.port
  }

  nextStart(): Promise<WorkerStart> {
    const existing = this.starts.shift()
    if (existing) return Promise.resolve(existing)
    return new Promise(resolve => this.waiters.push(resolve))
  }

  get cancellationAcknowledged(): boolean {
    return this.observedCancellation && this.acknowledgedCancellation
  }

  releaseAll(): void {
    this.releaseImmediately = true
    for (const socket of this.sockets) socket.write('1')
  }

  close(): Promise<void> {
    for (const socket of this.sockets) socket.destroy()
    return new Promise(resolve => this.server?.close(() => resolve()) ?? resolve())
  }
}

function uniqueWorkflowName(): string {
  const project = test.info().project.name.replace(/[^a-zA-Z0-9_-]/g, '_')
  return `held_execution_${project}_${Date.now()}_${Math.floor(Math.random() * 10000)}`
}

function heldGraph(workflowName: string, controlPort: number): GraphState {
  return {
    schema_version: 2,
    name: workflowName,
    display_name: workflowName,
    nodes: [
      {
        type: 'tool', id: SOURCE_ID, name: 'Completed source', tool_name: 'SeedNumbers',
        position: [160, 180], parameters: {}, resources: {}, output_templates: {},
        enabled: true, collapsed: false,
      },
      {
        type: 'tool', id: WORKER_ID, name: 'Held worker', tool_name: 'HeldWorkerNumbers',
        position: [520, 180], parameters: { control_port: controlPort, report_progress: true },
        resources: { max_concurrent: 1 }, output_templates: {}, enabled: true, collapsed: false,
      },
    ],
    edges: [{
      type: 'column', id: 'source-to-held-worker', source_node: SOURCE_ID,
      source_output: 'number', target_node: WORKER_ID, target_input: 'value',
    }],
    interface: { inputs: [], outputs: [] },
    config: { engine: 'wetlands', execution: 'sequential' },
  }
}

async function createAndOpenFixture(page: Page, workflowName: string, controlPort: number) {
  expect((await page.request.post(`${API_BASE}/api/v1/dev/seed`)).ok()).toBeTruthy()
  const tools = await (await page.request.get(`${API_BASE}/api/v1/tools`)).json()
  expect(tools.find((tool: { name: string }) => tool.name === 'HeldWorkerNumbers')).toMatchObject({
    tool_type: 'ProcessingTool', row_consumption: 'mapped',
  })
  const graph = heldGraph(workflowName, controlPort)
  const validation = await page.request.put(`${API_BASE}/api/v1/graph`, { data: graph })
  expect(validation.ok()).toBeTruthy()
  expect(await validation.json()).toMatchObject({ valid: true, errors: [] })
  expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
    data: { name: workflowName, display_name: workflowName },
  })).status()).toBe(201)
  expect((await page.request.put(`${API_BASE}/api/v1/workflows/${workflowName}`, {
    data: { graph },
  })).ok()).toBeTruthy()

  await page.goto('/')
  await expect(page.locator('#bioimageflow-app')).toBeVisible()
  await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
  await page.getByTestId('workflow-search').fill(workflowName)
  await page.getByTestId(`workflow-row-${workflowName}`).dblclick()
  await expect(page.getByTestId('workflow-title')).toContainText(workflowName)
  await expect(page.locator('.vue-flow__node')).toHaveCount(2)
}

async function executionStatus(page: Page) {
  const response = await page.request.get(`${API_BASE}/api/v1/execution/status`)
  expect(response.ok()).toBeTruthy()
  return response.json()
}

async function expectExactTable(panel: Locator, columns: string[], rows: string[][]) {
  const table = panel.locator('.p-datatable')
  await expect(table).toBeVisible()
  await expect.poll(async () => (
    await table.locator('.p-datatable-thead [aria-label^="Sort "]')
      .evaluateAll(buttons => buttons.map(button => button.getAttribute('aria-label')?.slice(5)))
  ), { timeout: 15_000 }).toEqual(columns)
  await expect(table.locator('.p-datatable-tbody tr')).toHaveCount(rows.length)
  for (let row = 0; row < rows.length; row++) {
    const cells = table.locator('.p-datatable-tbody tr').nth(row).locator('td')
    for (let column = 0; column < columns.length; column++) {
      const cell = cells.nth(column)
      const pathValue = cell.locator('.path-cell__path-value')
      await expect(await pathValue.count() === 1 ? pathValue : cell).toHaveText(rows[row]![column]!)
    }
  }
}

test('cancels a held real sequential worker without mutating its exact draft', async ({ page }) => {
  test.setTimeout(180_000)
  await page.addInitScript(() => {
    const NativeWebSocket = window.WebSocket
    window.WebSocket = class extends NativeWebSocket {
      constructor(url: string | URL, protocols?: string | string[]) {
        super(url, protocols)
        if (new URL(url, window.location.href).pathname === '/ws') {
          ;(window as unknown as { campaignExecutionSocket: WebSocket }).campaignExecutionSocket = this
        }
      }
    }
  })
  const executionEvents: Record<string, unknown>[] = []
  const transports: Array<{ socket: PlaywrightWebSocket; frames: Record<string, unknown>[] }> = []
  const observeSocket = (socket: PlaywrightWebSocket) => {
    if (new URL(socket.url()).pathname !== '/ws') return
    const transport = { socket, frames: [] as Record<string, unknown>[] }
    transports.push(transport)
    socket.on('framereceived', frame => {
      try {
        const event = JSON.parse(frame.payload.toString()) as Record<string, unknown>
        executionEvents.push(event)
        transport.frames.push(event)
      } catch {
        // Other WebSocket traffic is not part of this execution contract.
      }
    })
  }
  page.on('websocket', observeSocket)
  const control = new WorkerControl()
  const controlPort = await control.listen()
  const workflowName = uniqueWorkflowName()
  const siblingName = `${workflowName}_sibling`
  let workflowCreated = false
  let siblingCreated = false
  let primaryOccurred = false
  const cleanupErrors: unknown[] = []

  try {
    await createAndOpenFixture(page, workflowName, controlPort)
    workflowCreated = true
    const acceptedDraft = await (await page.request.get(
      `${API_BASE}/api/v1/workflow-drafts/${workflowName}`,
    )).json()
    // This sibling has the same declared tools and node IDs, but is never run.
    const siblingGraph = heldGraph(siblingName, controlPort)
    siblingGraph.nodes[0]!.name = 'Unexecuted sibling source'
    siblingGraph.nodes[1]!.name = 'Unexecuted sibling worker'
    expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name: siblingName, display_name: siblingName },
    })).status()).toBe(201)
    siblingCreated = true
    const savedSibling = await page.request.put(`${API_BASE}/api/v1/workflows/${siblingName}`, {
      data: { graph: siblingGraph },
    })
    expect(savedSibling.ok(), await savedSibling.text()).toBeTruthy()
    const siblingDraft = await (await page.request.get(
      `${API_BASE}/api/v1/workflow-drafts/${siblingName}`,
    )).json()
    const openExistingWorkflow = async (id: string) => {
      const panel = page.getByTestId('workflows-panel')
      if (!await panel.isVisible()) {
        const catalogGroup = page.locator('.dv-groupview').filter({
          has: page.locator('.tools-panel, .datasets-panel, [data-testid="workflows-panel"]'),
        })
        await expect(catalogGroup).toHaveCount(1)
        await catalogGroup.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
      }
      await expect(panel).toBeVisible()
      await panel.getByTestId('workflow-search').fill(id)
      await panel.getByTestId(`workflow-row-${id}`).dblclick()
      await expect(page.getByTestId('workflow-title')).toHaveText(id)
    }
    const activateCanvas = async (id: string) => {
      const title = page.getByTestId('canvas-tab').getByText(id, { exact: true })
      await expect(title).toHaveCount(1)
      await title.click()
      await expect(page.getByTestId('workflow-title')).toHaveText(id)
    }
    // A new Open is locked during Run; existing canvas tabs remain inspectable.
    await openExistingWorkflow(siblingName)
    await activateCanvas(workflowName)

    for (const [targets, detail] of [
      [[], 'Run Selected requires at least one requested execution target'],
      [['missing-worker'], 'Requested execution targets do not exist'],
      [[WORKER_ID, 'missing-worker'], 'Requested execution targets do not exist'],
    ] as const) {
      const refusal = await page.request.post(`${API_BASE}/api/v1/execution/run`, {
        data: {
          workflow_id: workflowName,
          draft_revision: acceptedDraft.draft_revision, nodes: targets,
        },
      })
      expect(refusal.status()).toBe(422)
      expect(JSON.stringify(await refusal.json())).toContain(detail)
      expect(await executionStatus(page)).toMatchObject({ state: 'idle' })
      expect(await (await page.request.get(
        `${API_BASE}/api/v1/workflow-drafts/${workflowName}`,
      )).json()).toMatchObject({
        draft_revision: acceptedDraft.draft_revision, graph: acceptedDraft.graph,
      })
      expect((await page.request.post(`${API_BASE}/api/v1/nodes/${WORKER_ID}/data/query`, {
        data: { workflow_name: workflowName },
      })).status()).toBe(404)
    }

    const runResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-workflow-button').click()
    expect((await runResponse).status()).toBe(202)

    const firstStart = await control.nextStart()
    const backendPid = await (await page.request.get(
      `${API_BASE}/api/v1/dev/e2e/process-id`,
    )).json()
    expect(firstStart).toMatchObject({ value: 1 })
    expect(firstStart.process_id).not.toBe(backendPid.process_id)

    const heldStatus = await executionStatus(page)
    expect(heldStatus).toMatchObject({
      state: 'running', workflow_id: workflowName,
      draft_revision: acceptedDraft.draft_revision,
      planned_node_ids: [SOURCE_ID, WORKER_ID],
      planned_node_names: {
        [SOURCE_ID]: 'Completed source',
        [WORKER_ID]: 'Held worker',
      },
      node_statuses: {
        [SOURCE_ID]: { status: 'executed' },
        [WORKER_ID]: { status: 'running' },
      },
    })
    expect(heldStatus.execution_id).toMatch(/^run_/)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Executing workflow…')
    await expect(page.getByTestId('execution-banner-node-count')).toHaveText('1/2 nodes complete')
    await expect(page.getByTestId('execution-banner-overall-progress')).toHaveAttribute('aria-valuenow', '50')
    await expect(page.getByTestId('execution-banner-current-node')).toContainText('Running: Held worker')
    await expect(page.getByTestId('execution-banner-current-node')).toContainText('Processing row 1/3')
    await expect(page.getByTestId('execution-banner-current-node')).toContainText('Task progress 1/4')
    await expect(page.getByTestId('execution-banner-row-progress')).toHaveCount(0)

    const sourceResponse = await page.request.post(`${API_BASE}/api/v1/nodes/${SOURCE_ID}/data/query`, {
      data: { workflow_name: workflowName },
    })
    expect(sourceResponse.ok(), await sourceResponse.text()).toBeTruthy()
    const originResult = await sourceResponse.json() as NodeDataResponse
    expect(originResult.identity_status).toBe('captured')
    expect(originResult.rows).toEqual([
      { number: 1, label: 'one' }, { number: 2, label: 'two' }, { number: 3, label: 'three' },
    ])
    expect(originResult.source_identity).toMatchObject({
      run_id: heldStatus.execution_id, node_key: SOURCE_ID,
      result_key: expect.any(String), record_id: expect.any(String),
    })
    if (!originResult.source_identity) throw new Error('Held execution has no captured source result')
    await activateCanvas(siblingName)
    const siblingSource = page.locator(`.vue-flow__node[data-id="${SOURCE_ID}"]:visible .tool-node`)
    const siblingWorker = page.locator(`.vue-flow__node[data-id="${WORKER_ID}"]:visible .tool-node`)
    await expect(siblingSource).toHaveClass(/status-unexecuted/)
    await expect(siblingWorker).toHaveClass(/status-unexecuted/)
    const previousTransport = transports.at(-1)
    if (!previousTransport) throw new Error('No real execution WebSocket was observed')
    const closed = new Promise<void>(resolve => previousTransport.socket.once('close', resolve))
    const newSocket = page.waitForEvent('websocket', socket => new URL(socket.url()).pathname === '/ws')
    await page.evaluate(() => {
      const socket = (window as unknown as { campaignExecutionSocket: WebSocket }).campaignExecutionSocket
      if (socket.readyState !== WebSocket.OPEN) throw new Error('Execution socket is not open')
      socket.close(4001, 'Reconnect execution snapshot control')
    })
    await closed
    const reconnected = await newSocket
    expect(reconnected).not.toBe(previousTransport.socket)
    await expect.poll(() => transports.find(transport => transport.socket === reconnected)
      ?.frames.find(frame => frame.type === 'status_snapshot'), { timeout: 15_000 }).toMatchObject({
      type: 'status_snapshot', state: 'running', execution_id: heldStatus.execution_id,
      workflow_id: workflowName, draft_revision: acceptedDraft.draft_revision,
      planned_node_ids: [SOURCE_ID, WORKER_ID], planned_node_names: heldStatus.planned_node_names,
      node_statuses: {
        [SOURCE_ID]: { status: 'executed' }, [WORKER_ID]: { status: 'running' },
      },
      progress: { node_id: WORKER_ID, task_current: 1, task_maximum: 4 },
    })
    await expect(page.getByTestId('workflow-title')).toContainText(siblingName)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Executing workflow…')
    await expect(page.getByTestId('execution-banner-node-count')).toHaveText('1/2 nodes complete')
    await expect(page.getByTestId('execution-banner-current-node')).toContainText('Running: Held worker')
    await expect(page.getByTestId('execution-banner-current-node')).toContainText('Task progress 1/4')
    await expect(siblingSource).toHaveClass(/status-unexecuted/)
    await expect(siblingWorker).toHaveClass(/status-unexecuted/)
    for (const nodeId of [SOURCE_ID, WORKER_ID]) {
      expect((await page.request.post(`${API_BASE}/api/v1/nodes/${nodeId}/data/query`, {
        data: { workflow_name: siblingName },
      })).status()).toBe(404)
    }
    for (const identity of [undefined, originResult.source_identity]) {
      const retained = await page.request.post(`${API_BASE}/api/v1/nodes/${SOURCE_ID}/data/query`, {
        data: { workflow_name: workflowName, ...(identity ? { result_identity: identity } : {}) },
      })
      expect(retained.ok(), await retained.text()).toBeTruthy()
      expect(await retained.json()).toMatchObject({
        source_identity: originResult.source_identity, rows: originResult.rows,
      })
    }
    for (const [id, draft] of [[workflowName, acceptedDraft], [siblingName, siblingDraft]] as const) {
      expect(await (await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${id}`)).json()).toMatchObject({
        graph: draft.graph, draft_revision: draft.draft_revision,
      })
    }
    await activateCanvas(workflowName)
    await expect(page.locator(`.vue-flow__node[data-id="${SOURCE_ID}"]:visible .tool-node`)).toHaveClass(/status-executed/)
    await expect(page.locator(`.vue-flow__node[data-id="${WORKER_ID}"]:visible .tool-node`)).toHaveClass(/status-running/)

    await page.reload()
    await expect(page.getByTestId('workflow-title')).toContainText(workflowName)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Executing workflow…')
    await expect(page.getByTestId('execution-banner-node-count')).toHaveText('1/2 nodes complete')
    await expect(page.getByTestId('execution-banner-overall-progress')).toHaveAttribute('aria-valuenow', '50')
    const recovered = await executionStatus(page)
    expect(recovered).toMatchObject({
      state: 'running', execution_id: heldStatus.execution_id,
      workflow_id: workflowName, draft_revision: acceptedDraft.draft_revision,
    })

    const injectExecutionEvent = (event: Record<string, unknown>) => page.evaluate(payload => {
      const socket = (window as unknown as { campaignExecutionSocket: WebSocket }).campaignExecutionSocket
      socket.dispatchEvent(new MessageEvent('message', { data: JSON.stringify(payload) }))
    }, event)
    const progressContext = {
      type: 'progress', node_id: WORKER_ID, status: 'row_progress',
      row: 0, total_rows: 3, task_current: 2, task_maximum: 4,
      workflow_id: workflowName, draft_revision: acceptedDraft.draft_revision,
    }
    await injectExecutionEvent({ ...progressContext, execution_id: 'run_stale_context' })
    await injectExecutionEvent({
      ...progressContext, execution_id: heldStatus.execution_id, draft_revision: 'malformed',
    })
    await expect(page.getByTestId('execution-banner-node-count')).toHaveText('1/2 nodes complete')
    await expect(page.getByTestId('execution-banner-overall-progress')).toHaveAttribute('aria-valuenow', '50')
    await expect(page.getByTestId('execution-banner-current-node')).toContainText('Task progress 1/4')
    await injectExecutionEvent({ ...progressContext, execution_id: heldStatus.execution_id })
    await expect(page.getByTestId('execution-banner-current-node')).toContainText('Task progress 2/4')

    const workerNode = page.locator(`.vue-flow__node[data-id="${WORKER_ID}"]`)
    await workerNode.click()
    await page.locator('.dv-tab').filter({ hasText: /^Nodes$/ }).click()
    await expect(page.getByTestId('clear-node-outputs')).toBeDisabled()
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await expect(page.getByRole('menuitem', { name: 'Save', exact: true })).toHaveAttribute(
      'aria-disabled', 'true',
    )
    const draftWhileHeld = await (await page.request.get(
      `${API_BASE}/api/v1/workflow-drafts/${workflowName}`,
    )).json()
    expect(draftWhileHeld).toMatchObject({
      draft_revision: acceptedDraft.draft_revision, graph: acceptedDraft.graph,
    })

    const stopResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/stop') && response.request().method() === 'POST'
    ))
    await page.getByTestId('stop-execution-button').click()
    expect((await stopResponse).status()).toBe(200)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution stopped')
    await expect(page.getByTestId('execution-banner-node-count')).toHaveText('1/2 nodes complete')
    await expect(page.getByTestId('execution-banner-overall-progress')).toHaveAttribute('aria-valuenow', '50')
    await expect.poll(async () => ({
      state: (await executionStatus(page)).state,
      cancellationAcknowledged: control.cancellationAcknowledged,
    }), {
      timeout: 15_000,
    }).toEqual({ state: 'idle', cancellationAcknowledged: true })

    const stopped = await executionStatus(page)
    expect(stopped).toMatchObject({
      execution_id: heldStatus.execution_id, workflow_id: workflowName,
      draft_revision: acceptedDraft.draft_revision,
      node_statuses: {
        [SOURCE_ID]: { status: 'executed' },
        [WORKER_ID]: { status: 'unexecuted' },
      },
    })
    const partial = await page.request.post(`${API_BASE}/api/v1/nodes/${WORKER_ID}/data/query`, {
      data: { workflow_name: workflowName },
    })
    expect(partial.status()).toBe(404)

    await page.locator(`.vue-flow__node[data-id="${SOURCE_ID}"]`).click()
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    await expectExactTable(page.getByTestId('data-table-panel'), ['number', 'label'], [
      ['1', 'one'], ['2', 'two'], ['3', 'three'],
    ])

    const rerunResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-workflow-button').click()
    const acceptedRerun = await rerunResponse
    expect(acceptedRerun.status()).toBe(202)
    const rerunContext = await acceptedRerun.json()
    expect(rerunContext).toMatchObject({
      execution_id: expect.stringMatching(/^run_/),
      workflow_id: workflowName,
      draft_revision: acceptedDraft.draft_revision,
      planned_node_ids: [SOURCE_ID, WORKER_ID],
    })
    expect(rerunContext.execution_id).not.toBe(heldStatus.execution_id)
    const firstRerunStart = await control.nextStart()
    expect(firstRerunStart).toMatchObject({ value: 1 })
    expect(firstRerunStart.process_id).not.toBe(backendPid.process_id)
    expect(await executionStatus(page)).toMatchObject({
      state: 'running', execution_id: rerunContext.execution_id,
      workflow_id: workflowName, draft_revision: acceptedDraft.draft_revision,
      planned_node_ids: [SOURCE_ID, WORKER_ID],
      node_statuses: {
        [SOURCE_ID]: { status: 'executed', cached: true },
        [WORKER_ID]: { status: 'running', cached: false },
      },
    })
    await expect(page.getByTestId('execution-banner-node-count')).toHaveText('1/2 nodes complete')
    await expect(page.getByTestId('execution-banner-overall-progress')).toHaveAttribute('aria-valuenow', '50')
    await expect.poll(() => executionEvents.some(event => event.type === 'node_state'
      && event.status === 'running' && event.node_id === WORKER_ID
      && event.execution_id === rerunContext.execution_id
      && event.workflow_id === workflowName
      && event.draft_revision === acceptedDraft.draft_revision), {
      timeout: 5_000,
    }).toBe(true)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Executing workflow…')
    control.releaseAll()
    await expect.poll(async () => {
      const status = await executionStatus(page)
      return [status.state, status.last_result?.success, status.node_statuses?.[WORKER_ID]?.status]
    }, { timeout: 60_000 }).toEqual(['idle', true, 'executed'])
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete')
    await expect(page.getByTestId('execution-banner-node-count')).toHaveText('2/2 nodes complete')
    await expect(page.getByTestId('execution-banner-overall-progress')).toHaveAttribute('aria-valuenow', '100')
    await expect.poll(() => executionEvents.filter(event => (
      event.type === 'progress' && event.execution_id === rerunContext.execution_id
    )).map(event => [event.status, event.node_id, event.row, event.total_rows]), {
      timeout: 5_000,
    }).toContainEqual(['row_complete', WORKER_ID, 0, 3])
    const firstProgress = executionEvents.find(event => (
      event.type === 'progress' && event.status === 'row_complete'
      && event.node_id === WORKER_ID && event.row === 0
      && event.execution_id === rerunContext.execution_id
    ))
    expect(firstProgress).toMatchObject({
      execution_id: rerunContext.execution_id,
      workflow_id: workflowName,
      draft_revision: acceptedDraft.draft_revision,
    })
    await expect.poll(() => executionEvents.some(event => (
      event.type === 'execution_complete' && event.execution_id === rerunContext.execution_id
    )), { timeout: 15_000 }).toBe(true)
    expect(executionEvents.find(event => (
      event.type === 'execution_complete' && event.execution_id === rerunContext.execution_id
    ))).toMatchObject({
      success: true,
      execution_id: rerunContext.execution_id,
      workflow_id: workflowName,
      draft_revision: acceptedDraft.draft_revision,
    })
    expect(executionEvents.filter(event => event.execution_id === rerunContext.execution_id)
      .every(event => event.workflow_id === workflowName
        && event.draft_revision === acceptedDraft.draft_revision)).toBe(true)
    const completed = await executionStatus(page)
    expect(completed).toMatchObject({
      execution_id: rerunContext.execution_id,
      workflow_id: workflowName,
      draft_revision: acceptedDraft.draft_revision,
      last_result: { success: true },
    })
    await page.reload()
    await expect(page.getByTestId('workflow-title')).toContainText(workflowName)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete')
    await expect(page.getByTestId('execution-banner-node-count')).toHaveText('2/2 nodes complete')
    await expect(page.getByTestId('execution-banner-overall-progress')).toHaveAttribute('aria-valuenow', '100')
    expect(await executionStatus(page)).toMatchObject({
      execution_id: rerunContext.execution_id,
      workflow_id: workflowName,
      draft_revision: acceptedDraft.draft_revision,
      last_result: { success: true },
    })

    const workerResult = await page.request.post(
      `${API_BASE}/api/v1/nodes/${WORKER_ID}/data/query`,
      { data: { workflow_name: workflowName } },
    )
    expect(workerResult.ok()).toBeTruthy()
    const result = await workerResult.json()
    expect(result.rows.map((row: Record<string, unknown>) => row.multiplied)).toEqual([4, 8, 12])
    const workerPids = new Set(
      result.rows.map((row: Record<string, unknown>) => row.process_id as number),
    )
    expect(workerPids.size).toBe(1)
    expect(workerPids.has(backendPid.process_id)).toBe(false)
    const workflowResponse = await page.request.get(`${API_BASE}/api/v1/workflows/${workflowName}`)
    expect(workflowResponse.ok()).toBeTruthy()
    const workflow = await workflowResponse.json()
    await expect.poll(async () => Promise.all([1, 2, 3].map(async (value) => {
      try {
        return await readFile(join(
          workflow.info.results_path, 'outputs', 'latest', WORKER_ID,
          `held_number_${value}.txt`,
        ), 'utf8')
      } catch {
        return null
      }
    })), { timeout: 10_000 }).toEqual([
      '1 * 4 = 4\n', '2 * 4 = 8\n', '3 * 4 = 12\n',
    ])
    await page.locator(`.vue-flow__node[data-id="${WORKER_ID}"]`).click()
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    await expectExactTable(page.getByTestId('data-table-panel'), result.columns, result.rows.map(
      (row: Record<string, unknown>) => result.columns.map((column: string) => String(row[column])),
    ))
  } catch (error) {
    primaryOccurred = true
    throw error
  } finally {
    page.off('websocket', observeSocket)
    control.releaseAll()
    try {
      await expect.poll(async () => (await executionStatus(page)).state, {
        timeout: 60_000,
      }).toBe('idle')
    } catch (error) { cleanupErrors.push(error) }
    try { await page.goto('about:blank') } catch (error) { cleanupErrors.push(error) }
    for (const id of [workflowCreated ? workflowName : null, siblingCreated ? siblingName : null]) {
      if (id === null) continue
      try {
        const deletion = await page.request.delete(`${API_BASE}/api/v1/workflows/${id}`)
        expect([200, 204, 404], await deletion.text()).toContain(deletion.status())
      } catch (error) { cleanupErrors.push(error) }
    }
    try { await control.close() } catch (error) { cleanupErrors.push(error) }
    if (primaryOccurred && cleanupErrors.length) console.error('Held reconnect cleanup failed while preserving the primary:', cleanupErrors)
  }
  if (cleanupErrors.length) throw cleanupErrors[0]
})
