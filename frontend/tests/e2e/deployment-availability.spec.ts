import { expect, test } from '@playwright/test'
import { realpath } from 'node:fs/promises'
import { isAbsolute, relative, sep } from 'node:path'
import type { SettingsResponse, WorkspaceInfo } from '../../src/api/types'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`

test('Preferences reflects the actual deployment mode and refuses forbidden settings without changing them', async ({ page }) => {
  const expectedMode = process.env.BIOIMAGEFLOW_E2E_DEPLOYMENT_MODE ?? 'desktop'
  expect(['desktop', 'webapp']).toContain(expectedMode)
  const initialResponse = await page.request.get(`${API}/settings`)
  expect(initialResponse.ok(), await initialResponse.text()).toBe(true)
  const initial = await initialResponse.json() as SettingsResponse
  expect(initial.deployment_mode).toBe(expectedMode)
  const workspaceResponse = await page.request.get(`${API}/workspace`)
  expect(workspaceResponse.ok(), await workspaceResponse.text()).toBe(true)
  const workspaceInfo = await workspaceResponse.json() as WorkspaceInfo
  const runtimeRoot = process.env.BIOIMAGEFLOW_E2E_ROOT
  expect(runtimeRoot, 'The deployment fixture needs an owned runtime root.').toBeTruthy()
  const [canonicalRoot, canonicalWorkspace] = await Promise.all([
    realpath(runtimeRoot!), realpath(workspaceInfo.workspace_path),
  ])
  const workspaceWithinRoot = relative(canonicalRoot, canonicalWorkspace)
  expect(workspaceWithinRoot).not.toBe('')
  expect(isAbsolute(workspaceWithinRoot)).toBe(false)
  expect(workspaceWithinRoot === '..' || workspaceWithinRoot.startsWith(`..${sep}`)).toBe(false)
  await page.goto('/')
  await page.getByRole('menuitem', { name: 'Edit', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Preferences...', exact: true }).click()
  const dialog = page.getByTestId('settings-panel')
  await expect(dialog).toBeVisible()
  const viewers = dialog.getByRole('tab', { name: 'Image Viewers', exact: true })
  if (expectedMode === 'desktop') await expect(viewers).toBeVisible()
  else await expect(viewers).toHaveCount(0)
  await dialog.getByRole('tab', { name: 'Storage', exact: true }).click()
  const workspace = dialog.getByTestId('workspace-path-input')
  await expect(workspace).toHaveAttribute('readonly', '')
  await expect(workspace).toHaveValue(workspaceInfo.workspace_path)
  // No pywebview bridge is injected: even desktop headless mode cannot offer
  // a native Browse action. Native chooser behavior belongs to final M5.
  await expect(dialog.getByTestId('workspace-path-change-button')).toHaveCount(0)
  await expect(dialog.getByTestId('workspace-path-help')).toContainText(expectedMode === 'desktop'
    ? 'Desktop workspace location.' : 'managed by the web application')
  const forbiddenChanges = [
    { deployment_mode: expectedMode === 'desktop' ? 'webapp' : 'desktop' },
    ...(expectedMode === 'webapp' ? [{ workspaces_root: '/forbidden-campaign-root' }] : []),
  ]
  for (const data of forbiddenChanges) {
    const refused = await page.request.patch(`${API}/settings`, { data })
    expect(refused.status(), await refused.text()).toBe(403)
    expect(await refused.json()).toMatchObject({ error: 'settings_policy_read_only', field: Object.keys(data)[0] })
    const after = await page.request.get(`${API}/settings`)
    expect(after.ok(), await after.text()).toBe(true)
    expect(await after.json()).toEqual(initial)
    const retainedWorkspace = await page.request.get(`${API}/workspace`)
    expect(retainedWorkspace.ok(), await retainedWorkspace.text()).toBe(true)
    expect(await retainedWorkspace.json()).toEqual(workspaceInfo)
  }
  await dialog.getByTestId('settings-close').click()
  await page.reload()
  await page.getByRole('menuitem', { name: 'Edit', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Preferences...', exact: true }).click()
  await expect(dialog).toBeVisible()
  if (expectedMode === 'desktop') await expect(viewers).toBeVisible()
  else await expect(viewers).toHaveCount(0)
  const reopened = await page.request.get(`${API}/settings`)
  expect(reopened.ok(), await reopened.text()).toBe(true)
  expect(await reopened.json()).toEqual(initial)
})
