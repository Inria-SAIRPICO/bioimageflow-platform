import { expect, test } from '@playwright/test'
import { readFile, realpath } from 'node:fs/promises'
import { dirname, isAbsolute, relative, sep } from 'node:path'
import type { SettingsResponse, ToolCreateResponse, ToolMetadata, ToolRenameResponse, WorkflowInfo } from '../../src/api/types'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`

test('custom tools create, rename, reopen and retry deletion without changing another source', async ({ page }) => {
  const suffix = `${test.info().project.name === 'chromium' ? 'Chrome' : 'Firefox'}${Date.now()}`
  const name = `Campaign${suffix}Tool`
  const renamed = `Renamed${suffix}Tool`
  const occupied = `Occupied${suffix}Tool`
  const workflowName = `custom_tools_${suffix}`
  const ownedNames = new Set([name, renamed, occupied])
  const catalog = async () => {
    const response = await page.request.get(`${API}/tools`)
    expect(response.ok(), await response.text()).toBe(true)
    return await response.json() as ToolMetadata[]
  }
  const beforeCatalog = await catalog()
  expect(beforeCatalog.some(tool => ownedNames.has(tool.name))).toBe(false)
  const settingsResponse = await page.request.get(`${API}/settings`)
  expect(settingsResponse.ok(), await settingsResponse.text()).toBe(true)
  const beforeSettings = await settingsResponse.json() as SettingsResponse
  let info: WorkflowInfo | null = null
  let primaryOccurred = false
  let cleanupFailed = false
  let cleanupFailure: unknown
  let createRequests = 0
  let deleteRequests = 0
  let runRequests = 0
  page.on('request', request => {
    const path = new URL(request.url()).pathname
    if (request.method() === 'POST' && path === '/api/v1/tools') createRequests += 1
    if (request.method() === 'DELETE' && path === `/api/v1/tools/${renamed}`) deleteRequests += 1
    if (request.method() === 'POST' && path === '/api/v1/execution/run') runRequests += 1
  })
  const openWorkflow = async () => {
    await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
    await page.getByTestId('workflow-search').fill(workflowName)
    await page.getByTestId(`workflow-row-${workflowName}`).dblclick()
    await expect(page.getByTestId('workflow-title')).toHaveText(workflowName)
  }
  const openSettings = async () => {
    await page.getByRole('menuitem', { name: 'Edit', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Preferences...', exact: true }).click()
    await expect(page.getByTestId('settings-panel')).toBeVisible()
  }
  const rename = async (target: string, status: number) => {
    await page.getByTestId(`tool-item-${name}`).hover()
    const response = page.waitForResponse(item => item.request().method() === 'PATCH'
      && new URL(item.url()).pathname === `/api/v1/tools/${name}`)
    const prompted = page.waitForEvent('dialog')
    const clicked = page.getByTestId(`tool-rename-${name}`).click()
    const prompt = await prompted
    expect(prompt.type()).toBe('prompt')
    expect(prompt.message()).toBe('Rename custom tool')
    await prompt.accept(target)
    await clicked
    const result = await response
    expect(result.status(), await result.text()).toBe(status)
    return result
  }
  try {
    const creation = await page.request.post(`${API}/workflows`, { data: { name: workflowName } })
    expect(creation.status(), await creation.text()).toBe(201)
    info = await creation.json() as WorkflowInfo
    const originalWorkflow = await readFile(info.path)
    const collision = await page.request.post(`${API}/tools`, {
      params: { workflow_name: workflowName }, data: { name: occupied, tool_type: 'DataFrameTool' },
    })
    expect(collision.status(), await collision.text()).toBe(201)
    const collisionTool = await collision.json() as ToolCreateResponse
    const collisionBytes = await readFile(collisionTool.path)
    await page.goto('/')
    await openWorkflow()

    // The real Preferences field persists a harmless command. Editor requests
    // below execute `true`, not a native editor or a managed editor install.
    await openSettings()
    const settings = page.getByTestId('settings-panel')
    const editor = settings.getByTestId('external-editor-input')
    await editor.fill('true')
    const editorSaved = page.waitForResponse(response => response.request().method() === 'PATCH'
      && new URL(response.url()).pathname === '/api/v1/settings')
    await settings.getByTestId('settings-close').click()
    expect((await editorSaved).status()).toBe(200)
    await page.reload()
    await openWorkflow()
    await openSettings()
    await expect(editor).toHaveValue('true')
    expect((await (await page.request.get(`${API}/settings`)).json()).external_editor).toBe('true')
    await settings.getByTestId('settings-close').click()

    await page.locator('.dv-tab').filter({ hasText: /^Tools$/ }).click()
    await page.getByTestId('create-tool-btn').click()
    const dialog = page.getByRole('dialog', { name: 'Create Tool', exact: true })
    await dialog.getByTestId('tool-name-input').fill('../Invalid')
    await expect(dialog.getByTestId('create-tool-submit')).toBeDisabled()
    await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()
    expect(createRequests).toBe(0)
    expect((await catalog()).some(tool => tool.name === name)).toBe(false)
    await page.getByTestId('create-tool-btn').click()
    await dialog.getByTestId('tool-name-input').fill(occupied)
    await expect(dialog.getByTestId('create-tool-submit')).toBeDisabled()
    await dialog.getByTestId('tool-name-input').fill(name)
    await dialog.getByTestId('tool-type-select').click()
    await page.getByRole('option', { name: 'DataFrame Tool', exact: true }).click()
    const created = page.waitForResponse(response => response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/tools')
    const editorOpened = page.waitForResponse(response => response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/editor/open-tool')
    await dialog.getByTestId('create-tool-submit').click()
    const createdResponse = await created
    expect(createdResponse.status(), await createdResponse.text()).toBe(201)
    expect(new URL(createdResponse.url()).searchParams.get('workflow_name')).toBe(workflowName)
    const tool = await createdResponse.json() as ToolCreateResponse
    expect(tool).toMatchObject({ name, tool_type: 'DataFrameTool', source_kind: 'custom', editable: true })
    const [workflowRoot, toolPath] = await Promise.all([realpath(dirname(info.path)), realpath(tool.path)])
    const withinWorkflow = relative(workflowRoot, toolPath)
    expect(isAbsolute(withinWorkflow)).toBe(false)
    expect(withinWorkflow === '..' || withinWorkflow.startsWith(`..${sep}`)).toBe(false)
    const originalSource = await readFile(tool.path)
    expect(originalSource.toString()).toContain(`class ${name}(DataFrameTool):`)
    const opened = await editorOpened
    expect(opened.ok(), await opened.text()).toBe(true)
    expect(opened.request().postDataJSON()).toEqual({ tool_name: name, workflow_id: workflowName })
    expect(await opened.json()).toMatchObject({ opened: true, method: 'external', path: tool.path })
    await page.getByTestId('tool-search').fill(name)
    await expect(page.getByTestId(`tool-item-${name}`)).toBeVisible()
    expect(createRequests).toBe(1)

    await rename(occupied, 409)
    await expect(page.locator('.p-toast')).toContainText('Rename failed')
    expect(await readFile(tool.path)).toEqual(originalSource)
    expect(await readFile(collisionTool.path)).toEqual(collisionBytes)
    expect((await catalog()).filter(item => ownedNames.has(item.name)).map(item => item.name).sort()).toEqual([name, occupied].sort())
    const renamedResponse = await rename(renamed, 200)
    const replacement = await renamedResponse.json() as ToolRenameResponse
    expect(replacement).toMatchObject({ old_name: name, new_name: renamed })
    const renamedSource = await readFile(replacement.path)
    expect(renamedSource.toString()).toContain(`class ${renamed}(DataFrameTool):`)
    await expect(readFile(tool.path)).rejects.toMatchObject({ code: 'ENOENT' })
    expect(await readFile(collisionTool.path)).toEqual(collisionBytes)
    expect(await readFile(info.path)).toEqual(originalWorkflow)
    await page.reload()
    await openWorkflow()
    await page.locator('.dv-tab').filter({ hasText: /^Tools$/ }).click()
    await page.getByTestId('tool-search').fill(renamed)
    const row = page.getByTestId(`tool-item-${renamed}`)
    await expect(row).toBeVisible()
    await expect(page.getByTestId(`tool-item-${name}`)).toHaveCount(0)
    expect((await catalog()).find(item => item.name === renamed)).toMatchObject({ source_kind: 'custom', editable: true, tool_type: 'DataFrameTool' })
    await row.hover()
    await page.getByTestId(`tool-delete-${renamed}`).click()
    const confirmation = page.getByRole('alertdialog', { name: 'Delete Custom Tool', exact: true })
    await expect(confirmation).toContainText(`Delete ${renamed}?`)
    await confirmation.getByRole('button', { name: 'Cancel', exact: true }).click()
    expect(deleteRequests).toBe(0)
    expect(await readFile(replacement.path)).toEqual(renamedSource)

    let failNextDelete = true
    await page.route(url => url.pathname === `/api/v1/tools/${renamed}`, async route => {
      if (route.request().method() === 'DELETE' && failNextDelete) {
        failNextDelete = false
        await route.fulfill({ status: 503, json: { error: 'controlled_delete_failure', detail: 'Controlled custom-tool delete failure' } })
      } else await route.continue()
    })
    for (const status of [503, 200]) {
      await row.hover()
      await page.getByTestId(`tool-delete-${renamed}`).click()
      const deleted = page.waitForResponse(response => response.request().method() === 'DELETE'
        && new URL(response.url()).pathname === `/api/v1/tools/${renamed}`)
      await confirmation.getByRole('button', { name: 'Delete', exact: true }).click()
      expect((await deleted).status()).toBe(status)
      if (status === 503) {
        await expect(page.locator('.p-toast')).toContainText('Delete failed')
        expect(await readFile(replacement.path)).toEqual(renamedSource)
        expect((await catalog()).some(item => item.name === renamed)).toBe(true)
      }
    }
    await expect(row).toHaveCount(0)
    await expect(readFile(replacement.path)).rejects.toMatchObject({ code: 'ENOENT' })
    expect((await catalog()).some(item => item.name === renamed || item.name === name)).toBe(false)
    expect(await readFile(collisionTool.path)).toEqual(collisionBytes)
    expect(await readFile(info.path)).toEqual(originalWorkflow)
    expect(deleteRequests).toBe(2)
    expect(runRequests).toBe(0)
  } catch (error) {
    primaryOccurred = true
    throw error
  } finally {
    for (const cleanup of [
      () => page.goto('about:blank'),
      () => page.unrouteAll({ behavior: 'wait' }),
      async () => {
        if (!info) return
        for (const item of (await catalog()).filter(tool => ownedNames.has(tool.name))) {
          const deleted = await page.request.delete(`${API}/tools/${item.name}`, { params: { workflow_name: workflowName } })
          expect(deleted.ok(), await deleted.text()).toBe(true)
        }
        const removed = await page.request.delete(`${API}/workflows/${workflowName}`, {
          params: { expected_identity_generation: info.identity_generation },
        })
        expect(removed.ok(), await removed.text()).toBe(true)
      },
      async () => {
        const restored = await page.request.patch(`${API}/settings`, { data: { external_editor: beforeSettings.external_editor } })
        expect(restored.ok(), await restored.text()).toBe(true)
        expect(await (await page.request.get(`${API}/settings`)).json()).toEqual(beforeSettings)
        expect(await catalog()).toEqual(beforeCatalog)
      },
    ]) {
      try { await cleanup() } catch (error) {
        if (primaryOccurred) console.error('Custom-tool cleanup failed while preserving the primary:', error)
        else if (!cleanupFailed) { cleanupFailed = true; cleanupFailure = error }
      }
    }
  }
  if (cleanupFailed) throw cleanupFailure
})
