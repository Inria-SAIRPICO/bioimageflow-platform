import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

type PublishedInput = {
  name: string
  internal_node_id: string
  internal_field: string
  kind: 'input' | 'parameter'
  schema: Record<string, unknown>
  default?: unknown
}

type PublishedOutput = {
  name: string
  internal_node_id: string
  internal_output: string
  schema: Record<string, unknown>
}

type GraphState = {
  nodes: Array<Record<string, unknown>>
  edges: Array<Record<string, unknown>>
  published_inputs?: PublishedInput[]
  published_outputs?: PublishedOutput[]
}

function uniqueWorkflowName(prefix: string): string {
  const project = test.info().project.name.replace(/[^a-zA-Z0-9_-]/g, '_')
  return `${prefix}_${project}_${Date.now()}_${Math.floor(Math.random() * 10000)}`
}

async function seedTools(page: Page): Promise<void> {
  const response = await page.request.post(`${API_BASE}/api/v1/dev/seed`)
  expect(response.ok()).toBeTruthy()
}

async function deleteWorkflowIfExists(page: Page, name: string): Promise<void> {
  await page.request.delete(`${API_BASE}/api/v1/workflows/${name}`).catch(() => undefined)
}

async function createWorkflow(
  page: Page,
  name: string,
  displayName: string,
  graph: GraphState,
): Promise<void> {
  await deleteWorkflowIfExists(page, name)
  const created = await page.request.post(`${API_BASE}/api/v1/workflows`, {
    data: { name, display_name: displayName },
  })
  expect(created.status()).toBe(201)
  const saved = await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
    data: { graph },
  })
  expect(saved.ok()).toBeTruthy()
}

async function openWorkflowFromPanel(
  page: Page,
  name: string,
  displayName: string,
): Promise<void> {
  await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
  await page.getByTestId('workflow-search').fill(displayName)
  await expect(page.getByTestId(`workflow-row-${name}`)).toBeVisible({ timeout: 5000 })
  await page.getByTestId(`workflow-row-${name}`).dblclick()
  await expect(page.locator('.dv-tab').filter({ hasText: displayName })).toBeVisible({
    timeout: 5000,
  })
  await expect(page.getByTestId('workflow-title')).toContainText(displayName)
}

async function saveCurrentWorkflow(page: Page, name: string): Promise<void> {
  const saved = page.waitForResponse((response) =>
    response.url().includes(`/api/v1/workflows/${name}`)
    && response.request().method() === 'PUT'
    && response.status() === 200,
  )
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
  await saved
}

async function loadWorkflowGraph(page: Page, name: string): Promise<GraphState> {
  const response = await page.request.get(`${API_BASE}/api/v1/workflows/${name}`)
  expect(response.ok()).toBeTruthy()
  const body = await response.json()
  return body.graph as GraphState
}

function gaussianWorkflowGraph(
  publishedInputs: PublishedInput[] = [],
  publishedOutputs: PublishedOutput[] = [],
): GraphState {
  return {
    nodes: [
      {
        id: 'blur_1',
        name: 'Gaussian Blur',
        tool_name: 'GaussianBlur',
        position: [180, 160],
        parameters: { input_image: '/tmp/e2e-input.tif' },
      },
    ],
    edges: [],
    published_inputs: publishedInputs,
    published_outputs: publishedOutputs,
  }
}

function pathPublishedInput(name = 'input_folder'): PublishedInput {
  return {
    name,
    internal_node_id: 'blur_1',
    internal_field: 'input_image',
    kind: 'input',
    schema: {
      type: 'Path',
      required: true,
      connectable: 'by_default',
      image_spec: null,
    },
    default: null,
  }
}

function imagePublishedOutput(name = 'label_image'): PublishedOutput {
  return {
    name,
    internal_node_id: 'blur_1',
    internal_output: 'output_image',
    schema: {
      type: 'ImageFile',
      default: null,
      image_spec: null,
    },
  }
}

