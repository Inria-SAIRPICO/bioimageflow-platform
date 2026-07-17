import { test, expect } from '@playwright/test'
import type { Page, Response } from '@playwright/test'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`

type GraphNode = {
  id: string
  name: string
  tool_name: string
  position: [number, number]
  parameters: Record<string, unknown>
}

type GraphState = {
  nodes: GraphNode[]
  edges: Array<Record<string, unknown>>
}

type WorkflowDraft = {
  draft_revision: number
  dirty_against_saved: boolean
  graph: GraphState
  validation: {
    valid: boolean
    errors: Array<Record<string, unknown>>
    node_statuses: Record<string, Record<string, unknown>>
  }
}

type ParameterFeedbackSample = {
  className: string
  filter: string
  noticeVisible: boolean
  statusClass: string | null
  text: string
}

type ParameterFeedbackProbe = {
  capture(): void
  intervalId: number
  observer: MutationObserver
  samples: ParameterFeedbackSample[]
}

function uniqueName(prefix: string): string {
  const project = test.info().project.name.replace(/[^a-zA-Z0-9_-]/g, '_')
  return `${prefix}_${project}_${Date.now()}_${Math.floor(Math.random() * 10000)}`
}

function gaussianGraph(nodeId: string, sigma: number): GraphState {
  return {
    nodes: [
      {
        id: nodeId,
        name: 'Gaussian Blur',
        tool_name: 'GaussianBlur',
        position: [240, 180],
        parameters: {
          input_image: '/tmp/e2e-input.tif',
          sigma,
        },
      },
    ],
    edges: [],
  }
}

function graphParameter(
  graph: GraphState,
  nodeId: string,
  parameter: string,
): unknown {
  return graph.nodes.find((node) => node.id === nodeId)?.parameters[parameter]
}

function responseCarriesParameter(
  response: Response,
  workflowName: string,
  nodeId: string,
  value: number,
): boolean {
  if (
    !response.url().includes(`/api/v1/workflow-drafts/${workflowName}`)
    || response.request().method() !== 'PUT'
    || response.status() !== 200
  ) return false
  const body = response.request().postDataJSON() as { graph?: GraphState } | null
  return body?.graph !== undefined
    && graphParameter(body.graph, nodeId, 'sigma') === value
}

async function seedTools(page: Page): Promise<void> {
  const response = await page.request.post(`${API_BASE}/api/v1/dev/seed`)
  expect(response.ok()).toBeTruthy()
}

async function createWorkflow(
  page: Page,
  name: string,
  displayName: string,
  graph: GraphState,
): Promise<void> {
  await page.request
    .delete(`${API_BASE}/api/v1/workflows/${name}`)
    .catch(() => undefined)
  const created = await page.request.post(`${API_BASE}/api/v1/workflows`, {
    data: { name, display_name: displayName },
  })
  expect(created.status()).toBe(201)
  const saved = await page.request.put(`${API_BASE}/api/v1/workflows/${name}`, {
    data: { graph },
  })
  expect(saved.ok()).toBeTruthy()
}

async function openWorkflow(
  page: Page,
  name: string,
  displayName: string,
): Promise<void> {
  await page.locator('.dv-tab').filter({ hasText: /^Workflows$/ }).first().click()
  await page.getByTestId('workflow-search').fill(displayName)
  const row = page.getByTestId(`workflow-row-${name}`)
  await expect(row).toBeVisible({ timeout: 5000 })
  await row.dblclick()
  await expect(page.getByTestId('workflow-title')).toContainText(displayName)
}

async function activateWorkflow(page: Page, displayName: string): Promise<void> {
  const tab = page.locator('.dv-tab').filter({ hasText: displayName })
  await expect(tab).toBeVisible()
  await tab.click()
  await expect(page.getByTestId('workflow-title')).toContainText(displayName)
}

async function selectSigmaField(page: Page, nodeId: string) {
  const node = page.locator(`.vue-flow__node[data-id="${nodeId}"]`)
  await expect(node).toBeVisible({ timeout: 5000 })
  await node.click()
  await page.locator('.dv-tab').filter({ hasText: 'Nodes' }).click()
  const input = page.getByTestId('slider-row-sigma').locator('input')
  await expect(input).toBeVisible()
  return input
}

async function editSigma(input: ReturnType<Page['locator']>, value: number) {
  await input.fill(value.toFixed(1))
  await input.press('Tab')
}

async function fetchDraft(page: Page, workflowName: string): Promise<WorkflowDraft> {
  const response = await page.request.get(
    `${API_BASE}/api/v1/workflow-drafts/${workflowName}`,
  )
  expect(response.ok()).toBeTruthy()
  return await response.json() as WorkflowDraft
}

async function waitForDraftParameter(
  page: Page,
  workflowName: string,
  nodeId: string,
  value: number,
  dirty?: boolean,
): Promise<WorkflowDraft> {
  await expect.poll(async () => {
    const draft = await fetchDraft(page, workflowName)
    return {
      value: graphParameter(draft.graph, nodeId, 'sigma'),
      ...(dirty === undefined ? {} : { dirty: draft.dirty_against_saved }),
    }
  }, { timeout: 10000 }).toEqual({
    value,
    ...(dirty === undefined ? {} : { dirty }),
  })
  return await fetchDraft(page, workflowName)
}

async function loadSavedGraph(page: Page, workflowName: string): Promise<GraphState> {
  const response = await page.request.get(
    `${API_BASE}/api/v1/workflows/${workflowName}`,
  )
  expect(response.ok()).toBeTruthy()
  return (await response.json()).graph as GraphState
}

async function saveFromMenu(page: Page): Promise<void> {
  await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Save', exact: true }).click()
}

test.describe('critical operation race contracts', () => {
  test.beforeEach(async ({ page }) => {
    await seedTools(page)
  })

  test('Save keeps its initiating snapshot and canvas while a newer edit remains dirty', async ({ page }) => {
    const firstName = uniqueName('save_race_a')
    const secondName = uniqueName('save_race_b')
    const firstDisplay = `Save Race A ${firstName}`
    const secondDisplay = `Save Race B ${secondName}`
    const firstNode = 'blur_a'
    const secondNode = 'blur_b'
    await createWorkflow(page, firstName, firstDisplay, gaussianGraph(firstNode, 1))
    await createWorkflow(page, secondName, secondDisplay, gaussianGraph(secondNode, 9))

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await openWorkflow(page, firstName, firstDisplay)
    await openWorkflow(page, secondName, secondDisplay)
    await activateWorkflow(page, firstDisplay)

    const sigmaInput = await selectSigmaField(page, firstNode)
    const firstDraftAccepted = page.waitForResponse((response) => (
      responseCarriesParameter(response, firstName, firstNode, 2)
    ))
    await editSigma(sigmaInput, 2)
    await firstDraftAccepted
    await waitForDraftParameter(page, firstName, firstNode, 2, true)

    let releaseSave!: () => void
    const saveGate = new Promise<void>((resolve) => {
      releaseSave = resolve
    })
    let resolveSaveStarted!: (graph: GraphState) => void
    const saveStarted = new Promise<GraphState>((resolve) => {
      resolveSaveStarted = resolve
    })
    let intercepted = false
    await page.route(`**/api/v1/workflows/${firstName}`, async (route) => {
      if (route.request().method() !== 'PUT' || intercepted) {
        await route.continue()
        return
      }
      intercepted = true
      const body = route.request().postDataJSON() as { graph: GraphState }
      resolveSaveStarted(body.graph)
      await saveGate
      await route.continue()
    })
    const saveResponse = page.waitForResponse((response) => (
      response.url().includes(`/api/v1/workflows/${firstName}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))

    await saveFromMenu(page)
    const capturedSaveGraph = await saveStarted
    expect(graphParameter(capturedSaveGraph, firstNode, 'sigma')).toBe(2)

    const newerDraftAccepted = page.waitForResponse((response) => (
      responseCarriesParameter(response, firstName, firstNode, 3)
    ))
    await editSigma(sigmaInput, 3)
    await newerDraftAccepted
    await waitForDraftParameter(page, firstName, firstNode, 3, true)

    await activateWorkflow(page, secondDisplay)
    await expect(page.locator(`.vue-flow__node[data-id="${secondNode}"]`)).toBeVisible()
    releaseSave()
    await saveResponse

    await expect.poll(async () => (
      graphParameter(await loadSavedGraph(page, firstName), firstNode, 'sigma')
    )).toBe(2)
    await waitForDraftParameter(page, firstName, firstNode, 3, true)
    expect(
      graphParameter(await loadSavedGraph(page, secondName), secondNode, 'sigma'),
    ).toBe(9)
    await expect(page.getByTestId('workflow-title')).toContainText(secondDisplay)
  })

  test('Discard restores the saved graph before closing and reopening a root canvas', async ({ page }) => {
    const workflowName = uniqueName('discard_close')
    const displayName = `Discard Close ${workflowName}`
    const nodeId = 'blur_discard'
    await createWorkflow(page, workflowName, displayName, gaussianGraph(nodeId, 1))

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await openWorkflow(page, workflowName, displayName)
    const sigmaInput = await selectSigmaField(page, nodeId)
    const draftAccepted = page.waitForResponse((response) => (
      responseCarriesParameter(response, workflowName, nodeId, 2)
    ))
    await editSigma(sigmaInput, 2)
    await draftAccepted
    await waitForDraftParameter(page, workflowName, nodeId, 2, true)

    const workflowTab = page.getByTestId('canvas-tab').filter({ hasText: displayName })
    await workflowTab.getByTestId('canvas-tab-close').click()
    await expect(page.getByTestId('root-workflow-close-dialog')).toBeVisible()
    await page.getByTestId('root-workflow-close-discard').click()
    await expect(workflowTab).not.toBeVisible()

    const discardedDraft = await fetchDraft(page, workflowName)
    expect(discardedDraft.dirty_against_saved).toBe(false)
    expect(graphParameter(discardedDraft.graph, nodeId, 'sigma')).toBe(1)

    await openWorkflow(page, workflowName, displayName)
    const reopenedSigma = await selectSigmaField(page, nodeId)
    await expect.poll(async () => Number(await reopenedSigma.inputValue())).toBe(1)
  })

  test('Run asks again when the accepted graph changes during confirmation', async ({ page }) => {
    const workflowName = uniqueName('run_confirmation')
    const displayName = `Run Confirmation ${workflowName}`
    const nodeId = 'blur_confirmation'
    await createWorkflow(page, workflowName, displayName, gaussianGraph(nodeId, 1))

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await openWorkflow(page, workflowName, displayName)
    const sigmaInput = await selectSigmaField(page, nodeId)

    await page.route(`**/api/v1/workflow-drafts/${workflowName}`, async (route) => {
      if (route.request().method() !== 'PUT') {
        await route.continue()
        return
      }
      const response = await route.fetch()
      const body = await response.json() as WorkflowDraft
      body.validation.node_statuses = {
        ...body.validation.node_statuses,
        [nodeId]: {
          node_id: nodeId,
          status: 'out_of_date',
          cached: false,
        },
      }
      await route.fulfill({ response, json: body })
    })

    const firstDraftAccepted = page.waitForResponse((response) => (
      responseCarriesParameter(response, workflowName, nodeId, 2)
    ))
    await editSigma(sigmaInput, 2)
    await firstDraftAccepted
    await waitForDraftParameter(page, workflowName, nodeId, 2, true)

    let executionPayload: {
      graph: GraphState
      workflow_name: string
      draft_revision: number
    } | null = null
    await page.route('**/api/v1/execution/run', async (route) => {
      executionPayload = route.request().postDataJSON() as typeof executionPayload
      await route.fulfill({
        status: 202,
        json: {
          status: 'started',
          execution_id: `confirmation-e2e-${Date.now()}`,
          workflow_id: executionPayload!.workflow_name,
          draft_revision: executionPayload!.draft_revision,
        },
      })
    })

    await page.getByTestId('run-workflow-button').click()
    const confirmation = page.getByTestId('out-of-date-confirm')
    await expect(confirmation).toBeVisible()

    const newerDraftAccepted = page.waitForResponse((response) => (
      responseCarriesParameter(response, workflowName, nodeId, 3)
    ))
    const changed = await page.evaluate(
      async ({ targetNode }) => {
        const { useCanvasCommands } = await import('/src/composables/useCanvasCommands.ts')
        return useCanvasCommands().updateParameter(targetNode, 'sigma', 3)
      },
      { targetNode: nodeId },
    )
    expect(changed).toBe(true)
    await newerDraftAccepted
    const latestDraft = await waitForDraftParameter(
      page,
      workflowName,
      nodeId,
      3,
      true,
    )

    await page.getByTestId('out-of-date-continue').click()
    await expect(confirmation).toBeVisible()
    expect(executionPayload).toBeNull()

    const runResponse = page.waitForResponse((response) => (
      response.url().includes('/api/v1/execution/run')
      && response.request().method() === 'POST'
      && response.status() === 202
    ))
    await page.getByTestId('out-of-date-continue').click()
    await runResponse
    expect(executionPayload).not.toBeNull()
    expect(executionPayload!.workflow_name).toBe(workflowName)
    expect(executionPayload!.draft_revision).toBe(latestDraft.draft_revision)
    expect(graphParameter(executionPayload!.graph, nodeId, 'sigma')).toBe(3)
  })

  test('delayed parameter persistence keeps node presentation stable and success quiet', async ({ page }) => {
    const workflowName = uniqueName('parameter_feedback')
    const displayName = `Parameter Feedback ${workflowName}`
    const nodeId = 'blur_parameter_feedback'
    await createWorkflow(page, workflowName, displayName, gaussianGraph(nodeId, 1))

    let releaseDraftPut!: () => void
    const draftPutGate = new Promise<void>((resolve) => {
      releaseDraftPut = resolve
    })
    let resolveDraftPutHeld!: () => void
    const draftPutHeld = new Promise<void>((resolve) => {
      resolveDraftPutHeld = resolve
    })
    let heldEditedDraft = false
    await page.route(`**/api/v1/workflow-drafts/${workflowName}`, async (route) => {
      if (route.request().method() === 'GET') {
        const response = await route.fetch()
        const body = await response.json() as WorkflowDraft
        body.validation.node_statuses = {
          ...body.validation.node_statuses,
          [nodeId]: {
            node_id: nodeId,
            status: 'executed',
            cached: false,
          },
        }
        await route.fulfill({ response, json: body })
        return
      }
      if (route.request().method() !== 'PUT' || heldEditedDraft) {
        await route.continue()
        return
      }
      const request = route.request().postDataJSON() as { graph?: GraphState } | null
      if (
        request?.graph === undefined
        || graphParameter(request.graph, nodeId, 'sigma') !== 2
      ) {
        await route.continue()
        return
      }

      heldEditedDraft = true
      const response = await route.fetch()
      const body = await response.json() as WorkflowDraft
      body.validation.node_statuses = {
        ...body.validation.node_statuses,
        [nodeId]: {
          node_id: nodeId,
          status: 'out_of_date',
          cached: false,
        },
      }
      resolveDraftPutHeld()
      await draftPutGate
      await route.fulfill({ response, json: body })
    })

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await openWorkflow(page, workflowName, displayName)
    const sigmaInput = await selectSigmaField(page, nodeId)
    const toolNode = page.locator(
      `.vue-flow__node[data-id="${nodeId}"] .tool-node`,
    )
    await expect(toolNode).toHaveClass(/status-executed/)

    await page.evaluate((targetNodeId) => {
      const target = document.querySelector(
        `.vue-flow__node[data-id="${targetNodeId}"] .tool-node`,
      )
      if (!(target instanceof HTMLElement)) throw new Error('Tool node not found')
      const canvas = target.closest('.canvas-view')
      if (!(canvas instanceof HTMLElement)) throw new Error('Canvas not found')
      const samples: ParameterFeedbackSample[] = []
      let previous = ''
      const capture = () => {
        const sample: ParameterFeedbackSample = {
          className: target.className,
          filter: getComputedStyle(target).filter,
          noticeVisible: Boolean(canvas.querySelector([
            '[data-testid="canvas-persistence-issue"]',
            '.workflow-draft-conflict',
            '.workflow-draft-resolution',
          ].join(', '))) || Boolean(document.querySelector('.p-toast-message-success')),
          statusClass: [...target.classList]
            .find(className => className.startsWith('status-')) ?? null,
          text: target.textContent ?? '',
        }
        const signature = JSON.stringify(sample)
        if (signature === previous) return
        previous = signature
        samples.push(sample)
      }
      const observer = new MutationObserver(capture)
      observer.observe(canvas, {
        attributes: true,
        attributeFilter: ['class', 'style'],
        childList: true,
        characterData: true,
        subtree: true,
      })
      const intervalId = window.setInterval(capture, 16)
      const probeWindow = window as typeof window & {
        __parameterFeedbackProbe?: ParameterFeedbackProbe
      }
      probeWindow.__parameterFeedbackProbe = {
        capture,
        intervalId,
        observer,
        samples,
      }
      capture()
    }, nodeId)

    const acceptedResponse = page.waitForResponse((response) => (
      responseCarriesParameter(response, workflowName, nodeId, 2)
    ))
    try {
      await editSigma(sigmaInput, 2)
      await draftPutHeld

      const saving = page.getByTestId('canvas-persistence-saving')
      await expect(saving).toBeVisible({ timeout: 3000 })
      await expect(toolNode).toHaveClass(/status-executed/)
      await expect(toolNode).not.toHaveClass(/provisional/)
      await expect(toolNode).not.toContainText(/provisional/i)
      await expect(toolNode).toHaveCSS('filter', 'none')
      await expect(page.getByTestId('canvas-persistence-issue')).toHaveCount(0)
      await expect(page.locator('.workflow-draft-conflict')).toHaveCount(0)
      await expect(page.locator('.workflow-draft-resolution')).toHaveCount(0)

      const pendingSamples = await page.evaluate(() => {
        const probeWindow = window as typeof window & {
          __parameterFeedbackProbe?: ParameterFeedbackProbe
        }
        return probeWindow.__parameterFeedbackProbe?.samples ?? []
      })
      expect([...new Set(pendingSamples.map(sample => sample.statusClass))]).toEqual([
        'status-executed',
      ])

      releaseDraftPut()
      await acceptedResponse
      await expect(toolNode).toHaveClass(/status-out-of-date/)
      await expect(saving).toHaveCount(0)
      await expect(page.getByTestId('canvas-persistence-issue')).toHaveCount(0)
      await expect(page.locator('.workflow-draft-conflict')).toHaveCount(0)
      await expect(page.locator('.workflow-draft-resolution')).toHaveCount(0)
      await expect(page.locator('.p-toast-message-success')).toHaveCount(0)
    } finally {
      releaseDraftPut()
    }

    const samples = await page.evaluate(() => {
      const probeWindow = window as typeof window & {
        __parameterFeedbackProbe?: ParameterFeedbackProbe
      }
      const probe = probeWindow.__parameterFeedbackProbe
      if (!probe) return []
      probe.capture()
      window.clearInterval(probe.intervalId)
      probe.observer.disconnect()
      delete probeWindow.__parameterFeedbackProbe
      return probe.samples
    })
    expect(samples.length).toBeGreaterThan(1)
    expect(samples.every(sample => (
      !sample.className.split(/\s+/).includes('provisional')
      && !sample.text.toLowerCase().includes('provisional')
      && !sample.filter.includes('saturate')
      && !sample.noticeVisible
    ))).toBe(true)
    const statusTransitions = samples
      .map(sample => sample.statusClass)
      .filter((status): status is string => status !== null)
      .filter((status, index, values) => index === 0 || status !== values[index - 1])
    expect(statusTransitions).toEqual([
      'status-executed',
      'status-out-of-date',
    ])
  })

  test('immediate Node Panel parameter edit is the exact accepted Run input', async ({ page }) => {
    const workflowName = uniqueName('parameter_run')
    const displayName = `Parameter Run ${workflowName}`
    const nodeId = 'blur_parameter_run'
    await createWorkflow(page, workflowName, displayName, gaussianGraph(nodeId, 1))

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await openWorkflow(page, workflowName, displayName)
    const sigmaInput = await selectSigmaField(page, nodeId)

    let executionPayload: {
      graph: GraphState
      workflow_name: string
      draft_revision: number
    } | null = null
    await page.route('**/api/v1/execution/run', async (route) => {
      executionPayload = route.request().postDataJSON() as typeof executionPayload
      await route.fulfill({
        status: 202,
        json: {
          status: 'started',
          execution_id: `parameter-e2e-${Date.now()}`,
          workflow_id: executionPayload!.workflow_name,
          draft_revision: executionPayload!.draft_revision,
        },
      })
    })
    const runResponse = page.waitForResponse((response) => (
      response.url().includes('/api/v1/execution/run')
      && response.request().method() === 'POST'
      && response.status() === 202
    ))

    await sigmaInput.fill('4.5')
    await page.getByTestId('run-workflow-button').click()
    await runResponse

    expect(executionPayload).not.toBeNull()
    expect(executionPayload!.workflow_name).toBe(workflowName)
    expect(graphParameter(executionPayload!.graph, nodeId, 'sigma')).toBe(4.5)
    const acceptedDraft = await waitForDraftParameter(
      page,
      workflowName,
      nodeId,
      4.5,
      true,
    )
    expect(executionPayload!.draft_revision).toBe(acceptedDraft.draft_revision)
  })
})
