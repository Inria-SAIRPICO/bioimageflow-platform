import { test, expect } from '@playwright/test'
import type { Page, Request } from '@playwright/test'
import { createHash } from 'node:crypto'
import { lstatSync, readFileSync, readdirSync, readlinkSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import type { GraphState, NodeDataResponse, WorkflowFile, WorkflowInfo } from '../../src/api/types'

function fileSnapshot(root: string): Record<string, string> {
  const files: Record<string, string> = {}
  const visit = (directory: string, prefix: string) => {
    for (const name of readdirSync(directory).sort()) {
      const path = join(directory, name)
      const key = `${prefix}${name}`
      const stat = lstatSync(path)
      if (stat.isSymbolicLink()) files[key] = `link:${readlinkSync(path)}`
      else if (stat.isDirectory()) visit(path, `${key}/`)
      else files[key] = createHash('sha256').update(readFileSync(path)).digest('hex')
    }
  }
  visit(root, '')
  return files
}

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

function uniqueName(prefix: string, page: Page): string {
  const project = test.info().project.name.replace(/[^a-zA-Z0-9_-]/g, '_')
  return `${prefix}_${project}_${Date.now()}_${Math.floor(Math.random() * 10000)}`
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

async function openWorkflowMenu(page: Page) {
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
}

async function chooseWorkflowItem(page: Page, label: string) {
  await openWorkflowMenu(page)
  await page.getByRole('menuitem', { name: label, exact: true }).click()
}

async function deleteWorkflowIfExists(page: Page, name: string) {
  await page.request.delete(`${API_BASE}/api/v1/workflows/${name}`).catch(() => undefined)
}

async function createWorkflow(page: Page, name: string, displayName: string) {
  const response = await page.request.post(`${API_BASE}/api/v1/workflows`, {
    data: { name, display_name: displayName },
  })
  expect(response.status()).toBe(201)
  return (await response.json()).id as string
}

async function submitWorkflowDialog(page: Page, method = 'POST'): Promise<WorkflowInfo> {
  const created = page.waitForResponse(response =>
    new URL(response.url()).pathname.startsWith('/api/v1/workflows')
    && response.request().method() === method,
  )
  await page.getByTestId('workflow-dialog-submit').click()
  const response = await created
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json()
}

async function seedDevelopmentTools(page: Page) {
  const response = await page.request.post(`${API_BASE}/api/v1/dev/seed`)
  expect(response.ok(), await response.text()).toBeTruthy()
}

async function savedWorkflow(page: Page, name: string) {
  const response = await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json()
}

async function acceptedDraft(page: Page, name: string) {
  const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json()
}

async function openWorkflowFromDialog(page: Page, name: string, displayName: string) {
  await chooseWorkflowItem(page, 'Open')
  await expect(page.getByTestId('open-workflow-dialog')).toBeVisible()
  await page.getByTestId('workflow-open-search').fill(displayName)
  await page.getByTestId(`workflow-open-option-${name}`).click()
  await page.getByTestId('workflow-open-submit').click()
  await expect(page.getByTestId('workflow-title')).toContainText(displayName)
}

async function showWorkflowsPanel(page: Page) {
  const panel = page.getByTestId('workflows-panel')
  if (!await panel.isVisible()) {
    // Dockview mounts only the active content. The real catalog group contains
    // Tools, Datasets or Workflows; the empty canvas uses a different group.
    const catalogGroup = page.locator('.dv-groupview').filter({
      has: page.locator('.tools-panel, .datasets-panel, [data-testid="workflows-panel"]'),
    })
    await expect(catalogGroup).toHaveCount(1)
    await catalogGroup.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
  }
  await expect(panel).toBeVisible()
  return panel
}

async function openWorkflowFromPanel(page: Page, name: string, displayName: string) {
  const panel = await showWorkflowsPanel(page)
  await panel.getByTestId('workflow-search').fill(displayName)
  const row = panel.getByTestId(`workflow-row-${name.replace(/[^a-zA-Z0-9_-]/g, '_')}`)
  await expect(row).toBeVisible()
  await row.dblclick()
  await expect(page.getByTestId('workflow-title')).toContainText(displayName)
}

test.describe('workflow CRUD dialogs', () => {
  test.describe.configure({ mode: 'serial' })

  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await expect(page.locator('[data-testid="workflow-title"]')).toBeVisible()
  })

  test('creates and saves edits to a workflow inside a folder', { tag: '@critical' }, async ({ page }) => {
    const folder = uniqueName('Analysis Results', page)
    const displayName = uniqueName('Folder workflow', page)
    const leaf = deriveWorkflowId(displayName)
    const relativePath = `${folder}/${leaf}`
    let name = ''
    const created = await page.request.post(`${API_BASE}/api/v1/workflows/folders`, { data: { path: folder } })
    expect(created.status(), await created.text()).toBe(201)
    try {
      await seedDevelopmentTools(page)
      await page.reload()
      const panel = await showWorkflowsPanel(page)
      await panel.getByTestId(`workflow-folder-${folder.replace(/[^a-zA-Z0-9_-]/g, '_')}`).click()
      await panel.getByTestId('workflow-new-btn').click()
      await page.getByTestId('workflow-display-name-input').fill(displayName)
      name = (await submitWorkflowDialog(page)).id
      await expect(page.getByTestId('workflow-title')).toContainText(displayName)
      const initial = await savedWorkflow(page, name) as WorkflowFile
      expect(initial.graph.name).toBe(leaf)

      await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
      await page.getByTestId('tool-search').fill('SeedNumbers')
      const accepted = page.waitForResponse(response =>
        response.url().endsWith(`/api/v1/workflow-drafts/${encodeURI(name)}`)
        && response.request().method() === 'PUT',
      )
      await page.getByTestId('tool-item-SeedNumbers').dblclick()
      const response = await accepted
      expect(response.status(), await response.text()).toBe(200)
      const draft = await response.json()
      expect(draft.workflow_id).toBe(name)
      expect(draft.graph).toMatchObject({
        name: leaf, display_name: displayName, config: initial.graph.config,
        nodes: [{ tool_name: 'SeedNumbers' }],
      })
      await expect(page.getByTestId('canvas-persistence-issue')).toHaveCount(0)

      const saved = page.waitForResponse(response =>
        response.url().endsWith(`/api/v1/workflows/${encodeURI(name)}`)
        && response.request().method() === 'PUT',
      )
      await chooseWorkflowItem(page, 'Save')
      expect((await saved).status()).toBe(200)
      expect((await savedWorkflow(page, name)).graph).toEqual(draft.graph)
      await page.reload()
      await expect(page.getByTestId('workflow-title')).toContainText(displayName)
      await expect(page.locator('.vue-flow__node')).toHaveCount(1)
      await expect(page.getByTestId('canvas-persistence-issue')).toHaveCount(0)

      // Reproduce a queued browser snapshot left by the former creation bug.
      const recoveryGraph = structuredClone(draft.graph) as GraphState
      recoveryGraph.name = relativePath
      recoveryGraph.nodes[0]!.name = 'Recovered queued edit'
      await page.evaluate(async ({ name, graph, workspacePath, generation }) => {
        const { useAutoSave, writeAutoSaveEntry } = await import('/src/composables/useAutoSave.ts')
        await writeAutoSaveEntry({
          name, graph, timestamp: Date.now() + 1000,
          workspace_path: workspacePath, identity_generation: generation,
        })
        await useAutoSave().setLastOpenedWorkflow(name)
      }, { name, graph: recoveryGraph, workspacePath: initial.info.workspace_path!, generation: initial.info.identity_generation })
      const recovered = page.waitForResponse(response =>
        response.url().endsWith(`/api/v1/workflow-drafts/${encodeURI(name)}`)
        && response.request().method() === 'PUT',
      )
      await page.reload()
      const recoveredResponse = await recovered
      expect(recoveredResponse.status(), await recoveredResponse.text()).toBe(200)
      expect((await recoveredResponse.json()).graph).toEqual({ ...recoveryGraph, name: leaf })
      expect((await savedWorkflow(page, name)).graph).toEqual(draft.graph)
      await expect(page.locator('.vue-flow__node')).toContainText('Recovered queued edit')
      await expect(page.getByTestId('canvas-persistence-issue')).toHaveCount(0)
    } finally {
      await deleteWorkflowIfExists(page, name)
      await page.request.delete(`${API_BASE}/api/v1/workflows/folders/${folder}`, { data: { policy: 'empty' } })
    }
  })

  test('creates a workflow from the polished dialog', { tag: '@critical' }, async ({ page }) => {
    const displayName = uniqueName('Dialog Create', page)
    const relativePath = deriveWorkflowId(displayName)

    await chooseWorkflowItem(page, 'New')
    await expect(page.locator('[data-testid="workflow-dialog"]')).toBeVisible()
    await page.locator('[data-testid="workflow-display-name-input"]').fill(displayName)
    await expect(page.locator('[data-testid="workflow-generated-name"]')).toContainText(relativePath)
    const name = (await submitWorkflowDialog(page)).id

    await expect(page.locator('[data-testid="workflow-dialog"]')).not.toBeVisible()
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText(displayName)

    const response = await page.request.get(`${API_BASE}/api/v1/workflows`)
    expect(response.ok()).toBeTruthy()
    const workflows = await response.json()
    expect(
      workflows.some(
        (workflow: { id: string; display_name: string }) =>
          workflow.id === name && workflow.display_name === displayName,
      ),
    ).toBe(true)

    await deleteWorkflowIfExists(page, name)
  })

  test('create and Save As refuse invalid or occupied names without changing the open workflow', { tag: '@critical' }, async ({ page }) => {
    const sourceLabel = uniqueName('Dialog Source', page)
    const occupiedLabel = uniqueName('Dialog Occupied', page)
    const cancelledLabel = uniqueName('Dialog Cancelled', page)
    let source = ''
    let occupied = ''
    const occupiedPath = deriveWorkflowId(occupiedLabel)
    const cancelled = deriveWorkflowId(cancelledLabel)
    try {
      occupied = await createWorkflow(page, occupiedPath, occupiedLabel)
      await chooseWorkflowItem(page, 'New')
      const dialog = page.getByTestId('workflow-dialog')
      await expect(dialog).toBeVisible()
      await page.getByTestId('workflow-display-name-input').fill(sourceLabel)
      source = (await submitWorkflowDialog(page)).id
      await expect(dialog).not.toBeVisible()
      await expect(page.getByTestId('workflow-title')).toContainText(sourceLabel)

      const savedSource = page.waitForResponse(response =>
        response.url().endsWith(`/api/v1/workflows/${source}`)
        && response.request().method() === 'PUT'
        && response.status() === 200,
      )
      await chooseWorkflowItem(page, 'Save')
      await savedSource

      const sourceBefore = await savedWorkflow(page, source)
      const sourceDraftBefore = await acceptedDraft(page, source)
      const occupiedBefore = await savedWorkflow(page, occupied)
      const listBefore = await (await page.request.get(`${API_BASE}/api/v1/workflows`)).json()

      await chooseWorkflowItem(page, 'New')
      await expect(dialog).toBeVisible()
      await page.getByTestId('workflow-display-name-input').fill('!!!')
      await expect(page.getByTestId('workflow-display-name-error')).toHaveText('Use at least one letter or number.')
      await expect(page.getByTestId('workflow-dialog-submit')).toBeDisabled()
      await page.getByTestId('workflow-display-name-input').fill(occupiedLabel)
      const refusedCreate = page.waitForResponse(response =>
        response.url().endsWith('/api/v1/workflows')
        && response.request().method() === 'POST',
      )
      await page.getByTestId('workflow-dialog-submit').click()
      expect((await refusedCreate).status()).toBe(409)
      await expect(dialog).toBeVisible()
      await expect(page.getByTestId('workflow-generated-name')).toContainText(`${occupiedPath}_2`)
      await page.getByTestId('workflow-dialog-cancel').click()
      await expect(dialog).not.toBeVisible()

      await chooseWorkflowItem(page, 'Save As')
      await expect(dialog).toBeVisible()
      await page.getByTestId('workflow-display-name-input').fill('!!!')
      await expect(page.getByTestId('workflow-dialog-submit')).toBeDisabled()
      await page.getByTestId('workflow-display-name-input').fill(occupiedLabel)
      const refusedCopy = page.waitForResponse(response =>
        response.url().endsWith(`/api/v1/workflows/${source}`)
        && response.request().method() === 'PATCH',
      )
      await page.getByTestId('workflow-dialog-submit').click()
      expect((await refusedCopy).status()).toBe(409)
      await expect(dialog).toBeVisible()
      await expect(page.getByTestId('workflow-generated-name')).toContainText(`${occupiedPath}_2`)
      await page.getByTestId('workflow-display-name-input').fill(cancelledLabel)
      await expect(page.getByTestId('workflow-generated-name')).toContainText(cancelled)
      await page.getByTestId('workflow-dialog-cancel').click()
      await expect(dialog).not.toBeVisible()

      await expect(page.getByTestId('workflow-title')).toContainText(sourceLabel)
      await expect(page.getByTestId('canvas-tab').filter({ hasText: sourceLabel })).toHaveCount(1)
      expect(await savedWorkflow(page, source)).toEqual(sourceBefore)
      expect(await acceptedDraft(page, source)).toMatchObject({
        graph: sourceDraftBefore.graph,
        dirty_against_saved: false,
      })
      expect(await savedWorkflow(page, occupied)).toEqual(occupiedBefore)
      expect(await (await page.request.get(`${API_BASE}/api/v1/workflows`)).json()).toEqual(listBefore)
      expect((await (await page.request.get(`${API_BASE}/api/v1/workflows`)).json()).some((item: WorkflowInfo) => item.relative_path === cancelled)).toBe(false)

      await page.reload()
      await expect(page.getByTestId('workflow-title')).toContainText(sourceLabel)
      expect(await savedWorkflow(page, source)).toEqual(sourceBefore)
      expect(await acceptedDraft(page, source)).toMatchObject({
        graph: sourceDraftBefore.graph,
        dirty_against_saved: false,
      })
      expect(await savedWorkflow(page, occupied)).toEqual(occupiedBefore)
      expect(await (await page.request.get(`${API_BASE}/api/v1/workflows`)).json()).toEqual(listBefore)
      expect((await (await page.request.get(`${API_BASE}/api/v1/workflows`)).json()).some((item: WorkflowInfo) => item.relative_path === cancelled)).toBe(false)
    } finally {
      await page.goto('about:blank')
      await deleteWorkflowIfExists(page, source)
      await deleteWorkflowIfExists(page, occupied)
    }
  })

  test('import collision rename persists the chosen visible name', { tag: '@critical' }, async ({ page }) => {
    const originalLabel = uniqueName('Original Import', page)
    let original = ''
    let renamedId = ''
    const renamed = uniqueName('Renamed Import', page)
    try {
      original = await createWorkflow(page, deriveWorkflowId(originalLabel), originalLabel)
      const exported = await page.request.post(`${API_BASE}/api/v1/workflows/${original}/export`)
      expect(exported.ok(), await exported.text()).toBeTruthy()
      const chooserPromise = page.waitForEvent('filechooser')
      await chooseWorkflowItem(page, 'Import')
      await (await chooserPromise).setFiles({
        name: `${original}.bioimageflow.zip`,
        mimeType: 'application/zip',
        buffer: await exported.body(),
      })
      await expect(page.getByTestId('import-rename-dialog')).toBeVisible()
      await page.getByTestId('import-rename-input').fill(renamed)
      const imported = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/v1/workflows/import')
      await page.getByTestId('import-rename-submit').click()
      renamedId = (await (await imported).json()).info.id
      await expect(page.getByTestId('import-rename-dialog')).not.toBeVisible()
      await expect(page.getByTestId('workflow-title')).toHaveText(renamed)
      await expect(page.getByTestId('canvas-tab').filter({ hasText: renamed })).toBeVisible()
      await openWorkflowFromPanel(page, renamedId, renamed)
      await expect(page.getByTestId(`workflow-row-${renamedId}`)).toContainText(renamed)

      await page.reload()
      await openWorkflowFromPanel(page, renamedId, renamed)
      const originalResponse = await page.request.get(`${API_BASE}/api/v1/workflows/${original}`)
      expect((await originalResponse.json()).info.display_name).toBe(originalLabel)
    } finally {
      await page.goto('about:blank')
      await deleteWorkflowIfExists(page, renamedId)
      await deleteWorkflowIfExists(page, original)
    }
  })

  test('save-as creates an independent graph without copying results and switches exactly', { tag: '@critical' }, async ({ page }) => {
    test.setTimeout(60_000)
    const baseDisplayName = uniqueName('Dialog Base', page)
    const copyDisplayName = `${baseDisplayName} Copy`
    const basePath = deriveWorkflowId(baseDisplayName)
    const copyPath = deriveWorkflowId(copyDisplayName)
    let base = ''
    let copy = ''
    let unrelated = ''
    const folder = `${basePath}_folder`
    const renamedFolder = `${folder}_renamed`
    const folderPatches: string[] = []
    const observeFolderPatch = (request: Request) => {
      if (request.method() === 'PATCH' && new URL(request.url()).pathname === `/api/v1/workflows/folders/${folder}`) {
        folderPatches.push(request.postData() ?? '')
      }
    }
    let primaryOccurred = false
    const cleanupErrors: unknown[] = []
    try {
      await seedDevelopmentTools(page)
      await page.reload()

      await chooseWorkflowItem(page, 'New')
      await page.getByTestId('workflow-display-name-input').fill(baseDisplayName)
      base = (await submitWorkflowDialog(page)).id
      await expect(page.getByTestId('workflow-title')).toContainText(baseDisplayName)

      await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
      await page.getByTestId('tool-search').fill('SeedNumbers')
      const seedTool = page.getByTestId('tool-item-SeedNumbers')
      await expect(seedTool).toBeVisible()
      const acceptedNode = page.waitForResponse(response =>
        response.url().endsWith(`/api/v1/workflow-drafts/${base}`)
        && response.request().method() === 'PUT'
        && response.status() === 200,
      )
      await seedTool.dblclick()
      await acceptedNode
      const baseNode = page.locator('.vue-flow__node')
      await expect(baseNode).toHaveCount(1)
      const nodeId = await baseNode.getAttribute('data-id')
      expect(nodeId).toBeTruthy()

      const saveBase = page.waitForResponse(response =>
        response.url().endsWith(`/api/v1/workflows/${base}`)
        && response.request().method() === 'PUT'
        && response.status() === 200,
      )
      await chooseWorkflowItem(page, 'Save')
      await saveBase
      const baseBeforeCopy = await savedWorkflow(page, base)
      expect(baseBeforeCopy.graph).toMatchObject({
        name: basePath,
        display_name: baseDisplayName,
        nodes: [{ id: nodeId, tool_name: 'SeedNumbers', source_module: null }],
      })

      const runResponse = page.waitForResponse(response =>
        response.url().endsWith('/api/v1/execution/run')
        && response.request().method() === 'POST',
      )
      await page.getByTestId('run-workflow-button').click()
      expect((await runResponse).status()).toBe(202)
      await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete', { timeout: 30_000 })
      const baseResult = await page.request.post(`${API_BASE}/api/v1/nodes/${nodeId}/data/query`, {
        data: { workflow_name: base },
      })
      expect(baseResult.ok(), await baseResult.text()).toBeTruthy()
      const capturedResult = await baseResult.json() as NodeDataResponse
      expect(capturedResult).toMatchObject({
        rows: [
          { number: 1, label: 'one' },
          { number: 2, label: 'two' },
          { number: 3, label: 'three' },
        ],
        total_rows: 3,
      })
      expect(capturedResult.source_identity).toMatchObject({
        run_id: expect.any(String), node_key: nodeId,
        result_key: expect.any(String), record_id: expect.any(String),
      })

      await chooseWorkflowItem(page, 'Save As')
      await page.getByTestId('workflow-display-name-input').fill(copyDisplayName)
      await expect(page.getByTestId('workflow-generated-name')).toContainText(copyPath)
      copy = (await submitWorkflowDialog(page, 'PATCH')).id
      await expect(page.getByTestId('workflow-title')).toContainText(copyDisplayName)

      const baseAfterCopy = await savedWorkflow(page, base)
      const copyBeforeEdit = await savedWorkflow(page, copy)
      const copyDraftBeforeEdit = await acceptedDraft(page, copy)
      expect(baseAfterCopy.graph).toEqual(baseBeforeCopy.graph)
      expect(copyBeforeEdit.info).toMatchObject({ id: copy, display_name: copyDisplayName })
      expect(copyBeforeEdit.graph).toMatchObject({
        name: copyPath,
        display_name: copyDisplayName,
        nodes: [{ id: nodeId, tool_name: 'SeedNumbers', source_module: null }],
      })
      expect(copyDraftBeforeEdit.graph).toEqual(copyBeforeEdit.graph)
      expect(copyBeforeEdit.artifact_hash).not.toBe(baseBeforeCopy.artifact_hash)

      const copiedResult = await page.request.post(`${API_BASE}/api/v1/nodes/${nodeId}/data/query`, {
        data: { workflow_name: copy },
      })
      expect(copiedResult.status()).toBe(404)

      const copyNode = page.locator(`.vue-flow__node[data-id="${nodeId}"]`)
      await copyNode.click()
      await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
      const nodePanel = page.getByTestId('panel-nodePanel')
      await nodePanel.locator('.node-name').dblclick()
      const nameInput = nodePanel.locator('.name-input')
      await nameInput.fill('Copy-only seed')
      const acceptedRename = page.waitForResponse(response =>
        response.url().endsWith(`/api/v1/workflow-drafts/${copy}`)
        && response.request().method() === 'PUT'
        && response.status() === 200,
      )
      await nameInput.press('Enter')
      await acceptedRename
      await expect(copyNode.locator('.node-name')).toHaveText('Copy-only seed')
      const copyAfterRename = await acceptedDraft(page, copy)
      expect(copyAfterRename.graph.nodes[0]).toMatchObject({ id: nodeId, name: 'Copy-only seed' })

      const saveCopy = page.waitForResponse(response =>
        response.url().endsWith(`/api/v1/workflows/${copy}`)
        && response.request().method() === 'PUT'
        && response.status() === 200,
      )
      await chooseWorkflowItem(page, 'Save')
      await saveCopy

      await openWorkflowFromDialog(page, base, baseDisplayName)
      expect((await acceptedDraft(page, base)).graph).toEqual(baseBeforeCopy.graph)
      expect((await savedWorkflow(page, base)).graph).toEqual(baseBeforeCopy.graph)
      const retainedBaseResult = await page.request.post(`${API_BASE}/api/v1/nodes/${nodeId}/data/query`, {
        data: { workflow_name: base },
      })
      expect(retainedBaseResult.ok(), await retainedBaseResult.text()).toBeTruthy()

      await page.reload()
      await openWorkflowFromDialog(page, copy, copyDisplayName)
      expect((await acceptedDraft(page, copy)).graph).toEqual(copyAfterRename.graph)
      expect((await savedWorkflow(page, copy)).graph).toEqual(copyAfterRename.graph)
      expect((await savedWorkflow(page, base)).graph).toEqual(baseBeforeCopy.graph)

      // Public API setup places these already-tested graphs in one owned folder.
      // Only the following visible folder Rename is GUI move evidence.
      await page.goto('about:blank')
      const createdFolder = await page.request.post(`${API_BASE}/api/v1/workflows/folders`, { data: { path: folder } })
      expect(createdFolder.status(), await createdFolder.text()).toBe(201)
      unrelated = await createWorkflow(page, `${basePath}_unrelated`, 'Unrelated move sentinel')
      const unrelatedBefore = await savedWorkflow(page, unrelated) as WorkflowFile
      const sentinel = join(dirname(unrelatedBefore.info.path), 'unmanaged.txt')
      writeFileSync(sentinel, 'keep this unrelated file\n')
      const unrelatedFiles = fileSnapshot(dirname(unrelatedBefore.info.path))
      const parentGraph: GraphState = structuredClone(copyAfterRename.graph)
      parentGraph.nodes.push({
        type: 'workflow', id: 'moved-child', name: 'Moved child', position: [450, 180],
        enabled: true, collapsed: false,
        workflow: structuredClone(baseBeforeCopy.graph), bindings: {},
        source: { kind: 'workspace', workflow_id: base, artifact_hash: baseBeforeCopy.artifact_hash },
      })
      const installedParent = await page.request.put(`${API_BASE}/api/v1/workflows/${copy}`, { data: { graph: parentGraph } })
      expect(installedParent.ok(), await installedParent.text()).toBeTruthy()
      const currentParentDraft = await acceptedDraft(page, copy)
      const resetParent = await page.request.post(`${API_BASE}/api/v1/workflow-drafts/${copy}/reset-to-saved`, {
        data: { expected_revision: currentParentDraft.draft_revision, updated_by: 'frontend' },
      })
      expect(resetParent.ok(), await resetParent.text()).toBeTruthy()
      for (const id of [base, copy]) {
        const moved = await page.request.patch(`${API_BASE}/api/v1/workflows/${id}`, {
          data: { action: 'update', folder },
        })
        expect(moved.ok(), await moved.text()).toBeTruthy()
        expect(await moved.json()).toMatchObject({ id, relative_path: `${folder}/${id === base ? basePath : copyPath}`, identity_generation: expect.any(Number) })
      }
      const oldBase = base
      const oldCopy = copy
      const newBase = base
      const newCopy = copy
      await page.goto('/')
      await openWorkflowFromPanel(page, oldBase, baseDisplayName)
      await openWorkflowFromPanel(page, oldCopy, copyDisplayName)
      const nestedOpening = page.waitForResponse(response => response.request().method() === 'POST'
        && new URL(response.url()).pathname === '/api/v1/nested-workflow-snapshots/open')
      await page.locator('.vue-flow__node[data-id="moved-child"]:visible').dblclick()
      const nestedResponse = await nestedOpening
      expect(nestedResponse.status(), await nestedResponse.text()).toBe(201)
      let nested = await nestedResponse.json()
      await page.locator(`.vue-flow__node[data-id="${nodeId}"]:visible`).click()
      await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
      const privatePanel = page.getByTestId('panel-nodePanel')
      await privatePanel.locator('.node-name').dblclick()
      await privatePanel.locator('.name-input').fill('Private edit survives move')
      const privateWrite = page.waitForResponse(response =>
        response.url().endsWith(`/api/v1/nested-workflow-snapshots/${nested.session_id}`)
        && response.request().method() === 'PUT',
      )
      await privatePanel.locator('.name-input').press('Enter')
      const privateResponse = await privateWrite
      expect(privateResponse.ok(), await privateResponse.text()).toBeTruthy()
      nested = await privateResponse.json()
      const beforeBase = await savedWorkflow(page, oldBase) as WorkflowFile
      const beforeCopy = await savedWorkflow(page, oldCopy) as WorkflowFile
      expect(nested.owner).toMatchObject({ kind: 'root', workflow_id: oldCopy, identity_generation: beforeCopy.info.identity_generation })
      expect(nested.graph.nodes[0].name).toBe('Private edit survives move')
      expect(beforeCopy.graph.nodes.find(node => node.id === 'moved-child')).toMatchObject({
        workflow: baseBeforeCopy.graph,
      })
      const beforeBaseDraft = await acceptedDraft(page, oldBase)
      const beforeCopyDraft = await acceptedDraft(page, oldCopy)
      const baseFiles = fileSnapshot(dirname(beforeBase.info.path))
      const copyFiles = fileSnapshot(dirname(beforeCopy.info.path))
      const resultFiles = fileSnapshot(beforeBase.info.results_path)
      expect(Object.keys(resultFiles).length).toBeGreaterThan(0)
      const queryPinned = async (id: string) => {
        for (const identity of [undefined, capturedResult.source_identity]) {
          const response = await page.request.post(`${API_BASE}/api/v1/nodes/${nodeId}/data/query`, {
            data: { workflow_name: id, ...(identity ? { result_identity: identity } : {}) },
          })
          expect(response.ok(), await response.text()).toBeTruthy()
          expect(await response.json()).toMatchObject({ source_identity: capturedResult.source_identity, rows: capturedResult.rows })
        }
      }
      await queryPinned(oldBase)
      page.on('request', observeFolderPatch)
      const workflowsPanel = await showWorkflowsPanel(page)
      await workflowsPanel.getByTestId('workflow-search').fill('')
      await workflowsPanel.getByTestId(`workflow-folder-${folder}`).click()
      await workflowsPanel.getByTestId('workflow-rename-selected-btn').click()
      const folderDialog = page.getByTestId('workflow-folder-dialog')
      await expect(folderDialog).toBeVisible()
      await page.getByTestId('workflow-folder-name-input').fill(renamedFolder)
      const folderMoved = page.waitForResponse(response => response.request().method() === 'PATCH'
        && new URL(response.url()).pathname === `/api/v1/workflows/folders/${folder}`)
      await page.getByTestId('workflow-folder-dialog-submit').click()
      const movedResponse = await folderMoved
      expect(movedResponse.status(), await movedResponse.text()).toBe(200)
      expect(await movedResponse.json()).toMatchObject({ path: renamedFolder })
      expect(folderPatches.map(body => JSON.parse(body))).toEqual([{ new_path: renamedFolder }])
      await expect(folderDialog).not.toBeVisible()
      await expect(page.getByTestId('workflow-action-error')).toHaveCount(0)
      const afterBase = await savedWorkflow(page, newBase) as WorkflowFile
      const afterCopy = await savedWorkflow(page, newCopy) as WorkflowFile
      expect(afterBase.info).toMatchObject({ id: base, relative_path: `${renamedFolder}/${basePath}`, identity_generation: beforeBase.info.identity_generation })
      expect(afterCopy.info).toMatchObject({ id: copy, relative_path: `${renamedFolder}/${copyPath}`, identity_generation: beforeCopy.info.identity_generation })
      expect(afterBase.graph).toEqual(beforeBase.graph)
      expect(afterBase.artifact_hash).toBe(beforeBase.artifact_hash)
      const rewrittenParent = structuredClone(beforeCopy.graph)
      const child = rewrittenParent.nodes.find(node => node.id === 'moved-child')
      if (child?.type !== 'workflow' || !child.source) throw new Error('Missing accepted workspace provenance')
      expect(afterCopy.graph).toEqual(rewrittenParent)
      expect(afterCopy.artifact_hash).toBe(beforeCopy.artifact_hash)
      expect(await acceptedDraft(page, newBase)).toMatchObject({ workflow_id: newBase, graph: beforeBaseDraft.graph, draft_revision: beforeBaseDraft.draft_revision })
      expect(await acceptedDraft(page, newCopy)).toMatchObject({ workflow_id: newCopy, graph: rewrittenParent, draft_revision: beforeCopyDraft.draft_revision })
      expect(fileSnapshot(afterBase.info.results_path)).toEqual(resultFiles)
      await queryPinned(newBase)
      expect(await savedWorkflow(page, unrelated)).toEqual(unrelatedBefore)
      expect(fileSnapshot(dirname(unrelatedBefore.info.path))).toEqual(unrelatedFiles)
      expect(fileSnapshot(dirname(afterBase.info.path))).toEqual(baseFiles)
      expect(fileSnapshot(dirname(afterCopy.info.path))).toEqual(copyFiles)
      const retainedNested = await page.request.get(`${API_BASE}/api/v1/nested-workflow-snapshots/${nested.session_id}`)
      expect(retainedNested.ok(), await retainedNested.text()).toBeTruthy()
      expect(await retainedNested.json()).toMatchObject({ owner: nested.owner, session_id: nested.session_id, snapshot_revision: nested.snapshot_revision, graph: nested.graph })
      for (const label of [baseDisplayName, copyDisplayName]) {
        await expect(page.getByTestId('canvas-tab').filter({ has: page.getByText(label, { exact: true }) })).toHaveCount(1)
      }
      await expect(page.locator('.dv-tab').filter({ hasText: 'Moved child' })).toHaveCount(1)
      await page.reload()
      await openWorkflowFromPanel(page, newBase, baseDisplayName)
      await queryPinned(newBase)
      await openWorkflowFromPanel(page, newCopy, copyDisplayName)
      expect((await acceptedDraft(page, newCopy)).graph).toEqual(rewrittenParent)
      expect(fileSnapshot(afterBase.info.results_path)).toEqual(resultFiles)
      expect(fileSnapshot(dirname(unrelatedBefore.info.path))).toEqual(unrelatedFiles)
    } catch (error) {
      primaryOccurred = true
      throw error
    } finally {
      page.off('request', observeFolderPatch)
      if (!page.isClosed()) {
        await page.goto('about:blank').catch(error => cleanupErrors.push(error))
        for (const id of [copy, base, unrelated].filter(Boolean)) {
          try {
            const response = await page.request.delete(`${API_BASE}/api/v1/workflows/${id}`)
            expect([200, 204, 404], await response.text()).toContain(response.status())
          } catch (error) { cleanupErrors.push(error) }
        }
        for (const id of [folder, renamedFolder]) {
          try {
            const response = await page.request.delete(`${API_BASE}/api/v1/workflows/folders/${id}`, { data: { policy: 'empty' } })
            expect([200, 204, 404], await response.text()).toContain(response.status())
          } catch (error) { cleanupErrors.push(error) }
        }
      }
      if (primaryOccurred && cleanupErrors.length) console.error('Save As/folder move cleanup failures', cleanupErrors)
    }
    if (cleanupErrors.length) throw cleanupErrors[0]
  })

  test('delete workflow uses confirmation dialog and clears server file', async ({ page }) => {
    const displayName = uniqueName('Dialog Delete', page)
    await chooseWorkflowItem(page, 'New')
    await page.locator('[data-testid="workflow-display-name-input"]').fill(displayName)
    const name = (await submitWorkflowDialog(page)).id
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText(displayName)

    await chooseWorkflowItem(page, 'Delete')
    await expect(page.locator('[data-testid="delete-workflow-dialog"]')).toBeVisible()
    await page.getByTestId('delete-workflow-dialog').getByRole('button', { name: 'Cancel' }).click()
    await expect(page.getByTestId('delete-workflow-dialog')).not.toBeVisible()
    await expect(page.getByTestId('canvas-tab').filter({ hasText: displayName })).toBeVisible()
    await expect(page.getByTestId('workflow-title')).toContainText(displayName)
    expect((await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)).ok()).toBeTruthy()

    await chooseWorkflowItem(page, 'Delete')
    await expect(page.getByTestId('delete-workflow-dialog')).toContainText(displayName)
    await page.locator('[data-testid="delete-workflow-confirm"]').click()
    await expect(page.locator('[data-testid="delete-workflow-dialog"]')).not.toBeVisible()

    const deleted = await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)
    expect(deleted.status()).toBe(404)
  })

  test('deleting A closes its exact tab, activates B, and cannot recreate A on reload', async ({ page }) => {
    const firstDisplay = uniqueName('Delete Tab A', page)
    const secondDisplay = uniqueName('Delete Tab B', page)
    const firstName = await createWorkflow(page, deriveWorkflowId(firstDisplay), firstDisplay)
    const secondName = await createWorkflow(page, deriveWorkflowId(secondDisplay), secondDisplay)
    await page.reload()
    await openWorkflowFromPanel(page, firstName, firstDisplay)
    await openWorkflowFromPanel(page, secondName, secondDisplay)
    const firstBeforeDelete = await savedWorkflow(page, firstName)
    const secondBeforeDelete = await savedWorkflow(page, secondName)

    const firstTab = page.getByTestId('canvas-tab').filter({ hasText: firstDisplay })
    const secondTab = page.getByTestId('canvas-tab').filter({ hasText: secondDisplay })
    await firstTab.click()
    await expect(page.getByTestId('workflow-title')).toContainText(firstDisplay)
    const implicitCreates: string[] = []
    page.on('request', (request) => {
      if (
        request.method() === 'POST'
        && new URL(request.url()).pathname === '/api/v1/workflows'
      ) implicitCreates.push(request.url())
    })

    await chooseWorkflowItem(page, 'Delete')
    await expect(page.getByTestId('delete-workflow-dialog')).toContainText(firstDisplay)
    const deleteRequest = page.waitForRequest(request =>
      request.method() === 'DELETE'
      && new URL(request.url()).pathname === `/api/v1/workflows/${firstName}`,
    )
    await page.getByTestId('delete-workflow-confirm').click()
    const deleteUrl = new URL((await deleteRequest).url())
    expect(deleteUrl.searchParams.get('expected_identity_generation')).toBe(
      String(firstBeforeDelete.info.identity_generation),
    )

    await expect(firstTab).not.toBeVisible()
    await expect(secondTab).toBeVisible()
    await expect(page.getByTestId('workflow-title')).toContainText(secondDisplay)
    expect((await savedWorkflow(page, secondName))).toEqual(secondBeforeDelete)
    expect(implicitCreates).toEqual([])

    await page.reload()
    await expect(page.getByTestId('canvas-tab').filter({ hasText: firstDisplay })).toHaveCount(0)
    await expect(page.getByTestId('canvas-tab').filter({ hasText: secondDisplay })).toBeVisible()
    await expect(page.getByTestId('workflow-title')).toContainText(secondDisplay)
    expect((await page.request.get(`${API_BASE}/api/v1/workflows/${firstName}`)).status()).toBe(404)
    expect((await savedWorkflow(page, secondName))).toEqual(secondBeforeDelete)
    expect(implicitCreates).toEqual([])

    await deleteWorkflowIfExists(page, secondName)
  })

  test('deleting the last workflow leaves a non-persistent empty state across reload', async ({ page }) => {
    const existing = await page.request.get(`${API_BASE}/api/v1/workflows`)
    for (const workflow of await existing.json() as Array<{ name: string }>) {
      await deleteWorkflowIfExists(page, workflow.name)
    }
    const displayName = uniqueName('Delete Last', page)
    const name = await createWorkflow(page, deriveWorkflowId(displayName), displayName)
    await page.reload()
    await expect(page.getByTestId('canvas-tab').filter({ hasText: displayName })).toBeVisible()
    const lastWorkflow = await savedWorkflow(page, name)
    const implicitCreates: string[] = []
    page.on('request', (request) => {
      if (
        request.method() === 'POST'
        && new URL(request.url()).pathname === '/api/v1/workflows'
      ) implicitCreates.push(request.url())
    })

    await chooseWorkflowItem(page, 'Delete')
    const deleteRequest = page.waitForRequest(request =>
      request.method() === 'DELETE'
      && new URL(request.url()).pathname === `/api/v1/workflows/${name}`,
    )
    await page.getByTestId('delete-workflow-confirm').click()
    const deleteUrl = new URL((await deleteRequest).url())
    expect(deleteUrl.searchParams.get('expected_identity_generation')).toBe(
      String(lastWorkflow.info.identity_generation),
    )

    await expect(page.getByTestId('canvas-placeholder')).toContainText('No workflow is open')
    await expect(page.getByTestId('canvas-tab')).toHaveCount(0)
    expect(await (await page.request.get(`${API_BASE}/api/v1/workflows`)).json()).toEqual([])
    expect(implicitCreates).toEqual([])

    await page.reload()
    await expect(page.getByTestId('canvas-placeholder')).toContainText('No workflow is open')
    await expect(page.getByTestId('canvas-tab')).toHaveCount(0)
    expect((await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)).status()).toBe(404)
    expect((await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)).status()).toBe(404)
    expect(await (await page.request.get(`${API_BASE}/api/v1/workflows`)).json()).toEqual([])
    expect(implicitCreates).toEqual([])
  })
})
