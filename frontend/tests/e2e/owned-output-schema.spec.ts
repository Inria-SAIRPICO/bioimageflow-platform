import { expect, test } from '@playwright/test'
import { writeFileSync } from 'node:fs'
import { basename } from 'node:path'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`

test('owned dynamic output schemas resolve on Open, parameter edits and reload without execution', async ({ page }) => {
  const name = `owned_schema_${test.info().project.name}_${Date.now()}`
  const className = `OwnedSchema${Date.now()}`
  expect((await page.request.post(`${API}/workflows`, { data: { name } })).ok()).toBeTruthy()
  try {
    const created = await page.request.post(`${API}/tools`, {
      params: { workflow_name: name }, data: { name: className, tool_type: 'DataFrameTool' },
    })
    expect(created.ok(), await created.text()).toBeTruthy()
    const path = (await created.json()).path as string
    writeFileSync(path, `from bioimageflow import DataFrameTool
from bioimageflow_core import IOModel
class ${className}(DataFrameTool):
    accepts_upstream = False
    class Inputs(IOModel):
        column_name: str = "sensitivity"
    @classmethod
    def resolve_outputs(cls, inputs=None):
        return {(inputs or {}).get("column_name", "sensitivity"): {"type": "int"}}
    def transform(self, df, arguments):
        raise AssertionError("Schema inspection must not execute")
`)
    const saved = await (await page.request.get(`${API}/workflows/${name}`)).json()
    saved.graph.nodes = [{
      type: 'tool', id: 'values', name: 'Values', tool_name: className,
      tool_module: `tools.${basename(path, '.py')}`, tool_class: className,
      position: [200, 160], parameters: { column_name: 'sensitivity' },
    }]
    saved.graph.config = { engine: 'direct', execution: 'sequential' }
    expect((await page.request.put(`${API}/workflows/${name}`, { data: { graph: saved.graph } })).ok()).toBeTruthy()
    const failures: number[] = []
    page.on('response', response => {
      if (response.url().includes('/output_schema') && !response.ok()) failures.push(response.status())
    })
    const schemaResponse = page.waitForResponse(response => response.url().endsWith('/nodes/values/output_schema'))
    await page.goto('/')
    await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
    await page.getByTestId('workflow-search').fill(name)
    await page.getByTestId(`workflow-row-${name}`).dblclick()
    const schema = await schemaResponse
    expect(schema.status()).toBe(200)
    expect(schema.request().postDataJSON().workflow_name).toBe(name)
    expect(await schema.json()).toMatchObject({ resolved: true, columns: { sensitivity: { type: 'int' } } })
    const node = page.locator('.vue-flow__node[data-id="values"]')
    await expect(node.locator('.body-outputs .pin-label')).toContainText('sensitivity')
    await node.click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const input = page.getByTestId('panel-nodePanel').locator('.param-row').filter({ hasText: 'column_name' }).locator('input')
    await input.fill('size')
    await input.press('Tab')
    await expect(node.locator('.body-outputs .pin-label')).toContainText('size')
    await expect.poll(async () => {
      const draft = await (await page.request.get(`${API}/workflow-drafts/${name}`)).json()
      return draft.graph.nodes.find((candidate: { id: string }) => candidate.id === 'values')?.parameters.column_name
    }).toBe('size')
    await page.reload()
    await expect(node.locator('.body-outputs .pin-label')).toContainText('size')
    expect(failures).toEqual([])
    const history = await (await page.request.get(`${API}/executions`, { params: { workflow_id: name } })).json()
    expect(history.executions ?? history.items ?? history).toEqual([])
  } finally {
    await page.goto('about:blank')
    expect((await page.request.delete(`${API}/workflows/${name}`)).ok()).toBeTruthy()
  }
})
