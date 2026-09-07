<script setup lang="ts">
import { computed, useId } from 'vue'
import { useVueFlow } from '@vue-flow/core'

const { viewport } = useVueFlow()
// SVG fragment references decode percent escapes. Keep encoded workflow paths
// out of pattern IDs so workflows in folders retain their background.
const patternId = `canvas-grid-${useId().replace(/[^a-zA-Z0-9_-]/g, '-')}`
const gap = computed(() => 16 * viewport.value.zoom)
</script>

<template>
  <svg class="vue-flow__background vue-flow__container" aria-hidden="true">
    <defs>
      <pattern
        :id="patternId"
        :x="viewport.x % gap"
        :y="viewport.y % gap"
        :width="gap"
        :height="gap"
        patternUnits="userSpaceOnUse"
      >
        <circle :cx="gap / 2" :cy="gap / 2" :r="viewport.zoom / 2" fill="currentColor" />
      </pattern>
    </defs>
    <rect width="100%" height="100%" :fill="`url(#${patternId})`" />
  </svg>
</template>

<style scoped>
.vue-flow__background {
  color: #81818a;
  pointer-events: none;
}
</style>
