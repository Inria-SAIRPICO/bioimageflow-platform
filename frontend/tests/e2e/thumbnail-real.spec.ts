import { expect, test, type Page, type Response } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { mkdtempSync, readFileSync, realpathSync } from 'node:fs'
import { isAbsolute, relative, resolve, sep } from 'node:path'
import type { GraphState, NodeDataResponse, PackageInfo, ResultArtifactIdentity, ToolMetadata, WorkflowFile } from '../../src/api/types'
import type { WorkflowDraftResponse } from '../../src/api/workflowDrafts'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`
const NODE = 'files'
const PACKAGE = 'bioimageflow_common_tools'

function commonToolsVersion(): string {
  const versions = readFileSync(resolve('../scripts/ci/test_versions.env'), 'utf8')
  const version = /^BIOIMAGEFLOW_COMMON_TOOLS_VERSION=([^\s#]+)$/m.exec(versions)?.[1]
  if (!version) throw new Error('The published common-tools certification version is missing')
  return version
}

async function catalogFiles(page: Page): Promise<ToolMetadata> {
  const response = await page.request.get(`${API}/tools`)
  expect(response.ok(), await response.text()).toBeTruthy()
  const tools = await response.json() as ToolMetadata[]
  const files = tools.find(tool => tool.name === 'Files')
  if (!files) throw new Error('The isolated E2E Files catalog fixture is missing')
  return files
}

async function query(page: Page, name: string, identity?: ResultArtifactIdentity): Promise<NodeDataResponse> {
  const response = await page.request.post(`${API}/nodes/${NODE}/data/query`, {
    data: { workflow_name: name, tool_name: 'Files', ...(identity ? { result_identity: identity } : {}) },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  return await response.json() as NodeDataResponse
}

async function openData(page: Page, name: string, label: string): Promise<void> {
  await page.goto('/')
  await expect(page.locator('#bioimageflow-app')).toBeVisible()
  await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
  await page.getByTestId('workflow-search').fill(name)
  // A startup read can already be in flight. Bind acceptance to the GET
  // dispatched after this explicit Open, rather than an older same-URL reply.
  const openedRequest = page.waitForRequest(request => request.method() === 'GET'
    && new URL(request.url()).pathname === `/api/v1/workflow-drafts/${name}`)
  const [opened] = await Promise.all([
    page.waitForResponse(async response => response.request() === await openedRequest),
    page.getByTestId(`workflow-row-${name}`).dblclick(),
  ])
  expect(opened.ok(), await opened.text()).toBeTruthy()
  const accepted = await opened.json() as WorkflowDraftResponse
  expect(accepted.graph.display_name).toBe(label)
  expect(accepted.graph.nodes).toEqual(expect.arrayContaining([expect.objectContaining({ id: NODE })]))
  await expect(page.getByTestId('workflow-title')).toHaveText(label)
  await page.locator(`.vue-flow__node[data-id="${NODE}"]`).click()
  await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
}

test('renders a real TIFF thumbnail through the managed reader and preserves its captured result after reload', async ({ page }, testInfo) => {
  // Noncritical milestone acceptance: a genuinely cold reader environment may
  // provision here. Product thumbnail retry delays remain unchanged.
  test.setTimeout(660_000)
  const root = realpathSync(process.env.BIOIMAGEFLOW_E2E_ROOT ?? '')
  const version = commonToolsVersion()
  const originalFiles = await catalogFiles(page)
  // Refuse an unsupported starting catalog before installation or mutation.
  expect(originalFiles).toMatchObject({
    package: 'e2e_hot_reload_tools', package_version: '1.0.0',
    tool_type: 'DataFrameTool', outputs: { path: { type: 'str' } },
  })
  const packagesResponse = await page.request.get(`${API}/tools/packages`)
  expect(packagesResponse.ok(), await packagesResponse.text()).toBeTruthy()
  const packages = await packagesResponse.json() as PackageInfo[]
  expect(packages.find(pkg => pkg.name === originalFiles.package)?.installed_versions).toContain(originalFiles.package_version)
  const configuredTiff = process.env.BIOIMAGEFLOW_THUMBNAIL_TIFF
  const source = configuredTiff ? realpathSync(configuredTiff)
    : resolve(mkdtempSync(resolve(root, 'thumbnail-input-')), 'ramp.tif')
  const withinRoot = relative(root, source)
  expect(isAbsolute(source)).toBe(true)
  expect(withinRoot).not.toBe('..')
  expect(withinRoot.startsWith(`..${sep}`)).toBe(false)
  expect(isAbsolute(withinRoot)).toBe(false)
  expect(source).toMatch(/\.tiff?$/i)
  execFileSync(resolve('../backend/.venv/bin/python'), ['-c', `
