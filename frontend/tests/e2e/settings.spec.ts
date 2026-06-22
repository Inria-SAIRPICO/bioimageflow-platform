import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

test.describe('Settings Panel', () => {
  test.describe.configure({ mode: 'serial' })

  async function openSettings(page: Page) {
    await page
      .locator('[data-testid="app-menubar"]')
      .getByRole('menuitem', { name: 'Edit', exact: true })
      .click()
    await page
      .getByRole('menuitem', { name: 'Preferences...', exact: true })
      .click()
  }

  test('opens via Edit > Preferences... and shows the four tabs', async ({
    page,
  }) => {
    await page.goto('/')
    await expect(page.locator('[data-testid="app-menubar"]')).toBeVisible()

    await openSettings(page)

    const dialog = page.locator('[data-testid="settings-panel"]')
    await expect(dialog).toBeVisible()
    for (const label of ['External Editor', 'Napari', 'Execution', 'Storage']) {
      await expect(dialog.getByText(label, { exact: true })).toBeVisible()
    }
  })

  test('execution settings show current runtime summary without stale controls', async ({
    page,
  }) => {
    await page.goto('/')
    await openSettings(page)
    const dialog = page.locator('[data-testid="settings-panel"]')
    await expect(dialog).toBeVisible()

    await dialog.getByText('Execution', { exact: true }).click()

    await expect(dialog.locator('[data-testid="execution-backend-value"]')).toBeVisible()
    await expect(dialog.locator('[data-testid="execution-scheduling-value"]')).toBeVisible()
    await expect(dialog).not.toContainText('Parsl')
    await expect(dialog.locator('[data-testid="cache-unlimited-checkbox"]')).toHaveCount(0)
    await expect(
      dialog.locator('[data-testid="cache-max-executions-input"]'),
    ).toHaveCount(0)
    await expect(dialog.locator('[data-testid="cache-max-age-input"]')).toHaveCount(0)
  })
})
