<script lang="ts">
import { defineComponent } from 'vue'
import ToolsPanel from './components/panels/ToolsPanel.vue'
import WorkflowsPanel from './components/panels/WorkflowsPanel.vue'
import DatasetsPanel from './components/panels/DatasetsPanel.vue'
import CanvasView from './components/canvas/CanvasView.vue'
import NodePanel from './components/panels/NodePanel.vue'
import SettingsPanel from './components/panels/SettingsPanel.vue'
import LoggerPanel from './components/panels/LoggerPanel.vue'
import DataTablePanel from './components/panels/DataTablePanel.vue'
import CodeEditorPanel from './components/panels/CodeEditorPanel.vue'
import CodeEditorTab from './components/layout/CodeEditorTab.vue'
import AvivatorPanel from './components/panels/AvivatorPanel.vue'
import AvivatorTab from './components/layout/AvivatorTab.vue'
import NestedWorkflowEditorPanel from './components/panels/NestedWorkflowEditorPanel.vue'
import CanvasTab from './components/layout/CanvasTab.vue'
import CanvasPlaceholder from './components/canvas/CanvasPlaceholder.vue'

export default defineComponent({
  components: {
    tools: ToolsPanel,
    workflows: WorkflowsPanel,
    datasets: DatasetsPanel,
    canvasView: CanvasView,
    nodePanel: NodePanel,
    logger: LoggerPanel,
    dataTable: DataTablePanel,
    codeEditor: CodeEditorPanel,
    codeEditorTab: CodeEditorTab,
    avivator: AvivatorPanel,
    avivatorTab: AvivatorTab,
    nestedWorkflowEditor: NestedWorkflowEditorPanel,
    canvasTab: CanvasTab,
    canvasPlaceholder: CanvasPlaceholder,
  },
})
</script>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, shallowRef, watchEffect } from 'vue'
import { DockviewVue, type DockviewReadyEvent, type DockviewApi } from 'dockview-vue'
import { themeDark, themeLight, type DockviewIDisposable, type IDockviewPanel } from 'dockview-core'
import MenuBar from './components/layout/MenuBar.vue'
import Toast from 'primevue/toast'
import ConfirmDialog from 'primevue/confirmdialog'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import ExecutionBanner from './components/execution/ExecutionBanner.vue'
import NapariProgressBanner from './components/execution/NapariProgressBanner.vue'
import EnvironmentRecoveryDialog from './components/execution/EnvironmentRecoveryDialog.vue'
import { useUIStore } from './stores/ui'
import { useDatasetsStore } from './stores/datasets'
import { useNapariStore } from './stores/napari'
import { useFileDrop } from './composables/useFileDrop'
import { useExecutionLock } from './composables/useExecutionLock'
import { useSettingsPanel } from './composables/useSettingsPanel'
import { isDesktop as isPywebview } from './utils/nativeDialogs'
import { useWebSocket } from './composables/useWebSocket'
import { useNestedWorkflowSessionsStore } from './stores/nestedWorkflowSessions'
import { useWorkflowStore } from './stores/workflow'
import { useCanvasLifecycleStore } from './stores/canvasLifecycle'
import type { GraphState, MissingTool } from './api/types'
import type { WorkflowDraftResponse } from './api/workflowDrafts'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
} from './sessions/canvasSessionRegistry'
import { useAutoSave } from './composables/useAutoSave'
import { resolveStartupWorkflow } from './services/startupWorkflow'
import {
  isRootWorkflowPresentationCurrent,
  loadRootWorkflowPresentation,
  workflowInfoId,
} from './services/rootWorkflowPresentation'
import { saveRootWorkflowTarget } from './services/rootWorkflowSave'
import {
  CanvasDiscardRecoveryCleanupError,
  getRootCanvasPersistenceResource,
} from './composables/useCanvasPersistence'
import {
  WorkflowDeletionCommittedCleanupError,
  WorkflowDeletionTargetChangedError,
  type WorkflowDeletionEventDetail,
  type WorkflowDeletionRequest,
} from './services/workflowDeletion'
import {
  CANVAS_EMPTY_PANEL_ID,
  CANVAS_LOADING_PANEL_ID,
  isCanvasPanelId,
  sessionIdFromNestedWorkflowPanelId,
  nestedWorkflowPanelId,
  workflowIdFromPanelId,
  workflowPanelId,
} from './utils/canvasPanels'
import {
  activateGraphSyncCanvas,
  deleteRetainedNestedSnapshot,
  forgetRetainedNestedSnapshot,
  flushRetainedNestedSnapshot,
  unregisterGraphSyncCanvas,
} from './composables/useGraphSync'

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
const datasetsStore = useDatasetsStore()
const napariStore = useNapariStore()
const websocket = useWebSocket()
const nestedWorkflowSessionsStore = useNestedWorkflowSessionsStore()
const workflowStore = useWorkflowStore()
const autoSave = useAutoSave()
const canvasLifecycleStore = useCanvasLifecycleStore()

interface PendingRootClose {
  panelId: string
  panel: IDockviewPanel
  canvasId: ReturnType<typeof canvasIdFromPanelId>
  workflowName: string
}

const rootCloseDialogVisible = ref(false)
const pendingRootClose = shallowRef<PendingRootClose | null>(null)
const rootCloseError = ref<string | null>(null)
const rootCloseBusy = ref(false)

// Initialize once at the root so uiStore.isExecutionLocked reflects
// executionStore.isMutationLocked anywhere in the tree. The composable has a
// side-effectful watch; the return values are unused here.
useExecutionLock()

onMounted(() => {
  websocket.connect()
  window.addEventListener('bif:open-code-editor-loading', onCodeEditorLoading as EventListener)
  window.addEventListener('bif:open-code-editor', onOpenCodeEditor as EventListener)
  window.addEventListener(
    'bif:open-code-editor-loading-finished',
    onCodeEditorLoadingFinished as EventListener,
  )
  window.addEventListener('bioimageflow:open-avivator', onOpenAvivator as EventListener)
  window.addEventListener(
    'bioimageflow:nested-workflow-session-opened',
    onNestedWorkflowSessionOpened as EventListener,
  )
  window.addEventListener(
    'bioimageflow:apply-graph',
    onApplyGraph as EventListener,
  )
  window.addEventListener(
    'bioimageflow:close-nested-workflow-session',
    onCloseNestedWorkflowSession as EventListener,
  )
  window.addEventListener(
    'bioimageflow:canvas-context-updated',
    onCanvasContextUpdated as EventListener,
  )
  window.addEventListener(
    'bioimageflow:request-close-canvas',
    onRequestCloseCanvas as EventListener,
  )
  window.addEventListener(
    'bioimageflow:request-delete-workflow',
    onRequestDeleteWorkflow as EventListener,
  )
  window.addEventListener('bioimageflow:workflow-removed', onWorkflowRemoved as EventListener)
  window.addEventListener(
    'bioimageflow:workflow-identities-refreshed',
    onWorkflowIdentitiesRefreshed as EventListener,
  )
  if (shortcutEnabled) {
    window.addEventListener('keydown', onPreferencesShortcut)
  }
})

