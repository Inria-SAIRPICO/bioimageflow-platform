import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import {
  applyWorkflowFormatMigrations,
  getWorkflowFormatNotices,
  getWorkflowFormatStatus,
} from '@/api/workflowFormats'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

describe('workflow format API', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
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

  it('returns the pending plan and confirms that exact plan', async () => {
    const status = {
      notices: [],
      pending_plan_id: `sha256:${'a'.repeat(64)}`,
    }
    vi.mocked(api.get).mockResolvedValueOnce({ data: status })
    vi.mocked(api.post).mockResolvedValueOnce({
      data: { notices: [], pending_plan_id: null },
    })

    await expect(getWorkflowFormatStatus()).resolves.toEqual(status)
    await expect(
      applyWorkflowFormatMigrations(status.pending_plan_id),
    ).resolves.toEqual({ notices: [], pending_plan_id: null })
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/workflows/format-migrations/apply',
      { pending_plan_id: status.pending_plan_id },
    )
  })
})
