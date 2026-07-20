import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

async function deleteAllWorkflows(page: Page) {
  const response = await page.request.get(`${API_BASE}/api/v1/workflows`)
  for (const workflow of await response.json() as Array<{ name: string }>) {
    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflow.name}`)
  }
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
  })

  test('Canvas panel has dot grid background and no minimap', async ({ page }) => {
    const name = `canvas_grid_${Date.now()}`
    const displayName = `Canvas Grid ${name}`
    const created = await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name, display_name: displayName },
    })
    expect(created.status()).toBe(201)
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
    await page.request.delete(`${API_BASE}/api/v1/workflows/${name}`)
  })

  test('shows a non-persistent chooser when no workflow exists', async ({ page }) => {
    await deleteAllWorkflows(page)
    await page.reload()

    await expect(page.getByTestId('canvas-placeholder')).toContainText('No workflow is open')
    await expect(page.getByTestId('canvas-tab')).toHaveCount(0)
    await expect(page.locator('.vue-flow')).toHaveCount(0)
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

  test('search filters tool list to empty on nonsense query', async ({ page }) => {
    // Activate Tools panel
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()

    const searchInput = page.locator('[data-testid="tool-search"]')
    await expect(searchInput).toBeVisible()
    await searchInput.fill('nonexistent_tool_xyz_99999')

    // TreeTable body should have no meaningful data rows.
    // PrimeVue TreeTable may render an empty-state row, so check
    // that no row contains tool-specific content.
    const toolNameCells = page.locator('.p-treetable-tbody .tool-name-cell')
    await expect(toolNameCells).toHaveCount(0)
  })

})
