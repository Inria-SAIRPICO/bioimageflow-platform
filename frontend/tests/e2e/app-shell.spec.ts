import { test, expect, type Page } from '@playwright/test'

const catalogTitles = ['Datasets', 'Tools', 'Workflows']

function catalogGroups(page: Page) {
  return page.locator('.dv-groupview').filter({
    has: page.locator('.tools-panel, .datasets-panel, [data-testid="workflows-panel"]'),
  })
}

async function expectCatalogTabs(page: Page, titles = catalogTitles) {
  await expect(catalogGroups(page)).toHaveCount(1)
  await expect(catalogGroups(page).locator('.dv-tab')).toHaveText(titles)
}

async function togglePanel(page: Page, title: string) {
  await page.getByTestId('app-menubar').getByRole('menuitem', { name: 'View', exact: true }).click()
  await page.getByRole('menuitem', { name: `${title} Panel`, exact: true }).click()
}

test('long workflow titles keep the menu height stable when a canvas opens', { tag: '@critical' }, async ({ page }) => {
  const api = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`
  const suffix = `${test.info().project.name}_${Date.now()}`
  const names = [`menu_short_${suffix}`, `menu_long_${suffix}`]
  const labels = ['Short title', `Long workflow ${'descriptive analysis name '.repeat(12)}${suffix}`]
  for (const [index, name] of names.entries()) {
    const created = await page.request.post(`${api}/workflows`, {
      data: { name, display_name: labels[index] },
    })
    expect(created.status()).toBe(201)
  }
  try {
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    const open = async (index: number) => {
      await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
      await page.getByTestId('workflow-search').fill(names[index]!)
      await page.getByTestId(`workflow-row-${names[index]}`).click()
      await page.getByTestId('workflow-open-btn').click()
      await expect(page.getByTestId('workflow-title')).toHaveText(labels[index]!)
    }
    await open(0)
    const menu = page.getByTestId('app-menubar')
    const before = await menu.boundingBox()
    expect(before).not.toBeNull()
    await open(1)
    await expect.poll(async () => (await menu.boundingBox())!.height).toBe(before!.height)
    await expect(page.getByTestId('workflow-title')).toHaveAttribute('title', labels[1]!)
  } finally {
    for (const name of names) await page.request.delete(`${api}/workflows/${name}`)
  }
})

test.describe('app shell', () => {
  test('renders Dockview layout with ordered catalog tabs and Workflows selected', { tag: '@critical' }, async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await expect(page.locator('.dockview-theme-light')).toBeVisible()
    await expect(page.locator('[data-testid="app-menubar"]')).toBeVisible()
    await expect(page.locator('.dv-tab').filter({ hasText: /^Node Data$/ })).toBeVisible()
    await expectCatalogTabs(page)
    await expect(catalogGroups(page).locator('.dv-active-tab')).toHaveText('Workflows')
    await expect(page.getByTestId('workflows-panel')).toBeVisible()

    // Verify all 5 menu items
    const menubar = page.locator('[data-testid="app-menubar"]')
    for (const label of ['Workflow', 'Edit', 'Execution', 'View', 'Help']) {
      await expect(
        menubar.getByRole('menuitem', { name: label, exact: true }),
      ).toBeVisible()
    }
  })

  test('reopened catalog panels keep their shared group and tab order', { tag: '@critical' }, async ({ page }) => {
    await page.goto('/')
    await expectCatalogTabs(page)
    const initialGroupCount = await page.locator('.dv-groupview').count()

    for (const title of catalogTitles) {
      await togglePanel(page, title)
      await expectCatalogTabs(page, catalogTitles.filter(other => other !== title))
      await togglePanel(page, title)
      await expectCatalogTabs(page)
      await expect(page.locator('.dv-groupview')).toHaveCount(initialGroupCount)
    }

    // Recreate the group after closing every tab, with each possible first panel.
    for (const order of [catalogTitles, ['Tools', 'Workflows', 'Datasets'], ['Workflows', 'Datasets', 'Tools']]) {
      for (const title of catalogTitles) {
        const tab = catalogGroups(page).locator('.dv-tab').filter({ hasText: new RegExp(`^${title}$`) })
        await tab.hover()
        await tab.locator('.dv-default-tab-action').click()
        await expect(tab).toHaveCount(0)
      }
      await expect(page.locator('.dv-groupview')).toHaveCount(initialGroupCount - 1)

      const reopened = new Set<string>()
      for (const title of order) {
        await togglePanel(page, title)
        reopened.add(title)
        await expectCatalogTabs(page, catalogTitles.filter(candidate => reopened.has(candidate)))
        await expect(page.locator('.dv-groupview')).toHaveCount(initialGroupCount)
      }
    }
  })

  test('resizes, reorders and reopens dock panels within the session', async ({ page }) => {
    await page.goto('/')
    const dock = page.locator('.dockview-theme-light')
    await expect(dock).toBeVisible()
    // Datasets remains in the sidebar group while Tools is closed and reopened.
    const sidebarGroup = page.locator('.dv-groupview').filter({
      has: page.locator('.dv-tab').filter({ hasText: /^Datasets$/ }),
    })
    await expect(sidebarGroup).toHaveCount(1)
    const toolsTab = page.locator('.dv-tab').filter({ hasText: /^Tools$/ })
    const workflowsTab = sidebarGroup.locator('.dv-tab').filter({ hasText: /^Workflows$/ })
    await toolsTab.click()
    const before = await sidebarGroup.boundingBox()
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
    await expect.poll(async () => (await sidebarGroup.boundingBox())!.width).toBeGreaterThan(before!.width + 50)

    const tabTitles = sidebarGroup.locator('.dv-tabs-container > .dv-tab .dv-default-tab-content')
    const initialOrder = await tabTitles.allTextContents()
    expect(initialOrder).toContain('Tools')
    expect(initialOrder).toContain('Workflows')
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
