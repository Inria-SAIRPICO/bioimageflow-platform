import { expect, test, type Page } from '@playwright/test'
import { writeFile } from 'node:fs/promises'
import type { WorkflowDraftResponse } from '../../src/api/workflowDrafts'

const favoriteTest = test.extend({ trace: 'retain-on-failure' })

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`
const environmentA = '68ff94c5-b649-4dc5-9d98-605e82736e3b'
const environmentB = '0767ed99-f301-445a-8c31-c75462303fde'
const resultIdentity = {
  run_id: 'run-captured',
  node_key: 'seed',
  result_key: 'result-captured',
  record_id: 'record-captured',
}

async function openNodeData(page: Page, workflowName: string): Promise<void> {
  await page.goto('/')
  await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
  await page.getByTestId('workflow-search').fill(workflowName)
  await page.getByTestId(`workflow-row-${workflowName}`).click()
  await expect(page.getByRole('region', { name: 'Selected workflow details' }).getByRole('heading')).toHaveText(workflowName)
  // Pair this explicit Open's draft request with its response; an earlier
  // startup read of the same workflow is not the acceptance boundary.
  const openedRequest = page.waitForRequest(request => request.method() === 'GET'
    && new URL(request.url()).pathname === `/api/v1/workflow-drafts/${workflowName}`)
  const [opened] = await Promise.all([
    page.waitForResponse(async response => response.request() === await openedRequest),
    page.getByRole('button', { name: 'Open workflow', exact: true }).click(),
  ])
  expect(opened.ok(), await opened.text()).toBeTruthy()
  const accepted = await opened.json() as WorkflowDraftResponse
  expect(accepted.graph.display_name).toBe(workflowName)
  expect(accepted.graph.nodes).toEqual(expect.arrayContaining([expect.objectContaining({ id: 'seed' })]))
  await expect(page.getByTestId('workflow-title')).toContainText(workflowName)
  const seed = page.locator('.vue-flow__node[data-id="seed"]')
  await expect(seed).toBeVisible()
  await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
  await seed.click()
  await expect(page.getByTestId('open-napari-42-mask')).toBeVisible({ timeout: 15000 })
}

async function fixture(page: Page) {
  const workflowName = `napari_chooser_${test.info().project.name}_${Date.now()}`
  expect((await page.request.post(`${API_BASE}/api/v1/dev/seed`)).ok()).toBeTruthy()
  expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
    data: { name: workflowName, display_name: workflowName },
  })).ok()).toBeTruthy()
  expect((await page.request.put(`${API_BASE}/api/v1/workflows/${workflowName}`, { data: { graph: {
    schema_version: 2,
    name: workflowName,
    display_name: workflowName,
    nodes: [{
      type: 'tool', id: 'seed', name: 'Seed', tool_name: 'SeedNumbers',
      position: [180, 160], parameters: {}, viewer_additions: {},
    }],
    edges: [], interface: { inputs: [], outputs: [] },
    config: { engine: 'direct', execution: 'sequential' },
  } } })).ok()).toBeTruthy()

  const openBodies: Record<string, unknown>[] = []
  const resolveBodies: Record<string, unknown>[] = []
  let favorite: string | null = null
  let preferenceRevision = 0
  let identityGeneration = 0
  const favoriteBodies: Record<string, unknown>[] = []
  const controls = {
    projectionQueryCount: 0,
    projectedIdentity: resultIdentity,
    environmentAStatus: 'compatible',
    environmentBStatus: 'compatible',
    resolveFailure: false,
    openFailure: false,
    resolveGate: null as Promise<void> | null,
    pendingResolveCount: 0,
    effectiveDefault: environmentA,
    readerId: 'retained.reader',
  }

  await page.route('**/api/v1/data-table/query', async route => {
    controls.projectionQueryCount += 1
    await route.fulfill({ json: {
      mode: 'merged',
      sources: [{
        node_id: 'seed', role: 'anchor', label: 'Seed', tool_name: 'SeedNumbers',
        columns: null, column_aliases: {}, result_identity: controls.projectedIdentity,
      }],
      columns: [{
        id: 's0:mask', label: 'mask', type: 'str', source_node_id: 'seed', source_column: 'mask',
        viewer: { napari: { required_packages: [], recommended_packages: [], napari_version: null, reader_id: 'retained.reader' } },
        viewer_status: 'captured',
      }],
      rows: Array.from({ length: 30 }, (_, offset) => ({
        index: `row-${offset}`, values: { 's0:mask': `/captured/labels-${42 + offset}.custom` },
        source_rows: { seed: 42 + offset },
      })),
      total_rows: 30,
      unfiltered_total_rows: 30,
      page: 0,
      page_size: 250,
    } })
  })
  await page.route('**/api/v1/napari/environments', route => route.fulfill({ json: {
    revision: 3,
    environments: [
      { id: environmentA, registration_order: 0, name: 'Microscopy', ownership: 'external', kind: 'venv', root: '/a', interpreter: '/a/python', interpreter_identity: 'a', launch: { strategy: 'interpreter', argv_prefix: ['/a/python'] }, inventory: { python_version: '3.12', napari_version: '0.9.1', distributions: [], fingerprint: 'a', probed_at: '2026-09-15T10:00:00Z' }, state: 'ready' },
      { id: environmentB, registration_order: 1, name: 'Tracking', ownership: 'external', kind: 'venv', root: '/b', interpreter: '/b/python', interpreter_identity: 'b', launch: { strategy: 'interpreter', argv_prefix: ['/b/python'] }, state: 'ready' },
    ],
    default_environment_id: environmentA,
    filename_rules: [], operations: [],
  } }))
  await page.route('**/api/v1/napari/viewer-preferences', route => route.fulfill({ json: {
    preferences_version: 1,
    revision: preferenceRevision,
    favorites: favorite ? [{
      key: { kind: 'persistent', workspace_id: '300e69e0-ef55-4d22-928c-38bf9bf30aae', workflow_id: workflowName, identity_generation: identityGeneration, node_path: ['seed'], output_key: 'mask' },
      environment_id: favorite,
    }] : [],
  } }))
  await page.route('**/api/v1/napari/resolve', async route => {
    const request = route.request().postDataJSON()
    resolveBodies.push(request)
    if (controls.resolveFailure) {
      await route.fulfill({ status: 404, json: { detail: 'Captured result no longer exists' } })
      return
    }
    if (controls.resolveGate && request.result_identity.result_key === controls.projectedIdentity.result_key) {
      controls.pendingResolveCount += 1
      await controls.resolveGate
      controls.pendingResolveCount -= 1
    }
    identityGeneration = request.identity_generation
    const candidates = [
      { environment_id: environmentA, name: 'Microscopy', status: controls.environmentAStatus, label: 'Required packages installed', reason: favorite === environmentA ? 'Selected favorite' : 'Selected by global default', preference: favorite === environmentA ? 'favorite' : 'global_default', issues: [], missing_recommended_packages: [], reader_id: controls.readerId },
      { environment_id: environmentB, name: 'Tracking', status: controls.environmentBStatus, label: 'Required packages installed', reason: favorite === environmentB ? 'Selected favorite' : 'Compatible fallback', preference: favorite === environmentB ? 'favorite' : 'other', issues: [], missing_recommended_packages: [], reader_id: controls.readerId },
    ]
    const effective = candidates.find(candidate => candidate.status === 'compatible' && candidate.environment_id === favorite)
      ?? candidates.find(candidate => candidate.status === 'compatible' && candidate.environment_id === controls.effectiveDefault)
      ?? candidates.find(candidate => candidate.status === 'compatible')
    await route.fulfill({ json: {
      artifact_identity: request.result_identity,
      preference_key: { kind: 'persistent', workspace_id: '300e69e0-ef55-4d22-928c-38bf9bf30aae', workflow_id: workflowName, identity_generation: request.identity_generation, node_path: ['seed'], output_key: 'mask' },
      workflow_id: workflowName,
      identity_generation: request.identity_generation,
      node_path: ['seed'], output_key: 'mask', filename: 'labels.ome.tif',
      candidates,
      effective_environment_id: effective?.environment_id ?? null,
      effective_reason: effective?.reason ?? 'No registered environment has verified required packages',
    } })
  })
  await page.route('**/api/v1/napari/viewer-preferences/favorite/toggle', async route => {
    const request = route.request().postDataJSON()
    favoriteBodies.push(request)
    expect(request.expected_revision).toBe(preferenceRevision)
    favorite = favorite === request.environment_id ? null : request.environment_id
    preferenceRevision += 1
    await route.fulfill({ json: {
      preferences_version: 1,
      revision: preferenceRevision,
      favorites: favorite ? [{ key: request.key, environment_id: favorite }] : [],
    } })
  })
  await page.route('**/api/v1/napari/open', async route => {
    openBodies.push(route.request().postDataJSON())
    await route.fulfill(controls.openFailure
      ? { status: 504, json: { detail: { error: 'napari_open_outcome_unknown', detail: 'Open outcome unknown; inspect the viewer before retrying' } } }
      : { json: { status: 'ok' } })
  })

  return { workflowName, controls, openBodies, resolveBodies, favoriteBodies }
}

function picker(page: Page) {
  return page.locator('[data-testid="napari-environment-picker"]:visible')
}

function expectedOpen(workflowName: string, environmentId: string, row = 42, clearLayers = false) {
  return {
    paths: [`/captured/labels-${row}.custom`], environment_id: environmentId,
    clear_layers: clearLayers, reader_id: 'retained.reader', node_id: 'seed',
    row, col: 'mask', workflow_name: workflowName, result_identity: resultIdentity,
  }
}

test('napari captured result launches primary, one-shot and replacement exactly once', async ({ page }) => {
  const state = await fixture(page)
  await openNodeData(page, state.workflowName)
  const primary = page.getByTestId('open-napari-42-mask')
  await expect(primary).toHaveAttribute('aria-label', 'Open in Microscopy')
  expect(state.resolveBodies).toContainEqual(expect.objectContaining({
    workflow_id: state.workflowName, node_path: ['seed'], output_key: 'mask', row: 42,
    result_identity: resultIdentity,
  }))
  expect(state.openBodies).toHaveLength(0)
  await primary.click()
  await expect.poll(() => state.openBodies.length).toBe(1)
  expect(state.openBodies[0]).toEqual(expectedOpen(state.workflowName, environmentA))
  await page.getByTestId('choose-napari-42-mask').click()
  await expect(picker(page)).toContainText('Will open in Microscopy')
  await expect(picker(page).locator('button[aria-pressed="true"]')).toHaveCount(0)
  await picker(page).getByRole('button', { name: 'Open once in Tracking' }).click()
  await expect.poll(() => state.openBodies.length).toBe(2)
  expect(state.openBodies[1]).toEqual(expectedOpen(state.workflowName, environmentB))
  const replace = picker(page).getByRole('button', { name: 'Clear layers, then open' })
  await expect(replace).toHaveAttribute('title', 'Clear all layers in Microscopy, then open mask')
  await replace.click()
  await expect.poll(() => state.openBodies.length).toBe(3)
  expect(state.openBodies[2]).toEqual(expectedOpen(state.workflowName, environmentA, 42, true))
  expect(state.favoriteBodies).toEqual([])
})

favoriteTest('napari exclusive structural favorite replaces, survives reload across rows and unsets', async ({ page }) => {
  const state = await test.step('Create captured-output fixture', () => fixture(page))
  await test.step('Replace the exclusive favorite on row 42', async () => {
    await openNodeData(page, state.workflowName)
    await page.getByTestId('choose-napari-42-mask').click()
    const menu = picker(page)
    await menu.getByRole('button', { name: 'Set Microscopy as favorite for this output' }).click()
    await expect(menu.locator('button[aria-pressed="true"]')).toHaveCount(1)
    await menu.getByRole('button', { name: 'Set Tracking as favorite for this output' }).click()
    await expect(menu.getByTestId(`napari-environment-${environmentB}`).getByRole('button', { name: 'Unset favorite for this output' })).toHaveAttribute('aria-pressed', 'true')
    await expect(menu.locator('button[aria-pressed="true"]')).toHaveCount(1)
    expect(state.openBodies).toEqual([])
  })
  const next = page.getByTestId('open-napari-43-mask')
  await test.step('Reload and launch row 43 using the retained favorite', async () => {
    await page.reload()
    await openNodeData(page, state.workflowName)
    await expect(next).toHaveAttribute('aria-label', 'Open in Tracking')
    await next.click()
    await expect.poll(() => state.openBodies.length).toBe(1)
    expect(state.openBodies[0]).toEqual(expectedOpen(state.workflowName, environmentB, 43))
  })
  await test.step('Wait for the picker to load and unset the favorite', async () => {
    await page.getByTestId('choose-napari-43-mask').click()
    await expect(picker(page)).toBeVisible()
    await expect(picker(page)).not.toContainText('Checking environments')
    await picker(page).getByRole('button', { name: 'Unset favorite for this output' }).click()
    await expect(picker(page).locator('button[aria-pressed="true"]')).toHaveCount(0)
    await expect(next).toHaveAttribute('aria-label', 'Open in Microscopy')
    expect(state.openBodies).toHaveLength(1)
    expect(state.favoriteBodies.map(body => [body.environment_id, body.expected_revision])).toEqual([
      [environmentA, 0], [environmentB, 1], [environmentB, 2],
    ])
    for (const body of state.favoriteBodies) {
      expect(body.key).toEqual({ kind: 'persistent', workspace_id: '300e69e0-ef55-4d22-928c-38bf9bf30aae',
        workflow_id: state.workflowName, identity_generation: expect.any(Number), node_path: ['seed'], output_key: 'mask' })
      expect(body).not.toHaveProperty('row')
      expect(body).not.toHaveProperty('result_identity')
    }
  })
})

test('napari inactive visible dock keeps scroll gestures and refreshes only on reveal', async ({ page }) => {
  const state = await fixture(page)
  await page.setViewportSize({ width: 1280, height: 960 })
  await openNodeData(page, state.workflowName)
  await expect(page.locator('.p-datatable-mask')).toBeHidden()
  await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
  const beforePrimary = state.controls.projectionQueryCount
  await page.getByTestId('open-napari-43-mask').click()
  expect(state.controls.projectionQueryCount, 'cell focus must not replace the visible projection').toBe(beforePrimary)
  await expect.poll(() => state.openBodies.length).toBe(1)
  expect(state.openBodies[0]).toEqual(expectedOpen(state.workflowName, environmentA, 43))
  await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
  const beforeArrow = state.controls.projectionQueryCount
  const arrow = page.getByTestId('choose-napari-60-mask')
  await arrow.scrollIntoViewIfNeeded()
  await expect(arrow).toBeInViewport()
  const scroll = await arrow.evaluate(button => {
    const viewport = button.closest('.p-datatable-table-container')!
    const header = viewport.querySelector('.p-datatable-thead')!
    const b = button.getBoundingClientRect(), v = viewport.getBoundingClientRect(), h = header.getBoundingClientRect()
    return { x: v.x + v.width / 2, y: (h.bottom + v.bottom) / 2,
      delta: b.y + b.height / 2 - (h.bottom + v.bottom) / 2 }
  })
  await page.mouse.move(scroll.x, scroll.y)
  await page.mouse.wheel(0, scroll.delta)
  await expect.poll(async () => arrow.evaluate(button => {
    const viewport = button.closest('.p-datatable-table-container')!
    const header = viewport.querySelector('.p-datatable-thead')!
    const b = button.getBoundingClientRect(), v = viewport.getBoundingClientRect(), h = header.getBoundingClientRect()
    return b.top >= Math.max(v.top, h.bottom) && b.bottom <= v.bottom
  })).toBe(true)
  const geometry = await arrow.evaluate(button => {
    const viewport = button.closest('.p-datatable-table-container')!
    const header = viewport.querySelector('.p-datatable-thead')!
    const b = button.getBoundingClientRect(), v = viewport.getBoundingClientRect(), h = header.getBoundingClientRect()
    const center = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2)
    return { unobscured: b.top >= Math.max(v.top, h.bottom) && b.bottom <= v.bottom
      && center !== null && button.contains(center), scrollTop: viewport.scrollTop }
  })
  expect(geometry.unobscured, JSON.stringify(geometry)).toBe(true)
  expect(geometry.scrollTop).toBeGreaterThan(0)
  await arrow.click()
  await expect(picker(page)).toContainText('Will open in Microscopy')
  expect(state.controls.projectionQueryCount).toBe(beforeArrow)
  expect(state.openBodies).toHaveLength(1)
  expect(state.favoriteBodies).toEqual([])
  await page.keyboard.press('Escape')
  await page.locator('.dv-tab').filter({ hasText: /^Execution$/ }).click()
  const beforeReveal = state.controls.projectionQueryCount
  await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
  await expect.poll(() => state.controls.projectionQueryCount).toBeGreaterThan(beforeReveal)
})

test('napari refuses unavailable choices without launch or favorite writes', async ({ page }) => {
  const state = await fixture(page)
  state.controls.environmentAStatus = 'incompatible'
  state.controls.environmentBStatus = 'unavailable'
  await openNodeData(page, state.workflowName)
  const primary = page.getByTestId('open-napari-42-mask')
  await expect(primary).toHaveAttribute('aria-label', 'Choose a napari environment')
  await primary.click()
  await expect(picker(page)).toContainText('No registered environment has verified required packages')
  await expect(picker(page).getByRole('button', { name: 'Try opening anyway in Tracking' })).toBeDisabled()
  await expect(picker(page).getByRole('button', { name: 'Set Tracking as favorite for this output' })).toBeDisabled()
  await expect(picker(page).getByRole('button', { name: 'Set Microscopy as favorite for this output' })).toBeDisabled()
  expect(state.openBodies).toEqual([])
  expect(state.favoriteBodies).toEqual([])
})

test('napari unknown open outcome waits for an explicit same-artifact retry', async ({ page }) => {
  const state = await fixture(page)
  state.controls.openFailure = true
  await openNodeData(page, state.workflowName)
  await page.getByTestId('open-napari-42-mask').click()
  await expect(page.getByText('Open outcome unknown; inspect the viewer before retrying')).toBeVisible()
  expect(state.openBodies).toHaveLength(1)
  expect(state.openBodies[0]).toEqual(expectedOpen(state.workflowName, environmentA))
  state.controls.openFailure = false
  await page.getByTestId('open-napari-42-mask').click()
  await expect.poll(() => state.openBodies.length).toBe(2)
  expect(state.openBodies[1]).toEqual(state.openBodies[0])
  expect(state.favoriteBodies).toEqual([])
})

test('napari stale captured result refusal never opens or saves a favorite', async ({ page }) => {
  const state = await fixture(page)
  state.controls.projectedIdentity = { ...resultIdentity, result_key: 'result-replaced' }
  state.controls.resolveFailure = true
  await openNodeData(page, state.workflowName)
  await expect(page.getByText('Captured result no longer exists').first()).toBeVisible()
  await page.getByTestId('open-napari-42-mask').click()
  await expect.poll(() => state.resolveBodies.filter(body => body.row === 42).length).toBeGreaterThan(1)
  expect(state.resolveBodies).toContainEqual(expect.objectContaining({ row: 42, result_identity: state.controls.projectedIdentity }))
  expect(state.openBodies).toEqual([])
  expect(state.favoriteBodies).toEqual([])
})

test('napari replaces captured artifact without stale clear or favorite dispatch', async ({ page }) => {
  const state = await fixture(page)
  await openNodeData(page, state.workflowName)
  await expect(page.getByTestId('open-napari-42-mask')).toHaveAttribute('aria-label', 'Open in Microscopy')
  const originalChooser = await page.getByTestId('choose-napari-42-mask').elementHandle()
  await page.getByTestId('choose-napari-42-mask').click()
  await expect(picker(page)).toContainText('Will open in Microscopy')
  let release!: () => void
  state.controls.resolveGate = new Promise<void>(resolve => { release = resolve })
  const nextIdentity = { ...resultIdentity, result_key: 'result-replaced' }
  state.controls.projectedIdentity = nextIdentity
  state.controls.effectiveDefault = environmentB
  state.controls.readerId = 'replacement.reader'
  await page.keyboard.press('Escape')
  await page.locator('.dv-tab').filter({ hasText: /^Execution$/ }).click()
  await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
  await expect.poll(() => state.controls.pendingResolveCount).toBeGreaterThan(0)
  const ownerPath = test.info().outputPath('replacement-owner.json')
  await writeFile(ownerPath, JSON.stringify({
    originalChooserConnected: await originalChooser!.evaluate(button => button.isConnected),
    projectionQueryCount: state.controls.projectionQueryCount,
    replacementIdentity: nextIdentity,
  }))
  await test.info().attach('replacement-owner', { contentType: 'application/json', path: ownerPath })
  await page.getByTestId('choose-napari-42-mask').click()
  const menu = picker(page)
  await expect(menu).toContainText('Checking environments')
  await expect(menu).not.toContainText('Will open in Microscopy')
  await expect(menu.getByRole('button', { name: 'Clear layers, then open' })).toHaveCount(0)
  await expect(menu.locator('button[aria-pressed]')).toHaveCount(0)
  await expect(menu.getByRole('button', { name: /^Open once in/ })).toHaveCount(0)
  expect(state.openBodies).toEqual([])
  expect(state.favoriteBodies).toEqual([])
  state.controls.resolveGate = null
  release()
  await expect.poll(() => state.controls.pendingResolveCount).toBe(0)
  await expect(page.getByTestId('open-napari-42-mask')).toHaveAttribute('aria-label', 'Open in Tracking')
  await page.keyboard.press('Escape')
  await expect(menu).toBeHidden()
  await page.getByTestId('choose-napari-42-mask').click()
  await expect(menu).toContainText('Will open in Tracking')
  await menu.getByRole('button', { name: 'Clear layers, then open' }).click()
  await expect.poll(() => state.openBodies.length).toBe(1)
  expect(state.openBodies[0]).toEqual({ ...expectedOpen(state.workflowName, environmentB, 42, true),
    reader_id: 'replacement.reader', result_identity: nextIdentity })
  expect(state.favoriteBodies).toEqual([])
})
