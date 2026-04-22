import { test, expect } from '@playwright/test'

/**
 * E2E coverage for the graph validation flow.
 *
 * These tests exercise the PUT /graph and PATCH /graph/nodes/{id}/parameters
 * endpoints via the canvas. They rely on at least one tool being installed
 * in the backend's tool registry; if no tools are present the tests are
 * skipped (rather than failing).
 */
test.describe('graph validation', () => {
  test.beforeEach(async ({ page }) => {
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

  test('PATCH without tool_name returns 400', async ({ page }) => {
    const result = await page.evaluate(async () => {
      const res = await fetch('/api/v1/graph/nodes/n1/parameters', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parameters: { x: 1 } }),
      })
      return { status: res.status }
    })
    expect(result.status).toBe(400)
  })

  test('PATCH with binding-shaped parameter is rejected', async ({ page }) => {
    const result = await page.evaluate(async () => {
      const res = await fetch(
        '/api/v1/graph/nodes/n1/parameters?tool_name=AnyTool',
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            parameters: { x: { node_id: 'u', output: 'mask' } },
          }),
        },
      )
      return { status: res.status }
    })
    expect(result.status).toBe(400)
  })

  test('PUT /graph with a tool node returns a node status', async ({ page }) => {
    // Look up the first installed tool; skip the test if none exist.
    const tool = await page.evaluate(async () => {
      const res = await fetch('/api/v1/tools')
      const tools = await res.json()
      return Array.isArray(tools) && tools.length > 0 ? tools[0] : null
    })
    test.skip(tool === null, 'no tools installed in backend')

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
    }, tool.name)

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
