import { test, expect } from '@playwright/test'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

for (const extent of [0, 8000]) {
  test(`centers a ${extent ? 'large' : 'small'} workflow with a working folder grid @critical`, async ({ page }) => {
    await page.request.post(`${API_BASE}/api/v1/dev/seed`)
    const folder = `viewport_${Date.now()}`
    const name = `${folder}/workflow`
    expect((await page.request.post(`${API_BASE}/api/v1/workflows/folders`, {
      data: { path: folder },
    })).ok()).toBe(true)
    try {
      expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
        data: { name, display_name: 'Viewport test' },
      })).ok()).toBe(true)
      const nodes = [0, ...(extent ? [extent] : [])].map((x, index) => ({
        type: 'tool', id: `source_${index}`, name: `Source ${index}`, tool_name: 'SeedNumbers',
        parameters: {}, position: [x, 100], enabled: true, collapsed: false,
      }))
      const saved = await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
        data: { graph: {
          schema_version: 1, name: 'workflow', display_name: 'Viewport test', nodes, edges: [],
          interface: { inputs: [], outputs: [] }, config: { engine: 'direct', execution: 'parallel' },
        } },
      })
      expect(saved.ok(), await saved.text()).toBe(true)
      await page.goto('/')
      await page.evaluate(async (workflowName) => {
        const { useAutoSave } = await import('/src/composables/useAutoSave.ts')
        await useAutoSave().setLastOpenedWorkflow(workflowName)
      }, name)
      await page.reload()
      await expect(page.locator('.vue-flow__node')).toHaveCount(nodes.length)
      const zoom = () => page.locator('.vue-flow__transformationpane').evaluate((element) =>
        new DOMMatrix(getComputedStyle(element).transform).a,
      )
      if (extent) await expect.poll(zoom).toBeLessThan(0.5)
      else await expect.poll(zoom).toBeCloseTo(1, 3)
      await expect(async () => {
        const canvas = await page.locator('.vue-flow').boundingBox()
        const boxes = await page.locator('.vue-flow__node').evaluateAll((elements) => elements.map((element) => {
          const rect = element.getBoundingClientRect()
          return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom }
        }))
        expect(canvas).not.toBeNull()
        for (const box of boxes) {
          expect(box.left).toBeGreaterThanOrEqual(canvas!.x)
          expect(box.right).toBeLessThanOrEqual(canvas!.x + canvas!.width)
          expect(box.top).toBeGreaterThanOrEqual(canvas!.y)
          expect(box.bottom).toBeLessThanOrEqual(canvas!.y + canvas!.height)
        }
        const center = (Math.min(...boxes.map(b => b.left)) + Math.max(...boxes.map(b => b.right))) / 2
        expect(Math.abs(center - canvas!.x - canvas!.width / 2)).toBeLessThan(5)
      }).toPass({ timeout: 5000 })
      // SVG URL fragments are decoded by the browser, unlike element IDs.
      expect(await page.locator('.vue-flow__background').evaluate((svg) => {
        const fill = svg.querySelector('rect')!.getAttribute('fill')!
        const fragment = fill.slice(fill.indexOf('#') + 1, -1)
        return document.getElementById(decodeURIComponent(fragment)) === svg.querySelector('pattern')
      })).toBe(true)
      await expect(page.getByTestId('run-selected-button')).toBeVisible()
    } finally {
      await page.request.delete(`${API_BASE}/api/v1/workflows/${name}`)
      await page.request.delete(`${API_BASE}/api/v1/workflows/folders/${folder}`)
    }
  })
}
