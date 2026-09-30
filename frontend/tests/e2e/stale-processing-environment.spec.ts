import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import type { GraphState } from '../../src/api/types'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`
const ENVIRONMENT = 'platform-stale-worker-numbers'
const WORKER = 'worker'

type EnvironmentIdentity = {
  name: string
  generation_id: string
  recipe_hash: string
  worker_pids: number[]
  path: string
}

type EnvironmentEvidence = {
  inventory: EnvironmentIdentity[]
  recipe_state: string
  preparations: Array<{ action: string; name: string; replace_existing: boolean }>
  events: Array<{ operation_id: string; kind: string; message: string }>
  retired_worker_pids: number[]
  retired_workers_alive: number[]
}

async function evidence(page: Page): Promise<EnvironmentEvidence> {
  const response = await page.request.get(`${API}/dev/e2e/worker-environment`)
  expect(response.ok()).toBeTruthy()
  return response.json()
}

function generation(snapshot: EnvironmentEvidence): EnvironmentIdentity {
  return snapshot.inventory.find(item => item.name === ENVIRONMENT)!
}

function workflowName(): string {
  return `stale_worker_${test.info().project.name}_${Date.now()}`
}

function workerGraph(name: string): GraphState {
  return {
    schema_version: 1,
    name,
    display_name: name,
    nodes: [
      {
        type: 'tool', id: 'source', name: 'Source', tool_name: 'SeedNumbers',
        position: [160, 180], parameters: {}, resources: {}, output_templates: {},
        enabled: true, collapsed: false,
      },
      {
        type: 'tool', id: WORKER, name: 'Worker', tool_name: 'StaleWorkerNumbers',
        position: [520, 180], parameters: { multiplier: 3 }, resources: { max_concurrent: 1 },
        output_templates: {}, enabled: true, collapsed: false,
      },
    ],
    edges: [{
      type: 'column', id: 'source-to-worker', source_node: 'source',
      source_output: 'number', target_node: WORKER, target_input: 'value',
    }],
    interface: { inputs: [], outputs: [] },
    config: { engine: 'wetlands', execution: 'sequential' },
  }
}

async function startFromGui(page: Page, priorExecutionId?: string) {
  const responsePromise = page.waitForResponse(response => (
    response.url().endsWith('/api/v1/execution/run')
    && response.request().method() === 'POST'
  ))
  await page.getByTestId('run-workflow-button').click()
  const response = await responsePromise
  expect(response.status()).toBe(202)
  const accepted = await response.json() as { execution_id: string }
  expect(accepted.execution_id).not.toBe(priorExecutionId)
  return accepted.execution_id
}

async function finishRun(page: Page, executionId: string, success = true) {
  await expect.poll(async () => {
    const status = await (await page.request.get(`${API}/execution/status`)).json()
    return status.execution_id === executionId && status.state === 'idle'
      ? status.last_result?.success : null
  }, { timeout: 180_000 }).toBe(success)
}

async function assertExactWorkerOutput(page: Page, name: string) {
  const response = await page.request.post(`${API}/nodes/${WORKER}/data/query`, {
    data: { workflow_name: name },
  })
  expect(response.ok()).toBeTruthy()
  const data = await response.json()
  expect(data).toMatchObject({
    total_rows: 3,
    rows: [
      { multiplied: 3 },
      { multiplied: 6 },
      { multiplied: 9 },
    ],
  })
  const backend = await (await page.request.get(`${API}/dev/e2e/process-id`)).json()
  const workerProcesses = new Set(data.rows.map((row: { process_id: number }) => row.process_id))
  expect(workerProcesses.size).toBe(1)
  expect(workerProcesses.has(backend.process_id)).toBe(false)
  expect([...workerProcesses]).toEqual(generation(await evidence(page)).worker_pids)
  const workflow = await (await page.request.get(`${API}/workflows/${name}`)).json()
  const reports = await Promise.all([0, 1, 2].map(index => readFile(
    join(workflow.info.results_path, 'outputs', 'latest', WORKER, `number_${index}.txt`),
    'utf8',
  )))
  expect(reports).toEqual(['1 * 3 = 3\n', '2 * 3 = 6\n', '3 * 3 = 9\n'])
}

async function createAndOpen(page: Page, name: string, graph = workerGraph(name)) {
  expect((await page.request.post(`${API}/dev/seed`)).ok()).toBeTruthy()
  expect((await page.request.post(`${API}/workflows`, {
    data: { name, display_name: name },
  })).status()).toBe(201)
  expect((await page.request.put(`${API}/workflows/${name}`, {
    data: { graph },
  })).ok()).toBeTruthy()
  await page.goto('/')
  await expect(page.locator('#bioimageflow-app')).toBeVisible()
  await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
  await page.getByTestId('workflow-search').fill(name)
  await page.getByTestId(`workflow-row-${name}`).dblclick()
  await expect(page.getByTestId('workflow-title')).toContainText(name)
  await expect(page.locator('.vue-flow__node')).toHaveCount(2)
}

test('GUI Run replaces one real stale worker generation with visible setup and reuses it', async ({ page }, testInfo) => {
  test.setTimeout(360_000)
  const events: Record<string, unknown>[] = []
  page.on('websocket', socket => socket.on('framereceived', frame => {
    try {
      events.push(JSON.parse(frame.payload.toString()) as Record<string, unknown>)
    } catch {
      // Unrelated WebSocket traffic is outside this environment journey.
    }
  }))

  const oldResponse = await page.request.post(`${API}/dev/e2e/stale-worker-environment`)
  expect(oldResponse.ok()).toBeTruthy()
  const old = await oldResponse.json() as EnvironmentIdentity
  expect(old.worker_pids).toHaveLength(1)
  const name = workflowName()
  await createAndOpen(page, name)
  const firstExecutionId = await startFromGui(page)
  await expect.poll(async () => (await evidence(page)).preparations[0]?.action).toBe('updating')
  await page.getByTestId('open-execution-panel').click()
  const panel = page.getByTestId('panel-execution')
  const workerJob = panel.locator('button.job-row').filter({ hasText: 'Worker' })
  await expect(workerJob)
    .toContainText(`Updating execution environment ${ENVIRONMENT}`)
  await testInfo.attach('visible-real-update', { body: await workerJob.screenshot(), contentType: 'image/png' })
  await page.reload()
  await expect(page.getByTestId('workflow-title')).toContainText(name)
  await page.getByTestId('open-execution-panel').click()
  await expect(page.getByTestId('panel-execution')).toContainText(`Updating execution environment ${ENVIRONMENT}`)
  expect((await page.request.post(`${API}/dev/e2e/release-worker-environment`)).ok()).toBeTruthy()
  await finishRun(page, firstExecutionId)
  await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete')
  const afterReplacement = await evidence(page)
  const replacement = generation(afterReplacement)
  expect(afterReplacement.recipe_state).toBe('current')
  expect(replacement.generation_id).not.toBe(old.generation_id)
  expect(replacement.recipe_hash).not.toBe(old.recipe_hash)
  expect(afterReplacement.retired_worker_pids).toEqual(old.worker_pids)
  expect(afterReplacement.retired_workers_alive).toEqual([])
  expect(events.filter(event => event.type === 'environment_status'
    && event.env_name === ENVIRONMENT && event.status === 'updating')).toHaveLength(1)
  await assertExactWorkerOutput(page, name)
  expect(afterReplacement.preparations.filter(item => item.replace_existing)).toHaveLength(1)
  expect(afterReplacement.events.some(event => event.kind === 'step'
    && event.message.includes('Pixi installed'))).toBe(true)

  await page.reload()
  await expect(page.getByTestId('workflow-title')).toContainText(name)
  await page.locator(`.vue-flow__node[data-id="${WORKER}"]`).click()
  await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
  const clearResponse = page.waitForResponse(response => (
    response.url().endsWith('/api/v1/execution/clear')
    && response.request().method() === 'POST'
  ))
  await page.getByTestId('panel-nodePanel').getByTestId('clear-node-outputs').click()
  await page.getByTestId('node-destructive-confirm').click()
  expect((await clearResponse).status()).toBe(200)

  await finishRun(page, await startFromGui(page, firstExecutionId))
  await assertExactWorkerOutput(page, name)
  const reused = await evidence(page)
  expect(generation(reused)).toEqual(replacement)
  expect(reused.preparations.filter(item => item.replace_existing)).toHaveLength(1)
  expect(events.filter(event => event.type === 'environment_status'
    && event.env_name === ENVIRONMENT && event.status === 'updating')).toHaveLength(1)
  await testInfo.attach('real-generation-and-worker-evidence', {
    body: JSON.stringify({ old, replacement, reused }, null, 2), contentType: 'application/json',
  })
})

test('GUI reports an actual injected Pixi replacement failure and recovers on Run retry', async ({ page }, testInfo) => {
  test.setTimeout(360_000)
  const oldResponse = await page.request.post(`${API}/dev/e2e/stale-worker-environment`)
  expect(oldResponse.ok()).toBeTruthy()
  const old = await oldResponse.json() as EnvironmentIdentity
  expect((await page.request.post(`${API}/dev/e2e/fail-next-worker-install`)).ok()).toBeTruthy()
  const name = workflowName()
  await createAndOpen(page, name)
  const failedExecution = await startFromGui(page)
  expect((await page.request.post(`${API}/dev/e2e/release-worker-environment`)).ok()).toBeTruthy()
  await finishRun(page, failedExecution, false)
  await expect(page.getByTestId('execution-banner-headline')).toContainText('Execution failed')
  await page.locator('.dv-tab').filter({ hasText: 'Logger' }).click()
  await expect(page.getByTestId('panel-logger')).toContainText('E1 injected Pixi install failure')
  const failed = await evidence(page)
  expect(failed.preparations[0]).toMatchObject({ action: 'updating', replace_existing: true })
  expect((await page.request.post(`${API}/nodes/${WORKER}/data/query`, {
    data: { workflow_name: name },
  })).status()).toBe(404)
  const retriedExecution = await startFromGui(page, failedExecution)
  await finishRun(page, retriedExecution)
  await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete')
  await assertExactWorkerOutput(page, name)
  const recovered = await evidence(page)
  expect(generation(recovered).generation_id).not.toBe(old.generation_id)
  await testInfo.attach('actual-injected-failure-and-retry', {
    body: JSON.stringify({ old, failed, recovered }, null, 2), contentType: 'application/json',
  })
})

test('GUI refuses an incompatible core recipe before any environment mutation', async ({ page }, testInfo) => {
  const name = workflowName()
  const graph = workerGraph(name)
  const worker = graph.nodes[1]!
  if (worker.type !== 'tool') throw new Error('Expected a processing tool fixture')
  worker.tool_name = 'IncompatibleWorkerNumbers'
  const before = await evidence(page)
  await createAndOpen(page, name, graph)
  await page.locator(`.vue-flow__node[data-id="${WORKER}"]`).click()
  await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
  await expect(page.getByTestId('node-validation-errors')).toContainText('bioimageflow-core==0.0.0')
  const guiSubmissions: string[] = []
  page.on('request', request => {
    if (request.url().endsWith('/api/v1/execution/run')) guiSubmissions.push(request.url())
  })
  await page.getByTestId('run-workflow-button').click()
  await expect(page.locator('.p-toast-message')).toContainText('Validation errors')
  expect(guiSubmissions).toEqual([])
  const draft = await (await page.request.get(`${API}/workflow-drafts/${name}`)).json()
  const refused = await page.request.post(`${API}/execution/run`, {
    data: { workflow_id: name, draft_revision: draft.draft_revision },
  })
  expect(refused.status()).toBe(422)
  const refusal = await refused.json()
  expect(refusal).toMatchObject({
    error: 'validation_error',
    errors: [expect.objectContaining({ type: 'environment_incompatible', node: WORKER })],
  })
  const after = await evidence(page)
  expect(after.inventory).toEqual(before.inventory)
  expect(after.preparations).toEqual(before.preparations)
  await testInfo.attach('incompatible-core-refusal', {
    body: JSON.stringify({ guiSubmissions, refusal, before, after }, null, 2),
    contentType: 'application/json',
  })
})
