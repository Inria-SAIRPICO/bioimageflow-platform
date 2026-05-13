import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import {
  applyOpenHandsProposal,
  getOpenHandsStatus,
  rejectOpenHandsProposal,
  sendOpenHandsContext,
  shutdownOpenHandsAgent,
  startOpenHandsAgent,
} from '@/api/openhands'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

const mockedGet = vi.mocked(api.get as any)
const mockedPost = vi.mocked(api.post as any)

describe('openhands api helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches agent status', async () => {
    mockedGet.mockResolvedValueOnce({
      data: {
        available: true,
        status: 'running',
        iframe_url: 'http://127.0.0.1:3000',
        external_url: 'http://127.0.0.1:3000',
        message: null,
        proposals: [],
      },
    })

    await expect(getOpenHandsStatus()).resolves.toMatchObject({
      available: true,
      status: 'running',
    })
    expect(mockedGet).toHaveBeenCalledWith('/api/v1/openhands/status')
  })

  it('starts and shuts down the agent', async () => {
    mockedPost
      .mockResolvedValueOnce({ data: { available: true, status: 'starting' } })
      .mockResolvedValueOnce({ data: { available: true, status: 'stopped' } })

    await startOpenHandsAgent()
    await shutdownOpenHandsAgent()

    expect(mockedPost).toHaveBeenNthCalledWith(1, '/api/v1/openhands/start')
    expect(mockedPost).toHaveBeenNthCalledWith(2, '/api/v1/openhands/shutdown')
  })

  it('sends current workflow draft context', async () => {
    const payload = {
      workflow_name: 'cells',
      workflow_display_name: 'Cells',
      selected_node_ids: ['segment'],
      dirty: true,
      draft: { graph: { nodes: [], edges: [] } },
    }
    mockedPost.mockResolvedValueOnce({ data: { accepted: true } })

    await sendOpenHandsContext(payload)

    expect(mockedPost).toHaveBeenCalledWith('/api/v1/openhands/context', payload)
  })

  it('applies and rejects proposals by id', async () => {
    mockedPost
      .mockResolvedValueOnce({ data: { applied: true } })
      .mockResolvedValueOnce({ data: { rejected: true } })

    await applyOpenHandsProposal('proposal-1')
    await rejectOpenHandsProposal('proposal-1')

    expect(mockedPost).toHaveBeenNthCalledWith(
      1,
      '/api/v1/openhands/proposals/proposal-1/apply',
    )
    expect(mockedPost).toHaveBeenNthCalledWith(
      2,
      '/api/v1/openhands/proposals/proposal-1/reject',
    )
  })
})
