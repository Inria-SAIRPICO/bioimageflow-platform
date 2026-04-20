<script setup lang="ts">
import { computed } from 'vue'
import { getBezierPath, Position } from '@vue-flow/core'
import { getTypeColor } from '@/utils/typeColors'

const props = defineProps<{
  id: string
  sourceX: number
  sourceY: number
  targetX: number
  targetY: number
  sourcePosition: Position
  targetPosition: Position
  data?: { type?: string }
}>()

const path = computed(() => {
  const [d] = getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    sourcePosition: props.sourcePosition,
    targetX: props.targetX,
    targetY: props.targetY,
    targetPosition: props.targetPosition,
  })
  return d
})

const strokeColor = computed(() => {
  return getTypeColor(props.data?.type ?? '')
})
</script>

<template>
  <path
    :d="path"
    stroke="transparent"
    stroke-width="12"
    fill="none"
    class="vue-flow__edge-interaction"
  />
  <path
    :id="id"
    class="vue-flow__edge-path"
    :d="path"
    :stroke="strokeColor"
    stroke-width="2"
    fill="none"
  />
</template>
