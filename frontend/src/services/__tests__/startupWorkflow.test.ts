import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { GraphState, WorkflowInfo } from '@/api/types'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import type { RootWorkflowPresentation } from '../rootWorkflowPresentation'
import { makeGraph } from '@/test-utils/graphFixtures'

const workflowStoreMock = vi.hoisted(() => ({
  fetchWorkflowTree: vi.fn(),
  fetchWorkflows: vi.fn(),
  flattenedWorkflows: [] as WorkflowInfo[],
  workflows: [] as WorkflowInfo[],
}))

const autoSaveMock = vi.hoisted(() => ({
  loadMostRecentAutoSave: vi.fn(),
  getLastOpenedWorkflow: vi.fn(),
  clearAutoSave: vi.fn(),
  setLastOpenedWorkflow: vi.fn(),
}))

const presentationMocks = vi.hoisted(() => ({
  loadRootWorkflowPresentation: vi.fn(),
}))

vi.mock('@/stores/workflow', () => ({
  useWorkflowStore: () => workflowStoreMock,
}))

vi.mock('@/composables/useAutoSave', () => ({
  useAutoSave: () => autoSaveMock,
}))

vi.mock('../rootWorkflowPresentation', () => ({
  workflowInfoId: (workflow: WorkflowInfo & { id?: string | null }) => (
    workflow.id || workflow.name
  ),
  loadRootWorkflowPresentation: presentationMocks.loadRootWorkflowPresentation,
}))

import { resolveStartupWorkflow } from '../startupWorkflow'

function graph(nodeId: string): GraphState {
  return makeGraph({
    nodes: [{
      type: 'tool',
      id: nodeId,
      name: nodeId,
      tool_name: 'gaussian_blur',
      position: [0, 0],
      parameters: {},
      resources: {},
      output_templates: {},
      enabled: true,
      collapsed: false,
    }],
    edges: [],
  })
}

function workflowInfo(name: string, lastModified = '2026-05-21T10:00:00Z'): WorkflowInfo {
  const parts = name.split('/')
  return {
    id: name,
    name: parts[parts.length - 1]!,
    folder: parts.slice(0, -1).join('/'),
    display_name: `Display ${name}`,
    path: `/workspace/workflows/${name}/workflow.json`,
    last_modified: lastModified,
      identity_generation: 0,
  }
}

function presentation(
  name: string,
  overrides: Partial<RootWorkflowPresentation> = {},
): RootWorkflowPresentation {
  return {
    graph: graph(name),
    workflowName: name,
    workflowDisplayName: `Display ${name}`,
    missingTools: [],
    dirty: false,
    identityGeneration: 0,
    ...overrides,
    serverIdentityGeneration: overrides.serverIdentityGeneration ?? null,
  }
}

