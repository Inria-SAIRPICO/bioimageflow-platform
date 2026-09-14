import { test, expect } from '@playwright/test'
import type { Locator, Page } from '@playwright/test'
import type { GraphState } from '../../src/api/types'
import type { WorkflowDraftResponse } from '../../src/api/workflowDrafts'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

function deriveWorkflowId(value: string): string {
  return value
    .trim()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .replace(/_+/g, '_')
    .toLowerCase()
}

async function seedTools(page: Page) {
  const response = await page.request.post(`${API_BASE}/api/v1/dev/seed`)
  expect(response.ok()).toBeTruthy()
}

async function waitForToolsRequest(page: Page) {
  const toolsResponse = page.waitForResponse(
    response => response.url().includes('/api/v1/tools') && response.status() === 200,
  )
  await page.goto('/')
  await toolsResponse
  await expect(page.locator('#bioimageflow-app')).toBeVisible()
}

async function createWorkflow(page: Page, displayName: string) {
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: 'New', exact: true }).click()
  await page.getByTestId('workflow-display-name-input').fill(displayName)
  await page.getByTestId('workflow-dialog-submit').click()
  await expect(page.getByTestId('workflow-title')).toContainText(displayName)
}

async function openWorkflowMenuItem(page: Page, label: string) {
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: label, exact: true }).click()
}

async function addToolNode(
  page: Page,
  toolName: string,
  position: { x: number; y: number },
) {
  await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
  await page.getByTestId('tool-search').fill(toolName)
  const tool = page.getByTestId(`tool-item-${toolName}`)
  await expect(tool).toBeVisible({ timeout: 5000 })
  const canvas = page.locator('.vue-flow')
  await expect(canvas).toBeVisible()
  const nodeCount = await page.locator('.vue-flow__node').count()
  await tool.dragTo(canvas, { targetPosition: position })
  const node = page.locator('.vue-flow__node').nth(nodeCount)
  await expect(node).toBeVisible({ timeout: 5000 })
  return node
}

