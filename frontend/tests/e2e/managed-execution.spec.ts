import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'
import { readFile } from 'node:fs/promises'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`
const RUN_ID = 'run_0123456789abcdef0123456789abcdef'
const PROFILE_ID = 'profile_0123456789abcdef0123456789abcdef'
const PLAN_DIGEST = `sha256:${'c'.repeat(64)}`

type ToolMetadata = {
  name: string
  display_name: string
  tool_type: string
  accepts_upstream?: boolean
  inputs: Record<string, { required?: boolean }>
}

function uniqueDisplayName(): string {
  const project = test.info().project.name.replace(/[^a-zA-Z0-9_-]/g, '_')
  return `Managed Execution ${project} ${Date.now()} ${Math.floor(Math.random() * 10000)}`
}

function deriveWorkflowId(value: string): string {
  return value
    .trim()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .replace(/_+/g, '_')
    .toLowerCase()
}

async function seedSourceTool(page: Page): Promise<ToolMetadata> {
  const seeded = await page.request.post(`${API_BASE}/api/v1/dev/seed`)
  expect(seeded.ok()).toBeTruthy()
  const response = await page.request.get(`${API_BASE}/api/v1/tools`)
  expect(response.ok()).toBeTruthy()
  const tools = (await response.json()) as ToolMetadata[]
  const source = tools.find(tool => tool.name === 'SeedNumbers')
  expect(source).toBeTruthy()
  return source!
}

async function createWorkflow(page: Page, displayName: string): Promise<void> {
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: 'New', exact: true }).click()
  await page.locator('[data-testid="workflow-display-name-input"]').fill(displayName)
  await page.locator('[data-testid="workflow-dialog-submit"]').click()
  await expect(page.locator('[data-testid="workflow-dialog"]')).not.toBeVisible()
}

async function addSourceNode(
  page: Page,
  source: ToolMetadata,
  workflowId: string,
): Promise<void> {
  await page.goto('about:blank')
  const current = await page.request.get(`${API_BASE}/api/v1/workflows/${workflowId}`)
  expect(current.ok()).toBeTruthy()
  const document = await current.json()
  document.graph.nodes = [{
    type: 'tool',
    id: 'seed_1',
    name: source.display_name,
    tool_name: source.name,
    position: [300, 180],
    parameters: {},
  }]
  const saved = await page.request.put(`${API_BASE}/api/v1/workflows/${workflowId}`, {
    data: { graph: document.graph },
  })
  expect(saved.ok()).toBeTruthy()
  const draft = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowId}`)
  expect(draft.ok()).toBeTruthy()
  const draftRevision = (await draft.json()).draft_revision
  const reset = await page.request.post(
    `${API_BASE}/api/v1/workflow-drafts/${workflowId}/reset-to-saved`,
    { data: { expected_revision: draftRevision, updated_by: 'frontend' } },
  )
  expect(reset.ok()).toBeTruthy()
  await page.goto('/')
  await expect(page.locator('.vue-flow__node[data-id="seed_1"]')).toBeVisible()
}

function managedSnapshot(workflowId: string) {
  return {
    revision: 2,
    execution_id: RUN_ID,
    workflow_id: workflowId,
    draft_revision: 1,
    command: 'run',
    retry_of_execution_id: null,
    child_execution_ids: [],
    backend: 'managed_remote',
    target_id: PROFILE_ID,
    target_label: 'Managed Cluster',
    target_mode: 'managed_remote',
    scheduler_job_id: 'slurm-4242',
    state: 'succeeded',
    jobs: {
      seed_1: {
        scoped_node_path: 'seed_1',
        state: 'succeeded',
        row: 1,
        total_rows: 1,
        current: 1,
        maximum: 1,
        message: 'Completed remotely',
        result_key: 'result-seed',
        record_id: 'record-seed',
        executor_label: 'cpu-workers',
        route_reason: 'Managed cluster route',
        effective_resources: { cpu: 1 },
        diagnostic: null,
        started_at: '2026-08-29T10:00:00Z',
        finished_at: '2026-08-29T10:00:05Z',
        updated_at: '2026-08-29T10:00:05Z',
      },
    },
    progress_cursor: 4,
    actions: {
      cancel: { available: false, reason: 'Execution is succeeded.' },
      retry: { available: true, reason: null },
      recompute: { available: true, reason: null },
      download_results: { available: true, reason: null },
      cleanup: { available: true, reason: null },
    },
    diagnostics: [],
    observation: {
      reachable: true,
      observed_at: '2026-08-29T10:00:05Z',
      error: null,
    },
    created_at: '2026-08-29T10:00:00Z',
    updated_at: '2026-08-29T10:00:05Z',
    finished_at: '2026-08-29T10:00:05Z',
  }
}

