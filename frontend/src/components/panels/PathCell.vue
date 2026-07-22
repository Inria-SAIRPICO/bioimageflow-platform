<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import Button from 'primevue/button'
import { useToast } from 'primevue/usetoast'
import { api } from '@/api/client'

const props = withDefaults(defineProps<{
  value: string
  showActions?: boolean
}>(), {
  showActions: true,
})

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

const editing = ref(false)
const input = ref<HTMLInputElement | null>(null)

function showError(detail: string) {
  toast?.add({ severity: 'error', summary: 'Action failed', detail, life: 3000 })
}

async function editPath() {
  editing.value = true
  await nextTick()
  input.value?.focus()
  input.value?.select()
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
      <input
        v-if="editing"
        ref="input"
        class="path-cell__input"
        data-testid="path-input"
        :value="value"
        readonly
        :title="value"
        @blur="editing = false"
        @keydown.escape="editing = false"
      >
      <button
        v-else
        class="path-cell__path"
        type="button"
        :title="value"
        data-testid="path-display"
        style="text-align: right"
        @click="editPath"
      >
        {{ value }}
      </button>
      <span class="path-cell__name">{{ filename }}</span>
    </div>
    <template v-if="showActions">
      <Button
        icon="pi pi-folder-open"
        text
        size="small"
        title="Reveal in file browser"
        data-testid="path-reveal"
        @click="reveal"
      />
      <Button
        icon="pi pi-copy"
        text
        size="small"
        title="Copy path"
        data-testid="path-copy"
        @click="copyPath"
      />
    </template>
  </div>
</template>

<style scoped>
.path-cell {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  width: 100%;
  min-width: 0;
}

.path-cell__text {
  min-width: 0;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.path-cell__path {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
  max-width: 100%;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: text;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 0.8125rem;
  padding: 0;
  direction: ltr;
  text-align: right !important;
}

.path-cell__input {
  width: 100%;
  max-width: min(520px, 48vw);
  border: 1px solid var(--p-primary-color);
  border-radius: 4px;
  background: var(--bif-surface);
  color: var(--p-text-color);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 0.8125rem;
  padding: 0.125rem 0.25rem;
  direction: ltr;
  text-align: right;
}

.path-cell__name {
  color: var(--p-text-muted-color);
  font-size: 0.75rem;
  text-align: right;
}
</style>
