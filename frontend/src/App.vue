<script lang="ts">
import { defineComponent } from 'vue'
import ToolsPanel from './components/panels/ToolsPanel.vue'
import WorkflowsPanel from './components/panels/WorkflowsPanel.vue'
import CanvasView from './components/canvas/CanvasView.vue'
import NodePanel from './components/panels/NodePanel.vue'
import SettingsPanel from './components/panels/SettingsPanel.vue'
import LoggerPanel from './components/panels/LoggerPanel.vue'
import DataTablePanel from './components/panels/DataTablePanel.vue'
import CodeEditorPanel from './components/panels/CodeEditorPanel.vue'
import CodeEditorTab from './components/layout/CodeEditorTab.vue'
import OpenHandsAgentPanel from './components/panels/OpenHandsAgentPanel.vue'
import SubWorkflowEditorPanel from './components/panels/SubWorkflowEditorPanel.vue'

export default defineComponent({
  components: {
    tools: ToolsPanel,
    workflows: WorkflowsPanel,
    canvasView: CanvasView,
    nodePanel: NodePanel,
    logger: LoggerPanel,
    dataTable: DataTablePanel,
    codeEditor: CodeEditorPanel,
    codeEditorTab: CodeEditorTab,
    openHandsAgent: OpenHandsAgentPanel,
    subWorkflowEditor: SubWorkflowEditorPanel,
  },
})
</script>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, shallowRef, watchEffect } from 'vue'
import { DockviewVue, type DockviewReadyEvent, type DockviewApi } from 'dockview-vue'
import { themeDark, themeLight, type DockviewIDisposable, type IDockviewPanel } from 'dockview-core'
import MenuBar from './components/layout/MenuBar.vue'
import Toast from 'primevue/toast'
import ConfirmDialog from 'primevue/confirmdialog'
import DatasetBrowser from './components/panels/DatasetBrowser.vue'
import ExecutionBanner from './components/execution/ExecutionBanner.vue'
import { useUIStore } from './stores/ui'
import { useDatasetBrowserStore } from './stores/datasetBrowser'
import { useFileDrop } from './composables/useFileDrop'
import { useExecutionLock } from './composables/useExecutionLock'
import { useSettingsPanel } from './composables/useSettingsPanel'
import { isDesktop as isPywebview } from './utils/nativeDialogs'
import { useWebSocket } from './composables/useWebSocket'
import { useSubWorkflowSessionsStore } from './stores/subWorkflowSessions'
import { useWorkflowStore } from './stores/workflow'
import { useSettingsStore } from './stores/settings'
import type { GraphState, MissingTool, ValidationResult } from './api/types'

function isMac(): boolean {
  return typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform)
}

function onPreferencesShortcut(event: KeyboardEvent) {
  if (event.key !== ',') return
  // macOS: Cmd+, always (browser or pywebview).
  // Linux/Windows pywebview: Ctrl+, only.
  // Linux/Windows browser: never registered (the menu entry is the fallback —
  // some browsers reserve Ctrl+, for their own preferences).
  const fired =
    (isMac() && event.metaKey) || (!isMac() && isPywebview() && event.ctrlKey)
  if (!fired) return
  event.preventDefault()
  useSettingsPanel().open()
}

const shortcutEnabled = isMac() || isPywebview()

const uiStore = useUIStore()
const datasetBrowserStore = useDatasetBrowserStore()
const websocket = useWebSocket()
const subWorkflowSessionsStore = useSubWorkflowSessionsStore()
const workflowStore = useWorkflowStore()
const settingsStore = useSettingsStore()

// Initialize once at the root so uiStore.isExecutionLocked reflects
// executionStore.isRunning anywhere in the tree. The composable has a
// side-effectful watch; the return values are unused here.
useExecutionLock()

onMounted(() => {
  if (!settingsStore.isLoaded) {
    void settingsStore.fetchSettings()
  }
  websocket.connect()
  window.addEventListener('bif:open-code-editor-loading', onCodeEditorLoading as EventListener)
  window.addEventListener('bif:open-code-editor', onOpenCodeEditor as EventListener)
  window.addEventListener(
    'bif:open-code-editor-loading-finished',
    onCodeEditorLoadingFinished as EventListener,
  )
  window.addEventListener(
    'bioimageflow:sub-workflow-session-opened',
    onSubWorkflowSessionOpened as EventListener,
  )
  window.addEventListener(
    'bioimageflow:apply-graph',
    onApplyGraph as EventListener,
  )
  window.addEventListener(
    'bioimageflow:close-sub-workflow-session',
    onCloseSubWorkflowSession as EventListener,
  )
  window.addEventListener(
    'bioimageflow:canvas-context-updated',
    onCanvasContextUpdated as EventListener,
  )
  if (shortcutEnabled) {
    window.addEventListener('keydown', onPreferencesShortcut)
  }
})