onBeforeUnmount(() => {
  isUnmounting = true
  canvasActivationRequest += 1
  rootOpenRequest += 1
  dockviewDisposables.splice(0).forEach((disposable) => disposable.dispose())
  websocket.disconnect()
  window.removeEventListener('bif:open-code-editor-loading', onCodeEditorLoading as EventListener)
  window.removeEventListener('bif:open-code-editor', onOpenCodeEditor as EventListener)
  window.removeEventListener(
    'bif:open-code-editor-loading-finished',
    onCodeEditorLoadingFinished as EventListener,
  )
  window.removeEventListener('bioimageflow:open-avivator', onOpenAvivator as EventListener)
  window.removeEventListener(
    'bioimageflow:nested-workflow-session-opened',
    onNestedWorkflowSessionOpened as EventListener,
  )
  window.removeEventListener(
    'bioimageflow:apply-graph',
    onApplyGraph as EventListener,
  )
  window.removeEventListener(
    'bioimageflow:close-nested-workflow-session',
    onCloseNestedWorkflowSession as EventListener,
  )
  window.removeEventListener(
    'bioimageflow:canvas-context-updated',
    onCanvasContextUpdated as EventListener,
  )
  window.removeEventListener(
    'bioimageflow:request-close-canvas',
    onRequestCloseCanvas as EventListener,
  )
  window.removeEventListener(
    'bioimageflow:request-delete-workflow',
    onRequestDeleteWorkflow as EventListener,
  )
  window.removeEventListener('bioimageflow:workflow-removed', onWorkflowRemoved as EventListener)
  window.removeEventListener(
    'bioimageflow:workflow-identities-refreshed',
    onWorkflowIdentitiesRefreshed as EventListener,
  )
  if (shortcutEnabled) {
    window.removeEventListener('keydown', onPreferencesShortcut)
  }
})

// Window-level regular-file drops become managed datasets, including on desktop.
useFileDrop()

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
watch(
  () => datasetsStore.activationRequest,
  () => {
    uiStore.panels.datasets = true
    nextTick(() => dockviewApi.value?.getPanel('datasets')?.api.setActive())
  },
)
watch(
  () => napariStore.loggerActivationRequest,
  () => {
    uiStore.panels.logger = true
    nextTick(() => dockviewApi.value?.getPanel('logger')?.api.setActive())
  },
)
const dockviewDisposables: DockviewIDisposable[] = []
const confirmedNestedWorkflowPanelCloses = new Set<string>()
const removedWorkflowNestedWorkflowCloses = new Set<string>()
const nestedWorkflowParentCanvasIds = new Map<string, string>()
const openCanvasPanelIds = new Set<string>()
const rootPanelActivationOrder: string[] = []
let canvasActivationRequest = 0
let rootOpenRequest = 0
let startupResolved = false
let isUnmounting = false
let activeCanvasPanelId: string | null = null
let canvasFallbackPending = false
let canvasGenerationReplacementCount = 0
const workflowDeletionsInFlight = new Set<string>()
const workflowGenerationReplacements = new Map<string, Promise<void>>()
const deferredWorkflowGenerationReplacements = new Map<string, number>()
const canvasContexts = new Map<string, {
  workflowName: string
  workflowDisplayName: string
  serverIdentityGeneration: number | null
}>()
const dockviewTheme = computed(() => uiStore.isDarkTheme ? themeDark : themeLight)

// --- Dockview setup ---

const panelKeys = ['tools', 'workflows', 'datasets', 'nodePanel', 'dataTable', 'logger', 'codeEditor'] as const
type DockPanelKey = typeof panelKeys[number]

function isDockPanelKey(id: string): id is DockPanelKey {
  return panelKeys.includes(id as DockPanelKey)
}

function rememberRootActivation(panelId: string): void {
  const index = rootPanelActivationOrder.indexOf(panelId)
  if (index !== -1) rootPanelActivationOrder.splice(index, 1)
  rootPanelActivationOrder.push(panelId)
}

function openCanvasPanel(api: DockviewApi): IDockviewPanel | null {
  for (const panelId of openCanvasPanelIds) {
    const panel = api.getPanel(panelId)
    if (panel) return panel
    openCanvasPanelIds.delete(panelId)
  }
  return null
}

function openRootPanel(api: DockviewApi): IDockviewPanel | null {
  for (let index = rootPanelActivationOrder.length - 1; index >= 0; index -= 1) {
    const panelId = rootPanelActivationOrder[index]
    const panel = api.getPanel(panelId)
    if (panel && workflowIdFromPanelId(panel.id) !== null) return panel
    rootPanelActivationOrder.splice(index, 1)
  }
  for (const panelId of openCanvasPanelIds) {
    if (workflowIdFromPanelId(panelId) === null) continue
    const panel = api.getPanel(panelId)
    if (panel) return panel
    openCanvasPanelIds.delete(panelId)
  }
  return null
}

function layoutAnchorPanel(api: DockviewApi): IDockviewPanel | null {
  return openRootPanel(api)
    ?? api.getPanel(CANVAS_EMPTY_PANEL_ID)
    ?? api.getPanel(CANVAS_LOADING_PANEL_ID)
    ?? openCanvasPanel(api)
}

function removeCanvasPlaceholder(api: DockviewApi): void {
  for (const panelId of [CANVAS_LOADING_PANEL_ID, CANVAS_EMPTY_PANEL_ID]) {
    const panel = api.getPanel(panelId)
    if (panel) api.removePanel(panel)
  }
}

