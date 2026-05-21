<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { DockviewApi, DockviewPanelApi } from 'dockview-core'

type Disposable = {
  dispose: () => void
}

type AvivatorTabParams = {
  api: DockviewPanelApi
  containerApi: DockviewApi
}

const props = defineProps<{
  params: AvivatorTabParams
}>()

const title = ref(props.params.api.title ?? 'Avivator')
const locationType = ref(props.params.api.location.type)
const pending = ref(false)
const disposables: Disposable[] = []

const isPopout = computed(() => locationType.value === 'popout')
const windowToggleLabel = computed(() => (
  isPopout.value ? 'Close window' : 'Open in separate window'
))
const windowToggleIcon = computed(() => (
  isPopout.value ? 'pi pi-window-minimize' : 'pi pi-external-link'
))

function syncLocation() {
  locationType.value = props.params.api.location.type
}

function avivatorPanel() {
  return props.params.containerApi.getPanel(props.params.api.id)
}

async function toggleWindow() {
  if (pending.value) return
  if (props.params.api.location.type === 'popout') {
    props.params.api.location.getWindow().close()
    return
  }
  const panel = avivatorPanel()
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
  <div class="dv-default-tab avivator-tab" data-testid="avivator-tab">
    <div class="dv-default-tab-content avivator-tab__title">
      {{ title }}
    </div>
    <button
      class="avivator-tab__action"
      type="button"
      :title="windowToggleLabel"
      :aria-label="windowToggleLabel"
      :disabled="pending"
      data-testid="avivator-tab-window-toggle"
      @pointerdown.stop.prevent
      @click.stop.prevent="toggleWindow"
    >
      <i :class="windowToggleIcon" aria-hidden="true" />
    </button>
    <button
      class="avivator-tab__action"
      type="button"
      title="Close"
      aria-label="Close Avivator"
      data-testid="avivator-tab-close"
      @pointerdown.stop.prevent
      @click.stop.prevent="closePanel"
    >
      <i class="pi pi-times" aria-hidden="true" />
    </button>
  </div>
</template>

<style scoped>
.avivator-tab {
  gap: 0.25rem;
  min-width: 0;
}

.avivator-tab__title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.avivator-tab__action {
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

.avivator-tab__action:hover {
  background: var(--dv-icon-hover-background-color);
}

.avivator-tab__action:disabled {
  opacity: 0.55;
  cursor: wait;
}
</style>
