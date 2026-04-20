import { test, expect } from '@playwright/test'

test.describe('app shell', () => {
  test('renders Dockview layout with menu bar and panels', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await expect(page.locator('.dockview-theme-light')).toBeVisible()
    await expect(page.locator('[data-testid="app-menubar"]')).toBeVisible()

    // Verify all 5 menu items
    const menubar = page.locator('[data-testid="app-menubar"]')
    for (const label of ['Workflow', 'Edit', 'Execution', 'View', 'Help']) {
      await expect(menubar.getByText(label)).toBeVisible()
    }
  })

  test('View menu toggles panel visibility', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.dockview-theme-light')).toBeVisible()

    // Tools tab should be visible initially
    const toolsTab = page.locator('.dv-tab').filter({ hasText: 'Tools' })
    await expect(toolsTab).toHaveCount(1, { timeout: 2000 })

    // Toggle Tools off via View menu
    await page.locator('[data-testid="app-menubar"]').getByText('View').click()
    await page.getByText('Tools Panel').click()
    await expect(toolsTab).toHaveCount(0, { timeout: 2000 })

    // Toggle Tools back on
    await page.locator('[data-testid="app-menubar"]').getByText('View').click()
    await page.getByText('Tools Panel').click()
    await expect(toolsTab).toHaveCount(1, { timeout: 2000 })
  })
})
