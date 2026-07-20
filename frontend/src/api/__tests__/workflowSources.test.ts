import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import {
  applyWorkflowSourceOperation,
  previewPythonWorkflowSource,
  previewWorkflowSourceUpdate,
} from '../workflowSources'

vi.mock('@/api/client', () => ({ api: { post: vi.fn() } }))

describe('workflow source API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('previews a source update at a stable workflow-node path', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { token: 'preview' } } as never)
    await previewWorkflowSourceUpdate('folder/parent', {
      workflow_path: ['child'],
      expected_artifact_hash: `sha256:${'a'.repeat(64)}`,
    })
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/workflows/folder/parent/source-update/preview',
      {
        workflow_path: ['child'],
        expected_artifact_hash: `sha256:${'a'.repeat(64)}`,
      },
    )
  })

  it('previews trusted Python materialization without accepting a path', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { token: 'preview' } } as never)
    await previewPythonWorkflowSource('parent', {
      expected_artifact_hash: `sha256:${'b'.repeat(64)}`,
    })
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/workflows/parent/python-source/preview',
      { expected_artifact_hash: `sha256:${'b'.repeat(64)}` },
    )
  })

  it('applies the immutable preview token with exact confirmations', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { graph: {}, artifact_hash: 'hash' } } as never)
    await applyWorkflowSourceOperation('parent', {
      token: 'preview',
      confirm_effects: [],
    })
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/workflows/parent/source-operations/apply',
      { token: 'preview', confirm_effects: [] },
    )
  })
})
