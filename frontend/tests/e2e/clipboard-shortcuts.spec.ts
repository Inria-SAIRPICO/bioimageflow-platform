import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import type { GraphState } from '../../src/api/types'
import type { WorkflowDraftResponse } from '../../src/api/workflowDrafts'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`
const SOURCE_ID = 'clipboard_source'
const MIDDLE_ID = 'clipboard_middle'
const OUTSIDE_ID = 'clipboard_outside'
const INTERNAL_EDGE_ID = 'clipboard_internal_edge'
const EXTERNAL_EDGE_ID = 'clipboard_external_edge'

function uniqueWorkflowName(prefix: string): string {
  const project = test.info().project.name.replace(/[^a-zA-Z0-9_-]/g, '_')
  return `${prefix}_${project}_${Date.now()}_${Math.floor(Math.random() * 10000)}`
}

function clipboardGraph(workflowName: string): GraphState {
  return {
    schema_version: 1,
    name: workflowName,
    display_name: workflowName,
    nodes: [
      {
        type: 'tool', id: SOURCE_ID, name: 'Clipboard source', tool_name: 'SeedNumbers',
        position: [100, 180], parameters: {}, resources: {}, output_templates: {},
        enabled: true, collapsed: false,
      },
      {
        type: 'tool', id: MIDDLE_ID, name: 'Clipboard middle', tool_name: 'IncrementNumbers',
        position: [430, 180], parameters: { number: 1 }, resources: {}, output_templates: {},
        enabled: true, collapsed: false,
      },
      {
        type: 'tool', id: OUTSIDE_ID, name: 'Clipboard outside', tool_name: 'IncrementNumbers',
        position: [760, 180], parameters: { number: 1 }, resources: {}, output_templates: {},
        enabled: true, collapsed: false,
      },
    ],
    edges: [
      {
        type: 'dataframe', id: INTERNAL_EDGE_ID, source_node: SOURCE_ID,
        target_node: MIDDLE_ID, target_position: 0,
      },
      {
        type: 'dataframe', id: EXTERNAL_EDGE_ID, source_node: MIDDLE_ID,
        target_node: OUTSIDE_ID, target_position: 0,
      },
    ],
    interface: { inputs: [], outputs: [] },
    config: { engine: 'direct', execution: 'sequential' },
  }
}

async function fetchDraft(page: Page, workflowName: string): Promise<WorkflowDraftResponse> {
  const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`)
  expect(response.ok()).toBeTruthy()
  return response.json() as Promise<WorkflowDraftResponse>
}

async function createAndOpenFixture(page: Page, workflowName: string): Promise<void> {
  expect((await page.request.post(`${API_BASE}/api/v1/dev/seed`)).ok()).toBeTruthy()
  const graph = clipboardGraph(workflowName)
  const validation = await page.request.put(`${API_BASE}/api/v1/graph`, { data: graph })
  expect(validation.ok(), await validation.text()).toBeTruthy()
  expect(await validation.json()).toMatchObject({ valid: true, errors: [] })
  expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
    data: { name: workflowName, display_name: workflowName },
  })).status()).toBe(201)
  expect((await page.request.put(`${API_BASE}/api/v1/workflows/${workflowName}`, {
    data: { graph },
  })).ok()).toBeTruthy()

  await page.goto('/')
  await expect(page.locator('#bioimageflow-app')).toBeVisible()
  await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
  await page.getByTestId('workflow-search').fill(workflowName)
  await page.getByTestId(`workflow-row-${workflowName}`).dblclick()
  await expect(page.getByTestId('workflow-title')).toContainText(workflowName)
  await expect(page.locator('.vue-flow__node')).toHaveCount(3)
  await expect.poll(async () => (await fetchDraft(page, workflowName)).validation.valid).toBe(true)
}

async function pressCanvasShortcut(page: Page, shortcut: string): Promise<void> {
  await page.locator('.vue-flow__pane').click({ position: { x: 20, y: 20 } })
  await page.keyboard.press(shortcut)
}

