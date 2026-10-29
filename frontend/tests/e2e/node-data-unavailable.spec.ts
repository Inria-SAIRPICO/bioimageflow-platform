import { expect, test } from '@playwright/test'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`

test('a rejected saved result shows an immediate persistent error without polling', async ({ page }) => {
  const name = `unavailable_data_${test.info().project.name}_${Date.now()}`
  expect((await page.request.post(`${API}/dev/seed`)).ok()).toBeTruthy()
  expect((await page.request.post(`${API}/workflows`, { data: { name } })).ok()).toBeTruthy()
  let queries = 0
  const detail = 'Saved output cannot be read: Invalid record manifest schema. Re-run this node to regenerate its output.'
  try {
    const document = await (await page.request.get(`${API}/workflows/${name}`)).json()
    document.graph.nodes = [{
      type: 'tool', id: 'seed', name: 'Seed', tool_name: 'SeedNumbers',
      position: [180, 160], parameters: {},
    }]
    document.graph.config = { engine: 'direct', execution: 'sequential' }
    expect((await page.request.put(`${API}/workflows/${name}`, { data: { graph: document.graph } })).ok()).toBeTruthy()
    await page.route('**/api/v1/data-table/query', async route => {
      if (route.request().postDataJSON().workflow_id !== name) return route.continue()
      queries += 1
      await route.fulfill({ status: 409, json: { error: 'result_unavailable', detail } })
    })
    await page.goto('/')
    await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
    await page.getByTestId('workflow-search').fill(name)
    await page.getByTestId(`workflow-row-${name}`).dblclick()
    await expect(page.getByTestId('workflow-title')).toHaveText(name)
    await page.locator('.vue-flow__node[data-id="seed"]').click()
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    await expect(page.locator('.data-table-panel__error')).toHaveText(detail)
    await expect(page.getByText('Loading consolidated data...', { exact: true })).toHaveCount(0)
    const completedQueries = queries
    expect(completedQueries).toBeGreaterThan(0)
    await page.waitForTimeout(1_500)
    expect(queries).toBe(completedQueries)
    await expect(page.locator('.data-table-panel__error')).toHaveText(detail)
  } finally {
    await page.goto('about:blank')
    await page.unrouteAll({ behavior: 'wait' })
    expect((await page.request.delete(`${API}/workflows/${name}`)).ok()).toBeTruthy()
  }
})
