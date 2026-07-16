import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/client', () => ({ api: apiMocks }))

import {
  deleteNestedWorkflowSnapshot,
  getNestedWorkflowSnapshot,
  openNestedWorkflowSnapshot,
  putNestedWorkflowSnapshot,
} from '../nestedWorkflowSnapshots'

const graph = { nodes: [], edges: [], published_inputs: [], published_outputs: [] }

describe('nested workflow snapshot API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('sends complete open and revision-checked mutation contracts', async () => {
    const response = {
      snapshot_version: 1 as const,
      session_id: 'f16fd9d4-18e5-4d73-a9df-b7675ef44c9e',
      owner: { kind: 'root' as const, canvas_id: 'canvas', workflow_id: null },
      parent_node_id: 'sub_1',
      snapshot_revision: 0,
      updated_at: '2026-07-16T00:00:00Z',
      graph,
      validation: { valid: true, node_statuses: {}, errors: [] },
    }
    apiMocks.post.mockResolvedValue({ data: response })
    apiMocks.get.mockResolvedValue({ data: response })
    apiMocks.put.mockResolvedValue({ data: { ...response, snapshot_revision: 1 } })
    apiMocks.delete.mockResolvedValue({ data: undefined })
    const controller = new AbortController()

    await openNestedWorkflowSnapshot({
      owner: response.owner,
      parent_node_id: 'sub_1',
      graph,
    }, controller.signal)
    await getNestedWorkflowSnapshot(response.session_id, controller.signal)
    await putNestedWorkflowSnapshot(response.session_id, {
      expected_revision: 0,
      graph,
    }, controller.signal)
    await deleteNestedWorkflowSnapshot(response.session_id, 1, controller.signal)

    expect(apiMocks.post).toHaveBeenCalledWith(
      '/api/v1/nested-workflow-snapshots/open',
      expect.objectContaining({ graph }),
      { signal: controller.signal },
    )
    expect(apiMocks.get).toHaveBeenCalledWith(
      `/api/v1/nested-workflow-snapshots/${response.session_id}`,
      { signal: controller.signal },
    )
    expect(apiMocks.put).toHaveBeenCalledWith(
      `/api/v1/nested-workflow-snapshots/${response.session_id}`,
      { expected_revision: 0, graph },
      { signal: controller.signal },
    )
    expect(apiMocks.delete).toHaveBeenCalledWith(
      `/api/v1/nested-workflow-snapshots/${response.session_id}`,
      { params: { expected_revision: 1 }, signal: controller.signal },
    )
  })
})
