import { test, expect } from '@playwright/test'

/**
 * E2E coverage for the graph validation flow.
 *
 * These tests exercise request-local full-graph validation via the canvas.
 * The Playwright backend exposes the dev seed
 * router, so these tests create their own deterministic tool registry.
 */
test.describe('graph validation', () => {
  test.beforeEach(async ({ page }) => {
    const seed = await page.request.post('/api/v1/dev/seed')
    expect(seed.ok()).toBeTruthy()
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await expect(page.locator('.dv-tab').filter({ hasText: 'Tools' })).toBeVisible()
  })

  test('PUT /graph with empty graph returns 200 and valid=true', async ({ page }) => {
    const result = await page.evaluate(async () => {
      const res = await fetch('/api/v1/graph', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes: [], edges: [] }),
      })
      return { status: res.status, body: await res.json() }
    })
    expect(result.status).toBe(200)
    expect(result.body.valid).toBe(true)
  })

  test('request-history parameter PATCH is not exposed', async ({ page }) => {
    const result = await page.evaluate(async () => {
      const res = await fetch('/api/v1/graph/nodes/n1/parameters', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parameters: { x: 1 } }),
      })
      return { status: res.status }
    })
    expect(result.status).toBe(404)
  })

  test('PUT /graph with a tool node returns a node status', async ({ page }) => {
    const tool = await page.evaluate(async () => {
      const res = await fetch('/api/v1/tools')
      const tools = (await res.json()) as Array<{ name: string }>
      return tools.find((candidate) => candidate.name === 'SeedNumbers')
    })
    expect(tool, '/api/v1/dev/seed must register SeedNumbers').toBeTruthy()

    const result = await page.evaluate(async (toolName: string) => {
      const res = await fetch('/api/v1/graph', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [
            {
              id: 'n1',
              name: 'n1',
              tool_name: toolName,
              position: [0, 0],
              parameters: {},
            },
          ],
          edges: [],
        }),
      })
      return { status: res.status, body: await res.json() }
    }, tool!.name)

    expect(result.status).toBe(200)
    expect(result.body.node_statuses).toHaveProperty('n1')
  })

  test('no console errors during validation', async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', (err) => errors.push(err.message))
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })
    await page.evaluate(async () => {
      await fetch('/api/v1/graph', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes: [], edges: [] }),
      })
    })
    expect(errors).toEqual([])
  })
})
