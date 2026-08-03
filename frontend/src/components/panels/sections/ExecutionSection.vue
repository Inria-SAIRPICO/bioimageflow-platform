<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import Textarea from 'primevue/textarea'
import type { Settings } from '@/stores/settings'
import ExecutionProfilesSection from './ExecutionProfilesSection.vue'

const props = defineProps<{ modelValue: Settings }>()
const emit = defineEmits<{
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

const trustedFactories = computed(() => {
  const value = (props.modelValue as Settings & {
    trusted_parsl_factories?: string[]
  }).trusted_parsl_factories
  return Array.isArray(value) ? value : []
})

const profilesEditable = computed(() => props.modelValue.deployment_mode === 'desktop')
const trustedFactoriesText = ref('')

watch(trustedFactories, value => {
  trustedFactoriesText.value = value.join('\n')
}, { immediate: true })

function saveTrustedFactories(): void {
  const values = [...new Set(
    trustedFactoriesText.value
      .split(/\r?\n/)
      .map(value => value.trim())
      .filter(Boolean),
  )]
  emit('update:field', {
    field: 'trusted_parsl_factories' as keyof Settings,
    value: values,
  })
}
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

    <div class="field" data-testid="trusted-parsl-factories">
      <span class="field-label">Trusted Parsl configuration factories</span>
      <Textarea
        v-model="trustedFactoriesText"
        rows="4"
        :readonly="!profilesEditable"
        placeholder="package.module:build_config"
      />
      <small>One importable module:callable reference per line. Secrets remain environment-variable references.</small>
      <Button
        v-if="profilesEditable"
        label="Save trusted factories"
        severity="secondary"
        size="small"
        @click="saveTrustedFactories"
      />
    </div>

    <ExecutionProfilesSection
      :trusted-factories="trustedFactories"
      :editable="profilesEditable"
    />
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
