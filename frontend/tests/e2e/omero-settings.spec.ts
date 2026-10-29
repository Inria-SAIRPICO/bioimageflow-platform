import { expect, test } from '@playwright/test'
import type { Locator } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import type { SettingsResponse } from '../../src/api/types'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`

test('OMERO cards validate, retry, share and remove memory-only credentials without exposing passwords', async ({ page }) => {
  // This exercises the injected memory credential provider through the real
  // Settings API. It neither connects to OMERO nor accesses the OS keyring.
  const root = process.env.BIOIMAGEFLOW_E2E_ROOT
  expect(root, 'The test requires an isolated browser runtime root.').toBeTruthy()
  const settingsPath = join(root!, 'settings.json')
  const settings = async () => {
    const response = await page.request.get(`${API}/settings`)
    expect(response.ok(), await response.text()).toBe(true)
    return await response.json() as SettingsResponse
  }
  const before = await settings()
  const beforeDisk = JSON.parse(await readFile(settingsPath, 'utf8')) as Record<string, unknown>
  const previousInstances = before.omero_instances.map(({ name, host, port, username }) => ({ name, host, port, username }))
  const suffix = `${test.info().project.name}_${Date.now()}`
  const name = `OMERO admin ${suffix}`
  const duplicateName = `${name} shared`
  const connection = { host: `omero-admin-${suffix}.invalid`, port: 4064, username: 'campaign_fixture' }
  const password = `synthetic-memory-only-${suffix}`
  const controlledFailure = 'Controlled OMERO settings save failure'
  const baseIndex = before.omero_instances.length
  let browserPatches = 0
  let failNextSave = true
  let primaryOccurred = false
  let cleanupFailed = false
  let cleanupFailure: unknown
  page.on('request', request => {
    if (request.method() === 'PATCH' && new URL(request.url()).pathname === '/api/v1/settings') browserPatches += 1
  })
  await page.route('**/api/v1/settings', async route => {
    if (route.request().method() === 'PATCH' && failNextSave) {
      failNextSave = false
      await route.fulfill({ status: 503, json: { error: 'settings_unavailable', detail: controlledFailure } })
      return
    }
    await route.continue()
  })
  const open = async () => {
    await page.getByRole('menuitem', { name: 'Edit', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Preferences...', exact: true }).click()
    await page.getByTestId('settings-panel').getByRole('tab', { name: 'OMERO', exact: true }).click()
  }
  const save = async (card: Locator, status = 200) => {
    const response = page.waitForResponse(item => item.request().method() === 'PATCH'
      && new URL(item.url()).pathname === '/api/v1/settings')
    await card.getByRole('button', { name: 'Save OMERO instance', exact: true }).click()
    const accepted = await response
    expect(accepted.status(), await accepted.text()).toBe(status)
    return accepted
  }
  const assertNoPassword = async (current: SettingsResponse) => {
    expect(JSON.stringify(current)).not.toContain(password)
    for (const instance of current.omero_instances) expect(instance).not.toHaveProperty('password')
    const disk = await readFile(settingsPath, 'utf8')
    expect(disk).not.toContain(password)
    expect(disk).not.toContain('"password"')
  }
  try {
    await page.goto('/')
    await open()
    const dialog = page.getByTestId('settings-panel')
    const first = dialog.getByTestId(`omero-card-${baseIndex}`)
    await dialog.getByTestId('omero-add-button').click()
    await first.getByLabel('Name', { exact: true }).fill(name)
    await first.getByRole('button', { name: 'Save OMERO instance', exact: true }).click()
    await expect(dialog.getByTestId('omero-validation-error')).toHaveText('Host is required.')
    expect(browserPatches).toBe(0)
    expect(await settings()).toEqual(before)
    expect(JSON.parse(await readFile(settingsPath, 'utf8'))).toEqual(beforeDisk)

    await first.getByLabel('Host', { exact: true }).fill(connection.host)
    await first.getByLabel('Username', { exact: true }).fill(connection.username)
    await first.getByLabel('Password', { exact: true }).fill(password)
    await save(first, 503)
    await expect(page.locator('.p-toast')).toContainText(controlledFailure)
    await expect(first.getByLabel('Password', { exact: true })).toHaveValue(password)
    expect(await settings()).toEqual(before)
    expect(JSON.parse(await readFile(settingsPath, 'utf8'))).toEqual(beforeDisk)
    const accepted = await (await save(first)).json() as SettingsResponse
    expect(accepted.omero_instances).toEqual([...before.omero_instances, { name, ...connection, password_stored: true }])
    await expect(first.getByLabel('Password', { exact: true })).toHaveValue('')
    await expect(first.getByText('Stored', { exact: true })).toBeVisible()
    await assertNoPassword(accepted)
    expect(browserPatches).toBe(2)

    await first.getByRole('button', { name: 'Duplicate OMERO instance', exact: true }).click()
    const duplicate = dialog.getByTestId(`omero-card-${baseIndex + 1}`)
    await expect(duplicate.getByLabel('Password', { exact: true })).toHaveValue('')
    await duplicate.getByRole('button', { name: 'Save OMERO instance', exact: true }).click()
    await expect(dialog.getByTestId('omero-validation-error')).toHaveText('OMERO instance names must be unique.')
    expect(browserPatches).toBe(2)
    expect(await settings()).toEqual(accepted)
    await duplicate.getByLabel('Name', { exact: true }).fill(duplicateName)
    const shared = await (await save(duplicate)).json() as SettingsResponse
    expect(shared.omero_instances).toEqual([...before.omero_instances,
      { name, ...connection, password_stored: true },
      { name: duplicateName, ...connection, password_stored: true },
    ])
    await expect(duplicate.getByText('Stored', { exact: true })).toBeVisible()
    await assertNoPassword(shared)

    await dialog.getByTestId('settings-close').click()
    await page.reload()
    await open()
    await expect(first.getByLabel('Host', { exact: true })).toHaveValue(connection.host)
    await expect(duplicate.getByLabel('Name', { exact: true })).toHaveValue(duplicateName)
    await expect(first.getByText('Stored', { exact: true })).toBeVisible()
    await expect(duplicate.getByText('Stored', { exact: true })).toBeVisible()
    expect(await settings()).toEqual(shared)

    await first.getByRole('button', { name: 'Remove OMERO instance', exact: true }).click()
    const confirmation = page.getByRole('alertdialog', { name: 'Remove OMERO instance', exact: true })
    await expect(confirmation).toContainText(name)
    await confirmation.getByRole('button', { name: 'No', exact: true }).click()
    await expect(confirmation).toHaveCount(0)
    expect(browserPatches).toBe(3)
    expect(await settings()).toEqual(shared)
    await first.getByRole('button', { name: 'Remove OMERO instance', exact: true }).click()
    const removal = page.waitForResponse(item => item.request().method() === 'PATCH'
      && new URL(item.url()).pathname === '/api/v1/settings')
    await confirmation.getByRole('button', { name: 'Yes', exact: true }).click()
    expect((await removal).status()).toBe(200)
    // The remaining card shares the connection key, so its credential survives.
    await expect(first.getByLabel('Name', { exact: true })).toHaveValue(duplicateName)
    await expect(first.getByText('Stored', { exact: true })).toBeVisible()
    expect((await settings()).omero_instances).toEqual([...before.omero_instances,
      { name: duplicateName, ...connection, password_stored: true },
    ])
    await first.getByRole('button', { name: 'Remove OMERO instance', exact: true }).click()
    const finalRemoval = page.waitForResponse(item => item.request().method() === 'PATCH'
      && new URL(item.url()).pathname === '/api/v1/settings')
    await confirmation.getByRole('button', { name: 'Yes', exact: true }).click()
    expect((await finalRemoval).status()).toBe(200)
    expect(await settings()).toEqual(before)
    expect(JSON.parse(await readFile(settingsPath, 'utf8'))).toEqual(beforeDisk)

    // Recreate only the owned metadata, without a password, through the public
    // API. A false status proves the last-reference removal deleted the key.
    const probe = await page.request.patch(`${API}/settings`, {
      data: { omero_instances: [...previousInstances, { name, ...connection }] },
    })
    expect(probe.ok(), await probe.text()).toBe(true)
    const probed = await probe.json() as SettingsResponse
    expect(probed.omero_instances.at(-1)).toEqual({ name, ...connection, password_stored: false })
    await assertNoPassword(probed)
  } catch (error) {
    primaryOccurred = true
    throw error
  } finally {
    for (const cleanup of [
      () => page.goto('about:blank'),
      () => page.unrouteAll({ behavior: 'wait' }),
      async () => {
        const restored = await page.request.patch(`${API}/settings`, { data: { omero_instances: previousInstances } })
        expect(restored.ok(), await restored.text()).toBe(true)
        expect(await settings()).toEqual(before)
        expect(JSON.parse(await readFile(settingsPath, 'utf8'))).toEqual(beforeDisk)
      },
    ]) {
      try { await cleanup() } catch (error) {
        if (primaryOccurred) console.error('OMERO card cleanup failed while preserving the primary:', error)
        else if (!cleanupFailed) { cleanupFailed = true; cleanupFailure = error }
      }
    }
  }
  if (cleanupFailed) throw cleanupFailure
})
