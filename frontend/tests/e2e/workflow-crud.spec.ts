import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

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
  await deleteWorkflowIfExists(page, name)
  const response = await page.request.post(`${API_BASE}/api/v1/workflows`, {
    data: { name, display_name: displayName },
  })
  expect(response.status()).toBe(201)
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

async function openWorkflowFromPanel(page: Page, name: string, displayName: string) {
  await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
  await page.getByTestId('workflow-search').fill(displayName)
  const row = page.getByTestId(`workflow-row-${name.replace(/[^a-zA-Z0-9_-]/g, '_')}`)
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

  test('creates a workflow from the polished dialog', { tag: '@critical' }, async ({ page }) => {
    const displayName = uniqueName('Dialog Create', page)
    const name = deriveWorkflowId(displayName)
    await deleteWorkflowIfExists(page, name)

    await chooseWorkflowItem(page, 'New')
    await expect(page.locator('[data-testid="workflow-dialog"]')).toBeVisible()
    await page.locator('[data-testid="workflow-display-name-input"]').fill(displayName)
    await expect(page.locator('[data-testid="workflow-generated-name"]')).toContainText(name)
    await page.locator('[data-testid="workflow-dialog-submit"]').click()

    await expect(page.locator('[data-testid="workflow-dialog"]')).not.toBeVisible()
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText(displayName)

    const response = await page.request.get(`${API_BASE}/api/v1/workflows`)
    expect(response.ok()).toBeTruthy()
    const workflows = await response.json()
    expect(
      workflows.some(
        (workflow: { name: string; display_name: string }) =>
          workflow.name === name && workflow.display_name === displayName,
      ),
    ).toBe(true)

    await deleteWorkflowIfExists(page, name)
  })

  test('import collision rename persists the chosen visible name', { tag: '@critical' }, async ({ page }) => {
    const originalLabel = uniqueName('Original Import', page)
    const original = deriveWorkflowId(originalLabel)
    const renamed = uniqueName('Renamed Import', page)
    try {
      await createWorkflow(page, original, originalLabel)
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
      await page.getByTestId('import-rename-submit').click()
      await expect(page.getByTestId('import-rename-dialog')).not.toBeVisible()
      await expect(page.getByTestId('workflow-title')).toHaveText(renamed)
      await expect(page.getByTestId('canvas-tab').filter({ hasText: renamed })).toBeVisible()
      await openWorkflowFromPanel(page, renamed, renamed)
      await expect(page.getByTestId(`workflow-row-${renamed.replace(/[^a-zA-Z0-9_-]/g, '_')}`)).toContainText(renamed)

      await page.reload()
      await openWorkflowFromPanel(page, renamed, renamed)
      const originalResponse = await page.request.get(`${API_BASE}/api/v1/workflows/${original}`)
      expect((await originalResponse.json()).info.display_name).toBe(originalLabel)
    } finally {
      await page.goto('about:blank')
      await deleteWorkflowIfExists(page, renamed)
      await deleteWorkflowIfExists(page, original)
    }
  })

  test('save-as creates an independent graph without copying results and switches exactly', { tag: '@critical' }, async ({ page }) => {
    test.setTimeout(60_000)
    const baseDisplayName = uniqueName('Dialog Base', page)
    const copyDisplayName = `${baseDisplayName} Copy`
    const base = deriveWorkflowId(baseDisplayName)
    const copy = deriveWorkflowId(copyDisplayName)
    try {
      await deleteWorkflowIfExists(page, base)
      await deleteWorkflowIfExists(page, copy)
      await seedDevelopmentTools(page)
      await page.reload()

      await chooseWorkflowItem(page, 'New')
      await page.getByTestId('workflow-display-name-input').fill(baseDisplayName)
      await page.getByTestId('workflow-dialog-submit').click()
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
        name: base,
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
      expect(await baseResult.json()).toMatchObject({
        rows: [
          { number: 1, label: 'one' },
          { number: 2, label: 'two' },
          { number: 3, label: 'three' },
        ],
        total_rows: 3,
      })

      await chooseWorkflowItem(page, 'Save As')
      await page.getByTestId('workflow-display-name-input').fill(copyDisplayName)
      await expect(page.getByTestId('workflow-generated-name')).toContainText(copy)
      await page.getByTestId('workflow-dialog-submit').click()
      await expect(page.getByTestId('workflow-title')).toContainText(copyDisplayName)

      const baseAfterCopy = await savedWorkflow(page, base)
      const copyBeforeEdit = await savedWorkflow(page, copy)
      const copyDraftBeforeEdit = await acceptedDraft(page, copy)
      expect(baseAfterCopy.graph).toEqual(baseBeforeCopy.graph)
      expect(copyBeforeEdit.info).toMatchObject({ id: copy, display_name: copyDisplayName })
      expect(copyBeforeEdit.graph).toMatchObject({
        name: copy,
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
    } finally {
      if (!page.isClosed()) {
        await page.goto('about:blank')
        await deleteWorkflowIfExists(page, copy)
        await deleteWorkflowIfExists(page, base)
      }
    }
  })

  test('delete workflow uses confirmation dialog and clears server file', async ({ page }) => {
    const displayName = uniqueName('Dialog Delete', page)
    const name = deriveWorkflowId(displayName)
    await deleteWorkflowIfExists(page, name)

    await chooseWorkflowItem(page, 'New')
    await page.locator('[data-testid="workflow-display-name-input"]').fill(displayName)
    await page.locator('[data-testid="workflow-dialog-submit"]').click()
    await expect(page.locator('[data-testid="workflow-title"]')).toContainText(displayName)

    await chooseWorkflowItem(page, 'Delete')
    await expect(page.locator('[data-testid="delete-workflow-dialog"]')).toBeVisible()
    await page.locator('[data-testid="delete-workflow-confirm"]').click()
    await expect(page.locator('[data-testid="delete-workflow-dialog"]')).not.toBeVisible()

    const deleted = await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)
    expect(deleted.status()).toBe(404)
  })

  test('deleting A closes its exact tab, activates B, and cannot recreate A on reload', async ({ page }) => {
    const firstDisplay = uniqueName('Delete Tab A', page)
    const secondDisplay = uniqueName('Delete Tab B', page)
    const firstName = deriveWorkflowId(firstDisplay)
    const secondName = deriveWorkflowId(secondDisplay)
    await createWorkflow(page, firstName, firstDisplay)
    await createWorkflow(page, secondName, secondDisplay)
    await page.reload()
    await openWorkflowFromPanel(page, firstName, firstDisplay)
    await openWorkflowFromPanel(page, secondName, secondDisplay)

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
    await page.getByTestId('delete-workflow-confirm').click()

    await expect(firstTab).not.toBeVisible()
    await expect(secondTab).toBeVisible()
    await expect(page.getByTestId('workflow-title')).toContainText(secondDisplay)
    expect(implicitCreates).toEqual([])

    await page.reload()
    await expect(page.getByTestId('canvas-tab').filter({ hasText: firstDisplay })).toHaveCount(0)
    await expect(page.getByTestId('canvas-tab').filter({ hasText: secondDisplay })).toBeVisible()
    await expect(page.getByTestId('workflow-title')).toContainText(secondDisplay)
    expect((await page.request.get(`${API_BASE}/api/v1/workflows/${firstName}`)).status()).toBe(404)
    expect(implicitCreates).toEqual([])

    await deleteWorkflowIfExists(page, secondName)
  })

  test('deleting the last workflow leaves a non-persistent empty state across reload', async ({ page }) => {
    const existing = await page.request.get(`${API_BASE}/api/v1/workflows`)
    for (const workflow of await existing.json() as Array<{ name: string }>) {
      await deleteWorkflowIfExists(page, workflow.name)
    }
    const displayName = uniqueName('Delete Last', page)
    const name = deriveWorkflowId(displayName)
    await createWorkflow(page, name, displayName)
    await page.reload()
    await expect(page.getByTestId('canvas-tab').filter({ hasText: displayName })).toBeVisible()
    const implicitCreates: string[] = []
    page.on('request', (request) => {
      if (
        request.method() === 'POST'
        && new URL(request.url()).pathname === '/api/v1/workflows'
      ) implicitCreates.push(request.url())
    })

    await chooseWorkflowItem(page, 'Delete')
    await page.getByTestId('delete-workflow-confirm').click()

    await expect(page.getByTestId('canvas-placeholder')).toContainText('No workflow is open')
    await expect(page.getByTestId('canvas-tab')).toHaveCount(0)
    expect(implicitCreates).toEqual([])

    await page.reload()
    await expect(page.getByTestId('canvas-placeholder')).toContainText('No workflow is open')
    await expect(page.getByTestId('canvas-tab')).toHaveCount(0)
    expect((await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)).status()).toBe(404)
    expect(implicitCreates).toEqual([])
  })
})