onBeforeUnmount(() => {
  dockviewDisposables.splice(0).forEach((disposable) => disposable.dispose())
  websocket.disconnect()
  window.removeEventListener('bif:open-code-editor-loading', onCodeEditorLoading as EventListener)
  window.removeEventListener('bif:open-code-editor', onOpenCodeEditor as EventListener)
  window.removeEventListener(
    'bif:open-code-editor-loading-finished',
    onCodeEditorLoadingFinished as EventListener,
  )
  window.removeEventListener(
    'bioimageflow:sub-workflow-session-opened',
    onSubWorkflowSessionOpened as EventListener,
  )
  window.removeEventListener(
    'bioimageflow:apply-graph',
    onApplyGraph as EventListener,
  )
  window.removeEventListener(
    'bioimageflow:close-sub-workflow-session',
    onCloseSubWorkflowSession as EventListener,
  )
  window.removeEventListener(
    'bioimageflow:canvas-context-updated',
    onCanvasContextUpdated as EventListener,
  )
  if (shortcutEnabled) {
    window.removeEventListener('keydown', onPreferencesShortcut)
  }
})

// Server-side upload cap default (2 GB, matches backend default). Used for
// the client-side pre-upload size check in DatasetBrowser. The authoritative
// cap lives on the server — the component adds 10% headroom.
const DEFAULT_SERVER_CAP = 2 * 1024 ** 3

// Window-level file drop → Dataset Browser (browser mode) or direct Files
// node creation (desktop mode). The canvas listens for `bif:drop-paths` to
// actually add the node at the viewport center.
useFileDrop({
  onPaths: (paths) => {
    window.dispatchEvent(new CustomEvent('bif:drop-paths', { detail: paths }))
  },
})

// Sync document.title with uiStore.tabTitle
watchEffect(() => {
  document.title = uiStore.tabTitle
})

watchEffect(() => {
  const isDark = uiStore.isDarkTheme
  document.documentElement.classList.toggle('bif-dark-theme', isDark)
  document.documentElement.style.colorScheme = isDark ? 'dark' : 'light'
})

const dockviewApi = shallowRef<DockviewApi | null>(null)
const dockviewDisposables: DockviewIDisposable[] = []
const confirmedSubWorkflowPanelCloses = new Set<string>()
const canvasContexts = new Map<string, {
  workflowName: string
  workflowDisplayName: string
}>()
const dockviewTheme = computed(() => uiStore.isDarkTheme ? themeDark : themeLight)
const openHandsAgentHiddenByGate = ref(false)
const openHandsAgentEnabled = computed(() => (
  settingsStore.isDesktop
  || settingsStore.unsafeWebappFeaturesEnabled
))

// --- Dockview setup ---

const panelKeys = [
  'tools',
  'workflows',
  'nodePanel',
  'dataTable',
  'logger',
  'codeEditor',
  'openHandsAgent',
] as const
type DockPanelKey = typeof panelKeys[number]

function isDockPanelKey(id: string): id is DockPanelKey {
  return panelKeys.includes(id as DockPanelKey)
}

function subWorkflowPanelId(sessionId: string): string {
  return `sub-workflow:${encodeURIComponent(sessionId)}`
}

function workflowPanelId(workflowName: string): string {
  return `workflow:${encodeURIComponent(workflowName)}`
}

function workflowNameFromPanelId(panelId: string): string | null {
  if (!panelId.startsWith('workflow:')) return null
  return decodeURIComponent(panelId.slice('workflow:'.length))
}

function sessionIdFromSubWorkflowPanelId(panelId: string): string | null {
  if (!panelId.startsWith('sub-workflow:')) return null
  return decodeURIComponent(panelId.slice('sub-workflow:'.length))
}

