import { expect, test, type Page } from '@playwright/test'
import type { GraphState, WorkflowNodeState } from '../../src/api/types'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`

function fixture(name: string): GraphState {
  const leaf: GraphState = {
    schema_version: 1, name: 'leaf', display_name: 'Leaf',
    nodes: [{ type: 'tool', id: 'controls', name: 'Controls', tool_name: 'ParameterControls', position: [180, 180], parameters: {} }],
    edges: [], config: { engine: 'direct', execution: 'sequential' },
    interface: { inputs: [
      { id: 'amount', name: 'Public amount', kind: 'field', schema: { type: 'int' }, default: { __type__: 'int', value: 60 }, targets: [{ node: 'controls', port: { kind: 'field', name: 'connected_number' } }] },
      { id: 'mode', name: 'Public mode', kind: 'field', schema: { type: 'str' }, default: { __type__: 'str', value: 'precise' }, targets: [{ node: 'controls', port: { kind: 'field', name: 'mode' } }] },
    ], outputs: [] },
  }
  const wrap = (id: string, child: GraphState): GraphState => ({
    schema_version: 1, name: id, display_name: id,
    nodes: [{ type: 'workflow', id: 'child', name: `${id} child`, position: [250, 180], workflow: child, bindings: {} }],
    edges: [], config: { engine: 'direct', execution: 'sequential' },
    interface: { inputs: child.interface.inputs.map(input => ({
      ...input, targets: [{ node: 'child', port: { kind: 'workflow', id: input.id } }],
    })), outputs: [] },
  })
  return wrap(name, wrap('middle', wrap('inner', leaf)))
}

function child(graph: GraphState): WorkflowNodeState {
  const node = graph.nodes[0]
  if (node?.type !== 'workflow') throw new Error('Expected workflow node')
  return node
}

async function save(page: Page): Promise<void> {
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
}

test('workflow controls retain defaults, pins and private depth-two edits through save and reopen', async ({ page }) => {
  expect((await page.request.post(`${API}/dev/seed`)).ok()).toBeTruthy()
  const name = `workflow_controls_${Date.now()}`
  expect((await page.request.post(`${API}/workflows`, { data: { name } })).ok()).toBeTruthy()
  const setup = await page.request.put(`${API}/workflows/${name}`, { data: { graph: fixture(name) } })
  expect(setup.ok(), await setup.text()).toBeTruthy()
  const requests: string[] = []
  page.on('request', request => {
    if (request.url().includes('/execution/run') || request.url().includes('/environments/install')) requests.push(request.url())
  })
  const open = async () => {
    await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
    await page.getByTestId('workflow-search').fill(name)
    await page.getByTestId(`workflow-row-${name}`).dblclick()
    await expect(page.getByTestId('workflow-title')).toContainText(name)
  }
  const select = async () => {
    await page.locator('.vue-flow__node[data-id="child"]:visible').click()
    await page.locator('.dv-tab').filter({ hasText: /^Nodes$/ }).click()
  }
  const amount = () => page.getByTestId('workflow-binding-amount').locator('input')
  const row = () => page.locator('.param-row').filter({ has: page.getByTestId('workflow-binding-amount') })
  await page.goto('/')
  await open()
  await select()
  await expect(amount()).toHaveValue('60')
  await expect(row()).toContainText('Using workflow default')
  // The leaf's default is 3; the public interface's 60 is authoritative.
  await expect(row().getByTestId('pin-toggle')).toBeVisible()
  const handle = page.locator('.vue-flow__node[data-id="child"]:visible [data-handleid="bif:v1:workflow-input:amount"]')
  await expect(handle).toBeVisible()
  await row().getByTestId('pin-toggle').click()
  await expect(handle).toHaveCount(0)
  await row().getByTestId('pin-toggle').click()
  await expect(handle).toBeVisible()
  await expect(page.getByTestId('workflow-binding-mode')).toContainText('precise')
  // Constant-only inputs still have publication controls, without column pins.
  const mode = page.locator('.param-row').filter({ has: page.getByTestId('workflow-binding-mode') })
  await expect(mode.getByTestId('pin-toggle')).toHaveCount(0)
  await expect(mode.getByTestId('interface-input-toggle-mode')).toBeVisible()
  await amount().fill('71')
  await amount().blur()
  await row().getByTestId('reset-default').click()
  await expect(amount()).toHaveValue('60')
  await page.locator('.vue-flow__pane:visible').click({ position: { x: 20, y: 20 } })
  await page.keyboard.press('Control+z')
  await select()
  await expect(amount()).toHaveValue('71')

  // Two private editor levels use the same row and recursive metadata.
  await page.locator('.vue-flow__node[data-id="child"]:visible').dblclick()
  await expect(page.getByTestId('workflow-title')).toContainText(`${name} child`)
  await page.locator('.vue-flow__node[data-id="child"]:visible').dblclick()
  await expect(page.getByTestId('workflow-title')).toContainText('middle child')
  await select()
  await expect(amount()).toHaveValue('60')
  await amount().fill('83')
  await amount().blur()
  const appliedInner = page.waitForResponse(response => response.url().includes('/nested-workflow-snapshots/') && response.request().method() === 'PUT' && response.ok())
  await save(page)
  await appliedInner
  await page.locator('.dv-tab').filter({ hasText: new RegExp(`^${name} child$`) }).click()
  await save(page)
  await page.locator('.dv-tab').filter({ hasText: new RegExp(`^${name}$`) }).click()
  const saved = page.waitForResponse(response => response.url().endsWith(`/workflows/${name}`) && response.request().method() === 'PUT')
  await save(page)
  expect((await saved).ok()).toBeTruthy()
  const persisted = (await (await page.request.get(`${API}/workflows/${name}`)).json()).graph as GraphState
  expect(child(persisted).bindings.amount).toEqual({ __type__: 'int', value: 71 })
  expect(child(child(child(persisted).workflow).workflow).bindings.amount).toEqual({ __type__: 'int', value: 83 })
  expect(JSON.stringify(persisted)).not.toContain('pinnedInputs')
  await page.reload()
  await open()
  await select()
  await expect(amount()).toHaveValue('71')
  expect(requests).toEqual([])
})

test('connected workflow parameters retain their source and protect the connected pin', async ({ page }) => {
  expect((await page.request.post(`${API}/dev/seed`)).ok()).toBeTruthy()
  const name = `workflow_connected_controls_${Date.now()}`
  expect((await page.request.post(`${API}/workflows`, { data: { name } })).ok()).toBeTruthy()
  const graph = fixture(name)
  graph.nodes.push({ type: 'tool', id: 'seed', name: 'Number source', tool_name: 'SeedNumbers', position: [0, 180], parameters: {} })
  graph.edges.push({ type: 'column', id: 'connected-number', source_node: 'seed', source_output: 'number', target_node: 'child', target_input: 'amount' })
  const setup = await page.request.put(`${API}/workflows/${name}`, { data: { graph } })
  expect(setup.ok(), await setup.text()).toBeTruthy()
  await page.goto('/')
  await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).click()
  await page.getByTestId('workflow-search').fill(name)
  await page.getByTestId(`workflow-row-${name}`).dblclick()
  await expect(page.getByTestId('workflow-title')).toContainText(name)
  await page.locator('.vue-flow__node[data-id="child"]').click()
  await page.locator('.dv-tab').filter({ hasText: /^Nodes$/ }).click()
  const row = page.locator('.param-row').filter({ has: page.locator('label').filter({ hasText: /^Public amount$/ }) })
  await expect(row.locator('.connected-source')).toContainText('number')
  await expect(row.getByTestId('workflow-binding-amount')).toHaveCount(0)
  await expect(row.getByTestId('reset-default')).toBeDisabled()
  await expect(row.getByTestId('pin-toggle')).toBeDisabled()
  await expect(page.locator('.vue-flow__node[data-id="child"] [data-handleid="bif:v1:workflow-input:amount"]')).toBeVisible()
})
