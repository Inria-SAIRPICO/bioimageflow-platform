<script lang="ts">
import { defineComponent } from 'vue'
import ToolsPanel from './components/panels/ToolsPanel.vue'
import CanvasView from './components/canvas/CanvasView.vue'
import NodePanel from './components/panels/NodePanel.vue'
import SettingsPanel from './components/panels/SettingsPanel.vue'
import LoggerPanel from './components/panels/LoggerPanel.vue'
import DataTablePanel from './components/panels/DataTablePanel.vue'
import CodeEditorPanel from './components/panels/CodeEditorPanel.vue'
import SubWorkflowEditorPanel from './components/panels/SubWorkflowEditorPanel.vue'

export default defineComponent({
  components: {
    tools: ToolsPanel,
    canvasView: CanvasView,
    nodePanel: NodePanel,
    logger: LoggerPanel,
    dataTable: DataTablePanel,
    codeEditor: CodeEditorPanel,
    subWorkflowEditor: SubWorkflowEditorPanel,
  },
})
</script>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch, shallowRef, watchEffect } from 'vue'
import { DockviewVue, type DockviewReadyEvent, type DockviewApi } from 'dockview-vue'
import { themeLight, type DockviewIDisposable, type IDockviewPanel } from 'dockview-core'
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

// Initialize once at the root so uiStore.isExecutionLocked reflects
// executionStore.isRunning anywhere in the tree. The composable has a
// side-effectful watch; the return values are unused here.
useExecutionLock()

onMounted(() => {
  websocket.connect()
  window.addEventListener('bif:open-code-editor', onOpenCodeEditor as EventListener)
  window.addEventListener(
    'bioimageflow:sub-workflow-session-opened',
    onSubWorkflowSessionOpened as EventListener,
  )
  window.addEventListener(
    'bioimageflow:close-sub-workflow-session',
    onCloseSubWorkflowSession as EventListener,
  )
  if (shortcutEnabled) {
    window.addEventListener('keydown', onPreferencesShortcut)
  }
})

onBeforeUnmount(() => {
  dockviewDisposables.splice(0).forEach((disposable) => disposable.dispose())
  websocket.disconnect()
  window.removeEventListener('bif:open-code-editor', onOpenCodeEditor as EventListener)
  window.removeEventListener(
    'bioimageflow:sub-workflow-session-opened',
    onSubWorkflowSessionOpened as EventListener,
  )
  window.removeEventListener(
    'bioimageflow:close-sub-workflow-session',
    onCloseSubWorkflowSession as EventListener,
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

const dockviewApi = shallowRef<DockviewApi | null>(null)
const dockviewDisposables: DockviewIDisposable[] = []
const confirmedSubWorkflowPanelCloses = new Set<string>()

// --- Dockview setup ---

const panelKeys = ['tools', 'nodePanel', 'dataTable', 'logger', 'codeEditor'] as const
type DockPanelKey = typeof panelKeys[number]

function isDockPanelKey(id: string): id is DockPanelKey {
  return panelKeys.includes(id as DockPanelKey)
}

function subWorkflowPanelId(sessionId: string): string {
  return `sub-workflow:${encodeURIComponent(sessionId)}`
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
}

function onOpenCodeEditor(event: CustomEvent<{ url: string; path: string }>) {
  uiStore.setCodeEditorTarget(event.detail.url, event.detail.path)
  queueMicrotask(() => {
    const panel = dockviewApi.value?.getPanel('codeEditor')
    panel?.api.setActive()
  })
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
    params: { sessionId },
    position: canvasPanel
      ? { referencePanel: 'canvas', direction: 'within' }
      : { direction: 'below' },
  })
  panel.api.setActive()
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
    case 'codeEditor':
      return { id: 'codeEditor', component: 'codeEditor', title: 'Code Editor', initialHeight: 360, position: { direction: 'below' as const } }
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
        :theme="themeLight"
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

/* Preserve newlines in toast detail (used by the run-button validation
 * summary so errors appear as a bullet list). */
:global(.p-toast-detail) {
  white-space: pre-line;
}
</style>
