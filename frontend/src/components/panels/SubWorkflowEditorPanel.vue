<script setup lang="ts">
import { computed } from 'vue'
import CanvasView from '@/components/canvas/CanvasView.vue'

const props = defineProps<{
  params?: {
    sessionId?: string
    params?: {
      sessionId?: string
    }
  }
}>()

const sessionId = computed(() => (
  props.params?.sessionId ?? props.params?.params?.sessionId ?? ''
))
</script>

<template>
  <div class="sub-workflow-editor">
    <CanvasView
      v-if="sessionId"
      :sub-workflow-session-id="sessionId"
    />
  </div>
</template>

<style scoped>
.sub-workflow-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.sub-workflow-editor :deep(.canvas-view) {
  flex: 1;
  min-height: 0;
}
</style>
