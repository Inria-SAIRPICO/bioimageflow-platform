import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { getWorkflowFormatNotices } from '@/api/workflowFormats'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn() },
}))

describe('workflow format API', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset()
  })

  it('returns format notices from the workspace endpoint', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        notices: [{
          status: 'error',
          workflow_id: 'broken',
          path: '/workspace/workflows/broken/workflow.json',
          detail: 'Invalid workflow document.',
          backup_paths: [],
        }],
      },
    })

    await expect(getWorkflowFormatNotices()).resolves.toEqual([
      expect.objectContaining({ workflow_id: 'broken', status: 'error' }),
    ])
    expect(api.get).toHaveBeenCalledWith('/api/v1/workflows/format-status')
  })
})
