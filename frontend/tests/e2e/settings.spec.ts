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

  test('Image Viewers explains a changed legacy interpreter and uses application dialogs', async ({ page }) => {
    await page.route('**/api/v1/napari/environments', route => route.fulfill({ json: {
      revision: 1,
      environments: [{
        id: '68ff94c5-b649-4dc5-9d98-605e82736e3b', registration_order: 0,
        name: 'Old napari', ownership: 'managed', kind: 'conda', root: '/old/napari',
        interpreter: '/old/napari/bin/python', interpreter_identity: '/old/napari/bin/python',
        interpreter_fingerprint: 'old-fingerprint', launch: { strategy: 'wetlands-managed', argv_prefix: ['/old/napari/bin/python'] },
        managed: { wetlands_name: 'napari', installation_generation: 'f5f7bc30-9065-4f40-a88f-e7ee4842d7f1', recipe: { source: 'adopted' } },
        state: 'replaced', last_error: 'The Python executable at the saved environment path changed since registration.',
        inventory: null,
      }],
      default_environment_id: null, filename_rules: [], operations: [],
    } }))
    await page.route('**/api/v1/napari/status?environment_id=*', route => route.fulfill({ status: 503, json: { detail: 'Unavailable' } }))
    await page.goto('/')
    await openSettings(page)
    const dialog = page.locator('[data-testid="settings-panel"]')
    await dialog.getByText('Image Viewers', { exact: true }).click()
    const section = dialog.locator('[data-testid="image-viewers-section"]')

    await expect(section).toContainText('previous package check may no longer apply')
    await expect(section).toContainText('Create a napari environment')
    await expect(section).toContainText('Reader plugin ID (optional)')
    await expect(section.getByRole('button', { name: 'Locate environment' })).toHaveCount(0)
    await expect(section.getByRole('button', { name: 'Create modified copy' })).toHaveCount(0)
    await expect(section.getByRole('button', { name: 'Test', exact: true })).toHaveCount(0)
    await expect(section.getByRole('heading', { name: 'Viewing requirements' })).toHaveCount(0)
    await expect(section.locator('select')).toHaveCount(0)
    await expect(section.getByRole('combobox', { name: 'Default environment' })).toBeVisible()

    await section.getByText('Details', { exact: true }).click()
    await section.getByRole('button', { name: 'Rename' }).click()
    const rename = page.getByRole('dialog', { name: 'Rename napari environment' })
    await expect(rename).toBeVisible()
    await expect(rename.getByLabel('Environment name')).toHaveValue('Old napari')
    await rename.getByRole('button', { name: 'Cancel' }).click()

    await section.getByRole('button', { name: 'Forget', exact: true }).click()
    const forget = page.getByRole('dialog', { name: 'Forget napari environment' })
    await expect(forget).toContainText('will not be registered automatically again')
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
