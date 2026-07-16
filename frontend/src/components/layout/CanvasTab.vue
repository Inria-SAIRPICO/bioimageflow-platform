<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import type { DockviewPanelApi } from 'dockview-core'

type Disposable = { dispose: () => void }

const props = defineProps<{
  params: {
    api: DockviewPanelApi
  }
}>()

const title = ref(props.params.api.title ?? 'Workflow')
const disposables: Disposable[] = []

function requestClose(): void {
  window.dispatchEvent(new CustomEvent('bioimageflow:request-close-canvas', {
    detail: { canvasId: props.params.api.id },
  }))
}

onMounted(() => {
  disposables.push(props.params.api.onDidTitleChange((event) => {
    title.value = event.title
  }))
})

onBeforeUnmount(() => {
  disposables.splice(0).forEach(disposable => disposable.dispose())
})
</script>

<template>
  <div class="dv-default-tab canvas-tab" data-testid="canvas-tab">
    <div class="dv-default-tab-content canvas-tab__title">
      {{ title }}
    </div>
    <button
      class="canvas-tab__close"
      type="button"
      title="Close"
      :aria-label="`Close ${title}`"
      data-testid="canvas-tab-close"
      @pointerdown.stop.prevent
      @click.stop.prevent="requestClose"
    >
      <i class="pi pi-times" aria-hidden="true" />
    </button>
  </div>
</template>

<style scoped>
.canvas-tab {
  gap: 0.25rem;
  min-width: 0;
}

.canvas-tab__title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.canvas-tab__close {
  align-items: center;
  background: transparent;
  border: 0;
  border-radius: 3px;
  color: inherit;
  cursor: pointer;
  display: inline-flex;
  flex: 0 0 auto;
  height: 1.375rem;
  justify-content: center;
  padding: 0;
  width: 1.375rem;
}

.canvas-tab__close:hover {
  background: var(--dv-icon-hover-background-color);
}
</style>
