import { expect, test } from '@playwright/test'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')

test('cold thumbnail setup stays visible beyond the former deadline and completes automatically', async ({ page }) => {
  const name = `pending_thumbnail_${test.info().project.name}_${Date.now()}`
  expect((await page.request.post(`${API}/dev/seed`)).ok()).toBeTruthy()
  expect((await page.request.post(`${API}/workflows`, { data: { name } })).ok()).toBeTruthy()
  let ready = false
  let requests = 0
  try {
    const document = await (await page.request.get(`${API}/workflows/${name}`)).json()
    document.graph.nodes = [{ type: 'tool', id: 'seed', name: 'Seed', tool_name: 'SeedNumbers', position: [180, 160], parameters: {} }]
    expect((await page.request.put(`${API}/workflows/${name}`, { data: { graph: document.graph } })).ok()).toBeTruthy()
    await page.route('**/api/v1/data-table/query', async route => {
      const request = route.request().postDataJSON()
      await route.fulfill({ json: {
        mode: 'merged', sources: request.sources,
        columns: [{ id: 'path', label: 'Path', type: 'Path', source_node_id: 'seed', source_column: 'path', viewer: null, viewer_status: 'legacy_unpinned' }],
        rows: [{ index: '0', values: { path: '/fixture.tif' }, source_rows: { seed: 0 } }],
        total_rows: 1, unfiltered_total_rows: 1, page: 0, page_size: 250,
      } })
    })
    await page.route('**/api/v1/nodes/seed/thumbnail?**', async route => {
      requests += 1
      await route.fulfill({ contentType: 'image/png', body: png, headers: {
        'X-Thumbnail-Status': ready ? 'ready' : 'pending',
        'X-Thumbnail-Environment': ready ? 'ready' : 'installing',
        'Cache-Control': 'no-store',
      } })
    })
    await page.goto('/')
    await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
    await page.getByTestId('workflow-search').fill(name)
    await page.getByTestId(`workflow-row-${name}`).dblclick()
    await page.locator('.vue-flow__node[data-id="seed"]').click()
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    const notice = page.getByTestId('thumbnail-installation-status')
    const thumbnail = page.getByTestId('merged-data-table').getByTestId('image-thumbnail')
    await expect(notice).toContainText('First-time setup may take several minutes')
    await page.clock.install()
    for (let attempt = 0; attempt < 6; attempt += 1) {
      const before = requests
      await page.clock.fastForward(15_000)
      await expect.poll(() => requests).toBeGreaterThan(before)
      await expect(thumbnail).toHaveAttribute('aria-label', 'thumbnail generating')
    }
    ready = true
    await page.clock.fastForward(15_000)
    await expect(thumbnail).toHaveAttribute('src', /^blob:/)
    await expect(notice).toHaveCount(0)
    const completed = requests
    await page.clock.fastForward(60_000)
    expect(requests).toBe(completed)
  } finally {
    await page.goto('about:blank')
    await page.unrouteAll({ behavior: 'wait' })
    expect((await page.request.delete(`${API}/workflows/${name}`)).ok()).toBeTruthy()
  }
})
