import { expect, test, type Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'
import type { NapariViewingReadinessResponse, WorkflowImportResponse } from '../../src/api/types'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`
const ownedWorkflows: string[] = []
const heldReleases: (() => void)[] = []

test.afterEach(async ({ page }) => {
  for (const release of heldReleases.splice(0)) release()
  await page.unrouteAll({ behavior: 'wait' })
  await page.goto('about:blank')
  for (const name of ownedWorkflows.splice(0)) {
    const response = await page.request.delete(`${API}/workflows/${name}`)
    expect([200, 204, 404]).toContain(response.status())
  }
})

async function archiveFixture(page: Page, reader = 'unavailable-reader') {
  const name = `viewing_import_${test.info().project.name}_${Date.now()}`
  expect((await page.request.post(`${API}/dev/seed`)).ok()).toBeTruthy()
  expect((await page.request.post(`${API}/workflows`, { data: { name } })).ok()).toBeTruthy()
  ownedWorkflows.push(name)
  const requirement = { napari: { required_packages: [{ distribution: reader, normalized_name: reader, version: '>=2,<3' }] } }
  const graph = {
    schema_version: 2, name, display_name: name,
    nodes: ['first', 'second'].map((id, index) => ({
      type: 'tool', id, name: id, tool_name: 'SeedNumbers', position: [100 + index * 240, 120],
      parameters: {}, viewer_additions: { number: requirement },
    })),
    edges: [], interface: { inputs: [], outputs: [] }, config: { engine: 'direct', execution: 'sequential' },
  }
  expect((await page.request.put(`${API}/workflows/${name}`, { data: { graph } })).ok()).toBeTruthy()
  const exported = await page.request.post(`${API}/workflows/${name}/export`)
  expect(exported.ok(), await exported.text()).toBeTruthy()
  // Retain an honest incomplete snapshot from an external exporter while
  // addressing the normal installed declaration rather than an owned clone.
  const buffer = execFileSync(resolve('../backend/.venv/bin/python'), ['-c', `
import io, json, sys, zipfile
with zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read())) as archive:
    files = {name: archive.read(name) for name in archive.namelist()}
document = json.loads(files['workflow.json'])
document['custom_sources'] = []
for node in document['workflow']['nodes']:
    node.pop('source_module', None)
    node['tool_module'] = 'bioimageflow_dev_tools.tools'
    node['tool_class'] = 'SeedNumbers'
manifest = document['viewing_requirements']
identity = next(identity for identity in manifest['outputs'] if identity.endswith('/label'))
manifest['complete'] = False
manifest['outputs'][identity] = {'status': 'unknown', 'viewer': None, 'reason': 'Exporter could not resolve viewer metadata for this output.'}
files['workflow.json'] = json.dumps(document).encode()
result = io.BytesIO()
with zipfile.ZipFile(result, 'w') as archive:
    for name, content in files.items(): archive.writestr(name, content)