async function currentDraft(page: Page, workflowName: string): Promise<WorkflowDraftResponse> {
  const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`)
  expect(response.ok()).toBeTruthy()
  return response.json()
}

async function connectColumns(
  page: Page,
  source: Locator,
  sourceOutput: string,
  target: Locator,
  targetInput: string,
) {
  const sourceHandle = source.locator(`.body-outputs .vue-flow__handle[data-handleid$="${sourceOutput}"]`)
  const targetHandle = target.locator(`.body-inputs .vue-flow__handle[data-handleid$="${targetInput}"]`)
  const sourceBox = await sourceHandle.boundingBox()
  const targetBox = await targetHandle.boundingBox()
  expect(sourceBox).not.toBeNull()
  expect(targetBox).not.toBeNull()
  await page.mouse.move(sourceBox!.x + sourceBox!.width / 2, sourceBox!.y + sourceBox!.height / 2)
  await page.mouse.down()
  await page.mouse.move(targetBox!.x + targetBox!.width / 2, targetBox!.y + targetBox!.height / 2, { steps: 8 })
  await page.mouse.up()
}

function toolNode(graph: GraphState, nodeId: string) {
  const node = graph.nodes.find(candidate => candidate.id === nodeId)
  expect(node?.type).toBe('tool')
  if (!node || node.type !== 'tool') throw new Error(`Missing tool node ${nodeId}`)
  return node
}

test('typed parameter controls refuse invalid lists, recover, reset, connect, and persist', async ({ page }) => {
  await seedTools(page)
  await waitForToolsRequest(page)

  const displayName = `Parameter Controls ${Date.now()} ${Math.floor(Math.random() * 10000)}`
  const workflowName = deriveWorkflowId(displayName)
  const otherDisplayName = `Parameter Switch ${Date.now()} ${Math.floor(Math.random() * 10000)}`
  const otherWorkflowName = deriveWorkflowId(otherDisplayName)

  try {
    const toolsResponse = await page.request.get(`${API_BASE}/api/v1/tools`)
    expect(toolsResponse.ok()).toBeTruthy()
    const tools = await toolsResponse.json()
    expect(tools.find((tool: { name: string }) => tool.name === 'ParameterControls')).toMatchObject({
      name: 'ParameterControls',
      display_name: 'Parameter Controls',
      package: 'bioimageflow-e2e-dynamic',
      package_version: '1.0.0',
      tool_type: 'ProcessingTool',
      inputs: {
        mode: { type: 'str', default: 'fast', choices: ['fast', 'precise'], connectable: 'never' },
        enabled: { type: 'bool', default: true, connectable: 'never' },
        labels: { type: 'list', default: ['alpha', 'beta'], connectable: 'never' },
        connected_number: { type: 'int', default: 3, connectable: 'by_default' },
      },
      outputs: { configured_number: { type: 'int' } },
    })

    await createWorkflow(page, displayName)
    const sourceNode = await addToolNode(page, 'SeedNumbers', { x: 80, y: 180 })
    const parameterNode = await addToolNode(page, 'ParameterControls', { x: 340, y: 180 })
    const sourceId = await sourceNode.getAttribute('data-id')
    const parameterId = await parameterNode.getAttribute('data-id')
    expect(sourceId).toBeTruthy()
    expect(parameterId).toBeTruthy()

    await parameterNode.click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const nodePanel = page.getByTestId('panel-nodePanel')
    await expect(nodePanel.locator('.tool-name')).toHaveText('ParameterControls')

    const modeRow = nodePanel.locator('.param-row').filter({ hasText: /^mode/ })
    const enabledRow = nodePanel.locator('.param-row').filter({ hasText: /^enabled/ })
    const labelsRow = nodePanel.locator('.param-row').filter({ hasText: /^labels/ })
    const connectedRow = nodePanel.locator('.param-row').filter({ hasText: /^connected_number/ })

    const modeSelect = modeRow.getByTestId('choices-select-mode')
    await modeSelect.click()
    await page.getByRole('option', { name: 'precise', exact: true }).click()
    await enabledRow.locator('.p-checkbox').click()

    await expect.poll(async () => {
      const draft = await currentDraft(page, workflowName)
      const node = draft.graph.nodes.find(candidate => candidate.id === parameterId)
      return node?.type === 'tool' ? node.parameters : undefined
    }).toMatchObject({
      mode: 'precise',
      enabled: false,
      labels: ['alpha', 'beta'],
      connected_number: 3,
    })
    const beforeInvalid = await currentDraft(page, workflowName)
    const beforeInvalidNode = toolNode(beforeInvalid.graph, parameterId!)
    expect(beforeInvalid.validation).toMatchObject({ valid: true, errors: [] })
    expect(beforeInvalidNode.parameters).toMatchObject({
      mode: 'precise',
      enabled: false,
      labels: ['alpha', 'beta'],
      connected_number: 3,
    })

    const labelsInput = labelsRow.getByTestId('list-input-labels')
    await labelsInput.fill('["gamma",')
    await labelsInput.press('Tab')
    await expect(labelsRow.locator('.list-input-error')).toBeVisible()
    await expect(labelsRow.locator('.list-input-error')).toContainText('JSON')
    const refused = await currentDraft(page, workflowName)
    expect(toolNode(refused.graph, parameterId!).parameters.labels).toEqual(['alpha', 'beta'])
    expect(refused.draft_revision).toBe(beforeInvalid.draft_revision)

    await labelsInput.fill('["gamma", "delta"]')
    await labelsInput.press('Tab')
    await expect(labelsRow.locator('.list-input-error')).toHaveCount(0)
    await expect.poll(async () => {
      const draft = await currentDraft(page, workflowName)
      return {
        validation: draft.validation,
        parameters: toolNode(draft.graph, parameterId!).parameters,
      }
    }).toMatchObject({
      validation: { valid: true, errors: [] },
      parameters: {
        mode: 'precise',
        enabled: false,
        labels: ['gamma', 'delta'],
        connected_number: 3,
      },
    })

    await modeRow.getByTestId('reset-default').click()
    await expect(modeSelect).toContainText('fast')
    await expect.poll(async () => toolNode(
      (await currentDraft(page, workflowName)).graph,
      parameterId!,
    ).parameters.mode).toBe('fast')

    await connectedRow.getByTestId('pin-toggle').click()
    await expect(parameterNode.locator('.body-inputs .vue-flow__handle[data-handleid$="connected_number"]'))
      .toBeVisible()
    await connectColumns(page, sourceNode, 'number', parameterNode, 'connected_number')
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)
    await expect(connectedRow.locator('.connected-source')).toHaveText('number of Seed Numbers 1')
    await expect(connectedRow.locator('input, textarea, [role="combobox"]')).toHaveCount(0)

    await expect.poll(async () => {
      const draft = await currentDraft(page, workflowName)
      return {
        validation: draft.validation,
        activeWorkflow: draft.workflow_id,
        parameters: toolNode(draft.graph, parameterId!).parameters,
        edges: draft.graph.edges.map(({ id: _id, ...edge }) => edge),
      }
    }).toMatchObject({
      validation: { valid: true, errors: [] },
      activeWorkflow: workflowName,
      parameters: { mode: 'fast', enabled: false, labels: ['gamma', 'delta'] },
      edges: [{
        type: 'column',
        source_node: sourceId,
        source_output: 'number',
        target_node: parameterId,
        target_input: 'connected_number',
      }],
    })
    expect(toolNode((await currentDraft(page, workflowName)).graph, parameterId!).parameters)
      .not.toHaveProperty('connected_number')

    const saveResponse = page.waitForResponse(response =>
      response.url().endsWith(`/api/v1/workflows/${workflowName}`)
      && response.request().method() === 'PUT'
      && response.status() === 200,
    )
    await openWorkflowMenuItem(page, 'Save')
    await saveResponse
    await expect(page.getByTestId('workflow-title')).not.toContainText('*')

    const savedResponse = await page.request.get(`${API_BASE}/api/v1/workflows/${workflowName}`)
    expect(savedResponse.ok()).toBeTruthy()
    const saved = await savedResponse.json()

    await createWorkflow(page, otherDisplayName)
    await openWorkflowMenuItem(page, 'Open')
    await page.getByTestId('workflow-open-search').fill(workflowName)
    await page.getByTestId(`workflow-open-option-${workflowName}`).click()
    await page.getByTestId('workflow-open-submit').click()
    await expect(page.getByTestId('workflow-title')).toContainText(saved.graph.display_name)
    await expect(page.locator(`.vue-flow__node[data-id="${parameterId}"]`)).toBeVisible()
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)

    const reopened = await currentDraft(page, workflowName)
    expect(reopened.workflow_id).toBe(workflowName)
    expect(reopened.validation).toMatchObject({ valid: true, errors: [] })
    expect(reopened.graph).toEqual(saved.graph)

    await page.locator(`.vue-flow__node[data-id="${parameterId}"]`).click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    await expect(modeSelect).toContainText('fast')
    await expect(enabledRow.locator('input[type="checkbox"]')).not.toBeChecked()
    await expect(labelsInput).toHaveValue('[\n  "gamma",\n  "delta"\n]')
    await expect(connectedRow.locator('.connected-source')).toHaveText('number of Seed Numbers 1')
  } finally {
    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`).catch(() => undefined)
    await page.request.delete(`${API_BASE}/api/v1/workflows/${otherWorkflowName}`).catch(() => undefined)
  }
})
