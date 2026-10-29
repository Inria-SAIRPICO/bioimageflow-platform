import { expect, test } from '@playwright/test'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')
const identity = (node: string) => ({ run_id: 'retained-run', node_key: node, result_key: `result-${node}`, record_id: `record-${node}` })

for (const mode of ['paginated', 'continuous'] as const) {
  test(`${mode} virtual rows reuse four previews and preserve a pinned window`, async ({ page }) => {
    // Forty-eight tiny response rows cross one 32-row block. Only four 1px PNG
    // responses exist; no scientific environment or bulk image work runs.
    const name = `small_window_${mode}_${test.info().project.name}_${Date.now()}`
    const settings = await (await page.request.get(`${API}/settings`)).json()
    const previousMode = (settings.settings ?? settings).node_data_browsing_mode ?? 'paginated'
    expect((await page.request.post(`${API}/dev/seed`)).ok()).toBeTruthy()
    expect((await page.request.patch(`${API}/settings`, { data: { node_data_browsing_mode: mode } })).ok()).toBeTruthy()
    expect((await page.request.post(`${API}/workflows`, { data: { name } })).ok()).toBeTruthy()
    let viewerReads = 0
    const previews: { row: number; identity: unknown }[] = []
    const queries: Record<string, any>[] = []
    try {
      expect((await page.request.put(`${API}/workflows/${name}`, { data: { graph: {
        schema_version: 2, name, display_name: name,
        nodes: [
          { type: 'tool', id: 'seed', name: 'Seed', tool_name: 'SeedNumbers', position: [100, 160], parameters: {} },
          { type: 'tool', id: 'child', name: 'Measurements', tool_name: 'IncrementNumbers', position: [400, 160], parameters: {} },
        ], edges: [{ type: 'dataframe', id: 'input', source_node: 'seed', target_node: 'child', target_position: 0 }],
        interface: { inputs: [], outputs: [] }, config: { engine: 'direct', execution: 'sequential' },
      } } })).ok()).toBeTruthy()
      await page.route('**/api/v1/data-table/query', async route => {
        const request = route.request().postDataJSON()
        queries.push(request)
        const imageContext = request.sources.some((source: { node_id: string }) => source.node_id === 'seed')
        const start = request.page * request.page_size
        await route.fulfill({ json: {
          mode: 'merged', sources: request.sources.map((source: { node_id: string }) => ({ ...source, result_identity: identity(source.node_id) })),
          columns: [
            { id: 'value', label: 'Measurement', type: 'int', source_node_id: 'child', source_column: 'number', viewer: null, viewer_status: 'captured' },
            ...(imageContext ? [{ id: 'image', label: 'Parent image', type: 'Path', source_node_id: 'seed', source_column: 'path', viewer: null, viewer_status: 'captured' }] : []),
          ],
          rows: Array.from({ length: Math.max(0, Math.min(request.page_size, 48 - start)) }, (_, offset) => {
            const index = start + offset
            return { index: String(index), values: { value: index, image: `/fixture/image-${index % 4}.tif` }, source_rows: { child: index, seed: index % 4 } }
          }),
          total_rows: 48, unfiltered_total_rows: 48, page: request.page, page_size: request.page_size,
        } })
      })
      await page.route('**/api/v1/napari/resolve', async route => {
        viewerReads += 1
        await route.fulfill({ status: 500, json: { detail: 'No passive viewer resolution is allowed' } })
      })
      await page.route('**/api/v1/nodes/seed/thumbnail?**', async route => {
        const url = new URL(route.request().url())
        previews.push({ row: Number(url.searchParams.get('row')), identity: JSON.parse(url.searchParams.get('result_identity') ?? 'null') })
        await route.fulfill({ contentType: 'image/png', body: png, headers: { 'X-Thumbnail-Status': 'ready', 'X-Thumbnail-Environment': 'idle' } })
      })
      await page.goto('/')
      await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
      await page.getByTestId('workflow-search').fill(name)
      await page.getByTestId(`workflow-row-${name}`).dblclick()
      await expect(page.getByTestId('workflow-title')).toHaveText(name)
      await page.locator('.vue-flow__node[data-id="child"]').click()
      await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
      const depth = page.getByTestId('upstream-depth').locator('input')
      await depth.fill('1')
      await depth.press('Tab')
      const table = page.getByTestId('merged-data-table')
      const viewport = table.getByTestId('node-data-viewport')
      await expect(table.getByRole('columnheader', { name: /Parent image/ })).toBeVisible()
      await expect(table.getByTestId('image-thumbnail').first()).toHaveAttribute('src', /^blob:/)
      const mounted = table.locator('tr[data-virtual-index]')
      expect(await mounted.count()).toBeLessThan(48)
      for (let step = 0; step < 5; step += 1) {
        await viewport.evaluate((element, target) => { element.scrollTop = target }, step * 110)
        await expect.poll(() => previews.some(read => read.row === step % 4)).toBe(true)
      }
      await expect.poll(() => new Set(previews.map(read => read.row)).size).toBe(4)
      expect(previews).toHaveLength(4)
      expect(previews.every(read => JSON.stringify(read.identity) === JSON.stringify(identity('seed')))).toBe(true)
      expect(viewerReads).toBe(0)
      if (mode === 'continuous') {
        await expect(table.getByTestId('continuous-row-count')).toContainText('48 rows')
        await viewport.evaluate(element => { element.scrollTop = element.scrollHeight })
        await expect.poll(() => queries.some(query => query.page === 1)).toBe(true)
        const next = queries.find(query => query.page === 1)!
        expect(next.sources.every((source: { result_identity: unknown }) => source.result_identity)).toBe(true)
        await expect(table.locator('tr[data-virtual-index="47"]')).toContainText('47')
        await viewport.evaluate(element => { element.scrollTop = 0 })
        await expect(table.locator('tr[data-virtual-index="0"]')).toContainText('0')
        expect(previews).toHaveLength(4)
      } else await expect(table.getByTestId('node-data-paginator')).toBeVisible()
      const before = previews.length
      await table.getByRole('button', { name: 'Refresh data', exact: true }).click()
      await expect.poll(() => previews.length).toBeGreaterThan(before)
      expect(viewerReads).toBe(0)
    } finally {
      await page.goto('about:blank')
      await page.unrouteAll({ behavior: 'wait' })
      expect((await page.request.patch(`${API}/settings`, { data: { node_data_browsing_mode: previousMode } })).ok()).toBeTruthy()
      expect((await page.request.delete(`${API}/workflows/${name}`)).ok()).toBeTruthy()
    }
  })
}
