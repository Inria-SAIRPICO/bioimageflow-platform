/**
 * Hot-reload E2E
 *
 * Drives the full backend → WebSocket → frontend path:
 *   1. Add a tool from the existing tool store onto the canvas.
 *   2. Subscribe to the WebSocket and listen for a `tool_reload` message.
 *   3. Modify a `*.py` file inside the tool fixture so the backend's
 *      watchdog observer fires.
 *   4. Wait up to 3 s for the `tool_reload` message and the resulting
 *      `updatedBadge` UI mutation.
 *   5. Click the badge to dismiss it.
 *
 * This test is destructive — it appends a comment line to a tool source
 * file. To avoid mutating the user's real install, it requires the
 * `BIOIMAGEFLOW_HOT_RELOAD_FIXTURE` env var pointing to an absolute path
 * of a `*.py` file in a *fixture* tool store the test is allowed to
 * modify. The corresponding tool must surface in the Tools panel as
 * "Files" (i.e. the fixture is a copy of bioimageflow_common_tools).
 *
 * Without that env var the test is skipped — see `manual-verification`
 * in the plan for the unautomated checklist.
 *
 * macOS FSEvents has a ~300 ms minimum latency. We use a 4.5 s timeout
 * to keep the test robust on CI.
 */

import { test, expect } from '@playwright/test'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'

test.describe('hot-reload', () => {
  test('file edit broadcasts tool_reload and surfaces updated badge', async ({ page }) => {
    const fixturePath = process.env.BIOIMAGEFLOW_HOT_RELOAD_FIXTURE
    test.skip(
      !fixturePath || !existsSync(fixturePath),
      'Set BIOIMAGEFLOW_HOT_RELOAD_FIXTURE to an absolute path of a fixture *.py file the test is allowed to modify.',
    )
    const filePath = fixturePath as string
    const original = readFileSync(filePath, 'utf-8')

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await page.waitForResponse(
      (resp) => resp.url().includes('/api/v1/tools') && resp.status() === 200,
    )

    // Add a Files node so the canvas has at least one node from the fixture.
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    const toolRow = page
      .locator('.p-treetable-tbody tr')
      .filter({ hasText: 'Files' })
    if ((await toolRow.count()) === 0) {
      test.skip(true, 'Files tool not available in the tools panel.')
      return
    }
    await toolRow.dblclick()
    const node = page.locator('.vue-flow__node').first()
    await expect(node).toBeVisible({ timeout: 3000 })

    // Capture the next `tool_reload` message via a page-side promise.
    const toolReloadReceived = page.evaluate(() => {
      return new Promise<{ tool_name: string }>((resolve, reject) => {
        const sock = new WebSocket(
          (location.protocol === 'https:' ? 'wss://' : 'ws://')
          + location.host
          + '/ws',
        )
        const timeout = setTimeout(() => {
          try { sock.close() } catch { /* */ }
          reject(new Error('Did not receive tool_reload within timeout.'))
        }, 4500)
        sock.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data as string)
            if (msg.type === 'tool_reload') {
              clearTimeout(timeout)
              try { sock.close() } catch { /* */ }
              resolve({ tool_name: msg.tool_name })
            }
          } catch {
            /* */
          }
        }
        sock.onerror = () => {
          clearTimeout(timeout)
          reject(new Error('WebSocket error'))
        }
      })
    })

    try {
      // Append a harmless comment to force a real source change.
      const modified = original + `\n# hot-reload e2e marker ${Date.now()}\n`
      writeFileSync(filePath, modified, 'utf-8')

      const result = await toolReloadReceived
      expect(result.tool_name.length).toBeGreaterThan(0)

      // Edit affects every class re-exported from this file (including Files),
      // so the canvas node should pick up the badge.
      await expect(node.locator('.updated-badge')).toBeVisible({ timeout: 3000 })

      // Dismissing clears the badge.
      await node.locator('.updated-badge').click()
      await expect(node.locator('.updated-badge')).toHaveCount(0)
    } finally {
      // Restore the fixture file even if assertions failed.
      writeFileSync(filePath, original, 'utf-8')
    }
  })
})