test.describe('workflow publishing and sub-workflow E2E', () => {
  test.describe.configure({ mode: 'serial' })

  test.beforeEach(async ({ page }) => {
    await seedTools(page)
  })

  test('publishes a normal workflow interface from the Nodes panel and saves it', async ({ page }) => {
    const workflowName = uniqueWorkflowName('publish_controls')
    const displayName = `Publish Controls ${workflowName}`
    await createWorkflow(page, workflowName, displayName, gaussianWorkflowGraph())

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await openWorkflowFromPanel(page, workflowName, displayName)

    await page.locator('.vue-flow__node[data-id="blur_1"]').click()
    await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()

    const inputRow = page.locator('.param-row').filter({
      has: page.getByText('input_image', { exact: true }),
    })
    await expect(inputRow.getByTestId('publish-input-toggle')).toBeVisible()
    await inputRow.getByTestId('publish-input-toggle').click()
    await expect(page.getByTestId('published-input-name-input_image')).toBeVisible()
    await page.getByTestId('published-input-name-input_image').fill('input_image')

    await page.getByTestId('publish-output-toggle-output_image').click()
    await expect(page.getByTestId('published-output-name-output_image')).toBeVisible()
    await page.getByTestId('published-output-name-output_image').fill('output_image')

    await saveCurrentWorkflow(page, workflowName)
    const graph = await loadWorkflowGraph(page, workflowName)
    expect(graph.published_inputs).toEqual([
      expect.objectContaining({
        name: 'input_image',
        internal_node_id: 'blur_1',
        internal_field: 'input_image',
        kind: 'input',
      }),
    ])
    expect(graph.published_outputs).toEqual([
      expect.objectContaining({
        name: 'output_image',
        internal_node_id: 'blur_1',
        internal_output: 'output_image',
      }),
    ])

    await deleteWorkflowIfExists(page, workflowName)
  })

  test('opens workflows as named canvas tabs and switches the active workflow title', async ({ page }) => {
    const firstName = uniqueWorkflowName('tab_a')
    const secondName = uniqueWorkflowName('tab_b')
    const firstDisplay = `Tab A ${firstName}`
    const secondDisplay = `Tab B ${secondName}`
    await createWorkflow(page, firstName, firstDisplay, { nodes: [], edges: [] })
    await createWorkflow(page, secondName, secondDisplay, { nodes: [], edges: [] })

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await openWorkflowFromPanel(page, firstName, firstDisplay)
    await openWorkflowFromPanel(page, secondName, secondDisplay)

    const firstTab = page.locator('.dv-tab').filter({ hasText: firstDisplay })
    const secondTab = page.locator('.dv-tab').filter({ hasText: secondDisplay })
    await expect(firstTab).toBeVisible()
    await expect(secondTab).toBeVisible()
    await expect(page.getByTestId('workflow-title')).toContainText(secondDisplay)

    await firstTab.click()
    await expect(page.getByTestId('workflow-title')).toContainText(firstDisplay)
    await secondTab.click()
    await expect(page.getByTestId('workflow-title')).toContainText(secondDisplay)

    await deleteWorkflowIfExists(page, firstName)
    await deleteWorkflowIfExists(page, secondName)
  })

  test('drags a workflow as a sub-workflow and validates Path/ImageFile pins in a parent graph', async ({ page }) => {
    const childName = uniqueWorkflowName('child_path_image')
    const parentName = uniqueWorkflowName('parent_path_image')
    const childDisplay = `Child Path Image ${childName}`
    const parentDisplay = `Parent Path Image ${parentName}`
    const childGraph = gaussianWorkflowGraph(
      [pathPublishedInput('input_folder')],
      [imagePublishedOutput('label_image')],
    )
    await createWorkflow(page, childName, childDisplay, childGraph)
    await createWorkflow(page, parentName, parentDisplay, { nodes: [], edges: [] })

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await openWorkflowFromPanel(page, parentName, parentDisplay)

    await page.locator('.dv-tab').filter({ hasText: 'Workflows' }).click()
    const workflowSearch = page.getByTestId('workflow-search')
    await workflowSearch.fill(childDisplay)
    const workflowRow = page.getByTestId(`workflow-row-${childName}`)
    await expect(workflowRow).toBeVisible()
    await workflowSearch.clear()
    await expect(workflowRow).toBeVisible()
    const draggableRow = workflowRow.locator(
      'xpath=ancestor::*[@draggable="true"][1]',
    )
    await expect(draggableRow).toBeVisible()

    await draggableRow.dragTo(page.locator('.vue-flow'), {
      targetPosition: { x: 360, y: 240 },
    })
    const subWorkflowNode = page.locator('.vue-flow__node').filter({ hasText: childDisplay })
    await expect(subWorkflowNode).toBeVisible({ timeout: 5000 })
    await expect(subWorkflowNode.getByText('input_folder', { exact: true })).toBeVisible()
    await expect(subWorkflowNode.getByText('label_image', { exact: true })).toBeVisible()

    const parentGraph: GraphState = {
      nodes: [
        {
          id: 'source_image',
          name: 'Source Image',
          tool_name: 'GaussianBlur',
          position: [100, 120],
          parameters: { input_image: '/tmp/source.tif' },
        },
        {
          id: 'sub_workflow_1',
          name: childDisplay,
          tool_name: '__sub_workflow__',
          position: [390, 120],
          parameters: {},
          sub_workflow: childGraph,
          published_inputs: childGraph.published_inputs,
          published_outputs: childGraph.published_outputs,
        },
        {
          id: 'target_image',
          name: 'Target Image',
          tool_name: 'GaussianBlur',
          position: [690, 120],
          parameters: {},
        },
      ],
      edges: [
        {
          type: 'column_ref',
          id: 'e-source_image-output_image-sub_workflow_1-input_folder',
          source_node: 'source_image',
          target_node: 'sub_workflow_1',
          source_output: 'output_image',
          target_input: 'input_folder',
        },
        {
          type: 'column_ref',
          id: 'e-sub_workflow_1-label_image-target_image-input_image',
          source_node: 'sub_workflow_1',
          target_node: 'target_image',
          source_output: 'label_image',
          target_input: 'input_image',
        },
      ],
    }

    const validation = await page.request.put(`${API_BASE}/api/v1/graph`, {
      data: { graph: parentGraph, workflow_name: parentName },
    })
    expect(validation.ok()).toBeTruthy()
    const validationBody = await validation.json()
    expect(validationBody.valid, JSON.stringify(validationBody.errors ?? [])).toBe(true)

    await page.request.put(`${API_BASE}/api/v1/workflows/${parentName}`, {
      data: { graph: parentGraph },
    })
    await page.reload()
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await openWorkflowFromPanel(page, parentName, parentDisplay)
    await expect(page.locator('.vue-flow__node[data-id="sub_workflow_1"]')).toBeVisible()
    await expect(page.locator('.vue-flow__edge')).toHaveCount(2, { timeout: 5000 })

    await deleteWorkflowIfExists(page, childName)
    await deleteWorkflowIfExists(page, parentName)
  })
})
