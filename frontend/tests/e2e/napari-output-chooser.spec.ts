import { expect, test, type Page } from '@playwright/test'

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
  await page.getByRole('button', { name: 'Open workflow', exact: true }).click()
  await expect(page.getByTestId('workflow-title')).toContainText(workflowName)
  const seed = page.locator('.vue-flow__node[data-id="seed"]')
  await expect(seed).toBeVisible()
  await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
  await seed.click()
  await expect(page.getByTestId('open-napari-42-mask')).toBeVisible({ timeout: 15000 })
}

test('napari result action resolves the captured identity to the server-selected environment', async ({ page }) => {
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
    config: { engine: 'direct', execution: 'parallel' },
  } } })).ok()).toBeTruthy()

  const openBodies: Record<string, unknown>[] = []
  const resolveBodies: Record<string, unknown>[] = []
  let favorite: string | null = null
  let preferenceRevision = 0
  let identityGeneration = 0

  await page.route('**/api/v1/data-table/query', async route => {
    await route.fulfill({ json: {
      mode: 'merged',
      sources: [{
        node_id: 'seed', role: 'anchor', label: 'Seed', tool_name: 'SeedNumbers',
        columns: null, column_aliases: {}, result_identity: resultIdentity,
      }],
      columns: [{
        id: 's0:mask', label: 'mask', type: 'str', source_node_id: 'seed', source_column: 'mask',
        viewer: { napari: { required_packages: [], recommended_packages: [], napari_version: null, reader_id: 'retained.reader' } },
        viewer_status: 'captured',
      }],
      rows: [{ index: 'selected', values: { 's0:mask': '/captured/labels.custom' }, source_rows: { seed: 42 } }],
      total_rows: 1,
      unfiltered_total_rows: 1,
      page: 0,
      page_size: 250,
    } })
  })
  await page.route('**/api/v1/napari/environments', route => route.fulfill({ json: {
    revision: 3,
    environments: [
      { id: environmentA, registration_order: 0, name: 'Microscopy', ownership: 'external', kind: 'venv', root: '/a', interpreter: '/a/python', interpreter_identity: 'a', interpreter_fingerprint: 'a', launch: { strategy: 'interpreter', argv_prefix: ['/a/python'] }, inventory: { python_version: '3.12', napari_version: '0.9.1', distributions: [], fingerprint: 'a', probed_at: '2026-09-15T10:00:00Z' }, state: 'ready' },
      { id: environmentB, registration_order: 1, name: 'Tracking', ownership: 'external', kind: 'venv', root: '/b', interpreter: '/b/python', interpreter_identity: 'b', interpreter_fingerprint: 'b', launch: { strategy: 'interpreter', argv_prefix: ['/b/python'] }, state: 'ready' },
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
    identityGeneration = request.identity_generation
    const candidates = [
      { environment_id: environmentA, name: 'Microscopy', status: 'compatible', label: 'Required packages installed', reason: favorite === environmentA ? 'Selected favorite' : 'Selected by global default', preference: favorite === environmentA ? 'favorite' : 'global_default', issues: [], missing_recommended_packages: [], reader_id: 'retained.reader' },
      { environment_id: environmentB, name: 'Tracking', status: 'compatible', label: 'Required packages installed', reason: favorite === environmentB ? 'Selected favorite' : 'Compatible fallback', preference: favorite === environmentB ? 'favorite' : 'other', issues: [], missing_recommended_packages: [], reader_id: 'retained.reader' },
    ]
    await route.fulfill({ json: {
      artifact_identity: request.result_identity,
      preference_key: { kind: 'persistent', workspace_id: '300e69e0-ef55-4d22-928c-38bf9bf30aae', workflow_id: workflowName, identity_generation: request.identity_generation, node_path: ['seed'], output_key: 'mask' },
      workflow_id: workflowName,
      identity_generation: request.identity_generation,
      node_path: ['seed'], output_key: 'mask', filename: 'labels.ome.tif',
      candidates,
      effective_environment_id: favorite ?? environmentA,
      effective_reason: favorite ? 'Selected favorite' : 'Selected by global default',
    } })
  })
  await page.route('**/api/v1/napari/viewer-preferences/favorite/toggle', async route => {
    const request = route.request().postDataJSON()
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
    await route.fulfill({ json: { status: 'ok' } })
  })

  await openNodeData(page, workflowName)
  const primary = page.getByTestId('open-napari-42-mask')
  await expect(primary).toHaveAttribute('aria-label', 'Open in Microscopy')
  expect(resolveBodies.at(-1)).toMatchObject({
    workflow_id: workflowName,
    node_path: ['seed'], output_key: 'mask', row: 42,
    result_identity: resultIdentity,
  })
  expect(openBodies).toHaveLength(0)

  await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
  const chooser = page.getByTestId('choose-napari-42-mask')
  await expect(page.locator('.p-datatable-mask')).toBeHidden()
  await chooser.scrollIntoViewIfNeeded()
  await expect(chooser).toBeInViewport()
  await chooser.click()
  const picker = page.getByTestId('napari-environment-picker')
  await expect(picker).toContainText('Will open in Microscopy')
  await expect(picker).not.toContainText('Selected by global default')
  await expect(picker.getByRole('button', { name: 'Unset favorite', exact: true })).toHaveCount(0)
  const clearAndOpen = picker.getByRole('button', { name: 'Clear layers, then open' })
  await expect(clearAndOpen).toHaveAttribute('title', 'Clear all layers in Microscopy, then open mask')
  await clearAndOpen.click()
  expect(openBodies).toHaveLength(1)
  expect(openBodies[0]).toMatchObject({
    environment_id: environmentA,
    clear_layers: true,
    reader_id: 'retained.reader',
    result_identity: resultIdentity,
  })
})
