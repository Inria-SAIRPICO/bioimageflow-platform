<script lang="ts">
import { defineComponent, h } from 'vue'
import ToolsPanel from './components/panels/ToolsPanel.vue'
import CanvasView from './components/canvas/CanvasView.vue'

export default defineComponent({
  components: {
    tools: ToolsPanel,
    canvasView: CanvasView,
    nodePanel: defineComponent({
      render() {
        return h('div', { 'data-testid': 'panel-nodePanel', style: 'padding: 8px' }, 'Node Panel (placeholder)')
      },
    }),
    dataTable: defineComponent({
      render() {
        return h('div', { 'data-testid': 'panel-dataTable', style: 'padding: 8px' }, 'Data Table (placeholder)')
      },
    }),
    logger: defineComponent({
      render() {
        return h('div', { 'data-testid': 'panel-logger', style: 'padding: 8px' }, 'Logger (placeholder)')
      },
    }),
  },
})
</script>

<script setup lang="ts">
import { watch, shallowRef, watchEffect } from 'vue'
import { DockviewVue, type DockviewReadyEvent, type DockviewApi } from 'dockview-vue'
import MenuBar from './components/layout/MenuBar.vue'
import { useUIStore } from './stores/ui'

const uiStore = useUIStore()

// Sync document.title with uiStore.tabTitle
watchEffect(() => {
  document.title = uiStore.tabTitle
})

const dockviewApi = shallowRef<DockviewApi | null>(null)

// --- Dockview setup ---

function onDockviewReady(event: DockviewReadyEvent) {
  const api = event.api
  dockviewApi.value = api

  api.addPanel({
    id: 'tools',
    component: 'tools',
    title: 'Tools',
    initialWidth: 320,
    position: { direction: 'left' },
  })

  api.addPanel({
    id: 'canvas',
    component: 'canvasView',
    title: 'Canvas',
  })

  api.addPanel({
    id: 'nodePanel',
    component: 'nodePanel',
    title: 'Node Panel',
    initialWidth: 320,
    position: { direction: 'right' },
  })

  api.addPanel({
    id: 'dataTable',
    component: 'dataTable',
    title: 'Data Table',
    initialHeight: 250,
    position: { direction: 'below' },
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
}

// --- Panel visibility sync ---

const panelKeys = ['tools', 'nodePanel', 'dataTable', 'logger'] as const

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
      return { id: 'nodePanel', component: 'nodePanel', title: 'Node Panel', initialWidth: 320, position: { direction: 'right' as const } }
    case 'dataTable':
      return { id: 'dataTable', component: 'dataTable', title: 'Data Table', initialHeight: 250, position: { direction: 'below' as const } }
    case 'logger': {
      const dataTablePanel = dockviewApi.value?.getPanel('dataTable')
      if (dataTablePanel) {
        return { id: 'logger', component: 'logger', title: 'Logger', position: { referencePanel: 'dataTable' as const, direction: 'within' as const } }
      }
      return { id: 'logger', component: 'logger', title: 'Logger', initialHeight: 250, position: { direction: 'below' as const } }
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
    <div class="dockview-wrapper">
      <DockviewVue
        class-name="dockview-theme-light"
        @ready="onDockviewReady"
      />
    </div>
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
</style>