function showEmptyCanvasState(api: DockviewApi): IDockviewPanel | null {
  const existingRoot = openRootPanel(api)
  if (existingRoot) return existingRoot
  const existing = api.getPanel(CANVAS_EMPTY_PANEL_ID)
  if (existing) return existing
  const loading = api.getPanel(CANVAS_LOADING_PANEL_ID)
  const bottomPanel = api.getPanel('dataTable') ?? api.getPanel('logger')
  const panel = api.addPanel({
    id: CANVAS_EMPTY_PANEL_ID,
    component: 'canvasPlaceholder',
    title: 'Workflows',
    params: { state: 'empty' },
    position: loading
      ? { referencePanel: loading.id, direction: 'within' }
      : bottomPanel
        ? { referencePanel: bottomPanel.id, direction: 'above' }
        : { direction: 'below' },
  })
  if (loading) api.removePanel(loading)
  panel.api.setActive()
  return panel
}

function ensureCanvasStateAfterRemoval(api: DockviewApi): void {
  queueMicrotask(() => {
    if (
      isUnmounting
      || canvasFallbackPending
      || canvasGenerationReplacementCount > 0
      || !startupResolved
      || openRootPanel(api)
    ) return
    showEmptyCanvasState(api)
  })
}

function requestGraphSyncActivation(panelId: string): void {
  const request = ++canvasActivationRequest
  const canvasId = canvasIdFromPanelId(panelId)
  if (activateGraphSyncCanvas(canvasId)) return
  void nextTick().then(() => {
    if (request === canvasActivationRequest) {
      activateGraphSyncCanvas(canvasId)
    }
  })
}

async function resolveAndOpenStartupWorkflow(api: DockviewApi): Promise<void> {
  const request = rootOpenRequest
  let startup: Awaited<ReturnType<typeof resolveStartupWorkflow>> = null
  try {
    startup = await resolveStartupWorkflow()
  } catch (error) {
    console.warn('[startup] Failed to resolve a workflow:', error)
  }
  startupResolved = true
  if (isUnmounting || dockviewApi.value !== api) return
  if (request !== rootOpenRequest || openRootPanel(api)) {
    const loading = api.getPanel(CANVAS_LOADING_PANEL_ID)
    if (loading) api.removePanel(loading)
    if (!openRootPanel(api)) showEmptyCanvasState(api)
    return
  }
  if (startup && openWorkflowCanvasPanel(startup)) return
  showEmptyCanvasState(api)
}

