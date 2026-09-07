import { expect, test, type Page } from '@playwright/test'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`
const labels = ['A very long numerical measurement column', 'Flag', 'Description']

async function openData(page: Page, name: string) {
  await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
  await page.getByTestId('workflow-search').fill(name)
  await page.getByTestId(`workflow-row-${name}`).dblclick()
  await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
  // A restored canvas can finish replacing its initial nodes after the tab appears.
  await expect(async () => {
    await page.locator('.vue-flow__node[data-id="seed"]').click()
    await expect(page.getByRole('separator', { name: `Resize ${labels[0]}` })).toBeVisible({ timeout: 1000 })
  }).toPass({ timeout: 10000 })
}

for (const mode of ['stacked', 'merged'] as const) {
  test(`${mode} Node Data sizes, resizes and restores columns without overlapping controls`, async ({ page }) => {
    const name = `widths_${mode}_${test.info().project.name}_${Date.now()}`
    expect((await page.request.post(`${API_BASE}/api/v1/dev/seed`)).ok()).toBeTruthy()
    expect((await page.request.post(`${API_BASE}/api/v1/workflows`, { data: { name, display_name: name } })).ok()).toBeTruthy()
    expect((await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, { data: { graph: {
      schema_version: 1, name, display_name: name,
      nodes: [{ type: 'tool', id: 'seed', name: 'Seed', tool_name: 'SeedNumbers', position: [180, 160], parameters: {} }],
      edges: [], interface: { inputs: [], outputs: [] }, config: { engine: 'direct', execution: 'parallel' },
    } } })).ok()).toBeTruthy()
    await page.route('**/api/v1/data-table/query', async route => {
      const request = route.request().postDataJSON()
      await route.fulfill({ json: mode === 'stacked' ? {
        mode, sources: request.sources, reason: 'test', message: 'Separate table',
      } : {
        mode, sources: request.sources,
        columns: labels.map((label, index) => ({ id: label, label, type: index === 0 ? 'int' : index === 1 ? 'bool' : 'str', source_node_id: 'seed', source_column: label })),
        rows: [{ index: '0', values: { [labels[0]!]: 12, Flag: true, Description: 'A useful descriptive result value' }, source_rows: { seed: 0 } }],
        total_rows: 1, unfiltered_total_rows: 1, page: 0, page_size: 250,
      } })
    })
    await page.route('**/api/v1/nodes/seed/data/query', async route => route.fulfill({ json: {
      columns: labels, column_types: { [labels[0]!]: 'int', Flag: 'bool', Description: 'str' },
      rows: [{ [labels[0]!]: 12, Flag: true, Description: 'A useful descriptive result value' }],
      absolute_rows: [0], total_rows: 1, unfiltered_total_rows: 1, page: 0, page_size: 250,
    } }))
    await page.goto('/')
    await openData(page, name)
    const grid = page.locator('.node-data-sized-grid:visible')
    const headers = grid.locator('thead th')
    const first = headers.nth(0)
    const second = headers.nth(1)
    const separator = page.getByRole('separator', { name: `Resize ${labels[0]}` })
    await separator.hover()
    await expect(grid.locator('.p-datatable-mask')).toHaveCount(0)
    await expect.poll(async () => (await first.boundingBox())!.width).toBeGreaterThan(300)
    const initial = (await first.boundingBox())!.width
    const adjacent = (await second.boundingBox())!.width
    await expect(page.getByRole('button', { name: 'Fit', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Auto', exact: true })).toHaveCount(0)
    expect(await page.evaluate(() => Object.keys(localStorage).filter(key => key.startsWith('bif-node-data-widths-v2:')))).toEqual([])
    const box = (await separator.boundingBox())!
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
    await page.mouse.down()
    await page.mouse.move(box.x + box.width / 2 - initial + 120, box.y + box.height / 2, { steps: 8 })
    await page.mouse.up()
    await expect.poll(async () => Math.round((await first.boundingBox())!.width)).toBe(120)
    expect((await second.boundingBox())!.width).toBeCloseTo(adjacent, 0)
    const bounds = await first.evaluate(element => {
      const label = element.querySelector('.node-data-column-header__labels')!.getBoundingClientRect()
      const sort = element.querySelector('.node-data-column-header__sort i')!.getBoundingClientRect()
      const filter = element.querySelector('[aria-label^="Filter"]')!.getBoundingClientRect()
      return { labelEnd: label.right, sortStart: sort.left, sortEnd: sort.right, filterStart: filter.left }
    })
    expect(bounds.labelEnd).toBeLessThanOrEqual(bounds.sortStart)
    expect(bounds.sortEnd).toBeLessThanOrEqual(bounds.filterStart)
    const color = await separator.evaluate(element => getComputedStyle(element, '::after').backgroundColor)
    expect(color).not.toBe('rgba(0, 0, 0, 0)')
    await page.screenshot({ path: test.info().outputPath('columns-light.png') })
    await page.getByRole('button', { name: /^Theme:/ }).click()
    await page.getByRole('menuitem', { name: 'Dark', exact: true }).click()
    await expect(page.getByRole('menuitem', { name: 'Dark', exact: true })).toBeHidden()
    const darkColor = await separator.evaluate(element => getComputedStyle(element, '::after').backgroundColor)
    expect(darkColor).not.toBe('rgba(0, 0, 0, 0)')
    expect(darkColor).not.toBe(color)
    await page.screenshot({ path: test.info().outputPath('columns-dark.png') })
    await page.reload()
    await openData(page, name)
    await expect.poll(async () => Math.round((await first.boundingBox())!.width)).toBe(120)
    await separator.focus()
    await separator.press('ArrowRight')
    await expect.poll(async () => Math.round((await first.boundingBox())!.width)).toBe(130)
    await separator.press('ArrowRight')
    await expect.poll(async () => Math.round((await first.boundingBox())!.width)).toBe(140)
    await separator.dblclick()
    await expect.poll(async () => (await first.boundingBox())!.width).toBeCloseTo(initial, 0)
    await page.setViewportSize({ width: 900, height: 800 })
    await expect.poll(async () => grid.locator('.p-datatable-table-container').evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true)
    expect((await first.boundingBox())!.width).toBeCloseTo(initial, 0)
    await separator.press('ArrowRight')
    await page.getByRole('button', { name: 'Reset column widths', exact: true }).click()
    await expect.poll(async () => (await first.boundingBox())!.width).toBeCloseTo(initial, 0)
    await page.getByRole('button', { name: `Filter ${labels[0]}` }).click()
    await expect(page.getByRole('combobox', { name: 'Filter operator' })).toBeVisible()
  })
}
