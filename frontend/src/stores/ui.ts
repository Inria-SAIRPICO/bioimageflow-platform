import { ref, reactive, computed } from 'vue'
import { defineStore } from 'pinia'

export type ThemePreference = 'light' | 'dark' | 'system'

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
  const selectedNodeIds = ref<string[]>([])
  const graphNodes = ref<any[]>([])
  const activeWorkflowName = ref<string | null>(null)
  const hasUnsavedChanges = ref(false)
  const isExecutionLocked = ref(false)
  const codeEditorUrl = ref<string | null>(null)
  const codeEditorPath = ref<string | null>(null)
  const codeEditorOpening = ref(false)
  const codeEditorOpeningPath = ref<string | null>(null)
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
    selectedNodeIds.value = ids
  }

  function clearSelection() {
    selectedNodeIds.value = []
  }

  function setGraphNodes(nodes: any[]) {
    graphNodes.value = nodes
  }

  function setActiveWorkflow(name: string | null) {
    activeWorkflowName.value = name
  }

  function markDirty() {
    hasUnsavedChanges.value = true
  }

  function markClean() {
    hasUnsavedChanges.value = false
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

  function setCodeEditorTarget(url: string, path: string) {
    codeEditorUrl.value = url
    codeEditorPath.value = path
    codeEditorOpening.value = false
    codeEditorOpeningPath.value = null
    panels.codeEditor = true
  }

  function setCodeEditorOpening(path: string) {
    codeEditorOpeningPath.value = path || null
    if (!codeEditorUrl.value && path) {
      codeEditorPath.value = path
    }
    codeEditorOpening.value = true
    panels.codeEditor = true
  }

  function clearCodeEditorOpening(path?: string) {
    if (path !== undefined && codeEditorOpeningPath.value !== (path || null)) return
    codeEditorOpening.value = false
    codeEditorOpeningPath.value = null
  }

  function setCodeEditorDetached(detached: boolean) {
    codeEditorDetached.value = detached
    panels.codeEditor = true
  }

  return {
    selectedNodeIds,
    graphNodes,
    activeWorkflowName,
    hasUnsavedChanges,
    isExecutionLocked,
    codeEditorUrl,
    codeEditorPath,
    codeEditorOpening,
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
    markDirty,
    markClean,
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
