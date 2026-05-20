import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
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
        running: true,
        url: 'http://127.0.0.1:12000',
        reason: null,
      },
    })

    await expect(getOpenHandsStatus()).resolves.toMatchObject({
      available: true,
      status: 'running',
    })
    expect(mockedGet).toHaveBeenCalledWith('/api/v1/openhands/status')
  })

  it('loads, saves, and installs OpenHands configuration', async () => {
    mockedGet.mockResolvedValueOnce({
      data: {
        installed: false,
        provider: 'openai',
        model: 'gpt-5',
        api_key_ref: 'OPENAI_API_KEY',
        command: 'openhands',
      },
    })
    mockedPost
      .mockResolvedValueOnce({ data: { installed: true } })
      .mockResolvedValueOnce({ data: { configured: true } })

    await getOpenHandsConfig()
    await installOpenHandsAgent()
    await saveOpenHandsConfig({
      provider: 'openai',
      model: 'gpt-5',
      api_key_ref: 'OPENAI_API_KEY',
      command: 'openhands',
    })

    expect(mockedGet).toHaveBeenCalledWith('/api/v1/openhands/config')
    expect(mockedPost).toHaveBeenNthCalledWith(1, '/api/v1/openhands/install')
    expect(mockedPost).toHaveBeenNthCalledWith(2, '/api/v1/openhands/config', {
      provider: 'openai',
      model: 'gpt-5',
      api_key_ref: 'OPENAI_API_KEY',
      command: 'openhands',
    })
  })

  it('starts and shuts down the agent', async () => {
    mockedPost
      .mockResolvedValueOnce({ data: { available: true, running: true } })
      .mockResolvedValueOnce({ data: { available: true, running: false } })

    await startOpenHandsAgent()
    await shutdownOpenHandsAgent()

    expect(mockedPost).toHaveBeenNthCalledWith(1, '/api/v1/openhands/launch')
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

  it('handles package install approvals and agent undo', async () => {
    mockedPost
      .mockResolvedValueOnce({ data: { approved: true } })
      .mockResolvedValueOnce({ data: { rejected: true } })
      .mockResolvedValueOnce({ data: { graph: { nodes: [], edges: [] } } })

    await approveOpenHandsApproval('approval-1')
    await rejectOpenHandsApproval('approval-2')
    await undoOpenHandsChange('draft-1')

    expect(mockedPost).toHaveBeenNthCalledWith(
      1,
      '/api/v1/openhands/approvals/approval-1/approve',
    )
    expect(mockedPost).toHaveBeenNthCalledWith(
      2,
      '/api/v1/openhands/approvals/approval-2/reject',
    )
    expect(mockedPost).toHaveBeenNthCalledWith(3, '/api/v1/openhands/undo', {
      draft_id: 'draft-1',
    })
  })

  it('applies and rejects proposals by id', async () => {
    mockedPost
      .mockResolvedValueOnce({ data: { applied: true } })
      .mockResolvedValueOnce({ data: { rejected: true } })

    await applyOpenHandsProposal('draft-1', 'proposal-1')
    await rejectOpenHandsProposal('draft-1', 'proposal-1')

    expect(mockedPost).toHaveBeenNthCalledWith(
      1,
      '/api/v1/workflow-drafts/draft-1/agent-proposals/proposal-1/apply',
    )
    expect(mockedPost).toHaveBeenNthCalledWith(
      2,
      '/api/v1/workflow-drafts/draft-1/agent-proposals/proposal-1/reject',
    )
  })
})
