<script setup lang="ts">
import { computed, toRef } from 'vue'
import { getBezierPath, Position } from '@vue-flow/core'
import { useEdgeError } from '@/composables/useEdgeError'
import type { GraphValidationError } from '@/api/types'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  id: string
  sourceX: number
  sourceY: number
  targetX: number
  targetY: number
  sourcePosition: Position
  targetPosition: Position
  data?: { errors?: GraphValidationError[] }
}>()

const geometry = computed(() => {
  const [path, labelX, labelY] = getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    sourcePosition: props.sourcePosition,
    targetX: props.targetX,
    targetY: props.targetY,
    targetPosition: props.targetPosition,
  })
  return { path, labelX, labelY }
})

const { hasError, errorTitle } = useEdgeError(toRef(props, 'data'))
const strokeColor = computed(() =>
  hasError.value ? 'var(--p-red-500)' : '#7A7A80',
)
</script>

<template>
  <path
    :d="geometry.path"
    stroke="transparent"
    stroke-width="14"
    fill="none"
    class="vue-flow__edge-interaction"
  />
  <path
    :id="id"
    :class="['vue-flow__edge-path', { 'edge-error': hasError }]"
    :d="geometry.path"
    :stroke="strokeColor"
    stroke-width="2.5"
    fill="none"
  >
    <title>{{ hasError ? errorTitle : 'Whole DataFrame' }}</title>
  </path>
  <g
    class="dataframe-edge-badge"
    :transform="`translate(${geometry.labelX - 8} ${geometry.labelY - 7})`"
    pointer-events="none"
  >
    <rect width="16" height="14" rx="2" :stroke="strokeColor" fill="var(--p-surface-0)" />
    <path d="M 1 5 H 15 M 1 9 H 15 M 6 1 V 13 M 11 1 V 13" :stroke="strokeColor" />
    <title>Whole DataFrame</title>
  </g>
</template>
