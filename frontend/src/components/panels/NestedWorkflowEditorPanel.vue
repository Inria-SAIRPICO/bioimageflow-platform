<script setup lang="ts">
import { computed } from 'vue'
import CanvasView from '@/components/canvas/CanvasView.vue'

const props = defineProps<{
  params?: {
    sessionId?: string
    panelId?: string
    parentCanvasPanelId?: string
    params?: {
      sessionId?: string
      panelId?: string
      parentCanvasPanelId?: string
    }
  }
}>()

const sessionId = computed(() => (
  props.params?.sessionId ?? props.params?.params?.sessionId ?? ''
))
const panelId = computed(() => (
  props.params?.panelId ?? props.params?.params?.panelId ?? ''
))
const parentCanvasPanelId = computed(() => (
  props.params?.parentCanvasPanelId
  ?? props.params?.params?.parentCanvasPanelId
  ?? 'canvas'
))
</script>

<template>
  <div class="nested-workflow-editor">
    <CanvasView
      v-if="sessionId"
      :nested-workflow-session-id="sessionId"
      :parent-canvas-panel-id="parentCanvasPanelId"
      :params="{ panelId }"
    />
  </div>
</template>

<style scoped>
.nested-workflow-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.nested-workflow-editor :deep(.canvas-view) {
  flex: 1;
  min-height: 0;
}
</style>
