<script setup lang="ts">
import { computed } from 'vue'
import type { Settings } from '@/api/types'

const props = defineProps<{ modelValue: Settings }>()
defineEmits<{
  (e: 'update:field', payload: { field: keyof Settings; value: unknown }): void
}>()

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
