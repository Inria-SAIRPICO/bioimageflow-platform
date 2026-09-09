import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import { CAMPAIGN_ANNOTATION } from '../../src/test-utils/campaignScope'

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

  test('opens via Edit > Preferences... and shows the settings tabs', async ({
    page,
  }) => {
    let releaseSettings!: () => void
    const settingsReleased = new Promise<void>((resolve) => {
      releaseSettings = resolve
    })
    await page.route('**/api/v1/settings', async (route) => {
      if (route.request().method() === 'GET') await settingsReleased
      await route.continue()
    })
    await page.goto('/')
    await expect(page.locator('[data-testid="app-menubar"]')).toBeVisible()

    await openSettings(page)

    const dialog = page.locator('[data-testid="settings-panel"]')
    await expect(dialog).toBeVisible()
    await expect(dialog.locator('[data-testid="settings-loading"]')).toBeVisible()
    releaseSettings()
    await expect(dialog.locator('[data-testid="settings-tabs"]')).toBeVisible()
    for (const label of ['External Editor', 'Image Viewers', 'Execution', 'Display', 'Storage', 'OMERO']) {
      await expect(dialog.getByText(label, { exact: true })).toBeVisible()
    }
  })

  test('Image Viewers explains Fiji setup and links to the official download', async ({ page }) => {
    await page.goto('/')
    await openSettings(page)
    const dialog = page.locator('[data-testid="settings-panel"]')

    await dialog.getByText('Image Viewers', { exact: true }).click()

    const section = dialog.locator('[data-testid="image-viewers-section"]')
    await expect(section).toContainText('Fiji is installed separately')
    await expect(section.getByRole('link', { name: 'Download Fiji' })).toHaveAttribute(
      'href',
      'https://imagej.net/software/fiji/downloads',
    )
    await expect(section.locator('[data-testid="fiji-path-input"]')).toBeVisible()
  })

  test('Display exposes the persisted Node Data page-size preference', async ({ page }) => {
    await page.goto('/')
    await openSettings(page)
    const dialog = page.locator('[data-testid="settings-panel"]')

    await dialog.getByText('Display', { exact: true }).click()

    await expect(dialog.locator('[data-testid="node-data-page-size-setting"]')).toContainText('250')
  })

  test('execution settings show the local runtime summary', async ({
    page,
  }) => {
    await page.goto('/')
    await openSettings(page)
    const dialog = page.locator('[data-testid="settings-panel"]')
    await expect(dialog).toBeVisible()

    await dialog.getByText('Execution', { exact: true }).click()

    await expect(dialog.locator('[data-testid="execution-backend-value"]')).toBeVisible()
    await expect(dialog.locator('[data-testid="execution-scheduling-value"]')).toBeVisible()
    await expect(dialog.locator('[data-testid="cache-unlimited-checkbox"]')).toHaveCount(0)
    await expect(
      dialog.locator('[data-testid="cache-max-executions-input"]'),
    ).toHaveCount(0)
    await expect(dialog.locator('[data-testid="cache-max-age-input"]')).toHaveCount(0)
  })

  test('execution settings show managed-cluster controls', {
    annotation: { type: CAMPAIGN_ANNOTATION, description: 'managed-remote' },
  }, async ({ page }) => {
    test.skip(process.env.BIOIMAGEFLOW_CAMPAIGN_LOCAL === '1', 'Excluded from the local-platform campaign')
    await page.goto('/')
    await openSettings(page)
    const dialog = page.locator('[data-testid="settings-panel"]')
    await dialog.getByText('Execution', { exact: true }).click()

    await expect(dialog).toContainText('Managed remote clusters')
    await expect(dialog).toContainText('Secrets are never saved')
    await expect(dialog.getByRole('button', { name: 'Slurm example' })).toBeVisible()
    await expect(dialog).not.toContainText('Trusted Parsl configuration factories')
  })

  test('OMERO instance cards keep fields and actions visible without horizontal scrolling', async ({
    page,
  }) => {
    await page.goto('/')
    await openSettings(page)
    const dialog = page.locator('[data-testid="settings-panel"]')
    await expect(dialog.locator('[data-testid="settings-tabs"]')).toBeVisible()

    await dialog.getByText('OMERO', { exact: true }).click()
    await dialog.locator('[data-testid="omero-add-button"]').click()

    const section = dialog.locator('[data-testid="omero-section"]')
    const card = section.locator('[data-testid="omero-card-0"]')
    await expect(card).toBeVisible()
    for (const label of ['Name', 'Host', 'Port', 'Username', 'Password']) {
      await expect(card.getByLabel(label, { exact: true })).toBeVisible()
    }
    for (const action of [
      'Save OMERO instance',
      'Duplicate OMERO instance',
      'Remove OMERO instance',
    ]) {
      await expect(card.getByRole('button', { name: action })).toBeVisible()
    }
    expect(await section.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(
      true,
    )

    await page.setViewportSize({ width: 480, height: 800 })
    await expect(dialog).toBeVisible()
    await expect(card).toBeVisible()
    expect(await section.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(
      true,
    )

    const nameBox = await card.getByLabel('Name', { exact: true }).boundingBox()
    const hostBox = await card.getByLabel('Host', { exact: true }).boundingBox()
    expect(nameBox).not.toBeNull()
    expect(hostBox).not.toBeNull()
    expect(hostBox!.y).toBeGreaterThan(nameBox!.y)
  })
})
