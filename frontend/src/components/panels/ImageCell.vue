<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import Button from 'primevue/button'
import { useToast } from 'primevue/usetoast'
import { api } from '@/api/client'
import PathCell from './PathCell.vue'

const props = withDefaults(defineProps<{
  nodeId: string
  workflowName?: string | null
  row: number
  col: string
  value: string
  showPath?: boolean
  showImageActions?: boolean
  hideThumbnailFallback?: boolean
}>(), {
  showPath: true,
  showImageActions: true,
  hideThumbnailFallback: false,
})

let toast: ReturnType<typeof useToast> | null = null
try {
  toast = useToast()
} catch {
  toast = null
}

const napariDisabled = ref(false)
const blobUrl = ref<string | null>(null)
const thumbnailPending = ref(false)
const fetchFailed = ref(false)

// Backoff schedule for "pending" retries. ~30 s total budget across 5
// retries — enough for most renders to finish without hammering the
// server. The frontend gives up after this; the user can scroll away
// and back to retrigger.
const RETRY_DELAYS_MS = [1_000, 2_000, 4_000, 8_000, 15_000]
const THUMBNAIL_REQUEST_SIZE = 256
const THUMBNAIL_RENDER_SIZE = 96
const AVIVATOR_HOST = 'avivator.gehlenborglab.org'

const colSlug = computed(() => props.col.replace(/[^a-zA-Z0-9_-]/g, '_') || '_')
const shouldShowPath = computed(() => props.showPath)
const shouldShowImageActions = computed(() => props.showImageActions)
const shouldShowThumbnailFallback = computed(() => !props.hideThumbnailFallback)
const thumbnailStyle = {
  width: `${THUMBNAIL_RENDER_SIZE}px`,
  height: `${THUMBNAIL_RENDER_SIZE}px`,
}
const imageFileName = computed(() => {
  const parts = props.value.split(/[\\/]/).filter(Boolean)
  return parts[parts.length - 1] || 'image'
})
const avivatorImageFileName = computed(() => {
  const name = imageFileName.value
  if (/\.ome\.tiff?$/i.test(name)) {
    return name
  }
  const withoutSuffix = name.replace(/\.[^/.]+$/, '')
  return `${withoutSuffix || 'image'}.ome.tif`
})
const baseUrl = computed(() => {
  const params = new URLSearchParams({
    row: String(props.row),
    col: props.col,
    size: String(THUMBNAIL_REQUEST_SIZE),
  })
  if (props.workflowName && props.workflowName.trim() !== '') {
    params.set('workflow_name', props.workflowName)
  }
  return `/api/v1/nodes/${encodeURIComponent(props.nodeId)}/thumbnail?${params.toString()}`
})
const avivatorApiOrigin = computed(() => {
  const backendHttpUrl = import.meta.env.VITE_BIOIMAGEFLOW_BACKEND_HTTP_URL
  if (import.meta.env.DEV && backendHttpUrl) {
    return new URL(backendHttpUrl).origin
  }
  return window.location.origin
})
const imageUrl = computed(() => {
  const params = new URLSearchParams({
    row: String(props.row),
    col: props.col,
    format: 'ome-tiff',
  })
  if (props.workflowName && props.workflowName.trim() !== '') {
    params.set('workflow_name', props.workflowName)
  }
  return new URL(
    `/api/v1/nodes/${encodeURIComponent(props.nodeId)}/image/${encodeURIComponent(avivatorImageFileName.value)}?${params.toString()}`,
    avivatorApiOrigin.value,
  ).toString()
})
const avivatorUrl = computed(() => {
  const url = new URL(`https://${AVIVATOR_HOST}/`)
  url.searchParams.set('image_url', imageUrl.value)
  return url.toString()
})

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
  thumbnailPending.value = true
  fetchFailed.value = false
  const versioned = `${baseUrl.value}&_v=${retryAttempt}`
  try {
    const response = await fetch(versioned, { signal: abort.signal })
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    const status = response.headers.get('X-Thumbnail-Status')
    if (status === 'pending') {
      revokeBlob()
      fetchFailed.value = false
      if (retryAttempt >= RETRY_DELAYS_MS.length) {
        thumbnailPending.value = false
        fetchFailed.value = true
        clearTimer()
        return
      }
      thumbnailPending.value = true
      const delay = RETRY_DELAYS_MS[retryAttempt]
      retryAttempt += 1
      clearTimer()
      retryTimer = setTimeout(() => {
        retryTimer = null
        void fetchThumbnail()
      }, delay)
      return
    }

    const blob = await response.blob()
    revokeBlob()
    blobUrl.value = URL.createObjectURL(blob)
    thumbnailPending.value = false
    fetchFailed.value = false
    clearTimer()
  } catch (exc) {
    if ((exc as DOMException)?.name === 'AbortError') return
    revokeBlob()
    thumbnailPending.value = false
    fetchFailed.value = true
    clearTimer()
  }
}

