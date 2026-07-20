import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { makeGraph } from '@/test-utils/graphFixtures'
import { openNestedWorkflowSnapshot } from '../nestedWorkflowSnapshots'

vi.mock('@/api/client', () => ({ api: { post: vi.fn() } }))

describe('nested workflow snapshot API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('opens a snapshot with the canonical graph document', async () => {
    const graph = makeGraph({ name: 'child', display_name: 'Child' })
    vi.mocked(api.post).mockResolvedValue({ data: { graph } } as never)
    await openNestedWorkflowSnapshot({
      owner: { kind: 'root', canvas_id: 'root', workflow_id: 'parent' },
      parent_node_id: 'child-node',
      graph,
    })
    expect(api.post).toHaveBeenCalledWith('/api/v1/nested-workflow-snapshots/open', {
      owner: { kind: 'root', canvas_id: 'root', workflow_id: 'parent' },
      parent_node_id: 'child-node',
      graph,
    }, { signal: undefined })
  })
})