function onDockviewReady(event: DockviewReadyEvent) {
  const api = event.api
  dockviewApi.value = api
  dockviewDisposables.push(
    api.onDidRemovePanel((panel: IDockviewPanel) => {
      if (isDockPanelKey(panel.id)) {
        const panelId = panel.id
        queueMicrotask(() => {
          if (!api.getPanel(panelId)) {
            uiStore.setPanelVisible(panelId, false)
          }
        })
        return
      }
      const sessionId = sessionIdFromSubWorkflowPanelId(panel.id)
      if (!sessionId) {
        return
      }
      if (confirmedSubWorkflowPanelCloses.delete(panel.id)) {
        subWorkflowSessionsStore.closeSession(sessionId)
        return
      }
      const session = subWorkflowSessionsStore.sessionById(sessionId)
      if (!session) return
      if (
        subWorkflowSessionsStore.isDirty(sessionId) &&
        !window.confirm(`Discard unsaved changes to sub-workflow '${session.parentNodeName}'?`)
      ) {
        queueMicrotask(() => openSubWorkflowPanel(sessionId))
        return
      }
      subWorkflowSessionsStore.closeSession(sessionId)
    }),
  )
  const activePanelChange = (api as unknown as {
    onDidActivePanelChange?: (listener: (event: { panel?: IDockviewPanel } | IDockviewPanel) => void) => DockviewIDisposable
  }).onDidActivePanelChange
  if (activePanelChange) {
    dockviewDisposables.push(
      activePanelChange((event) => {
        const panel = ((event as { panel?: IDockviewPanel }).panel ?? event) as
          | IDockviewPanel
          | undefined
        if (panel) activateWorkflowContextForPanel(panel)
      }),
    )
  }

  // Canvas first — it becomes the root group that others dock relative to
  api.addPanel({
    id: 'canvas',
    component: 'canvasView',
    title: 'Canvas',
  })

  api.addPanel({
    id: 'tools',
    component: 'tools',
    title: 'Tools',
    initialWidth: 320,
    position: { referencePanel: 'canvas', direction: 'left' },
  })

  api.addPanel({
    id: 'workflows',
    component: 'workflows',
    title: 'Workflows',
    position: { referencePanel: 'tools', direction: 'within' },
  })

  api.addPanel({
    id: 'nodePanel',
    component: 'nodePanel',
    title: 'Nodes',
    initialWidth: 320,
    position: { referencePanel: 'canvas', direction: 'right' },
  })

  const dataTablePanel = api.addPanel({
    id: 'dataTable',
    component: 'dataTable',
    title: 'Data Table',
    initialHeight: 250,
    position: { referencePanel: 'canvas', direction: 'below' },
  })

  api.addPanel({
    id: 'logger',
    component: 'logger',
    title: 'Logger',
    position: {
      referencePanel: 'dataTable',
      direction: 'within',
    },
  })
  dataTablePanel.api.setActive()

  if (openHandsAgentEnabled.value && uiStore.panels.openHandsAgent) {
    api.addPanel(getPanelAddOptions('openHandsAgent'))
  } else if (!openHandsAgentEnabled.value) {
    uiStore.setPanelVisible('openHandsAgent', false)
    openHandsAgentHiddenByGate.value = true
  }
}

function activateCodeEditorPanel() {
  queueMicrotask(() => {
    const panel = dockviewApi.value?.getPanel('codeEditor')
    panel?.api.setActive()
  })
}

function onCodeEditorLoading(event: CustomEvent<{ path?: string }>) {
  uiStore.setCodeEditorOpening(event.detail?.path ?? '')
  activateCodeEditorPanel()
}

function onOpenCodeEditor(event: CustomEvent<{ url: string; path: string }>) {
  uiStore.setCodeEditorTarget(event.detail.url, event.detail.path)
  activateCodeEditorPanel()
}

function onCodeEditorLoadingFinished(event: CustomEvent<{ path?: string }>) {
  uiStore.clearCodeEditorOpening(event.detail?.path)
}

function openSubWorkflowPanel(sessionId: string): void {
  const api = dockviewApi.value
  const session = subWorkflowSessionsStore.sessionById(sessionId)
  if (!api || !session) return
  const panelId = subWorkflowPanelId(sessionId)
  const existing = api.getPanel(panelId)
  if (existing) {
    existing.api.setActive()
    return
  }
  const canvasPanel = api.getPanel('canvas')
  const panel = api.addPanel({
    id: panelId,
    component: 'subWorkflowEditor',
    title: session.parentNodeName,
    params: { sessionId, panelId },
    position: canvasPanel
      ? { referencePanel: 'canvas', direction: 'within' }
      : { direction: 'below' },
  })
  panel.api.setActive()
  uiStore.setActiveWorkflow(session.parentNodeName)
}

