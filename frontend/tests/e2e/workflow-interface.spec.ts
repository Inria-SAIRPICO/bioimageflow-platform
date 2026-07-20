import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import type { GraphState } from '../../src/api/types'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

function workflowName(prefix: string): string {
  return `${prefix}_${test.info().project.name}_${Date.now()}`.replace(/[^a-zA-Z0-9_-]/g, '_')
}

function graph(name: string, displayName: string): GraphState {
  return {
    schema_version: 1,
    name,
    display_name: displayName,
    nodes: [{
      type: 'tool',
      id: 'blur_1',
      name: 'Gaussian Blur',
      tool_name: 'GaussianBlur',
      position: [180, 160],
      parameters: { input_image: '/tmp/e2e-input.tif' },
    }],
    edges: [],
    interface: { inputs: [], outputs: [] },
    config: { storage_path: './bif_data', engine: 'direct', execution: 'parallel' },
  }
}

async function createWorkflow(page: Page, name: string, displayName: string): Promise<void> {
  await page.request.delete(`${API_BASE}/api/v1/workflows/${name}`).catch(() => undefined)
  expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
    data: { name, display_name: displayName },
  })).status()).toBe(201)
  expect((await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
    data: { graph: graph(name, displayName) },
  })).ok()).toBeTruthy()
}

async function openWorkflow(page: Page, name: string, displayName: string): Promise<void> {
  await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
  await page.getByTestId('workflow-search').fill(displayName)
  await page.getByTestId(`workflow-row-${name}`).dblclick()
  await expect(page.getByTestId('workflow-title')).toContainText(displayName)
}

async function saveWorkflow(page: Page, name: string): Promise<void> {
  const saved = page.waitForResponse(response => (
    response.url().includes(`/api/v1/workflows/${name}`)
    && response.request().method() === 'PUT'
    && response.ok()
  ))
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
  await saved
}

async function savedGraph(page: Page, name: string): Promise<GraphState> {
  const response = await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)
  expect(response.ok()).toBeTruthy()
  return (await response.json()).graph as GraphState
}

test.describe('workflow interface and grouping', () => {
  test.beforeEach(async ({ page }) => {
    expect((await page.request.post(`${API_BASE}/api/v1/dev/seed`)).ok()).toBeTruthy()
  })

  test('exposes and renames stable interface ports', async ({ page }) => {
    const name = workflowName('interface')
    const displayName = `Interface ${name}`
    await createWorkflow(page, name, displayName)
    await page.goto('/')
    await openWorkflow(page, name, displayName)
    await page.locator('.vue-flow__node[data-id="blur_1"]').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()

    await page.getByTestId('interface-input-toggle-input_image').click()
    const inputName = page.getByTestId('workflow-input-name-input_image')
    await inputName.fill('Source image')
    await page.getByTestId('interface-output-toggle-output_image').click()
    await page.getByTestId('workflow-output-name-output_image').fill('Blurred image')
    await saveWorkflow(page, name)

    const first = await savedGraph(page, name)
    expect(first.interface.inputs[0]).toMatchObject({
      name: 'Source image',
      targets: [{ node: 'blur_1', port: { kind: 'field', name: 'input_image' } }],
    })
    expect(first.interface.outputs[0]).toMatchObject({
      name: 'Blurred image', source: { node: 'blur_1', column: 'output_image' },
    })
    const inputId = first.interface.inputs[0].id

    await inputName.fill('Image to blur')
    await saveWorkflow(page, name)
    expect((await savedGraph(page, name)).interface.inputs[0]).toMatchObject({
      id: inputId, name: 'Image to blur',
    })
  })

  test('groups a selected tool into an ordinary workflow node', async ({ page }) => {
    const name = workflowName('group')
    const displayName = `Group ${name}`
    await createWorkflow(page, name, displayName)
    await page.goto('/')
    await openWorkflow(page, name, displayName)

    const node = page.locator('.vue-flow__node[data-id="blur_1"]')
    await node.click()
    await node.click({ button: 'right' })
    await page.getByText('Group into workflow', { exact: true }).click()
    await saveWorkflow(page, name)

    const saved = await savedGraph(page, name)
    expect(saved.nodes).toHaveLength(1)
    expect(saved.nodes[0].type).toBe('workflow')
    if (saved.nodes[0].type !== 'workflow') throw new Error('expected workflow node')
    expect(saved.nodes[0].workflow.nodes[0]).toMatchObject({ id: 'blur_1', type: 'tool' })
  })
})
