/**
 * Editable sources reload through the filesystem watcher, registry, WebSocket,
 * and canvas. Installed package sources retain their admitted generation until
 * an explicit lifecycle operation; ordinary file events leave the catalog and
 * canvas unchanged.
 *
 * The installed-source control edits only an isolated Playwright fixture and its
 * faithful RECORD row, then restores both original byte sequences. Its bounded
 * observation window covers the native watcher latency, including macOS FSEvents.
 */

import { test, expect } from '@playwright/test'
import type { ToolMetadata } from '../../src/api/types'
import { createHash } from 'node:crypto'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { basename, dirname, join } from 'node:path'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

test.describe('hot-reload', () => {
  test('custom DataFrame tool display name refreshes after an editor save', async ({ page }) => {
    // Editor installation belongs to desktop manual QA; the save below still
    // exercises the real filesystem watcher, registry, WebSocket, and canvas.
    await page.route('**/api/v1/editor/open-tool', route => route.fulfill({
      json: { opened: true, method: 'external', path: '/mock-editor/tool.py' },
    }))
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    const workflowName = `custom_reload_${Date.now()}`
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'New', exact: true }).click()
    await page.getByTestId('workflow-display-name-input').fill(workflowName)
    await page.getByTestId('workflow-dialog-submit').click()
    await expect(page.getByTestId('workflow-title')).toContainText(workflowName)
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    await page.getByTestId('create-tool-btn').click()
    await page.getByTestId('tool-name-input').fill('QaManualEdit')
    await page.getByTestId('tool-type-select').click()
    await page.getByRole('option', { name: 'DataFrame Tool', exact: true }).click()
    const created = page.waitForResponse(response => response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/tools')
    await page.getByTestId('create-tool-submit').click()
    const response = await created
    expect(response.ok()).toBeTruthy()
    const { path } = await response.json()
    const tool = page.getByTestId('tool-item-QaManualEdit')
    await expect(tool).toContainText('Qa Manual Edit')
    try {
      writeFileSync(path, readFileSync(path, 'utf8').replace(
        'display_name = "Qa Manual Edit"', 'display_name = "Qa Manual Edit 2"',
      ))
      await expect(tool).toContainText('Qa Manual Edit 2', { timeout: 8000 })
      await tool.dragTo(page.locator('.vue-flow'), { targetPosition: { x: 260, y: 180 } })
      const node = page.locator('.vue-flow__node').first()
      await expect(node).toBeVisible()
      const badge = node.locator('.updated-badge')
      if (await badge.isVisible()) await badge.click()
      await expect(badge).toHaveCount(0)
      writeFileSync(path, readFileSync(path, 'utf8').replace('df.copy()', 'df.copy(deep=True)'))
      await expect(badge).toBeVisible({ timeout: 8000 })
      await page.locator('.vue-flow__controls-fitview').click()
      await badge.click()
      await expect(badge).toHaveCount(0)
    } finally {
      await page.request.delete(`${API_BASE}/api/v1/tools/QaManualEdit`, {
        params: { workflow_name: workflowName },
      }).catch(() => undefined)
      await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`).catch(() => undefined)
    }
  })

  test('installed file edit preserves the admitted catalog without reload or updated badge', async ({ page }) => {
    const fixturePath = process.env.BIOIMAGEFLOW_HOT_RELOAD_FIXTURE
    expect(
      fixturePath,
      'Playwright must set BIOIMAGEFLOW_HOT_RELOAD_FIXTURE to its isolated installed Files-tool fixture.',
    ).toBeTruthy()
    const filePath = fixturePath as string
    expect(
      existsSync(filePath),
      `The Playwright backend did not provision the hot-reload fixture at ${filePath}.`,
    ).toBe(true)
    const originalSource = readFileSync(filePath)
    const original = originalSource.toString('utf8')
    const packageDirectory = dirname(filePath)
    const installationDirectory = dirname(packageDirectory)
    const recordPath = join(
      installationDirectory,
      `${basename(packageDirectory)}-${basename(installationDirectory)}.dist-info`,
      'RECORD',
    )
    expect(existsSync(recordPath), 'The installed fixture must have its real distribution RECORD.').toBe(true)
    const originalRecord = readFileSync(recordPath)
    const member = `${basename(packageDirectory)}/${basename(filePath)}`
    const prefix = `${member},`
    const recordLines = originalRecord.toString('utf8').split('\n')
    const memberLines = recordLines.filter(line => line.startsWith(prefix))
    expect(memberLines, 'Only the known Files source RECORD row may change.').toHaveLength(1)
    const originalDigest = createHash('sha256').update(originalSource).digest('base64url')
    expect(memberLines[0]!.trimEnd()).toBe(`${prefix}sha256=${originalDigest},${originalSource.length}`)

    function recordForSource(source: Buffer): string {
      const digest = createHash('sha256').update(source).digest('base64url')
      return recordLines.map(line => line.startsWith(prefix)
        ? `${prefix}sha256=${digest},${source.length}${line.endsWith('\r') ? '\r' : ''}`
        : line).join('\n')
    }

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    const workflowName = `hot_reload_${Date.now()}`
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'New', exact: true }).click()
    await page.getByTestId('workflow-display-name-input').fill(workflowName)
    await page.getByTestId('workflow-dialog-submit').click()
    await expect(page.getByTestId('workflow-title')).toContainText(workflowName)

    async function catalogFiles(): Promise<ToolMetadata> {
      const response = await page.request.get(`${API_BASE}/api/v1/tools`)
      expect(response.ok()).toBeTruthy()
      const files = (await response.json() as ToolMetadata[]).find(tool => tool.name === 'Files')
      expect(files, 'The admitted installed Files tool must remain available.').toBeTruthy()
      return files!
    }
    const admitted = await catalogFiles()
    expect(admitted).toMatchObject({
      source_kind: 'package', editable: false,
      inputs: { path: { default: '' } },
    })

    // Add a Files node so the canvas has at least one node from the fixture.
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    await page.locator('[data-testid="tool-search"]').fill('Files')
    const toolRow = page.getByTestId('tool-item-Files')
    await expect(toolRow).toBeVisible({ timeout: 5000 })
    await toolRow.dragTo(page.locator('.vue-flow'), {
      targetPosition: { x: 260, y: 180 },
    })
    const node = page.locator('.vue-flow__node').first()
    await expect(node).toBeVisible({ timeout: 3000 })

    const badge = node.locator('.updated-badge')
    await expect(badge).toHaveCount(0)

    // Accept the owned socket before editing, so a missing connection cannot
    // turn the no-reload assertion into a false positive in either browser.
    await page.evaluate(async () => {
      type HotReloadWindow = typeof window & {
        __bioimageflowHotReloadMessages?: string[]
        __bioimageflowHotReloadSocket?: WebSocket
      }
      const state = window as HotReloadWindow
      const socket = new WebSocket(
        (location.protocol === 'https:' ? 'wss://' : 'ws://')
        + location.host
        + '/ws',
      )
      state.__bioimageflowHotReloadSocket = socket
      state.__bioimageflowHotReloadMessages = []
      socket.addEventListener('message', (event) => {
        try {
          const message = JSON.parse(event.data as string)
          if (message.type === 'system_error' && message.code === 'tool_reload_failed')
            state.__bioimageflowHotReloadMessages!.push(`${message.type}:${message.code}`)
          else if (message.tool_name === 'Files' && ['tool_reload', 'tool_removed'].includes(message.type))
            state.__bioimageflowHotReloadMessages!.push(message.type)
        } catch {
          /* Ignore unrelated non-JSON WebSocket traffic. */
        }
      })
      await new Promise<void>((resolve, reject) => {
        socket.addEventListener('open', () => resolve(), { once: true })
        socket.addEventListener('error', () => reject(new Error('WebSocket connection failed')), {
          once: true,
        })
      })
    })

    let primaryOccurred = false
    let cleanupFailed = false
    let cleanupFailure: unknown
    try {
      // A valid installed-file edit still cannot replace admitted executable facts.
      const modified = original.replace(
        "path: str = ''",
        `path: str = 'hot_reload_${Date.now()}'`,
      )
      expect(modified).not.toBe(original)
      const modifiedSource = Buffer.from(modified, 'utf8')
      // RECORD is not a Python watcher input. Stage its exact row first so
      // the source event observes the complete admitted fixture pair.
      writeFileSync(recordPath, recordForSource(modifiedSource), 'utf8')
      writeFileSync(filePath, modifiedSource)

      const observed = await page.evaluate(async () => {
        type HotReloadWindow = typeof window & {
          __bioimageflowHotReloadMessages?: string[]
          __bioimageflowHotReloadSocket?: WebSocket
        }
        // Absence must hold beyond the watcher/debounce window, not merely at
        // the instant the files are written.
        await new Promise<void>(resolve => window.setTimeout(resolve, 4500))
        const state = window as HotReloadWindow
        return {
          connected: state.__bioimageflowHotReloadSocket?.readyState === WebSocket.OPEN,
          messages: state.__bioimageflowHotReloadMessages,
        }
      })
      expect(observed).toEqual({ connected: true, messages: [] })
      await expect(badge).toHaveCount(0)
      expect(await catalogFiles()).toEqual(admitted)
    } catch (error) {
      primaryOccurred = true
      throw error
    } finally {
      // Restore the exact original pair independently, with metadata first.
      for (const restore of [
        () => writeFileSync(recordPath, originalRecord),
        () => writeFileSync(filePath, originalSource),
      ]) {
        try { restore() } catch (error) {
          if (primaryOccurred) console.error('Fixture restoration failed while preserving the primary:', error)
          else if (!cleanupFailed) { cleanupFailed = true; cleanupFailure = error }
        }
      }
      await page.evaluate(() => {
        type HotReloadWindow = typeof window & {
          __bioimageflowHotReloadMessages?: string[]
          __bioimageflowHotReloadSocket?: WebSocket
        }
        const state = window as HotReloadWindow
        state.__bioimageflowHotReloadSocket?.close()
        delete state.__bioimageflowHotReloadMessages
        delete state.__bioimageflowHotReloadSocket
      }).catch(() => undefined)
      await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`).catch(() => undefined)
    }
    if (cleanupFailed) throw cleanupFailure
    expect(readFileSync(recordPath)).toEqual(originalRecord)
    expect(readFileSync(filePath)).toEqual(originalSource)
  })
})