function reset() {
  clearTimer()
  abort?.abort()
  abort = null
  revokeBlob()
  thumbnailPending.value = false
  fetchFailed.value = false
  retryAttempt = 0
  void fetchThumbnail()
}

watch(
  () =>
    `${props.nodeId}::${props.workflowName ?? ''}::${props.row}::${props.col}::${props.value}`,
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
      node_id: props.nodeId,
      row: props.row,
      col: props.col,
      workflow_name: props.workflowName ?? null,
    })
  } catch (exc: any) {
    const status = exc?.response?.status
    if (status === 404) {
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

function openAvivator() {
  window.dispatchEvent(new CustomEvent('bioimageflow:open-avivator', {
    detail: {
      url: avivatorUrl.value,
      imageUrl: imageUrl.value,
      title: avivatorImageFileName.value,
    },
  }))
}

async function copyPath() {
  try {
    await navigator.clipboard?.writeText(props.value)
    toast?.add({ severity: 'info', summary: 'Path copied to clipboard', life: 3000 })
  } catch (exc: any) {
    showError(exc?.message ?? 'Could not copy path')
  }
}

async function reveal() {
  try {
    const params = new URLSearchParams({
      row: String(props.row),
      col: props.col,
    })
    if (props.workflowName && props.workflowName.trim() !== '') {
      params.set('workflow_name', props.workflowName)
    }
    await api.post(`/api/v1/nodes/${encodeURIComponent(props.nodeId)}/reveal?${params.toString()}`)
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
      data-testid="image-thumbnail"
      :src="blobUrl"
      :style="thumbnailStyle"
      alt=""
    >
    <div
      v-else-if="thumbnailPending && shouldShowThumbnailFallback"
      class="image-cell__pending"
      data-testid="image-thumbnail"
      aria-label="thumbnail generating"
      :style="thumbnailStyle"
    />
    <div
      v-else-if="shouldShowThumbnailFallback"
      class="image-cell__unavailable"
      data-testid="image-thumbnail"
      aria-label="thumbnail unavailable"
      :style="thumbnailStyle"
    />
    <PathCell
      v-if="shouldShowPath"
      :value="value"
      :show-actions="false"
    />
    <div class="image-cell__actions">
      <Button
        v-if="shouldShowImageActions"
        icon="pi pi-image"
        text
        size="small"
        title="Open in Napari"
        :disabled="napariDisabled"
        :data-testid="`open-napari-${row}-${colSlug}`"
        @click="openNapari"
      />
      <Button
        v-if="shouldShowImageActions"
        icon="pi pi-external-link"
        text
        size="small"
        title="Open in Avivator"
        :data-testid="`open-avivator-${row}-${colSlug}`"
        @click="openAvivator"
      />
      <Button
        icon="pi pi-folder-open"
        text
        size="small"
        title="Reveal in file browser"
        :data-testid="`reveal-${row}-${colSlug}`"
        @click="reveal"
      />
      <Button
        v-if="shouldShowPath"
        icon="pi pi-copy"
        text
        size="small"
        title="Copy path"
        data-testid="path-copy"
        @click="copyPath"
      />
    </div>
  </div>
</template>

<style scoped>
.image-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 450px;
}

.image-cell__thumb,
.image-cell__pending,
.image-cell__unavailable {
  object-fit: contain;
  border: 1px solid var(--bif-border-strong);
  background: var(--bif-surface-hover);
  flex: 0 0 auto;
}

.image-cell__pending,
.image-cell__unavailable {
  position: relative;
}

.image-cell__pending::before {
  content: "";
  position: absolute;
  inset: 8px;
  border: 3px solid var(--bif-border-strong);
  border-top-color: var(--p-primary-color);
  border-radius: 999px;
  animation: image-cell-spin 0.9s linear infinite;
}

.image-cell__unavailable::before,
.image-cell__unavailable::after {
  content: "";
  position: absolute;
  left: 10px;
  right: 10px;
  top: 23px;
  border-top: 2px solid var(--p-text-muted-color);
}

.image-cell__unavailable::before {
  transform: rotate(45deg);
}

.image-cell__unavailable::after {
  transform: rotate(-45deg);
}

@keyframes image-cell-spin {
  to {
    transform: rotate(360deg);
  }
}

.image-cell__actions {
  display: flex;
  gap: 0.125rem;
}
</style>