import sys
from pathlib import Path
import numpy as np
import tifffile
expected = np.arange(64, dtype=np.uint16).reshape(8, 8)
if sys.argv[2] == "create":
    assert not Path(sys.argv[1]).exists()
    tifffile.imwrite(sys.argv[1], expected, metadata={"axes": "YX"})
image = tifffile.imread(sys.argv[1])
np.testing.assert_array_equal(image, expected)
assert image.dtype == expected.dtype
`, source, configuredTiff ? 'existing' : 'create'], { encoding: 'utf8', timeout: 30_000 })
  const sourceBytes = readFileSync(source)
  const sourceHash = createHash('sha256').update(sourceBytes).digest('hex')
  const name = `real_thumbnail_${testInfo.project.name}_${Date.now()}`
  const label = `Real TIFF ${name}`
  const graph: GraphState = {
    schema_version: 2, name, display_name: label,
    nodes: [{
      type: 'tool', id: NODE, name: 'Published Files', tool_name: 'Files',
      tool_module: 'bioimageflow_common_tools.files', tool_class: 'Files',
      tool_package: PACKAGE, tool_package_version: version,
      position: [220, 160], parameters: { files: [source] }, enabled: true, collapsed: false,
    }],
    edges: [],
    interface: { inputs: [], outputs: [] },
    config: { engine: 'direct', execution: 'sequential' },
  }
  const thumbnailPath = `/api/v1/nodes/${NODE}/thumbnail`
  const observed: Response[] = []
  let runCount = 0
  const observe = (response: Response) => {
    const url = new URL(response.url())
    if (url.pathname === thumbnailPath && url.searchParams.get('workflow_name') === name) observed.push(response)
    if (url.pathname === '/api/v1/execution/run' && response.request().method() === 'POST') runCount += 1
  }
  page.on('response', observe)
  let primaryOccurred = false
  let cleanupFailed = false
  let cleanupFailure: unknown
  let created = false
  let catalogMayHaveChanged = false
  const firstRequestAt = Date.now()
  const restoreCatalog = async () => {
    const restored = await page.request.post(`${API}/tools/packages/${originalFiles.package}/use`, {
      data: { version: originalFiles.package_version },
    })
    expect(restored.ok(), await restored.text()).toBeTruthy()
    expect(await catalogFiles(page)).toEqual(originalFiles)
    catalogMayHaveChanged = false
  }
  try {
    catalogMayHaveChanged = true
    // Use the same no-dependencies public installation boundary as published
    // compatibility acceptance, scoped to this Playwright runtime's tool store.
    execFileSync(resolve('../backend/.venv/bin/python'), ['-c', `
import os
import signal
import subprocess
import sys
installer = '''
from pathlib import Path
import sys
from bioimageflow.tool_loader import ensure_installed
ensure_installed("bioimageflow_common_tools", sys.argv[2], "bioimageflow-common-tools",
                 Path(sys.argv[1]), install_dependencies=False)
'''
child = subprocess.Popen([sys.executable, "-c", installer, *sys.argv[1:]], start_new_session=True)
try:
    code = child.wait(timeout=180)
finally:
    # This process group contains only this installer and its pip descendants.
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    child.wait()
if code:
    raise subprocess.CalledProcessError(code, child.args)