function onSubWorkflowSessionOpened(event: CustomEvent<{ sessionId?: string }>) {
  const sessionId = event.detail?.sessionId
  if (!sessionId) return
  openSubWorkflowPanel(sessionId)
}

function onCloseSubWorkflowSession(event: CustomEvent<{
  sessionId?: string
  discardConfirmed?: boolean
}>) {
  const sessionId = event.detail?.sessionId
  if (!sessionId) return
  const panel = dockviewApi.value?.getPanel(subWorkflowPanelId(sessionId))
  if (!panel) {
    subWorkflowSessionsStore.closeSession(sessionId)
    return
  }
  if (event.detail?.discardConfirmed) {
    confirmedSubWorkflowPanelCloses.add(panel.id)
  }
  dockviewApi.value?.removePanel(panel)
}

function dockviewParams(panel: IDockviewPanel): Record<string, unknown> {
  const raw = (panel as unknown as { params?: unknown }).params
  if (!raw || typeof raw !== 'object') return {}
  const wrapped = (raw as { params?: unknown }).params
  return wrapped && typeof wrapped === 'object'
    ? wrapped as Record<string, unknown>
    : raw as Record<string, unknown>
}

function activateWorkflowContextForPanel(panel: IDockviewPanel): void {
  const workflowNameFromId = workflowNameFromPanelId(panel.id)
  const sessionId = sessionIdFromSubWorkflowPanelId(panel.id)
  if (sessionId) {
    uiStore.clearSelection()
    const session = subWorkflowSessionsStore.sessionById(sessionId)
    uiStore.setActiveWorkflow(session?.parentNodeName ?? null)
  } else if (workflowNameFromId) {
    uiStore.clearSelection()
    const params = dockviewParams(panel)
    const workflowName = typeof params.workflowName === 'string'
      ? params.workflowName
      : workflowNameFromId
    if (typeof workflowName === 'string') {
      workflowStore.activateWorkflow(workflowName)
    }
    const label = params.workflowDisplayName ?? workflowName
    if (typeof label === 'string') {
      uiStore.setActiveWorkflow(label)
    }
  } else if (panel.id === 'canvas') {
    uiStore.clearSelection()
    const context = canvasContexts.get(panel.id)
    if (context) {
      workflowStore.activateWorkflow(context.workflowName)
      uiStore.setActiveWorkflow(context.workflowDisplayName)
    } else {
      uiStore.setActiveWorkflow(workflowStore.current?.display_name ?? null)
    }
  } else {
    return
  }
  window.dispatchEvent(new CustomEvent('bioimageflow:canvas-tab-activated', {
    detail: { panelId: panel.id },
  }))
}

function onCanvasContextUpdated(event: CustomEvent<{
  panelId?: string
  workflowName?: string | null
  workflowDisplayName?: string | null
}>) {
  const detail = event.detail
  if (!detail?.panelId || !detail.workflowName) return
  canvasContexts.set(detail.panelId, {
    workflowName: detail.workflowName,
    workflowDisplayName: detail.workflowDisplayName ?? detail.workflowName,
  })
}

function openWorkflowCanvasPanel(detail: {
  graph: GraphState
  workflowName?: string
  workflowDisplayName?: string
  missingTools?: MissingTool[]
  dirty?: boolean
  pushUndo?: boolean
  draftRevision?: number
  validation?: ValidationResult | null
}): void {
  const api = dockviewApi.value
  if (!api || !detail.graph) return
  const workflowName = detail.workflowName ?? workflowStore.currentName ?? 'workflow'
  const workflowDisplayName =
    detail.workflowDisplayName
    ?? workflowStore.current?.display_name
    ?? workflowName
  const panelId = workflowPanelId(workflowName)
  const existing = api.getPanel(panelId)
  if (existing) {
    window.dispatchEvent(new CustomEvent('bioimageflow:replace-canvas-graph', {
      detail: {
        panelId,
        graph: detail.graph,
        missingTools: detail.missingTools ?? [],
        dirty: detail.dirty ?? false,
        pushUndo: detail.pushUndo ?? false,
        draftRevision: detail.draftRevision,
        validation: detail.validation,
      },
    }))
    existing.api.setActive()
    return
  }
  canvasContexts.set(panelId, { workflowName, workflowDisplayName })
  const canvasPanel = api.getPanel('canvas')
  const panel = api.addPanel({
    id: panelId,
    component: 'canvasView',
    title: workflowDisplayName,
    params: {
      panelId,
      workflowName,
      workflowDisplayName,
      graph: detail.graph,
      missingTools: detail.missingTools ?? [],
      dirty: detail.dirty ?? false,
      draftRevision: detail.draftRevision,
      validation: detail.validation,
    },
    position: canvasPanel
      ? { referencePanel: 'canvas', direction: 'within' }
      : { direction: 'below' },
  })
  panel.api.setActive()
  uiStore.setActiveWorkflow(workflowDisplayName)
}

