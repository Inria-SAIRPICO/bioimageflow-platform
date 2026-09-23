import { readFile } from 'node:fs/promises'
import { createServer, type Server, type Socket } from 'node:net'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import type { Locator, Page } from '@playwright/test'
import type { GraphState } from '../../src/api/types'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`
const SOURCE_ID = 'completed_source'
const WORKER_ID = 'controlled_worker'
const FAILURE = 'Controlled worker failure: multiplier must not be zero'
const FAILURE_SUMMARY = `Worker task failed for node '${WORKER_ID}' (row 0).`

type WorkerStart = {
  event: 'started'
  process_id: number
  value: number
  multiplier: number
}

class WorkerControl {
  private server: Server | null = null
  private sockets = new Set<Socket>()
  private starts: WorkerStart[] = []
  private waiters: Array<(start: WorkerStart) => void> = []
  releaseImmediately = false

  async listen(): Promise<number> {
    this.server = createServer((socket) => {
      this.sockets.add(socket)
      socket.on('close', () => this.sockets.delete(socket))
      let pending = ''
      socket.on('data', (chunk) => {
        pending += chunk.toString()
        let newline = pending.indexOf('\n')
        while (newline >= 0) {
          const event = JSON.parse(pending.slice(0, newline)) as WorkerStart
          pending = pending.slice(newline + 1)
          if (event.event === 'started') {
            const waiter = this.waiters.shift()
            if (waiter) waiter(event)
            else this.starts.push(event)
            if (this.releaseImmediately) socket.write('1')
          }
          newline = pending.indexOf('\n')
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

  nextStart(timeoutMs = 60_000): Promise<WorkerStart> {
    const existing = this.starts.shift()
    if (existing) return Promise.resolve(existing)
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        const index = this.waiters.indexOf(waiter)
        if (index >= 0) this.waiters.splice(index, 1)
        reject(new Error(`Worker did not reach the control socket within ${timeoutMs}ms`))
      }, timeoutMs)
      const waiter = (start: WorkerStart) => {
        clearTimeout(timeout)
        resolve(start)
      }
      this.waiters.push(waiter)
    })
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
  return `worker_failure_${project}_${Date.now()}_${Math.floor(Math.random() * 10000)}`
}

function failureGraph(workflowName: string, controlPort: number, exposedSource = false): GraphState {
  return {
    schema_version: 1,
    name: workflowName,
    display_name: workflowName,
    nodes: [
      {
        type: 'tool', id: SOURCE_ID, name: 'Completed source', tool_name: 'SeedNumbers',
        position: [160, 180], parameters: {}, resources: {}, output_templates: {},
        enabled: true, collapsed: false,
      },
      {
        type: 'tool', id: WORKER_ID, name: 'Controlled worker', tool_name: 'HeldWorkerNumbers',
        position: [520, 180], parameters: { control_port: controlPort, multiplier: 0 },
        resources: { max_concurrent: 1 }, output_templates: {}, enabled: true, collapsed: false,
      },
    ],
    edges: [{
      type: 'column', id: 'source-to-controlled-worker', source_node: SOURCE_ID,
      source_output: 'number', target_node: WORKER_ID, target_input: 'value',
    }],
    interface: { inputs: [], outputs: exposedSource ? [{
      id: 'published-number', name: 'Published number', schema: { type: 'int' },
      source: { node: SOURCE_ID, column: 'number' },
    }] : [] },
    config: { engine: 'wetlands', execution: 'sequential' },
  }
}

async function createAndOpenFixture(
  page: Page, workflowName: string, controlPort: number, exposedSource = false,
) {
  expect((await page.request.post(`${API_BASE}/api/v1/dev/seed`)).ok()).toBeTruthy()
  const tools = await (await page.request.get(`${API_BASE}/api/v1/tools`)).json()
  expect(tools.find((tool: { name: string }) => tool.name === 'HeldWorkerNumbers')).toMatchObject({
    tool_type: 'ProcessingTool', row_consumption: 'mapped',
    inputs: { multiplier: { type: 'int', default: 4, connectable: 'never' } },
  })
  const graph = failureGraph(workflowName, controlPort, exposedSource)
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

async function fetchDraft(page: Page, workflowName: string) {
  const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`)
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

