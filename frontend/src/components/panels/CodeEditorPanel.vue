<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useUIStore } from '@/stores/ui'
import { getEditorStatus } from '@/api/editor'

const uiStore = useUIStore()
const { codeEditorUrl, codeEditorPath, codeEditorOpening } = storeToRefs(uiStore)
const failed = ref(false)
const statusLoading = ref(false)

const loading = computed(() => statusLoading.value || codeEditorOpening.value)
const loadingMessage = computed(() => (
  codeEditorOpening.value ? 'Opening code editor...' : 'Starting code-server...'
))
const available = computed(() => Boolean(codeEditorUrl.value) && !failed.value && !loading.value)

onMounted(async () => {
  if (codeEditorUrl.value || codeEditorOpening.value) return
  statusLoading.value = true
  try {
    const status = await getEditorStatus({ launch: true })
    if (status.available && status.url) {
      uiStore.setCodeEditorTarget(status.url, codeEditorPath.value ?? '')
      failed.value = false
    }
  } catch {
    // The unavailable state below is the user-facing fallback.
  } finally {
    statusLoading.value = false
  }
})
</script>

<template>
  <section class="code-editor-panel" data-testid="code-editor-panel">
    <iframe
      v-if="available"
      class="code-editor-panel__frame"
      data-testid="code-editor-iframe"
      :src="codeEditorUrl ?? undefined"
      :title="codeEditorPath ? `Code editor - ${codeEditorPath}` : 'Code editor'"
      @error="failed = true"
    />
    <div v-else-if="loading" class="code-editor-panel__loading" data-testid="code-editor-loading">
      <i class="pi pi-spin pi-spinner" aria-hidden="true" />
      <span>{{ loadingMessage }}</span>
    </div>
    <div v-else class="code-editor-panel__unavailable" data-testid="code-editor-unavailable">
      code-server is not available. Configure an external editor in Settings.
    </div>
  </section>
</template>

<style scoped>
.code-editor-panel {
  width: 100%;
  height: 100%;
  min-height: 240px;
  background: var(--p-surface-0);
}

.code-editor-panel__frame {
  display: block;
  width: 100%;
  height: 100%;
  border: 0;
}

.code-editor-panel__unavailable {
  height: 100%;
  display: grid;
  place-items: center;
  padding: 1rem;
  color: var(--p-text-muted-color);
  text-align: center;
}

.code-editor-panel__loading {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.625rem;
  padding: 1rem;
  color: var(--p-text-muted-color);
  text-align: center;
}

.code-editor-panel__loading .pi {
  font-size: 1.125rem;
}
</style>
