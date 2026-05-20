import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OpenHandsAgentPanel from '../OpenHandsAgentPanel.vue'
import { useOpenHandsAgentStore } from '@/stores/openHandsAgent'
import { useUIStore } from '@/stores/ui'
import { useWorkflowStore } from '@/stores/workflow'

const graphSyncState = vi.hoisted(() => ({
  currentGraph: { value: { nodes: [] as any[], edges: [] as any[] } },
  draft_id: { value: 'draft-1' as string | null },
  revision: { value: 7 },
}))

vi.mock('@/composables/useGraphSync', () => ({
  useGraphSync: () => graphSyncState,
}))

describe('OpenHandsAgentPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    graphSyncState.currentGraph.value = { nodes: [], edges: [] }
    graphSyncState.draft_id.value = 'draft-1'
    graphSyncState.revision.value = 7
  })

  it('loads status on mount without auto-starting and renders install state', async () => {
    const store = useOpenHandsAgentStore()
    const refresh = vi.spyOn(store, 'refreshStatus').mockResolvedValue(undefined)
    const start = vi.spyOn(store, 'start').mockResolvedValue(undefined)
    const install = vi.spyOn(store, 'install').mockResolvedValue(undefined)
    store.applyStatus({
      available: false,
      status: 'unavailable',
      iframe_url: null,
      external_url: null,
      message: 'OpenHands is not configured',
      installed: false,
      configured: false,
      proposals: [],
    })

    const wrapper = mount(OpenHandsAgentPanel)
    await flushPromises()

    expect(refresh).toHaveBeenCalledOnce()
    expect(start).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="openhands-agent-unavailable"]').text())
      .toContain('OpenHands is not configured')
    await wrapper.find('[data-testid="openhands-agent-install"]').trigger('click')
    expect(install).toHaveBeenCalledOnce()
  })

  it('renders settings inputs and enables Start only after installed/configured', async () => {
    const store = useOpenHandsAgentStore()
    vi.spyOn(store, 'refreshStatus').mockResolvedValue(undefined)
    const start = vi.spyOn(store, 'start').mockResolvedValue(undefined)
    store.applyConfig({
      installed: false,
      configured: false,
      provider: '',
      model: '',
      api_key_ref: '',
      command: '',
    })
    const wrapper = mount(OpenHandsAgentPanel)

    expect(wrapper.find('[data-testid="openhands-agent-provider"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="openhands-agent-model"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="openhands-agent-api-key-ref"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="openhands-agent-command"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="openhands-agent-start"]').attributes('disabled'))
      .toBeDefined()

    store.applyConfig({
      installed: true,
      configured: true,
      provider: 'openai',
      model: 'gpt-5',
      api_key_ref: 'OPENAI_API_KEY',
      command: 'openhands',
    })
    await wrapper.vm.$nextTick()
    await wrapper.find('[data-testid="openhands-agent-start"]').trigger('click')

    expect(start).toHaveBeenCalledOnce()
  })

  it('shows loading state while status is pending', () => {
    const store = useOpenHandsAgentStore()
    store.isLoadingStatus = true

    const wrapper = mount(OpenHandsAgentPanel)

    expect(wrapper.find('[data-testid="openhands-agent-loading"]').text())
      .toContain('Checking OpenHands')
  })

  it('renders iframe and fallback external action when running', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
    const store = useOpenHandsAgentStore()
    vi.spyOn(store, 'refreshStatus').mockResolvedValue(undefined)
    store.applyStatus({
      available: true,
      status: 'running',
      iframe_url: 'http://127.0.0.1:3000',
      external_url: 'http://127.0.0.1:3000',
      message: null,
      installed: true,
      configured: true,
      proposals: [],
    })
    const wrapper = mount(OpenHandsAgentPanel)

    expect(wrapper.find('[data-testid="openhands-agent-iframe"]').attributes('src'))
      .toBe('http://127.0.0.1:3000')

    await wrapper.find('[data-testid="openhands-agent-iframe"]').trigger('error')
    expect(wrapper.find('[data-testid="openhands-agent-iframe-blocked"]').exists()).toBe(true)

    await wrapper.find('[data-testid="openhands-agent-open-external"]').trigger('click')
    expect(openSpy).toHaveBeenCalledWith('http://127.0.0.1:3000', '_blank', 'noopener')
    openSpy.mockRestore()
  })

  it('sends current workflow draft context', async () => {
    graphSyncState.currentGraph.value = {
      nodes: [{ id: 'segment' } as any],
      edges: [],
    }
    const uiStore = useUIStore()
    uiStore.setSelectedNodes(['segment'])
    uiStore.markDirty()
    const workflowStore = useWorkflowStore()
    workflowStore.current = {
      name: 'cells',
      display_name: 'Cells',
      path: '/tmp/cells.json',
      last_modified: '2026-05-13T00:00:00Z',
    }
    const agentStore = useOpenHandsAgentStore()
    vi.spyOn(agentStore, 'refreshStatus').mockResolvedValue(undefined)
    const send = vi.spyOn(agentStore, 'sendCurrentContext').mockResolvedValue(undefined)

    const wrapper = mount(OpenHandsAgentPanel)
    await wrapper.find('[data-testid="openhands-agent-send-context"]').trigger('click')

    expect(send).toHaveBeenCalledWith({
      workflow_name: 'cells',
      workflow_display_name: 'Cells',
      selected_node_ids: ['segment'],
      dirty: true,
      draft: {
        draft_id: 'draft-1',
        revision: 7,
        graph: graphSyncState.currentGraph.value,
        workflow_name: 'cells',
        workflow_display_name: 'Cells',
      },
    })
    expect(wrapper.find('[data-testid="openhands-agent-context"]').text()).toContain('Cells')
  })

  it('renders proposal review actions', async () => {
    const store = useOpenHandsAgentStore()
    vi.spyOn(store, 'refreshStatus').mockResolvedValue(undefined)
    const apply = vi.spyOn(store, 'applyProposal').mockResolvedValue(undefined)
    const reject = vi.spyOn(store, 'rejectProposal').mockResolvedValue(undefined)
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
        title: 'Add segmentation',
        summary: 'Adds a segmentation node.',
        status: 'pending',
        draft_id: 'draft-1',
        draft: { graph: { nodes: [], edges: [] } },
      }],
    })
    const wrapper = mount(OpenHandsAgentPanel)

    expect(wrapper.find('[data-testid="openhands-agent-proposal"]').text())
      .toContain('Add segmentation')

    await wrapper.find('[data-testid="openhands-agent-apply-proposal"]').trigger('click')
    await wrapper.find('[data-testid="openhands-agent-reject-proposal"]').trigger('click')

    expect(apply).toHaveBeenCalledWith('proposal-1')
    expect(reject).toHaveBeenCalledWith('proposal-1')
  })

  it('renders package install approvals and undo action', async () => {
    const store = useOpenHandsAgentStore()
    vi.spyOn(store, 'refreshStatus').mockResolvedValue(undefined)
    const approve = vi.spyOn(store, 'approveApproval').mockResolvedValue(undefined)
    const reject = vi.spyOn(store, 'rejectApproval').mockResolvedValue(undefined)
    const undo = vi.spyOn(store, 'undoLastChange').mockResolvedValue(undefined)
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
    store.undoAvailable = true
    const wrapper = mount(OpenHandsAgentPanel)

    expect(wrapper.find('[data-testid="openhands-agent-approval"]').text())
      .toContain('cellpose')
    await wrapper.find('[data-testid="openhands-agent-approve-approval"]').trigger('click')
    await wrapper.find('[data-testid="openhands-agent-reject-approval"]').trigger('click')
    await wrapper.find('[data-testid="openhands-agent-undo"]').trigger('click')

    expect(approve).toHaveBeenCalledWith('approval-1')
    expect(reject).toHaveBeenCalledWith('approval-1')
    expect(undo).toHaveBeenCalledOnce()
  })
})
