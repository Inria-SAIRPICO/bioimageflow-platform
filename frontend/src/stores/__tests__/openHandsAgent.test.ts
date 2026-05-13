import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import {
  applyOpenHandsProposal,
  getOpenHandsStatus,
  rejectOpenHandsProposal,
  sendOpenHandsContext,
  shutdownOpenHandsAgent,
  startOpenHandsAgent,
} from '@/api/openhands'
import { useOpenHandsAgentStore } from '../openHandsAgent'

vi.mock('@/api/openhands', () => ({
  applyOpenHandsProposal: vi.fn(),
  getOpenHandsStatus: vi.fn(),
  rejectOpenHandsProposal: vi.fn(),
  sendOpenHandsContext: vi.fn(),
  shutdownOpenHandsAgent: vi.fn(),
  startOpenHandsAgent: vi.fn(),
}))

describe('openHandsAgent store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(getOpenHandsStatus).mockResolvedValue({
      available: false,
      status: 'unavailable',
      iframe_url: null,
      external_url: null,
      message: 'OpenHands is not configured',
      proposals: [],
    })
  })

  it('loads unavailable status with message', async () => {
    const store = useOpenHandsAgentStore()

    await store.refreshStatus()

    expect(store.available).toBe(false)
    expect(store.status).toBe('unavailable')
    expect(store.message).toBe('OpenHands is not configured')
    expect(store.isLoadingStatus).toBe(false)
  })

  it('starts, retries, and shuts down through the API', async () => {
    vi.mocked(startOpenHandsAgent)
      .mockResolvedValueOnce({
        available: true,
        status: 'starting',
        iframe_url: null,
        external_url: null,
        message: null,
        proposals: [],
      })
      .mockResolvedValueOnce({
        available: true,
        status: 'running',
        iframe_url: 'http://127.0.0.1:3000',
        external_url: 'http://127.0.0.1:3000',
        message: null,
        proposals: [],
      })
    vi.mocked(shutdownOpenHandsAgent).mockResolvedValueOnce({
      available: true,
      status: 'stopped',
      iframe_url: null,
      external_url: null,
      message: null,
      proposals: [],
    })
    const store = useOpenHandsAgentStore()

    await store.start()
    expect(store.status).toBe('starting')

    await store.retry()
    expect(store.status).toBe('running')
    expect(store.iframeUrl).toBe('http://127.0.0.1:3000')

    await store.shutdown()
    expect(store.status).toBe('stopped')
  })

  it('sends context and tracks the active context summary', async () => {
    vi.mocked(sendOpenHandsContext).mockResolvedValueOnce({
      accepted: true,
      context: {
        workflow_name: 'cells',
        workflow_display_name: 'Cells',
        selected_node_ids: ['segment'],
        dirty: true,
        draft: { graph: { nodes: [], edges: [] } },
      },
    })
    const store = useOpenHandsAgentStore()

    await store.sendCurrentContext({
      workflow_name: 'cells',
      workflow_display_name: 'Cells',
      selected_node_ids: ['segment'],
      dirty: true,
      draft: { graph: { nodes: [], edges: [] } },
    })

    expect(sendOpenHandsContext).toHaveBeenCalledWith(expect.objectContaining({
      workflow_name: 'cells',
      selected_node_ids: ['segment'],
    }))
    expect(store.context?.workflow_display_name).toBe('Cells')
  })

  it('applies proposal graph responses and rejects proposals', async () => {
    const applyListener = vi.fn()
    window.addEventListener('bioimageflow:apply-graph', applyListener)
    vi.mocked(applyOpenHandsProposal).mockResolvedValueOnce({
      applied: true,
      proposal: {
        id: 'proposal-1',
        title: 'Add segmentation',
        summary: 'Adds a segmentation node.',
        status: 'applied',
        draft: { graph: { nodes: [], edges: [] } },
      },
    })
    vi.mocked(rejectOpenHandsProposal).mockResolvedValueOnce({
      rejected: true,
      proposal: {
        id: 'proposal-1',
        title: 'Add segmentation',
        summary: 'Adds a segmentation node.',
        status: 'rejected',
      },
    })
    const store = useOpenHandsAgentStore()

    await store.applyProposal('proposal-1')
    await store.rejectProposal('proposal-1')

    expect(applyListener).toHaveBeenCalledTimes(1)
    expect(applyListener.mock.calls[0][0].detail.graph).toEqual({ nodes: [], edges: [] })
    expect(rejectOpenHandsProposal).toHaveBeenCalledWith('proposal-1')
    window.removeEventListener('bioimageflow:apply-graph', applyListener)
  })

  it('marks iframe as blocked when embedding fails', () => {
    const store = useOpenHandsAgentStore()

    store.setIframeBlocked(true)

    expect(store.iframeBlocked).toBe(true)
  })
})
