import { test, expect } from '@playwright/test'
import type { WorkflowFile } from '../../src/api/types'

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
      const accepted = await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)
      expect(accepted.ok(), await accepted.text()).toBe(true)
      const acceptedGraph = (await accepted.json() as WorkflowFile).graph
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
      const expectNodesInView = async () => {
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
      }
      await expect(expectNodesInView).toPass({ timeout: 5000 })
      // SVG URL fragments are decoded by the browser, unlike element IDs.
      expect(await page.locator('.vue-flow__background').evaluate((svg) => {
        const fill = svg.querySelector('rect')!.getAttribute('fill')!
        const fragment = fill.slice(fill.indexOf('#') + 1, -1)
        return document.getElementById(decodeURIComponent(fragment)) === svg.querySelector('pattern')
      })).toBe(true)
      await expect(page.getByTestId('run-selected-button')).toBeVisible()

      await test.step('Wheel zoom respects the five-percent floor and middle-button drag pans', async () => {
        const canvas = await page.locator('.vue-flow').boundingBox()
        expect(canvas).not.toBeNull()
        const initialZoom = await zoom()
        await page.mouse.move(canvas!.x + canvas!.width * 0.8, canvas!.y + canvas!.height * 0.75)
        await page.mouse.wheel(0, -500)
        await expect.poll(zoom).toBeGreaterThan(initialZoom)
        await page.mouse.wheel(0, 4000)
        await expect.poll(zoom).toBeCloseTo(0.05, 5)
        await page.mouse.wheel(0, 1000)
        await expect.poll(zoom).toBeCloseTo(0.05, 5)
        const translation = () => page.locator('.vue-flow__transformationpane').evaluate(element => {
          const matrix = new DOMMatrix(getComputedStyle(element).transform)
          return { x: matrix.e, y: matrix.f }
        })
        const before = await translation()
        const start = { x: canvas!.x + canvas!.width * 0.6, y: canvas!.y + canvas!.height * 0.6 }
        await page.mouse.move(start.x, start.y)
        await page.mouse.down({ button: 'middle' })
        await page.mouse.move(start.x + 80, start.y + 50, { steps: 8 })
        await page.mouse.up({ button: 'middle' })
        await expect.poll(async () => {
          const after = await translation()
          return Math.hypot(after.x - before.x, after.y - before.y)
        }).toBeGreaterThan(50)
        expect(await zoom()).toBeCloseTo(0.05, 5)
      })

      await test.step('Fit keeps nodes visible after the canvas bounds change', async () => {
        const before = await page.locator('.vue-flow').boundingBox()
        expect(before).not.toBeNull()
        if (extent) {
          // Both window sizes remain within the supported desktop layout.
          const viewport = page.viewportSize()!
          await page.setViewportSize({ width: viewport.width + 160, height: viewport.height + 100 })
          await expect.poll(async () => (await page.locator('.vue-flow').boundingBox())!.width)
            .toBeGreaterThan(before!.width + 20)
        } else {
          const sashes = page.locator('.dv-sash.dv-enabled')
          const index = await sashes.evaluateAll((elements, edge) => elements.findIndex(element => {
            const rect = element.getBoundingClientRect()
            return rect.height <= 8 && rect.width > 40
              && Math.abs(rect.y + rect.height / 2 - edge.y) < 6
              && rect.left < edge.x && rect.right > edge.x
          }), { x: before!.x + before!.width / 2, y: before!.y + before!.height })
          expect(index).toBeGreaterThanOrEqual(0)
          const sash = await sashes.nth(index).boundingBox()
          expect(sash).not.toBeNull()
          const x = before!.x + before!.width / 2
          const y = sash!.y + sash!.height / 2
          await page.mouse.move(x, y)
          await page.mouse.down()
          await page.mouse.move(x, y - 60, { steps: 8 })
          await page.mouse.up()
          await expect.poll(async () => (await page.locator('.vue-flow').boundingBox())!.height)
            .toBeLessThan(before!.height - 40)
        }
        await page.locator('.vue-flow__controls-fitview').click()
        await expect(expectNodesInView).toPass({ timeout: 5000 })
        for (const item of nodes) {
          await expect(page.locator(`.vue-flow__node[data-id="${item.id}"] .node-name`)).toHaveText(item.name)
          await expect(page.locator(`.vue-flow__node[data-id="${item.id}"] .node-name`)).toBeVisible()
        }
        const retained = await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)
        expect(retained.ok(), await retained.text()).toBe(true)
        expect((await retained.json() as WorkflowFile).graph).toEqual(acceptedGraph)
      })
    } finally {
      await page.request.delete(`${API_BASE}/api/v1/workflows/${name}`)
      await page.request.delete(`${API_BASE}/api/v1/workflows/folders/${folder}`)
    }
  })
}