async function fulfillJson(route: Route, json: unknown, status = 200): Promise<void> {
  await route.fulfill({ status, contentType: 'application/json', json })
}

test('managed execution resolves paths, retains its run, downloads results, and cleans up', { tag: '@critical' }, async ({ page }) => {
  const displayName = uniqueDisplayName()
  const workflowId = deriveWorkflowId(displayName)
  const source = await seedSourceTool(page)
  let preflightCount = 0
  let submitCount = 0
  let listCount = 0
  let cleanupPlanCount = 0
  let cleanupApplyCount = 0

  await page.route('**/api/v1/execution/targets', route => fulfillJson(route, {
    capabilities: {
      schema: 'bioimageflow.execution_capabilities.v1',
      capabilities: {
        remote_cluster_bootstrap: { supported: true, reason: null },
        remote_cluster_validation: { supported: true, reason: null },
        remote_cluster_planning: { supported: true, reason: null },
        idempotent_planned_submission: { supported: true, reason: null },
        durable_remote_diagnostics: { supported: true, reason: null },
      },
    },
    targets: [
      {
        id: 'local', name: 'Local', kind: 'local', mode: 'local', available: true,
        disabled_reason: null, profile_revision: null,
      },
      {
        id: PROFILE_ID, name: 'Managed Cluster', kind: 'profile', mode: 'managed_remote',
        available: true, disabled_reason: null, profile_revision: 3,
      },
      {
        id: 'profile_unavailable', name: 'Unavailable Cluster', kind: 'profile',
        mode: 'managed_remote', available: false,
        disabled_reason: 'Gateway capability is unavailable.', profile_revision: 1,
      },
    ],
  }))
  await page.route('**/api/v1/execution/preflight', async route => {
    preflightCount += 1
    const request = route.request().postDataJSON()
    expect(request).toMatchObject({
      workflow_id: workflowId,
      target_id: PROFILE_ID,
      profile_revision: 3,
      requested_nodes: null,
    })
    if (preflightCount === 1) {
      expect(request.node_path_choices).toEqual({})
      await fulfillJson(route, {
        kind: 'resolution_required',
        remote_node_paths: {
          schema: 'bioimageflow.remote_node_path_plan.v1',
          allocates_resources: false,
          reads_local_files: false,
          inputs: [{
            scoped_node_path: 'seed_1',
            input_name: 'source_path',
            value_shape: 'path',
            nullable: false,
            path_picker: 'file',
            current_paths: ['/cluster/incoming/image.tif'],
            cluster_compatible: true,
          }],
        },
        unresolved: [{ scoped_node_path: 'seed_1', input_name: 'source_path' }],
      })
      return
    }
    expect(request.node_path_choices).toEqual({
      seed_1: {
        source_path: { source: 'cluster', value: '/cluster/data/image.tif' },
      },
    })
    await fulfillJson(route, {
      kind: 'ready',
      token: 'managed-submit-token',
      expires_at: 1_800_000_000,
      resolved_inputs: 1,
    })
  })
  await page.route(/\/api\/v1\/executions(?:\?.*)?$/, async route => {
    if (route.request().method() === 'POST') {
      submitCount += 1
      expect(route.request().postDataJSON()).toMatchObject({
        token: 'managed-submit-token',
        workflow_id: workflowId,
        target_id: PROFILE_ID,
        requested_nodes: null,
      })
      await fulfillJson(route, managedSnapshot(workflowId), 202)
      return
    }
    listCount += 1
    await fulfillJson(route, {
      items: [managedSnapshot(workflowId)],
      total: 1,
      offset: 0,
      limit: 50,
    })
  })
  await page.route(`**/api/v1/executions/${RUN_ID}/result`, route => route.fulfill({
    status: 200,
    contentType: 'application/zip',
    headers: { 'Content-Disposition': `attachment; filename="${RUN_ID}-results.zip"` },
    body: 'verified managed result',
  }))
  await page.route(`**/api/v1/executions/${RUN_ID}/cleanup/plan`, async route => {
    cleanupPlanCount += 1
    expect(route.request().postDataJSON()).toEqual({ older_than_seconds: 0 })
    await fulfillJson(route, {
      execution_id: RUN_ID,
      plan_digest: PLAN_DIGEST,
      plan: {
        schema: 'bioimageflow.cluster_cleanup_plan.v1',
        plan_id: 'cleanup-managed-run',
        root_revision: 4,
        candidates: [{
          namespace: 'runs',
          identity: RUN_ID,
          path: `runs/${RUN_ID}`,
          size: 4096,
          reference_reasons: ['result bundle'],
          consequences: ['removes reconnectable cluster artifacts'],
        }],
      },
    })
  })
  await page.route(`**/api/v1/executions/${RUN_ID}/cleanup`, async route => {
    cleanupApplyCount += 1
    expect(route.request().postDataJSON()).toEqual({ plan_digest: PLAN_DIGEST })
    await fulfillJson(route, {
      execution_id: RUN_ID,
      report: {
        schema: 'bioimageflow.cluster_cleanup_report.v1',
        plan_id: 'cleanup-managed-run',
        removed: [RUN_ID],
        skipped: {},
      },
    })
  })

  await page.goto('/')
  await createWorkflow(page, displayName)
  await addSourceNode(page, source, workflowId)

  const targetSelector = page.locator('[data-testid="execution-target-selector"]')
  await targetSelector.click()
  await expect(page.getByRole('option', { name: 'Unavailable Cluster' })).toHaveCount(0)
  await page.getByRole('option', { name: 'Managed Cluster', exact: true }).click()
  await expect(page.locator('[data-testid="managed-submit-warning"]')).toContainText(
    'allocated before its ID is returned',
  )

  await page.locator('[data-testid="run-workflow-button"]').click()
  const pathDialog = page.locator('[data-testid="remote-execution-dialog"]')
  await expect(pathDialog).toBeVisible()
  await pathDialog
    .locator('[data-testid="remote-path-source-seed_1-source_path-0"]')
    .getByRole('button', { name: 'Cluster', exact: true })
    .click()
  await pathDialog.getByPlaceholder('/absolute/cluster/path').fill('/cluster/data/image.tif')
  await pathDialog.locator('[data-testid="prepare-remote-execution"]').click()

  await expect(pathDialog).not.toBeVisible()
  expect(preflightCount).toBe(2)
  expect(submitCount).toBe(1)

  await page.reload()
  await page.locator('.dv-tab').filter({ hasText: /^Execution$/ }).click()
  const executionPanel = page.locator('[data-testid="panel-execution"]')
  await expect(executionPanel).toBeVisible()
  await expect(executionPanel).toContainText(RUN_ID)
  await expect(executionPanel).toContainText('slurm-4242')
  await expect(executionPanel).toContainText('managed remote')
  await expect(executionPanel).toContainText('100%')
  expect(listCount).toBeGreaterThanOrEqual(1)

  const downloadPromise = page.waitForEvent('download')
  await executionPanel.locator('[data-testid="execution-results"]').click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe(`${RUN_ID}-results.zip`)
  const downloadPath = await download.path()
  expect(downloadPath).not.toBeNull()
  expect(await readFile(downloadPath!, 'utf8')).toBe('verified managed result')

  await executionPanel.locator('[data-testid="execution-cleanup"]').click()
  const cleanupDialog = page.locator('[data-testid="execution-cleanup-dialog"]')
  await expect(cleanupDialog).toBeVisible()
  await expect(cleanupDialog).toContainText(RUN_ID)
  await expect(cleanupDialog).toContainText('4.0 KiB')
  await expect(cleanupDialog).toContainText('result bundle')
  await expect(cleanupDialog).toContainText('removes reconnectable cluster artifacts')
  await cleanupDialog.locator('[data-testid="confirm-execution-cleanup"]').click()
  await expect(cleanupDialog).not.toBeVisible()
  await expect(executionPanel).toContainText('platform history entry is retained')
  expect(cleanupPlanCount).toBe(1)
  expect(cleanupApplyCount).toBe(1)

  await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowId}`).catch(() => undefined)
})
