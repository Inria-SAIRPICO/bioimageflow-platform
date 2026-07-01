<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useUIStore } from '@/stores/ui'
import { getEditorStatus, openEditorPath } from '@/api/editor'
import type { EditorStatus } from '@/api/editor'
import { closeCodeEditorWindow } from '@/utils/nativeDialogs'

const uiStore = useUIStore()
const {
  codeEditorUrl,
  codeEditorPath,
  codeEditorOpening,
  codeEditorTargetRequestId,
  codeEditorDetached,
} =
  storeToRefs(uiStore)
const failed = ref(false)
const statusLoading = ref(false)
const statusDiagnostic = ref<EditorStatus | null>(null)
const focusedAfterLoadKey = ref<string | null>(null)
const iframeElement = ref<HTMLIFrameElement | null>(null)

const loading = computed(() => (
  statusLoading.value || (!codeEditorUrl.value && codeEditorOpening.value)
))
const loadingMessage = computed(() => (
  codeEditorOpening.value ? 'Opening code editor...' : 'Starting code-server...'
))
const detached = computed(() => (
  codeEditorDetached.value && Boolean(codeEditorUrl.value) && !statusLoading.value
))
const available = computed(() => (
  Boolean(codeEditorUrl.value) && !failed.value && !detached.value
))
const editorTitle = computed(() => (
  codeEditorPath.value ? `Code editor - ${codeEditorPath.value}` : 'Code editor'
))
const hasStatusDiagnostic = computed(() => Boolean(statusDiagnostic.value?.error_code))
const unavailableMessage = computed(() => (
  hasStatusDiagnostic.value
    ? 'code-server failed to start.'
    : 'code-server is not available. Configure an external editor in Settings.'
))
const unavailableDetail = computed(() => statusDiagnostic.value?.error_detail ?? '')

async function restoreEditor() {
  await closeCodeEditorWindow()
  uiStore.setCodeEditorDetached(false)
}

function shouldFocusPathAfterLoad(url: string | null, path: string | null): path is string {
  if (!url || !path) return false
  return url.includes('folder=')
}

async function focusPathAfterLoad(event: Event) {
  if (event.currentTarget !== iframeElement.value) return
  if (codeEditorOpening.value) return
  const url = codeEditorUrl.value
  const path = codeEditorPath.value
  if (!shouldFocusPathAfterLoad(url, path)) return
  const loadedUrl = iframeElement.value?.getAttribute('src')
  if (loadedUrl && loadedUrl !== url) return
  const key = `${codeEditorTargetRequestId.value ?? ''}\n${url}\n${path}`
  if (focusedAfterLoadKey.value === key) return
  focusedAfterLoadKey.value = key
  try {
    await openEditorPath(path)
  } catch {
    // The editor panel is already open on the project folder; diagnostics for
    // failed file focus are kept out of the main panel state.
  }
}

function onDetachedWindowClosed() {
  uiStore.setCodeEditorDetached(false)
}

function onCodeEditorDiagnostic(event: Event) {
  const detail = (event as CustomEvent<{
    path?: string
    error_code?: string | null
    error_detail?: string | null
  }>).detail
  if (!detail?.error_code) return
  statusDiagnostic.value = {
    available: false,
    url: null,
    version: null,
    control_available: false,
    launch_attempted: true,
    error_code: detail.error_code,
    error_detail: detail.error_detail ?? null,
  }
}

onMounted(async () => {
  window.addEventListener('bioimageflow:code-editor-window-closed', onDetachedWindowClosed)
  window.addEventListener('bif:code-editor-diagnostic', onCodeEditorDiagnostic)
  if (codeEditorUrl.value || codeEditorOpening.value) return
  statusLoading.value = true
  try {
    const status = await getEditorStatus({ launch: true })
    if (status.available && status.url) {
      uiStore.setCodeEditorTarget(status.url, codeEditorPath.value ?? '')
      failed.value = false
      statusDiagnostic.value = null
    } else {
      statusDiagnostic.value = status
    }
  } catch {
    // The unavailable state below is the user-facing fallback.
  } finally {
    statusLoading.value = false
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('bioimageflow:code-editor-window-closed', onDetachedWindowClosed)
  window.removeEventListener('bif:code-editor-diagnostic', onCodeEditorDiagnostic)
})

watch([codeEditorUrl, codeEditorPath], () => {
  focusedAfterLoadKey.value = null
})
</script>

<template>
  <section class="code-editor-panel" data-testid="code-editor-panel">
    <template v-if="available">
      <iframe
        ref="iframeElement"
        :key="codeEditorUrl ?? ''"
        class="code-editor-panel__frame"
        data-testid="code-editor-iframe"
        :src="codeEditorUrl ?? undefined"
        :title="editorTitle"
        @error="failed = true"
        @load="focusPathAfterLoad"
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
      <span>{{ unavailableMessage }}</span>
      <span
        v-if="unavailableDetail"
        class="code-editor-panel__unavailable-detail"
        data-testid="code-editor-unavailable-detail"
      >
        {{ unavailableDetail }}
      </span>
      <span v-if="hasStatusDiagnostic">Configure an external editor in Settings, or check the server logs.</span>
    </div>
  </section>
</template>

<style scoped>
.code-editor-panel {
  width: 100%;
  height: 100%;
  min-height: 240px;
  background: var(--bif-surface);
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

.code-editor-panel__unavailable,
.code-editor-panel__detached {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 1rem;
  color: var(--p-text-muted-color);
  text-align: center;
}

.code-editor-panel__unavailable-detail {
  max-width: min(48rem, 100%);
  color: var(--p-text-color);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  overflow-wrap: anywhere;
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
