import { test, expect } from '@playwright/test'

test.describe('app shell', () => {
  test('renders Dockview layout with menu bar and panels', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await expect(page.locator('.dockview-theme-light')).toBeVisible()
    await expect(page.locator('[data-testid="app-menubar"]')).toBeVisible()
    await expect(page.locator('.dv-tab').filter({ hasText: /^Node Data$/ })).toBeVisible()

    // Verify all 5 menu items
    const menubar = page.locator('[data-testid="app-menubar"]')
    for (const label of ['Workflow', 'Edit', 'Execution', 'View', 'Help']) {
      await expect(
        menubar.getByRole('menuitem', { name: label, exact: true }),
      ).toBeVisible()
    }
  })

  test('View menu toggles panel visibility', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.dockview-theme-light')).toBeVisible()

    // Tools tab should be visible initially
    const toolsTab = page.locator('.dv-tab').filter({ hasText: 'Tools' })
    await expect(toolsTab).toHaveCount(1, { timeout: 2000 })

    // Toggle Tools off via View menu
    await page
      .locator('[data-testid="app-menubar"]')
      .getByRole('menuitem', { name: 'View', exact: true })
      .click()
    await page.getByRole('menuitem', { name: 'Tools Panel', exact: true }).click()
    await expect(toolsTab).toHaveCount(0, { timeout: 2000 })

    // Toggle Tools back on
    await page
      .locator('[data-testid="app-menubar"]')
      .getByRole('menuitem', { name: 'View', exact: true })
      .click()
    await page.getByRole('menuitem', { name: 'Tools Panel', exact: true }).click()
    await expect(toolsTab).toHaveCount(1, { timeout: 2000 })
  })

  test('resizes, reorders and reopens dock panels within the session', async ({ page }) => {
    await page.goto('/')
    const dock = page.locator('.dockview-theme-light')
    await expect(dock).toBeVisible()
    const toolsTab = page.locator('.dv-tab').filter({ hasText: /^Tools$/ })
    const workflowsTab = page.locator('.dv-tab').filter({ hasText: /^Workflows$/ })
    await toolsTab.click()
    const toolsGroup = page.locator('.dv-groupview').filter({ has: toolsTab })
    const before = await toolsGroup.boundingBox()
    expect(before).not.toBeNull()
    const sashes = dock.locator('.dv-sash.dv-enabled')
    const sashIndex = await sashes.evaluateAll((elements, edge) => elements.findIndex(element => {
      const rect = element.getBoundingClientRect()
      return rect.width <= 8 && rect.height > 40
        && Math.abs(rect.x + rect.width / 2 - edge.x) < 6
        && rect.top < edge.y && rect.bottom > edge.y
    }), { x: before!.x + before!.width, y: before!.y + before!.height / 2 })
    expect(sashIndex).toBeGreaterThanOrEqual(0)
    const sash = await sashes.nth(sashIndex).boundingBox()
    expect(sash).not.toBeNull()
    await page.mouse.move(sash!.x + sash!.width / 2, before!.y + before!.height / 2)
    await page.mouse.down()
    await page.mouse.move(sash!.x + sash!.width / 2 + 80, before!.y + before!.height / 2, { steps: 8 })
    await page.mouse.up()
    await expect.poll(async () => (await toolsGroup.boundingBox())!.width).toBeGreaterThan(before!.width + 50)

    const tabTitles = toolsGroup.locator('.dv-tabs-container > .dv-tab .dv-default-tab-content')
    const initialOrder = await tabTitles.allTextContents()
    expect(initialOrder.indexOf('Tools')).toBeLessThan(initialOrder.indexOf('Workflows'))
    await expect(toolsTab).toHaveAttribute('draggable', 'true')
    const target = await workflowsTab.boundingBox()
    expect(target).not.toBeNull()
    await toolsTab.dragTo(workflowsTab, {
      sourcePosition: { x: 20, y: target!.height / 2 },
      targetPosition: { x: target!.width - 5, y: target!.height / 2 },
    })
    const reordered = initialOrder.filter(title => title !== 'Tools')
    reordered.splice(reordered.indexOf('Workflows') + 1, 0, 'Tools')
    await expect.poll(() => tabTitles.allTextContents()).toEqual(reordered)
    await toolsTab.click()
    await expect(page.locator('.tools-panel')).toBeVisible()
    await toolsTab.locator('.dv-default-tab-action').click()
    await expect(toolsTab).toHaveCount(0)
    await workflowsTab.click()
    await expect(page.getByTestId('workflows-panel')).toBeVisible()

    await page.getByTestId('app-menubar').getByRole('menuitem', { name: 'View', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Tools Panel', exact: true }).click()
    await expect(toolsTab).toHaveCount(1)
    await toolsTab.click()
    const tools = page.locator('.tools-panel')
    await expect(tools).toBeVisible()
    await expect(async () => {
      const bounds = await dock.boundingBox()
      const panel = await tools.boundingBox()
      expect(bounds).not.toBeNull()
      expect(panel).not.toBeNull()
      expect(panel!.width).toBeGreaterThan(200)
      expect(panel!.height).toBeGreaterThan(100)
      expect(panel!.x).toBeGreaterThanOrEqual(bounds!.x - 1)
      expect(panel!.y).toBeGreaterThanOrEqual(bounds!.y - 1)
      expect(panel!.x + panel!.width).toBeLessThanOrEqual(bounds!.x + bounds!.width + 1)
      expect(panel!.y + panel!.height).toBeLessThanOrEqual(bounds!.y + bounds!.height + 1)
    }).toPass()
    await expect(page.getByTestId('app-menubar')).toBeVisible()
  })
})