test('shows a real sequential worker failure, accepts a GUI correction, and reruns cleanly', async ({ page }) => {
  test.setTimeout(180_000)
  const control = new WorkerControl()
  const controlPort = await control.listen()
  const workflowName = uniqueWorkflowName()
  let workflowCreated = false

  try {
    await createAndOpenFixture(page, workflowName, controlPort)
    workflowCreated = true
    const initialDraft = await fetchDraft(page, workflowName)
    const runResponsePromise = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-workflow-button').click()
    const runResponse = await runResponsePromise
    expect(runResponse.status()).toBe(202)
    const firstAccepted = await runResponse.json()
    const firstRequest = runResponse.request().postDataJSON()
    expect(firstRequest).toMatchObject({
      workflow_id: workflowName,
      draft_revision: initialDraft.draft_revision,
    })
    expect(firstRequest).not.toHaveProperty('graph')
    expect(firstAccepted).toMatchObject({
      execution_id: expect.stringMatching(/^run_/),
      workflow_id: workflowName,
      draft_revision: initialDraft.draft_revision,
    })

    const firstStart = await control.nextStart()
    const backendPid = (await (await page.request.get(
      `${API_BASE}/api/v1/dev/e2e/process-id`,
    )).json()).process_id as number
    expect(firstStart).toMatchObject({ value: 1, multiplier: 0 })
    expect(firstStart.process_id).not.toBe(backendPid)
    const running = await executionStatus(page)
    expect(running).toMatchObject({
      state: 'running', execution_id: firstAccepted.execution_id,
      workflow_id: workflowName, draft_revision: initialDraft.draft_revision,
      node_statuses: {
        [SOURCE_ID]: { status: 'executed' },
        [WORKER_ID]: { status: 'running' },
      },
    })

    control.releaseAll()
    await expect.poll(async () => (await executionStatus(page)).state, {
      timeout: 60_000,
    }).toBe('idle')
    const failed = await executionStatus(page)
    expect(failed).toMatchObject({
      state: 'idle', execution_id: firstAccepted.execution_id,
      workflow_id: workflowName, draft_revision: initialDraft.draft_revision,
      last_result: { success: false },
      node_statuses: {
        [SOURCE_ID]: { status: 'executed' },
        [WORKER_ID]: {
          status: 'failed', cached: false,
          error: FAILURE_SUMMARY,
          traceback: expect.stringContaining(FAILURE),
        },
      },
    })
    expect(failed.last_result.errors).toEqual([
      expect.objectContaining({
        detail: FAILURE_SUMMARY,
        traceback: expect.stringContaining('held_worker.py'),
      }),
    ])
    const partial = await page.request.post(`${API_BASE}/api/v1/nodes/${WORKER_ID}/data/query`, {
      data: { workflow_name: workflowName },
    })
    expect(partial.status()).toBe(404)

    await expect(page.getByTestId('execution-banner-headline')).toContainText(FAILURE_SUMMARY)
    await expect(page.locator('.error-indicator .unread-badge')).toHaveText('1')
    await page.locator('.error-indicator').click()
    const historyRow = page.getByTestId('error-row').filter({ hasText: FAILURE_SUMMARY })
    await expect(historyRow).toHaveCount(1)
    await expect(historyRow).toContainText(`${WORKER_ID}:`)
    await historyRow.getByTestId('error-row-details').click()
    const errorDetails = page.getByTestId('error-details-body')
    await expect(errorDetails).toContainText(WORKER_ID)
    await expect(errorDetails).toContainText('Remote traceback:')
    await expect(errorDetails).toContainText('held_worker.py')
    await expect(errorDetails).toContainText(FAILURE)
    await page.getByRole('button', { name: 'Close', exact: true }).last().click()
    await page.getByTestId('error-history-close').click()

    await page.locator('.dv-tab').filter({ hasText: 'Logger' }).click()
    const failureLog = page.locator('[data-testid="log-entry"].log-entry--error')
      .filter({ hasText: FAILURE })
    await expect(failureLog).toHaveCount(1)
    await expect(failureLog.getByTestId('log-node-name')).toHaveText('Controlled worker')
    await expect(failureLog.getByTestId('log-message')).toContainText('Remote traceback:')
    await expect(failureLog.getByTestId('log-message')).toContainText('held_worker.py')

    await page.locator(`.vue-flow__node[data-id="${WORKER_ID}"]`).click()
    await page.locator('.dv-tab').filter({ hasText: /^Nodes$/ }).click()
    const nodePanel = page.getByTestId('panel-nodePanel')
    const multiplierRow = nodePanel.locator('.param-row').filter({ hasText: 'Multiplier' })
    const multiplierInput = multiplierRow.locator('.param-number input')
    await expect(multiplierInput).toBeEnabled()
    const acceptedCorrectionPromise = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${workflowName}`)
      && response.request().method() === 'PUT'
    ), { timeout: 15_000 })
    await multiplierInput.fill('4')
    await multiplierInput.press('Tab')
    const correctionResponse = await acceptedCorrectionPromise
    expect(correctionResponse.status()).toBe(200)
    const acceptedCorrection = await correctionResponse.json()
    expect(acceptedCorrection).toMatchObject({
      draft_revision: initialDraft.draft_revision + 1,
      validation: { valid: true, errors: [] },
    })
    expect(acceptedCorrection.graph.nodes.find(
      (node: { id: string }) => node.id === WORKER_ID,
    ).parameters.multiplier).toBe(4)
    expect((await fetchDraft(page, workflowName)).graph).toEqual(acceptedCorrection.graph)

    const rerunResponsePromise = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST'
    ), { timeout: 15_000 })
    await page.getByTestId('run-workflow-button').click()
    const rerunResponse = await rerunResponsePromise
    expect(rerunResponse.status()).toBe(202)
    const rerunAccepted = await rerunResponse.json()
    expect(rerunResponse.request().postDataJSON()).toMatchObject({
      workflow_id: workflowName,
      draft_revision: acceptedCorrection.draft_revision,
    })
    expect(rerunResponse.request().postDataJSON()).not.toHaveProperty('graph')
    expect(rerunAccepted).toMatchObject({
      execution_id: expect.stringMatching(/^run_/),
      workflow_id: workflowName,
      draft_revision: acceptedCorrection.draft_revision,
    })
    expect(rerunAccepted.execution_id).not.toBe(firstAccepted.execution_id)

    await expect.poll(async () => {
      const status = await executionStatus(page)
      return [status.state, status.last_result?.success, status.node_statuses?.[WORKER_ID]?.status]
    }, { timeout: 60_000 }).toEqual(['idle', true, 'executed'])
    const rerunStarts = await Promise.all([
      control.nextStart(), control.nextStart(), control.nextStart(),
    ])
    expect(rerunStarts.map(start => start.value)).toEqual([1, 2, 3])
    expect(rerunStarts.every(start => start.multiplier === 4)).toBe(true)
    expect(rerunStarts.every(start => start.process_id !== backendPid)).toBe(true)
    const succeeded = await executionStatus(page)
    expect(succeeded).toMatchObject({
      execution_id: rerunAccepted.execution_id,
      workflow_id: workflowName,
      draft_revision: acceptedCorrection.draft_revision,
      last_result: { success: true, errors: [] },
      node_statuses: {
        [SOURCE_ID]: { status: 'executed' },
        [WORKER_ID]: { status: 'executed', error: null, traceback: null },
      },
    })

    const workerResult = await page.request.post(
      `${API_BASE}/api/v1/nodes/${WORKER_ID}/data/query`,
      { data: { workflow_name: workflowName } },
    )
    expect(workerResult.ok()).toBeTruthy()
    const result = await workerResult.json()
    expect(result.columns).toEqual(['multiplied', 'process_id', 'report'])
    expect(result.rows.map((row: Record<string, unknown>) => row.multiplied)).toEqual([4, 8, 12])
    const resultPids = new Set(result.rows.map(
      (row: Record<string, unknown>) => row.process_id as number,
    ))
    expect(resultPids.size).toBe(1)
    expect(resultPids.has(backendPid)).toBe(false)
    const workflowResponse = await page.request.get(`${API_BASE}/api/v1/workflows/${workflowName}`)
    expect(workflowResponse.ok()).toBeTruthy()
    const workflow = await workflowResponse.json()
    expect(workflow.info.results_path).toBeTruthy()
    await expect.poll(async () => Promise.all([1, 2, 3].map(async (value) => {
      try {
        const content = await readFile(join(
          workflow.info.results_path, 'outputs', 'latest', WORKER_ID,
          `held_number_${value}.txt`,
        ), 'utf8')
        return [value, content]
      } catch (error) {
        return [value, error instanceof Error ? error.message : String(error)]
      }
    })), { timeout: 10_000 }).toEqual([
      [1, '1 * 4 = 4\n'], [2, '2 * 4 = 8\n'], [3, '3 * 4 = 12\n'],
    ])

    await page.locator(`.vue-flow__node[data-id="${WORKER_ID}"]`).click()
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    await expectExactTable(page.getByTestId('data-table-panel'), result.columns, result.rows.map(
      (row: Record<string, unknown>) => result.columns.map((column: string) => String(row[column])),
    ))
    await page.locator('.dv-tab').filter({ hasText: /^Nodes$/ }).click()
    await nodePanel.getByTestId('node-tab-execution').click()
    await expect(nodePanel.getByTestId('node-runtime-error')).toHaveCount(0)
  } finally {
    control.releaseAll()
    try {
      if (!page.isClosed()) {
        const current = await executionStatus(page).catch(() => null)
        if (current?.state === 'running') {
          await expect.poll(async () => (await executionStatus(page)).state, {
            timeout: 60_000,
          }).toBe('idle')
        }
      }
      if (workflowCreated && !page.isClosed()) {
        const deletion = await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`)
        expect(deletion.ok()).toBeTruthy()
      }
    } finally {
      await control.close()
    }
  }
})