function onDockviewReady(event: DockviewReadyEvent) {
  const api = event.api
  dockviewApi.value = api
  dockviewDisposables.push(
    api.onDidRemovePanel((panel: IDockviewPanel) => {
      if (isCanvasPanelId(panel.id)) {
        const canvasId = canvasIdFromPanelId(panel.id)
        openCanvasPanelIds.delete(panel.id)
        const activationIndex = rootPanelActivationOrder.indexOf(panel.id)
        if (activationIndex !== -1) rootPanelActivationOrder.splice(activationIndex, 1)
        if (activeCanvasPanelId === panel.id) activeCanvasPanelId = null
        canvasContexts.delete(panel.id)
        unregisterGraphSyncCanvas(canvasId)
        canvasLifecycleStore.finish(canvasId)
        uiStore.releaseCanvasPresentation(canvasId)
        if (workflowIdFromPanelId(panel.id) !== null) {
          ensureCanvasStateAfterRemoval(api)
        }
      }
      if (isDockPanelKey(panel.id)) {
        const panelId = panel.id
        queueMicrotask(() => {
          if (!api.getPanel(panelId)) {
            uiStore.setPanelVisible(panelId, false)
          }
        })
        return
      }
      const sessionId = sessionIdFromNestedWorkflowPanelId(panel.id)
      if (!sessionId) {
        return
      }
      if (removedWorkflowNestedWorkflowCloses.delete(panel.id)) {
        nestedWorkflowSessionsStore.closeSession(sessionId)
        nestedWorkflowParentCanvasIds.delete(sessionId)
        return
      }
      if (confirmedNestedWorkflowPanelCloses.delete(panel.id)) {
        void finalizeNestedWorkflowClose(sessionId)
        return
      }
      const session = nestedWorkflowSessionsStore.sessionById(sessionId)
      if (!session) return
      if (
        nestedWorkflowSessionsStore.isDirty(sessionId) &&
        !window.confirm(`Discard unsaved changes to nested-workflow '${session.parentNodeName}'?`)
      ) {
        queueMicrotask(() => openNestedWorkflowPanel(sessionId))
        return
      }
      void finalizeNestedWorkflowClose(sessionId)
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

  // A non-session placeholder establishes the initial layout while startup
  // resolves. It is replaced by a canonical workflow:<id> panel or the
  // explicit empty state; it never becomes a canvas identity.
  api.addPanel({
    id: CANVAS_LOADING_PANEL_ID,
    component: 'canvasPlaceholder',
    title: 'Loading…',
    params: { state: 'loading' },
  })

  api.addPanel({
    id: 'tools',
    component: 'tools',
    title: 'Tools',
    initialWidth: 320,
    position: { referencePanel: CANVAS_LOADING_PANEL_ID, direction: 'left' },
  })

  api.addPanel({
    id: 'workflows',
    component: 'workflows',
    title: 'Workflows',
    position: { referencePanel: 'tools', direction: 'within' },
  })

  api.addPanel({
    id: 'datasets',
    component: 'datasets',
    title: 'Datasets',
    position: { referencePanel: 'tools', direction: 'within' },
  })

  api.addPanel({
    id: 'nodePanel',
    component: 'nodePanel',
    title: 'Nodes',
    initialWidth: 320,
    position: { referencePanel: CANVAS_LOADING_PANEL_ID, direction: 'right' },
  })

  const dataTablePanel = api.addPanel({
    id: 'dataTable',
    component: 'dataTable',
    title: 'Data Table',
    initialHeight: 250,
    position: { referencePanel: CANVAS_LOADING_PANEL_ID, direction: 'below' },
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
  void resolveAndOpenStartupWorkflow(api)
}

function activateCodeEditorPanel() {
  queueMicrotask(() => {
    const panel = dockviewApi.value?.getPanel('codeEditor')
    panel?.api.setActive()
  })
}

function onCodeEditorLoading(event: CustomEvent<{ path?: string, requestId?: number }>) {
  const existingPanel = dockviewApi.value?.getPanel('codeEditor')
  uiStore.setCodeEditorOpening(event.detail?.path ?? '', event.detail?.requestId ?? null)
  if (!existingPanel) {
    activateCodeEditorPanel()
  }
}

function onOpenCodeEditor(event: CustomEvent<{
  url: string
  path: string
  projectPath?: string | null
  requestId?: number
}>) {
  const existingPanel = dockviewApi.value?.getPanel('codeEditor')
  const urlChanged = uiStore.codeEditorUrl !== event.detail.url
  uiStore.setCodeEditorTarget(
    event.detail.url,
    event.detail.path,
    event.detail.projectPath ?? null,
    event.detail.requestId ?? null,
  )
  if (!existingPanel || urlChanged) {
    activateCodeEditorPanel()
  }
}

function onCodeEditorLoadingFinished(event: CustomEvent<{ path?: string, requestId?: number }>) {
  uiStore.clearCodeEditorOpening(event.detail?.path, event.detail?.requestId ?? null)
}

function onOpenAvivator(event: CustomEvent<{
  url?: string
  imageUrl?: string
  title?: string
}>) {
  const api = dockviewApi.value
  const url = event.detail?.url
  if (!api || !url) return

  const existing = api.getPanel('avivator')
  if (existing) {
    api.removePanel(existing)
  }
  const dataTablePanel = api.getPanel('dataTable')
  const canvasPanel = layoutAnchorPanel(api)
  const imageTitle = event.detail?.title?.trim() || 'Image'
  const panel = api.addPanel({
    id: 'avivator',
    component: 'avivator',
    tabComponent: 'avivatorTab',
    title: `Avivator - ${imageTitle}`,
    params: {
      url,
      imageUrl: event.detail?.imageUrl,
      title: imageTitle,
    },
    initialHeight: 360,
    position: dataTablePanel
      ? { referencePanel: 'dataTable', direction: 'within' }
      : canvasPanel
        ? { referencePanel: canvasPanel.id, direction: 'below' }
        : { direction: 'below' },
  })
  panel.api.setActive()
}

function openNestedWorkflowPanel(sessionId: string): void {
  const api = dockviewApi.value
  const session = nestedWorkflowSessionsStore.sessionById(sessionId)
  if (!api || !session) return
  const panelId = nestedWorkflowPanelId(sessionId)
  const existing = api.getPanel(panelId)
  if (existing) {
    existing.api.setActive()
    return
  }
  const ownerPanelId = nestedWorkflowParentCanvasIds.get(sessionId)
  const canvasPanel = ownerPanelId
    ? api.getPanel(ownerPanelId) ?? layoutAnchorPanel(api)
    : layoutAnchorPanel(api)
  uiStore.setCanvasWorkflow(
    canvasIdFromPanelId(panelId),
    session.parentWorkflowName,
    session.parentNodeName,
  )
  const panel = api.addPanel({
    id: panelId,
    component: 'nestedWorkflowEditor',
    title: session.parentNodeName,
    params: {
      sessionId,
      panelId,
      parentCanvasPanelId: ownerPanelId ?? canvasPanel?.id,
    },
    position: canvasPanel
      ? { referencePanel: canvasPanel.id, direction: 'within' }
      : { direction: 'below' },
  })
  openCanvasPanelIds.add(panel.id)
  panel.api.setActive()
}

function onNestedWorkflowSessionOpened(event: CustomEvent<{
  sessionId?: string
  parentCanvasPanelId?: string
}>) {
  const sessionId = event.detail?.sessionId
  if (!sessionId) return
  if (event.detail.parentCanvasPanelId) {
    nestedWorkflowParentCanvasIds.set(sessionId, event.detail.parentCanvasPanelId)
  }
  openNestedWorkflowPanel(sessionId)
}

async function finalizeNestedWorkflowClose(sessionId: string): Promise<void> {
  try {
    const deletedRetainedSnapshot = await deleteRetainedNestedSnapshot(sessionId)
    if (!deletedRetainedSnapshot) {
      await nestedWorkflowSessionsStore.deleteDurableSession(sessionId)
    }
    nestedWorkflowSessionsStore.closeSession(sessionId)
    nestedWorkflowParentCanvasIds.delete(sessionId)
  } catch (error) {
    console.warn('[nested-snapshot] failed to discard snapshot:', error)
    queueMicrotask(() => openNestedWorkflowPanel(sessionId))
  }
}

function onCloseNestedWorkflowSession(event: CustomEvent<{
  sessionId?: string
  discardConfirmed?: boolean
}>) {
  const sessionId = event.detail?.sessionId
  if (!sessionId) return
  const panel = dockviewApi.value?.getPanel(nestedWorkflowPanelId(sessionId))
  if (!panel) {
    void finalizeNestedWorkflowClose(sessionId)
    return
  }
  if (event.detail?.discardConfirmed) {
    confirmedNestedWorkflowPanelCloses.add(panel.id)
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
  const canvasId = canvasIdFromPanelId(panel.id)
  const workflowNameFromId = workflowIdFromPanelId(panel.id)
  const sessionId = sessionIdFromNestedWorkflowPanelId(panel.id)
  if (sessionId) {
    const session = nestedWorkflowSessionsStore.sessionById(sessionId)
    if (session?.parentWorkflowName) {
      workflowStore.activateWorkflow(session.parentWorkflowName, canvasId)
    }
    uiStore.setCanvasWorkflow(
      canvasId,
      session?.parentWorkflowName ?? null,
      session?.parentNodeName ?? null,
    )
  } else if (workflowNameFromId) {
    rememberRootActivation(panel.id)
    const params = dockviewParams(panel)
    const workflowName = workflowNameFromId
    workflowStore.activateWorkflow(workflowName, canvasId)
    const label = canvasContexts.get(panel.id)?.workflowDisplayName
      ?? params.workflowDisplayName
      ?? workflowName
    if (typeof label === 'string') {
      uiStore.setCanvasWorkflow(canvasId, workflowName, label)
    }
  } else {
    return
  }
  activeCanvasPanelId = panel.id
  requestGraphSyncActivation(panel.id)
  window.dispatchEvent(new CustomEvent('bioimageflow:canvas-tab-activated', {
    detail: { panelId: panel.id },
  }))
  if (workflowNameFromId) {
    void autoSave.setLastOpenedWorkflow(workflowNameFromId)
  }
}

function onCanvasContextUpdated(event: CustomEvent<{
  panelId?: string
  workflowName?: string | null
  workflowDisplayName?: string | null
}>) {
  const detail = event.detail
  if (!detail?.panelId || !detail.workflowName) return
  const canonicalWorkflowName = workflowIdFromPanelId(detail.panelId)
  if (
    canonicalWorkflowName !== null
    && canonicalWorkflowName !== detail.workflowName
  ) return
  const title = detail.workflowDisplayName ?? detail.workflowName
  canvasContexts.set(detail.panelId, {
    workflowName: detail.workflowName,
    workflowDisplayName: title,
    serverIdentityGeneration:
      canvasContexts.get(detail.panelId)?.serverIdentityGeneration ?? null,
  })
  uiStore.setCanvasWorkflow(
    canvasIdFromPanelId(detail.panelId),
    detail.workflowName,
    title,
  )
  dockviewApi.value?.getPanel(detail.panelId)?.api.setTitle(title)
  if (
    workflowIdFromPanelId(detail.panelId) !== null
    && activeCanvasPanelId === detail.panelId
  ) {
    rememberRootActivation(detail.panelId)
    void autoSave.setLastOpenedWorkflow(detail.workflowName)
  }
}

function resetRootCloseDialog(): void {
  if (rootCloseBusy.value) return
  rootCloseDialogVisible.value = false
  pendingRootClose.value = null
  rootCloseError.value = null
}

function onRequestCloseCanvas(event: CustomEvent<{ canvasId?: string }>): void {
  const panelId = event.detail?.canvasId
  const workflowName = panelId ? workflowIdFromPanelId(panelId) : null
  const api = dockviewApi.value
  const panel = panelId ? api?.getPanel(panelId) : undefined
  if (!panelId || !workflowName || !panel) return
  const canvasId = canvasIdFromPanelId(panelId)
  if (canvasLifecycleStore.isBusy(canvasId)) return
  if (!uiStore.canvasHasUnsavedChanges(canvasId)) {
    api?.removePanel(panel)
    return
  }
  pendingRootClose.value = { panelId, panel, canvasId, workflowName }
  rootCloseError.value = null
  rootCloseDialogVisible.value = true
}

function rootCloseTargetIsMounted(target: PendingRootClose): boolean {
  return dockviewApi.value?.getPanel(target.panelId) === target.panel
    && workflowIdFromPanelId(target.panelId) === target.workflowName
}

function closeRootTarget(target: PendingRootClose): void {
  const api = dockviewApi.value
  const panel = api?.getPanel(target.panelId)
  if (panel) api?.removePanel(panel)
  rootCloseBusy.value = false
  canvasLifecycleStore.finish(target.canvasId)
  resetRootCloseDialog()
}

async function saveAndCloseRootCanvas(): Promise<void> {
  const target = pendingRootClose.value
  if (!target || rootCloseBusy.value) return
  if (!canvasLifecycleStore.begin(target.canvasId, 'saving')) return
  rootCloseBusy.value = true
  rootCloseError.value = null
  try {
    const result = await saveRootWorkflowTarget({
      canvasId: target.canvasId,
      workflowName: target.workflowName,
    })
    if (!rootCloseTargetIsMounted(target)) return
    if (result.status === 'saved') {
      closeRootTarget(target)
      return
    }
    rootCloseError.value = result.status === 'newer-edit'
      ? 'The workflow changed while it was being saved. Review the newer edit and close again.'
      : result.status === 'conflict'
        ? 'This workflow changed elsewhere. Resolve the draft conflict before closing.'
        : 'The workflow is no longer available at its original identity.'
  } catch (error) {
    rootCloseError.value = error instanceof Error ? error.message : String(error)
  } finally {
    if (rootCloseBusy.value) {
      rootCloseBusy.value = false
      canvasLifecycleStore.finish(target.canvasId)
    }
  }
}

async function restoreSavedCanvas(
  target: PendingRootClose,
  draft: WorkflowDraftResponse,
): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const detail = {
      canvasId: target.canvasId,
      draft,
      handled: false,
      resolve,
      reject,
    }
    window.dispatchEvent(new CustomEvent('bioimageflow:restore-saved-canvas', { detail }))
    if (!detail.handled) resolve()
  })
}

async function discardAndCloseRootCanvas(): Promise<void> {
  const target = pendingRootClose.value
  if (!target || rootCloseBusy.value) return
  if (!canvasLifecycleStore.begin(target.canvasId, 'discarding')) return
  rootCloseBusy.value = true
  rootCloseError.value = null
  try {
    const persistence = getRootCanvasPersistenceResource(target.canvasId)
    if (!persistence || persistence.workflowId.value !== target.workflowName) {
      throw new Error('The workflow is no longer available at its original identity.')
    }
    const draft = await persistence.discardToSaved()
    if (!rootCloseTargetIsMounted(target)) return
    await restoreSavedCanvas(target, draft)
    if (!rootCloseTargetIsMounted(target)) return
    uiStore.markCanvasClean(target.canvasId)
    closeRootTarget(target)
  } catch (error) {
    if (
      error instanceof CanvasDiscardRecoveryCleanupError
      && rootCloseTargetIsMounted(target)
    ) {
      try {
        await restoreSavedCanvas(target, error.draft)
        if (rootCloseTargetIsMounted(target)) {
          // Keep the close decision actionable: retrying Discard uses the
          // newly accepted revision and retries the strict recovery clear.
          uiStore.markCanvasDirty(target.canvasId)
        }
      } catch (restoreError) {
        rootCloseError.value = restoreError instanceof Error
          ? restoreError.message
          : String(restoreError)
        return
      }
    }
    rootCloseError.value = error instanceof Error ? error.message : String(error)
  } finally {
    if (rootCloseBusy.value) {
      rootCloseBusy.value = false
      canvasLifecycleStore.finish(target.canvasId)
    }
  }
}

function closeNestedCanvasesForWorkflow(workflowName: string): void {
  const api = dockviewApi.value
  for (const session of [...nestedWorkflowSessionsStore.sessions]) {
    if (session.parentWorkflowName !== workflowName) continue
    const panelId = nestedWorkflowPanelId(session.id)
    const panel = api?.getPanel(panelId)
    if (panel) {
      removedWorkflowNestedWorkflowCloses.add(panelId)
      api?.removePanel(panel)
    } else {
      nestedWorkflowSessionsStore.closeSession(session.id)
      nestedWorkflowParentCanvasIds.delete(session.id)
    }
  }
}

function closeAndForgetNestedCanvasesForWorkflow(workflowName: string): void {
  const nestedSessionIds = nestedWorkflowSessionsStore.sessions
    .filter(session => session.parentWorkflowName === workflowName)
    .map(session => session.id)
  closeNestedCanvasesForWorkflow(workflowName)
  for (const sessionId of nestedSessionIds) {
    forgetRetainedNestedSnapshot(sessionId)
  }
}

interface DeletionCanvasTarget {
  canvasId: ReturnType<typeof canvasIdFromPanelId>
  nestedSessionId: string | null
}

function deletionCanvasTargets(workflowName: string): DeletionCanvasTarget[] {
  const targets: DeletionCanvasTarget[] = []
  const rootPanelId = workflowPanelId(workflowName)
  if (dockviewApi.value?.getPanel(rootPanelId)) {
    targets.push({
      canvasId: canvasIdFromPanelId(rootPanelId),
      nestedSessionId: null,
    })
  }
  for (const session of nestedWorkflowSessionsStore.sessions) {
    if (session.parentWorkflowName !== workflowName) continue
    targets.push({
      canvasId: canvasIdFromPanelId(nestedWorkflowPanelId(session.id)),
      nestedSessionId: session.id,
    })
  }
  return targets
}

function beginWorkflowDeletion(
  targets: DeletionCanvasTarget[],
): DeletionCanvasTarget[] {
  const acquired: DeletionCanvasTarget[] = []
  for (const target of targets) {
    if (canvasLifecycleStore.begin(target.canvasId, 'deleting')) {
      acquired.push(target)
      continue
    }
    for (const acquiredTarget of acquired) {
      canvasLifecycleStore.finish(acquiredTarget.canvasId)
    }
    throw new Error('A workflow canvas is already completing another action.')
  }
  return acquired
}

async function activateWorkflowFallback(
  excludedWorkflowNames: ReadonlySet<string> = new Set(),
): Promise<void> {
  const api = dockviewApi.value
  if (!api) return
  const remaining = openRootPanel(api)
  if (remaining) {
    remaining.api.setActive()
    return
  }

  canvasFallbackPending = true
  try {
    for (const workflow of workflowStore.flattenedWorkflows) {
      const workflowName = workflowInfoId(workflow)
      if (excludedWorkflowNames.has(workflowName)) continue
      try {
        const presentation = await loadRootWorkflowPresentation(workflowName)
        if (openRootPanel(api) || openWorkflowCanvasPanel(presentation)) return
      } catch {
        // Try the next workflow in stable tree order.
      }
    }
    showEmptyCanvasState(api)
  } finally {
    canvasFallbackPending = false
  }
}

function disposeRemovedWorkflowCanvases(workflowName: string): boolean {
  deferredWorkflowGenerationReplacements.delete(workflowName)
  closeAndForgetNestedCanvasesForWorkflow(workflowName)

  const panelId = workflowPanelId(workflowName)
  const canvasId = canvasIdFromPanelId(panelId)
  const api = dockviewApi.value
  const panel = api?.getPanel(panelId)
  const removedRootPanel = Boolean(panel)
  if (panel) api?.removePanel(panel)
  // Dockview removal normally triggers this through onDidRemovePanel. Keep the
  // disposal fence explicit for headless/no-panel convergence as well.
  unregisterGraphSyncCanvas(canvasId)
  canvasLifecycleStore.finish(canvasId)
  if (pendingRootClose.value?.workflowName === workflowName) {
    rootCloseBusy.value = false
    resetRootCloseDialog()
  }
  return removedRootPanel
}

async function convergeRemovedWorkflow(workflowName: string): Promise<void> {
  const removedRootPanel = disposeRemovedWorkflowCanvases(workflowName)
  try {
    await workflowStore.forgetDeletedWorkflow(workflowName)
  } finally {
    if (removedRootPanel) await activateWorkflowFallback(new Set([workflowName]))
  }
}

async function replaceMountedWorkflowGeneration(
  workflowName: string,
  serverIdentityGeneration: number,
): Promise<void> {
  const existingOperation = workflowGenerationReplacements.get(workflowName)
  if (existingOperation) return existingOperation
  const api = dockviewApi.value
  const panelId = workflowPanelId(workflowName)
  const canvasId = canvasIdFromPanelId(panelId)
  const panel = api?.getPanel(panelId)
  const context = canvasContexts.get(panelId)
  const lifecycleBusy = canvasLifecycleStore.isBusy(canvasId)
    || workflowDeletionsInFlight.has(workflowName)
  if (lifecycleBusy) {
    deferredWorkflowGenerationReplacements.set(
      workflowName,
      Math.max(
        deferredWorkflowGenerationReplacements.get(workflowName) ?? -1,
        serverIdentityGeneration,
      ),
    )
    return
  }
  if (
    !api
    || !panel
    || context?.serverIdentityGeneration === serverIdentityGeneration
  ) {
    deferredWorkflowGenerationReplacements.delete(workflowName)
    return
  }

  canvasGenerationReplacementCount += 1
  const operation = (async () => {
    if (
      api.getPanel(panelId) !== panel
      || workflowDeletionsInFlight.has(workflowName)
      || canvasLifecycleStore.isBusy(canvasId)
    ) {
      deferredWorkflowGenerationReplacements.set(
        workflowName,
        serverIdentityGeneration,
      )
      return
    }
    deferredWorkflowGenerationReplacements.delete(workflowName)
    closeAndForgetNestedCanvasesForWorkflow(workflowName)
    api.removePanel(panel)
    await workflowStore.resetWorkflowPresentationGeneration(workflowName)
    const presentation = await loadRootWorkflowPresentation(workflowName)
    if (!openWorkflowCanvasPanel(presentation)) {
      throw new Error(`Workflow '${workflowName}' could not be reopened at its fresh generation.`)
    }
  })().catch(async (replacementError) => {
    console.warn(
      `[workflow-generation] Failed to replace '${workflowName}':`,
      replacementError,
    )
    if (!openRootPanel(api)) {
      await activateWorkflowFallback(new Set([workflowName]))
    }
  }).finally(() => {
    canvasGenerationReplacementCount -= 1
    workflowGenerationReplacements.delete(workflowName)
  })
  workflowGenerationReplacements.set(workflowName, operation)
  return operation
}

interface WorkflowIdentityRefreshEntry {
  workflowName: string
  identityGeneration: number | null
}

async function reconcileMountedWorkflowGenerations(
  entries: WorkflowIdentityRefreshEntry[],
): Promise<void> {
  const identities = new Map(entries.map(entry => [entry.workflowName, entry]))
  for (const [panelId, context] of [...canvasContexts]) {
    if (workflowIdFromPanelId(panelId) === null) continue
    if (!dockviewApi.value?.getPanel(panelId)) continue
    const refreshed = identities.get(context.workflowName)
    if (!refreshed) {
      await convergeRemovedWorkflow(context.workflowName)
      continue
    }
    if (
      refreshed.identityGeneration !== null
      && refreshed.identityGeneration !== context.serverIdentityGeneration
    ) {
      await replaceMountedWorkflowGeneration(
        context.workflowName,
        refreshed.identityGeneration,
      )
    }
  }
}

function onWorkflowIdentitiesRefreshed(event: CustomEvent<{
  workflows?: WorkflowIdentityRefreshEntry[]
}>): void {
  const entries = event.detail?.workflows
  if (!Array.isArray(entries)) return
  void reconcileMountedWorkflowGenerations(entries).catch((reconciliationError) => {
    console.warn('[workflow-generation] Failed to reconcile mounted workflows:', reconciliationError)
  })
}

function retryDeferredWorkflowGenerationReplacements(): void {
  for (const [workflowName, identityGeneration] of [
    ...deferredWorkflowGenerationReplacements,
  ]) {
    const canvasId = canvasIdFromPanelId(workflowPanelId(workflowName))
    if (
      canvasLifecycleStore.isBusy(canvasId)
      || workflowDeletionsInFlight.has(workflowName)
    ) continue
    deferredWorkflowGenerationReplacements.delete(workflowName)
    void replaceMountedWorkflowGeneration(workflowName, identityGeneration)
  }
}

watch(
  () => canvasLifecycleStore.operations.size,
  retryDeferredWorkflowGenerationReplacements,
)

async function deleteWorkflowFromRequest(
  request: WorkflowDeletionEventDetail,
): Promise<void> {
  const { workflowName } = request
  if (workflowDeletionsInFlight.has(workflowName)) {
    throw new Error(`Workflow '${workflowName}' is already being deleted.`)
  }
  const canonicalCanvasId = canvasIdFromPanelId(workflowPanelId(workflowName))
  if (request.canvasId !== null && request.canvasId !== canonicalCanvasId) {
    throw new Error('The delete request no longer matches its original workflow tab.')
  }
  assertWorkflowDeletionTargetCurrent(request)
  const targets = deletionCanvasTargets(workflowName)
  const targetCanvasId = targets.some(target => target.nestedSessionId === null)
    ? canonicalCanvasId
    : null
  const acquiredTargets = beginWorkflowDeletion(targets)

  workflowDeletionsInFlight.add(workflowName)
  try {
    if (targetCanvasId) {
      const persistence = getRootCanvasPersistenceResource(targetCanvasId)
      if (!persistence || persistence.workflowId.value !== workflowName) {
        throw new Error('The workflow tab is not initialized for deletion.')
      }
      const fresh = await persistence.ensureFreshForCriticalOperation()
      if (!fresh) {
        throw new Error('This workflow changed elsewhere. Resolve the draft conflict before deleting it.')
      }
    }
    await Promise.all(acquiredTargets.flatMap(target => (
      target.nestedSessionId === null
        ? []
        : [flushRetainedNestedSnapshot(target.nestedSessionId)]
    )))
    assertWorkflowDeletionTargetCurrent(request)
    let disposedBeforeRecoveryCleanup = false
    let removedRootPanel = false
    try {
      await workflowStore.deleteWorkflow(workflowName, {
        closingCanvasId: targetCanvasId ?? undefined,
        allowMountedIdentity: true,
        expectedIdentityGeneration: request.serverIdentityGeneration ?? undefined,
        beforeRecoveryCleanup: () => {
          disposedBeforeRecoveryCleanup = true
          removedRootPanel = disposeRemovedWorkflowCanvases(workflowName)
        },
      })
      if (!disposedBeforeRecoveryCleanup) {
        await convergeRemovedWorkflow(workflowName)
      } else if (removedRootPanel) {
        await activateWorkflowFallback(new Set([workflowName]))
      }
    } catch (error) {
      if (disposedBeforeRecoveryCleanup && removedRootPanel) {
        await activateWorkflowFallback(new Set([workflowName]))
      }
      if (disposedBeforeRecoveryCleanup) {
        throw new WorkflowDeletionCommittedCleanupError(workflowName, error)
      }
      if (isWorkflowDeleteGenerationConflict(error)) {
        throw new WorkflowDeletionTargetChangedError(workflowName)
      }
      throw error
    }
  } finally {
    workflowDeletionsInFlight.delete(workflowName)
    for (const target of acquiredTargets) {
      canvasLifecycleStore.finish(target.canvasId)
    }
  }
}

function isWorkflowDeleteGenerationConflict(error: unknown): boolean {
  return typeof error === 'object'
    && error !== null
    && 'response' in error
    && (
      error as {
        response?: { status?: unknown; data?: { error?: unknown } }
      }
    ).response?.status === 409
    && (
      error as {
        response?: { data?: { error?: unknown } }
      }
    ).response?.data?.error === 'workflow_identity_generation_conflict'
}

function assertWorkflowDeletionTargetCurrent(
  request: WorkflowDeletionRequest,
): void {
  if (!workflowStore.isWorkflowIdentityCurrent(
    request.workflowName,
    request.localIdentityGeneration,
  )) {
    throw new WorkflowDeletionTargetChangedError(request.workflowName)
  }
  if (
    workflowStore.workflowServerIdentityGeneration(request.workflowName)
    !== request.serverIdentityGeneration
  ) {
    throw new WorkflowDeletionTargetChangedError(request.workflowName)
  }
  if (request.canvasId === null) {
    if (request.sessionRegistrationToken !== null) {
      throw new WorkflowDeletionTargetChangedError(request.workflowName)
    }
    return
  }
  const session = canvasSessionRegistry.get(request.canvasId)
  if (
    session?.descriptor.kind !== 'root'
    || session.descriptor.workflowId !== request.workflowName
    || session.registrationToken !== request.sessionRegistrationToken
  ) {
    throw new WorkflowDeletionTargetChangedError(request.workflowName)
  }
}

function onRequestDeleteWorkflow(event: CustomEvent<WorkflowDeletionEventDetail>): void {
  const request = event.detail
  if (!request?.workflowName) return
  void deleteWorkflowFromRequest(request).then(request.resolve, request.reject)
}

function onWorkflowRemoved(event: CustomEvent<{
  workflowName?: string
  identityGeneration?: number
}>): void {
  const workflowName = event.detail?.workflowName
  if (!workflowName) return
  const identityGeneration = event.detail.identityGeneration
  if (
    identityGeneration !== undefined
    && !workflowStore.observeWorkflowServerIdentityGeneration(
      workflowName,
      identityGeneration,
      { structuralEvent: true },
    )
  ) return
  void convergeRemovedWorkflow(workflowName).catch((error) => {
    console.warn(`[workflow-delete] Failed to converge '${workflowName}':`, error)
  })
}

function openWorkflowCanvasPanel(detail: {
  graph: GraphState
  workflowName: string
  workflowDisplayName?: string
  missingTools?: MissingTool[]
  dirty?: boolean
  draft?: WorkflowDraftResponse
  identityGeneration?: number
  serverIdentityGeneration?: number | null
}): boolean {
  const api = dockviewApi.value
  if (!api || !detail.graph) return false
  const workflowName = detail.workflowName
  if (!workflowName) return false
  if (
    workflowDeletionsInFlight.has(workflowName)
    || !isRootWorkflowPresentationCurrent(
      workflowName,
      detail.graph,
      detail.identityGeneration,
    )
  ) return false
  const workflowDisplayName =
    detail.workflowDisplayName
    ?? workflowName
  const panelId = workflowPanelId(workflowName)
  const existing = api.getPanel(panelId)
  if (existing) {
    rememberRootActivation(existing.id)
    existing.api.setActive()
    removeCanvasPlaceholder(api)
    return true
  }
  canvasContexts.set(panelId, {
    workflowName,
    workflowDisplayName,
    serverIdentityGeneration: detail.serverIdentityGeneration ?? null,
  })
  uiStore.setCanvasWorkflow(
    canvasIdFromPanelId(panelId),
    workflowName,
    workflowDisplayName,
  )
  const canvasPanel = layoutAnchorPanel(api)
  const bottomPanel = api.getPanel('dataTable') ?? api.getPanel('logger')
  const panel = api.addPanel({
    id: panelId,
    component: 'canvasView',
    tabComponent: 'canvasTab',
    title: workflowDisplayName,
    params: {
      panelId,
      workflowName,
      workflowDisplayName,
      graph: detail.graph,
      missingTools: detail.missingTools ?? [],
      dirty: detail.dirty ?? false,
      draft: detail.draft,
      serverIdentityGeneration: detail.serverIdentityGeneration ?? null,
    },
    position: canvasPanel
      ? { referencePanel: canvasPanel.id, direction: 'within' }
      : bottomPanel
        ? { referencePanel: bottomPanel.id, direction: 'above' }
        : { direction: 'below' },
  })
  openCanvasPanelIds.add(panel.id)
  rememberRootActivation(panel.id)
  panel.api.setActive()
  removeCanvasPlaceholder(api)
  return true
}

function onApplyGraph(event: CustomEvent<{
  graph?: GraphState
  workflowName?: string
  workflowDisplayName?: string
  missingTools?: MissingTool[]
  dirty?: boolean
  draft?: WorkflowDraftResponse
  identityGeneration?: number
  serverIdentityGeneration?: number | null
}>) {
  const detail = event.detail
  if (!detail?.graph || !detail.workflowName) return
  const opened = openWorkflowCanvasPanel({
    graph: detail.graph,
    workflowName: detail.workflowName,
    workflowDisplayName: detail.workflowDisplayName,
    missingTools: detail.missingTools,
    dirty: detail.dirty,
    draft: detail.draft,
    identityGeneration: detail.identityGeneration,
    serverIdentityGeneration: detail.serverIdentityGeneration,
  })
  if (opened) rootOpenRequest += 1
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
    case 'datasets': {
      const reference = dockviewApi.value?.getPanel('tools') ?? dockviewApi.value?.getPanel('workflows')
      if (reference) {
        return { id: 'datasets', component: 'datasets', title: 'Datasets', position: { referencePanel: reference.id, direction: 'within' as const } }
      }
      return { id: 'datasets', component: 'datasets', title: 'Datasets', initialWidth: 320, position: { direction: 'left' as const } }
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
      const canvasPanel = dockviewApi.value
        ? layoutAnchorPanel(dockviewApi.value)
        : null
      return {
        id: 'codeEditor',
        component: 'codeEditor',
        tabComponent: 'codeEditorTab',
        title: 'Code Editor',
        initialWidth: 520,
        position: canvasPanel
          ? { referencePanel: canvasPanel.id, direction: 'right' as const }
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
    <NapariProgressBanner />
    <EnvironmentRecoveryDialog />
    <div class="dockview-wrapper">
      <DockviewVue
        :theme="dockviewTheme"
        popout-url="/popout.html"
        @ready="onDockviewReady"
      />
    </div>
    <Toast position="bottom-right" />
    <ConfirmDialog />
    <Dialog
      :visible="rootCloseDialogVisible"
      modal
      header="Save changes before closing?"
      :closable="!rootCloseBusy"
      :close-on-escape="!rootCloseBusy"
      :style="{ width: '460px' }"
      data-testid="root-workflow-close-dialog"
      @update:visible="(visible: boolean) => { if (!visible) resetRootCloseDialog() }"
    >
      <p>
        <strong>{{ pendingRootClose?.workflowName }}</strong> has unsaved changes.
        Save them, restore the last saved version, or keep the tab open.
      </p>
      <p v-if="rootCloseError" class="root-close-error" role="alert">
        {{ rootCloseError }}
      </p>
      <template #footer>
        <Button
          label="Cancel"
          text
          :disabled="rootCloseBusy"
          data-testid="root-workflow-close-cancel"
          @click="resetRootCloseDialog"
        />
        <Button
          label="Discard"
          severity="danger"
          outlined
          :disabled="rootCloseBusy"
          data-testid="root-workflow-close-discard"
          @click="discardAndCloseRootCanvas"
        />
        <Button
          label="Save"
          icon="pi pi-save"
          :loading="rootCloseBusy"
          data-testid="root-workflow-close-save"
          @click="saveAndCloseRootCanvas"
        />
      </template>
    </Dialog>
    <SettingsPanel />
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

.root-close-error {
  color: var(--p-red-500);
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

.bif-dark-theme .vue-flow__controls-button svg,
.bif-dark-theme .vue-flow__controls-button path {
  fill: currentColor;
}

/* Preserve newlines in toast detail (used by the run-button validation
 * summary so errors appear as a bullet list). */
:global(.p-toast-detail) {
  white-space: pre-line;
}
</style>
