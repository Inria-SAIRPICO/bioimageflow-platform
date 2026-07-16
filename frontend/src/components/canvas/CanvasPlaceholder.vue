<script setup lang="ts">
import Button from 'primevue/button'

const props = defineProps<{
  params?: {
    state?: 'loading' | 'empty'
    message?: string
    params?: {
      state?: 'loading' | 'empty'
      message?: string
    }
  }
}>()

function values() {
  return props.params?.params ?? props.params
}

function command(action: 'new' | 'open'): void {
  window.dispatchEvent(new CustomEvent('bioimageflow:workflow-command', {
    detail: { action },
  }))
}
</script>

<template>
  <div class="canvas-placeholder" data-testid="canvas-placeholder">
    <template v-if="values()?.state !== 'empty'">
      <i class="pi pi-spin pi-spinner" aria-hidden="true" />
      <p>{{ values()?.message ?? 'Loading your workflows…' }}</p>
    </template>
    <template v-else>
      <i class="pi pi-sitemap canvas-placeholder__empty-icon" aria-hidden="true" />
      <h2>No workflow is open</h2>
      <p>{{ values()?.message ?? 'Create a workflow or open an existing one to start editing.' }}</p>
      <div class="canvas-placeholder__actions">
        <Button label="New workflow" icon="pi pi-plus" @click="command('new')" />
        <Button label="Open workflow" icon="pi pi-folder-open" outlined @click="command('open')" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.canvas-placeholder {
  align-items: center;
  background: var(--bif-app-bg);
  color: var(--bif-text-subtle);
  display: flex;
  flex-direction: column;
  height: 100%;
  justify-content: center;
  padding: 2rem;
  text-align: center;
}

.canvas-placeholder > .pi-spinner,
.canvas-placeholder__empty-icon {
  font-size: 2rem;
}

.canvas-placeholder h2 {
  color: var(--bif-text-strong);
  margin-bottom: 0;
}

.canvas-placeholder__actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.75rem;
}
</style>
