<script setup lang="ts">
import { computed } from 'vue'
import Button from 'primevue/button'
import { useToast } from 'primevue/usetoast'
import { api } from '@/api/client'
import { openPathWithEditor } from '@/api/editor'

const props = defineProps<{ value: string }>()

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

function showError(detail: string) {
  toast?.add({ severity: 'error', summary: 'Action failed', detail, life: 3000 })
}

async function openEditor() {
  try {
    await openPathWithEditor(props.value, toast)
  } catch (exc: any) {
    showError(exc?.response?.data?.detail ?? exc?.message ?? 'Could not open path')
  }
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
    await api.post('/api/v1/fs/reveal', { path: props.value })
  } catch (exc: any) {
    showError(exc?.response?.data?.detail ?? exc?.message ?? 'Could not reveal file')
  }
}
</script>

<template>
  <div class="path-cell">
    <div class="path-cell__text">
      <span
        class="path-cell__path"
        :title="value"
      >{{ value }}</span>
      <span class="path-cell__name">{{ filename }}</span>
    </div>
    <Button
      icon="pi pi-copy"
      text
      size="small"
      title="Copy path"
      data-testid="path-copy"
      @click="copyPath"
    />
    <Button
      icon="pi pi-file-edit"
      text
      size="small"
      title="Open in editor"
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
  min-width: 260px;
}

.path-cell__text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.path-cell__path {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 320px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 0.8125rem;
}

.path-cell__name {
  color: var(--p-text-muted-color);
  font-size: 0.75rem;
}
</style>
