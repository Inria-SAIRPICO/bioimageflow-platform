<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import type { DockviewApi, DockviewPanelApi } from 'dockview-core'
import { useUIStore } from '@/stores/ui'
import {
  closeCodeEditorWindow,
  hasCodeEditorWindowBridge,
  isDesktop,
  openCodeEditorWindow,
} from '@/utils/nativeDialogs'

type Disposable = {
  dispose: () => void
}

type CodeEditorTabParams = {
  api: DockviewPanelApi
  containerApi: DockviewApi
}

const props = defineProps<{
  params: CodeEditorTabParams
}>()

const uiStore = useUIStore()
const { codeEditorUrl, codeEditorPath, codeEditorOpening, codeEditorDetached } =
  storeToRefs(uiStore)
const title = ref(props.params.api.title ?? 'Code Editor')
const locationType = ref(props.params.api.location.type)
const pending = ref(false)
const disposables: Disposable[] = []

const editorTitle = computed(() => (
  codeEditorPath.value ? `Code editor - ${codeEditorPath.value}` : 'Code editor'
))
const hasEditor = computed(() => Boolean(codeEditorUrl.value) && !codeEditorOpening.value)
const isPopout = computed(() => locationType.value === 'popout')
const isDetachedDesktopEditor = computed(() => codeEditorDetached.value && isDesktop())
const showWindowToggle = computed(() => {
  if (isPopout.value) return true
  if (isDetachedDesktopEditor.value) return hasCodeEditorWindowBridge()
  return hasEditor.value && (!isDesktop() || hasCodeEditorWindowBridge())
})
const windowToggleLabel = computed(() => (
  isPopout.value || isDetachedDesktopEditor.value
    ? 'Close window'
    : 'Open in separate window'
))
const windowToggleIcon = computed(() => (
  isPopout.value || isDetachedDesktopEditor.value
    ? 'pi pi-window-minimize'
    : 'pi pi-external-link'
))

function syncLocation() {
  locationType.value = props.params.api.location.type
}

function codeEditorPanel() {
  return props.params.containerApi.getPanel(props.params.api.id)
}

async function toggleWindow() {
  if (pending.value) return
  if (props.params.api.location.type === 'popout') {
    props.params.api.location.getWindow().close()
    return
  }
  if (codeEditorDetached.value) {
    pending.value = true
    try {
      await closeCodeEditorWindow()
      uiStore.setCodeEditorDetached(false)
    } finally {
      pending.value = false
    }
    return
  }
  if (!codeEditorUrl.value) return
  if (hasCodeEditorWindowBridge()) {
    pending.value = true
    try {
      const opened = await openCodeEditorWindow(codeEditorUrl.value, editorTitle.value)
      if (opened) {
        uiStore.setCodeEditorDetached(true)
      }
    } finally {
      pending.value = false
    }
    return
  }
  const panel = codeEditorPanel()
  if (!panel) return
  pending.value = true
  try {
    await props.params.containerApi.addPopoutGroup(panel, { popoutUrl: '/popout.html' })
  } finally {
    pending.value = false
  }
}

function closePanel() {
  props.params.api.close()
}

onMounted(() => {
  disposables.push(
    props.params.api.onDidTitleChange((event) => {
      title.value = event.title
    }),
    props.params.api.onDidLocationChange(syncLocation),
  )
})

onBeforeUnmount(() => {
  disposables.splice(0).forEach((disposable) => disposable.dispose())
})
</script>

<template>
  <div class="dv-default-tab code-editor-tab" data-testid="code-editor-tab">
    <div class="dv-default-tab-content code-editor-tab__title">
      {{ title }}
    </div>
    <button
      v-if="showWindowToggle"
      class="code-editor-tab__action"
      type="button"
      :title="windowToggleLabel"
      :aria-label="windowToggleLabel"
      :disabled="pending"
      data-testid="code-editor-tab-window-toggle"
      @pointerdown.stop.prevent
      @click.stop.prevent="toggleWindow"
    >
      <i :class="windowToggleIcon" aria-hidden="true" />
    </button>
    <button
      class="code-editor-tab__action"
      type="button"
      title="Close"
      aria-label="Close Code Editor"
      data-testid="code-editor-tab-close"
      @pointerdown.stop.prevent
      @click.stop.prevent="closePanel"
    >
      <i class="pi pi-times" aria-hidden="true" />
    </button>
  </div>
</template>

<style scoped>
.code-editor-tab {
  gap: 0.25rem;
  min-width: 0;
}

.code-editor-tab__title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.code-editor-tab__action {
  flex: 0 0 auto;
  width: 1.375rem;
  height: 1.375rem;
  display: inline-grid;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 3px;
  color: inherit;
  background: transparent;
  cursor: pointer;
}

.code-editor-tab__action:hover {
  background: var(--dv-icon-hover-background-color);
}

.code-editor-tab__action:disabled {
  opacity: 0.45;
  cursor: default;
}

.code-editor-tab__action .pi {
  font-size: 0.75rem;
}
</style>