describe('resolveStartupWorkflow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    presentationMocks.loadRootWorkflowPresentation.mockReset()
    workflowStoreMock.flattenedWorkflows = []
    workflowStoreMock.workflows = []
    workflowStoreMock.fetchWorkflowTree.mockResolvedValue(undefined)
    workflowStoreMock.fetchWorkflows.mockResolvedValue(undefined)
    autoSaveMock.loadMostRecentAutoSave.mockResolvedValue(null)
    autoSaveMock.getLastOpenedWorkflow.mockResolvedValue(null)
    autoSaveMock.clearAutoSave.mockResolvedValue(undefined)
    autoSaveMock.setLastOpenedWorkflow.mockResolvedValue(undefined)
  })

  it('falls back to the flat workflow list when the tree request fails', async () => {
    const info = workflowInfo('analysis')
    const loaded = presentation('analysis')
    workflowStoreMock.flattenedWorkflows = [info]
    workflowStoreMock.workflows = [info]
    workflowStoreMock.fetchWorkflowTree.mockRejectedValueOnce(new Error('tree unavailable'))
    presentationMocks.loadRootWorkflowPresentation.mockResolvedValueOnce(loaded)

    await expect(resolveStartupWorkflow()).resolves.toEqual(loaded)

    expect(workflowStoreMock.fetchWorkflows).toHaveBeenCalledOnce()
    expect(presentationMocks.loadRootWorkflowPresentation).toHaveBeenCalledWith('analysis')
  })

  it('prefers a fresh recovery graph over the last-opened workflow', async () => {
    const recoveredInfo = workflowInfo('recovered', '2026-05-21T10:00:00Z')
    const lastInfo = workflowInfo('last-opened')
    const draftGraph = graph('draft')
    const recoveryGraph = graph('recovery')
    const draft: WorkflowDraftResponse = {
      draft_version: 1,
      workflow_id: 'recovered',
      base_saved_revision: 'sha256:abc',
      draft_revision: 2,
      updated_at: '2026-05-21T11:00:00Z',
      updated_by: 'agent',
      dirty_against_saved: true,
      graph: draftGraph,
      validation: { valid: true, node_statuses: {}, errors: [] },
    }
    workflowStoreMock.flattenedWorkflows = [lastInfo, recoveredInfo]
    workflowStoreMock.workflows = [lastInfo, recoveredInfo]
    autoSaveMock.loadMostRecentAutoSave.mockResolvedValueOnce({
      name: 'recovered',
      graph: recoveryGraph,
      timestamp: Date.parse('2026-05-21T12:00:00Z'),
    })
    autoSaveMock.getLastOpenedWorkflow.mockResolvedValueOnce('last-opened')
    presentationMocks.loadRootWorkflowPresentation.mockResolvedValueOnce(
      presentation('recovered', { graph: draftGraph, dirty: true, draft }),
    )

    const result = await resolveStartupWorkflow()

    expect(result).toMatchObject({
      workflowName: 'recovered',
      graph: recoveryGraph,
      dirty: true,
    })
    expect(presentationMocks.loadRootWorkflowPresentation).toHaveBeenCalledTimes(1)
    expect(presentationMocks.loadRootWorkflowPresentation).toHaveBeenCalledWith('recovered')
  })

  it('clears a recovery entry that is older than the saved workflow or durable draft', async () => {
    const info = workflowInfo('saved', '2026-05-21T12:00:00Z')
    const loaded = presentation('saved')
    workflowStoreMock.flattenedWorkflows = [info]
    workflowStoreMock.workflows = [info]
    autoSaveMock.loadMostRecentAutoSave.mockResolvedValueOnce({
      name: 'saved',
      graph: graph('stale'),
      timestamp: Date.parse('2026-05-21T11:59:59Z'),
    })
    presentationMocks.loadRootWorkflowPresentation.mockResolvedValueOnce(loaded)

    await expect(resolveStartupWorkflow()).resolves.toEqual(loaded)

    expect(autoSaveMock.clearAutoSave).toHaveBeenCalledWith('saved')
  })

  it('clears recovery for an obsolete workflow name and opens the known last workflow', async () => {
    const info = workflowInfo('renamed')
    const loaded = presentation('renamed')
    workflowStoreMock.flattenedWorkflows = [info]
    workflowStoreMock.workflows = [info]
    autoSaveMock.loadMostRecentAutoSave.mockResolvedValueOnce({
      name: 'Untitled',
      graph: graph('stale'),
      timestamp: Date.parse('2026-05-21T12:00:00Z'),
    })
    autoSaveMock.getLastOpenedWorkflow.mockResolvedValueOnce('renamed')
    presentationMocks.loadRootWorkflowPresentation.mockResolvedValueOnce(loaded)

    await expect(resolveStartupWorkflow()).resolves.toEqual(loaded)

    expect(autoSaveMock.clearAutoSave).toHaveBeenCalledWith('Untitled')
    expect(presentationMocks.loadRootWorkflowPresentation).toHaveBeenCalledWith('renamed')
  })

  it('clears a missing startup target and falls through to the next known workflow', async () => {
    const missingInfo = workflowInfo('missing')
    const fallbackInfo = workflowInfo('fallback')
    const loaded = presentation('fallback')
    workflowStoreMock.flattenedWorkflows = [missingInfo, fallbackInfo]
    workflowStoreMock.workflows = [missingInfo, fallbackInfo]
    autoSaveMock.loadMostRecentAutoSave.mockResolvedValueOnce({
      name: 'missing',
      graph: graph('recovery'),
      timestamp: Date.parse('2026-05-21T12:00:00Z'),
    })
    autoSaveMock.getLastOpenedWorkflow.mockResolvedValueOnce('missing')
    presentationMocks.loadRootWorkflowPresentation
      .mockRejectedValueOnce(new Error('404'))
      .mockResolvedValueOnce(loaded)

    await expect(resolveStartupWorkflow()).resolves.toEqual(loaded)

    expect(autoSaveMock.clearAutoSave).toHaveBeenCalledWith('missing')
    expect(autoSaveMock.setLastOpenedWorkflow).toHaveBeenCalledWith(null)
    expect(presentationMocks.loadRootWorkflowPresentation.mock.calls).toEqual([
      ['missing'],
      ['fallback'],
    ])
  })

  it('returns null instead of creating a special startup workflow when none can load', async () => {
    const info = workflowInfo('missing')
    workflowStoreMock.flattenedWorkflows = [info]
    workflowStoreMock.workflows = [info]
    autoSaveMock.getLastOpenedWorkflow.mockResolvedValueOnce('missing')
    presentationMocks.loadRootWorkflowPresentation.mockRejectedValueOnce(new Error('404'))

    await expect(resolveStartupWorkflow()).resolves.toBeNull()

    expect(autoSaveMock.setLastOpenedWorkflow).toHaveBeenCalledWith(null)
  })
})
