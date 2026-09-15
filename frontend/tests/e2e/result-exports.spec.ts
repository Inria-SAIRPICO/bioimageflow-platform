import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { inflateRawSync } from 'node:zlib'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

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

function zipEntries(archive: Buffer): Map<string, Buffer> {
  const endSignature = Buffer.from([0x50, 0x4b, 0x05, 0x06])
  const end = archive.lastIndexOf(endSignature)
  expect(end, 'ZIP end-of-central-directory record').toBeGreaterThanOrEqual(0)
  const count = archive.readUInt16LE(end + 10)
  let cursor = archive.readUInt32LE(end + 16)
  const entries = new Map<string, Buffer>()

  for (let index = 0; index < count; index += 1) {
    expect(archive.readUInt32LE(cursor), 'ZIP central-directory entry').toBe(0x02014b50)
    const method = archive.readUInt16LE(cursor + 10)
    const compressedSize = archive.readUInt32LE(cursor + 20)
    const size = archive.readUInt32LE(cursor + 24)
    const nameLength = archive.readUInt16LE(cursor + 28)
    const extraLength = archive.readUInt16LE(cursor + 30)
    const commentLength = archive.readUInt16LE(cursor + 32)
    const localOffset = archive.readUInt32LE(cursor + 42)
    const name = archive.subarray(cursor + 46, cursor + 46 + nameLength).toString('utf8')

    expect(archive.readUInt32LE(localOffset), `ZIP local entry for ${name}`).toBe(0x04034b50)
    const localNameLength = archive.readUInt16LE(localOffset + 26)
    const localExtraLength = archive.readUInt16LE(localOffset + 28)
    const dataOffset = localOffset + 30 + localNameLength + localExtraLength
    const compressed = archive.subarray(dataOffset, dataOffset + compressedSize)
    const value = method === 0 ? compressed : method === 8 ? inflateRawSync(compressed) : null
    expect(value, `supported ZIP compression method for ${name}`).not.toBeNull()
    expect(value!.length, `uncompressed size for ${name}`).toBe(size)
    entries.set(name, value!)
    cursor += 46 + nameLength + extraLength + commentLength
  }
  return entries
}

async function createWorkflow(page: Page, displayName: string): Promise<string> {
  const workflowName = deriveWorkflowId(displayName)
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: 'New', exact: true }).click()
  await page.getByTestId('workflow-display-name-input').fill(displayName)
  await page.getByTestId('workflow-dialog-submit').click()
  await expect(page.getByTestId('workflow-title')).toContainText(displayName)
  return workflowName
}

async function installExportGraph(page: Page, workflowName: string): Promise<void> {
  await page.goto('about:blank')
  const current = await page.request.get(`${API_BASE}/api/v1/workflows/${workflowName}`)
  expect(current.ok()).toBeTruthy()
  const document = await current.json()
  document.graph.nodes = [
    {
      type: 'tool',
      id: 'generate_result',
      name: 'Generated result',
      tool_name: 'Generate',
      position: [140, 160],
      parameters: { column_name: 'marker', values: [1] },
    },
    {
      type: 'tool',
      id: 'seed_result',
      name: 'Seed result',
      tool_name: 'SeedNumbers',
      position: [480, 160],
      parameters: {},
    },
  ]
  document.graph.edges = []
  const saved = await page.request.put(`${API_BASE}/api/v1/workflows/${workflowName}`, {
    data: { graph: document.graph },
  })
  expect(saved.ok(), await saved.text()).toBeTruthy()
  const draftResponse = await page.request.get(
    `${API_BASE}/api/v1/workflow-drafts/${workflowName}`,
  )
  expect(draftResponse.ok()).toBeTruthy()
  const draft = await draftResponse.json()
  const reset = await page.request.post(
    `${API_BASE}/api/v1/workflow-drafts/${workflowName}/reset-to-saved`,
    { data: { expected_revision: draft.draft_revision, updated_by: 'frontend' } },
  )
  expect(reset.ok(), await reset.text()).toBeTruthy()
  await page.goto('/')
  await expect(page.locator('.vue-flow__node')).toHaveCount(2)
}

async function runAndReadId(page: Page, action: () => Promise<void>): Promise<string> {
  const response = page.waitForResponse(candidate => (
    candidate.url().endsWith('/api/v1/execution/run')
    && candidate.request().method() === 'POST'
  ))
  await action()
  expect((await response).status()).toBe(202)
  await expect(page.getByTestId('execution-banner-headline')).toHaveText(
    'Execution complete',
    { timeout: 30_000 },
  )
  const statusResponse = await page.request.get(`${API_BASE}/api/v1/execution/status`)
  expect(statusResponse.ok()).toBeTruthy()
  const status = await statusResponse.json()
  expect(status).toMatchObject({
    state: 'idle',
    last_result: { success: true },
  })
  expect(status.execution_id).toMatch(/^run_/)
  return status.execution_id as string
}

async function openExportDialog(page: Page): Promise<void> {
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Export', exact: true }).click()
  await expect(page.getByTestId('workflow-export-dialog')).toBeVisible()
}

