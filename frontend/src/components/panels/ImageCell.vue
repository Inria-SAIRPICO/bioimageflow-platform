<script setup lang="ts">
import { computed, ref } from 'vue'
import Button from 'primevue/button'
import { useToast } from 'primevue/usetoast'
import { api } from '@/api/client'

const props = defineProps<{
  nodeId: string
  row: number
  col: string
  value: string
}>()

let toast: ReturnType<typeof useToast> | null = null
try {
  toast = useToast()
} catch {
  toast = null
}

const napariDisabled = ref(false)
const thumbnailFailed = ref(false)

const colSlug = computed(() => props.col.replace(/[^a-zA-Z0-9_-]/g, '_') || '_')
const thumbnailUrl = computed(() => {
  const node = encodeURIComponent(props.nodeId)
  const col = encodeURIComponent(props.col)
  return `/api/v1/nodes/${node}/thumbnail?row=${props.row}&col=${col}&size=128`
})

function showError(detail: string) {
  toast?.add({ severity: 'error', summary: 'Action failed', detail, life: 3000 })
}

async function openNapari(event: MouseEvent) {
  if (napariDisabled.value) return
  try {
    await api.post('/api/v1/napari/open', {
      paths: [props.value],
      clear_layers: event.ctrlKey || event.metaKey,
    })
  } catch (exc: any) {
    const status = exc?.response?.status
    if (status === 404 || status === 503) {
      napariDisabled.value = true
      toast?.add({
        severity: 'warn',
        summary: 'Napari integration not available',
        life: 3000,
      })
      return
    }
    showError(exc?.response?.data?.detail ?? exc?.message ?? 'Could not open in Napari')
  }
}

async function reveal() {
  try {
    await api.post('/api/v1/fs/reveal', { path: props.value })
  } catch (exc: any) {
    showError(exc?.response?.data?.detail ?? exc?.message ?? 'Could not reveal file')
  }
}
</script>

<template>
  <div class="image-cell">
    <img
      v-if="!thumbnailFailed"
      class="image-cell__thumb"
      :src="thumbnailUrl"
      loading="lazy"
      alt=""
      @error="thumbnailFailed = true"
    >
    <div
      v-else
      class="image-cell__placeholder"
      aria-label="thumbnail unavailable"
    />
    <div class="image-cell__actions">
      <Button
        icon="pi pi-image"
        text
        size="small"
        title="Open in Napari"
        :disabled="napariDisabled"
        :data-testid="`open-napari-${row}-${colSlug}`"
        @click="openNapari"
      />
      <Button
        icon="pi pi-folder-open"
        text
        size="small"
        title="Reveal in file browser"
        :data-testid="`reveal-${row}-${colSlug}`"
        @click="reveal"
      />
    </div>
  </div>
</template>

<style scoped>
.image-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 150px;
}

.image-cell__thumb,
.image-cell__placeholder {
  width: 48px;
  height: 48px;
  object-fit: contain;
  border: 1px solid var(--p-surface-300);
  background: var(--p-surface-100);
}

.image-cell__placeholder {
  position: relative;
}

.image-cell__placeholder::before,
.image-cell__placeholder::after {
  content: "";
  position: absolute;
  left: 10px;
  right: 10px;
  top: 23px;
  border-top: 2px solid var(--p-text-muted-color);
}

.image-cell__placeholder::before {
  transform: rotate(45deg);
}

.image-cell__placeholder::after {
  transform: rotate(-45deg);
}

.image-cell__actions {
  display: flex;
  gap: 0.125rem;
}
</style>
