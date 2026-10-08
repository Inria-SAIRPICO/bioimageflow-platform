import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { CAMPAIGN_ANNOTATION } from '../../src/test-utils/campaignScope'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`

async function currentSettings(page: Page): Promise<Record<string, unknown>> {
  const response = await page.request.get(`${API}/settings`)
  expect(response.status()).toBe(200)
  return await response.json() as Record<string, unknown>
}

async function settleSettingsTest(operations: (() => Promise<unknown>)[]): Promise<unknown[]> {
  const failures: unknown[] = []
  for (const operation of operations) {
    try { await operation() } catch (error) { failures.push(error) }
  }
  return failures
}

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
  }, testInfo) => {
    const before = await currentSettings(page)
    const failure = 'Controlled first settings load failure'
    let getCount = 0
    let releaseSettings!: () => void
    const settingsReleased = new Promise<void>((resolve) => {
      releaseSettings = resolve
    })
    await page.route('**/api/v1/settings', async (route) => {
      if (route.request().method() === 'GET') {
        getCount++
        if (getCount === 1) {
          await settingsReleased
          await route.fulfill({ status: 503, json: { error: 'settings_unavailable', detail: failure } })
          return
        }
      }
      await route.continue()
    })
    let mainFailed = false
    let cleanupFailures: unknown[] = []
    try {
      await page.goto('/')
      await expect(page.locator('[data-testid="app-menubar"]')).toBeVisible()
      await openSettings(page)
      const dialog = page.locator('[data-testid="settings-panel"]')
      await expect(dialog).toBeVisible()
      await expect(dialog.locator('[data-testid="settings-loading"]')).toBeVisible()
      const rejected = page.waitForResponse(response =>
        new URL(response.url()).pathname === '/api/v1/settings' && response.request().method() === 'GET',
      )
      releaseSettings()
      expect((await rejected).status()).toBe(503)
      await expect(dialog.getByTestId('settings-loading')).toHaveCount(0)
      await expect(page.locator('.p-toast')).toContainText(failure)
      expect(getCount).toBe(1)
      expect(await currentSettings(page)).toEqual(before)
      await dialog.getByTestId('settings-close').click()
      await expect(dialog).not.toBeVisible()
      const recovered = page.waitForResponse(response =>
        new URL(response.url()).pathname === '/api/v1/settings' && response.request().method() === 'GET',
      )
      await openSettings(page)
      const response = await recovered
      expect(response.status()).toBe(200)
      expect(await response.json()).toEqual(before)
      await expect(dialog.getByTestId('settings-loading')).toHaveCount(0)
      await expect(dialog.getByTestId('settings-tabs')).toBeVisible()
      for (const label of ['External Editor', 'Image Viewers', 'Execution', 'Display', 'Storage', 'OMERO']) {
        await expect(dialog.getByText(label, { exact: true })).toBeVisible()
      }
      expect(getCount).toBe(2)
      expect(await currentSettings(page)).toEqual(before)
      await dialog.getByTestId('settings-close').click()
      await openSettings(page)
      await expect(dialog.getByTestId('settings-tabs')).toBeVisible()
      expect(getCount).toBe(2)
      expect(await currentSettings(page)).toEqual(before)
    } catch (error) {
      mainFailed = true
      throw error
    } finally {
      releaseSettings()
      cleanupFailures = await settleSettingsTest([
        () => page.unrouteAll({ behavior: 'wait' }),
        () => page.goto('about:blank'),
      ])
      if (cleanupFailures.length) {
        await settleSettingsTest([() => testInfo.attach('settings-cleanup-errors', {
          body: cleanupFailures.map(String).join('\n'), contentType: 'text/plain',
        })])
      }
    }
    if (!mainFailed && cleanupFailures.length) throw cleanupFailures[0]
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

  test('Image Viewers manages an adopted installation and uses application dialogs', async ({ page }) => {
    await page.route('**/api/v1/napari/environments', route => route.fulfill({ json: {
      revision: 1,
      environments: [{
        id: '68ff94c5-b649-4dc5-9d98-605e82736e3b', registration_order: 0,
        name: 'Old napari', ownership: 'managed', kind: 'conda', root: '/old/napari',
        interpreter: '/old/napari/bin/python', interpreter_identity: '/old/napari/bin/python',
        launch: { strategy: 'wetlands-managed', argv_prefix: ['/old/napari/bin/python'] },
        managed: { wetlands_name: 'napari', installation_generation: 'f5f7bc30-9065-4f40-a88f-e7ee4842d7f1', recipe: { source: 'adopted' } },
        state: 'ready', last_error: null,
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

  test('Image Viewers saves an ordered desktop settings journey and restores it after reopen', async ({ page }) => {
    type Environment = Record<string, any>
    type Rule = { id: string; pattern: string; environment_id: string; enabled: boolean; reader_id: string | null }
    const environments: Environment[] = []
    const rules: Rule[] = []
    const operations: Record<string, any>[] = []
    const requests: { path: string; method: string; body: any }[] = []
    let revision = 0
    let defaultId: string | null = null
    const snapshot = () => ({ revision, environments, default_environment_id: defaultId, filename_rules: rules, operations })
    const makeEnvironment = (name: string, path: string, ownership: 'external' | 'managed', id: string): Environment => ({
      id, registration_order: environments.length, name, ownership, kind: ownership === 'managed' ? 'conda' : 'venv',
      root: path, interpreter: `${path}/bin/python`, interpreter_identity: `${path}/bin/python`,
      launch: { strategy: ownership === 'managed' ? 'wetlands-managed' : 'direct', argv_prefix: [`${path}/bin/python`] },
      managed: ownership === 'managed' ? {
        wetlands_name: `napari-${id}`, installation_generation: null,
        recipe: { source: 'managed', preset: 'default', python: '==3.12.*', napari: '0.9.1', qt: 'PyQt6', requested_packages: [], channels: ['conda-forge'] },
      } : null,
      state: ownership === 'managed' ? 'failed' : 'ready', inventory: null,
    })
    await page.route('**/api/v1/napari/**', async route => {
      const url = new URL(route.request().url())
      const path = url.pathname
      const method = route.request().method()
      if (!path.startsWith('/api/v1/napari/environments') && !path.startsWith('/api/v1/napari/environment-settings') && path !== '/api/v1/napari/status') {
        await route.continue()
        return
      }
      const body = route.request().postDataJSON() ?? null
      requests.push({ path, method, body })
      if (path === '/api/v1/napari/status') {
        await route.fulfill({ json: { status: 'stopped', running: false } })
      } else if (path === '/api/v1/napari/environments' && method === 'GET') {
        await route.fulfill({ json: snapshot() })
      } else if (path === '/api/v1/napari/environments' && method === 'POST') {
        if (environments.some(item => item.name.toLowerCase() === body.name.toLowerCase())) {
          await route.fulfill({ status: 409, json: { error: 'duplicate_environment_name', detail: 'environment name is already registered' } })
          return
        }
        const environment = makeEnvironment(body.name, body.path, 'external', `00000000-0000-4000-8000-00000000000${environments.length + 1}`)
        environments.push(environment)
        await route.fulfill({ status: 201, json: { revision: ++revision, environment } })
      } else if (path === '/api/v1/napari/environments/managed' && method === 'POST') {
        const environment = makeEnvironment(body.name, 'managed-pending:viewer', 'managed', '00000000-0000-4000-8000-000000000003')
        const operation = { id: '00000000-0000-4000-8000-000000000004', environment_id: environment.id, kind: 'create', state: 'failed', progress: 0, message: 'Setup failed', error: { code: 'napari_provision_failed', detail: 'solver unavailable' } }
        environments.push(environment)
        operations.push(operation)
        revision += 2
        await route.fulfill({ status: 202, json: { revision, environment, operation } })
      } else if (path.endsWith('/retry') && method === 'POST') {
        const environment = environments.find(item => path.includes(item.id))!
        const operation = { ...operations[0], id: '00000000-0000-4000-8000-000000000005', kind: 'retry' }
        operations.push(operation)
        revision += 2
        await route.fulfill({ status: 202, json: { revision, environment, operation } })
      } else if (path.includes('/operations/') && method === 'GET') {
        const operation = operations.find(item => path.endsWith(item.id))!
        await route.fulfill({ json: { revision, environment: environments.find(item => item.id === operation.environment_id), operation } })
      } else if (path === '/api/v1/napari/environment-settings/default' && method === 'PUT') {
        defaultId = body.environment_id
        await route.fulfill({ json: { ...snapshot(), revision: ++revision } })
      } else if (path === '/api/v1/napari/environment-settings/filename-rules' && method === 'POST') {
        const created = { id: `00000000-0000-4000-8000-00000000001${rules.length + 1}`, pattern: body.mode === 'pattern' ? body.value : `*.${body.value.replace(/^\./, '')}`, environment_id: body.environment_id, enabled: true, reader_id: body.reader_id }
        rules.push(created)
        await route.fulfill({ status: 201, json: { revision: ++revision, rule: created } })
      } else if (path === '/api/v1/napari/environment-settings/filename-rules' && method === 'PUT') {
        rules.splice(0, rules.length, ...body.rules)
        await route.fulfill({ json: { ...snapshot(), revision: ++revision } })
      } else {
        await route.continue()
      }
    })

    await page.goto('/')
    await openSettings(page)
    const dialog = page.locator('[data-testid="settings-panel"]')
    await dialog.getByText('Image Viewers', { exact: true }).click()
    const section = dialog.locator('[data-testid="image-viewers-section"]')
    await expect(section.getByText('No napari environments are registered.')).toBeVisible()

    for (const [name, path] of [['Microscopy', '/viewer with spaces'], ['Labels', '/labels-viewer']]) {
      await section.getByRole('textbox', { name: 'Existing environment name' }).fill(name)
      await section.getByRole('textbox', { name: 'Environment path' }).fill(path)
      await section.getByRole('button', { name: 'Add existing', exact: true }).click()
      await expect(section.getByText(name, { exact: true }).first()).toBeVisible()
    }
    await section.getByRole('combobox', { name: 'Default environment' }).click()
    await page.getByRole('option', { name: 'Microscopy' }).click()
    await expect.poll(() => defaultId).toBe(environments[0]!.id)

    await section.getByRole('textbox', { name: 'Extension or filename pattern' }).fill('.tif')
    await section.getByRole('combobox', { name: 'Preferred environment', exact: true }).click()
    await page.getByRole('option', { name: 'Microscopy' }).last().click()
    await section.getByRole('button', { name: 'Add rule' }).click()
    await expect(section.locator('.rule').first()).toContainText('*.tif')
    await section.getByRole('combobox', { name: 'Filename rule mode' }).click()
    await page.getByRole('option', { name: 'Filename pattern' }).click()
    await section.getByRole('textbox', { name: 'Extension or filename pattern' }).fill('*_labels.tif')
    await section.getByRole('combobox', { name: 'Preferred environment', exact: true }).click()
    await page.getByRole('option', { name: 'Labels' }).last().click()
    await section.getByRole('textbox', { name: 'Reader plugin ID (optional)' }).fill('labels-reader')
    await section.getByRole('button', { name: 'Add rule' }).click()
    await section.locator('.rule').nth(1).locator('button[title="Move rule up"]').click()
    await expect(section.locator('.rule').first()).toContainText('*_labels.tif')
    expect(rules.map(rule => [rule.pattern, rule.environment_id, rule.reader_id])).toEqual([
      ['*_labels.tif', environments[1]!.id, 'labels-reader'], ['*.tif', environments[0]!.id, null],
    ])

    await section.getByRole('textbox', { name: 'Existing environment name' }).fill('microscopy')
    await section.getByRole('textbox', { name: 'Environment path' }).fill('/other-viewer')
    await section.getByRole('button', { name: 'Add existing', exact: true }).click()
    await expect(section.getByRole('alert')).toContainText('environment name is already registered')
    expect(environments).toHaveLength(2)

    await section.getByRole('textbox', { name: 'Managed environment name' }).fill('Managed retry')
    await section.getByRole('button', { name: 'Create environment' }).click()
    await expect(section).toContainText('solver unavailable')
    const managed = section.locator('[data-testid="napari-environment-card-00000000-0000-4000-8000-000000000003"]')
    await managed.getByText('Details').click()
    await expect(managed.getByRole('button', { name: 'Retry' })).toBeVisible()
    await expect(managed.getByRole('button', { name: 'Delete managed installation' })).toBeVisible()
    await expect(managed.getByRole('button', { name: 'Forget' })).toHaveCount(0)
    await managed.getByRole('button', { name: 'Retry' }).click()
    await expect.poll(() => operations.filter(item => item.kind === 'retry').length).toBe(1)
    expect(environments).toHaveLength(3)
    const external = section.locator('[data-testid="napari-environment-card-00000000-0000-4000-8000-000000000001"]')
    await external.getByText('Details').click()
    await expect(external.getByRole('button', { name: 'Forget' })).toBeVisible()
    await expect(external.getByRole('button', { name: 'Delete managed installation' })).toHaveCount(0)

    await dialog.locator('[data-testid="settings-close"]').click()
    await openSettings(page)
    await dialog.getByText('Image Viewers', { exact: true }).click()
    await expect(section.locator('.rule').first()).toContainText('*_labels.tif')
    await expect(section.getByRole('combobox', { name: 'Default environment' })).toContainText('Microscopy')
    await expect(section.locator('[data-testid="napari-environment-card-00000000-0000-4000-8000-000000000003"]')).toContainText('Managed retry')
    expect(requests.some(request => request.path.endsWith('/retry') && request.body.expected_revision > 0)).toBe(true)
  })

  test('Display exposes the persisted Node Data page-size preference', async ({ page }, testInfo) => {
    const before = await currentSettings(page)
    expect(before.node_data_page_size).toBe(250)
    const runtimeRoot = process.env.BIOIMAGEFLOW_E2E_ROOT
    expect(runtimeRoot, 'Playwright must provide its isolated settings root.').toBeTruthy()
    const settingsPath = join(runtimeRoot!, 'settings.json')
    const beforeDisk = JSON.parse(readFileSync(settingsPath, 'utf8')) as Record<string, unknown>
    const failure = 'Controlled page-size update refusal'
    const patches: number[] = []
    let refuse = false
    await page.route('**/api/v1/settings', async route => {
      if (route.request().method() === 'PATCH') {
        const body = route.request().postDataJSON() as { node_data_page_size: number }
        patches.push(body.node_data_page_size)
        expect(Object.keys(body)).toEqual(['node_data_page_size'])
        if (refuse) {
          refuse = false
          await route.fulfill({ status: 422, json: { error: 'validation_error', detail: failure } })
          return
        }
      }
      await route.continue()
    })
    let mainFailed = false
    let cleanupFailures: unknown[] = []
    try {
      await page.goto('/')
      await openSettings(page)
      const dialog = page.getByTestId('settings-panel')
      await dialog.getByText('Display', { exact: true }).click()
      const selector = dialog.getByTestId('node-data-page-size-setting')
      await expect(selector).toContainText(String(before.node_data_page_size))
      async function choose(value: number) {
        const completed = page.waitForResponse(response =>
          new URL(response.url()).pathname === '/api/v1/settings' && response.request().method() === 'PATCH',
        )
        await selector.click()
        await page.getByRole('option', { name: String(value), exact: true }).click()
        return await completed
      }
      const accepted = await choose(50)
      expect(accepted.status()).toBe(200)
      const saved = await currentSettings(page)
      expect(saved).toEqual({ ...before, node_data_page_size: 50 })
      const savedDisk = readFileSync(settingsPath)
      expect(JSON.parse(savedDisk.toString())).toEqual({ ...beforeDisk, node_data_page_size: 50 })
      await expect(selector).toContainText('50')
      refuse = true
      const refused = await choose(100)
      expect(refused.status()).toBe(422)
      expect(await refused.json()).toMatchObject({ error: 'validation_error', detail: failure })
      await expect(page.locator('.p-toast')).toContainText(failure)
      await expect(selector).toContainText('50')
      expect(await currentSettings(page)).toEqual(saved)
      expect(readFileSync(settingsPath)).toEqual(savedDisk)
      const retried = await choose(100)
      expect(retried.status()).toBe(200)
      expect(await currentSettings(page)).toEqual({ ...before, node_data_page_size: 100 })
      expect(JSON.parse(readFileSync(settingsPath, 'utf8'))).toEqual({ ...beforeDisk, node_data_page_size: 100 })
      await expect(selector).toContainText('100')
      expect(patches).toEqual([50, 100, 100])
      await dialog.getByTestId('settings-close').click()
      await openSettings(page)
      await dialog.getByText('Display', { exact: true }).click()
      await expect(selector).toContainText('100')
      await page.reload()
      await openSettings(page)
      await dialog.getByText('Display', { exact: true }).click()
      await expect(selector).toContainText('100')
      expect(await currentSettings(page)).toEqual({ ...before, node_data_page_size: 100 })
      expect(patches).toEqual([50, 100, 100])
    } catch (error) {
      mainFailed = true
      throw error
    } finally {
      cleanupFailures = await settleSettingsTest([
        () => page.unrouteAll({ behavior: 'wait' }),
        () => page.goto('about:blank'),
        async () => {
          const restored = await page.request.patch(`${API}/settings`, { data: { node_data_page_size: before.node_data_page_size } })
          expect(restored.status()).toBe(200)
          expect(await currentSettings(page)).toEqual(before)
          expect(JSON.parse(readFileSync(settingsPath, 'utf8'))).toEqual(beforeDisk)
        },
      ])
      if (cleanupFailures.length) {
        await settleSettingsTest([() => testInfo.attach('settings-cleanup-errors', {
          body: cleanupFailures.map(String).join('\n'), contentType: 'text/plain',
        })])
      }
    }
    if (!mainFailed && cleanupFailures.length) throw cleanupFailures[0]
  })

  test('execution settings show the new-workflow scheduling preference', async ({
    page,
  }) => {
    await page.goto('/')
    await openSettings(page)
    const dialog = page.locator('[data-testid="settings-panel"]')
    await expect(dialog).toBeVisible()

    await dialog.getByText('Execution', { exact: true }).click()

    await expect(dialog).toContainText('New workflow scheduling')
    await expect(dialog.locator('#new-workflow-execution')).toContainText('Sequential')
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
