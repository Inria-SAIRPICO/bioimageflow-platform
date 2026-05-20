import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUIStore } from '@/stores/ui'

describe('UI store', () => {
  beforeEach(() => {
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
