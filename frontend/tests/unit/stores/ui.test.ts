import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUIStore } from '@/stores/ui'
import {
  canvasIdFromPanelId,
  type CanvasSessionDescriptor,
} from '@/sessions/canvasSessionRegistry'
import { graphSyncCanvasSessions } from '@/composables/useGraphSync'

function registerCanvas(descriptor: CanvasSessionDescriptor): void {
  graphSyncCanvasSessions.register(descriptor)
}

describe('UI store', () => {
  beforeEach(() => {
    graphSyncCanvasSessions.dispose()
    window.localStorage.clear()
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
    setActivePinia(createPinia())
  })

  afterEach(() => {
    graphSyncCanvasSessions.dispose()
  })

  it('starts with no selection', () => {
    const store = useUIStore()
    expect(store.selectedNodeIds).toEqual([])
    expect(store.hasSelection).toBe(false)
    expect(store.isSingleSelection).toBe(false)
    expect(store.isMultiSelection).toBe(false)
  })

  it('setSelectedNodes updates selection', () => {
    const store = useUIStore()
    store.setSelectedNodes(['n1', 'n2'])
    expect(store.hasSelection).toBe(true)
    expect(store.isMultiSelection).toBe(true)
    expect(store.isSingleSelection).toBe(false)
  })

  it('clearSelection clears all', () => {
    const store = useUIStore()
    store.setSelectedNodes(['n1'])
    store.clearSelection()
    expect(store.selectedNodeIds).toEqual([])
    expect(store.hasSelection).toBe(false)
  })

  it('single selection detected', () => {
    const store = useUIStore()
    store.setSelectedNodes(['n1'])
    expect(store.isSingleSelection).toBe(true)
    expect(store.isMultiSelection).toBe(false)
  })

  it('tracks active workflow name', () => {
    const store = useUIStore()
    expect(store.activeWorkflowName).toBeNull()
    store.setActiveWorkflow('My Pipeline')
    expect(store.activeWorkflowName).toBe('My Pipeline')
  })

  it('tracks unsaved changes', () => {
    const store = useUIStore()
    expect(store.hasUnsavedChanges).toBe(false)
    store.markDirty()
    expect(store.hasUnsavedChanges).toBe(true)
    store.markClean()
    expect(store.hasUnsavedChanges).toBe(false)
  })

  it('isolates presentation state for canvases with identical node ids', () => {
    const rootCanvasId = canvasIdFromPanelId('workflow:root')
    const nestedCanvasId = canvasIdFromPanelId('sub-workflow:nested')
    registerCanvas({
      kind: 'root',
      canvasId: rootCanvasId,
      workflowId: 'root',
    })
    registerCanvas({
      kind: 'nested',
      canvasId: nestedCanvasId,
      sessionId: 'nested',
      parentCanvasId: rootCanvasId,
    })
    const store = useUIStore()
    const rootNode = { id: 'shared', data: { name: 'Root node' } }
    const nestedNode = { id: 'shared', data: { name: 'Nested node' } }

    store.setCanvasSelectedNodes(rootCanvasId, ['shared'])
    store.setCanvasGraphNodes(rootCanvasId, [rootNode])
    store.setCanvasWorkflow(rootCanvasId, 'root', 'Root workflow')
    store.markCanvasDirty(rootCanvasId)
    store.setCanvasSelectedNodes(nestedCanvasId, ['shared'])
    store.setCanvasGraphNodes(nestedCanvasId, [nestedNode])
    store.setCanvasWorkflow(nestedCanvasId, 'root', 'Nested workflow')
    store.markCanvasClean(nestedCanvasId)

    graphSyncCanvasSessions.activate(rootCanvasId)
    expect(store.selectedNodeIds).toEqual(['shared'])
    expect(store.graphNodes).toEqual([rootNode])
    expect(store.activeWorkflowId).toBe('root')
    expect(store.hasUnsavedChanges).toBe(true)
    expect(store.tabTitle).toBe('BioImageFlow \u2014 Root workflow *')

    graphSyncCanvasSessions.activate(nestedCanvasId)
    expect(store.selectedNodeIds).toEqual(['shared'])
    expect(store.graphNodes).toEqual([nestedNode])
    expect(store.activeWorkflowId).toBe('root')
    expect(store.hasUnsavedChanges).toBe(false)
    expect(store.tabTitle).toBe('BioImageFlow \u2014 Nested workflow')
  })

  it('keeps inactive canvas updates out of the active presentation facade', () => {
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    registerCanvas({ kind: 'root', canvasId: canvasA, workflowId: 'a' })
    registerCanvas({ kind: 'root', canvasId: canvasB, workflowId: 'b' })
    const store = useUIStore()

    store.setCanvasSelectedNodes(canvasA, ['same-id'])
    store.setCanvasGraphNodes(canvasA, [{ id: 'same-id', data: { name: 'A' } }])
    store.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
    store.markCanvasClean(canvasA)
    graphSyncCanvasSessions.activate(canvasA)

    store.setCanvasSelectedNodes(canvasB, ['same-id'])
    store.setCanvasGraphNodes(canvasB, [{ id: 'same-id', data: { name: 'B' } }])
    store.setCanvasWorkflow(canvasB, 'b', 'Workflow B')
    store.markCanvasDirty(canvasB)

    expect(store.graphNodes[0]?.data.name).toBe('A')
    expect(store.activeWorkflowName).toBe('Workflow A')
    expect(store.activeWorkflowId).toBe('a')
    expect(store.hasUnsavedChanges).toBe(false)

    graphSyncCanvasSessions.activate(canvasB)
    expect(store.graphNodes[0]?.data.name).toBe('B')
    expect(store.activeWorkflowName).toBe('Workflow B')
    expect(store.activeWorkflowId).toBe('b')
    expect(store.hasUnsavedChanges).toBe(true)
  })

  it('does not fall back to legacy state when sessions exist without an active canvas', () => {
    const store = useUIStore()
    store.setSelectedNodes(['legacy'])
    store.setGraphNodes([{ id: 'legacy' }])
    store.setActiveWorkflow('Legacy workflow')
    store.markDirty()

    const canvasId = canvasIdFromPanelId('workflow:registered')
    registerCanvas({ kind: 'root', canvasId, workflowId: 'registered' })

    expect(store.selectedNodeIds).toEqual([])
    expect(store.graphNodes).toEqual([])
    expect(store.activeWorkflowName).toBeNull()
    expect(store.activeWorkflowId).toBeNull()
    expect(store.hasUnsavedChanges).toBe(false)
    expect(store.tabTitle).toBe('BioImageFlow')

    store.setSelectedNodes(['must-not-target-root'])
    graphSyncCanvasSessions.activate(canvasId)
    expect(store.selectedNodeIds).toEqual([])
  })

  it('keeps remaining canvas context after another canvas unregisters', () => {
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    registerCanvas({ kind: 'root', canvasId: canvasA, workflowId: 'a' })
    registerCanvas({ kind: 'root', canvasId: canvasB, workflowId: 'b' })
    const store = useUIStore()
    store.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
    store.setCanvasWorkflow(canvasB, 'b', 'Workflow B')
    store.setCanvasSelectedNodes(canvasB, ['b-node'])

    graphSyncCanvasSessions.activate(canvasA)
    graphSyncCanvasSessions.unregister(canvasA)
    expect(store.activeWorkflowName).toBeNull()
    expect(store.selectedNodeIds).toEqual([])

    graphSyncCanvasSessions.activate(canvasB)
    expect(store.activeWorkflowName).toBe('Workflow B')
    expect(store.activeWorkflowId).toBe('b')
    expect(store.selectedNodeIds).toEqual(['b-node'])
  })

  it('tracks execution lock state', () => {
    const store = useUIStore()
    expect(store.isExecutionLocked).toBe(false)
    store.setExecutionLocked(true)
    expect(store.isExecutionLocked).toBe(true)
  })

  it('tracks panel visibility with correct defaults', () => {
    const store = useUIStore()
    expect(store.panels.tools).toBe(true)
    expect(store.panels.nodePanel).toBe(true)
    expect(store.panels.dataTable).toBe(true)
    expect(store.panels.logger).toBe(true)
  })

  it('togglePanel flips visibility', () => {
    const store = useUIStore()
    store.togglePanel('tools')
    expect(store.panels.tools).toBe(false)
    store.togglePanel('tools')
    expect(store.panels.tools).toBe(true)
  })

  it('tab title with no workflow', () => {
    const store = useUIStore()
    expect(store.tabTitle).toBe('BioImageFlow')
  })

  it('tab title reflects workflow name', () => {
    const store = useUIStore()
    store.setActiveWorkflow('My Pipeline')
    expect(store.tabTitle).toBe('BioImageFlow \u2014 My Pipeline')
  })

  it('tab title shows asterisk for unsaved changes', () => {
    const store = useUIStore()
    store.setActiveWorkflow('My Pipeline')
    store.markDirty()
    expect(store.tabTitle).toBe('BioImageFlow \u2014 My Pipeline *')
  })

  it('tracks detached code editor state', () => {
    const store = useUIStore()
    expect(store.codeEditorDetached).toBe(false)

    store.setCodeEditorDetached(true)

    expect(store.codeEditorDetached).toBe(true)
    expect(store.panels.codeEditor).toBe(true)
  })

  it('defaults to the system theme preference', () => {
    const store = useUIStore()
    expect(store.themePreference).toBe('system')
    expect(store.resolvedTheme).toBe('light')
    expect(store.isDarkTheme).toBe(false)
  })

  it('persists an explicit dark theme preference', () => {
    const store = useUIStore()
    store.setThemePreference('dark')

    expect(store.themePreference).toBe('dark')
    expect(store.resolvedTheme).toBe('dark')
    expect(store.isDarkTheme).toBe(true)
    expect(window.localStorage.getItem('bioimageflow.theme')).toBe('dark')
  })

  it('resolves system preference to dark when the OS is dark', () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-color-scheme: dark)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))
    setActivePinia(createPinia())

    const store = useUIStore()

    expect(store.themePreference).toBe('system')
    expect(store.resolvedTheme).toBe('dark')
    expect(store.isDarkTheme).toBe(true)
  })
})
