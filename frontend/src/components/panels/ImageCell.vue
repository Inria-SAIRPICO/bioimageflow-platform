<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
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
const blobUrl = ref<string | null>(null)
const fetchFailed = ref(false)

// Backoff schedule for "pending" retries. ~30 s total budget across 5
// retries — enough for most renders to finish without hammering the
// server. The frontend gives up after this; the user can scroll away
// and back to retrigger.
const RETRY_DELAYS_MS = [1_000, 2_000, 4_000, 8_000, 15_000]

const colSlug = computed(() => props.col.replace(/[^a-zA-Z0-9_-]/g, '_') || '_')
const baseUrl = computed(
  () =>
    `/api/v1/nodes/${encodeURIComponent(props.nodeId)}/thumbnail` +
    `?row=${props.row}&col=${encodeURIComponent(props.col)}&size=128`,
)

let abort: AbortController | null = null
let retryTimer: ReturnType<typeof setTimeout> | null = null
let retryAttempt = 0

function clearTimer() {
  if (retryTimer !== null) {
    clearTimeout(retryTimer)
    retryTimer = null
  }
}

function revokeBlob() {
  if (blobUrl.value !== null) {
    try {
      URL.revokeObjectURL(blobUrl.value)
    } catch {
      // jsdom or stub may throw; safe to ignore
    }
    blobUrl.value = null
  }
}

async function fetchThumbnail() {
  abort?.abort()
  abort = new AbortController()
  const versioned = `${baseUrl.value}&_v=${retryAttempt}`
  try {
    const response = await fetch(versioned, { signal: abort.signal })
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    const status = response.headers.get('X-Thumbnail-Status')
    const blob = await response.blob()
    revokeBlob()
    blobUrl.value = URL.createObjectURL(blob)
    fetchFailed.value = false

    if (status === 'pending' && retryAttempt < RETRY_DELAYS_MS.length) {
      const delay = RETRY_DELAYS_MS[retryAttempt]
      retryAttempt += 1
      clearTimer()
      retryTimer = setTimeout(() => {
        retryTimer = null
        void fetchThumbnail()
      }, delay)
    } else {
      // Either ready, or exhausted retries — stop polling.
      clearTimer()
    }
  } catch (exc) {
    if ((exc as DOMException)?.name === 'AbortError') return
    revokeBlob()
    fetchFailed.value = true
    clearTimer()
  }
}

function reset() {
  clearTimer()
  abort?.abort()
  abort = null
  revokeBlob()
  fetchFailed.value = false
  retryAttempt = 0
  void fetchThumbnail()
}

watch(
  () => `${props.nodeId}::${props.row}::${props.col}::${props.value}`,
  () => reset(),
  { immediate: true },
)

onBeforeUnmount(() => {
  clearTimer()
  abort?.abort()
  abort = null
  revokeBlob()
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
      v-if="blobUrl !== null && !fetchFailed"
      class="image-cell__thumb"
      :src="blobUrl"
      alt=""
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
