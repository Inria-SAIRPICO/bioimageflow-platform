import { test, expect } from '@playwright/test'

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

    // TreeTable headers rendered
    const headers = page.locator('.p-treetable-thead th')
    await expect(headers).toHaveCount(5)
  })

  test('Tools Panel fetches tools from backend successfully', async ({ page }) => {
    // The tools API call already happened during mount.
    // Verify the data loaded by checking the store via evaluate.
    const toolsLoaded = await page.evaluate(async () => {
      const res = await fetch('/api/v1/tools')
      return { status: res.status, isArray: Array.isArray(await res.json()) }
    })
    expect(toolsLoaded.status).toBe(200)
    expect(toolsLoaded.isArray).toBe(true)
  })

  test('Canvas panel has dot grid background and no minimap', async ({ page }) => {
    // Canvas tab visible
    await expect(page.locator('.dv-tab').filter({ hasText: 'Canvas' })).toBeVisible()

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
  })

  test('canvas starts empty with no nodes', async ({ page }) => {
    await expect(page.locator('.vue-flow')).toBeVisible()
    const nodes = page.locator('.vue-flow__node')
    await expect(nodes).toHaveCount(0)
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

  test('global font is sans-serif, not browser default', async ({ page }) => {
    const fontFamily = await page.evaluate(() =>
      getComputedStyle(document.body).fontFamily,
    )
    expect(fontFamily).toContain('apple-system')
    expect(fontFamily).toContain('sans-serif')
  })

  test('primeicons CSS is loaded', async ({ page }) => {
    const iconFontLoaded = await page.evaluate(() => {
      const icon = document.querySelector('[class*="pi-"]')
      if (!icon) return false
      return getComputedStyle(icon).fontFamily.includes('primeicons')
    })
    expect(iconFontLoaded).toBe(true)
  })
})
