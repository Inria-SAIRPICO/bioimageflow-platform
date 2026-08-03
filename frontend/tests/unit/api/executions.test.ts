import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

import { api } from '@/api/client'
import {
  applyPreparedExecution,
  preflightExecution,
  type ExecutionPreflightRequest,
} from '@/api/executions'

const request: ExecutionPreflightRequest = {
  workflow_id: 'demo',
  draft_revision: 3,
  graph: {},
  target_id: 'profile_1',
  profile_revision: 2,
  command: { kind: 'workflow' },
}

describe('distributed execution API adapter', () => {
  beforeEach(() => {
    vi.mocked(api.post).mockReset()
  })

  it('maps the public BioImageFlow path plan into explicit UI choices', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        kind: 'resolution_required',
        distributed_plan: { nodes: [] },
        unresolved: [{ scoped_node_path: 'files', input_name: 'path' }],
        remote_node_paths: {
          inputs: [{
            scoped_node_path: 'files', input_name: 'path', value_shape: 'path',
            nullable: false, path_picker: 'folder', current_paths: ['images'],
            cluster_compatible: false,
          }],
        },
      },
    })

    const response = await preflightExecution(request)

    expect(response).toEqual({
      status: 'resolution_required',
      unresolved_paths: [{
        node_path: 'files', input_name: 'path', value_shape: 'path',
        values: ['images'], nullable: false, path_picker: 'folder',
        cluster_compatible: false,
      }],
    })
  })

  it('sends scoped invocation-only choices and normalizes retained snapshots', async () => {
    vi.mocked(api.post)
      .mockResolvedValueOnce({
        data: {
          kind: 'ready', token: 'prepared', expires_at: 1_800_000_000,
          distributed_plan: { nodes: [] },
          manifest: {
            bundle_digest: `sha256:${'1'.repeat(64)}`,
            entries: [], external_sources: [],
          },
        },
      })
      .mockResolvedValueOnce({
        data: {
          revision: 0, execution_id: 'run_1', workflow_id: 'demo',
          draft_revision: 3, backend: 'submitted_remote', target_id: 'profile_1',
          state: 'prepared', jobs: {}, created_at: '2026-08-03T12:00:00Z',
        },
      })
    const choiceRequest: ExecutionPreflightRequest = {
      ...request,
      node_path_resolutions: [
        {
          node_path: 'files', input_name: 'path', value_shape: 'path',
          values: [{ source: 'upload', path: '/local/images' }],
        },
        {
          node_path: 'files', input_name: 'mask', value_shape: 'path',
          values: [{ source: 'cluster', path: '/cluster/mask.tif' }],
        },
      ],
    }

    const prepared = await preflightExecution(choiceRequest)
    if (prepared.status !== 'ready') throw new Error('expected ready')
    const snapshot = await applyPreparedExecution(prepared.token, choiceRequest)

    expect(vi.mocked(api.post).mock.calls[0]?.[1]).toMatchObject({
      profile_revision: 2,
      node_path_choices: {
        files: {
          path: { source: 'upload', value: '/local/images' },
          mask: { source: 'cluster', value: '/cluster/mask.tif' },
        },
      },
    })
    expect(vi.mocked(api.post).mock.calls[1]?.[1]).toEqual({
      token: 'prepared', workflow_id: 'demo', draft_revision: 3,
      target_id: 'profile_1', requested_nodes: null,
    })
    expect(snapshot).toMatchObject({
      id: 'run_1', workflow_id: 'demo', target_mode: 'submitted_remote',
      state: 'prepared', jobs: [],
    })
  })
})
