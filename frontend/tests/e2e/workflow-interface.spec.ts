import { expect, test } from '@playwright/test'
import type { Page, Response } from '@playwright/test'
import type { GraphState } from '../../src/api/types'
import type { WorkflowDraftResponse } from '../../src/api/workflowDrafts'

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
  result.interface.inputs.push({
    id: 'shared-image-input', name: 'Shared image', kind: 'field',
    schema: { type: 'ImageFile' }, default: null,
    targets: [
      { node: 'blur_1', port: { kind: 'field', name: 'input_image' } },
      { node: 'blur_2', port: { kind: 'field', name: 'input_image' } },
    ],
  }, {
    id: 'removed-sigma-input', name: 'Removed sigma', kind: 'field',
    schema: { type: 'float' }, default: null,
    targets: [{ node: 'blur_1', port: { kind: 'field', name: 'sigma' } }],
  })
  return result
}

function groupingBoundaryGraph(name: string, displayName: string): GraphState {
  return {
    schema_version: 1,
    name,
    display_name: displayName,
    nodes: [{
      type: 'tool', id: 'table_before', name: 'Table before', tool_name: 'SeedNumbers',
      position: [60, 120], parameters: {},
    }, {
      type: 'tool', id: 'table_first', name: 'Table first', tool_name: 'IncrementNumbers',
      position: [340, 120], parameters: { number: 1 },
    }, {
      type: 'tool', id: 'table_second', name: 'Table second', tool_name: 'IncrementAgainNumbers',
      position: [600, 120], parameters: { number_plus_one: 2 },
    }, {
      type: 'tool', id: 'table_after', name: 'Table after', tool_name: 'IncrementAgainNumbers',
      position: [860, 120], parameters: { number_plus_one: 2 },
    }, {
      type: 'tool', id: 'field_before', name: 'Field before', tool_name: 'GaussianBlur',
      position: [200, 400], parameters: { input_image: '/tmp/group-before.tif', sigma: 1 },
      output_templates: { output_image: '' },
    }, {
      type: 'tool', id: 'field_middle', name: 'Field middle', tool_name: 'GaussianBlur',
      position: [480, 400], parameters: { sigma: 1 },
      output_templates: { output_image: '' },
    }, {
      type: 'tool', id: 'field_after', name: 'Field after', tool_name: 'GaussianBlur',
      position: [760, 400], parameters: { sigma: 1 },
      output_templates: { output_image: '' },
    }],
    edges: [{
      type: 'dataframe', id: 'table-in', source_node: 'table_before',
      target_node: 'table_first', target_position: 0,
    }, {
      type: 'dataframe', id: 'table-internal', source_node: 'table_first',
      target_node: 'table_second', target_position: 0,
    }, {
      type: 'dataframe', id: 'table-out', source_node: 'table_second',
      target_node: 'table_after', target_position: 0,
    }, {
      type: 'column', id: 'field-in', source_node: 'field_before', target_node: 'field_middle',
      source_output: 'output_image', target_input: 'input_image',
    }, {
      type: 'column', id: 'field-out', source_node: 'field_middle', target_node: 'field_after',
      source_output: 'output_image', target_input: 'input_image',
    }],
    interface: { inputs: [], outputs: [] },
    config: { engine: 'wetlands', execution: 'sequential' },
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

async function draftGraph(page: Page, name: string): Promise<GraphState> {
  const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)
  expect(response.ok()).toBeTruthy()
  return ((await response.json()) as WorkflowDraftResponse).graph
}

async function draftState(page: Page, name: string): Promise<WorkflowDraftResponse> {
  const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json() as Promise<WorkflowDraftResponse>
}

async function waitForAcceptedGraph(
  page: Page,
  name: string,
  action: () => Promise<void>,
): Promise<WorkflowDraftResponse> {
  const accepted = page.waitForResponse(response => (
    response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
    && response.request().method() === 'PUT'
    && response.status() === 200
  ))
  await action()
  await accepted
  return draftState(page, name)
}

async function replaceDraftChildInputName(
  page: Page,
  name: string,
  inputName: string,
): Promise<void> {
  const currentResponse = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)
  expect(currentResponse.ok(), await currentResponse.text()).toBeTruthy()
  const current = (await currentResponse.json()) as WorkflowDraftResponse
  const nextGraph = structuredClone(current.graph)
  const input = childNode(nextGraph).workflow.interface.inputs.find(
    candidate => candidate.id === 'child-table-input',
  )
  expect(input).toBeTruthy()
  input!.name = inputName
  const response = await page.request.put(`${API_BASE}/api/v1/workflow-drafts/${name}`, {
    data: {
      graph: nextGraph,
      expected_revision: current.draft_revision,
      updated_by: 'agent',
    },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  expect(childInputName(childNode(
    ((await response.json()) as WorkflowDraftResponse).graph,
  ).workflow)).toBe(inputName)
}

function nestedInterfaceGraph(name: string, displayName: string): GraphState {
  const child: GraphState = {
    schema_version: 1,
    name: 'stable_child',
    display_name: 'Stable child',
    nodes: [{
      type: 'tool',
      id: 'increment',
      name: 'Increment',
      tool_name: 'IncrementNumbers',
      position: [300, 180],
      parameters: { number: 1 },
    }],
    edges: [],
    interface: {
      inputs: [{
        id: 'child-table-input',
        name: 'Source table',
        kind: 'dataframe',
        schema: { type: 'DataFrame' },
        targets: [{ node: 'increment', port: { kind: 'positional', index: 0 } }],
      }, {
        id: 'child-number-input',
        name: 'Number value',
        kind: 'field',
        schema: { type: 'int' },
        targets: [{ node: 'increment', port: { kind: 'field', name: 'number' } }],
      }],
      outputs: [],
    },
    config: { engine: 'direct', execution: 'sequential' },
  }
  return {
    schema_version: 1,
    name,
    display_name: displayName,
    nodes: [{
      type: 'tool',
      id: 'seed',
      name: 'Seed',
      tool_name: 'SeedNumbers',
      position: [80, 180],
      parameters: {},
    }, {
      type: 'workflow',
      id: 'child',
      name: 'Stable child',
      position: [520, 180],
      workflow: child,
      bindings: { 'child-number-input': { __type__: 'int', value: 7 } },
    }],
    edges: [{
      type: 'dataframe',
      id: 'parent-child-edge',
      source_node: 'seed',
      target_node: 'child',
      target_input: 'child-table-input',
    }],
    interface: { inputs: [], outputs: [] },
    config: { engine: 'direct', execution: 'sequential' },
  }
}

function childNode(graph: GraphState) {
  const node = graph.nodes.find(candidate => candidate.id === 'child')
  expect(node?.type).toBe('workflow')
  if (!node || node.type !== 'workflow') throw new Error('Expected child workflow node')
  return node
}

function expectStableParentRoutes(graph: GraphState): void {
  expect(graph.edges).toEqual([{
    type: 'dataframe',
    id: 'parent-child-edge',
    source_node: 'seed',
    target_node: 'child',
    target_position: null,
    target_input: 'child-table-input',
  }])
  expect(childNode(graph).bindings).toEqual({
    'child-number-input': { __type__: 'int', value: 7 },
  })
}

function responseCarriesNestedInputName(response: Response, name: string): boolean {
  if (
    !response.url().includes('/api/v1/nested-workflow-snapshots/')
    || response.request().method() !== 'PUT'
    || response.status() !== 200
  ) return false
  const body = response.request().postDataJSON() as { graph?: GraphState } | null
  return childInputName(body?.graph) === name
}

function responseCarriesNestedInputCount(response: Response, count: number): boolean {
  if (
    !response.url().includes('/api/v1/nested-workflow-snapshots/')
    || response.request().method() !== 'PUT'
    || response.status() !== 200
  ) return false
  const body = response.request().postDataJSON() as { graph?: GraphState } | null
  return body?.graph?.interface.inputs.length === count
}

function responseCarriesEmptyNestedInterface(response: Response): boolean {
  if (!responseCarriesNestedInputCount(response, 0)) return false
  const body = response.request().postDataJSON() as { graph?: GraphState } | null
  return body?.graph?.interface.outputs.length === 0
}

function childInputName(graph: GraphState | undefined): string | undefined {
  return graph?.interface.inputs.find(input => input.id === 'child-table-input')?.name
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

  test('groups connected nodes with stable ports as one durable undo transition @critical', async ({ page }) => {
    const name = workflowName('group_routes')
    const displayName = `Group routes ${name}`
    await createWorkflow(page, name, displayName)
    const fixture = groupingBoundaryGraph(name, displayName)
    const setup = await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
      data: { graph: fixture },
    })
    expect(setup.ok(), await setup.text()).toBeTruthy()
    await page.goto('/')
    await openWorkflow(page, name, displayName)
    const original = await draftState(page, name)
    expect(original.validation).toMatchObject({ valid: true, errors: [] })

    // Dismissing the offered action must leave the accepted graph and history alone.
    await page.locator('.vue-flow__node[data-id="table_first"]').click({ button: 'right' })
    await expect(page.getByText('Group into workflow', { exact: true })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByText('Group into workflow', { exact: true })).toHaveCount(0)
    const afterCancelledMenu = await draftState(page, name)
    expect(afterCancelledMenu.graph).toEqual(original.graph)
    expect(afterCancelledMenu.draft_revision).toBe(original.draft_revision)
    await page.getByRole('menuitem', { name: 'Edit', exact: true }).click()
    await expect(page.getByRole('menuitem', { name: 'Undo', exact: true })).toBeDisabled()
    await page.keyboard.press('Escape')

    await page.locator('.vue-flow__node[data-id="table_first"]').click()
    await page.locator('.vue-flow__node[data-id="table_second"]').click({ modifiers: ['Shift'] })
    await page.locator('.vue-flow__node[data-id="field_middle"]').click({ modifiers: ['Shift'] })
    await expect(page.locator('.vue-flow__node.selected')).toHaveCount(3)
    let draftWrites = 0
    await page.route(`**/api/v1/workflow-drafts/${name}`, async (route) => {
      if (route.request().method() !== 'PUT') return route.continue()
      draftWrites += 1
      if (draftWrites === 1) {
        return route.fulfill({ status: 500, json: { detail: 'forced grouping persistence failure' } })
      }
      return route.continue()
    })
    const failedWrite = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT'
      && response.status() === 500
    ))
    await page.locator('.vue-flow__node[data-id="table_first"]').click({ button: 'right' })
    await page.getByText('Group into workflow', { exact: true }).click()
    await failedWrite
    await expect(page.locator('.vue-flow__node[data-id="workflow_1"]')).toBeVisible()
    await expect(page.getByTestId('canvas-persistence-retry')).toBeVisible()
    const afterFailedWrite = await draftState(page, name)
    expect(afterFailedWrite.graph).toEqual(original.graph)
    expect(afterFailedWrite.draft_revision).toBe(original.draft_revision)
    const grouped = await waitForAcceptedGraph(page, name, async () => {
      await page.getByTestId('canvas-persistence-retry').click()
    })
    expect(draftWrites).toBe(2)
    await expect(page.getByTestId('canvas-persistence-retry')).toHaveCount(0)
    expect(grouped.validation).toMatchObject({ valid: true, errors: [] })
    await expect(page.locator('.vue-flow__node')).toHaveCount(5)

    const groupedNode = grouped.graph.nodes.find(node => node.type === 'workflow')
    expect(groupedNode?.type).toBe('workflow')
    if (!groupedNode || groupedNode.type !== 'workflow') throw new Error('Expected grouped workflow node')
    expect(groupedNode).toMatchObject({
      id: 'workflow_1',
      name: 'Workflow 1',
      position: [473.3333333333333, 213.33333333333334],
      bindings: {},
      source: null,
    })
    expect(groupedNode.workflow.nodes).toEqual(original.graph.nodes.filter(node => (
      ['table_first', 'table_second', 'field_middle'].includes(node.id)
    )))
    expect(groupedNode.workflow.edges).toEqual([original.graph.edges.find(edge => (
      edge.id === 'table-internal'
    ))])
    expect(groupedNode.workflow.interface.inputs).toMatchObject([{
      id: 'input-table-in',
      name: 'table_first.table_0',
      kind: 'dataframe',
      targets: [{ node: 'table_first', port: { kind: 'positional', index: 0 } }],
    }, {
      id: 'input-field-in',
      name: 'field_middle.input_image',
      kind: 'field',
      targets: [{ node: 'field_middle', port: { kind: 'field', name: 'input_image' } }],
    }])
    expect(groupedNode.workflow.interface.outputs).toMatchObject([{
      id: 'output-field-out',
      name: 'field_middle.output_image',
      source: { node: 'field_middle', column: 'output_image' },
    }])
    expect(grouped.graph.edges).toEqual([{
      type: 'dataframe', id: 'table-in', source_node: 'table_before', target_node: 'workflow_1',
      target_position: null, target_input: 'input-table-in',
    }, {
      type: 'column', id: 'field-in', source_node: 'field_before', target_node: 'workflow_1',
      source_output: 'output_image', target_input: 'input-field-in',
    }, {
      type: 'dataframe', id: 'table-out', source_node: 'workflow_1', target_node: 'table_after',
      target_position: 0, target_input: null,
    }, {
      type: 'column', id: 'field-out', source_node: 'workflow_1', target_node: 'field_after',
      source_output: 'output-field-out', target_input: 'input_image',
    }])

    // A workflow node offers opening its child instead of another grouping action.
    await page.locator('.vue-flow__node[data-id="workflow_1"]').click({ button: 'right' })
    await expect(page.locator('.node-context-menu').getByText('Open workflow', { exact: true })).toBeVisible()
    await expect(page.getByText('Group into workflow', { exact: true })).toHaveCount(0)
    await page.keyboard.press('Escape')
    const afterOpenMenu = await draftState(page, name)
    expect(afterOpenMenu.graph).toEqual(grouped.graph)
    expect(afterOpenMenu.draft_revision).toBe(grouped.draft_revision)

    const restored = await waitForAcceptedGraph(page, name, async () => {
      await page.getByRole('menuitem', { name: 'Edit', exact: true }).click()
      await page.getByRole('menuitem', { name: 'Undo', exact: true }).click()
    })
    expect(restored.graph).toEqual(original.graph)
    await page.getByRole('menuitem', { name: 'Edit', exact: true }).click()
    await expect(page.getByRole('menuitem', { name: 'Undo', exact: true })).toBeDisabled()
    await expect(page.getByRole('menuitem', { name: 'Redo', exact: true })).toBeEnabled()
    const redone = await waitForAcceptedGraph(page, name, async () => {
      await page.getByRole('menuitem', { name: 'Redo', exact: true }).click()
    })
    expect(redone.graph).toEqual(grouped.graph)

    await saveWorkflow(page, name)
    expect(await savedGraph(page, name)).toEqual(grouped.graph)
    await page.reload()
    await openWorkflow(page, name, displayName)
    expect(await draftGraph(page, name)).toEqual(grouped.graph)
    await expect(page.locator('.vue-flow__node[data-id="workflow_1"]')).toBeVisible()
    await expect(page.locator('.vue-flow__edge')).toHaveCount(4)
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
    const beforeRefusal = await draftState(page, name)
    await expect(page.getByTestId('publish-dataframe-input')).toBeVisible()
    await page.locator('.vue-flow__node[data-id="seed"]').click()
    await expect(page.getByTestId('publish-dataframe-input')).toHaveCount(0)
    await page.locator('.vue-flow__node[data-id="increment"]').click()
    expect(await draftState(page, name)).toMatchObject({
      draft_revision: beforeRefusal.draft_revision,
      graph: beforeRefusal.graph,
    })
    for (let index = 0; index < 3; index++) {
      await page.getByTestId('publish-dataframe-input').click()
      await expect(page.getByTestId(`dataframe-input-name-${index}`)).toBeVisible()
    }
    await page.getByTestId('dataframe-input-name-2').fill('Last table')
    await saveWorkflow(page, name)
    const first = await savedGraph(page, name)
    const firstIds = first.interface.inputs.map(input => input.id)
    expect(new Set(firstIds).size).toBe(3)
    expect(first.interface.inputs.map(input => input.targets[0]?.port)).toEqual([
      { kind: 'positional', index: 0 }, { kind: 'positional', index: 1 }, { kind: 'positional', index: 2 },
    ])
    expect(first.interface.inputs.every(input => input.kind === 'dataframe')).toBe(true)

    await page.getByTestId('dataframe-input-name-2').fill(first.interface.inputs[0]!.name)
    await expect(page.locator('[data-testid="published-dataframe-inputs"] [role="alert"]')).toContainText(
      `Workflow interface name '${first.interface.inputs[0]!.name}' is already used.`,
    )
    expect(await draftGraph(page, name)).toEqual(first)
    await page.getByTestId('dataframe-input-name-2').fill('Last table')

    // A connected slot after the publications must move with them on unpublish.
    const connectedDraftWrite = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
      && (response.request().postDataJSON() as { graph?: GraphState } | null)
        ?.graph?.edges.length === 1
    ))
    const source = await page.locator('.vue-flow__node[data-id="seed"] [data-handleid="bif:v1:dataframe-output"]').boundingBox()
    const target = await page.locator('.vue-flow__node[data-id="increment"] [data-handleid="bif:v1:dataframe-position:3"]').boundingBox()
    if (!source || !target) throw new Error('Expected DataFrame handles')
    await page.mouse.move(source.x + source.width / 2, source.y + source.height / 2)
    await page.mouse.down()
    await page.mouse.move(target.x + target.width / 2, target.y + target.height / 2, { steps: 10 })
    await page.mouse.up()
    await connectedDraftWrite
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)
    await expect(page.getByTestId('dataframe-input-name-2')).toHaveValue('Last table')
    await saveWorkflow(page, name)
    await expect(page.getByTestId('workflow-title')).not.toContainText('*')
    await page.waitForLoadState('networkidle')
    await expect.poll(async () => (await draftGraph(page, name)).edges.length).toBe(1)
    const beforeCompaction = await draftState(page, name)
    expect(beforeCompaction.graph.interface.inputs).toHaveLength(3)
    let allowCompactionWrite = false
    await page.route(`**/api/v1/workflow-drafts/${name}`, async (route) => {
      const body = route.request().method() === 'PUT'
        ? route.request().postDataJSON() as { graph?: GraphState } | null
        : null
      if (body?.graph?.interface.inputs.length === 2 && !allowCompactionWrite) {
        await route.fulfill({ status: 500, json: { detail: 'forced compaction persistence failure' } })
        return
      }
      await route.continue()
    })
    const failedCompaction = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT'
      && response.status() === 500
      && (response.request().postDataJSON() as { graph?: GraphState } | null)
        ?.graph?.interface.inputs.length === 2
    ))
    await page.getByTestId('unpublish-dataframe-1').click()
    await failedCompaction
    await expect(page.getByTestId('dataframe-input-name-1')).toHaveValue('Last table')
    await expect(page.getByTestId('dataframe-input-name-2')).toHaveCount(0)
    const afterFailedCompaction = await draftState(page, name)
    expect(afterFailedCompaction.graph).toEqual(beforeCompaction.graph)
    expect(afterFailedCompaction.draft_revision).toBe(beforeCompaction.draft_revision)
    await expect(page.getByTestId('canvas-persistence-issue')).toBeVisible()
    allowCompactionWrite = true
    const recoveredWrite = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await page.getByTestId('canvas-persistence-retry').click()
    const recovered = await (await recoveredWrite).json() as WorkflowDraftResponse
    expect(recovered.draft_revision).toBe(afterFailedCompaction.draft_revision + 1)
    expect(recovered.graph.interface.inputs.map(input => input.id)).toEqual([
      firstIds[0], firstIds[2],
    ])
    expect(recovered.graph.edges).toMatchObject([{
      target_node: 'increment', target_position: 2,
    }])
    await expect(page.getByTestId('canvas-persistence-issue')).toHaveCount(0)
    await page.getByRole('menuitem', { name: 'Edit', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Undo', exact: true }).click()
    await expect(page.getByTestId('dataframe-input-name-2')).toHaveValue('Last table')
    await page.getByRole('menuitem', { name: 'Edit', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Redo', exact: true }).click()
    await expect(page.getByTestId('dataframe-input-name-1')).toHaveValue('Last table')
    await saveWorkflow(page, name)
    const saved = await savedGraph(page, name)
    expect(saved.interface.inputs.map(input => input.id)).toEqual([firstIds[0], firstIds[2]])
    expect(saved.interface.inputs[1]).toMatchObject({ name: 'Last table', targets: [{ node: 'increment', port: { kind: 'positional', index: 1 } }] })
    expect(saved.edges[0]).toMatchObject({ type: 'dataframe', target_node: 'increment', target_position: 2 })
    await page.reload()
    await openWorkflow(page, name, displayName)
    await page.locator('.vue-flow__node[data-id="increment"]').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    await expect(page.getByTestId('dataframe-input-name-1')).toHaveValue('Last table')
    expect(await draftGraph(page, name)).toEqual(saved)
    expect(await savedGraph(page, name)).toEqual(saved)
  })

  test('publishes an existing child DataFrame port through the parent interface', async ({ page }) => {
    const name = workflowName('forward_dataframe')
    const displayName = `Forward ${name}`
    await createWorkflow(page, name, displayName)
    const child = graph('child', 'Child')
    child.nodes = [{ type: 'tool', id: 'increment', name: 'Increment', tool_name: 'IncrementNumbers', position: [180, 160], parameters: { number: 1 } }]
    child.interface.inputs.push({
      id: 'child-bound-number', name: 'Bound number', kind: 'field',
      schema: { type: 'int' }, default: null,
      targets: [{ node: 'increment', port: { kind: 'field', name: 'number' } }],
    })
    const parent = graph(name, displayName)
    parent.nodes = [{
      type: 'workflow', id: 'child', name: 'Child', position: [180, 160], workflow: child,
      bindings: { 'child-bound-number': { __type__: 'int', value: 7 } },
    }, {
      type: 'tool', id: 'seed', name: 'Seed', tool_name: 'SeedNumbers',
      position: [180, 400], parameters: {},
    }, {
      type: 'tool', id: 'outside_increment', name: 'Outside increment',
      tool_name: 'IncrementNumbers', position: [520, 400], parameters: { number: 1 },
    }]
    parent.edges = [{
      type: 'dataframe', id: 'outside-edge', source_node: 'seed',
      target_node: 'outside_increment', target_position: 0,
    }]
    const setup = await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, { data: { graph: parent } })
    expect(setup.ok(), await setup.text()).toBeTruthy()
    await page.goto('/')
    await openWorkflow(page, name, displayName)
    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    await page.locator('.vue-flow__node[data-id="increment"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    await page.getByTestId('publish-dataframe-input').click()
    await page.getByTestId('dataframe-input-name-0').fill('Source table')
    const privateParent = await draftGraph(page, name)
    const privateParentChild = privateParent.nodes.find(node => node.id === 'child')
    expect(privateParentChild?.type).toBe('workflow')
    if (privateParentChild?.type !== 'workflow') throw new Error('Expected child workflow')
    expect(privateParentChild.workflow.interface.inputs.map(input => input.id)).toEqual(['child-bound-number'])
    expect(privateParentChild.bindings).toEqual({ 'child-bound-number': { __type__: 'int', value: 7 } })
    expect(privateParent.edges).toEqual((await savedGraph(page, name)).edges)
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await expect(page.getByTestId('workflow-title')).not.toContainText('*')
    await page.locator('.dv-tab').getByText(displayName, { exact: true }).click()
    await saveWorkflow(page, name)
    const savedChild = (await savedGraph(page, name)).nodes.find(node => node.id === 'child')!
    if (savedChild.type !== 'workflow') throw new Error('Expected child workflow')
    const childPortId = savedChild.workflow.interface.inputs.find(input => input.kind === 'dataframe')!.id
    await page.locator('.vue-flow__node[data-id="child"]').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    await page.getByRole('button', { name: 'Publish DataFrame input: Source table', exact: true }).click()
    await page.getByTestId(`dataframe-input-name-${childPortId}`).fill('Parent table')
    await saveWorkflow(page, name)
    await expect(page.getByTestId('workflow-title')).not.toContainText('*')
    await page.waitForLoadState('networkidle')
    expect((await savedGraph(page, name)).interface.inputs[0]).toMatchObject({
      kind: 'dataframe', name: 'Parent table', targets: [{ node: 'child', port: { kind: 'workflow', id: childPortId } }],
    })
    const beforeRefusal = await draftState(page, name)
    const parentInput = page.getByTestId(`dataframe-input-name-${childPortId}`)
    const portNameError = page.getByTestId('published-dataframe-inputs').getByRole('alert')
    await parentInput.fill('   ')
    await expect(portNameError).toContainText('Workflow interface name cannot be empty.')
    const refused = await draftState(page, name)
    expect(refused.draft_revision).toBe(beforeRefusal.draft_revision)
    expect(refused.graph).toEqual(beforeRefusal.graph)
    await parentInput.fill('Parent table')
    await expect(portNameError).toHaveCount(0)

    let allowUnpublish = false
    await page.route(`**/api/v1/workflow-drafts/${name}`, async (route) => {
      const body = route.request().method() === 'PUT'
        ? route.request().postDataJSON() as { graph?: GraphState } | null
        : null
      if (body?.graph?.interface.inputs.length === 0 && !allowUnpublish) {
        await route.fulfill({ status: 500, json: { detail: 'forced forwarded-port write failure' } })
        return
      }
      await route.continue()
    })
    const failedUnpublish = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT'
      && response.status() === 500
    ))
    await page.getByTestId(`unpublish-dataframe-${childPortId}`).click()
    await failedUnpublish
    await expect(page.getByRole('button', { name: 'Publish DataFrame input: Source table', exact: true })).toBeVisible()
    await expect(page.getByTestId('canvas-persistence-retry')).toBeVisible()
    const afterFailure = await draftState(page, name)
    expect(afterFailure.draft_revision).toBe(beforeRefusal.draft_revision)
    expect(afterFailure.graph).toEqual(beforeRefusal.graph)
    allowUnpublish = true
    const recovered = await waitForAcceptedGraph(page, name, async () => {
      await page.getByTestId('canvas-persistence-retry').click()
    })
    expect(recovered.draft_revision).toBe(beforeRefusal.draft_revision + 1)
    expect(recovered.graph.interface.inputs).toEqual([])
    expect(recovered.graph.edges).toEqual(beforeRefusal.graph.edges)
    const recoveredChild = recovered.graph.nodes.find(node => node.id === 'child')
    expect(recoveredChild?.type).toBe('workflow')
    if (recoveredChild?.type !== 'workflow') throw new Error('Expected child workflow')
    expect(recoveredChild.workflow.interface.inputs.find(input => input.kind === 'dataframe')?.id).toBe(childPortId)
    expect(recoveredChild.bindings).toEqual({ 'child-bound-number': { __type__: 'int', value: 7 } })
    await saveWorkflow(page, name)
    expect((await savedGraph(page, name)).interface.inputs).toEqual([])
    await page.reload()
    await openWorkflow(page, name, displayName)
    const reloaded = await draftGraph(page, name)
    expect(reloaded).toEqual(await savedGraph(page, name))
    expect(reloaded.edges).toEqual(beforeRefusal.graph.edges)
    const reloadedChild = reloaded.nodes.find(node => node.id === 'child')
    expect(reloadedChild?.type).toBe('workflow')
    if (reloadedChild?.type !== 'workflow') throw new Error('Expected child workflow')
    expect(reloadedChild.workflow.interface.inputs.find(input => input.kind === 'dataframe')?.id).toBe(childPortId)
    expect(reloadedChild.bindings).toEqual({ 'child-bound-number': { __type__: 'int', value: 7 } })
  })

  test('keeps nested edits private until save and discards later private changes', async ({ page }) => {
    const name = workflowName('nested_private')
    const displayName = `Nested private ${name}`
    const initial = nestedInterfaceGraph(name, displayName)
    const validation = await page.request.put(`${API_BASE}/api/v1/graph`, { data: initial })
    expect(validation.ok(), await validation.text()).toBeTruthy()
    expect(await validation.json()).toMatchObject({
      valid: true,
      errors: [],
    })
    expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name, display_name: displayName },
    })).status()).toBe(201)
    const setup = await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, { data: { graph: initial } })
    expect(setup.ok(), await setup.text()).toBeTruthy()

    await page.goto('/')
    await openWorkflow(page, name, displayName)
    await expect(page.locator('.vue-flow__node[data-id="seed"]')).toBeVisible()
    await expect(page.locator('.vue-flow__node[data-id="child"]')).toBeVisible()
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)
    expect(childNode(await draftGraph(page, name)).workflow.interface.inputs[0]).toMatchObject({
      id: 'child-table-input', name: 'Source table',
    })

    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    await expect(page.locator('.nested-workflow-editor')).toBeVisible()
    await page.locator('.vue-flow__node[data-id="increment"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const privateInputName = page.getByTestId('dataframe-input-name-0')
    await expect(privateInputName).toHaveValue('Source table')
    const privateSnapshotAccepted = page.waitForResponse(response => (
      responseCarriesNestedInputName(response, 'Applied source table')
    ))
    await privateInputName.fill('Applied source table')
    const acceptedPrivate = await (await privateSnapshotAccepted).json() as {
      session_id: string
      snapshot_revision: number
      graph: GraphState
    }
    await expect(privateInputName).toHaveValue('Applied source table')
    expectStableParentRoutes(await draftGraph(page, name))

    await privateInputName.fill('Number value')
    await expect(page.getByTestId('interface-name-error')).toContainText(
      "Workflow interface name 'Number value' is already used.",
    )
    await privateInputName.fill('   ')
    await expect(page.getByTestId('interface-name-error')).toContainText(
      'Workflow interface name cannot be empty.',
    )
    const refusedPrivateResponse = await page.request.get(
      `${API_BASE}/api/v1/nested-workflow-snapshots/${acceptedPrivate.session_id}`,
    )
    expect(refusedPrivateResponse.ok(), await refusedPrivateResponse.text()).toBeTruthy()
    const refusedPrivate = await refusedPrivateResponse.json() as {
      snapshot_revision: number
      graph: GraphState
    }
    expect(refusedPrivate.snapshot_revision).toBe(acceptedPrivate.snapshot_revision)
    expect(refusedPrivate.graph).toEqual(acceptedPrivate.graph)
    expectStableParentRoutes(await draftGraph(page, name))
    await privateInputName.fill('Applied source table')
    await expect(page.getByTestId('interface-name-error')).toHaveCount(0)

    // The nested snapshot autosaves privately; the owning draft is unchanged until Save applies it.
    await expect.poll(async () => childNode(await draftGraph(page, name)).workflow.interface.inputs[0]?.name)
      .toBe('Source table')
    expectStableParentRoutes(await draftGraph(page, name))

    const parentApplied = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await parentApplied
    await expect.poll(async () => childNode(await draftGraph(page, name)).workflow.interface.inputs[0]?.name)
      .toBe('Applied source table')
    expectStableParentRoutes(await draftGraph(page, name))

    await page.locator('.dv-tab').filter({ hasText: displayName }).click()
    await saveWorkflow(page, name)
    await page.reload()
    await openWorkflow(page, name, displayName)
    const reloaded = await draftGraph(page, name)
    expect(childNode(reloaded).workflow.interface.inputs[0]).toMatchObject({
      id: 'child-table-input', name: 'Applied source table',
    })
    expectStableParentRoutes(reloaded)

    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    await page.locator('.vue-flow__node[data-id="increment"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const discardedInputName = page.getByTestId('dataframe-input-name-0')
    await expect(discardedInputName).toHaveValue('Applied source table')
    const discardedSnapshotAccepted = page.waitForResponse(response => (
      responseCarriesNestedInputName(response, 'Discarded private name')
    ))
    await discardedInputName.fill('Discarded private name')
    await discardedSnapshotAccepted
    await expect(discardedInputName).toHaveValue('Discarded private name')

    page.once('dialog', async (dialog) => {
      expect(dialog.message()).toContain("Discard unsaved changes to nested-workflow 'Stable child'?")
      await dialog.accept()
    })
    const nestedTab = page.locator('.dv-tab').filter({ hasText: 'Stable child' })
    await nestedTab.locator('.dv-default-tab-action').click()
    await expect(page.locator('.nested-workflow-editor')).toHaveCount(0)
    const afterDiscard = await draftGraph(page, name)
    expect(childNode(afterDiscard).workflow.interface.inputs[0]).toMatchObject({
      id: 'child-table-input', name: 'Applied source table',
    })
    expectStableParentRoutes(afterDiscard)
  })

  test('retries a failed private interface rename without changing stable parent routes', async ({ page }) => {
    const name = workflowName('nested_port_retry')
    const displayName = `Nested port retry ${name}`
    const initial = nestedInterfaceGraph(name, displayName)
    expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name, display_name: displayName },
    })).status()).toBe(201)
    const setup = await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, { data: { graph: initial } })
    expect(setup.ok(), await setup.text()).toBeTruthy()

    await page.goto('/')
    await openWorkflow(page, name, displayName)
    const originalParent = await draftState(page, name)
    expectStableParentRoutes(originalParent.graph)
    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    await expect(page.locator('.nested-workflow-editor')).toBeVisible()
    await page.locator('.vue-flow__node[data-id="increment"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const portName = page.getByTestId('dataframe-input-name-0')
    await expect(portName).toHaveValue('Source table')

    let privateSessionId: string | undefined
    let privateWrites = 0
    await page.route('**/api/v1/nested-workflow-snapshots/*', async route => {
      if (route.request().method() !== 'PUT') return route.continue()
      const body = route.request().postDataJSON() as { graph?: GraphState } | null
      if (childInputName(body?.graph) !== 'Recovered source table') return route.continue()
      privateWrites += 1
      privateSessionId = new URL(route.request().url()).pathname.split('/').at(-1)
      if (privateWrites === 1) {
        return route.fulfill({ status: 500, json: { detail: 'forced private port write failure' } })
      }
      return route.continue()
    })
    const failedWrite = page.waitForResponse(response => (
      response.url().includes('/api/v1/nested-workflow-snapshots/')
      && response.request().method() === 'PUT'
      && response.status() === 500
    ))
    await portName.fill('Recovered source table')
    await failedWrite
    await expect(portName).toHaveValue('Recovered source table')
    await expect(page.getByTestId('canvas-persistence-retry')).toBeVisible()
    expect(privateSessionId).toBeTruthy()
    const privateUrl = `${API_BASE}/api/v1/nested-workflow-snapshots/${privateSessionId}`
    const failedSnapshotResponse = await page.request.get(privateUrl)
    expect(failedSnapshotResponse.ok(), await failedSnapshotResponse.text()).toBeTruthy()
    const failedSnapshot = await failedSnapshotResponse.json() as {
      snapshot_revision: number; graph: GraphState
    }
    expect(childInputName(failedSnapshot.graph)).toBe('Source table')
    expect(failedSnapshot.graph.interface.inputs[0]?.id).toBe('child-table-input')
    const failedParent = await draftState(page, name)
    expect(failedParent.draft_revision).toBe(originalParent.draft_revision)
    expect(failedParent.graph).toEqual(originalParent.graph)
    expectStableParentRoutes(failedParent.graph)

    const acceptedWrite = page.waitForResponse(response => responseCarriesNestedInputName(response, 'Recovered source table'))
    await page.getByTestId('canvas-persistence-retry').click()
    const accepted = await (await acceptedWrite).json() as { snapshot_revision: number; graph: GraphState }
    expect(privateWrites).toBe(2)
    expect(accepted.snapshot_revision).toBe(failedSnapshot.snapshot_revision + 1)
    expect(childInputName(accepted.graph)).toBe('Recovered source table')
    expect(accepted.graph.interface.inputs[0]?.id).toBe('child-table-input')
    await expect(page.getByTestId('canvas-persistence-retry')).toHaveCount(0)
    const durableSnapshotResponse = await page.request.get(privateUrl)
    expect(durableSnapshotResponse.ok(), await durableSnapshotResponse.text()).toBeTruthy()
    expect(await durableSnapshotResponse.json()).toMatchObject({
      snapshot_revision: accepted.snapshot_revision, graph: accepted.graph,
    })
    const stillPrivate = await draftState(page, name)
    expect(stillPrivate.draft_revision).toBe(originalParent.draft_revision)
    expect(stillPrivate.graph).toEqual(originalParent.graph)

    const parentApplied = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await parentApplied
    const applied = await draftState(page, name)
    expect(applied.draft_revision).toBe(originalParent.draft_revision + 1)
    expect(childInputName(childNode(applied.graph).workflow)).toBe('Recovered source table')
    expect(childNode(applied.graph).workflow.interface.inputs[0]?.id).toBe('child-table-input')
    expectStableParentRoutes(applied.graph)

    await page.locator('.dv-tab').filter({ hasText: displayName }).click()
    await saveWorkflow(page, name)
    await page.reload()
    await openWorkflow(page, name, displayName)
    const reloaded = await draftState(page, name)
    expect(reloaded.graph).toEqual(await savedGraph(page, name))
    expect(childInputName(childNode(reloaded.graph).workflow)).toBe('Recovered source table')
    expect(childNode(reloaded.graph).workflow.interface.inputs[0]?.id).toBe('child-table-input')
    expectStableParentRoutes(reloaded.graph)
  })

  test('closes depth-two nested snapshots child-first after refusal and failed delete', async ({ page }) => {
    test.setTimeout(60_000)
    const name = workflowName('nested_depth_two')
    const displayName = `Nested depth two ${name}`
    const initial = nestedInterfaceGraph(name, displayName)
    const child = childNode(initial).workflow
    child.nodes.push({
      type: 'workflow', id: 'grandchild', name: 'Grandchild', position: [600, 180],
      workflow: graph('grandchild_graph', 'Grandchild graph'), bindings: {},
    })
    expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name, display_name: displayName },
    })).status()).toBe(201)
    const setup = await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, { data: { graph: initial } })
    expect(setup.ok(), await setup.text()).toBeTruthy()

    const otherName = workflowName('nested_depth_other')
    expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name: otherName, display_name: `Other ${otherName}` },
    })).status()).toBe(201)
    expect((await page.request.put(`${API_BASE}/api/v1/workflows/${otherName}`, {
      data: { graph: nestedInterfaceGraph(otherName, `Other ${otherName}`) },
    })).ok()).toBeTruthy()
    const otherOpened = await page.request.post(`${API_BASE}/api/v1/nested-workflow-snapshots/open`, {
      data: {
        owner: { kind: 'root', canvas_id: `workflow:${otherName}`, workflow_id: otherName },
        parent_node_id: 'child', graph: childNode(nestedInterfaceGraph(otherName, `Other ${otherName}`)).workflow,
      },
    })
    expect(otherOpened.status()).toBe(201)
    const unrelated = await otherOpened.json() as { session_id: string; graph: GraphState }

    await page.goto('/')
    await openWorkflow(page, name, displayName)
    const rootBefore = await draftState(page, name)
    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    await expect(page.locator('.nested-workflow-editor')).toHaveCount(1)
    const parentTab = page.locator('.dv-tab').filter({ hasText: 'Stable child' })
    const parentOpen = await page.request.post(`${API_BASE}/api/v1/nested-workflow-snapshots/open`, {
      data: {
        owner: { kind: 'root', canvas_id: `workflow:${name}`, workflow_id: name },
        parent_node_id: 'child', graph: child,
      },
    })
    expect(parentOpen.status()).toBe(201)
    const parent = await parentOpen.json() as {
      session_id: string; snapshot_revision: number; graph: GraphState
      owner: { workflow_id: string; canvas_id: string; identity_generation: number }
    }
    const rootIdentity = await setup.json() as {
      identity_generation: number
    }
    expect(parent.owner).toMatchObject({
      workflow_id: name, canvas_id: `workflow:${name}`,
      identity_generation: rootIdentity.identity_generation,
    })
    await page.locator('.vue-flow__node[data-id="grandchild"]:visible').dblclick()
    await expect(page.locator('.dv-tab').filter({ hasText: 'Grandchild' })).toBeVisible()
    const grandchildOpen = await page.request.post(`${API_BASE}/api/v1/nested-workflow-snapshots/open`, {
      data: {
        owner: { kind: 'nested', session_id: parent.session_id },
        parent_node_id: 'grandchild', graph: graph('grandchild_graph', 'Grandchild graph'),
      },
    })
    expect(grandchildOpen.status()).toBe(201)
    const grandchild = await grandchildOpen.json() as { session_id: string; snapshot_revision: number; owner: { session_id: string }; graph: GraphState }
    expect(grandchild.owner.session_id).toBe(parent.session_id)
    expect(parent.session_id).not.toBe(unrelated.session_id)

    await page.locator('.vue-flow__node[data-id="blur_1"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    await page.locator('.node-panel-header .node-name').dblclick()
    const nodeName = page.locator('.node-panel-header .name-input')
    await nodeName.fill('Private grandchild edit')
    const privateWrite = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/nested-workflow-snapshots/${grandchild.session_id}`)
      && response.request().method() === 'PUT' && response.status() === 200
    ))
    await nodeName.press('Enter')
    const edited = await (await privateWrite).json() as typeof grandchild
    expect(edited.snapshot_revision).toBe(grandchild.snapshot_revision + 1)
    expect(edited.graph.nodes[0]?.name).toBe('Private grandchild edit')
    expect((await draftState(page, name)).graph).toEqual(rootBefore.graph)
    expect((await page.request.get(`${API_BASE}/api/v1/nested-workflow-snapshots/${parent.session_id}`)).json())
      .resolves.toMatchObject({ snapshot_revision: parent.snapshot_revision, graph: parent.graph })

    await page.reload()
    await openWorkflow(page, name, displayName)
    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    await page.locator('.vue-flow__node[data-id="grandchild"]:visible').dblclick()
    await expect(page.locator('.vue-flow__node[data-id="blur_1"]:visible')).toContainText('Private grandchild edit')
    const reopenedParent = await page.request.post(`${API_BASE}/api/v1/nested-workflow-snapshots/open`, {
      data: {
        owner: { kind: 'root', canvas_id: `workflow:${name}`, workflow_id: name },
        parent_node_id: 'child', graph: child,
      },
    })
    expect((await reopenedParent.json()).session_id).toBe(parent.session_id)
    const reopenedGrandchild = await page.request.post(`${API_BASE}/api/v1/nested-workflow-snapshots/open`, {
      data: {
        owner: { kind: 'nested', session_id: parent.session_id },
        parent_node_id: 'grandchild', graph: graph('grandchild_graph', 'Grandchild graph'),
      },
    })
    expect((await reopenedGrandchild.json()).session_id).toBe(grandchild.session_id)
    expect((await page.request.get(`${API_BASE}/api/v1/nested-workflow-snapshots/${grandchild.session_id}`)).json())
      .resolves.toMatchObject({ snapshot_revision: edited.snapshot_revision, graph: edited.graph })

    await parentTab.click()
    const refusedDelete = page.waitForResponse(response => (
      response.url().includes(`/api/v1/nested-workflow-snapshots/${parent.session_id}?`)
      && response.request().method() === 'DELETE'
    ))
    await parentTab.locator('.dv-default-tab-action').click()
    const refusal = await refusedDelete
    expect(refusal.status()).toBe(409)
    expect(await refusal.json()).toMatchObject({
      error: 'nested_snapshot_has_dependents', dependent_session_ids: [grandchild.session_id],
    })
    await expect(page.getByTestId('nested-workflow-close-error')).toContainText('dependent nested snapshot must be deleted first')
    await expect(page.getByTestId('nested-workflow-close-error')).toContainText('Close the child tab first, then retry.')
    await expect(parentTab).toBeVisible()
    expect((await draftState(page, name)).graph).toEqual(rootBefore.graph)
    expect((await page.request.get(`${API_BASE}/api/v1/nested-workflow-snapshots/${parent.session_id}`)).status()).toBe(200)
    expect((await page.request.get(`${API_BASE}/api/v1/nested-workflow-snapshots/${grandchild.session_id}`)).status()).toBe(200)

    const grandchildTab = page.locator('.dv-tab').filter({ hasText: 'Grandchild' })
    await grandchildTab.click()
    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain('Discard unsaved changes')
      await dialog.dismiss()
    })
    await grandchildTab.locator('.dv-default-tab-action').click()
    await expect(grandchildTab).toBeVisible()
    expect((await page.request.get(`${API_BASE}/api/v1/nested-workflow-snapshots/${grandchild.session_id}`)).status()).toBe(200)

    let failDelete = true
    await page.route(`**/api/v1/nested-workflow-snapshots/${grandchild.session_id}?*`, async route => {
      if (route.request().method() === 'DELETE' && failDelete) {
        failDelete = false
        await route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Injected delete failure"}' })
      } else {
        await route.continue()
      }
    })
    page.once('dialog', dialog => dialog.accept())
    const failedDelete = page.waitForResponse(response => (
      response.url().includes(grandchild.session_id) && response.request().method() === 'DELETE'
    ))
    await grandchildTab.locator('.dv-default-tab-action').click()
    expect((await failedDelete).status()).toBe(500)
    await expect(grandchildTab).toBeVisible()
    await expect(page.getByTestId('nested-workflow-close-error')).toContainText('Injected delete failure')
    await expect(page.getByTestId('nested-workflow-close-error')).toContainText('Close the tab again to retry.')
    expect((await page.request.get(`${API_BASE}/api/v1/nested-workflow-snapshots/${grandchild.session_id}`)).status()).toBe(200)

    page.once('dialog', dialog => dialog.accept())
    const retryDelete = page.waitForResponse(response => (
      response.url().includes(grandchild.session_id) && response.request().method() === 'DELETE'
    ))
    await grandchildTab.locator('.dv-default-tab-action').click()
    expect((await retryDelete).status()).toBe(204)
    await expect(grandchildTab).toHaveCount(0)
    expect((await page.request.get(`${API_BASE}/api/v1/nested-workflow-snapshots/${grandchild.session_id}`)).status()).toBe(404)
    await parentTab.locator('.dv-default-tab-action').click()
    await expect(parentTab).toHaveCount(0)
    await expect.poll(async () => (
      await page.request.get(`${API_BASE}/api/v1/nested-workflow-snapshots/${parent.session_id}`)
    ).status()).toBe(404)
    expect((await draftState(page, name)).graph).toEqual(rootBefore.graph)
    expect((await savedGraph(page, name))).toEqual(rootBefore.graph)
    const unrelatedAfter = await page.request.get(`${API_BASE}/api/v1/nested-workflow-snapshots/${unrelated.session_id}`)
    expect(unrelatedAfter.status()).toBe(200)
    expect((await unrelatedAfter.json()).graph).toEqual(unrelated.graph)

    await page.locator('.dv-tab').filter({ hasText: displayName }).click()
    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    const freshParent = await page.request.post(`${API_BASE}/api/v1/nested-workflow-snapshots/open`, {
      data: {
        owner: { kind: 'root', canvas_id: `workflow:${name}`, workflow_id: name },
        parent_node_id: 'child', graph: child,
      },
    })
    expect(freshParent.status()).toBe(201)
    expect((await freshParent.json()).session_id).not.toBe(parent.session_id)
  })

  test('isolates nested keyboard history from the parent and saves only the active context', async ({ page }) => {
    const name = workflowName('nested_shortcut_history')
    const displayName = `Nested shortcut history ${name}`
    const initial = nestedInterfaceGraph(name, displayName)
    expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name, display_name: displayName },
    })).status()).toBe(201)
    expect((await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
      data: { graph: initial },
    })).ok()).toBeTruthy()
    await page.goto('/')
    await openWorkflow(page, name, displayName)
    const canonicalInitial = await draftState(page, name)

    const renameSelected = async (nodeId: string, nextName: string): Promise<void> => {
      await page.locator(`.vue-flow__node[data-id="${nodeId}"]`).click()
      await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
      await page.locator('.node-panel-header .node-name').dblclick()
      const input = page.locator('.node-panel-header .name-input')
      await input.fill(nextName)
      await input.press('Enter')
    }
    const shortcut = async (keys: string): Promise<void> => {
      await page.locator('.vue-flow__pane').click({ position: { x: 20, y: 20 } })
      await page.keyboard.press(keys)
    }
    const nestedWrite = () => page.waitForResponse(response => (
      response.url().includes('/api/v1/nested-workflow-snapshots/')
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))

    const rootEdit = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT' && response.status() === 200
    ))
    await renameSelected('seed', 'Parent edit')
    await rootEdit
    const parentEdited = await draftState(page, name)
    expect(parentEdited.graph.nodes.find(node => node.id === 'seed')?.name).toBe('Parent edit')

    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    await expect(page.locator('.nested-workflow-editor')).toBeVisible()
    const initialPrivateWrite = nestedWrite()
    await renameSelected('increment', 'Private edit')
    const privateEdited = await (await initialPrivateWrite).json() as {
      session_id: string; snapshot_revision: number; graph: GraphState
    }
    expect(privateEdited.graph.nodes.find(node => node.id === 'increment')?.name).toBe('Private edit')
    expect((await draftState(page, name)).graph).toEqual(parentEdited.graph)

    let accepted = nestedWrite()
    await shortcut('Control+z')
    const privateUndone = await (await accepted).json() as typeof privateEdited
    expect(privateUndone.session_id).toBe(privateEdited.session_id)
    expect(privateUndone.snapshot_revision).toBe(privateEdited.snapshot_revision + 1)
    expect(privateUndone.graph).toEqual(childNode(parentEdited.graph).workflow)
    expect((await draftState(page, name)).draft_revision).toBe(parentEdited.draft_revision)

    accepted = nestedWrite()
    await shortcut('Control+Shift+z')
    const privateRedone = await (await accepted).json() as typeof privateEdited
    expect(privateRedone.session_id).toBe(privateEdited.session_id)
    expect(privateRedone.snapshot_revision).toBe(privateUndone.snapshot_revision + 1)
    expect(privateRedone.graph).toEqual(privateEdited.graph)

    await page.locator('.dv-tab').filter({ hasText: displayName }).click()
    const rootUndo = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT' && response.status() === 200
    ))
    await shortcut('Control+z')
    await rootUndo
    const parentUndone = await draftState(page, name)
    expect(parentUndone.graph).toEqual(canonicalInitial.graph)
    expect(parentUndone.draft_revision).toBe(parentEdited.draft_revision + 1)
    const privateAfterRootUndo = await (await page.request.get(
      `${API_BASE}/api/v1/nested-workflow-snapshots/${privateEdited.session_id}`,
    )).json() as typeof privateEdited
    expect(privateAfterRootUndo.snapshot_revision).toBe(privateRedone.snapshot_revision)
    expect(privateAfterRootUndo.graph).toEqual(privateRedone.graph)

    await page.locator('.dv-tab').filter({ hasText: 'Stable child' }).click()
    const parentApply = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT' && response.status() === 200
    ))
    await shortcut('Control+s')
    await parentApply
    const applied = await draftState(page, name)
    expect(applied.graph.nodes.find(node => node.id === 'seed')?.name).toBe('Seed')
    expect(childNode(applied.graph).workflow).toEqual(privateRedone.graph)
    expect(await savedGraph(page, name)).toEqual(canonicalInitial.graph)

    await page.locator('.dv-tab').filter({ hasText: displayName }).click()
    const rootSave = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflows/${name}`)
      && response.request().method() === 'PUT' && response.status() === 200
    ))
    await shortcut('Control+s')
    await rootSave
    expect(await savedGraph(page, name)).toEqual(applied.graph)
  })

  test('refuses a stale-parent nested save without mutating either graph', async ({ page }) => {
    const name = workflowName('nested_parent_conflict')
    const displayName = `Nested parent conflict ${name}`
    const initial = nestedInterfaceGraph(name, displayName)
    expect((await page.request.put(`${API_BASE}/api/v1/graph`, { data: initial })).ok()).toBeTruthy()
    expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name, display_name: displayName },
    })).status()).toBe(201)
    expect((await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
      data: { graph: initial },
    })).ok()).toBeTruthy()

    await page.goto('/')
    await openWorkflow(page, name, displayName)
    expectStableParentRoutes(await draftGraph(page, name))
    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    await page.locator('.vue-flow__node[data-id="increment"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const inputName = page.getByTestId('dataframe-input-name-0')
    const rootTab = page.locator('.dv-tab').filter({ hasText: displayName })
    const nestedTab = page.locator('.dv-tab').filter({ hasText: 'Stable child' })

    async function installChangedParent(nextInputName: string, nextSeedName: string) {
      await rootTab.click()
      await page.locator('.vue-flow__node[data-id="seed"]').click()
      await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
      const panelName = page.locator('.node-panel-header .node-name')
      await panelName.dblclick()
      await page.locator('.node-panel-header .name-input').fill(nextSeedName)
      const localWrite = page.waitForResponse(response => (
        response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
        && response.request().method() === 'PUT'
        && response.status() === 200
      ))
      await page.locator('.node-panel-header .name-input').press('Enter')
      await localWrite
      await replaceDraftChildInputName(page, name, nextInputName)
      const rootConflict = page.locator('.workflow-draft-conflict')
      await expect(rootConflict).toBeVisible()
      await page.getByRole('button', { name: 'Apply agent changes', exact: true }).click()
      await expect(rootConflict).toHaveCount(0)
      await expect(page.locator('.vue-flow__node[data-id="seed"] .node-name')).toHaveText(nextSeedName)
      await nestedTab.click()
    }

    const privateWrite = page.waitForResponse(response => (
      responseCarriesNestedInputName(response, 'Durable private version')
    ))
    await inputName.fill('Durable private version')
    const privateSnapshot = await (await privateWrite).json() as {
      session_id: string
      snapshot_revision: number
      graph: GraphState
    }
    expect(childInputName(privateSnapshot.graph)).toBe('Durable private version')
    await installChangedParent('Latest parent version', 'Latest parent seed')
    await expect.poll(async () => childInputName(childNode(await draftGraph(page, name)).workflow))
      .toBe('Latest parent version')
    const parentBeforeRefusalResponse = await page.request.get(
      `${API_BASE}/api/v1/workflow-drafts/${name}`,
    )
    expect(parentBeforeRefusalResponse.ok()).toBeTruthy()
    const parentBeforeRefusal = (await parentBeforeRefusalResponse.json()) as WorkflowDraftResponse

    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await expect(page.getByText(
      'Cannot save nested-workflow because its parent node changed after this editor was opened.',
      { exact: true },
    )).toBeVisible()
    await expect(inputName).toHaveValue('Durable private version')
    await expect(page.getByTestId('workflow-title')).toContainText('*')
    const parentAfterRefusal = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)
    expect(parentAfterRefusal.ok()).toBeTruthy()
    const refusedParent = (await parentAfterRefusal.json()) as WorkflowDraftResponse
    expect(refusedParent.draft_revision).toBe(parentBeforeRefusal.draft_revision)
    expect(refusedParent.graph).toEqual(parentBeforeRefusal.graph)
    expect(childInputName(childNode(refusedParent.graph).workflow)).toBe('Latest parent version')
    expect(childNode(refusedParent.graph).workflow.nodes[0]?.name).toBe('Increment')
    expect(refusedParent.graph.nodes.find(node => node.id === 'seed')?.name).toBe('Latest parent seed')
    expectStableParentRoutes(refusedParent.graph)

    const durableResponse = await page.request.get(
      `${API_BASE}/api/v1/nested-workflow-snapshots/${privateSnapshot.session_id}`,
    )
    expect(durableResponse.ok(), await durableResponse.text()).toBeTruthy()
    const durablePrivate = await durableResponse.json() as {
      snapshot_revision: number
      graph: GraphState
    }
    expect(durablePrivate.snapshot_revision).toBeGreaterThanOrEqual(privateSnapshot.snapshot_revision)
    expect(durablePrivate.graph).toEqual(privateSnapshot.graph)

    page.once('dialog', async (dialog) => {
      expect(dialog.message()).toContain("Discard unsaved changes to nested-workflow 'Stable child'?")
      await dialog.dismiss()
    })
    await nestedTab.locator('.dv-default-tab-action').click()
    await expect(page.locator('.nested-workflow-editor')).toBeVisible()
    await page.locator('.vue-flow__node[data-id="increment"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    await expect(page.getByTestId('dataframe-input-name-0')).toHaveValue('Durable private version')
    const afterCancelledClose = await page.request.get(
      `${API_BASE}/api/v1/nested-workflow-snapshots/${privateSnapshot.session_id}`,
    )
    expect(afterCancelledClose.ok()).toBeTruthy()
    await expect(afterCancelledClose.json()).resolves.toMatchObject({
      snapshot_revision: durablePrivate.snapshot_revision,
      graph: durablePrivate.graph,
    })

    page.once('dialog', async (dialog) => {
      expect(dialog.message()).toContain("Discard unsaved changes to nested-workflow 'Stable child'?")
      await dialog.accept()
    })
    await nestedTab.locator('.dv-default-tab-action').click()
    await expect(page.locator('.nested-workflow-editor')).toHaveCount(0)
    await rootTab.click()
    const afterDiscard = await draftGraph(page, name)
    expect(childInputName(childNode(afterDiscard).workflow)).toBe('Latest parent version')
    expectStableParentRoutes(await draftGraph(page, name))
    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    await page.locator('.vue-flow__node[data-id="increment"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    await expect(page.getByTestId('dataframe-input-name-0')).toHaveValue('Latest parent version')
  })

  test('refuses nested Save after its root owner closes without changing either durable state', async ({ page }) => {
    const name = workflowName('nested_missing_parent')
    const displayName = `Nested missing parent ${name}`
    const initial = nestedInterfaceGraph(name, displayName)
    expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name, display_name: displayName },
    })).status()).toBe(201)
    expect((await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
      data: { graph: initial },
    })).ok()).toBeTruthy()

    await page.goto('/')
    await openWorkflow(page, name, displayName)
    const rootBefore = await draftState(page, name)
    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    const nestedTab = page.locator('.dv-tab').filter({ hasText: 'Stable child' })
    await page.locator('.vue-flow__node[data-id="increment"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const privateWrite = page.waitForResponse(response => responseCarriesNestedInputName(response, 'Orphaned private edit'))
    await page.getByTestId('dataframe-input-name-0').fill('Orphaned private edit')
    const privateBefore = await (await privateWrite).json() as {
      session_id: string; snapshot_revision: number; graph: GraphState
    }
    const rootTab = page.locator('.dv-tab').filter({ hasText: displayName })
    await rootTab.getByRole('button', { name: `Close ${displayName}` }).click()
    await expect(rootTab).toHaveCount(0)
    await nestedTab.click()
    const privateBeforeSave = await (await page.request.get(
      `${API_BASE}/api/v1/nested-workflow-snapshots/${privateBefore.session_id}`,
    )).json() as typeof privateBefore
    expect(privateBeforeSave.graph).toEqual(privateBefore.graph)
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await expect(page.getByText(
      'Cannot save nested-workflow because its parent is no longer available.',
      { exact: true },
    )).toBeVisible()
    expect((await draftState(page, name))).toMatchObject({
      draft_revision: rootBefore.draft_revision, graph: rootBefore.graph,
    })
    const privateAfterRefusal = await (await page.request.get(
      `${API_BASE}/api/v1/nested-workflow-snapshots/${privateBefore.session_id}`,
    )).json() as typeof privateBefore
    expect(privateAfterRefusal.snapshot_revision).toBe(privateBeforeSave.snapshot_revision + 1)
    expect(privateAfterRefusal.graph).toEqual(privateBeforeSave.graph)
    expect(await savedGraph(page, name)).toEqual(rootBefore.graph)
    await expect(page.getByTestId('workflow-title')).toContainText('*')

    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain("Discard unsaved changes to nested-workflow 'Stable child'?")
      await dialog.dismiss()
    })
    await nestedTab.locator('.dv-default-tab-action').click()
    await expect(nestedTab).toBeVisible()
    await expect((await page.request.get(`${API_BASE}/api/v1/nested-workflow-snapshots/${privateBefore.session_id}`)).json())
      .resolves.toMatchObject({ snapshot_revision: privateAfterRefusal.snapshot_revision, graph: privateAfterRefusal.graph })

    page.once('dialog', async dialog => { await dialog.accept() })
    await nestedTab.locator('.dv-default-tab-action').click()
    await expect(nestedTab).toHaveCount(0)
    await expect.poll(async () => (
      await page.request.get(`${API_BASE}/api/v1/nested-workflow-snapshots/${privateBefore.session_id}`)
    ).status()).toBe(404)
    await page.getByTestId('workflow-search').fill(displayName)
    await page.getByTestId(`workflow-row-${name}`).dblclick()
    await expect(page.getByTestId('workflow-title')).toContainText(displayName)
    expect((await draftState(page, name))).toMatchObject({
      draft_revision: rootBefore.draft_revision, graph: rootBefore.graph,
    })
    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    await page.locator('.vue-flow__node[data-id="increment"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    await expect(page.getByTestId('dataframe-input-name-0')).toHaveValue('Source table')
  })

  test('waits for an explicit nested snapshot conflict choice without replacing newer private state', async ({ page }) => {
    const name = workflowName('nested_snapshot_conflict')
    const displayName = `Nested snapshot conflict ${name}`
    const initial = nestedInterfaceGraph(name, displayName)
    expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name, display_name: displayName },
    })).status()).toBe(201)
    expect((await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
      data: { graph: initial },
    })).ok()).toBeTruthy()

    await page.goto('/')
    await openWorkflow(page, name, displayName)
    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    await page.locator('.vue-flow__node[data-id="increment"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const inputName = page.getByTestId('dataframe-input-name-0')
    const privateWrite = page.waitForResponse(response => (
      responseCarriesNestedInputName(response, 'My accepted name')
    ))
    await inputName.fill('My accepted name')
    const accepted = await (await privateWrite).json() as {
      session_id: string
      snapshot_revision: number
      graph: GraphState
    }

    async function remoteRename(nextName: string) {
      const currentResponse = await page.request.get(
        `${API_BASE}/api/v1/nested-workflow-snapshots/${accepted.session_id}`,
      )
      expect(currentResponse.ok(), await currentResponse.text()).toBeTruthy()
      const current = await currentResponse.json() as {
        snapshot_revision: number
        graph: GraphState
      }
      const remoteGraph = structuredClone(current.graph)
      remoteGraph.interface.inputs.find(input => input.id === 'child-table-input')!.name = nextName
      const response = await page.request.put(
        `${API_BASE}/api/v1/nested-workflow-snapshots/${accepted.session_id}`,
        { data: { expected_revision: current.snapshot_revision, graph: remoteGraph } },
      )
      expect(response.ok(), await response.text()).toBeTruthy()
      return await response.json() as { snapshot_revision: number; graph: GraphState }
    }

    const remoteA = await remoteRename('Newer private name')
    const refusedWrite = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/nested-workflow-snapshots/${accepted.session_id}`)
      && response.request().method() === 'PUT'
      && response.status() === 409
    ))
    await inputName.fill('My conflicting name')
    await refusedWrite
    const issue = page.getByTestId('canvas-persistence-issue')
    await expect(issue).toContainText('nested-workflow changes need attention')
    await expect(issue.getByTestId('canvas-persistence-use-latest')).toBeVisible()
    await expect(issue.getByTestId('canvas-persistence-resolve-conflict')).toHaveText('Keep my changes')
    await expect(inputName).toHaveValue('My conflicting name')
    const stillRemote = await page.request.get(
      `${API_BASE}/api/v1/nested-workflow-snapshots/${accepted.session_id}`,
    )
    expect(await stillRemote.json()).toMatchObject({
      snapshot_revision: remoteA.snapshot_revision,
      graph: remoteA.graph,
    })
    expect(childInputName(childNode(await draftGraph(page, name)).workflow)).toBe('Source table')

    await issue.getByTestId('canvas-persistence-use-latest').click()
    await expect(issue).toHaveCount(0)
    await expect(inputName).toHaveValue('Newer private name')
    const afterDiscard = await page.request.get(
      `${API_BASE}/api/v1/nested-workflow-snapshots/${accepted.session_id}`,
    )
    expect(await afterDiscard.json()).toMatchObject({
      snapshot_revision: remoteA.snapshot_revision,
      graph: remoteA.graph,
    })

    const remoteB = await remoteRename('Newest private name')
    const secondRefusal = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/nested-workflow-snapshots/${accepted.session_id}`)
      && response.request().method() === 'PUT'
      && response.status() === 409
    ))
    await inputName.fill('Chosen local name')
    await secondRefusal
    await expect(issue).toBeVisible()
    expect((await (await page.request.get(
      `${API_BASE}/api/v1/nested-workflow-snapshots/${accepted.session_id}`,
    )).json()).snapshot_revision).toBe(remoteB.snapshot_revision)
    const resolvedWrite = page.waitForResponse(response => (
      responseCarriesNestedInputName(response, 'Chosen local name')
    ))
    await issue.getByTestId('canvas-persistence-resolve-conflict').click()
    await resolvedWrite
    await expect(issue).toHaveCount(0)
    await expect(inputName).toHaveValue('Chosen local name')
    const resolved = await (await page.request.get(
      `${API_BASE}/api/v1/nested-workflow-snapshots/${accepted.session_id}`,
    )).json() as { snapshot_revision: number; graph: GraphState }
    expect(resolved.snapshot_revision).toBe(remoteB.snapshot_revision + 1)
    expect(childInputName(resolved.graph)).toBe('Chosen local name')
    expect(childInputName(childNode(await draftGraph(page, name)).workflow)).toBe('Source table')

    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await expect.poll(async () => childInputName(childNode(await draftGraph(page, name)).workflow))
      .toBe('Chosen local name')
    await page.locator('.dv-tab').filter({ hasText: displayName }).click()
    await saveWorkflow(page, name)
    await page.reload()
    await openWorkflow(page, name, displayName)
    expect(childInputName(childNode(await draftGraph(page, name)).workflow)).toBe('Chosen local name')
    expectStableParentRoutes(await draftGraph(page, name))
  })

  test('confirms before atomically removing connected nested ports from the parent', async ({ page }) => {
    const name = workflowName('nested_destructive_ports')
    const displayName = `Nested destructive ports ${name}`
    const initial = nestedInterfaceGraph(name, displayName)
    const initialChild = childNode(initial)
    initialChild.workflow.nodes.push({
      type: 'tool', id: 'child_blur', name: 'Child blur', tool_name: 'GaussianBlur',
      position: [600, 180], parameters: { input_image: '/tmp/child-input.tif' },
    })
    initialChild.workflow.interface.inputs.push({
      id: 'child-image-input', name: 'Child image', kind: 'field',
      schema: { type: 'ImageFile' }, default: null,
      targets: [{ node: 'child_blur', port: { kind: 'field', name: 'input_image' } }],
    })
    initialChild.workflow.interface.outputs.push({
      id: 'child-image-output', name: 'Child output', schema: { type: 'ImageFile' },
      source: { node: 'child_blur', column: 'output_image' },
    })
    initial.nodes.push({
      type: 'tool', id: 'parent_blur', name: 'Parent blur', tool_name: 'GaussianBlur',
      position: [780, 360], parameters: { input_image: '/tmp/parent-input.tif' },
    })
    initial.interface.inputs.push({
      id: 'parent-forwarded-image', name: 'Forwarded image', kind: 'field',
      schema: { type: 'ImageFile' }, default: null,
      targets: [
        { node: 'child', port: { kind: 'workflow', id: 'child-image-input' } },
        { node: 'parent_blur', port: { kind: 'field', name: 'input_image' } },
      ],
    })
    initial.interface.outputs.push({
      id: 'parent-forwarded-output', name: 'Forwarded output', schema: { type: 'ImageFile' },
      source: { node: 'child', column: 'child-image-output' },
    })
    expect((await page.request.put(`${API_BASE}/api/v1/graph`, { data: initial })).ok()).toBeTruthy()
    expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name, display_name: displayName },
    })).status()).toBe(201)
    expect((await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
      data: { graph: initial },
    })).ok()).toBeTruthy()

    await page.goto('/')
    await openWorkflow(page, name, displayName)
    const beforeResponse = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)
    const before = (await beforeResponse.json()) as WorkflowDraftResponse
    expect(childNode(before.graph).workflow.interface.inputs.map(input => input.id)).toEqual([
      'child-table-input', 'child-number-input', 'child-image-input',
    ])
    expectStableParentRoutes(before.graph)
    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    await page.locator('.vue-flow__node[data-id="increment"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()

    await page.getByTestId('unpublish-dataframe-0').click()
    await page.getByTestId('interface-input-toggle-number').click()
    await page.locator('.vue-flow__node[data-id="child_blur"]:visible').click()
    await page.getByTestId('interface-input-toggle-input_image').click()
    const privateRemoval = page.waitForResponse(response => (
      responseCarriesEmptyNestedInterface(response)
    ))
    await page.getByTestId('interface-output-toggle-output_image').click()
    const privateSnapshot = await (await privateRemoval).json() as {
      session_id: string
      snapshot_revision: number
      graph: GraphState
    }
    expect(privateSnapshot.graph.interface.inputs).toEqual([])
    expect(privateSnapshot.graph.interface.outputs).toEqual([])
    expect((await draftGraph(page, name))).toEqual(before.graph)

    let parentWriteCount = 0
    page.on('request', (request) => {
      if (
        request.url().endsWith(`/api/v1/workflow-drafts/${name}`)
        && request.method() === 'PUT'
      ) parentWriteCount += 1
    })
    let cancelledMessage = ''
    page.once('dialog', async (dialog) => {
      cancelledMessage = dialog.message()
      await dialog.dismiss()
    })
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    expect(cancelledMessage).toContain(
      'remove 1 parent connection, 1 parent binding, and 2 enclosing interface references',
    )
    const afterCancelResponse = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)
    const afterCancel = (await afterCancelResponse.json()) as WorkflowDraftResponse
    expect(afterCancel.draft_revision).toBe(before.draft_revision)
    expect(afterCancel.graph).toEqual(before.graph)
    expect(parentWriteCount).toBe(0)
    expectStableParentRoutes(afterCancel.graph)
    expect(afterCancel.graph.interface).toEqual(before.graph.interface)
    await expect(page.getByTestId('workflow-title')).toContainText('*')
    const durablePrivateResponse = await page.request.get(
      `${API_BASE}/api/v1/nested-workflow-snapshots/${privateSnapshot.session_id}`,
    )
    const durablePrivate = await durablePrivateResponse.json() as {
      snapshot_revision: number
      graph: GraphState
    }
    expect(durablePrivate.snapshot_revision).toBeGreaterThanOrEqual(privateSnapshot.snapshot_revision)
    expect(durablePrivate.graph.interface.inputs).toEqual([])
    expect(durablePrivate.graph.interface.outputs).toEqual([])

    let routedParentWrites = 0
    await page.route(`**/api/v1/workflow-drafts/${name}`, async (route) => {
      if (route.request().method() !== 'PUT') {
        await route.continue()
        return
      }
      routedParentWrites += 1
      if (routedParentWrites === 1) {
        await route.fulfill({ status: 500, json: { detail: 'forced parent persistence failure' } })
        return
      }
      await route.continue()
    })
    const failedParentWrite = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT'
      && response.status() === 500
    ))
    let confirmedMessage = ''
    page.once('dialog', async (dialog) => {
      confirmedMessage = dialog.message()
      await dialog.accept()
    })
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    expect(confirmedMessage).toContain(
      'remove 1 parent connection, 1 parent binding, and 2 enclosing interface references',
    )
    await failedParentWrite
    expect(parentWriteCount).toBe(1)
    const afterFailure = await draftGraph(page, name)
    expect(afterFailure).toEqual(before.graph)
    await expect(page.getByTestId('workflow-title')).toContainText('*')
    await page.locator('.dv-tab').filter({ hasText: displayName }).click()
    await page.getByTestId('canvas-persistence-dismiss').click()
    await page.locator('.vue-flow__node[data-id="parent_blur"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const siblingWrite = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await page.getByTestId('path-input-input_image').locator('input')
      .fill('/tmp/unrelated-sibling-edit.tif')
    const siblingAccepted = (await siblingWrite).json() as Promise<WorkflowDraftResponse>
    const siblingGraph = await siblingAccepted
    expect(siblingGraph.graph.nodes.find(node => node.id === 'parent_blur')).toMatchObject({
      parameters: { input_image: '/tmp/unrelated-sibling-edit.tif' },
    })
    expect(childNode(siblingGraph.graph).workflow.interface.inputs).toEqual([])
    expect(parentWriteCount).toBe(2)

    await page.locator('.dv-tab').filter({ hasText: 'Stable child' }).click()
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await expect(page.getByTestId('workflow-title')).not.toContainText('*')

    const privateEditB = page.waitForResponse(response => (
      response.url().includes('/api/v1/nested-workflow-snapshots/')
      && response.request().method() === 'PUT'
      && response.status() === 200
      && (response.request().postDataJSON() as { graph?: GraphState } | null)
        ?.graph?.interface.outputs.length === 1
    ))
    await page.getByTestId('interface-output-toggle-output_image').click()
    const privateSnapshotB = await (await privateEditB).json() as {
      snapshot_revision: number
      graph: GraphState
    }
    expect(privateSnapshotB.snapshot_revision).toBeGreaterThan(privateSnapshot.snapshot_revision)
    await expect(page.getByTestId('workflow-title')).toContainText('*')
    expect(siblingGraph.graph.edges).toEqual([])
    expect(childNode(siblingGraph.graph).bindings).toEqual({})
    expect(childNode(siblingGraph.graph).workflow.interface.inputs).toEqual([])
    expect(childNode(siblingGraph.graph).workflow.interface.outputs).toEqual([])
    expect(siblingGraph.graph.interface.inputs).toEqual([{
      ...before.graph.interface.inputs[0]!,
      targets: [{ node: 'parent_blur', port: { kind: 'field', name: 'input_image' } }],
    }])
    expect(siblingGraph.graph.interface.outputs).toEqual([])
    expect(privateSnapshotB.graph.interface.outputs).toHaveLength(1)
    expect(privateSnapshotB.graph.interface.outputs[0]).toMatchObject({
      source: { node: 'child_blur', column: 'output_image' },
      schema: { type: 'ImageFile' },
    })
    const acceptedBWrite = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    const acceptedB = (await acceptedBWrite).json() as Promise<WorkflowDraftResponse>
    const finalB = await acceptedB
    expect(parentWriteCount).toBe(3)
    expect(childNode(finalB.graph).workflow).toEqual(privateSnapshotB.graph)
    expect(finalB.graph.nodes.find(node => node.id === 'parent_blur')).toMatchObject({
      parameters: { input_image: '/tmp/unrelated-sibling-edit.tif' },
    })
    expect(finalB.draft_revision).toBe(siblingGraph.draft_revision + 1)
    await expect(page.getByTestId('workflow-title')).not.toContainText('*')
    await page.locator('.dv-tab').filter({ hasText: displayName }).click()
    await saveWorkflow(page, name)
    await page.reload()
    await openWorkflow(page, name, displayName)
    expect(await draftGraph(page, name)).toEqual(finalB.graph)
  })

  test('applies destructive grandchild ports only through each explicit owner', async ({ page }) => {
    test.setTimeout(90_000)
    const name = workflowName('nested_apply_depth_two')
    const displayName = `Nested apply depth two ${name}`
    const grandchild = graph('grandchild_graph', 'Grandchild graph')
    grandchild.interface.inputs = [{
      id: 'image-input', name: 'Image input', kind: 'field',
      schema: { type: 'ImageFile' }, default: null,
      targets: [{ node: 'blur_1', port: { kind: 'field', name: 'input_image' } }],
    }, {
      id: 'sigma-input', name: 'Sigma input', kind: 'field',
      schema: { type: 'float' }, default: null,
      targets: [{ node: 'blur_1', port: { kind: 'field', name: 'sigma' } }],
    }]
    grandchild.interface.outputs = [{
      id: 'image-output', name: 'Image output', schema: { type: 'ImageFile' },
      source: { node: 'blur_1', column: 'output_image' },
    }]
    const parent = graph('parent_graph', 'Stable child')
    parent.nodes.push({
      type: 'workflow', id: 'grandchild', name: 'Grandchild', position: [540, 180],
      workflow: grandchild, bindings: { 'sigma-input': { __type__: 'float', value: 2 } },
    })
    parent.edges.push({
      type: 'column', id: 'parent-grandchild-edge', source_node: 'blur_1',
      source_output: 'output_image', target_node: 'grandchild', target_input: 'image-input',
    })
    parent.interface.inputs.push({
      id: 'parent-image-input', name: 'Parent image', kind: 'field',
      schema: { type: 'ImageFile' }, default: null,
      targets: [
        { node: 'grandchild', port: { kind: 'workflow', id: 'image-input' } },
        { node: 'blur_1', port: { kind: 'field', name: 'input_image' } },
      ],
    })
    parent.interface.outputs.push({
      id: 'parent-image-output', name: 'Parent output', schema: { type: 'ImageFile' },
      source: { node: 'grandchild', column: 'image-output' },
    })
    const initial = graph(name, displayName)
    initial.nodes.push({
      type: 'workflow', id: 'child', name: 'Stable child', position: [540, 180],
      workflow: parent, bindings: {},
    })
    initial.edges.push({
      type: 'column', id: 'root-child-edge', source_node: 'blur_1',
      source_output: 'output_image', target_node: 'child', target_input: 'parent-image-input',
    })
    initial.interface.inputs.push({
      id: 'root-image-input', name: 'Root image', kind: 'field',
      schema: { type: 'ImageFile' }, default: null,
      targets: [
        { node: 'child', port: { kind: 'workflow', id: 'parent-image-input' } },
        { node: 'blur_1', port: { kind: 'field', name: 'input_image' } },
      ],
    })
    initial.interface.outputs.push({
      id: 'root-image-output', name: 'Root output', schema: { type: 'ImageFile' },
      source: { node: 'child', column: 'parent-image-output' },
    })
    expect((await page.request.put(`${API_BASE}/api/v1/graph`, { data: initial })).ok()).toBeTruthy()
    expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name, display_name: displayName },
    })).status()).toBe(201)
    expect((await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
      data: { graph: initial },
    })).ok()).toBeTruthy()

    await page.goto('/')
    await openWorkflow(page, name, displayName)
    const rootBefore = await draftState(page, name)
    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    const parentTab = page.locator('.dv-tab').filter({ hasText: 'Stable child' })
    const parentOpen = await page.request.post(`${API_BASE}/api/v1/nested-workflow-snapshots/open`, {
      data: {
        owner: { kind: 'root', canvas_id: `workflow:${name}`, workflow_id: name },
        parent_node_id: 'child', graph: parent,
      },
    })
    const parentSnapshot = await parentOpen.json() as {
      session_id: string; snapshot_revision: number; graph: GraphState
    }
    await page.locator('.vue-flow__node[data-id="grandchild"]:visible').dblclick()
    const grandchildTab = page.locator('.dv-tab').filter({ hasText: 'Grandchild' })
    const grandchildOpen = await page.request.post(`${API_BASE}/api/v1/nested-workflow-snapshots/open`, {
      data: {
        owner: { kind: 'nested', session_id: parentSnapshot.session_id },
        parent_node_id: 'grandchild', graph: grandchild,
      },
    })
    const grandchildSnapshot = await grandchildOpen.json() as {
      session_id: string; snapshot_revision: number; graph: GraphState
    }
    await page.locator('.vue-flow__node[data-id="blur_1"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    await page.getByTestId('interface-input-toggle-input_image').click()
    await page.getByTestId('interface-input-toggle-sigma').click()
    const privateWrite = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/nested-workflow-snapshots/${grandchildSnapshot.session_id}`)
      && response.request().method() === 'PUT' && response.status() === 200
      && (response.request().postDataJSON() as { graph?: GraphState }).graph?.interface.outputs.length === 0
    ))
    await page.getByTestId('interface-output-toggle-output_image').click()
    const grandchildPrivate = await (await privateWrite).json() as typeof grandchildSnapshot
    expect(grandchildPrivate.graph.interface).toEqual({ inputs: [], outputs: [] })
    expect((await draftState(page, name))).toMatchObject({
      draft_revision: rootBefore.draft_revision, graph: rootBefore.graph,
    })
    await expect((await page.request.get(`${API_BASE}/api/v1/nested-workflow-snapshots/${parentSnapshot.session_id}`)).json())
      .resolves.toMatchObject({ snapshot_revision: parentSnapshot.snapshot_revision, graph: parentSnapshot.graph })

    let parentWrites = 0
    let rootWrites = 0
    page.on('request', request => {
      if (request.method() !== 'PUT') return
      if (request.url().endsWith(`/api/v1/nested-workflow-snapshots/${parentSnapshot.session_id}`)) parentWrites += 1
      if (request.url().endsWith(`/api/v1/workflow-drafts/${name}`)) rootWrites += 1
    })
    let cancelMessage = ''
    page.once('dialog', async dialog => {
      cancelMessage = dialog.message()
      await dialog.dismiss()
    })
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    expect(cancelMessage).toContain('remove 1 parent connection, 1 parent binding, and 2 enclosing interface references')
    expect(parentWrites).toBe(0)
    expect(rootWrites).toBe(0)
    await expect((await page.request.get(`${API_BASE}/api/v1/nested-workflow-snapshots/${parentSnapshot.session_id}`)).json())
      .resolves.toMatchObject({ snapshot_revision: parentSnapshot.snapshot_revision, graph: parentSnapshot.graph })

    const parentWrite = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/nested-workflow-snapshots/${parentSnapshot.session_id}`)
      && response.request().method() === 'PUT' && response.status() === 200
    ))
    page.once('dialog', async dialog => { await dialog.accept() })
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    const parentApplied = await (await parentWrite).json() as typeof parentSnapshot
    expect(parentApplied.snapshot_revision).toBe(parentSnapshot.snapshot_revision + 1)
    expect(parentWrites).toBe(1)
    expect(rootWrites).toBe(0)
    expect((await draftState(page, name))).toMatchObject({
      draft_revision: rootBefore.draft_revision, graph: rootBefore.graph,
    })
    const appliedGrandchild = parentApplied.graph.nodes.find(node => node.id === 'grandchild')
    expect(appliedGrandchild?.type).toBe('workflow')
    if (appliedGrandchild?.type !== 'workflow') throw new Error('Expected grandchild workflow node')
    expect(appliedGrandchild.workflow).toEqual(grandchildPrivate.graph)
    expect(appliedGrandchild.bindings).toEqual({})
    expect(parentApplied.graph.edges).toEqual([])
    expect(parentApplied.graph.interface.inputs).toEqual([{
      ...parentSnapshot.graph.interface.inputs[0]!,
      targets: [{ node: 'blur_1', port: { kind: 'field', name: 'input_image' } }],
    }])
    expect(parentApplied.graph.interface.outputs).toEqual([])

    await parentTab.click()
    const rootWrite = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT' && response.status() === 200
    ))
    page.once('dialog', async dialog => { await dialog.accept() })
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    const rootApplied = await (await rootWrite).json() as WorkflowDraftResponse
    expect(rootWrites).toBe(1)
    expect(childNode(rootApplied.graph).workflow).toEqual(parentApplied.graph)
    expect(rootApplied.draft_revision).toBe(rootBefore.draft_revision + 1)
    expect(rootApplied.graph.edges).toEqual([rootBefore.graph.edges[0]])
    expect(rootApplied.graph.interface.inputs).toEqual(rootBefore.graph.interface.inputs)
    expect(rootApplied.graph.interface.outputs).toEqual([])
    await page.locator('.dv-tab').filter({ hasText: displayName }).click()
    await saveWorkflow(page, name)
    await page.reload()
    await openWorkflow(page, name, displayName)
    expect(await draftGraph(page, name)).toEqual(rootApplied.graph)
    expect(await savedGraph(page, name)).toEqual(rootApplied.graph)
    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    await page.locator('.vue-flow__node[data-id="grandchild"]:visible').dblclick()
    await expect(page.locator('.vue-flow__node[data-id="blur_1"]:visible')).toBeVisible()
    await expect(grandchildTab).toBeVisible()
  })

  test('preserves nested dirtiness when remounted during a coalesced parent apply', async ({ page }) => {
    const name = workflowName('nested_apply_remount')
    const displayName = `Nested apply remount ${name}`
    const initial = nestedInterfaceGraph(name, displayName)
    expect((await page.request.put(`${API_BASE}/api/v1/graph`, { data: initial })).ok()).toBeTruthy()
    expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name, display_name: displayName },
    })).status()).toBe(201)
    expect((await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
      data: { graph: initial },
    })).ok()).toBeTruthy()

    await page.goto('/')
    await openWorkflow(page, name, displayName)
    const beforeResponse = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)
    const before = (await beforeResponse.json()) as WorkflowDraftResponse
    await page.locator('.vue-flow__node[data-id="child"]').dblclick()
    await page.locator('.vue-flow__node[data-id="increment"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    await page.getByTestId('unpublish-dataframe-0').click()
    const privateRemoval = page.waitForResponse(response => responseCarriesNestedInputCount(response, 0))
    await page.getByTestId('interface-input-toggle-number').click()
    const privateSnapshot = await (await privateRemoval).json() as {
      session_id: string
      graph: GraphState
    }

    let releaseParent!: () => void
    const parentRelease = new Promise<void>((resolve) => { releaseParent = resolve })
    let parentStarted!: () => void
    const parentStart = new Promise<void>((resolve) => { parentStarted = resolve })
    await page.route(`**/api/v1/workflow-drafts/${name}`, async (route) => {
      if (route.request().method() === 'PUT') {
        parentStarted()
        await parentRelease
      }
      await route.continue()
    })
    const acceptedParentWrite = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    page.once('dialog', dialog => dialog.accept())
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await parentStart

    let remountDiscardPrompt = ''
    page.once('dialog', async (dialog) => {
      remountDiscardPrompt = dialog.message()
      await dialog.dismiss()
    })
    await page.locator('.dv-tab').filter({ hasText: 'Stable child' })
      .locator('.dv-default-tab-action').click()
    await expect(page.locator('.nested-workflow-editor')).toBeVisible()
    expect(remountDiscardPrompt).toContain("Discard unsaved changes to nested-workflow 'Stable child'?")
    await expect(page.getByTestId('workflow-title')).toContainText('*')

    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    releaseParent()
    const accepted = (await acceptedParentWrite).json() as Promise<WorkflowDraftResponse>
    const acceptedA = await accepted
    expect(acceptedA.draft_revision).toBe(before.draft_revision + 1)
    expect(childNode(acceptedA.graph).workflow).toEqual(privateSnapshot.graph)
    await expect(page.getByTestId('workflow-title')).toContainText('*')

    let retainedDiscardPrompt = ''
    page.once('dialog', async (dialog) => {
      retainedDiscardPrompt = dialog.message()
      await dialog.dismiss()
    })
    await page.locator('.dv-tab').filter({ hasText: 'Stable child' })
      .locator('.dv-default-tab-action').click()
    await expect(page.locator('.nested-workflow-editor')).toBeVisible()
    expect(retainedDiscardPrompt).toContain("Discard unsaved changes to nested-workflow 'Stable child'?")
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await expect(page.getByTestId('workflow-title')).not.toContainText('*')
    const finalResponse = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${name}`)
    const final = (await finalResponse.json()) as WorkflowDraftResponse
    expect(final.draft_revision).toBe(acceptedA.draft_revision)
    expect(final.graph).toEqual(acceptedA.graph)
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
    const before = await draftState(page, name)
    let allowDeletion = false
    await page.route(`**/api/v1/workflow-drafts/${name}`, async (route) => {
      const body = route.request().method() === 'PUT'
        ? route.request().postDataJSON() as { graph?: GraphState } | null
        : null
      if (body?.graph?.nodes.length === 1 && !allowDeletion) {
        await route.fulfill({ status: 500, json: { detail: 'forced exposed-node write failure' } })
        return
      }
      await route.continue()
    })
    const acceptedDeletion = page.waitForResponse(response => (
      response.url().includes(`/api/v1/workflow-drafts/${name}`)
      && response.request().method() === 'PUT'
      && response.status() === 500
    ))
    await page.locator('.canvas-view').press('Delete')
    const deletionResponse = await acceptedDeletion

    expect(deletionResponse.status()).toBe(500)
    await expect(page.getByTestId('canvas-persistence-retry')).toBeVisible()
    const afterFailure = await draftState(page, name)
    expect(afterFailure.draft_revision).toBe(before.draft_revision)
    expect(afterFailure.graph).toEqual(before.graph)
    allowDeletion = true
    const accepted = await waitForAcceptedGraph(page, name, async () => {
      await page.getByTestId('canvas-persistence-retry').click()
    })
    expect(accepted.draft_revision).toBe(before.draft_revision + 1)
    expect(accepted.graph.nodes.map(node => node.id)).toEqual(['blur_2'])
    expect(accepted.graph.interface.inputs).toEqual([{
      id: 'shared-image-input', name: 'Shared image', kind: 'field',
      schema: { type: 'ImageFile' }, default: null,
      targets: [{ node: 'blur_2', port: { kind: 'field', name: 'input_image' } }],
    }])
    expect(accepted.graph.interface.outputs).toEqual([])
    await expect(page.locator('.vue-flow__node[data-id="blur_1"]')).toHaveCount(0)
    await expect(page.getByTestId('canvas-persistence-issue')).toHaveCount(0)
    await saveWorkflow(page, name)

    const saved = await savedGraph(page, name)
    expect(saved.nodes.map(node => node.id)).toEqual(['blur_2'])
    expect(saved.interface.outputs).toEqual([])
    expect(saved).toEqual(accepted.graph)
    await page.reload()
    await openWorkflow(page, name, displayName)
    expect(await draftGraph(page, name)).toEqual(saved)
    await expect(page.locator('.vue-flow__node[data-id="blur_2"]')).toBeVisible()
    await expect(page.locator('.vue-flow__node[data-id="blur_1"]')).toHaveCount(0)
  })
})