`, resolve(root, 'tool_packages'), version], { encoding: 'utf8', timeout: 200_000 })
    // The already-installed target is admitted without another download. The
    // public operation synchronously indexes it and settles pending reloads.
    const installation = await page.request.post(`${API}/tools/packages/${PACKAGE}/install`, {
      data: { version },
    })
    expect(installation.ok(), await installation.text()).toBeTruthy()
    await restoreCatalog()
    const creation = await page.request.post(`${API}/workflows`, { data: { name, display_name: label } })
    expect(creation.status(), await creation.text()).toBe(201)
    created = true
    const installed = await page.request.put(`${API}/workflows/${name}`, { data: { graph } })
    expect(installed.ok(), await installed.text()).toBeTruthy()
    const acceptedResponse = await page.request.get(`${API}/workflow-drafts/${name}`)
    expect(acceptedResponse.ok(), await acceptedResponse.text()).toBeTruthy()
    const accepted = await acceptedResponse.json() as WorkflowDraftResponse
    expect(accepted.validation).toMatchObject({ valid: true, errors: [] })
    expect(accepted.validation.node_tools?.[NODE]).toMatchObject({
      name: 'Files', package: PACKAGE, package_version: version, tool_type: 'DataFrameTool',
    })
    // Explicit carried identity avoids the unrelated same-name hot-reload fixture.
    await openData(page, name, label)
    const run = page.waitForResponse(response => response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/execution/run')
    await page.getByTestId('run-workflow-button').click()
    const started = await run
    expect(started.status(), await started.text()).toBe(202)
    const execution = await started.json() as { execution_id: string; workflow_id: string; draft_revision: number }
    expect(execution.workflow_id).toBe(name)
    expect(started.request().postDataJSON()).toMatchObject({ workflow_id: name, draft_revision: accepted.draft_revision })
    await expect.poll(async () => {
      const response = await page.request.get(`${API}/execution/status`)
      expect(response.ok(), await response.text()).toBeTruthy()
      const status = await response.json() as { execution_id: string; state: string; last_result?: { success: boolean } }
      return { id: status.execution_id, state: status.state, success: status.last_result?.success }
    }, { timeout: 30_000 }).toEqual({ id: execution.execution_id, state: 'idle', success: true })
    const captured = await query(page, name)
    expect(captured.identity_status).toBe('captured')
    expect(captured.source_identity).toMatchObject({ node_key: NODE, run_id: expect.any(String), record_id: expect.any(String), result_key: expect.any(String) })
    expect(captured.columns).toEqual(['path'])
    expect(captured.column_types).toEqual({ path: 'Path' })
    expect(await catalogFiles(page)).toEqual(originalFiles)
    expect(captured.rows).toEqual([{ path: source }])
    if (!captured.source_identity) throw new Error('Files did not publish a modern captured result')

    const table = page.getByTestId('merged-data-table')
    const thumbnail = table.getByTestId('image-thumbnail')
    await expect(table).toBeVisible()
    await thumbnail.scrollIntoViewIfNeeded()
    // Cold setup is owned by the service. The UI must finish automatically,
    // even when provisioning takes longer than the former 30-second budget.
    await expect(thumbnail).toHaveAttribute('src', /^blob:/, { timeout: 600_000 })
    expect(await thumbnail.getAttribute('aria-label')).not.toBe('thumbnail unavailable')
    const assertRendered = async () => {
      await expect(thumbnail).toHaveAttribute('src', /^blob:/, { timeout: 15_000 })
      const actual = await thumbnail.evaluate(async element => {
        const image = element as HTMLImageElement
        await image.decode()
        const canvas = document.createElement('canvas')
        canvas.width = image.naturalWidth
        canvas.height = image.naturalHeight
        const context = canvas.getContext('2d')!
        context.drawImage(image, 0, 0)
        return { complete: image.complete, width: image.naturalWidth, height: image.naturalHeight,
          rgba: Array.from(context.getImageData(0, 0, canvas.width, canvas.height).data) }
      })
      expect(actual).toMatchObject({ complete: true, width: 8, height: 8 })
      // The known row-major ramp must remain nonconstant and ordered after
      // display conversion. Do not prescribe the generator's stretch formula.
      const grayscale = Array.from({ length: 64 }, (_, index) => {
        const offset = index * 4
        expect(actual.rgba.slice(offset, offset + 4)).toEqual([
          actual.rgba[offset], actual.rgba[offset], actual.rgba[offset], 255,
        ])
        return actual.rgba[offset]!
      })
      expect(grayscale[0]).toBe(0)
      expect(grayscale[63]).toBe(255)
      for (let index = 1; index < grayscale.length; index += 1) {
        expect(grayscale[index]).toBeGreaterThan(grayscale[index - 1]!)
      }
      await expect(table.getByTestId('path-display')).toHaveAttribute('title', source)
      return actual
    }
    const firstImage = await assertRendered()
    const rawImage = await page.request.get(`${API}/nodes/${NODE}/image`, { params: { workflow_name: name, col: 'path', row: 0 } })
    expect(rawImage.ok(), await rawImage.text()).toBeTruthy()
    expect(await rawImage.body()).toEqual(sourceBytes)
    const savedResponse = await page.request.get(`${API}/workflows/${name}`)
    expect(savedResponse.ok(), await savedResponse.text()).toBeTruthy()
    const saved = await savedResponse.json() as WorkflowFile
    await openData(page, name, label)
    expect(await assertRendered()).toEqual(firstImage)
    expect(await query(page, name)).toEqual(captured)
    expect(await query(page, name, captured.source_identity)).toEqual(captured)
    expect(await catalogFiles(page)).toEqual(originalFiles)
    expect(await (await page.request.get(`${API}/workflows/${name}`)).json()).toEqual(saved)
    expect(createHash('sha256').update(readFileSync(source)).digest('hex')).toBe(sourceHash)
    expect(runCount).toBe(1)
    const headers = await Promise.all(observed.map(async response => {
      const url = new URL(response.url())
      expect(url.searchParams.get('row')).toBe('0')
      expect(url.searchParams.get('col')).toBe('path')
      expect(url.searchParams.get('size')).toBe('256')
      const fields = await response.allHeaders()
      expect(response.status()).toBe(200)
      expect(['pending', 'ready']).toContain(fields['x-thumbnail-status'])
      if (fields['x-thumbnail-status'] === 'pending') expect(fields['cache-control']).toBe('no-store')
      return { url: response.url(), status: fields['x-thumbnail-status'], cache_control: fields['cache-control'],
        timing: response.request().timing() }
    }))
    expect(headers.some(response => response.status === 'ready')).toBe(true)
    await testInfo.attach('real-thumbnail-observation', { contentType: 'application/json', body: Buffer.from(JSON.stringify({
      source, source_sha256: sourceHash, result_identity: captured.source_identity, execution_id: execution.execution_id,
      package_version: version, contradictory_catalog: originalFiles,
      case_started_at: firstRequestAt, responses: headers,
    }, null, 2)) })
  } catch (error) {
    primaryOccurred = true
    throw error
  } finally {
    page.off('response', observe)
    const cleanupErrors: unknown[] = []
    const cleanupActions = [
      async () => { await page.goto('about:blank') },
      async () => {
        if (!created) return
        const removed = await page.request.delete(`${API}/workflows/${name}`)
        expect([200, 204, 404], await removed.text()).toContain(removed.status())
      },
      async () => { if (catalogMayHaveChanged) await restoreCatalog() },
    ]
    for (const cleanup of cleanupActions) {
      try {
        await cleanup()
      } catch (error) {
        cleanupErrors.push(error)
      }
    }
    if (cleanupErrors.length) {
      cleanupFailed = true
      if (primaryOccurred) console.error('Thumbnail workflow cleanup failed while preserving the primary:', cleanupErrors)
      else cleanupFailure = cleanupErrors[0]
      try {
        await testInfo.attach('thumbnail-workflow-cleanup-failure', {
          contentType: 'application/json',
          body: Buffer.from(JSON.stringify({ workflow: name, primary_failure_preserved: primaryOccurred,
            errors: cleanupErrors.map(error => error instanceof Error
              ? { message: error.message, stack: error.stack } : String(error)) }, null, 2)),
        })
      } catch (attachmentError) {
        console.error('Could not attach the secondary thumbnail cleanup failure:', attachmentError)
      }
    }
    // Exact owned input, tool store, thumbnail pool and environment retirement
    // remain with the runtime owner after the backend has physically stopped.
  }
  if (cleanupFailed) throw cleanupFailure
})
