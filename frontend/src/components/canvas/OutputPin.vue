<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { getTypeColor } from '@/utils/typeColors'

const props = defineProps<{
  fieldName: string
  fieldType: string
}>()

const color = computed(() => getTypeColor(props.fieldType))
</script>

<template>
  <div class="output-pin" :title="fieldType">
    <span class="pin-label">{{ fieldName }}</span>
    <span class="type-badge">{{ fieldType }}</span>
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
  right: -7px !important;
  transform: none !important;
}
</style>
