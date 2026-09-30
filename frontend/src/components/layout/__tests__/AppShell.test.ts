import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import type { DockviewApi, DockviewReadyEvent } from 'dockview-vue'
import type { IDockviewPanel } from 'dockview-core'
import type { RootWorkflowPresentation } from '@/services/rootWorkflowPresentation'
import { makeGraph } from '@/test-utils/graphFixtures'
import { canvasIdFromPanelId, canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'
import { useUIStore } from '@/stores/ui'

const startup = vi.hoisted(() => ({ resolve: vi.fn() }))
vi.mock('@/services/startupWorkflow', () => ({ resolveStartupWorkflow: startup.resolve }))
vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({ connect: vi.fn(), disconnect: vi.fn() }),
}))
import App from '@/App.vue'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(accept => { resolve = accept })
  return { promise, resolve }
}

function presentation(): RootWorkflowPresentation {
  return {
    graph: makeGraph(), workflowName: 'analysis', workflowDisplayName: 'Analysis',
    missingTools: [], dirty: false, identityGeneration: 0, serverIdentityGeneration: null,
  }
}

function dockview() {
  const panels = new Map<string, IDockviewPanel>()
  let active: IDockviewPanel | undefined
  let onActivation: ((panel: IDockviewPanel) => void) | undefined
  const dispose = vi.fn()
  const addPanel = vi.fn((options: { id: string; params?: Record<string, unknown> }) => {
    const panel = {
      id: options.id, params: options.params,
      api: { setTitle: vi.fn(), setActive: vi.fn(() => {
        active = panel
        onActivation?.(panel)
      }) },
    } as unknown as IDockviewPanel
    if (options.id.startsWith('workflow:')) {
      canvasSessionRegistry.register({
        kind: 'root', canvasId: canvasIdFromPanelId(options.id), workflowId: options.id.slice(9),
      })
    }
    panels.set(panel.id, panel)
    return panel
  })
  const api = {
    addPanel,
    getPanel: (id: string) => panels.get(id),
    removePanel: (panel: IDockviewPanel) => panels.delete(panel.id),
    onDidRemovePanel: () => ({ dispose }),
    onDidActivePanelChange: (listener: (panel: IDockviewPanel) => void) => {
      onActivation = listener
      return { dispose }
    },
  } as unknown as DockviewApi
  return { api, panels, addPanel, dispose, active: () => active }
}

const wrappers: ReturnType<typeof shallowMount>[] = []
function mountShell() {
  const wrapper = shallowMount(App, { global: { plugins: [createPinia(), PrimeVue] } })
  wrappers.push(wrapper)
  const dock = dockview()
  const vm = wrapper.vm as unknown as { onDockviewReady(event: DockviewReadyEvent): void }
  vm.onDockviewReady({ api: dock.api } as DockviewReadyEvent)
  return { wrapper, dock }
}

function acceptedOpen() {
  window.dispatchEvent(new CustomEvent('bioimageflow:root-workflow-open-started', {
    detail: { workflowName: 'analysis' },
  }))
}
function applyOpen() {
  window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', { detail: presentation() }))
}

describe('application shell startup ownership', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    startup.resolve.mockReset()
    window.localStorage.clear()
  })
  afterEach(() => {
    wrappers.splice(0).forEach(wrapper => wrapper.unmount())
    canvasSessionRegistry.dispose()
  })

  it('mounts startup normally when there is no accepted Open', async () => {
    startup.resolve.mockResolvedValueOnce(presentation())
    const { dock } = mountShell()
    await flushPromises()
    expect(dock.panels.has('workflow:analysis')).toBe(true)
    expect(dock.panels.has('canvas-loading')).toBe(false)
  })

  it('does not mount competing startup content while accepted Open is loading', async () => {
    const loading = deferred<RootWorkflowPresentation>()
    startup.resolve.mockReturnValueOnce(loading.promise)
    const { dock } = mountShell()
    acceptedOpen()
    loading.resolve(presentation())
    await flushPromises()
    expect(dock.panels.has('workflow:analysis')).toBe(false)
    expect(dock.panels.has('canvas-empty')).toBe(true)
    applyOpen()
    await flushPromises()
    expect(dock.panels.has('workflow:analysis')).toBe(true)
    expect(dock.addPanel.mock.calls.filter(([options]) => options.id === 'workflow:analysis')).toHaveLength(1)
  })

  it('does not reactivate a root after explicit Open and child/dock activation', async () => {
    const loading = deferred<RootWorkflowPresentation>()
    startup.resolve.mockReturnValueOnce(loading.promise)
    const { dock } = mountShell()
    acceptedOpen()
    applyOpen()
    const child = dock.api.addPanel({ id: 'nested-workflow:child', component: 'nestedWorkflowEditor' })
    const childId = canvasIdFromPanelId(child.id)
    canvasSessionRegistry.register({
      kind: 'nested', canvasId: childId, sessionId: 'child', parentCanvasId: canvasIdFromPanelId('workflow:analysis'),
    })
    child.api.setActive()
    useUIStore().setCanvasSelectedNodes(childId, ['nested_increment'])
    dock.api.getPanel('dataTable')!.api.setActive()
    loading.resolve(presentation())
    await flushPromises()
    expect(canvasSessionRegistry.activeCanvasId.value).toBe(childId)
    expect(useUIStore().selectedNodeIds).toEqual(['nested_increment'])
    expect(dock.active()?.id).toBe('dataTable')

    // A deliberate later Open retains its ordinary existing-root activation.
    acceptedOpen()
    applyOpen()
    await flushPromises()
    expect(canvasSessionRegistry.activeCanvasId.value).toBe('workflow:analysis')
  })

  it('leaves usable empty controls after accepted Open fails', async () => {
    const loading = deferred<RootWorkflowPresentation>()
    startup.resolve.mockReturnValueOnce(loading.promise)
    const { dock } = mountShell()
    acceptedOpen()
    loading.resolve(presentation())
    await flushPromises()
    expect(dock.panels.has('canvas-empty')).toBe(true)
    expect(dock.panels.has('workflows')).toBe(true)
  })

  it('never mounts a late startup response after unmount', async () => {
    const loading = deferred<RootWorkflowPresentation>()
    startup.resolve.mockReturnValueOnce(loading.promise)
    const { wrapper, dock } = mountShell()
    wrapper.unmount()
    const calls = dock.addPanel.mock.calls.length
    loading.resolve(presentation())
    await flushPromises()
    expect(dock.addPanel).toHaveBeenCalledTimes(calls)
    expect(dock.dispose).toHaveBeenCalled()
  })
})
