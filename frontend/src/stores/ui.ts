import { ref, reactive, computed } from 'vue'
import { defineStore } from 'pinia'
import {
  canvasSessionRegistry,
  type CanvasId,
} from '@/sessions/canvasSessionRegistry'

export type ThemePreference = 'light' | 'dark' | 'system'

interface CanvasPresentationContext {
  selectedNodeIds: string[]
  graphNodes: any[]
  activeWorkflowId: string | null
  activeWorkflowName: string | null
  hasUnsavedChanges: boolean
}

function createPresentationContext(): CanvasPresentationContext {
  return {
    selectedNodeIds: [],
    graphNodes: [],
    activeWorkflowId: null,
    activeWorkflowName: null,
    hasUnsavedChanges: false,
  }
}

const THEME_STORAGE_KEY = 'bioimageflow.theme'

function isThemePreference(value: string | null): value is ThemePreference {
  return value === 'light' || value === 'dark' || value === 'system'
}

function readStoredThemePreference(): ThemePreference {
  if (typeof window === 'undefined') return 'system'
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
    return isThemePreference(stored) ? stored : 'system'
  } catch {
    return 'system'
  }
}

function writeStoredThemePreference(preference: ThemePreference): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, preference)
  } catch {
    // Ignore unavailable storage; the in-memory setting still applies.
  }
}

