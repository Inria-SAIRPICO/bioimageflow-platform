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
})
