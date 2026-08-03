<script setup lang="ts">
import { computed } from 'vue'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import type { ToolMetadata } from '@/api/types'
import { useExecutionRegistryStore } from '@/stores/executionRegistry'

type ResourceKey = 'cpu' | 'gpu' | 'memory' | 'gpu_memory' | 'max_concurrent'

const props = defineProps<{
  resources: Record<string, unknown>
  tool: ToolMetadata | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  change: [resources: Record<string, number | string>]
}>()

const registry = useExecutionRegistryStore()
const fields: Array<{
  key: ResourceKey
  label: string
  kind: 'count' | 'capacity'
  min?: number
}> = [
  { key: 'cpu', label: 'CPU cores', kind: 'count', min: 1 },
  { key: 'gpu', label: 'GPUs', kind: 'count', min: 0 },
  { key: 'memory', label: 'Memory', kind: 'capacity' },
  { key: 'gpu_memory', label: 'GPU memory', kind: 'capacity' },
  { key: 'max_concurrent', label: 'Maximum concurrent jobs', kind: 'count', min: 0 },
]

const declared = computed<Record<string, unknown>>(() => {
  const environment = props.tool?.environment as Record<string, unknown> | null | undefined
  const resources = environment?.resources
  return typeof resources === 'object' && resources !== null
    ? resources as Record<string, unknown>
    : {}
})

function declaredValue(key: ResourceKey): number | string | null {
  const aliases: Record<ResourceKey, string[]> = {
    cpu: ['cpu', 'cpus'],
    gpu: ['gpu', 'gpus'],
    memory: ['memory'],
    gpu_memory: ['gpu_memory'],
    max_concurrent: ['max_concurrent'],
  }
  for (const alias of aliases[key]) {
    const value = declared.value[alias]
    if (typeof value === 'number' || typeof value === 'string') return value
  }
  return null
}

function numericOverride(key: ResourceKey): number | null {
  const value = props.resources[key]
  return typeof value === 'number' ? value : null
}

function capacityOverride(key: ResourceKey): string {
  const value = props.resources[key]
  return typeof value === 'string' ? value : ''
}

function effectiveValue(key: ResourceKey): number | string | null {
  const override = props.resources[key]
  return typeof override === 'number' || typeof override === 'string'
    ? override
    : declaredValue(key)
}

function setOverride(key: ResourceKey, value: number | string | null): void {
  const next = Object.fromEntries(
    Object.entries(props.resources).filter(([, entry]) => (
      typeof entry === 'number' || typeof entry === 'string'
    )),
  ) as Record<string, number | string>
  if (value === null || value === '') delete next[key]
  else next[key] = value
  emit('change', next)
}

function resetAll(): void {
  emit('change', {})
}

const targetMessage = computed(() => {
  const target = registry.selectedTarget
  if (!target) return 'No execution target selected.'
  if (!target.enabled) return target.disabled_reason ?? 'This target is unavailable.'
  if (target.mode === 'local') {
    return 'Local execution uses these values where supported by the selected local engine.'
  }
  return `BioImageFlow will validate these requirements against ${target.label} during preflight.`
})
</script>

<template>
  <section class="resources-tab" data-testid="node-resources-tab">
    <div class="resources-toolbar">
      <div>
        <h4>Worker resources</h4>
        <small>Overrides apply to this node invocation only.</small>
      </div>
      <Button
        label="Reset all"
        icon="pi pi-undo"
        text
        size="small"
        :disabled="disabled || Object.keys(resources).length === 0"
        data-testid="resource-reset-all"
        @click="resetAll"
      />
    </div>

    <div class="resource-grid resource-grid--header" aria-hidden="true">
      <span>Resource</span><span>Declared</span><span>Override</span><span>Effective</span>
    </div>
    <div v-for="field in fields" :key="field.key" class="resource-grid">
      <label :for="`resource-${field.key}`">{{ field.label }}</label>
      <span class="resource-readonly">{{ declaredValue(field.key) ?? '—' }}</span>
      <InputNumber
        v-if="field.kind === 'count'"
        :input-id="`resource-${field.key}`"
        :model-value="numericOverride(field.key)"
        :min="field.min"
        :max-fraction-digits="0"
        :disabled="disabled"
        placeholder="Inherit"
        size="small"
        :data-testid="`resource-override-${field.key}`"
        @update:model-value="setOverride(field.key, $event)"
      />
      <InputText
        v-else
        :id="`resource-${field.key}`"
        :model-value="capacityOverride(field.key)"
        :disabled="disabled"
        placeholder="Inherit (for example 32GB)"
        size="small"
        :data-testid="`resource-override-${field.key}`"
        @update:model-value="setOverride(field.key, ($event ?? '').trim())"
      />
      <strong>{{ effectiveValue(field.key) ?? '—' }}</strong>
    </div>

    <div class="target-compatibility" data-testid="resource-target-compatibility">
      <i class="pi pi-info-circle" />
      <span>{{ targetMessage }}</span>
    </div>
  </section>
</template>

<style scoped>
.resources-tab { display: flex; flex-direction: column; gap: 0.75rem; }
.resources-toolbar { display: flex; align-items: start; justify-content: space-between; gap: 0.5rem; }
.resources-toolbar h4 { margin: 0 0 0.2rem; }
.resources-toolbar small { color: var(--p-text-muted-color); }
.resource-grid { display: grid; grid-template-columns: minmax(8rem, 1fr) 4rem minmax(8rem, 1fr) 4rem; gap: 0.5rem; align-items: center; }
.resource-grid--header { color: var(--p-text-muted-color); font-size: 0.72rem; text-transform: uppercase; }
.resource-readonly { color: var(--p-text-muted-color); }
.target-compatibility { display: flex; gap: 0.5rem; padding: 0.65rem; border-radius: 6px; background: var(--p-surface-100); color: var(--p-text-muted-color); }
@media (max-width: 420px) {
  .resource-grid { grid-template-columns: 1fr 1fr; }
  .resource-grid--header { display: none; }
}
</style>
