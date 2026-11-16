import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { api } from '@/api/client'
import { getWorkflowFormatStatus } from '@/api/workflowFormats'
import { useWorkflowStore } from '@/stores/workflow'
import { useSettingsStore } from '@/stores/settings'
import { useUIStore } from '@/stores/ui'
import { useNestedWorkflowSessionsStore } from '@/stores/nestedWorkflowSessions'
import { canvasIdFromPanelId, canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'
import WorkflowIdentityCopiesDialog from '../WorkflowIdentityCopiesDialog.vue'
import type { WorkflowFormatStatus } from '@/api/types'

vi.mock('@/api/client', () => ({ api: { post: vi.fn() } }))
vi.mock('@/api/workflowFormats', () => ({ getWorkflowFormatStatus: vi.fn() }))
const id = 'ea326544-fd09-4f9e-8ec7-425e980927cd'
const digest = `sha256:${'a'.repeat(64)}`
const status = () => ({
  notices: [], workspace_path: '/workspace',
  identity_conflicts: [{ workflow_id: id, copies: [
    { relative_path: 'Analysis/original', document_hash: digest },
    { relative_path: 'Analysis/copied', document_hash: digest },
  ] }],
}) as WorkflowFormatStatus

function render() {
  return mount(WorkflowIdentityCopiesDialog, {
    props: { status: status() },
    global: { plugins: [PrimeVue], stubs: { Dialog: { props: ['visible'], template: '<div v-if="visible"><slot /><slot name="footer" /></div>' } } },
  })
}

describe('external workflow identity copy resolution', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    canvasSessionRegistry.dispose()
    vi.mocked(api.post).mockReset().mockResolvedValue({ data: { id: 'new-workflow' } })
    vi.mocked(getWorkflowFormatStatus).mockReset().mockResolvedValue({ notices: [], workspace_path: '/workspace' })
    vi.spyOn(useWorkflowStore(), 'fetchWorkflowTree').mockResolvedValue([])
  })

  it('requires an explicit directory choice and sends its exact reviewed identity and digest', async () => {
    const wrapper = render()
    await wrapper.get('button').trigger('click')
    const resolve = wrapper.get('[data-testid="workflow-identity-copy-resolve"]')
    expect(resolve.attributes('disabled')).toBeDefined()
    await wrapper.get('select').setValue('Analysis/copied')
    await resolve.trigger('click')
    await flushPromises()
    expect(api.post).toHaveBeenCalledWith('/api/v1/workflows/identity-copies/resolve', {
      relative_path: 'Analysis/copied', expected_workflow_id: id, expected_document_hash: digest,
    }, { headers: { 'X-BioImageFlow-Workspace': '/workspace' } })
    expect(getWorkflowFormatStatus).toHaveBeenCalledWith('/workspace')
    expect(useWorkflowStore().fetchWorkflowTree).toHaveBeenCalledWith({ fresh: true })
    expect(wrapper.emitted('resolved')).toHaveLength(1)
  })

  it.each(['root', 'nested'])('requires affected %s editors to close without discarding them', async kind => {
    if (kind === 'root') {
      const canvasId = canvasIdFromPanelId(`workflow:${id}`)
      useUIStore().setCanvasWorkflow(canvasId, id, 'Original')
      canvasSessionRegistry.register({ kind: 'root', canvasId, workflowId: id })
    } else useNestedWorkflowSessionsStore().sessions = [{ id: 'child', parentWorkflowName: id }] as any
    const wrapper = render()
    await wrapper.get('button').trigger('click')
    await wrapper.get('select').setValue('Analysis/copied')
    expect(wrapper.get('[data-testid="workflow-identity-copy-open-editors"]').text()).toContain('Close the affected workflow')
    expect(wrapper.get('[data-testid="workflow-identity-copy-resolve"]').attributes('disabled')).toBeDefined()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('does not publish late refreshes into another workspace', async () => {
    let accept!: () => void
    vi.mocked(api.post).mockImplementationOnce(() => new Promise(resolve => { accept = () => resolve({ data: {} }) }))
    const wrapper = render()
    await wrapper.get('button').trigger('click')
    await wrapper.get('select').setValue('Analysis/copied')
    await wrapper.get('[data-testid="workflow-identity-copy-resolve"]').trigger('click')
    useSettingsStore().workspaceSelectionRevision += 1
    accept()
    await flushPromises()
    expect(wrapper.text()).toContain('The workspace changed')
    expect(wrapper.emitted('resolved')).toBeUndefined()
    expect(getWorkflowFormatStatus).not.toHaveBeenCalled()
    expect(useWorkflowStore().fetchWorkflowTree).not.toHaveBeenCalled()
  })

  it('preserves the reviewed choice and reports a changed document instead of retrying silently', async () => {
    vi.mocked(api.post).mockRejectedValueOnce(new Error('The workflow directory changed after review. Refresh and try again.'))
    const wrapper = render()
    await wrapper.get('button').trigger('click')
    await wrapper.get('select').setValue('Analysis/copied')
    await wrapper.get('[data-testid="workflow-identity-copy-resolve"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('changed after review')
    expect((wrapper.get('select').element as HTMLSelectElement).value).toBe('Analysis/copied')
    expect(getWorkflowFormatStatus).not.toHaveBeenCalled()
    expect(useWorkflowStore().fetchWorkflowTree).not.toHaveBeenCalled()
  })
})
