<script setup lang="ts">
import { computed, onMounted } from 'vue'
import Select from 'primevue/select'
import type { Settings } from '@/stores/settings'
import { useExecutionRegistryStore } from '@/stores/executionRegistry'
import ExecutionProfilesSection from './ExecutionProfilesSection.vue'

const props = defineProps<{ modelValue: Settings }>()
const emit = defineEmits<{
  (e: 'update:field', payload: { field: keyof Settings; value: unknown }): void
}>()
const executionRegistry = useExecutionRegistryStore()

const distributedSettings = computed(() => props.modelValue as Settings & {
  new_workflow_execution?: 'sequential' | 'parallel'
  default_execution_target_id?: string
})
const schedulingOptions = [
  { label: 'Sequential', value: 'sequential' },
  { label: 'Parallel', value: 'parallel' },
]
const targetOptions = computed(() => executionRegistry.targets.map(target => ({
  label: target.enabled ? target.label : `${target.label} — unavailable`,
  value: target.id,
  disabled: !target.enabled,
})))

const backendLabel = computed(() => {
  const engine = props.modelValue.engine
  if (engine === 'wetlands') return 'Wetlands'
  if (engine === 'direct') return 'Direct'
  return 'Automatic'
})

const schedulingLabel = computed(() => {
  const execution = props.modelValue.execution
  if (execution === 'parallel') return 'Parallel'
  if (execution === 'sequential') return 'Sequential'
  const legacyExecution = props.modelValue.execution_engine as string
  return legacyExecution === 'parallel' || legacyExecution === 'parsl'
    ? 'Parallel'
    : 'Sequential'
})

const profilesEditable = computed(() => props.modelValue.deployment_mode === 'desktop')

function updateExecutionPreference(field: string, value: unknown): void {
  emit('update:field', { field: field as keyof Settings, value })
}

onMounted(() => void executionRegistry.loadTargets())
</script>

<template>
  <div class="settings-section">
    <div class="field" data-testid="execution-runtime-summary">
      <span class="field-label">Execution backend</span>
      <span class="value" data-testid="execution-backend-value">{{ backendLabel }}</span>
    </div>

    <div class="field">
      <span class="field-label">Scheduling</span>
      <span class="value" data-testid="execution-scheduling-value">
        {{ schedulingLabel }}
      </span>
    </div>

    <div class="field">
      <label class="field-label" for="new-workflow-execution">New workflow scheduling</label>
      <Select
        id="new-workflow-execution"
        :model-value="distributedSettings.new_workflow_execution ?? 'sequential'"
        :options="schedulingOptions"
        option-label="label"
        option-value="value"
        @update:model-value="updateExecutionPreference('new_workflow_execution', $event)"
      />
      <small>Controls whether newly created workflows start with sequential or parallel scheduling.</small>
    </div>

    <div class="field">
      <label class="field-label" for="default-execution-target">Default execution target</label>
      <Select
        id="default-execution-target"
        :model-value="distributedSettings.default_execution_target_id ?? 'local'"
        :options="targetOptions"
        option-label="label"
        option-value="value"
        option-disabled="disabled"
        @update:model-value="updateExecutionPreference('default_execution_target_id', $event)"
      />
      <small>Local remains available even when optional distributed runtimes are unavailable.</small>
    </div>

    <ExecutionProfilesSection :editable="profilesEditable" />
  </div>
</template>

<style scoped>
.settings-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.field-label {
  font-weight: 600;
}
.value {
  color: var(--p-text-muted-color, #666);
}
</style>