test('refuses exposed-node Delete and Group during a real worker run, then accepts edits', async ({ page }) => {
  test.setTimeout(180_000)
  const control = new WorkerControl()
  const controlPort = await control.listen()
  const workflowName = uniqueWorkflowName()
  let workflowCreated = false
  try {
    await createAndOpenFixture(page, workflowName, controlPort, true)
    workflowCreated = true
    const before = await fetchDraft(page, workflowName)
    expect(before.graph.interface.outputs).toMatchObject([{
      id: 'published-number', source: { node: SOURCE_ID, column: 'number' },
    }])
    await page.locator(`.vue-flow__node[data-id="${WORKER_ID}"]`).click()
    await page.getByTestId('run-workflow-button').click()
    await control.nextStart()
    expect((await executionStatus(page)).state).toBe('running')

    await page.locator(`.vue-flow__node[data-id="${WORKER_ID}"]`).click({ button: 'right' })
    await page.getByText('Group into workflow', { exact: true }).click()
    await expect(page.locator('.p-toast')).toContainText('Group into workflow is unavailable')
    await expect(page.locator('.p-toast')).toContainText('locked while execution is running')

    await page.locator(`.vue-flow__node[data-id="${SOURCE_ID}"]`).click({ button: 'right' })
    await page.locator('.node-context-menu').getByText('Delete', { exact: true }).click()
    await expect(page.locator('.p-toast')).toContainText('Delete is unavailable')
    await expect(page.locator(`.vue-flow__node[data-id="${SOURCE_ID}"]`)).toBeVisible()
    await expect(page.locator(`.vue-flow__node[data-id="${WORKER_ID}"]`)).toBeVisible()
    const refused = await fetchDraft(page, workflowName)
    expect(refused.graph).toEqual(before.graph)
    expect(refused.draft_revision).toBe(before.draft_revision)

    control.releaseAll()
    await expect.poll(async () => (await executionStatus(page)).state, { timeout: 60_000 }).toBe('idle')
    await page.getByRole('menuitem', { name: 'Edit', exact: true }).click()
    await expect(page.getByRole('menuitem', { name: 'Undo', exact: true })).toBeDisabled()
    await page.keyboard.press('Escape')

    await page.locator(`.vue-flow__node[data-id="${WORKER_ID}"]`).click()
    const grouped = page.waitForResponse(response => response.url().endsWith(
      `/api/v1/workflow-drafts/${workflowName}`,
    ) && response.request().method() === 'PUT' && response.ok())
    await page.locator(`.vue-flow__node[data-id="${WORKER_ID}"]`).click({ button: 'right' })
    await page.getByText('Group into workflow', { exact: true }).click()
    await grouped
    await expect.poll(async () => (await fetchDraft(page, workflowName)).draft_revision).toBe(
      before.draft_revision + 1,
    )
    const groupedDraft = await fetchDraft(page, workflowName)
    expect(groupedDraft.graph.nodes.some((node: { type: string }) => node.type === 'workflow')).toBe(true)
    await page.getByRole('menuitem', { name: 'Edit', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Undo', exact: true }).click()
    await expect.poll(async () => (await fetchDraft(page, workflowName)).graph).toEqual(before.graph)

    await page.locator(`.vue-flow__node[data-id="${SOURCE_ID}"]`).click()
    await page.locator(`.vue-flow__node[data-id="${WORKER_ID}"]`).click({ modifiers: ['Shift'] })
    await expect(page.locator('.vue-flow__node.selected')).toHaveCount(2)
    await page.locator('.canvas-view').press('Delete')
    await expect.poll(async () => (await fetchDraft(page, workflowName)).graph.nodes.map(
      (node: { id: string }) => node.id,
    )).toEqual([])
    const deleted = await fetchDraft(page, workflowName)
    expect(deleted.graph.interface.outputs).toEqual([])
    expect(deleted.graph.edges).toEqual([])
    expect(deleted.draft_revision).toBe(before.draft_revision + 3)
    const saved = page.waitForResponse(response => response.url().endsWith(
      `/api/v1/workflows/${workflowName}`,
    ) && response.request().method() === 'PUT')
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    expect((await saved).ok()).toBeTruthy()
    await page.reload()
    await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
    await page.getByTestId('workflow-search').fill(workflowName)
    await page.getByTestId(`workflow-row-${workflowName}`).dblclick()
    await expect(page.locator('.vue-flow__node')).toHaveCount(0)
    expect((await fetchDraft(page, workflowName)).graph).toEqual(deleted.graph)
  } finally {
    control.releaseAll()
    try {
      if (!page.isClosed()) {
        await expect.poll(async () => (await executionStatus(page)).state, {
          timeout: 60_000,
        }).toBe('idle')
        if (workflowCreated) {
          const deletion = await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`)
          expect(deletion.ok()).toBeTruthy()
        }
      }
    } finally {
      await control.close()
    }
  }
})
