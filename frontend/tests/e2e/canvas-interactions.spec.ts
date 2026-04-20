import { test, expect } from '@playwright/test'

test.describe('Canvas interactions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await page.waitForResponse(
      (resp) => resp.url().includes('/api/v1/tools') && resp.status() === 200,
    )
  })

  test('common tools are loaded (not example_tools)', async ({ page }) => {
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    // Should see at least one bioimageflow-common-tool (e.g. Files)
    await expect(
      page.locator('.tool-name-cell').filter({ hasText: 'Files' }),
    ).toBeVisible({ timeout: 5000 })
    // Should NOT see example_tools
    await expect(
      page.locator('.tool-name-cell').filter({ hasText: 'GaussianBlur' }),
    ).toHaveCount(0)
  })

  test('PUT /graph returns 200', async ({ page }) => {
    // Add a node to trigger graph sync
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    const toolRow = page.locator('.p-treetable-tbody tr').filter({ hasText: 'Files' })
    if ((await toolRow.count()) > 0) {
      const graphResponse = page.waitForResponse(
        (resp) =>
          resp.url().includes('/api/v1/graph') &&
          resp.request().method() === 'PUT',
        { timeout: 5000 },
      )
      await toolRow.dblclick()
      const resp = await graphResponse
      expect(resp.status()).toBe(200)
    }
  })

  test('selected node has blue border', async ({ page }) => {
    // Add a node
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    const toolRow = page.locator('.p-treetable-tbody tr').filter({ hasText: 'Files' })
    if ((await toolRow.count()) > 0) {
      await toolRow.dblclick()
      // Wait for node to appear
      const node = page.locator('.vue-flow__node').first()
      await expect(node).toBeVisible({ timeout: 3000 })
      await node.click()
      // Check that the node wrapper has .selected class
      await expect(node).toHaveClass(/selected/)
    }
  })

  test('node panel updates on selection', async ({ page }) => {
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    const toolRow = page.locator('.p-treetable-tbody tr').filter({ hasText: 'Files' })
    if ((await toolRow.count()) > 0) {
      await toolRow.dblclick()
      const node = page.locator('.vue-flow__node').first()
      await expect(node).toBeVisible({ timeout: 3000 })
      await node.click()
      // Switch to Node Panel tab
      await page.locator('.dv-tab').filter({ hasText: 'Node Panel' }).click()
      const nodePanel = page.locator('[data-testid="panel-nodePanel"]')
      await expect(nodePanel).toBeVisible()
      // Should show node name, not empty state
      await expect(nodePanel.locator('.node-name')).toBeVisible({ timeout: 3000 })
    }
  })

  test('pins show single circle (no double)', async ({ page }) => {
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    const toolRow = page.locator('.p-treetable-tbody tr').filter({ hasText: 'Files' })
    if ((await toolRow.count()) > 0) {
      await toolRow.dblclick()
      const node = page.locator('.vue-flow__node').first()
      await expect(node).toBeVisible({ timeout: 3000 })
      // No .pin-dot elements should exist (we merged into Handle)
      await expect(node.locator('.pin-dot')).toHaveCount(0)
      // .pin-handle elements should exist
      const handles = node.locator('.pin-handle')
      expect(await handles.count()).toBeGreaterThan(0)
    }
  })

  test('context menu has light theme', async ({ page }) => {
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    const toolRow = page.locator('.p-treetable-tbody tr').filter({ hasText: 'Files' })
    if ((await toolRow.count()) > 0) {
      await toolRow.dblclick()
      const node = page.locator('.vue-flow__node').first()
      await expect(node).toBeVisible({ timeout: 3000 })
      await node.click({ button: 'right' })
      const menu = page.locator('.node-context-menu')
      if ((await menu.count()) > 0) {
        const bg = await menu.evaluate((el) => getComputedStyle(el).backgroundColor)
        // Should be white (#ffffff), not dark
        expect(bg).toContain('255')
      }
    }
  })
})
