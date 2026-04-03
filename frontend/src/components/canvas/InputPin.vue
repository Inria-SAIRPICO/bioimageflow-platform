<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { getTypeColor } from '@/utils/typeColors'

const props = defineProps<{
  fieldName: string
  fieldType: string
  connected: boolean
  sourceLabel?: string
  positional?: boolean
  positionalIndex?: number
}>()

const color = computed(() => getTypeColor(props.fieldType))

const label = computed(() => {
  if (props.positional && props.positionalIndex != null) {
    return String(props.positionalIndex + 1)
  }
  if (props.connected && props.sourceLabel) {
    return props.sourceLabel
  }
  return props.fieldName
})
</script>

<template>
  <div class="input-pin" :title="fieldType">
    <Handle
      type="target"
      :position="Position.Left"
      :id="fieldName"
    />
    <span
      class="pin-dot"
      :class="{ connected }"
      :style="{ backgroundColor: color }"
    />
    <span class="pin-label">{{ label }}</span>
  </div>
</template>

<style scoped>
.input-pin {
  display: flex;
  align-items: center;
  gap: 4px;
  position: relative;
  padding: 2px 0;
}

.pin-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.pin-dot.connected {
  box-shadow: 0 0 4px currentColor;
}

.pin-label {
  font-size: 12px;
  white-space: nowrap;
}
</style>
