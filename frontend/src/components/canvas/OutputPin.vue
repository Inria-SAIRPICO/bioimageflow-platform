<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { getTypeColor } from '@/utils/typeColors'

const props = withDefaults(defineProps<{
  fieldName: string
  fieldType: string
  placeholder?: boolean
}>(), {
  placeholder: false,
})

const color = computed(() => getTypeColor(props.fieldType))

const tooltip = computed(() => {
  if (props.fieldType === 'any') return '? (runtime-typed)'
  return props.fieldType
})
</script>

<template>
  <div
    class="output-pin"
    :class="{ 'output-pin--placeholder': placeholder, 'output-pin--any': fieldType === 'any' }"
    :title="tooltip"
  >
    <span class="pin-label">{{ fieldName }}</span>
    <span class="type-badge">{{ fieldType === 'any' ? '?' : fieldType }}</span>
    <Handle
      type="source"
      :position="Position.Right"
      :id="fieldName"
      class="pin-handle"
      :style="{ backgroundColor: color, borderColor: color }"
    />
  </div>
</template>

<style scoped>
.output-pin {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  position: relative;
  padding: 2px 0;
}

.output-pin--placeholder {
  pointer-events: none;
  opacity: 0.5;
}

.output-pin--placeholder .pin-handle {
  border-style: dashed !important;
  background-color: transparent !important;
}

.output-pin--any .type-badge {
  background: rgba(176, 160, 96, 0.2);
}

.pin-label {
  font-size: 12px;
  white-space: nowrap;
}

.type-badge {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 4px;
  background: rgba(128, 128, 128, 0.2);
}

.pin-handle {
  width: 14px !important;
  height: 14px !important;
  border-radius: 50% !important;
  border: 2px solid !important;
  position: relative !important;
  transform: none !important;
}
</style>
