import { test, expect } from '@playwright/test'
import type { APIResponse, Page } from '@playwright/test'
import type { ToolMetadata } from '../../src/api/types'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

async function deleteAllWorkflows(page: Page) {
  const response = await page.request.get(`${API_BASE}/api/v1/workflows`)
  for (const workflow of await response.json() as Array<{ name: string }>) {
    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflow.name}`)
  }
}

async function rememberLastOpenedWorkflow(page: Page, name: string) {
  await page.evaluate(async (workflowName) => {
    const { useAutoSave } = await import('/src/composables/useAutoSave.ts')
    await useAutoSave().setLastOpenedWorkflow(workflowName)
  }, name)
}

test.describe('workflow creation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    // Ensure Dockview panels are loaded
    await expect(page.locator('.dv-tab').filter({ hasText: 'Tools' })).toBeVisible()
  })

  test('Tools Panel loads with search and create button', async ({ page }) => {
    // Click Tools tab to ensure it's the active panel
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()

    // Search input present
    await expect(page.locator('[data-testid="tool-search"]')).toBeVisible()

    // Create Tool button present
    await expect(page.locator('[data-testid="create-tool-btn"]')).toBeVisible()

    // Tool list rendered
    await expect(page.locator('[data-testid="tool-list"]')).toBeVisible()
  })

  test('desktop shell shows Create Tool even when settings are unavailable', async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(window, 'pywebview', {
        configurable: true,
        value: {
          api: {
            select_file: async () => null,
            select_files: async () => [],
            select_folder: async () => null,
            resolve_dropped_paths: async () => ({ path: null, files: [] }),
            save_file: async () => null,
            set_title: async () => undefined,
            reveal_path: async () => undefined,
          },
        },
      })
    })
    await page.route('**/api/v1/settings', (route) =>
      route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'not_found', detail: 'settings unavailable' }),
      }),
    )

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()

    await expect(page.locator('[data-testid="tool-search"]')).toBeVisible()
    await expect(page.locator('[data-testid="create-tool-btn"]')).toBeVisible()
    await expect(page.locator('.dv-tab').filter({ hasText: 'Datasets' })).toHaveCount(0)
  })

  test('Canvas panel has dot grid background and no minimap', async ({ page }) => {
    const name = `canvas_grid_${Date.now()}`
    const displayName = `Canvas Grid ${name}`
    const created = await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name, display_name: displayName },
    })
    expect(created.status()).toBe(201)
    try {
      await rememberLastOpenedWorkflow(page, name)
      await page.reload()
      await expect(page.getByTestId('canvas-tab').filter({ hasText: displayName })).toBeVisible()

      // Vue Flow container rendered
      await expect(page.locator('.vue-flow')).toBeVisible()

      // Background dots present (SVG with pattern)
      const bgExists = await page.evaluate(() => {
        const bg = document.querySelector('.vue-flow__background')
        return bg !== null && bg.querySelector('pattern') !== null
      })
      expect(bgExists).toBe(true)

      // MiniMap must NOT be present
      const minimapExists = await page.evaluate(() =>
        document.querySelector('.vue-flow__minimap') !== null,
      )
      expect(minimapExists).toBe(false)
    } finally {
      await page.request.delete(`${API_BASE}/api/v1/workflows/${name}`)
    }
  })

  test('shows a non-persistent chooser when no workflow exists', async ({ page }) => {
    await deleteAllWorkflows(page)
    await rememberLastOpenedWorkflow(page, 'obsolete_startup_workflow')
    const workflowPosts: string[] = []
    page.on('request', (request) => {
      if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/v1/workflows') {
        workflowPosts.push(request.url())
      }
    })
    await page.reload()

    await expect(page.getByTestId('canvas-placeholder')).toContainText('No workflow is open')
    await expect(page.getByTestId('canvas-tab')).toHaveCount(0)
    await expect(page.locator('.vue-flow')).toHaveCount(0)
    expect((await (await page.request.get(`${API_BASE}/api/v1/workflows`)).json())).toEqual([])
    expect(workflowPosts).toEqual([])
    await expect.poll(() => page.evaluate(async () => {
      const { useAutoSave } = await import('/src/composables/useAutoSave.ts')
      return useAutoSave().getLastOpenedWorkflow()
    })).toBeNull()

    await page.getByTestId('canvas-placeholder').getByRole('button', { name: 'Open workflow' }).click()
    const openDialog = page.getByTestId('open-workflow-dialog')
    await expect(openDialog).toBeVisible()
    await expect(openDialog.getByText('No workflows match this search.')).toBeVisible()
    await expect(page.getByTestId('workflow-open-submit')).toBeDisabled()
    await openDialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(openDialog).not.toBeVisible()

    await page.getByTestId('canvas-placeholder').getByRole('button', { name: 'New workflow' }).click()
    await expect(page.getByTestId('workflow-dialog')).toBeVisible()
    await page.getByTestId('workflow-dialog-cancel').click()
    await expect(page.getByTestId('workflow-dialog')).not.toBeVisible()
    expect(workflowPosts).toEqual([])
    expect((await (await page.request.get(`${API_BASE}/api/v1/workflows`)).json())).toEqual([])

    const displayName = `First Workflow ${Date.now()}`
    const name = displayName.toLowerCase().replaceAll(' ', '_')
    try {
      await page.getByTestId('canvas-placeholder').getByRole('button', { name: 'New workflow' }).click()
      await page.getByTestId('workflow-display-name-input').fill(displayName)
      await expect(page.getByTestId('workflow-generated-name')).toContainText(name)
      await page.getByTestId('workflow-dialog-submit').click()
      await expect(page.getByTestId('workflow-title')).toContainText(displayName)
      await expect(page.getByTestId('canvas-tab').filter({ hasText: displayName })).toBeVisible()
      expect(workflowPosts).toHaveLength(1)
      const workflows = await (await page.request.get(`${API_BASE}/api/v1/workflows`)).json() as Array<{ id: string; display_name: string }>
      expect(workflows).toMatchObject([{ id: name, display_name: displayName }])

      await page.reload()
      await expect(page.getByTestId('workflow-title')).toContainText(displayName)
      await expect(page.getByTestId('canvas-tab').filter({ hasText: displayName })).toBeVisible()
      await expect(page.getByTestId('canvas-placeholder')).toHaveCount(0)
      expect(workflowPosts).toHaveLength(1)
    } finally {
      await page.request.delete(`${API_BASE}/api/v1/workflows/${name}`)
    }
  })

  test('delayed startup preserves a browsed workflow until its normal details Open', async ({ page, request }) => {
    const suffix = `${test.info().project.name}_${Date.now()}`
    const startupName = `startup_selection_${suffix}`
    const browseName = `browse_selection_${suffix}`
    const startupLabel = `Startup ${suffix}`
    const browseLabel = `Browse ${suffix}`
    let release!: () => void
    const gate = new Promise<void>(resolve => { release = resolve })
    let held = false
    let consumed = false
    const openedRequests: string[] = []
    let cleanup: PromiseSettledResult<APIResponse>[] = []
    try {
      for (const [name, displayName] of [[startupName, startupLabel], [browseName, browseLabel]]) {
        const response = await request.post(`${API_BASE}/api/v1/workflows`, { data: { name, display_name: displayName } })
        expect(response.status()).toBe(201)
      }
      const saved = await request.get(`${API_BASE}/api/v1/workflows/${startupName}`)
      const draft = await request.get(`${API_BASE}/api/v1/workflow-drafts/${startupName}`)
      expect(saved.ok()).toBeTruthy()
      expect(draft.ok()).toBeTruthy()
      const savedBody = await saved.json()
      const draftBody = await draft.json()
      expect(savedBody.info.id ?? savedBody.info.name).toBe(startupName)
      expect(draftBody.workflow_id).toBe(startupName)
      expect(draftBody.base_saved_revision).toBe(savedBody.artifact_hash)
      expect(draftBody.dirty_against_saved).toBe(false)
      expect(savedBody.graph.nodes).toEqual([])
      expect(draftBody.graph.nodes).toEqual([])
      await page.evaluate(async name => {
        const { useAutoSave } = await import('/src/composables/useAutoSave.ts')
        await useAutoSave().clearAutoSave(name)
      }, startupName)
      await rememberLastOpenedWorkflow(page, startupName)
      expect(await page.evaluate(async () => {
        const { useAutoSave } = await import('/src/composables/useAutoSave.ts')
        return useAutoSave().getLastOpenedWorkflow()
      })).toBe(startupName)
      await page.route(`**/api/v1/workflows/${startupName}`, async route => {
        if (route.request().method() !== 'GET' || consumed) return route.continue()
        consumed = true
        held = true
        const response = await route.fetch()
        await gate
        await route.fulfill({ response })
      })
      await page.reload()
      await expect.poll(() => held).toBe(true)
      await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
      await page.getByTestId(`workflow-row-${browseName}`).click()
      await expect(page.getByTestId('workflow-detail-api-name')).toHaveText(browseName)
      release()
      // Prove the saved GET and canonical startup activation actually completed.
      await expect(page.getByTestId('canvas-tab').filter({ hasText: startupLabel })).toBeVisible()
      await expect(page.getByTestId('workflow-title')).toContainText(startupLabel)
      await expect(page.getByTestId('workflow-detail-api-name')).toHaveText(browseName)
      page.on('request', request => {
        if (request.method() === 'GET') openedRequests.push(new URL(request.url()).pathname)
      })
      await page.getByTestId('workflow-open-btn').click()
      await expect(page.getByTestId('workflow-title')).toContainText(browseLabel)
      expect(openedRequests).toContain(`/api/v1/workflows/${browseName}`)
      expect(openedRequests).toContain(`/api/v1/workflow-drafts/${browseName}`)
      expect(openedRequests).not.toContain(`/api/v1/workflows/${startupName}`)
    } finally {
      release()
      cleanup = await Promise.allSettled([startupName, browseName].map(name => request.delete(`${API_BASE}/api/v1/workflows/${name}`)))
    }
    // A body failure propagates through finally and skips cleanup validation.
    for (const outcome of cleanup) {
      if (outcome.status === 'rejected') throw outcome.reason
      expect(outcome.value.ok()).toBeTruthy()
    }
  })

  test('Create Tool dialog opens and closes', async ({ page }) => {
    // Activate Tools panel
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    await expect(page.locator('[data-testid="create-tool-btn"]')).toBeVisible()

    await page.locator('[data-testid="create-tool-btn"]').click()

    // Dialog opens
    const dialog = page.locator('.p-dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText('Create Tool')).toBeVisible()

    // Name input and type select present
    await expect(page.locator('[data-testid="tool-name-input"]')).toBeVisible()
    await expect(page.locator('[data-testid="tool-type-select"]')).toBeVisible()

    // Create button disabled when name is empty
    const createBtn = page.locator('[data-testid="create-tool-submit"]')
    await expect(createBtn).toBeDisabled()

    // Cancel closes the dialog
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).not.toBeVisible()
  })

  test('search matches real catalog metadata and reveals the selected tool row', async ({ page, request }, testInfo) => {
    const name = `catalog_reveal_${testInfo.project.name}_${Date.now()}`
    const executionPosts: string[] = []
    page.on('request', outgoing => {
      if (outgoing.method() === 'POST' && new URL(outgoing.url()).pathname === '/api/v1/execution/run') {
        executionPosts.push(outgoing.url())
      }
    })
    let created = false
    let primaryFailed = false
    const cleanupErrors: unknown[] = []
    try {
      await page.setViewportSize({ width: 1280, height: 600 })
      expect((await request.post(`${API_BASE}/api/v1/dev/seed`)).ok()).toBeTruthy()
      const catalogResponse = await request.get(`${API_BASE}/api/v1/tools`)
      expect(catalogResponse.ok()).toBeTruthy()
      const catalog = await catalogResponse.json() as ToolMetadata[]
      const seed = catalog.find(tool => tool.name === 'SeedNumbers')
      expect(seed).toBeDefined()
      expect(seed!.tags).toContain('source')
      expect(seed!.categories).toContain('Utilities')
      expect((await request.post(`${API_BASE}/api/v1/workflows`, {
        data: { name, display_name: name },
      })).status()).toBe(201)
      created = true
      const saved = await request.put(`${API_BASE}/api/v1/workflows/${name}`, {
        data: { graph: {
          schema_version: 2, name, display_name: name,
          nodes: [
            { type: 'tool', id: 'source', name: 'Catalog source', tool_name: 'SeedNumbers', parameters: {}, position: [100, 100] },
            { type: 'tool', id: 'other', name: 'Other tool', tool_name: 'IncrementNumbers', parameters: {}, position: [450, 100] },
            {
              type: 'workflow', id: 'nested', name: 'Nested graph', position: [250, 330], bindings: {},
              workflow: {
                schema_version: 2, name: 'nested', display_name: 'Nested graph', nodes: [], edges: [],
                interface: { inputs: [], outputs: [] }, config: { engine: 'direct', execution: 'sequential' },
              },
            },
          ],
          edges: [], interface: { inputs: [], outputs: [] }, config: { engine: 'direct', execution: 'sequential' },
        } },
      })
      expect(saved.ok(), await saved.text()).toBeTruthy()
      const before = await (await request.get(`${API_BASE}/api/v1/workflows/${name}`)).json()
      await page.reload()
      await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
      await page.getByTestId('workflow-search').fill(name)
      const opened = page.waitForResponse(response =>
        new URL(response.url()).pathname === `/api/v1/workflow-drafts/${name}`
        && response.request().method() === 'GET' && response.status() === 200,
      )
      await page.getByTestId(`workflow-row-${name}`).dblclick()
      await opened
      await expect(page.getByTestId('workflow-title')).toContainText(name)
      await expect(page.locator('.vue-flow__node')).toHaveCount(3)
      await page.locator('.dv-tab').filter({ hasText: /^Tools$/ }).click()

      const search = page.getByTestId('tool-search')
      const list = page.getByTestId('tool-list')
      const row = page.getByTestId('tool-item-SeedNumbers')
      await search.fill('Seed Numbrs')
      await expect(row).toBeVisible()
      await expect(row.locator('.tool-list-name')).toHaveText(seed!.display_name)
      for (const query of ['source', 'Utilities']) {
        await search.fill(query)
        await expect(row).toBeVisible()
      }
      await search.fill('nonexistent_tool_xyz_99999')
      await expect(list.locator('.tool-list-item')).toHaveCount(0)
      await search.fill('')
      await expect(list.locator('.tool-list-item')).not.toHaveCount(0)

      // Real wheel input arranges an offscreen row before canvas selection.
      await list.hover()
      await page.mouse.wheel(0, -10000)
      await expect.poll(() => list.evaluate(element => element.scrollTop)).toBe(0)
      await expect.poll(async () => {
        const [item, viewport] = await Promise.all([row.boundingBox(), list.boundingBox()])
        return item !== null && viewport !== null
          && (item.y + item.height <= viewport.y || item.y >= viewport.y + viewport.height)
      }).toBe(true)
      const source = page.locator('.vue-flow__node[data-id="source"]')
      const other = page.locator('.vue-flow__node[data-id="other"]')
      const nested = page.locator('.vue-flow__node[data-id="nested"]')
      const assertRevealed = async () => {
        await expect(row).toHaveAttribute('aria-current', 'true')
        await expect(list.locator('.tool-list-item--selected')).toHaveCount(1)
        await expect.poll(async () => {
          const [item, viewport] = await Promise.all([row.boundingBox(), list.boundingBox()])
          return item !== null && viewport !== null && item.y >= viewport.y - 1
            && item.y + item.height <= viewport.y + viewport.height + 1
            && item.x >= viewport.x - 1 && item.x + item.width <= viewport.x + viewport.width + 1
        }).toBe(true)
      }
      const clearSelection = async () => {
        await page.locator('.vue-flow__pane').click({ position: { x: 10, y: 10 } })
        await expect(list.locator('.tool-list-item--selected')).toHaveCount(0)
      }
      await source.click()
      await assertRevealed()
      await clearSelection()

      const category = page.getByTestId('category-toggle-Utilities')
      await category.click()
      await expect(category).toHaveAttribute('aria-expanded', 'false')
      await search.fill('Increment Numbers')
      await expect(row).toHaveCount(0)
      await source.click()
      await expect(search).toHaveValue('')
      await expect(category).toHaveAttribute('aria-expanded', 'true')
      await assertRevealed()
      await clearSelection()
      await search.fill('Seed Numbrs')
      await source.click()
      await expect(search).toHaveValue('Seed Numbrs')
      await assertRevealed()

      await other.click({ modifiers: ['Shift'] })
      await expect(source).toHaveClass(/selected/)
      await expect(other).toHaveClass(/selected/)
      await expect(list.locator('.tool-list-item--selected')).toHaveCount(0)
      await clearSelection()
      await source.click()
      await assertRevealed()
      await nested.click()
      await expect(nested).toHaveClass(/selected/)
      await expect(list.locator('.tool-list-item--selected')).toHaveCount(0)
      await expect(page.locator('.vue-flow__node')).toHaveCount(3)
      expect((await (await request.get(`${API_BASE}/api/v1/workflows/${name}`)).json()).graph).toEqual(before.graph)
      expect(executionPosts).toEqual([])
    } catch (error) {
      primaryFailed = true
      throw error
    } finally {
      try { await page.goto('about:blank') } catch (error) { cleanupErrors.push(error) }
      if (created) {
        try {
          const deleted = await request.delete(`${API_BASE}/api/v1/workflows/${name}`)
          if (!deleted.ok()) cleanupErrors.push(new Error(`Owned workflow cleanup refused ${deleted.status()}`))
        } catch (error) { cleanupErrors.push(error) }
      }
      if (primaryFailed && cleanupErrors.length) {
        await testInfo.attach('catalog-reveal-cleanup-errors', {
          body: cleanupErrors.map(String).join('\n'), contentType: 'text/plain',
        }).catch(() => undefined)
      }
    }
    if (cleanupErrors.length) throw cleanupErrors[0]
  })

  test('Manage Tools ignores the panel search and exposes environment management', async ({ page }) => {
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    await page.getByTestId('tool-search').fill('Parameter Controls')
    await expect(page.getByTestId('tool-item-ParameterControls')).toBeVisible()
    await expect(page.getByTestId('tool-item-Generate')).toHaveCount(0)

    await page.getByTestId('manage-tools-btn').click()
    const dialog = page.getByTestId('manage-tools-dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText('Generate', { exact: true })).toBeVisible()
    await expect(dialog.getByTestId('tool-env-recreate-ParameterControls')).toBeVisible()

    await dialog.getByTestId('manage-tool-info-ParameterControls').click()
    await expect(dialog.getByTestId('manage-tool-environment-location')).toContainText(
      /wetlands[/\\]environments[/\\]bioimageflow-e2e/,
    )
  })

})
