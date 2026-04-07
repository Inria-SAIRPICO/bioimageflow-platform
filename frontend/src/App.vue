<script setup lang="ts">
import { ref, watchEffect } from 'vue'
import ToolsPanel from './components/panels/ToolsPanel.vue'
import CanvasView from './components/canvas/CanvasView.vue'
import { useUIStore } from './stores/ui'

const uiStore = useUIStore()

// Sync document.title with uiStore.tabTitle
watchEffect(() => {
  document.title = uiStore.tabTitle
})

const canvasRef = ref<InstanceType<typeof CanvasView> | null>(null)
const nodes = ref<any[]>([])
const edges = ref<any[]>([])

function onAddTool(toolName: string) {
  canvasRef.value?.onAddNode({ toolName })
}

function onGraphChanged(payload: { nodes: any[]; edges: any[] }) {
  nodes.value = payload.nodes
  edges.value = payload.edges
}
</script>

<template>
  <div id="bioimageflow-app">
    <aside class="tools-sidebar">
      <ToolsPanel @add-tool="onAddTool" />
    </aside>
    <main class="canvas-main">
      <CanvasView
        ref="canvasRef"
        :nodes="nodes"
        :edges="edges"
        @graph-changed="onGraphChanged"
      />
    </main>
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
}

.tools-sidebar {
  width: 320px;
  min-width: 240px;
  border-right: 1px solid #e0e0e0;
  overflow-y: auto;
  padding: 8px;
}

.canvas-main {
  flex: 1;
  overflow: hidden;
}
</style>
