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

const schedulingOptions = [
  { label: 'Sequential', value: 'sequential' },
  { label: 'Parallel', value: 'parallel' },
]
const targetOptions = computed(() => executionRegistry.targets.map(target => ({
  label: target.enabled ? target.label : `${target.label} — unavailable`,
  value: target.id,
  disabled: !target.enabled,
})))

const profilesEditable = computed(() => props.modelValue.deployment_mode === 'desktop')

function updateExecutionPreference(field: string, value: unknown): void {
  emit('update:field', { field: field as keyof Settings, value })
}

onMounted(() => void executionRegistry.loadTargets())
</script>

<template>
  <div class="settings-section">
    <div class="field">
      <label class="field-label" for="new-workflow-execution">New workflow scheduling</label>
      <Select
        id="new-workflow-execution"
        :model-value="props.modelValue.new_workflow_execution"
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
        :model-value="props.modelValue.default_execution_target_id"
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
