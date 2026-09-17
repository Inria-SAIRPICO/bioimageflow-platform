import { test, expect } from '@playwright/test'
import type { Locator, Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import type { WorkflowDraftResponse } from '../../src/api/workflowDrafts'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

type ToolMetadata = {
  name: string
  display_name: string
  package: string
  package_version: string
  tool_type: string
  documentation?: string
  accepts_upstream?: boolean
  inputs: Record<string, { type: string; required?: boolean; connectable?: string }>
  outputs: Record<string, { type: string }>
}

async function seedTools(page: Page) {
  const response = await page.request.post(`${API_BASE}/api/v1/dev/seed`)
  expect(response.ok()).toBeTruthy()
}

async function seedNumbersTool(page: Page): Promise<ToolMetadata> {
  const response = await page.request.get(`${API_BASE}/api/v1/tools`)
  expect(response.ok()).toBeTruthy()
  const tools = (await response.json()) as ToolMetadata[]
  const tool = tools.find((candidate) => candidate.name === 'SeedNumbers')
  expect(tool, 'expected the named SeedNumbers development tool').toBeTruthy()
  expect(tool).toMatchObject({
    name: 'SeedNumbers',
    display_name: 'Seed Numbers',
    package: 'bioimageflow-dev-seed',
    package_version: '0.1.0',
    tool_type: 'DataFrameTool',
    documentation: 'Create a deterministic three-row dataframe for development tests.',
    accepts_upstream: false,
    inputs: {},
    outputs: {
      number: { type: 'int' },
      label: { type: 'str' },
    },
  })
  return tool
}

async function waitForToolsRequest(page: Page) {
  const toolsResponse = page.waitForResponse(
    (resp) => resp.url().includes('/api/v1/tools') && resp.status() === 200,
  )
  await page.goto('/')
  await toolsResponse
  await expect(page.locator('#bioimageflow-app')).toBeVisible()
}

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

async function createEditableWorkflow(page: Page): Promise<string> {
  const displayName = `Canvas Interactions ${Date.now()} ${Math.floor(Math.random() * 10000)}`
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: 'New', exact: true }).click()
  await page.getByTestId('workflow-display-name-input').fill(displayName)
  await page.getByTestId('workflow-dialog-submit').click()
  await expect(page.getByTestId('workflow-title')).toContainText(displayName)
  return deriveWorkflowId(displayName)
}

async function seedNumbersRow(page: Page) {
  const source = await seedNumbersTool(page)
  await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
  await page.locator('[data-testid="tool-search"]').fill(source.name)
  const tool = page.getByTestId(`tool-item-${source.name}`)
  await expect(tool).toBeVisible({ timeout: 5000 })
  await expect(tool.locator('.tool-list-name')).toHaveText(source.display_name)
  return tool
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
  // dragTo presses on the source before waiting for its destination.
  // Startup can still be mounting the canvas while the tool list is visible.
  await expect(canvas).toBeVisible()
  const nodeCount = await page.locator('.vue-flow__node').count()
  await tool.dragTo(canvas, { targetPosition: position })
  const node = page.locator('.vue-flow__node').nth(nodeCount)
  await expect(node).toBeVisible({ timeout: 5000 })
  return node
}

async function connectDataFrames(page: Page, source: Locator, target: Locator) {
  const sourceHandle = source.locator('.header-outputs .vue-flow__handle')
  const targetHandle = target.locator('.header-inputs .vue-flow__handle').last()
  const sourceBox = await sourceHandle.boundingBox()
  const targetBox = await targetHandle.boundingBox()
  expect(sourceBox).not.toBeNull()
  expect(targetBox).not.toBeNull()
  await page.mouse.move(sourceBox!.x + sourceBox!.width / 2, sourceBox!.y + sourceBox!.height / 2)
  await page.mouse.down()
  await page.mouse.move(targetBox!.x + targetBox!.width / 2, targetBox!.y + targetBox!.height / 2, { steps: 8 })
  await page.mouse.up()
}

async function openWorkflowMenuItem(page: Page, label: string) {
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: label, exact: true }).click()
}

