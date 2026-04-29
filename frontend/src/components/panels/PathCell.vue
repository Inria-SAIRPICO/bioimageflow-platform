<script setup lang="ts">
import { computed } from 'vue'
import Button from 'primevue/button'
import { useToast } from 'primevue/usetoast'
import { api } from '@/api/client'
import { useSettingsStore } from '@/stores/settings'

const props = defineProps<{ value: string }>()

const settingsStore = useSettingsStore()
let toast: ReturnType<typeof useToast> | null = null
try {
  toast = useToast()
} catch {
  toast = null
}

const filename = computed(() => {
  const normalized = props.value.replace(/\\/g, '/')
  const parts = normalized.split('/').filter(Boolean)
  return parts.length > 0 ? parts[parts.length - 1] : props.value
})

const hasEditor = computed(() => {
  const editor = settingsStore.settings?.external_editor
  return typeof editor === 'string' && editor.trim() !== ''
})

function showError(detail: string) {
  toast?.add({ severity: 'error', summary: 'Action failed', detail, life: 3000 })
}

async function openEditor() {
  if (!hasEditor.value) return
  try {
    await api.post('/api/v1/editor/open', { path: props.value })
  } catch (exc: any) {
    if (exc?.response?.status === 404) {
      await navigator.clipboard?.writeText(props.value)
      toast?.add({ severity: 'info', summary: 'Path copied to clipboard', life: 3000 })
      return
    }
    showError(exc?.response?.data?.detail ?? exc?.message ?? 'Could not open path')
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
  <div class="path-cell">
    <span
      class="path-cell__name"
      :title="value"
    >{{ filename }}</span>
    <Button
      icon="pi pi-file-edit"
      text
      size="small"
      title="Configure an external editor in Settings"
      :disabled="!hasEditor"
      data-testid="path-open"
      @click="openEditor"
    />
    <Button
      icon="pi pi-folder-open"
      text
      size="small"
      title="Reveal in file browser"
      data-testid="path-reveal"
      @click="reveal"
    />
  </div>
</template>

<style scoped>
.path-cell {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  min-width: 180px;
}

.path-cell__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}
</style>