function onApplyGraph(event: CustomEvent<{
  graph?: GraphState
  workflowName?: string
  workflowDisplayName?: string
  missingTools?: MissingTool[]
  dirty?: boolean
  pushUndo?: boolean
  draftRevision?: number
  validation?: ValidationResult | null
}>) {
  const detail = event.detail
  if (!detail?.graph) return
  openWorkflowCanvasPanel({
    graph: detail.graph,
    workflowName: detail.workflowName,
    workflowDisplayName: detail.workflowDisplayName,
    missingTools: detail.missingTools,
    dirty: detail.dirty,
    pushUndo: detail.pushUndo,
    draftRevision: detail.draftRevision,
    validation: detail.validation,
  })
}

// --- Panel visibility sync ---

watch(
  () => panelKeys.map((k) => uiStore.panels[k]),
  (newVals, oldVals) => {
    if (!dockviewApi.value) return
    const api = dockviewApi.value

    for (let i = 0; i < panelKeys.length; i++) {
      const key = panelKeys[i]
      const isVisible = newVals[i]
      const wasVisible = oldVals?.[i]

      if (isVisible === wasVisible) continue

      const panel = api.getPanel(key)
      if (isVisible && !panel) {
        api.addPanel(getPanelAddOptions(key))
      } else if (!isVisible && panel) {
        api.removePanel(panel)
      }
    }
  },
)

watch(
  openHandsAgentEnabled,
  (enabled) => {
    const panel = dockviewApi.value?.getPanel('openHandsAgent')
    if (!enabled) {
      openHandsAgentHiddenByGate.value = uiStore.panels.openHandsAgent || Boolean(panel)
      if (uiStore.panels.openHandsAgent) {
        uiStore.setPanelVisible('openHandsAgent', false)
      } else if (panel && dockviewApi.value) {
        dockviewApi.value.removePanel(panel)
      }
      return
    }
    if (openHandsAgentHiddenByGate.value) {
      openHandsAgentHiddenByGate.value = false
      uiStore.setPanelVisible('openHandsAgent', true)
    }
  },
  { immediate: true },
)

function getPanelAddOptions(key: string) {
  switch (key) {
    case 'tools':
      return { id: 'tools', component: 'tools', title: 'Tools', initialWidth: 320, position: { direction: 'left' as const } }
    case 'workflows': {
      const toolsPanel = dockviewApi.value?.getPanel('tools')
      if (toolsPanel) {
        return { id: 'workflows', component: 'workflows', title: 'Workflows', position: { referencePanel: 'tools' as const, direction: 'within' as const } }
      }
      return { id: 'workflows', component: 'workflows', title: 'Workflows', initialWidth: 320, position: { direction: 'left' as const } }
    }
    case 'nodePanel':
      return { id: 'nodePanel', component: 'nodePanel', title: 'Nodes', initialWidth: 320, position: { direction: 'right' as const } }
    case 'dataTable':
      return { id: 'dataTable', component: 'dataTable', title: 'Data Table', initialHeight: 250, position: { direction: 'below' as const } }
    case 'logger': {
      const dataTablePanel = dockviewApi.value?.getPanel('dataTable')
      if (dataTablePanel) {
        return { id: 'logger', component: 'logger', title: 'Logger', position: { referencePanel: 'dataTable' as const, direction: 'within' as const } }
      }
      return { id: 'logger', component: 'logger', title: 'Logger', initialHeight: 250, position: { direction: 'below' as const } }
    }
    case 'codeEditor': {
      const nodePanel = dockviewApi.value?.getPanel('nodePanel')
      if (nodePanel) {
        return {
          id: 'codeEditor',
          component: 'codeEditor',
          tabComponent: 'codeEditorTab',
          title: 'Code Editor',
          initialWidth: 520,
          position: { referencePanel: 'nodePanel' as const, direction: 'right' as const },
        }
      }
      const canvasPanel = dockviewApi.value?.getPanel('canvas')
      return {
        id: 'codeEditor',
        component: 'codeEditor',
        tabComponent: 'codeEditorTab',
        title: 'Code Editor',
        initialWidth: 520,
        position: canvasPanel
          ? { referencePanel: 'canvas' as const, direction: 'right' as const }
          : { direction: 'right' as const },
      }
    }
    case 'openHandsAgent': {
      const codeEditorPanel = dockviewApi.value?.getPanel('codeEditor')
      if (codeEditorPanel) {
        return {
          id: 'openHandsAgent',
          component: 'openHandsAgent',
          title: 'OpenHands Agent',
          initialWidth: 420,
          position: { referencePanel: 'codeEditor' as const, direction: 'within' as const },
        }
      }
      const canvasPanel = dockviewApi.value?.getPanel('canvas')
      return {
        id: 'openHandsAgent',
        component: 'openHandsAgent',
        title: 'OpenHands Agent',
        initialWidth: 420,
        position: canvasPanel
          ? { referencePanel: 'canvas' as const, direction: 'right' as const }
          : { direction: 'right' as const },
      }
    }
    default:
      throw new Error(`Unknown panel key: ${key}`)
  }
}

