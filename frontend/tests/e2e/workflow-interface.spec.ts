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
    config: { engine: 'direct', execution: 'parallel' },
  }
}

function graphWithExposedOutput(name: string, displayName: string): GraphState {
  const result = graph(name, displayName)
  result.nodes.push({
    type: 'tool',
    id: 'blur_2',
    name: 'Gaussian Blur 2',
    tool_name: 'GaussianBlur',
    position: [520, 160],
    parameters: { input_image: '/tmp/e2e-input.tif' },
  })
  result.interface.outputs.push({
    id: 'blurred-output',
    name: 'Blurred image',
    schema: { type: 'ImageFile' },
    source: { node: 'blur_1', column: 'output_image' },
  })
  return result
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
  ))
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
  const response = await saved
  expect(response.ok(), await response.text()).toBeTruthy()
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
    await expect(page.getByTestId('workflow-title')).not.toContainText('*')

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

  test('publishes multiple DataFrames and compacts slots without changing surviving IDs or edges', async ({ page }) => {
    const name = workflowName('dataframe_interface')
    const displayName = `DataFrames ${name}`
    await createWorkflow(page, name, displayName)
    const initial = graph(name, displayName)
    initial.nodes = [{
      type: 'tool', id: 'increment', name: 'Increment', tool_name: 'IncrementNumbers',
      position: [400, 160], parameters: { number: 1 },
    }, {
      type: 'tool', id: 'seed', name: 'Seed', tool_name: 'SeedNumbers',
      position: [50, 160], parameters: {},
    }]
    expect((await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
      data: { graph: initial },
    })).ok()).toBeTruthy()
    await page.goto('/')
    await openWorkflow(page, name, displayName)
    await page.locator('.vue-flow__node[data-id="increment"]').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    for (let index = 0; index < 3; index++) {
      await page.getByTestId('publish-dataframe-input').click()
      await expect(page.getByTestId(`dataframe-input-name-${index}`)).toBeVisible()
    }
    await page.getByTestId('dataframe-input-name-2').fill('Last table')
    await saveWorkflow(page, name)
    const first = await savedGraph(page, name)
    expect(first.interface.inputs.map(input => input.targets[0]?.port)).toEqual([
      { kind: 'positional', index: 0 }, { kind: 'positional', index: 1 }, { kind: 'positional', index: 2 },
    ])
    expect(first.interface.inputs.every(input => input.kind === 'dataframe')).toBe(true)

    // A connected slot after the publications must move with them on unpublish.
    const source = await page.locator('.vue-flow__node[data-id="seed"] [data-handleid="bif:v1:dataframe-output"]').boundingBox()
    const target = await page.locator('.vue-flow__node[data-id="increment"] [data-handleid="bif:v1:dataframe-position:3"]').boundingBox()
    if (!source || !target) throw new Error('Expected DataFrame handles')
    await page.mouse.move(source.x + source.width / 2, source.y + source.height / 2)
    await page.mouse.down()
    await page.mouse.move(target.x + target.width / 2, target.y + target.height / 2, { steps: 10 })
    await page.mouse.up()
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)
    await expect(page.getByTestId('dataframe-input-name-2')).toHaveValue('Last table')
    await page.getByTestId('unpublish-dataframe-1').click()
    await expect(page.getByTestId('dataframe-input-name-1')).toHaveValue('Last table')
    await expect(page.getByTestId('dataframe-input-name-2')).toHaveCount(0)
    await page.getByRole('menuitem', { name: 'Edit', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Undo', exact: true }).click()
    await expect(page.getByTestId('dataframe-input-name-2')).toHaveValue('Last table')
    await page.getByRole('menuitem', { name: 'Edit', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Redo', exact: true }).click()
    await expect(page.getByTestId('dataframe-input-name-1')).toHaveValue('Last table')
    await saveWorkflow(page, name)
    const saved = await savedGraph(page, name)
    expect(saved.interface.inputs.map(input => input.id)).toEqual([first.interface.inputs[0]!.id, first.interface.inputs[2]!.id])
    expect(saved.interface.inputs[1]).toMatchObject({ name: 'Last table', targets: [{ node: 'increment', port: { kind: 'positional', index: 1 } }] })
    expect(saved.edges[0]).toMatchObject({ type: 'dataframe', target_node: 'increment', target_position: 2 })
    await page.reload()
    await openWorkflow(page, name, displayName)
    await page.locator('.vue-flow__node[data-id="increment"]').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    await expect(page.getByTestId('dataframe-input-name-1')).toHaveValue('Last table')
  })

  test('publishes an existing child DataFrame port through the parent interface', async ({ page }) => {
    const name = workflowName('forward_dataframe')
    const displayName = `Forward ${name}`
    await createWorkflow(page, name, displayName)
    const child = graph('child', 'Child')
    child.nodes = [{ type: 'tool', id: 'increment', name: 'Increment', tool_name: 'IncrementNumbers', position: [180, 160], parameters: { number: 1 } }]
    const parent = graph(name, displayName)
    parent.nodes = [{ type: 'workflow', id: 'child', name: 'Child', position: [180, 160], workflow: child, bindings: {} }]
    const setup = await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, { data: { graph: parent } })
    expect(setup.ok(), await setup.text()).toBeTruthy()
    await page.goto('/')
    await openWorkflow(page, name, displayName)
    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    await page.locator('.vue-flow__node[data-id="increment"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    await page.getByTestId('publish-dataframe-input').click()
    await page.getByTestId('dataframe-input-name-0').fill('Source table')
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await expect(page.getByTestId('workflow-title')).not.toContainText('*')
    await page.locator('.dv-tab').getByText(displayName, { exact: true }).click()
    await saveWorkflow(page, name)
    const savedChild = (await savedGraph(page, name)).nodes[0]!
    if (savedChild.type !== 'workflow') throw new Error('Expected child workflow')
    const childPortId = savedChild.workflow.interface.inputs[0]!.id
    await page.locator('.vue-flow__node[data-id="child"]').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    await page.getByRole('button', { name: 'Publish DataFrame input: Source table', exact: true }).click()
    await page.getByTestId(`dataframe-input-name-${childPortId}`).fill('Parent table')
    await saveWorkflow(page, name)
    expect((await savedGraph(page, name)).interface.inputs[0]).toMatchObject({
      kind: 'dataframe', name: 'Parent table', targets: [{ node: 'child', port: { kind: 'workflow', id: childPortId } }],
    })
    await page.getByTestId(`unpublish-dataframe-${childPortId}`).click()
    await expect(page.getByRole('button', { name: 'Publish DataFrame input: Source table', exact: true })).toBeVisible()
    await saveWorkflow(page, name)
    expect((await savedGraph(page, name)).interface.inputs).toEqual([])
  })

  test('deleting an exposed node removes its interface references before autosave', async ({
    page,
  }) => {
    const name = workflowName('delete_exposed')
    const displayName = `Delete exposed ${name}`
    await createWorkflow(page, name, displayName)
    expect((await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
      data: { graph: graphWithExposedOutput(name, displayName) },
    })).ok()).toBeTruthy()
    await page.goto('/')
    await openWorkflow(page, name, displayName)

    await page.locator('.vue-flow__node[data-id="blur_1"]').click()
    const acceptedDeletion = page.waitForResponse(response => (
      response.url().includes(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT'
    ))
    await page.locator('.canvas-view').press('Delete')
    const deletionResponse = await acceptedDeletion

    expect(deletionResponse.status(), await deletionResponse.text()).toBe(200)
    await expect(page.locator('.vue-flow__node[data-id="blur_1"]')).toHaveCount(0)
    await expect(page.getByTestId('canvas-persistence-issue')).toHaveCount(0)
    await saveWorkflow(page, name)

    const saved = await savedGraph(page, name)
    expect(saved.nodes.map(node => node.id)).toEqual(['blur_2'])
    expect(saved.interface.outputs).toEqual([])
  })
})
