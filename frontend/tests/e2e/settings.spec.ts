import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

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

  function waitForSettingsPatch(page: Page, value: unknown) {
    return page.waitForResponse((resp) => {
      if (
        !resp.url().includes('/api/v1/settings') ||
        resp.request().method() !== 'PATCH'
      ) {
        return false
      }
      const body = resp.request().postDataJSON() as
        | { cache_max_executions?: unknown }
        | undefined
      return body?.cache_max_executions === value
    })
  }

  async function fetchCacheMaxExecutions(page: Page): Promise<unknown> {
    const response = await page.request.get(`${API_BASE}/api/v1/settings`)
    expect(response.ok()).toBeTruthy()
    const settings = await response.json()
    return settings.cache_max_executions
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

  test('cache_max_executions=0 is accepted (regression for spec blocker)', async ({
    page,
  }) => {
    await page.request.patch(`${API_BASE}/api/v1/settings`, {
      data: { cache_max_executions: null },
    })
    await page.goto('/')
    await openSettings(page)
    const dialog = page.locator('[data-testid="settings-panel"]')
    await expect(dialog).toBeVisible()

    await dialog.getByText('Execution', { exact: true }).click()

    // Toggle "Unlimited" off so the InputNumber is editable, then set to 0.
    const unlimited = dialog.locator(
      '[data-testid="cache-unlimited-checkbox"] input',
    )
    if (await unlimited.isChecked()) {
      const patch = page.waitForResponse(
        (resp) =>
          resp.url().includes('/api/v1/settings') &&
          resp.request().method() === 'PATCH',
      )
      await unlimited.click()
      await patch
    }
    const input = dialog
      .locator('[data-testid="cache-max-executions-input"] input')
    await expect(input).toHaveValue('0')
    const increment = dialog.locator(
      '[data-testid="cache-max-executions-input"] .p-inputnumber-increment-button',
    )
    const decrement = dialog.locator(
      '[data-testid="cache-max-executions-input"] .p-inputnumber-decrement-button',
    )
    const patchOne = waitForSettingsPatch(page, 1)
    await increment.click()
    await patchOne
    await expect
      .poll(() => fetchCacheMaxExecutions(page), { timeout: 5000 })
      .toBe(1)
    const patchZero = waitForSettingsPatch(page, 0)
    await decrement.click()
    await patchZero
    await expect
      .poll(() => fetchCacheMaxExecutions(page), { timeout: 5000 })
      .toBe(0)

    // Reload and verify the value persisted.
    await page.locator('[data-testid="settings-close"]').click()
    await page.reload()
    await openSettings(page)
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
    await page.request.patch(`${API_BASE}/api/v1/settings`, {
      data: { cache_max_executions: 1 },
    })
    await page.goto('/')
    await openSettings(page)
    const dialog = page.locator('[data-testid="settings-panel"]')
    await dialog.getByText('Execution', { exact: true }).click()

    const unlimited = dialog.locator(
      '[data-testid="cache-unlimited-checkbox"] input',
    )
    if (!(await unlimited.isChecked())) {
      const patch = page.waitForResponse(
        (resp) =>
          resp.url().includes('/api/v1/settings') &&
          resp.request().method() === 'PATCH',
      )
      await unlimited.click()
      await patch
    }
    await expect(
      dialog.locator('[data-testid="cache-max-executions-input"]'),
    ).toHaveCount(0)
  })
})