test.describe('canvas clipboard and shortcuts', () => {
  let workflowName: string
  const additionalWorkflows: string[] = []

  test.beforeEach(async ({ page }) => {
    workflowName = uniqueWorkflowName('clipboard_shortcuts')
    await createAndOpenFixture(page, workflowName)
  })

  test.afterEach(async ({ page }) => {
    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`).catch(() => undefined)
    await Promise.all(additionalWorkflows.splice(0).map(name => (
      page.request.delete(`${API_BASE}/api/v1/workflows/${name}`).catch(() => undefined)
    )))
  })

  test('copies a connected selection, pastes only its internal structure, and refuses malformed clipboard data', async ({ page }) => {
    const source = page.locator(`.vue-flow__node[data-id="${SOURCE_ID}"]`)
    const middle = page.locator(`.vue-flow__node[data-id="${MIDDLE_ID}"]`)
    await source.click()
    await middle.click({ modifiers: ['Shift'] })
    await expect(source).toHaveClass(/selected/)
    await expect(middle).toHaveClass(/selected/)

    await page.keyboard.press('Control+c')

    const acceptedPaste = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${workflowName}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await page.keyboard.press('Control+v')
    await acceptedPaste
    await expect(page.locator('.vue-flow__node')).toHaveCount(5)
    await expect(page.locator('.vue-flow__edge')).toHaveCount(3)

    const pasted = await fetchDraft(page, workflowName)
    expect(pasted.validation).toMatchObject({ valid: true, errors: [] })
    const newNodes = pasted.graph.nodes.filter(node => ![SOURCE_ID, MIDDLE_ID, OUTSIDE_ID].includes(node.id))
    expect(newNodes).toHaveLength(2)
    expect(new Set(newNodes.map(node => node.id)).size).toBe(2)
    expect(newNodes.map(node => node.name)).toEqual(['Clipboard source 1', 'Clipboard middle 1'])
    const pastedEdge = pasted.graph.edges.find(edge => ![INTERNAL_EDGE_ID, EXTERNAL_EDGE_ID].includes(edge.id))
    expect(pastedEdge).toMatchObject({
      type: 'dataframe',
      source_node: newNodes[0].id,
      target_node: newNodes[1].id,
      target_position: 0,
    })
    expect(pasted.graph.edges.filter(edge => (
      newNodes.some(node => node.id === edge.source_node || node.id === edge.target_node)
    ))).toHaveLength(1)

    await page.reload()
    await expect(page.locator('.vue-flow__node')).toHaveCount(5)
    await expect(page.locator('.vue-flow__edge')).toHaveCount(3)
    const reloaded = await fetchDraft(page, workflowName)
    expect(reloaded.graph).toEqual(pasted.graph)

    await page.evaluate(() => {
      Object.defineProperty(navigator, 'clipboard', {
        configurable: true,
        value: {
          readText: async () => '{malformed clipboard',
          writeText: async () => undefined,
        },
      })
    })
    const beforeRefusal = await fetchDraft(page, workflowName)
    await page.locator('.vue-flow__pane').click({ position: { x: 20, y: 20 } })
    await page.keyboard.press('Control+v')
    await expect(page.getByText('Clipboard does not contain BioImageFlow nodes')).toBeVisible()
    const afterRefusal = await fetchDraft(page, workflowName)
    expect(afterRefusal.draft_revision).toBe(beforeRefusal.draft_revision)
    expect(afterRefusal.graph).toEqual(beforeRefusal.graph)
  })

  test('routes core shortcuts to the active canvas and preserves text-field input', async ({ page }) => {
    test.setTimeout(60_000)
    const inactiveName = workflowName
    const activeName = uniqueWorkflowName('shortcut_active')
    additionalWorkflows.push(activeName)
    const activeGraph = clipboardGraph(activeName)
    expect((await page.request.post(`${API_BASE}/api/v1/workflows`, {
      data: { name: activeName, display_name: activeName },
    })).status()).toBe(201)
    expect((await page.request.put(`${API_BASE}/api/v1/workflows/${activeName}`, {
      data: { graph: activeGraph },
    })).ok()).toBeTruthy()

    await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
    await page.getByTestId('workflow-search').fill(activeName)
    await page.getByTestId(`workflow-row-${activeName}`).dblclick()
    await expect(page.getByTestId('workflow-title')).toContainText(activeName)
    await expect(page.locator('.vue-flow__node')).toHaveCount(3)
    const inactiveBaseline = await fetchDraft(page, inactiveName)

    const pane = page.locator('.vue-flow__pane')
    const source = page.locator(`.vue-flow__node[data-id="${SOURCE_ID}"]`)
    const middle = page.locator(`.vue-flow__node[data-id="${MIDDLE_ID}"]`)
    const outside = page.locator(`.vue-flow__node[data-id="${OUTSIDE_ID}"]`)
    await pressCanvasShortcut(page, 'Control+a')
    await expect(page.locator('.vue-flow__node.selected')).toHaveCount(3)
    await page.keyboard.press('Escape')
    await expect(page.locator('.vue-flow__node.selected')).toHaveCount(0)

    await outside.click()
    let acceptedEdit = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${activeName}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await page.keyboard.press('Delete')
    await acceptedEdit
    await expect(page.locator('.vue-flow__node')).toHaveCount(2)
    acceptedEdit = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${activeName}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await pressCanvasShortcut(page, 'Control+z')
    await acceptedEdit
    await expect(outside).toBeVisible()

    await outside.click()
    acceptedEdit = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${activeName}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await page.keyboard.press('Backspace')
    await acceptedEdit
    await expect(page.locator('.vue-flow__node')).toHaveCount(2)
    acceptedEdit = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${activeName}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await pressCanvasShortcut(page, 'Control+z')
    await acceptedEdit

    await source.click()
    await middle.click({ modifiers: ['Shift'] })
    await page.keyboard.press('Control+c')
    acceptedEdit = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${activeName}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await page.keyboard.press('Control+v')
    await acceptedEdit
    await expect(page.locator('.vue-flow__node')).toHaveCount(5)
    expect((await fetchDraft(page, inactiveName)).graph).toEqual(inactiveBaseline.graph)

    const zoom = () => page.locator('.vue-flow__transformationpane').evaluate(element => (
      new DOMMatrix(getComputedStyle(element).transform).a
    ))
    await page.locator('.vue-flow__controls-zoomout').click()
    await page.locator('.vue-flow__controls-zoomout').click()
    const reducedZoom = await zoom()
    await pressCanvasShortcut(page, 'f')
    await expect.poll(zoom).not.toBeCloseTo(reducedZoom, 3)

    await middle.click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const parameter = page.getByTestId('panel-nodePanel').locator('.param-number input')
    await parameter.fill('7')
    const forcedValidation = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${activeName}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await pressCanvasShortcut(page, 'Control+Enter')
    await forcedValidation
    await expect.poll(async () => (await fetchDraft(page, activeName)).validation.valid).toBe(true)

    await middle.click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const nodePanel = page.getByTestId('panel-nodePanel')
    await nodePanel.locator('.node-name').dblclick()
    const nameInput = nodePanel.locator('.name-input')
    await nameInput.fill('Uncommitted active-canvas name')
    const beforeTyping = await fetchDraft(page, activeName)
    await nameInput.press('Delete')
    await nameInput.press('Backspace')
    await nameInput.press('Control+a')
    await nameInput.press('Control+c')
    await nameInput.press('Control+v')
    await nameInput.press('Control+s')
    await nameInput.press('Control+Enter')
    await nameInput.press('Control+f')
    await nameInput.press('f')
    await nameInput.press('Backspace')
    await nameInput.press('Escape')
    await expect(nameInput).toBeFocused()
    await expect(middle).toHaveClass(/selected/)
    expect((await fetchDraft(page, activeName)).graph).toEqual(beforeTyping.graph)
    await expect(middle).toBeVisible()

    await pressCanvasShortcut(page, 'Control+f')
    const toolSearch = page.getByTestId('tool-search')
    await expect(toolSearch).toBeFocused()
    await expect(page.locator('.dv-tab.dv-active-tab').filter({ hasText: 'Tools' })).toBeVisible()

    const saved = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflows/${activeName}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await pressCanvasShortcut(page, 'Control+s')
    await saved
    const savedActive = await (await page.request.get(`${API_BASE}/api/v1/workflows/${activeName}`)).json()
    expect(savedActive.graph).toEqual((await fetchDraft(page, activeName)).graph)
    const savedInactive = await (await page.request.get(`${API_BASE}/api/v1/workflows/${inactiveName}`)).json()
    expect(savedInactive.graph).toEqual(inactiveBaseline.graph)
  })
})