export const useUIStore = defineStore('ui', () => {
  const legacyPresentation = reactive(createPresentationContext())
  const canvasPresentations = reactive(
    new Map<CanvasId, CanvasPresentationContext>(),
  )
  const isExecutionLocked = ref(false)
  const codeEditorUrl = ref<string | null>(null)
  const codeEditorPath = ref<string | null>(null)
  const codeEditorProjectPath = ref<string | null>(null)
  const codeEditorOpening = ref(false)
  const codeEditorOpeningPath = ref<string | null>(null)
  const codeEditorOpeningRequestId = ref<number | null>(null)
  const codeEditorTargetRequestId = ref<number | null>(null)
  const codeEditorDetached = ref(false)
  const themePreference = ref<ThemePreference>(readStoredThemePreference())
  const systemPrefersDark = ref(false)

  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    systemPrefersDark.value = mediaQuery.matches
    const onSystemThemeChange = (event: MediaQueryListEvent) => {
      systemPrefersDark.value = event.matches
    }
    if (typeof mediaQuery.addEventListener === 'function') {
      mediaQuery.addEventListener('change', onSystemThemeChange)
    } else if (typeof mediaQuery.addListener === 'function') {
      mediaQuery.addListener(onSystemThemeChange)
    }
  }

  const panels = reactive({
    tools: true,
    workflows: true,
    nodePanel: true,
    dataTable: true,
    logger: true,
    codeEditor: false,
  })

  function activePresentation(): CanvasPresentationContext | null {
    const activeCanvasId = canvasSessionRegistry.activeCanvasId.value
    if (activeCanvasId !== null) {
      return canvasPresentations.get(activeCanvasId) ?? null
    }
    return canvasSessionRegistry.sessionCount.value === 0
      ? legacyPresentation
      : null
  }

  function writableActivePresentation(): CanvasPresentationContext | null {
    const activeCanvasId = canvasSessionRegistry.activeCanvasId.value
    if (activeCanvasId !== null) return canvasPresentation(activeCanvasId)
    return canvasSessionRegistry.sessionCount.value === 0
      ? legacyPresentation
      : null
  }

  function canvasPresentation(canvasId: CanvasId): CanvasPresentationContext {
    const existing = canvasPresentations.get(canvasId)
    if (existing) return existing
    const created = reactive(createPresentationContext()) as CanvasPresentationContext
    canvasPresentations.set(canvasId, created)
    return created
  }

  const selectedNodeIds = computed(() => activePresentation()?.selectedNodeIds ?? [])
  const graphNodes = computed(() => activePresentation()?.graphNodes ?? [])
  const activeWorkflowName = computed(
    () => activePresentation()?.activeWorkflowName ?? null,
  )
  const activeWorkflowId = computed(
    () => activePresentation()?.activeWorkflowId ?? null,
  )
  const hasUnsavedChanges = computed(
    () => activePresentation()?.hasUnsavedChanges ?? false,
  )
  const hasSelection = computed(() => selectedNodeIds.value.length > 0)
  const isSingleSelection = computed(() => selectedNodeIds.value.length === 1)
  const isMultiSelection = computed(() => selectedNodeIds.value.length > 1)
  const resolvedTheme = computed<'light' | 'dark'>(() => {
    if (themePreference.value !== 'system') return themePreference.value
    return systemPrefersDark.value ? 'dark' : 'light'
  })
  const isDarkTheme = computed(() => resolvedTheme.value === 'dark')

  const tabTitle = computed(() => {
    let title = 'BioImageFlow'
    if (activeWorkflowName.value) {
      title += ` \u2014 ${activeWorkflowName.value}`
    }
    if (hasUnsavedChanges.value) {
      title += ' *'
    }
    return title
  })

  function setSelectedNodes(ids: string[]) {
    const presentation = writableActivePresentation()
    if (presentation) presentation.selectedNodeIds = [...ids]
  }

  function clearSelection() {
    const presentation = writableActivePresentation()
    if (presentation) presentation.selectedNodeIds = []
  }

  function setGraphNodes(nodes: any[]) {
    const presentation = writableActivePresentation()
    if (presentation) presentation.graphNodes = nodes
  }

  function setActiveWorkflow(name: string | null) {
    const presentation = writableActivePresentation()
    if (presentation) presentation.activeWorkflowName = name
  }

  function setActiveWorkflowIdentity(
    workflowId: string | null,
    displayName: string | null,
  ) {
    const presentation = writableActivePresentation()
    if (!presentation) return
    presentation.activeWorkflowId = workflowId
    presentation.activeWorkflowName = displayName
  }

  function markDirty() {
    const presentation = writableActivePresentation()
    if (presentation) presentation.hasUnsavedChanges = true
  }

  function markClean() {
    const presentation = writableActivePresentation()
    if (presentation) presentation.hasUnsavedChanges = false
  }

  function setCanvasSelectedNodes(canvasId: CanvasId, ids: string[]) {
    canvasPresentation(canvasId).selectedNodeIds = [...ids]
  }

  function setCanvasGraphNodes(canvasId: CanvasId, nodes: any[]) {
    canvasPresentation(canvasId).graphNodes = nodes
  }

  function setCanvasWorkflow(
    canvasId: CanvasId,
    workflowId: string | null,
    displayName: string | null,
  ) {
    const presentation = canvasPresentation(canvasId)
    presentation.activeWorkflowId = workflowId
    presentation.activeWorkflowName = displayName
  }

  function canvasWorkflowId(canvasId: CanvasId): string | null {
    return canvasPresentations.get(canvasId)?.activeWorkflowId ?? null
  }

  function markCanvasDirty(canvasId: CanvasId) {
    canvasPresentation(canvasId).hasUnsavedChanges = true
  }

  function markCanvasClean(canvasId: CanvasId) {
    canvasPresentation(canvasId).hasUnsavedChanges = false
  }

  function canvasHasUnsavedChanges(canvasId: CanvasId): boolean {
    return canvasPresentations.get(canvasId)?.hasUnsavedChanges ?? false
  }

  function releaseCanvasPresentation(canvasId: CanvasId) {
    canvasPresentations.delete(canvasId)
  }

  function setExecutionLocked(locked: boolean) {
    isExecutionLocked.value = locked
  }

  function setThemePreference(preference: ThemePreference) {
    themePreference.value = preference
    writeStoredThemePreference(preference)
  }

  function togglePanel(panel: keyof typeof panels) {
    panels[panel] = !panels[panel]
  }

  function setPanelVisible(panel: keyof typeof panels, visible: boolean) {
    panels[panel] = visible
  }

  function setCodeEditorTarget(
    url: string,
    path: string,
    projectPath: string | null = null,
    requestId: number | null = null,
  ) {
    codeEditorUrl.value = url
    codeEditorPath.value = path
    codeEditorProjectPath.value = projectPath
    codeEditorTargetRequestId.value = requestId
    codeEditorOpening.value = false
    codeEditorOpeningPath.value = null
    codeEditorOpeningRequestId.value = null
    panels.codeEditor = true
  }

  function setCodeEditorOpening(path: string, requestId: number | null = null) {
    codeEditorOpeningPath.value = path || null
    codeEditorOpeningRequestId.value = requestId
    if (!codeEditorUrl.value && path) {
      codeEditorPath.value = path
    }
    codeEditorOpening.value = true
    panels.codeEditor = true
  }

  function clearCodeEditorOpening(path?: string, requestId?: number | null) {
    if (
      requestId !== undefined &&
      requestId !== null &&
      codeEditorOpeningRequestId.value !== null &&
      codeEditorOpeningRequestId.value !== requestId
    ) {
      return
    }
    if (path !== undefined && codeEditorOpeningPath.value !== (path || null)) return
    codeEditorOpening.value = false
    codeEditorOpeningPath.value = null
    codeEditorOpeningRequestId.value = null
  }

  function setCodeEditorDetached(detached: boolean) {
    codeEditorDetached.value = detached
    panels.codeEditor = true
  }

  return {
    selectedNodeIds,
    graphNodes,
    activeWorkflowName,
    activeWorkflowId,
    hasUnsavedChanges,
    isExecutionLocked,
    codeEditorUrl,
    codeEditorPath,
    codeEditorProjectPath,
    codeEditorOpening,
    codeEditorOpeningPath,
    codeEditorOpeningRequestId,
    codeEditorTargetRequestId,
    codeEditorDetached,
    themePreference,
    systemPrefersDark,
    panels,
    hasSelection,
    isSingleSelection,
    isMultiSelection,
    resolvedTheme,
    isDarkTheme,
    tabTitle,
    setSelectedNodes,
    clearSelection,
    setGraphNodes,
    setActiveWorkflow,
    setActiveWorkflowIdentity,
    markDirty,
    markClean,
    setCanvasSelectedNodes,
    setCanvasGraphNodes,
    setCanvasWorkflow,
    canvasWorkflowId,
    markCanvasDirty,
    markCanvasClean,
    canvasHasUnsavedChanges,
    releaseCanvasPresentation,
    setExecutionLocked,
    setThemePreference,
    togglePanel,
    setPanelVisible,
    setCodeEditorTarget,
    setCodeEditorOpening,
    clearCodeEditorOpening,
    setCodeEditorDetached,
  }
})