sys.stdout.buffer.write(result.getvalue())
`], { input: await exported.body() })
  expect((await page.request.delete(`${API}/workflows/${name}`)).ok()).toBeTruthy()
  return { name, buffer, reader }
}

async function importInGui(page: Page, archive: Awaited<ReturnType<typeof archiveFixture>>) {
  const upload = page.waitForResponse(response => response.url().endsWith('/workflows/import') && response.request().method() === 'POST')
  const chooser = page.waitForEvent('filechooser')
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Import', exact: true }).click()
  await (await chooser).setFiles({ name: `${archive.name}.bioimageflow.zip`, mimeType: 'application/zip', buffer: archive.buffer })
  const response = await upload
  expect(response.status(), await response.text()).toBe(201)
  const imported = await response.json() as WorkflowImportResponse
  expect(imported.info.id ?? imported.info.name).toBe(archive.name)
  expect(imported.missing_packages).toEqual([])
  expect(imported.missing_tools).toEqual([])
  await expect(page.getByTestId('workflow-title')).toHaveText(archive.name)
  await expect(page.locator('.vue-flow__node[data-id="first"]')).toBeVisible()
  return imported
}

async function runImported(page: Page, name: string, imported: WorkflowImportResponse) {
  const running = page.waitForResponse(response => response.url().endsWith('/execution/run') && response.request().method() === 'POST')
  await expect(page.getByTestId('run-workflow-button')).toBeEnabled()
  await page.getByTestId('run-workflow-button').click()
  const response = await running
  expect(response.status(), await response.text()).toBe(202)
  const execution = await response.json()
  expect(execution).toMatchObject({ status: 'started', workflow_id: name })
  expect(execution.execution_id).toEqual(expect.any(String))
  expect(response.request().postDataJSON()).toMatchObject({ workflow_id: name, draft_revision: execution.draft_revision })
  await expect(page.getByTestId('execution-banner-headline')).toContainText('Execution complete', { timeout: 15_000 })
  const identities: string[] = []
  for (const node of ['first', 'second']) {
    const data = await page.request.post(`${API}/nodes/${node}/data/query`, { data: { workflow_name: name } })
    expect(data.ok(), await data.text()).toBeTruthy()
    const result = await data.json()
    expect(result.rows).toEqual([{ number: 1, label: 'one' }, { number: 2, label: 'two' }, { number: 3, label: 'three' }])
    expect(result.identity_status).toBe('captured')
    expect(result.source_identity).toMatchObject({ node_key: node, run_id: expect.any(String), result_key: expect.any(String), record_id: expect.any(String) })
    identities.push(result.source_identity.run_id)
    const pinned = await page.request.post(`${API}/nodes/${node}/data/query`, {
      data: { workflow_name: name, result_identity: result.source_identity },
    })
    expect(pinned.ok(), await pinned.text()).toBeTruthy()
    expect((await pinned.json()).source_identity).toEqual(result.source_identity)
  }
  expect(identities[0]).toBe(identities[1])
  const status = await (await page.request.get(`${API}/execution/status`)).json()
  expect(status).toMatchObject({ workflow_id: name, execution_id: execution.execution_id, draft_revision: execution.draft_revision, state: 'idle', last_result: { success: true } })
  const accepted = await (await page.request.get(`${API}/workflows/${name}`)).json()
  expect(accepted.info.identity_generation).toBe(imported.info.identity_generation)
  expect(accepted.graph.config).toMatchObject({ engine: 'direct', execution: 'sequential' })
}

function observeViewerMutations(page: Page) {
  const requests: string[] = []
  page.on('request', request => {
    if (request.method() !== 'GET' && /\/napari\/(?:environments|launch|open|viewer-preferences)/.test(request.url())) requests.push(`${request.method()} ${request.url()}`)
  })
  return requests
}

async function reopenInGui(page: Page, name: string) {
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Open', exact: true }).click()
  await page.getByTestId('workflow-open-search').fill(name)
  await page.getByTestId(`workflow-open-option-${name}`).click()
  await page.getByTestId('workflow-open-submit').click()
  await expect(page.getByTestId('workflow-title')).toHaveText(name)
}

test('import viewing guidance groups actual missing and unknown requirements while the imported workflow runs', async ({ page }) => {
  const archive = await archiveFixture(page)
  const mutations = observeViewerMutations(page)
  const readiness = page.waitForResponse(response => response.url().endsWith('/napari/viewing-readiness'))
  await page.goto('/')
  const imported = await importInGui(page, archive)
  const response = await readiness
  expect(response.ok(), await response.text()).toBeTruthy()
  const report = await response.json() as NapariViewingReadinessResponse
  expect(report.summary).toMatchObject({ not_covered_outputs: 2, unknown_outputs: 1, covered_outputs: 1, outputs_needing_setup: 3 })
  expect(report.groups).toHaveLength(1)
  expect(report.groups[0]!.members).toEqual(['first::tool-output/number', 'second::tool-output/number'])
  expect(imported.viewing_requirements?.complete).toBe(false)
  const guidance = page.getByTestId('viewing-guidance')
  await expect(guidance).toContainText(archive.name)
  await expect(guidance).toContainText('3 outputs need viewer setup')
  await expect(guidance).toContainText('Workflow execution is unaffected.')
  await guidance.getByText('Viewer setup details', { exact: true }).click()
  await expect(guidance).toContainText('first::tool-output/number, second::tool-output/number')
  await expect(guidance).toContainText('unavailable-reader<3,>=2')
  await expect(guidance).toContainText('first::tool-output/label — Unknown viewing requirements')
  await expect(guidance).toContainText('Exporter could not resolve viewer metadata for this output.')
  await guidance.getByRole('button', { name: 'Create environment for this set', exact: true }).click()
  await expect(page.getByTestId('image-viewers-section')).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Required Python distributions' })).toHaveValue('unavailable-reader<3,>=2')
  await expect(page.getByText('Unknown or private packages must be installed manually in an external environment.', { exact: false })).toBeVisible()
  await page.getByTestId('settings-close').click()
  await guidance.getByRole('button', { name: 'Dismiss viewing guidance', exact: true }).click()
  await expect(guidance).toHaveCount(0)
  await runImported(page, archive.name, imported)
  expect(mutations).toEqual([])
})

test('import viewing check failure preserves execution and explicit saved Open refreshes guidance', async ({ page }) => {
  const archive = await archiveFixture(page)
  const mutations = observeViewerMutations(page)
  let imports = 0
  const checks: unknown[] = []
  page.on('request', request => { if (request.url().endsWith('/workflows/import')) imports += 1 })
  await page.route('**/api/v1/napari/viewing-readiness', async route => {
    checks.push(route.request().postDataJSON())
    if (checks.length === 1) await route.fulfill({ status: 503, json: { detail: 'Passive viewing check temporarily unavailable' } })
    else await route.continue()
  })
  await page.goto('/')
  const imported = await importInGui(page, archive)
  const guidance = page.getByTestId('viewing-guidance')
  await expect(guidance).toContainText('Viewing requirements not checked')
  await expect(guidance).toContainText('Workflow execution is unaffected.')
  expect(checks).toEqual([imported.viewing_requirements])
  await runImported(page, archive.name, imported)
  const saved = page.waitForResponse(response => response.url().endsWith(`/workflows/${archive.name}/viewing-readiness`))
  const refreshed = page.waitForResponse(response => response.url().endsWith('/napari/viewing-readiness') && response.ok())
  await reopenInGui(page, archive.name)
  const manifest = await (await saved).json()
  const report = await (await refreshed).json() as NapariViewingReadinessResponse
  expect(manifest.complete).toBe(true)
  expect(report.summary).toMatchObject({ not_covered_outputs: 2, unknown_outputs: 0, covered_outputs: 2, outputs_needing_setup: 2 })
  await expect(guidance).toContainText(report.summary.message)
  await expect(guidance).not.toContainText('Viewing requirements not checked')
  expect(checks).toEqual([imported.viewing_requirements, manifest])
  expect(imports).toBe(1)
  expect(mutations).toEqual([])
})

test('delayed sibling import viewing result cannot replace the accepted workflow guidance or form', async ({ page }) => {
  const first = await archiveFixture(page, 'first-reader')
  const second = await archiveFixture(page, 'second-reader')
  const mutations = observeViewerMutations(page)
  let release!: () => void
  const released = new Promise<void>(resolve => { release = resolve })
  heldReleases.push(release)
  let captured!: () => void
  const held = new Promise<void>(resolve => { captured = resolve })
  let firstReport: NapariViewingReadinessResponse | undefined
  await page.route('**/api/v1/napari/viewing-readiness', async route => {
    if (JSON.stringify(route.request().postDataJSON()).includes('first-reader')) {
      const response = await route.fetch()
      firstReport = await response.json() as NapariViewingReadinessResponse
      captured()
      await released
      await route.fulfill({ response })
    } else await route.continue()
  })
  await page.goto('/')
  await importInGui(page, first)
  await held
  await expect(page.getByTestId('viewing-guidance')).toContainText(first.name)
  const secondResponse = page.waitForResponse(response => response.url().endsWith('/napari/viewing-readiness') && JSON.stringify(response.request().postDataJSON()).includes('second-reader'))
  const imported = await importInGui(page, second)
  const report = await (await secondResponse).json() as NapariViewingReadinessResponse
  expect(report.groups?.[0]?.managed_create_prefill.requested_packages).toEqual(['second-reader<3,>=2'])
  const guidance = page.getByTestId('viewing-guidance')
  await expect(guidance).toContainText(second.name)
  await guidance.getByText('Viewer setup details', { exact: true }).click()
  await expect(guidance).toContainText('second-reader<3,>=2')
  const stale = page.waitForResponse(response => response.url().endsWith('/napari/viewing-readiness') && JSON.stringify(response.request().postDataJSON()).includes('first-reader'))
  release()
  await stale
  expect(firstReport?.groups?.[0]?.managed_create_prefill.requested_packages).toEqual(['first-reader<3,>=2'])
  await expect(guidance).toContainText(second.name)
  await expect(guidance).not.toContainText(first.name)
  await expect(guidance).not.toContainText('first-reader')
  await guidance.getByRole('button', { name: 'Create environment for this set', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Required Python distributions' })).toHaveValue('second-reader<3,>=2')
  await page.getByTestId('settings-close').click()
  await expect(page.getByTestId('workflow-title')).toHaveText(second.name)
  await expect(page.getByTestId('run-workflow-button')).toBeEnabled()
  const accepted = await (await page.request.get(`${API}/workflows/${second.name}`)).json()
  expect(accepted.info.identity_generation).toBe(imported.info.identity_generation)
  expect(mutations).toEqual([])
})
