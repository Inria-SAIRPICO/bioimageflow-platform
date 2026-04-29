<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import Checkbox from 'primevue/checkbox'
import type { Settings } from '@/api/types'

const props = defineProps<{ modelValue: Settings }>()
const emit = defineEmits<{
  (e: 'update:field', payload: { field: keyof Settings; value: unknown }): void
}>()

const engine = computed({
  get: () => props.modelValue.execution_engine ?? 'sequential',
  set: (value: 'sequential' | 'parsl') =>
    emit('update:field', { field: 'execution_engine', value }),
})

const engineOptions = [
  { label: 'Sequential', value: 'sequential' },
  { label: 'Parsl (parallel)', value: 'parsl' },
]

// PrimeVue InputNumber can't naturally distinguish "empty" from `0`, so we
// pair it with an "Unlimited" checkbox: checked → null, unchecked → integer.
const unlimited = ref<boolean>(props.modelValue.cache_max_executions === null)
const cacheCount = ref<number>(props.modelValue.cache_max_executions ?? 0)

watch(
  () => props.modelValue.cache_max_executions,
  (value) => {
    unlimited.value = value === null || value === undefined
    cacheCount.value = value ?? 0
  },
)

function toggleUnlimited(checked: boolean) {
  unlimited.value = checked
  emit('update:field', {
    field: 'cache_max_executions',
    value: checked ? null : cacheCount.value,
  })
}

function commitCacheCount(value: number | null | undefined) {
  if (unlimited.value) return
  const next = typeof value === 'number' && value >= 0 ? value : 0
  cacheCount.value = next
  emit('update:field', { field: 'cache_max_executions', value: next })
}

const cacheAge = ref<string>(props.modelValue.cache_max_age ?? '')

watch(
  () => props.modelValue.cache_max_age,
  (value) => {
    cacheAge.value = value ?? ''
  },
)

function commitCacheAge() {
  const trimmed = cacheAge.value.trim()
  emit('update:field', {
    field: 'cache_max_age',
    value: trimmed === '' ? null : trimmed,
  })
}
</script>

<template>
  <div class="settings-section">
    <div class="field">
      <label class="field-label" for="execution-engine-select">Execution engine</label>
      <Select
        id="execution-engine-select"
        v-model="engine"
        :options="engineOptions"
        option-label="label"
        option-value="value"
        data-testid="execution-engine-select"
      />
    </div>

    <div class="field">
      <label class="field-label">Cache: max executions per node</label>
      <div class="row">
        <Checkbox
          v-model="unlimited"
          :binary="true"
          data-testid="cache-unlimited-checkbox"
          input-id="cache-unlimited"
          @change="toggleUnlimited(unlimited)"
        />
        <label for="cache-unlimited" class="checkbox-label">Unlimited</label>
      </div>
      <InputNumber
        v-if="!unlimited"
        v-model="cacheCount"
        :min="0"
        :step="1"
        data-testid="cache-max-executions-input"
        show-buttons
        @update:model-value="commitCacheCount"
      />
      <p class="help-text">
        Number of past executions to keep per node. <code>0</code> deletes prior
        results when a new run completes.
      </p>
    </div>

    <div class="field">
      <label class="field-label" for="cache-max-age-input">Cache: max age</label>
      <InputText
        id="cache-max-age-input"
        v-model="cacheAge"
        placeholder="30d"
        data-testid="cache-max-age-input"
        @blur="commitCacheAge"
        @keydown.enter="commitCacheAge"
      />
      <p class="help-text">
        <code>s</code>/<code>m</code>/<code>h</code>/<code>d</code>, e.g.
        <code>30d</code>; empty = unlimited.
      </p>
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
.row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.checkbox-label {
  cursor: pointer;
}
.help-text {
  margin: 0;
  color: var(--p-text-muted-color, #888);
  font-size: 0.85rem;
}
</style>
