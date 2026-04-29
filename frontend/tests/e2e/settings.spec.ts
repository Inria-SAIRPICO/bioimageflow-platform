import { test, expect } from '@playwright/test'

test.describe('Settings Panel', () => {
  test('opens via Edit > Preferences... and shows the four tabs', async ({
    page,
  }) => {
    await page.goto('/')
    await expect(page.locator('[data-testid="app-menubar"]')).toBeVisible()

    await page.locator('[data-testid="app-menubar"]').getByText('Edit').click()
    await page.getByText('Preferences...').click()

    const dialog = page.locator('[data-testid="settings-panel"]')
    await expect(dialog).toBeVisible()
    for (const label of ['External Editor', 'Napari', 'Execution', 'Storage']) {
      await expect(dialog.getByText(label, { exact: true })).toBeVisible()
    }
  })

  test('cache_max_executions=0 is accepted (regression for spec blocker)', async ({
    page,
  }) => {
    await page.goto('/')
    await page.locator('[data-testid="app-menubar"]').getByText('Edit').click()
    await page.getByText('Preferences...').click()
    const dialog = page.locator('[data-testid="settings-panel"]')
    await expect(dialog).toBeVisible()

    await dialog.getByText('Execution', { exact: true }).click()

    // Toggle "Unlimited" off so the InputNumber is editable, then set to 0.
    const unlimited = dialog.locator(
      '[data-testid="cache-unlimited-checkbox"] input',
    )
    if (await unlimited.isChecked()) {
      await unlimited.click()
    }
    const input = dialog
      .locator('[data-testid="cache-max-executions-input"] input')
    await input.fill('0')
    await input.press('Tab')

    // Reload and verify the value persisted.
    await page.locator('[data-testid="settings-close"]').click()
    await page.reload()
    await page.locator('[data-testid="app-menubar"]').getByText('Edit').click()
    await page.getByText('Preferences...').click()
    await dialog.getByText('Execution', { exact: true }).click()

    const reopenedUnlimited = dialog.locator(
      '[data-testid="cache-unlimited-checkbox"] input',
    )
    await expect(reopenedUnlimited).not.toBeChecked()
    const reopenedInput = dialog.locator(
      '[data-testid="cache-max-executions-input"] input',
    )
    await expect(reopenedInput).toHaveValue('0')
  })

  test('toggling Unlimited disables the input and persists null', async ({
    page,
  }) => {
    await page.goto('/')
    await page.locator('[data-testid="app-menubar"]').getByText('Edit').click()
    await page.getByText('Preferences...').click()
    const dialog = page.locator('[data-testid="settings-panel"]')
    await dialog.getByText('Execution', { exact: true }).click()

    const unlimited = dialog.locator(
      '[data-testid="cache-unlimited-checkbox"] input',
    )
    if (!(await unlimited.isChecked())) {
      await unlimited.click()
    }
    await expect(
      dialog.locator('[data-testid="cache-max-executions-input"]'),
    ).toHaveCount(0)
  })
})