test.describe('result exports', () => {
  test('downloads exact mixed-latest and pinned-run bytes after two real GUI runs', async ({ page }) => {
    test.setTimeout(60_000)
    const displayName = `Result export ${test.info().project.name} ${Date.now()}`
    const workflowName = deriveWorkflowId(displayName)
    expect((await page.request.post(`${API_BASE}/api/v1/dev/seed`)).ok()).toBeTruthy()
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()

    await createWorkflow(page, displayName)
    await installExportGraph(page, workflowName)
    const generateNode = page.locator('.vue-flow__node[data-id="generate_result"]')
    const seedNode = page.locator('.vue-flow__node[data-id="seed_result"]')
    await expect(generateNode.locator('.node-name')).toHaveText('Generated result')
    await expect(seedNode.locator('.node-name')).toHaveText('Seed result')

    const firstRunId = await runAndReadId(
      page,
      () => page.getByTestId('run-workflow-button').click(),
    )

    await generateNode.click()
    await page.locator('.dv-tab').filter({ hasText: /^Nodes$/ }).click()
    const values = page.getByTestId('panel-nodePanel').getByTestId('list-input-values')
    await values.fill('[2]')
    await values.press('Tab')
    await expect.poll(async () => {
      const response = await page.request.get(
        `${API_BASE}/api/v1/workflow-drafts/${workflowName}`,
      )
      const draft = await response.json()
      return draft.graph.nodes.find((node: { id: string }) => node.id === 'generate_result')
        ?.parameters.values
    }).toEqual([2])

    const secondRunId = await runAndReadId(page, async () => {
      await page.getByTestId('run-selected-button').click()
      const confirmation = page.getByTestId('out-of-date-confirm')
      await expect(confirmation).toBeVisible()
      await expect(confirmation).toContainText('generate_result')
      await confirmation.getByTestId('out-of-date-continue').click()
    })
    expect(secondRunId).not.toBe(firstRunId)

    await openExportDialog(page)
    const latestDownloadPromise = page.waitForEvent('download')
    await page.getByTestId('export-latest-results').click()
    const latestDownload = await latestDownloadPromise
    expect(latestDownload.suggestedFilename()).toContain('latest-results.zip')
    const latestPath = await latestDownload.path()
    expect(latestPath).not.toBeNull()
    const latest = zipEntries(await readFile(latestPath!))
    expect([...latest.keys()].sort()).toEqual([
      'latest/generate_result/dataframe.csv',
      'latest/generate_result/dataframe.json',
      'latest/generate_result/dataframe.parquet',
      'latest/generate_result/provenance.json',
      'latest/seed_result/dataframe.csv',
      'latest/seed_result/dataframe.json',
      'latest/seed_result/dataframe.parquet',
      'latest/seed_result/provenance.json',
    ])
    expect(latest.get('latest/generate_result/dataframe.csv')!.toString('utf8'))
      .toBe(',marker\n0,2\n')
    expect(latest.get('latest/seed_result/dataframe.csv')!.toString('utf8'))
      .toBe(',number,label\n0,1,one\n1,2,two\n2,3,three\n')
    expect(JSON.parse(latest.get('latest/generate_result/provenance.json')!.toString('utf8')))
      .toMatchObject({ run: { run_id: secondRunId } })
    expect(JSON.parse(latest.get('latest/seed_result/provenance.json')!.toString('utf8')))
      .toMatchObject({ run: { run_id: firstRunId } })

    await openExportDialog(page)
    const bundleDownloadPromise = page.waitForEvent('download')
    await page.getByTestId('export-workflow-with-results').click()
    const bundleDownload = await bundleDownloadPromise
    expect(bundleDownload.suggestedFilename()).toContain('workflow-and-results.zip')
    const bundlePath = await bundleDownload.path()
    expect(bundlePath).not.toBeNull()
    const bundle = zipEntries(await readFile(bundlePath!))
    const manifest = JSON.parse(bundle.get('bioimageflow-results-bundle.json')!.toString('utf8'))
    expect(manifest).toMatchObject({
      schema: 'bioimageflow-results-bundle/v1',
      kind: 'workflow-with-results',
      workflow_id: workflowName,
      results: {
        kind: 'latest-successful-run',
        run_id: secondRunId,
        path: `results/runs/${secondRunId}`,
      },
    })
    const nestedArchive = bundle.get(manifest.workflow.archive)
    expect(nestedArchive).toBeDefined()
    expect(createHash('sha256').update(nestedArchive!).digest('hex'))
      .toBe(manifest.workflow.sha256)
    const runPrefix = `results/runs/${secondRunId}/nodes/generate_result/outputs/`
    expect([...bundle.keys()].filter(name => name.startsWith(runPrefix)).sort()).toEqual([
      `${runPrefix}dataframe.csv`,
      `${runPrefix}dataframe.json`,
      `${runPrefix}dataframe.parquet`,
      `${runPrefix}provenance.json`,
    ])
    expect([...bundle.keys()].some(name => name.includes('/nodes/seed_result/'))).toBe(false)
    expect(bundle.get(`${runPrefix}dataframe.csv`)!.toString('utf8')).toBe(',marker\n0,2\n')
    expect(JSON.parse(bundle.get(`${runPrefix}provenance.json`)!.toString('utf8')))
      .toMatchObject({ run: { run_id: secondRunId } })

    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`)
  })
})
