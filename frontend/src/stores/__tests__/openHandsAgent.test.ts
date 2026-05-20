import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import {
  approveOpenHandsApproval,
  applyOpenHandsProposal,
  getOpenHandsConfig,
  getOpenHandsStatus,
  installOpenHandsAgent,
  rejectOpenHandsProposal,
  rejectOpenHandsApproval,
  sendOpenHandsContext,
  saveOpenHandsConfig,
  shutdownOpenHandsAgent,
  startOpenHandsAgent,
  undoOpenHandsChange,
} from '@/api/openhands'
import { useOpenHandsAgentStore } from '../openHandsAgent'

vi.mock('@/api/openhands', () => ({
  approveOpenHandsApproval: vi.fn(),
  applyOpenHandsProposal: vi.fn(),
  getOpenHandsConfig: vi.fn(),
  getOpenHandsStatus: vi.fn(),
  installOpenHandsAgent: vi.fn(),
  rejectOpenHandsProposal: vi.fn(),
  rejectOpenHandsApproval: vi.fn(),
  sendOpenHandsContext: vi.fn(),
  saveOpenHandsConfig: vi.fn(),
  shutdownOpenHandsAgent: vi.fn(),
  startOpenHandsAgent: vi.fn(),
  undoOpenHandsChange: vi.fn(),
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
    vi.mocked(getOpenHandsConfig).mockResolvedValue({
      installed: false,
      configured: false,
      provider: '',
      model: '',
      api_key_ref: '',
      command: '',
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
    store.applyStatus({
      available: true,
      status: 'stopped',
      iframe_url: null,
      external_url: null,
      message: null,
      installed: true,
      configured: true,
      proposals: [],
    })

    await store.start()
    expect(store.status).toBe('starting')

    await store.retry()
    expect(store.status).toBe('running')
    expect(store.iframeUrl).toBe('http://127.0.0.1:3000')

    await store.shutdown()
    expect(store.status).toBe('stopped')
  })

  it('loads install/config state and only starts when installed and configured', async () => {
    vi.mocked(getOpenHandsConfig).mockResolvedValueOnce({
      installed: false,
      configured: false,
      provider: 'openai',
      model: 'gpt-5',
      api_key_ref: '',
      command: 'openhands',
    })
    vi.mocked(installOpenHandsAgent).mockResolvedValueOnce({
      installed: true,
      configured: false,
      provider: 'openai',
      model: 'gpt-5',
      api_key_ref: '',
      command: 'openhands',
    })
    vi.mocked(saveOpenHandsConfig).mockResolvedValueOnce({
      installed: true,
      configured: true,
      provider: 'openai',
      model: 'gpt-5',
      api_key_ref: 'OPENAI_API_KEY',
      command: 'openhands',
    })
    const store = useOpenHandsAgentStore()

    await store.refreshConfig()
    expect(store.canStart).toBe(false)

    await store.install()
    expect(store.installed).toBe(true)
    expect(store.canStart).toBe(false)

    store.updateConfigDraft('api_key_ref', 'OPENAI_API_KEY')
    await store.saveConfig()
    expect(store.configured).toBe(true)
    expect(store.canStart).toBe(true)
  })

  it('sends context and tracks the active context summary', async () => {
    vi.mocked(sendOpenHandsContext).mockResolvedValueOnce({
      accepted: true,
      context: {
        workflow_name: 'cells',
        workflow_display_name: 'Cells',
        selected_node_ids: ['segment'],
        dirty: true,
        draft: { draft_id: 'draft-1', revision: 7, graph: { nodes: [], edges: [] } },
      },
    })
    const store = useOpenHandsAgentStore()

    await store.sendCurrentContext({
      workflow_name: 'cells',
      workflow_display_name: 'Cells',
      selected_node_ids: ['segment'],
      dirty: true,
      draft: { draft_id: 'draft-1', revision: 7, graph: { nodes: [], edges: [] } },
    })

    expect(sendOpenHandsContext).toHaveBeenCalledWith(expect.objectContaining({
      workflow_name: 'cells',
      selected_node_ids: ['segment'],
      draft: expect.objectContaining({ draft_id: 'draft-1', revision: 7 }),
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
        draft_id: 'draft-1',
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
        draft_id: 'draft-1',
      },
    })
    const store = useOpenHandsAgentStore()
    store.applyStatus({
      available: true,
      status: 'running',
      iframe_url: null,
      external_url: null,
      message: null,
      proposals: [{
        id: 'proposal-1',
        title: 'Add segmentation',
        summary: 'Adds a segmentation node.',
        status: 'pending',
        draft_id: 'draft-1',
      }],
    })

    await store.applyProposal('proposal-1')
    store.applyStatus({
      available: true,
      status: 'running',
      iframe_url: null,
      external_url: null,
      message: null,
      proposals: [{
        id: 'proposal-1',
        title: 'Add segmentation',
        summary: 'Adds a segmentation node.',
        status: 'pending',
        draft_id: 'draft-1',
      }],
    })
    await store.rejectProposal('proposal-1')

    expect(applyListener).toHaveBeenCalledTimes(1)
    expect(applyListener.mock.calls[0][0].detail.graph).toEqual({ nodes: [], edges: [] })
    expect(applyOpenHandsProposal).toHaveBeenCalledWith('draft-1', 'proposal-1')
    expect(rejectOpenHandsProposal).toHaveBeenCalledWith('draft-1', 'proposal-1')
    window.removeEventListener('bioimageflow:apply-graph', applyListener)
  })

  it('tracks package install approvals and can approve or reject them', async () => {
    vi.mocked(approveOpenHandsApproval).mockResolvedValueOnce({ approved: true })
    vi.mocked(rejectOpenHandsApproval).mockResolvedValueOnce({ rejected: true })
    const store = useOpenHandsAgentStore()
    store.applyStatus({
      available: true,
      status: 'running',
      iframe_url: null,
      external_url: null,
      message: null,
      installed: true,
      configured: true,
      proposals: [],
      approvals: [{
        id: 'approval-1',
        type: 'package_install',
        package_name: 'cellpose',
        command: 'pip install cellpose',
        status: 'pending',
      }],
    })

    await store.approveApproval('approval-1')
    store.applyStatus({
      available: true,
      status: 'running',
      iframe_url: null,
      external_url: null,
      message: null,
      installed: true,
      configured: true,
      proposals: [],
      approvals: [{
        id: 'approval-2',
        type: 'package_install',
        package_name: 'stardist',
        status: 'pending',
      }],
    })
    await store.rejectApproval('approval-2')

    expect(approveOpenHandsApproval).toHaveBeenCalledWith('approval-1')
    expect(rejectOpenHandsApproval).toHaveBeenCalledWith('approval-2')
    expect(store.approvals).toEqual([])
  })

  it('marks automatic agent graph changes as undoable and can undo through backend', async () => {
    const applyListener = vi.fn()
    window.addEventListener('bioimageflow:apply-graph', applyListener)
    vi.mocked(applyOpenHandsProposal).mockResolvedValueOnce({
      applied: true,
      graph: { nodes: [{ id: 'agent-node' } as any], edges: [] },
      draft_id: 'draft-1',
      revision: 8,
    })
    vi.mocked(undoOpenHandsChange).mockResolvedValueOnce({
      graph: { nodes: [], edges: [] },
      draft_id: 'draft-1',
      revision: 9,
    })
    const store = useOpenHandsAgentStore()
    store.context = {
      workflow_name: 'cells',
      workflow_display_name: 'Cells',
      selected_node_ids: [],
      dirty: true,
      draft: { draft_id: 'draft-1', revision: 7, graph: { nodes: [], edges: [] } },
    }
    store.applyStatus({
      available: true,
      status: 'running',
      iframe_url: null,
      external_url: null,
      message: null,
      installed: true,
      configured: true,
      proposals: [{
        id: 'proposal-1',
        title: 'Add node',
        summary: 'Adds a node.',
        status: 'pending',
        draft_id: 'draft-1',
      }],
    })

    await store.applyProposal('proposal-1')
    await store.undoLastChange()

    expect(applyListener).toHaveBeenNthCalledWith(1, expect.objectContaining({
      detail: expect.objectContaining({ pushUndo: true }),
    }))
    expect(undoOpenHandsChange).toHaveBeenCalledWith('draft-1')
    expect(applyListener).toHaveBeenNthCalledWith(2, expect.objectContaining({
      detail: expect.objectContaining({ graph: { nodes: [], edges: [] }, dirty: true }),
    }))
    window.removeEventListener('bioimageflow:apply-graph', applyListener)
  })

  it('marks iframe as blocked when embedding fails', () => {
    const store = useOpenHandsAgentStore()

    store.setIframeBlocked(true)

    expect(store.iframeBlocked).toBe(true)
  })
})
