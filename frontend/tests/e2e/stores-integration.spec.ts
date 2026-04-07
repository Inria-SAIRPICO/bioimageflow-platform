import { test, expect } from '@playwright/test'

test.describe('stores integration', () => {
  test('Pinia is installed and stores initialize without errors', async ({ page }) => {
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()

    // Verify Pinia is installed on the Vue app instance
    const hasPinia = await page.evaluate(() => {
      const app = document.querySelector('#app')
      if (!app) return false
      const vue = (app as any).__vue_app__
      if (!vue) return false
      return vue.config.globalProperties.$pinia !== undefined
    })
    expect(hasPinia).toBe(true)

    // No console errors from store initialization
    const storeErrors = consoleErrors.filter(
      (e) => e.includes('store') || e.includes('pinia') || e.includes('Store'),
    )
    expect(storeErrors).toEqual([])
  })
})