defineExpose({ dockviewApi })
</script>

<template>
  <div id="bioimageflow-app">
    <MenuBar />
    <ExecutionBanner />
    <div class="dockview-wrapper">
      <DockviewVue
        :theme="dockviewTheme"
        popout-url="/popout.html"
        @ready="onDockviewReady"
      />
    </div>
    <Toast position="bottom-right" />
    <ConfirmDialog />
    <SettingsPanel />
    <DatasetBrowser
      v-if="datasetBrowserStore.isOpen && datasetBrowserStore.options"
      :visible="datasetBrowserStore.isOpen"
      :parameter-name="datasetBrowserStore.options.parameterName"
      :mode="datasetBrowserStore.options.mode"
      :file-type-filter="datasetBrowserStore.options.fileTypeFilter"
      :initial-files="datasetBrowserStore.options.initialFiles"
      :server-cap="DEFAULT_SERVER_CAP"
      @select="datasetBrowserStore.onSelect"
      @close="datasetBrowserStore.onClose"
      @create-files-node="datasetBrowserStore.onCreateFilesNode"
      @update:visible="(v: boolean) => { if (!v) datasetBrowserStore.onClose() }"
    />
  </div>
</template>

<style>
html, body, #app, #bioimageflow-app {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  background: var(--bif-app-bg);
  color: var(--p-text-color);
}

:root {
  --bif-app-bg: var(--p-surface-50);
  --bif-surface: var(--p-surface-0);
  --bif-surface-muted: var(--p-surface-50);
  --bif-surface-hover: var(--p-surface-100);
  --bif-surface-active: var(--p-surface-200);
  --bif-border-muted: var(--p-surface-200);
  --bif-border-strong: var(--p-surface-300);
  --bif-text-strong: var(--p-surface-900);
  --bif-text-subtle: var(--p-surface-500);
  --bif-danger-surface: var(--p-red-50);
}

.bif-dark-theme {
  --bif-app-bg: var(--p-surface-950);
  --bif-surface: var(--p-surface-900);
  --bif-surface-muted: var(--p-surface-800);
  --bif-surface-hover: var(--p-surface-800);
  --bif-surface-active: var(--p-surface-700);
  --bif-border-muted: var(--p-surface-700);
  --bif-border-strong: var(--p-surface-600);
  --bif-text-strong: var(--p-text-color);
  --bif-text-subtle: var(--p-text-muted-color);
  --bif-danger-surface: color-mix(in srgb, var(--p-red-500) 12%, var(--bif-surface));
}

#bioimageflow-app {
  display: flex;
  flex-direction: column;
}

.dockview-wrapper {
  flex: 1;
  overflow: hidden;
  position: relative;
}

.dockview-wrapper > div {
  height: 100%;
}

.bif-dark-theme .vue-flow {
  background: var(--bif-app-bg);
}

.bif-dark-theme .vue-flow__background {
  color: var(--bif-border-muted);
}

.bif-dark-theme .vue-flow__controls {
  box-shadow: 0 0 0 1px var(--p-content-border-color);
}

.bif-dark-theme .vue-flow__controls-button {
  background: var(--bif-surface);
  border-color: var(--p-content-border-color);
  color: var(--p-text-color);
}

/* Preserve newlines in toast detail (used by the run-button validation
 * summary so errors appear as a bullet list). */
:global(.p-toast-detail) {
  white-space: pre-line;
}
</style>
