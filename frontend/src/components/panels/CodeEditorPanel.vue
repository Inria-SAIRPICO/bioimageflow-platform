<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useUIStore } from '@/stores/ui'
import { getEditorStatus } from '@/api/editor'
import {
  closeCodeEditorWindow,
  hasCodeEditorWindowBridge,
  isDesktop,
  openCodeEditorWindow,
} from '@/utils/nativeDialogs'

const uiStore = useUIStore()
const { codeEditorUrl, codeEditorPath, codeEditorOpening, codeEditorDetached } =
  storeToRefs(uiStore)
const failed = ref(false)
const statusLoading = ref(false)

const loading = computed(() => statusLoading.value || codeEditorOpening.value)
const loadingMessage = computed(() => (
  codeEditorOpening.value ? 'Opening code editor...' : 'Starting code-server...'
))
const detached = computed(() => (
  codeEditorDetached.value && Boolean(codeEditorUrl.value) && !loading.value
))
const available = computed(() => (
  Boolean(codeEditorUrl.value) && !failed.value && !loading.value && !detached.value
))
const editorTitle = computed(() => (
  codeEditorPath.value ? `Code editor - ${codeEditorPath.value}` : 'Code editor'
))
const canPopOut = computed(() => (
  available.value && (!isDesktop() || hasCodeEditorWindowBridge())
))

async function popOutEditor() {
  if (!codeEditorUrl.value) return
  if (hasCodeEditorWindowBridge()) {
    const opened = await openCodeEditorWindow(codeEditorUrl.value, editorTitle.value)
    if (opened) {
      uiStore.setCodeEditorDetached(true)
    }
    return
  }
  window.dispatchEvent(new CustomEvent('bioimageflow:popout-code-editor'))
}

async function restoreEditor() {
  await closeCodeEditorWindow()
  uiStore.setCodeEditorDetached(false)
}

function onDetachedWindowClosed() {
  uiStore.setCodeEditorDetached(false)
}

onMounted(async () => {
  window.addEventListener('bioimageflow:code-editor-window-closed', onDetachedWindowClosed)
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

onBeforeUnmount(() => {
  window.removeEventListener('bioimageflow:code-editor-window-closed', onDetachedWindowClosed)
})
</script>

<template>
  <section class="code-editor-panel" data-testid="code-editor-panel">
    <template v-if="available">
      <div
        v-if="canPopOut"
        class="code-editor-panel__toolbar"
        data-testid="code-editor-toolbar"
      >
        <button
          class="code-editor-panel__icon-button"
          type="button"
          title="Open in separate window"
          aria-label="Open in separate window"
          data-testid="code-editor-popout"
          @click="popOutEditor"
        >
          <i class="pi pi-external-link" aria-hidden="true" />
        </button>
      </div>
      <iframe
        class="code-editor-panel__frame"
        data-testid="code-editor-iframe"
        :src="codeEditorUrl ?? undefined"
        :title="editorTitle"
        @error="failed = true"
      />
    </template>
    <div
      v-else-if="detached"
      class="code-editor-panel__detached"
      data-testid="code-editor-detached"
    >
      <span>Code editor is open in a separate window.</span>
      <button
        class="code-editor-panel__restore"
        type="button"
        data-testid="code-editor-restore"
        @click="restoreEditor"
      >
        Restore here
      </button>
    </div>
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
  display: flex;
  flex-direction: column;
}

.code-editor-panel__frame {
  display: block;
  width: 100%;
  min-height: 0;
  flex: 1 1 auto;
  border: 0;
}

.code-editor-panel__toolbar {
  flex: 0 0 auto;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  height: 2rem;
  padding: 0.25rem 0.5rem;
  border-bottom: 1px solid var(--p-content-border-color);
  background: var(--p-surface-50);
}

.code-editor-panel__icon-button {
  width: 1.5rem;
  height: 1.5rem;
  display: inline-grid;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 4px;
  color: var(--p-text-muted-color);
  background: transparent;
  cursor: pointer;
}

.code-editor-panel__icon-button:hover {
  color: var(--p-text-color);
  border-color: var(--p-content-border-color);
  background: var(--p-surface-100);
}

.code-editor-panel__unavailable,
.code-editor-panel__detached {
  flex: 1 1 auto;
  display: grid;
  place-items: center;
  padding: 1rem;
  color: var(--p-text-muted-color);
  text-align: center;
}

.code-editor-panel__detached {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
}

.code-editor-panel__restore {
  min-height: 2rem;
  padding: 0 0.75rem;
  border: 1px solid var(--p-primary-color);
  border-radius: 4px;
  color: var(--p-primary-contrast-color);
  background: var(--p-primary-color);
  cursor: pointer;
}

.code-editor-panel__restore:hover {
  background: var(--p-primary-hover-color);
}

.code-editor-panel__loading {
  flex: 1 1 auto;
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