async function currentDraft(page: Page, workflowName: string): Promise<WorkflowDraftResponse> {
  const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`)
  expect(response.ok()).toBeTruthy()
  return response.json()
}

async function moveNode(page: Page, node: Locator, delta: { x: number; y: number }) {
  const box = await node.boundingBox()
  expect(box).not.toBeNull()
  const draftResponse = page.waitForResponse(
    (resp) =>
      resp.url().includes('/api/v1/workflow-drafts/') &&
      resp.request().method() === 'PUT' &&
      resp.status() === 200,
  )
  const start = {
    x: box!.x + box!.width / 2,
    y: box!.y + Math.min(24, box!.height / 2),
  }
  await page.mouse.move(start.x, start.y)
  await page.mouse.down()
  await page.mouse.move(start.x + delta.x, start.y + delta.y, { steps: 8 })
  await page.mouse.up()
  await draftResponse
}

async function expectNodeNear(
  node: Locator,
  expected: { x: number; y: number },
) {
  await expect.poll(async () => {
    const box = await node.boundingBox()
    return box !== null
      && Math.abs(box.x - expected.x) <= 10
      && Math.abs(box.y - expected.y) <= 10
  }).toBe(true)
}

function expectedResultTableRows() {
  return Array.from({ length: 60 }, (_, sourceRow) => ({
    sourceRow,
    label: `${sourceRow % 2 === 0 ? 'keep' : 'drop'}-${String(sourceRow).padStart(2, '0')}`,
    score: (sourceRow * 17) % 61,
  }))
    .filter(row => row.label.startsWith('keep-'))
    .sort((left, right) => right.score - left.score)
}

function parseCsv(csv: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let field = ''
  let quoted = false

  for (let index = 0; index < csv.length; index += 1) {
    const character = csv[index]
    if (quoted) {
      if (character === '"' && csv[index + 1] === '"') {
        field += '"'
        index += 1
      } else if (character === '"') {
        quoted = false
      } else {
        field += character
      }
    } else if (character === '"') {
      quoted = true
    } else if (character === ',') {
      row.push(field)
      field = ''
    } else if (character === '\n') {
      row.push(field.endsWith('\r') ? field.slice(0, -1) : field)
      rows.push(row)
      row = []
      field = ''
    } else {
      field += character
    }
  }
  if (field || row.length) {
    row.push(field)
    rows.push(row)
  }
  return rows
}

async function projectionQueryAfter(
  page: Page,
  action: () => Promise<void>,
) {
  const responsePromise = page.waitForResponse(response =>
    response.url().endsWith('/api/v1/data-table/query')
    && response.request().method() === 'POST'
    && response.status() === 200,
  )
  await action()
  const response = await responsePromise
  return {
    request: response.request().postDataJSON(),
    result: await response.json(),
  }
}

test.describe('Canvas interactions', () => {
  test.describe.configure({ mode: 'serial' })
  let workflowName: string

  test.beforeEach(async ({ page }) => {
    await seedTools(page)
    await waitForToolsRequest(page)
    workflowName = await createEditableWorkflow(page)
  })

  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== testInfo.expectedStatus) {
      await testInfo.attach('canvas-before-cleanup', {
        body: await page.screenshot(),
        contentType: 'image/png',
      })
      await testInfo.attach('page-before-cleanup', {
        body: await page.locator('body').ariaSnapshot(),
        contentType: 'text/plain',
      })
    }
    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`).catch(() => undefined)
  })

  test('single click toggles tool information and double click persists an interactive node', { tag: '@critical' }, async ({ page }) => {
    const tool = await seedNumbersRow(page)
    await expect(page.locator('.vue-flow')).toBeVisible()
    const transformationPane = page.locator('.vue-flow__transformationpane')
    const initialTransform = await transformationPane.evaluate(
      element => window.getComputedStyle(element).transform,
    )
    await tool.click()
    const documentation = page.getByTestId('tool-doc-SeedNumbers')
    await expect(documentation).toBeVisible()
    await expect(documentation.locator('h4')).toHaveText('Seed Numbers')
    await expect(documentation.locator('p')).toHaveText(
      'Create a deterministic three-row dataframe for development tests.',
    )
    await expect(page.getByTestId('tool-info-SeedNumbers')).toHaveCount(0)
    await expect(page.locator('.vue-flow__node')).toHaveCount(0)

    await tool.click()
    await expect(documentation).toHaveCount(0)
    await expect(page.locator('.vue-flow__node')).toHaveCount(0)

    const draftResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes('/api/v1/workflow-drafts/') &&
        resp.request().method() === 'PUT' &&
        resp.status() === 200,
    )
    await tool.dblclick()
    expect((await draftResponse).status()).toBe(200)

    const node = page.locator('.vue-flow__node')
    await expect(node).toHaveCount(1)
    await expect(node).toBeVisible({ timeout: 5000 })
    await expect.poll(() => transformationPane.evaluate(
      element => window.getComputedStyle(element).transform,
    )).toBe(initialTransform)
    await expect(node.locator('.header-inputs .vue-flow__handle')).toHaveCount(0)
    await expect(node.locator('.header-outputs .vue-flow__handle')).toHaveCount(1)
    await expect(node.locator('.header-outputs .pin-label')).toHaveText('DataFrame')
    await expect(node.locator('.body-inputs .vue-flow__handle')).toHaveCount(0)
    await expect(node.locator('.body-outputs .pin-label')).toHaveText(['number', 'label'])

    await node.click()
    await expect(node).toHaveClass(/selected/)

    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const nodePanel = page.locator('[data-testid="panel-nodePanel"]')
    await expect(nodePanel).toBeVisible()
    await expect(nodePanel.locator('.node-name')).toHaveText('Seed Numbers 1')
    await expect(nodePanel.locator('.tool-name')).toHaveText('SeedNumbers')
    await expect(nodePanel.locator('.package-info')).toHaveText('bioimageflow-dev-seed v0.1.0')

    await expect.poll(async () => {
      const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`)
      expect(response.ok()).toBeTruthy()
      const draft: WorkflowDraftResponse = await response.json()
      return {
        validation: draft.validation,
        nodes: draft.graph.nodes.map(node => ({
          type: node.type,
          name: node.name,
          tool_name: node.type === 'tool' ? node.tool_name : undefined,
          parameters: node.type === 'tool' ? node.parameters : undefined,
        })),
      }
    }).toMatchObject({
      validation: { valid: true, errors: [] },
      nodes: [{ type: 'tool', name: 'Seed Numbers 1', tool_name: 'SeedNumbers', parameters: {} }],
    })
  })

  test('recovers a failed catalog double-click add without duplicating the node', async ({ page }) => {
    const tool = await seedNumbersRow(page)
    const baseline = await currentDraft(page, workflowName)
    expect(baseline.graph.nodes).toEqual([])
    let failedWrites = 0
    await page.route(`**/api/v1/workflow-drafts/${workflowName}`, async route => {
      if (route.request().method() !== 'PUT' || failedWrites !== 0) return route.continue()
      failedWrites += 1
      await route.fulfill({ status: 500, json: { detail: 'forced catalog add failure' } })
    })

    const failedWrite = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${workflowName}`)
      && response.request().method() === 'PUT'
      && response.status() === 500
    ))
    await tool.dblclick()
    await failedWrite
    expect(failedWrites).toBe(1)
    const localNode = page.locator('.vue-flow__node')
    await expect(localNode).toHaveCount(1)
    await expect(localNode.locator('.node-name')).toHaveText('Seed Numbers 1')
    const nodeId = await localNode.getAttribute('data-id')
    expect(nodeId).toBeTruthy()
    await expect(page.getByTestId('canvas-persistence-issue')).toContainText('forced catalog add failure')
    await expect(page.getByTestId('canvas-persistence-retry')).toBeVisible()
    const refused = await currentDraft(page, workflowName)
    expect(refused.draft_revision).toBe(baseline.draft_revision)
    expect(refused.graph).toEqual(baseline.graph)

    const acceptedWrite = page.waitForResponse(response => (
      response.url().endsWith(`/api/v1/workflow-drafts/${workflowName}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await page.getByTestId('canvas-persistence-retry').click()
    await acceptedWrite
    await expect(page.getByTestId('canvas-persistence-issue')).toHaveCount(0)
    await expect(localNode).toHaveCount(1)
    const accepted = await currentDraft(page, workflowName)
    expect(accepted.draft_revision).toBe(baseline.draft_revision + 1)
    expect(accepted.validation).toMatchObject({ valid: true, errors: [] })
    expect(accepted.graph.nodes).toMatchObject([{
      id: nodeId,
      type: 'tool',
      name: 'Seed Numbers 1',
      tool_name: 'SeedNumbers',
      parameters: {},
    }])
    expect(accepted.graph.nodes).toHaveLength(1)

    await page.reload()
    await expect(page.locator(`.vue-flow__node[data-id="${nodeId}"]`)).toBeVisible()
    await expect(page.locator('.vue-flow__node')).toHaveCount(1)
    const reopened = await currentDraft(page, workflowName)
    expect(reopened.draft_revision).toBe(accepted.draft_revision)
    expect(reopened.graph).toEqual(accepted.graph)
  })

  test('drags a named catalog tool to the requested canvas position', async ({ page }) => {
    const tool = await seedNumbersRow(page)
    const draftResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes('/api/v1/workflow-drafts/') &&
        resp.request().method() === 'PUT' &&
        resp.status() === 200,
    )
    await tool.dragTo(page.locator('.vue-flow'), {
      targetPosition: { x: 260, y: 180 },
    })
    expect((await draftResponse).status()).toBe(200)

    const node = page.locator('.vue-flow__node')
    await expect(node).toHaveCount(1)
    await expect(node).toBeVisible({ timeout: 5000 })
    await expect.poll(async () => {
      const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`)
      expect(response.ok()).toBeTruthy()
      const draft: WorkflowDraftResponse = await response.json()
      const created = draft.graph.nodes[0]
      return {
        validation: draft.validation,
        nodeCount: draft.graph.nodes.length,
        toolName: created?.type === 'tool' ? created.tool_name : undefined,
        positionXNearTarget: created?.position !== undefined
          && Math.abs(created.position[0] - 260) < 1,
        positionYNearTarget: created?.position !== undefined
          && Math.abs(created.position[1] - 180) < 1,
      }
    }).toMatchObject({
      validation: { valid: true, errors: [] },
      nodeCount: 1,
      toolName: 'SeedNumbers',
      positionXNearTarget: true,
      positionYNearTarget: true,
    })
  })

  test('new dynamic tools connect cleanly and expose their resolved columns', async ({ page }) => {
    // Execution policy is fixture setup; the journey below creates the nodes and edge in the GUI.
    await page.goto('about:blank')
    const initialResponse = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`)
    expect(initialResponse.ok()).toBeTruthy()
    const initial: WorkflowDraftResponse = await initialResponse.json()
    const configured = await page.request.put(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`, {
      data: {
        expected_revision: initial.draft_revision,
        updated_by: 'frontend',
        graph: { ...initial.graph, config: { ...initial.graph.config, engine: 'wetlands', execution: 'sequential' } },
      },
    })
    expect(configured.ok()).toBeTruthy()
    await page.goto('/')
    await expect(page.getByTestId('workflow-title')).toContainText(initial.graph.display_name)
    const generate = await addToolNode(page, 'Generate', { x: 220, y: 180 })
    const crossJoin = await addToolNode(page, 'CrossJoin', { x: 520, y: 180 })

    await generate.click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const nodePanel = page.getByTestId('panel-nodePanel')
    const columnNameRow = nodePanel.locator('.param-row').filter({ hasText: 'column_name' })
    await columnNameRow.locator('input').fill('sensitivity')
    await nodePanel.getByTestId('list-input-values').fill('[0.1, 0.2]')
    await nodePanel.getByTestId('list-input-values').press('Tab')
    await expect(nodePanel.locator('.list-input-error')).toHaveCount(0)
    await expect(generate.locator('.body-inputs .vue-flow__handle')).toHaveCount(0)

    await connectDataFrames(page, generate, crossJoin)

    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)
    await expect(page.locator('.vue-flow__connection')).toHaveCount(0)
    await expect(crossJoin.locator('.body-outputs .pin-label')).toContainText('sensitivity', {
      timeout: 5000,
    })

    const sourceId = await generate.getAttribute('data-id')
    const targetId = await crossJoin.getAttribute('data-id')
    expect(sourceId).toBeTruthy()
    expect(targetId).toBeTruthy()
    await expect.poll(async () => {
      const response = await page.request.get(`${API_BASE}/api/v1/workflow-drafts/${workflowName}`)
      expect(response.ok()).toBeTruthy()
      const draft: WorkflowDraftResponse = await response.json()
      return {
        validation: draft.validation,
        config: { engine: draft.graph.config.engine, execution: draft.graph.config.execution },
        edges: draft.graph.edges.map(({ id: _id, ...edge }) => edge),
      }
    }).toMatchObject({
      validation: { valid: true, errors: [] },
      config: { engine: 'wetlands', execution: 'sequential' },
      edges: [{ type: 'dataframe', source_node: sourceId, target_node: targetId, target_position: 0 }],
    })

    const runResponse = page.waitForResponse(response =>
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST',
    )
    await page.getByTestId('run-workflow-button').click()
    expect((await runResponse).status()).toBe(202)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete', { timeout: 30000 })
    const result = await page.request.post(`${API_BASE}/api/v1/nodes/${targetId}/data/query`, {
      data: { workflow_name: workflowName },
    })
    expect(result.ok()).toBeTruthy()
    expect(await result.json()).toMatchObject({
      columns: ['sensitivity'],
      rows: [{ sensitivity: 0.1 }, { sensitivity: 0.2 }],
      total_rows: 2,
    })
  })

  test('builds, runs, inspects, saves, and reopens a real workflow through the GUI', { tag: '@critical' }, async ({ page }) => {
    const seedTool = await seedNumbersRow(page)
    await seedTool.click()
    const documentation = page.getByTestId('tool-doc-SeedNumbers')
    await expect(documentation).toBeVisible()
    await expect(documentation.locator('h4')).toHaveText('Seed Numbers')
    await expect(documentation.locator('p')).toHaveText(
      'Create a deterministic three-row dataframe for development tests.',
    )
    await expect(page.locator('.vue-flow__node')).toHaveCount(0)

    await seedTool.dblclick()
    const seedNode = page.locator('.vue-flow__node').filter({ hasText: 'Seed Numbers 1' })
    await expect(seedNode).toBeVisible()

    const incrementNode = await addToolNode(page, 'IncrementNumbers', { x: 420, y: 220 })
    await incrementNode.click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const nodePanel = page.getByTestId('panel-nodePanel')
    await expect(nodePanel.locator('.tool-name')).toHaveText('IncrementNumbers')
    const numberRow = nodePanel.locator('.param-row').filter({ hasText: 'Number column to increment' })
    const numberInput = numberRow.locator('input.p-inputnumber-input')
    await numberInput.fill('10')
    await numberInput.press('Tab')

    const seedId = await seedNode.getAttribute('data-id')
    const incrementId = await incrementNode.getAttribute('data-id')
    expect(seedId).toBeTruthy()
    expect(incrementId).toBeTruthy()
    await expect.poll(async () => {
      const draft = await currentDraft(page, workflowName)
      const increment = draft.graph.nodes.find(node => node.id === incrementId)
      return increment?.type === 'tool' ? increment.parameters.number : undefined
    }).toBe(10)

    await connectDataFrames(page, seedNode, incrementNode)
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)
    await expect.poll(async () => {
      const draft = await currentDraft(page, workflowName)
      return {
        validation: draft.validation,
        nodes: draft.graph.nodes.map(node => node.type === 'tool'
          ? { id: node.id, tool_name: node.tool_name, parameters: node.parameters }
          : { id: node.id, type: node.type }),
        edges: draft.graph.edges.map(({ id: _id, ...edge }) => edge),
      }
    }).toMatchObject({
      validation: { valid: true, errors: [] },
      nodes: [
        { id: seedId, tool_name: 'SeedNumbers', parameters: {} },
        { id: incrementId, tool_name: 'IncrementNumbers', parameters: { number: 10 } },
      ],
      edges: [{ type: 'dataframe', source_node: seedId, target_node: incrementId, target_position: 0 }],
    })

    const runResponse = page.waitForResponse(response =>
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST',
    )
    await page.getByTestId('run-workflow-button').click()
    expect((await runResponse).status()).toBe(202)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete', { timeout: 30000 })

    await incrementNode.click()
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    const resultTable = page.getByTestId('data-table-panel').locator('.p-datatable')
    await expect(resultTable).toBeVisible()
    const headers = await resultTable.locator('.p-datatable-thead th').allTextContents()
    const numberColumn = headers.findIndex(header => header.includes('number') && !header.includes('number_plus_one'))
    const labelColumn = headers.findIndex(header => header.includes('label'))
    const resultColumn = headers.findIndex(header => header.includes('number_plus_one'))
    expect(numberColumn).toBeGreaterThanOrEqual(0)
    expect(labelColumn).toBeGreaterThanOrEqual(0)
    expect(resultColumn).toBeGreaterThanOrEqual(0)
    const resultRows = resultTable.locator('.p-datatable-tbody tr')
    await expect(resultRows).toHaveCount(3)
    await expect(resultRows.nth(0).locator('td').nth(numberColumn)).toHaveText('1')
    await expect(resultRows.nth(0).locator('td').nth(labelColumn)).toHaveText('one')
    await expect(resultRows.nth(0).locator('td').nth(resultColumn)).toHaveText('2')
    await expect(resultRows.nth(1).locator('td').nth(numberColumn)).toHaveText('2')
    await expect(resultRows.nth(1).locator('td').nth(labelColumn)).toHaveText('two')
    await expect(resultRows.nth(1).locator('td').nth(resultColumn)).toHaveText('3')
    await expect(resultRows.nth(2).locator('td').nth(numberColumn)).toHaveText('3')
    await expect(resultRows.nth(2).locator('td').nth(labelColumn)).toHaveText('three')
    await expect(resultRows.nth(2).locator('td').nth(resultColumn)).toHaveText('4')

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
    expect(saved.graph).toMatchObject({
      nodes: [
        { id: seedId, tool_name: 'SeedNumbers', parameters: {} },
        { id: incrementId, tool_name: 'IncrementNumbers', parameters: { number: 10 } },
      ],
      edges: [{ type: 'dataframe', source_node: seedId, target_node: incrementId, target_position: 0 }],
    })

    const otherDisplayName = `Journey Switch ${Date.now()} ${Math.floor(Math.random() * 10000)}`
    const otherWorkflowName = deriveWorkflowId(otherDisplayName)
    try {
      await openWorkflowMenuItem(page, 'New')
      await page.getByTestId('workflow-display-name-input').fill(otherDisplayName)
      await page.getByTestId('workflow-dialog-submit').click()
      await expect(page.getByTestId('workflow-title')).toContainText(otherDisplayName)

      await openWorkflowMenuItem(page, 'Open')
      await page.getByTestId('workflow-open-search').fill(workflowName)
      await page.getByTestId(`workflow-open-option-${workflowName}`).click()
      await page.getByTestId('workflow-open-submit').click()
      await expect(page.getByTestId('workflow-title')).toContainText(saved.graph.display_name)
      await expect(page.locator(`.vue-flow__node[data-id="${seedId}"]`)).toBeVisible()
      await expect(page.locator(`.vue-flow__node[data-id="${incrementId}"]`)).toBeVisible()
      await expect(page.locator('.vue-flow__edge')).toHaveCount(1)

      const reopened = await currentDraft(page, workflowName)
      expect(reopened.validation).toMatchObject({ valid: true, errors: [] })
      expect(reopened.graph).toEqual(saved.graph)
    } finally {
      await page.request.delete(`${API_BASE}/api/v1/workflows/${otherWorkflowName}`).catch(() => undefined)
    }
  })

  test('recovers a real Direct failure without publishing a partial result', { tag: '@critical' }, async ({ page }) => {
    const source = await addToolNode(page, 'SeedNumbers', { x: 160, y: 180 })
    const target = await addToolNode(page, 'ControlledDirectNumbers', { x: 450, y: 180 })
    const sourceId = await source.getAttribute('data-id')
    const targetId = await target.getAttribute('data-id')
    expect(sourceId).toBeTruthy()
    expect(targetId).toBeTruthy()
    await connectDataFrames(page, source, target)
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)

    await target.click()
    await page.locator('.dv-tab').filter({ hasText: /^Nodes$/ }).click()
    const failRow = page.getByTestId('panel-nodePanel').locator('.param-row').filter({ hasText: 'Raise a controlled execution error' })
    await failRow.locator('.p-checkbox').click()
    await expect.poll(async () => {
      const draft = await currentDraft(page, workflowName)
      return draft.graph.nodes.find(node => node.id === targetId && node.type === 'tool')?.parameters.fail === true
        ? draft : null
    }).not.toBeNull()
    const accepted = await currentDraft(page, workflowName)
    expect(accepted.validation).toMatchObject({ valid: true, errors: [] })
    expect(accepted.graph.edges).toMatchObject([{
      type: 'dataframe', source_node: sourceId, target_node: targetId, target_position: 0,
    }])

    const firstRunPromise = page.waitForResponse(response => response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST')
    await page.getByTestId('run-workflow-button').click()
    const firstRun = await firstRunPromise
    expect(firstRun.status()).toBe(202)
    expect(firstRun.request().postDataJSON()).toMatchObject({
      workflow_name: workflowName, draft_revision: accepted.draft_revision, graph: accepted.graph,
    })
    const firstIdentity = (await firstRun.json()).execution_id
    expect(await (await page.request.get(`${API_BASE}/api/v1/executions/${firstIdentity}`)).json()).toMatchObject({
      backend: 'direct', workflow_id: workflowName, draft_revision: accepted.draft_revision,
    })
    await expect.poll(async () => {
      const response = await page.request.get(`${API_BASE}/api/v1/execution/status`)
      const status = await response.json()
      return [status.state, status.last_result?.success, status.node_statuses?.[targetId!]?.status]
    }, { timeout: 30_000 }).toEqual(['idle', false, 'failed'])
    expect(await (await page.request.get(`${API_BASE}/api/v1/execution/status`)).json()).toMatchObject({
      execution_id: firstIdentity, workflow_id: workflowName,
      draft_revision: accepted.draft_revision,
      node_statuses: { [sourceId!]: { status: 'executed' }, [targetId!]: { status: 'failed' } },
    })
    await expect(page.getByTestId('execution-banner-headline')).toContainText('Controlled Direct failure')
    const failedResult = await page.request.post(`${API_BASE}/api/v1/nodes/${targetId}/data/query`, {
      data: { workflow_name: workflowName },
    })
    expect(failedResult.status()).toBe(404)
    const sourceResult = await page.request.post(`${API_BASE}/api/v1/nodes/${sourceId}/data/query`, {
      data: { workflow_name: workflowName },
    })
    expect((await sourceResult.json()).rows).toEqual([
      { number: 1, label: 'one' }, { number: 2, label: 'two' }, { number: 3, label: 'three' },
    ])

    await expect(failRow.locator('.p-checkbox')).toBeEnabled()
    await failRow.locator('.p-checkbox').click()
    await expect.poll(async () => {
      const draft = await currentDraft(page, workflowName)
      return draft.graph.nodes.find(node => node.id === targetId && node.type === 'tool')?.parameters.fail
    }).toBe(false)
    const corrected = await currentDraft(page, workflowName)
    expect(corrected.draft_revision).toBe(accepted.draft_revision + 1)
    expect(corrected.validation).toMatchObject({ valid: true, errors: [] })
    const rerunPromise = page.waitForResponse(response => response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST')
    await page.getByTestId('run-workflow-button').click()
    const rerun = await rerunPromise
    expect(rerun.status()).toBe(202)
    expect(rerun.request().postDataJSON()).toMatchObject({
      workflow_name: workflowName, draft_revision: corrected.draft_revision, graph: corrected.graph,
    })
    const secondIdentity = (await rerun.json()).execution_id
    expect(secondIdentity).not.toBe(firstIdentity)
    expect(await (await page.request.get(`${API_BASE}/api/v1/executions/${secondIdentity}`)).json()).toMatchObject({
      backend: 'direct', workflow_id: workflowName, draft_revision: corrected.draft_revision,
    })
    await expect.poll(async () => {
      const status = await (await page.request.get(`${API_BASE}/api/v1/execution/status`)).json()
      return [status.state, status.last_result?.success, status.node_statuses?.[targetId!]?.status]
    }, { timeout: 30_000 }).toEqual(['idle', true, 'executed'])
    const targetResult = await page.request.post(`${API_BASE}/api/v1/nodes/${targetId}/data/query`, {
      data: { workflow_name: workflowName },
    })
    expect(await targetResult.json()).toMatchObject({
      columns: ['number', 'label', 'number_plus_one'],
      rows: [
        { number: 1, label: 'one', number_plus_one: 2 },
        { number: 2, label: 'two', number_plus_one: 3 },
        { number: 3, label: 'three', number_plus_one: 4 },
      ],
      total_rows: 3,
    })
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    await expect(page.getByTestId('data-table-panel').locator('.p-datatable-tbody tr')).toHaveCount(3)
    await page.reload()
    await expect(page.getByTestId('workflow-title')).toContainText('Canvas Interactions')
    expect((await currentDraft(page, workflowName)).graph).toEqual(corrected.graph)
    const retained = await (await page.request.get(`${API_BASE}/api/v1/execution/status`)).json()
    expect(retained).toMatchObject({
      execution_id: secondIdentity, workflow_id: workflowName,
      draft_revision: corrected.draft_revision,
      last_result: { success: true },
    })
    const retainedResult = await page.request.post(`${API_BASE}/api/v1/nodes/${targetId}/data/query`, {
      data: { workflow_name: workflowName },
    })
    expect((await retainedResult.json()).rows.map((row: { number_plus_one: number }) => row.number_plus_one)).toEqual([2, 3, 4])
  })

  test('filters, sorts, pages, and exports an exact real execution result', { tag: '@critical' }, async ({ page }) => {
    const toolsResponse = await page.request.get(`${API_BASE}/api/v1/tools`)
    expect(toolsResponse.ok()).toBeTruthy()
    const tools = await toolsResponse.json() as ToolMetadata[]
    expect(tools.find(tool => tool.name === 'ResultTableFixture')).toMatchObject({
      tool_type: 'DataFrameTool',
      accepts_upstream: false,
      outputs: {
        source_row: { type: 'int' },
        label: { type: 'str' },
        score: { type: 'int' },
      },
    })
    const resultNode = await addToolNode(page, 'ResultTableFixture', { x: 280, y: 180 })
    const nodeId = await resultNode.getAttribute('data-id')
    expect(nodeId).toBeTruthy()
    await expect.poll(async () => {
      const draft = await currentDraft(page, workflowName)
      return {
        valid: draft.validation.valid,
        toolName: draft.graph.nodes[0]?.type === 'tool'
          ? draft.graph.nodes[0].tool_name
          : null,
      }
    }).toEqual({ valid: true, toolName: 'ResultTableFixture' })

    const runResponse = page.waitForResponse(response =>
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST',
    )
    await page.getByTestId('run-workflow-button').click()
    expect((await runResponse).status()).toBe(202)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete', { timeout: 30000 })

    await resultNode.click()
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    const nodeTable = page.getByTestId('merged-data-table')
    const dataTable = nodeTable.locator('.p-datatable')
    const paginator = nodeTable.getByTestId('node-data-paginator')
    await expect(dataTable).toBeVisible()
    await expect(paginator).toContainText('1–60 of 60')

    const filtered = await projectionQueryAfter(page, async () => {
      await dataTable.getByRole('button', { name: 'Filter label' }).click()
      await page.getByRole('combobox', { name: 'Filter operator' }).click()
      await page.getByRole('option', { name: 'Starts with' }).click()
      await page.getByRole('textbox', { name: 'Filter value' }).fill('keep-')
      await page.getByRole('button', { name: 'Apply' }).click()
    })
    expect(filtered.request).toMatchObject({
      page: 0,
      page_size: 250,
      sort_by: null,
      filters: [{ column: 's0:label', operator: 'starts_with', value: 'keep-' }],
    })
    expect(filtered.result).toMatchObject({ total_rows: 30, unfiltered_total_rows: 60 })
    await expect(nodeTable.getByTestId('node-data-active-filters')).toContainText('label: starts with keep-')
    await expect(paginator).toContainText('1–30 of 30 (60 unfiltered)')

    await projectionQueryAfter(page, async () => {
      await dataTable.getByRole('button', { name: 'Sort score' }).click()
    })
    const sorted = await projectionQueryAfter(page, async () => {
      await dataTable.getByRole('button', { name: 'Sort score' }).click()
    })
    expect(sorted.request).toMatchObject({
      page: 0,
      sort_by: 's0:score',
      sort_order: 'desc',
      filters: [{ column: 's0:label', operator: 'starts_with', value: 'keep-' }],
    })

    const expectedRows = expectedResultTableRows()
    expect(sorted.result.rows).toEqual(expectedRows.map(row => ({
      index: String(row.sourceRow),
      source_rows: { [nodeId!]: row.sourceRow },
      values: {
        's0:source_row': row.sourceRow,
        's0:label': row.label,
        's0:score': row.score,
      },
    })))
    await expect(dataTable.getByRole('button', { name: 'Sort score' }).locator('i')).toHaveClass(/pi-sort-amount-down/)

    const headers = await dataTable.locator('.p-datatable-thead th').allTextContents()
    const sourceRowColumn = headers.findIndex(header => header.includes('source_row'))
    const labelColumn = headers.findIndex(header => header.includes('label'))
    const scoreColumn = headers.findIndex(header => header.includes('score'))
    expect([sourceRowColumn, labelColumn, scoreColumn].every(index => index >= 0)).toBe(true)
    const visibleRows = dataTable.locator('.p-datatable-tbody tr')
    await expect(visibleRows).toHaveCount(30)
    for (const [index, expected] of expectedRows.entries()) {
      const cells = visibleRows.nth(index).locator('td')
      await expect(cells.nth(sourceRowColumn)).toHaveText(String(expected.sourceRow))
      await expect(cells.nth(labelColumn)).toHaveText(expected.label)
      await expect(cells.nth(scoreColumn)).toHaveText(String(expected.score))
    }

    const firstPage = await projectionQueryAfter(page, async () => {
      await paginator.getByRole('combobox', { name: 'Rows per page' }).click()
      await page.getByRole('option', { name: '25', exact: true }).click()
    })
    expect(firstPage.request).toMatchObject({ page: 0, page_size: 25 })
    expect(firstPage.result.rows.map((row: { source_rows: Record<string, number> }) => row.source_rows[nodeId!]))
      .toEqual(expectedRows.slice(0, 25).map(row => row.sourceRow))
    await expect(paginator).toContainText('1–25 of 30 (60 unfiltered)')
    await expect(visibleRows).toHaveCount(25)

    const secondPage = await projectionQueryAfter(page, async () => {
      await paginator.getByRole('button', { name: 'Next page' }).click()
    })
    expect(secondPage.request).toMatchObject({ page: 1, page_size: 25 })
    expect(secondPage.result.rows.map((row: { source_rows: Record<string, number> }) => row.source_rows[nodeId!]))
      .toEqual(expectedRows.slice(25).map(row => row.sourceRow))
    await expect(paginator).toContainText('26–30 of 30 (60 unfiltered)')
    await expect(visibleRows).toHaveCount(5)
    for (const [index, expected] of expectedRows.slice(25).entries()) {
      const cells = visibleRows.nth(index).locator('td')
      await expect(cells.nth(sourceRowColumn)).toHaveText(String(expected.sourceRow))
      await expect(cells.nth(labelColumn)).toHaveText(expected.label)
      await expect(cells.nth(scoreColumn)).toHaveText(String(expected.score))
    }

    const directPage = await projectionQueryAfter(page, async () => {
      const pageInput = paginator.getByTestId('node-data-page-input').locator('input')
      await pageInput.fill('1')
      await pageInput.press('Enter')
    })
    expect(directPage.request).toMatchObject({ page: 0, page_size: 25 })
    expect(directPage.result.rows.map((row: { source_rows: Record<string, number> }) => row.source_rows[nodeId!]))
      .toEqual(expectedRows.slice(0, 25).map(row => row.sourceRow))
    await expect(paginator).toContainText('1–25 of 30 (60 unfiltered)')
    await expect(visibleRows).toHaveCount(25)

    const largerPage = await projectionQueryAfter(page, async () => {
      await paginator.getByRole('combobox', { name: 'Rows per page' }).click()
      await page.getByRole('option', { name: '50', exact: true }).click()
    })
    expect(largerPage.request).toMatchObject({ page: 0, page_size: 50 })
    expect(largerPage.result.rows.map((row: { source_rows: Record<string, number> }) => row.source_rows[nodeId!]))
      .toEqual(expectedRows.map(row => row.sourceRow))
    await expect(paginator).toContainText('1–30 of 30 (60 unfiltered)')
    await expect(visibleRows).toHaveCount(30)

    const downloadPromise = page.waitForEvent('download')
    await nodeTable.getByTestId('download-merged-csv').click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toBe('data-table.csv')
    const downloadPath = await download.path()
    expect(downloadPath).not.toBeNull()
    const parsedCsv = parseCsv(await readFile(downloadPath!, 'utf8'))
    expect(parsedCsv).toEqual([
      ['', 'source_row', 'label', 'score'],
      ...expectedRows.map(row => [
        String(row.sourceRow),
        String(row.sourceRow),
        row.label,
        String(row.score),
      ]),
    ])

  })

  test('refuses an incomplete numeric range without losing result rows, then recovers', async ({ page }) => {
    const resultNode = await addToolNode(page, 'ResultTableFixture', { x: 280, y: 180 })
    const nodeId = await resultNode.getAttribute('data-id')
    expect(nodeId).toBeTruthy()
    await expect.poll(async () => (await currentDraft(page, workflowName)).validation.valid).toBe(true)
    const runResponse = page.waitForResponse(response =>
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST',
    )
    await page.getByTestId('run-workflow-button').click()
    expect((await runResponse).status()).toBe(202)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete', { timeout: 30000 })

    await resultNode.click()
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    const nodeTable = page.getByTestId('merged-data-table')
    const dataTable = nodeTable.locator('.p-datatable')
    const visibleRows = dataTable.locator('.p-datatable-tbody tr')
    await expect(visibleRows).toHaveCount(60)

    await dataTable.getByRole('button', { name: 'Filter score' }).click()
    await page.getByRole('combobox', { name: 'Filter operator' }).click()
    await page.getByRole('option', { name: 'Between' }).click()
    await page.getByRole('spinbutton', { name: 'Filter value', exact: true }).fill('20')
    await expect(page.getByRole('button', { name: 'Apply' })).toBeDisabled()
    await expect(visibleRows).toHaveCount(60)

    await page.getByRole('spinbutton', { name: 'Second filter value' }).fill('40')
    await page.getByRole('spinbutton', { name: 'Second filter value' }).press('Tab')
    await expect(page.getByRole('button', { name: 'Apply' })).toBeEnabled()
    const ranged = await projectionQueryAfter(page, async () => {
      await page.getByRole('button', { name: 'Apply' }).click()
    })
    expect(ranged.request.filters).toEqual([
      { column: 's0:score', operator: 'between', value: 20, second_value: 40 },
    ])
    const expectedRows = Array.from({ length: 60 }, (_, sourceRow) => sourceRow)
      .filter(sourceRow => {
        const score = (sourceRow * 17) % 61
        return score >= 20 && score <= 40
      })
    expect(ranged.result.rows.map((row: { source_rows: Record<string, number> }) => row.source_rows[nodeId!]))
      .toEqual(expectedRows)
    await expect(visibleRows).toHaveCount(expectedRows.length)

    const restored = await projectionQueryAfter(page, async () => {
      await nodeTable.getByTestId('node-data-active-filters').getByRole('button', { name: 'Clear filters' }).click()
    })
    expect(restored.request.filters).toEqual([])
    expect(restored.result.rows.map((row: { source_rows: Record<string, number> }) => row.source_rows[nodeId!]))
      .toEqual(Array.from({ length: 60 }, (_, sourceRow) => sourceRow))
    await expect(visibleRows).toHaveCount(60)
  })

  test('merges related selected results, stacks independent results, and restores explicit widths', async ({ page }) => {
    test.setTimeout(60_000)
    const seedNode = await addToolNode(page, 'SeedNumbers', { x: 120, y: 160 })
    const incrementNode = await addToolNode(page, 'IncrementNumbers', { x: 440, y: 160 })
    await incrementNode.click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const numberRow = page.getByTestId('panel-nodePanel').locator('.param-row')
      .filter({ hasText: 'Number column to increment' })
    await numberRow.locator('input.p-inputnumber-input').fill('10')
    await numberRow.locator('input.p-inputnumber-input').press('Tab')
    const independentNode = await addToolNode(page, 'ResultTableFixture', { x: 280, y: 60 })
    const seedId = await seedNode.getAttribute('data-id')
    const incrementId = await incrementNode.getAttribute('data-id')
    const independentId = await independentNode.getAttribute('data-id')
    expect(seedId).toBeTruthy()
    expect(incrementId).toBeTruthy()
    expect(independentId).toBeTruthy()

    await connectDataFrames(page, seedNode, incrementNode)
    await expect.poll(async () => {
      const draft = await currentDraft(page, workflowName)
      return {
        valid: draft.validation.valid,
        nodeIds: draft.graph.nodes.map(node => node.id),
        edges: draft.graph.edges.map(({ id: _id, ...edge }) => edge),
      }
    }).toEqual({
      valid: true,
      nodeIds: [seedId, incrementId, independentId],
      edges: [{
        type: 'dataframe',
        source_node: seedId,
        target_node: incrementId,
        target_position: 0,
        target_input: null,
      }],
    })

    const runResponse = page.waitForResponse(response =>
      response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST',
    )
    await page.getByTestId('run-workflow-button').click()
    expect((await runResponse).status()).toBe(202)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete', { timeout: 30000 })

    const seedResult = await page.request.post(`${API_BASE}/api/v1/nodes/${seedId}/data/query`, {
      data: { workflow_name: workflowName },
    })
    expect(seedResult.ok()).toBeTruthy()
    expect(await seedResult.json()).toMatchObject({
      columns: ['number', 'label'],
      rows: [
        { number: 1, label: 'one' },
        { number: 2, label: 'two' },
        { number: 3, label: 'three' },
      ],
      absolute_rows: [0, 1, 2],
      total_rows: 3,
    })
    const incrementResult = await page.request.post(`${API_BASE}/api/v1/nodes/${incrementId}/data/query`, {
      data: { workflow_name: workflowName },
    })
    expect(incrementResult.ok()).toBeTruthy()
    expect(await incrementResult.json()).toMatchObject({
      columns: ['number', 'label', 'number_plus_one'],
      rows: [
        { number: 1, label: 'one', number_plus_one: 2 },
        { number: 2, label: 'two', number_plus_one: 3 },
        { number: 3, label: 'three', number_plus_one: 4 },
      ],
      absolute_rows: [0, 1, 2],
      total_rows: 3,
    })

    await seedNode.click()
    const mergedResponse = page.waitForResponse(response =>
      response.url().endsWith('/api/v1/data-table/query')
      && response.request().method() === 'POST'
      && response.status() === 200
      && response.request().postDataJSON().sources.length === 2,
    )
    await incrementNode.click({ modifiers: ['Shift'] })
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    const merged = await mergedResponse
    const mergedRequest = merged.request().postDataJSON()
    const mergedResult = await merged.json()
    expect(mergedRequest).toMatchObject({
      workflow_id: workflowName,
      sources: [
        { node_id: seedId, role: 'anchor', label: 'Seed Numbers 1' },
        { node_id: incrementId, role: 'anchor', label: 'Increment Numbers 1' },
      ],
    })
    expect(mergedResult).toMatchObject({
      mode: 'merged',
      columns: [
        { label: 'Seed Numbers 1: number', source_node_id: seedId, source_column: 'number' },
        { label: 'Seed Numbers 1: label', source_node_id: seedId, source_column: 'label' },
        { label: 'Increment Numbers 1: number', source_node_id: incrementId, source_column: 'number' },
        { label: 'Increment Numbers 1: label', source_node_id: incrementId, source_column: 'label' },
        { label: 'number_plus_one', source_node_id: incrementId, source_column: 'number_plus_one' },
      ],
      rows: [
        { index: '0', source_rows: { [seedId!]: 0, [incrementId!]: 0 } },
        { index: '1', source_rows: { [seedId!]: 1, [incrementId!]: 1 } },
        { index: '2', source_rows: { [seedId!]: 2, [incrementId!]: 2 } },
      ],
      total_rows: 3,
    })

    const mergedTable = page.getByTestId('merged-data-table')
    await expect(mergedTable).toContainText('Seed Numbers 1 → Increment Numbers 1')
    const grid = mergedTable.locator('.p-datatable')
    const headers = await grid.locator('.p-datatable-thead th').allTextContents()
    const seedNumberColumn = headers.findIndex(header => header.includes('Seed Numbers 1: number'))
    const incrementNumberColumn = headers.findIndex(header => header.includes('Increment Numbers 1: number'))
    const resultColumn = headers.findIndex(header => header.includes('number_plus_one'))
    expect([seedNumberColumn, incrementNumberColumn, resultColumn].every(index => index >= 0)).toBe(true)
    const visibleRows = grid.locator('.p-datatable-tbody tr')
    await expect(visibleRows).toHaveCount(3)
    for (const [row, expected] of [[0, [1, 1, 2]], [1, [2, 2, 3]], [2, [3, 3, 4]]] as const) {
      const cells = visibleRows.nth(row).locator('td')
      await expect(cells.nth(seedNumberColumn)).toHaveText(String(expected[0]))
      await expect(cells.nth(incrementNumberColumn)).toHaveText(String(expected[1]))
      await expect(cells.nth(resultColumn)).toHaveText(String(expected[2]))
    }

    const seedSeparator = page.getByRole('separator', { name: 'Resize Seed Numbers 1: number' })
    const seedHeader = grid.locator('.p-datatable-thead th').nth(seedNumberColumn)
    await expect(seedSeparator).toBeVisible()
    const automaticWidth = (await seedHeader.boundingBox())!.width
    await seedSeparator.focus()
    for (let step = 0; step < 5; step += 1) await seedSeparator.press('ArrowRight')
    await expect.poll(async () => Math.round((await seedHeader.boundingBox())!.width))
      .toBe(Math.round(automaticWidth) + 50)
    const widthStorageKeys = await page.evaluate(() => Object.keys(localStorage)
      .filter(key => key.startsWith('bif-node-data-widths-v2:')))
    expect(widthStorageKeys).toHaveLength(1)

    await independentNode.click()
    await seedNode.click({ modifiers: ['Shift'] })
    const fallback = page.getByTestId('data-table-fallback')
    await expect(fallback).toHaveText(
      'The selected nodes are independent in this workflow, so their DataFrames are shown separately.',
    )
    const seedStackedTable = page.getByTestId(`node-data-table-${seedId}`)
    const independentStackedTable = page.getByTestId(`node-data-table-${independentId}`)
    async function expectIndependentStackedRows() {
      await expect(mergedTable).toHaveCount(0)
      await expect(seedStackedTable.locator('.p-datatable-thead th')).toHaveCount(2)
      await expect(independentStackedTable.locator('.p-datatable-thead th')).toHaveCount(3)
      await expect(seedStackedTable.locator('.p-datatable-tbody tr')).toHaveCount(3)
      await expect(independentStackedTable.locator('.p-datatable-tbody tr')).toHaveCount(60)
      expect(await seedStackedTable.locator('.p-datatable-tbody tr').evaluateAll(rows => rows.map(row =>
        [...row.querySelectorAll('td')].map(cell => cell.textContent?.trim()),
      ))).toEqual([['1', 'one'], ['2', 'two'], ['3', 'three']])
      expect(await independentStackedTable.locator('.p-datatable-tbody tr').evaluateAll(rows => rows.map(row =>
        [...row.querySelectorAll('td')].map(cell => cell.textContent?.trim()),
      ))).toEqual(Array.from({ length: 60 }, (_, sourceRow) => [
        String(sourceRow),
        `${sourceRow % 2 === 0 ? 'keep' : 'drop'}-${String(sourceRow).padStart(2, '0')}`,
        String((sourceRow * 17) % 61),
      ]))
    }
    await expectIndependentStackedRows()

    const restoredMergedResponse = page.waitForResponse(response =>
      response.url().endsWith('/api/v1/data-table/query')
      && response.request().method() === 'POST'
      && response.status() === 200
      && response.request().postDataJSON().sources.length === 2,
    )
    await incrementNode.click()
    await seedNode.click({ modifiers: ['Shift'] })
    await restoredMergedResponse
    await expect(mergedTable).toBeVisible()
    await expect.poll(async () => Math.round((await seedHeader.boundingBox())!.width))
      .toBe(Math.round(automaticWidth) + 50)
    await page.reload()
    await expect(page.getByTestId('workflow-title')).toBeVisible()
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    await page.locator(`.vue-flow__node[data-id="${independentId}"]`).click()
    await page.locator(`.vue-flow__node[data-id="${seedId}"]`).click({ modifiers: ['Shift'] })
    await expect(fallback).toHaveText(
      'The selected nodes are independent in this workflow, so their DataFrames are shown separately.',
    )
    await expectIndependentStackedRows()
    await page.locator(`.vue-flow__node[data-id="${incrementId}"]`).click()
    await page.locator(`.vue-flow__node[data-id="${seedId}"]`).click({ modifiers: ['Shift'] })
    await expect(mergedTable).toBeVisible()
    await expect.poll(async () => Math.round((await seedHeader.boundingBox())!.width))
      .toBe(Math.round(automaticWidth) + 50)
    await mergedTable.getByRole('button', { name: 'Reset column widths', exact: true }).click()
    await expect.poll(async () => Math.round((await seedHeader.boundingBox())!.width))
      .toBe(Math.round(automaticWidth))
    expect(await page.evaluate(key => localStorage.getItem(key), widthStorageKeys[0]!)).toBeNull()
  })

  test('keeps result filters, sorting, and manual widths on exact workflow and source identities', async ({ page }) => {
    test.setTimeout(120_000)
    const firstWorkflow = workflowName
    const seed = await addToolNode(page, 'SeedNumbers', { x: 120, y: 160 })
    const increment = await addToolNode(page, 'IncrementNumbers', { x: 440, y: 160 })
    await increment.click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
    const numberRow = page.getByTestId('panel-nodePanel').locator('.param-row')
      .filter({ hasText: 'Number column to increment' })
    await numberRow.locator('input.p-inputnumber-input').fill('10')
    await numberRow.locator('input.p-inputnumber-input').press('Tab')
    const seedId = (await seed.getAttribute('data-id'))!
    const incrementId = (await increment.getAttribute('data-id'))!
    await connectDataFrames(page, seed, increment)
    await expect.poll(async () => {
      const draft = await currentDraft(page, firstWorkflow)
      return { valid: draft.validation.valid, nodes: draft.graph.nodes.map(node => node.id), edges: draft.graph.edges.map(edge => [edge.source_node, edge.target_node]) }
    }).toEqual({ valid: true, nodes: [seedId, incrementId], edges: [[seedId, incrementId]] })
    const firstRun = page.waitForResponse(response => response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST')
    await page.getByTestId('run-workflow-button').click()
    expect((await firstRun).status()).toBe(202)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete', { timeout: 30000 })
    await seed.click()
    await increment.click({ modifiers: ['Shift'] })
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    const merged = page.getByTestId('merged-data-table')
    await expect(merged).toContainText('Seed Numbers 1 → Increment Numbers 1')
    const seedHeader = merged.locator('.p-datatable-thead th').filter({ hasText: 'Seed Numbers 1: number' })
    const seedAutomatic = Math.round((await seedHeader.boundingBox())!.width)
    const seedSeparator = merged.getByRole('separator', { name: 'Resize Seed Numbers 1: number' })
    await seedSeparator.focus()
    for (let step = 0; step < 5; step += 1) await seedSeparator.press('ArrowRight')
    await expect.poll(async () => Math.round((await seedHeader.boundingBox())!.width)).toBe(seedAutomatic + 50)
    const firstWidthKey = (await page.evaluate(() => Object.keys(localStorage)
      .filter(key => key.startsWith('bif-node-data-widths-v2:'))))[0]!
    expect(firstWidthKey).toContain(firstWorkflow)
    expect(firstWidthKey).toContain(seedId)
    expect(firstWidthKey).toContain(incrementId)

    const firstSorted = await projectionQueryAfter(page, async () => {
      await merged.getByRole('button', { name: 'Sort Increment Numbers 1: number' }).click()
    })
    expect(firstSorted.request).toMatchObject({ workflow_id: firstWorkflow, sort_by: 's1:number', filters: [] })
    expect(firstSorted.result.rows.map((row: { source_rows: Record<string, number>; values: Record<string, unknown> }) => [
      row.source_rows[seedId], row.source_rows[incrementId], row.values['s0:number'], row.values['s1:number'],
    ])).toEqual([[0, 0, 1, 1], [1, 1, 2, 2], [2, 2, 3, 3]])

    await openWorkflowMenuItem(page, 'Save')
    await expect(page.getByTestId('workflow-title')).not.toContainText('*')
    const secondDisplay = `Result Identity ${Date.now()} ${Math.floor(Math.random() * 10000)}`
    const secondWorkflow = deriveWorkflowId(secondDisplay)
    try {
      await openWorkflowMenuItem(page, 'New')
      await page.getByTestId('workflow-display-name-input').fill(secondDisplay)
      await page.getByTestId('workflow-dialog-submit').click()
      await expect(page.getByTestId('workflow-title')).toContainText(secondDisplay)
      await addToolNode(page, 'ResultTableFixture', { x: 250, y: 180 })
      await expect.poll(async () => (await currentDraft(page, secondWorkflow)).graph.nodes.length).toBe(1)
      const secondDraft = await currentDraft(page, secondWorkflow)
      const collidingGraph = {
        ...secondDraft.graph,
        nodes: secondDraft.graph.nodes.map(node => ({ ...node, id: seedId })),
      }
      const replacement = await page.request.put(`${API_BASE}/api/v1/workflow-drafts/${secondWorkflow}`, {
        data: { graph: collidingGraph, expected_revision: secondDraft.draft_revision, updated_by: 'frontend' },
      })
      expect(replacement.ok()).toBeTruthy()
      await page.reload()
      await expect(page.locator(`.vue-flow__node[data-id="${seedId}"]`)).toBeVisible()
      const secondRun = page.waitForResponse(response => response.url().endsWith('/api/v1/execution/run') && response.request().method() === 'POST')
      await page.getByTestId('run-workflow-button').click()
      expect((await secondRun).status()).toBe(202)
      await expect(page.getByTestId('execution-banner-headline')).toHaveText('Execution complete', { timeout: 30000 })
      await openWorkflowMenuItem(page, 'Save')
      await expect(page.getByTestId('workflow-title')).not.toContainText('*')
      await page.locator(`.vue-flow__node[data-id="${seedId}"]`).click()
      await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
      const secondTable = page.getByTestId('merged-data-table')
      await expect(secondTable.locator('.p-datatable-thead th')).toHaveCount(3)
      const secondGrid = secondTable.locator('.p-datatable')
      await expect(secondGrid.locator('.p-datatable-tbody tr')).toHaveCount(60)
      const secondAutomatic = Math.round((await secondGrid.locator('.p-datatable-thead th').first().boundingBox())!.width)
      expect(secondAutomatic).not.toBe(seedAutomatic + 50)
      const secondFiltered = await projectionQueryAfter(page, async () => {
        await secondGrid.getByRole('button', { name: 'Filter label' }).click()
        await page.getByRole('combobox', { name: 'Filter operator' }).click()
        await page.getByRole('option', { name: 'Starts with' }).click()
        await page.getByRole('textbox', { name: 'Filter value' }).fill('keep-')
        await page.getByRole('button', { name: 'Apply' }).click()
      })
      expect(secondFiltered.request).toMatchObject({ workflow_id: secondWorkflow, filters: [{ column: 's0:label', operator: 'starts_with', value: 'keep-' }] })
      await projectionQueryAfter(page, async () => { await secondGrid.getByRole('button', { name: 'Sort score' }).click() })
      const secondSorted = await projectionQueryAfter(page, async () => { await secondGrid.getByRole('button', { name: 'Sort score' }).click() })
      const expected = expectedResultTableRows()
      expect(secondSorted.result.rows.map((row: { source_rows: Record<string, number>; values: Record<string, unknown> }) => [
        row.source_rows[seedId], row.values['s0:source_row'], row.values['s0:label'], row.values['s0:score'],
      ])).toEqual(expected.map(row => [row.sourceRow, row.sourceRow, row.label, row.score]))
      const visibleSecondRows = secondGrid.locator('.p-datatable-tbody tr')
      await expect(visibleSecondRows).toHaveCount(expected.length)
      for (const [position, row] of expected.entries()) {
        await expect(visibleSecondRows.nth(position).locator('td')).toHaveText([
          String(row.sourceRow), row.label, String(row.score),
        ])
      }
      const scoreHeader = secondGrid.locator('.p-datatable-thead th').filter({ hasText: 'score' })
      const scoreAutomatic = Math.round((await scoreHeader.boundingBox())!.width)
      const scoreSeparator = secondTable.getByRole('separator', { name: 'Resize score' })
      await scoreSeparator.focus()
      for (let step = 0; step < 4; step += 1) await scoreSeparator.press('ArrowRight')
      await expect.poll(async () => Math.round((await scoreHeader.boundingBox())!.width)).toBe(scoreAutomatic + 40)
      const secondWidthKey = (await page.evaluate(() => Object.keys(localStorage)
        .filter(key => key.startsWith('bif-node-data-widths-v2:')))).find(key => key.includes(secondWorkflow))!
      expect(secondWidthKey).not.toBe(firstWidthKey)

      await openWorkflowMenuItem(page, 'Open')
      await page.getByTestId('workflow-open-search').fill(firstWorkflow)
      await page.getByTestId(`workflow-open-option-${firstWorkflow}`).click()
      await page.getByTestId('workflow-open-submit').click()
      await page.locator(`.vue-flow__node[data-id="${seedId}"]`).click()
      await page.locator(`.vue-flow__node[data-id="${incrementId}"]`).click({ modifiers: ['Shift'] })
      await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
      await expect.poll(async () => Math.round((await seedHeader.boundingBox())!.width)).toBe(seedAutomatic + 50)
      const firstRestored = await projectionQueryAfter(page, async () => {
        await merged.getByRole('button', { name: 'Sort Increment Numbers 1: number' }).click()
      })
      expect(firstRestored.request).toMatchObject({ workflow_id: firstWorkflow, filters: [] })
      expect(firstRestored.result.rows.map((row: { source_rows: Record<string, number> }) => [row.source_rows[seedId], row.source_rows[incrementId]])).toEqual([[0, 0], [1, 1], [2, 2]])
      await merged.getByRole('button', { name: 'Reset column widths', exact: true }).click()
      await expect.poll(async () => Math.round((await seedHeader.boundingBox())!.width)).toBe(seedAutomatic)
      expect(await page.evaluate(key => localStorage.getItem(key), firstWidthKey)).toBeNull()
      expect(await page.evaluate(key => localStorage.getItem(key), secondWidthKey)).not.toBeNull()

      await page.reload()
      await expect(page.getByTestId('workflow-title')).toBeVisible()
      await openWorkflowMenuItem(page, 'Open')
      await page.getByTestId('workflow-open-search').fill(secondWorkflow)
      await page.getByTestId(`workflow-open-option-${secondWorkflow}`).click()
      await page.getByTestId('workflow-open-submit').click()
      await expect(page.getByTestId('workflow-title')).toContainText(secondDisplay)
      await page.locator(`.vue-flow__node[data-id="${seedId}"]`).click()
      await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
      await expect.poll(async () => Math.round((await scoreHeader.boundingBox())!.width)).toBe(scoreAutomatic + 40)
      const secondRestored = await projectionQueryAfter(page, async () => {
        await secondTable.getByRole('button', { name: 'Sort score' }).click()
      })
      expect(secondRestored.request).toMatchObject({ workflow_id: secondWorkflow, sort_by: 's0:score', sort_order: 'asc', filters: [] })
      const ascendingSourceRows = Array.from({ length: 60 }, (_, index) => index)
        .sort((left, right) => (left * 17) % 61 - (right * 17) % 61)
      expect(secondRestored.result.rows.map((row: { source_rows: Record<string, number>; values: Record<string, unknown> }) => [
        row.source_rows[seedId], row.values['s0:source_row'], row.values['s0:label'], row.values['s0:score'],
      ])).toEqual(ascendingSourceRows.map(sourceRow => [
        sourceRow,
        sourceRow,
        `${sourceRow % 2 === 0 ? 'keep' : 'drop'}-${String(sourceRow).padStart(2, '0')}`,
        (sourceRow * 17) % 61,
      ]))
    } finally {
      await page.request.delete(`${API_BASE}/api/v1/workflows/${secondWorkflow}`).catch(() => undefined)
    }
  })

  test('repeated undo returns moved nodes to the loaded workflow baseline', async ({ page }) => {
    await addToolNode(page, 'Generate', { x: 220, y: 180 })
    await addToolNode(page, 'Generate', { x: 520, y: 260 })
    const saveResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes(`/api/v1/workflows/${workflowName}`) &&
        resp.request().method() === 'PUT' &&
        resp.status() === 200,
    )
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
    await saveResponse

    await page.reload()
    await expect(page.getByTestId('workflow-title')).toBeVisible()
    const nodes = page.locator('.vue-flow__node')
    await expect(nodes).toHaveCount(2)
    const first = nodes.nth(0)
    const second = nodes.nth(1)
    const firstInitial = await first.boundingBox()
    const secondInitial = await second.boundingBox()
    expect(firstInitial).not.toBeNull()
    expect(secondInitial).not.toBeNull()

    await moveNode(page, first, { x: 70, y: 45 })
    await moveNode(page, second, { x: -55, y: 65 })

    await page.locator('.canvas-view').press('Control+z')
    await expect(nodes).toHaveCount(2)
    await expectNodeNear(second, secondInitial!)

    await page.locator('.canvas-view').press('Control+z')
    await expect(nodes).toHaveCount(2)
    await expectNodeNear(first, firstInitial!)
    await expectNodeNear(second, secondInitial!)

    await page.locator('.canvas-view').press('Control+Shift+z')
    await page.locator('.canvas-view').press('Control+Shift+z')
    await expect(nodes).toHaveCount(2)
  })
})
