<script setup lang="ts">
import { computed } from 'vue'
import type { GraphValidationError } from '@/api/types'

const props = defineProps<{
  errors: GraphValidationError[]
}>()

let _idCounter = 0
function nextId(): string {
  _idCounter += 1
  return `param-error-${_idCounter}`
}
const descId = nextId()

const hasError = computed(() => props.errors.length > 0)
const joinedTitle = computed(() =>
  props.errors.map((e) => e.detail).join('\n'),
)
</script>

<template>
  <div
    :class="['parameter-field-error', { 'has-error': hasError }]"
    :aria-invalid="hasError ? 'true' : undefined"
    :aria-describedby="hasError ? descId : undefined"
    :title="hasError ? joinedTitle : undefined"
  >
    <slot />
    <ul
      v-if="hasError"
      :id="descId"
      data-testid="param-error-desc"
      class="param-error-desc"
    >
      <li v-for="(err, i) in errors" :key="i">{{ err.detail }}</li>
    </ul>
  </div>
</template>

<style scoped>
.parameter-field-error {
  position: relative;
}

.has-error :deep(input),
.has-error :deep(.p-inputtext),
.has-error :deep(.p-select),
.has-error :deep(.p-checkbox-box),
.has-error :deep(.p-slider) {
  border-color: var(--p-red-500, #dc2626) !important;
  box-shadow: 0 0 0 2px
    color-mix(in srgb, var(--p-red-500, #dc2626) 20%, transparent);
}

.param-error-desc {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}
</style>
