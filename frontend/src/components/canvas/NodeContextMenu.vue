<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

const props = defineProps<{
  nodeId: string
  position: { x: number; y: number }
  enabled: boolean
}>()

const emit = defineEmits<{
  'enable-toggle': []
  'delete': []
  'create-sub-workflow': []
  'close': []
}>()

const menuRef = ref<HTMLElement | null>(null)

function onClickOutside(event: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(event.target as Node)) {
    emit('close')
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    emit('close')
  }
}

onMounted(() => {
  document.addEventListener('mousedown', onClickOutside)
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  document.removeEventListener('mousedown', onClickOutside)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div
    ref="menuRef"
    class="node-context-menu"
    :style="{ left: `${position.x}px`, top: `${position.y}px` }"
  >
    <ul>
      <li @click="emit('enable-toggle')">
        {{ enabled ? 'Disable' : 'Enable' }}
      </li>
      <li @click="emit('create-sub-workflow')">
        Create Sub-workflow
      </li>
      <li @click="emit('delete')">
        Delete
      </li>
    </ul>
  </div>
</template>

<style scoped>
.node-context-menu {
  position: absolute;
  background: #2a2a2a;
  border: 1px solid #555;
  border-radius: 6px;
  padding: 4px 0;
  z-index: 100;
  min-width: 160px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

ul {
  list-style: none;
  margin: 0;
  padding: 0;
}

li {
  padding: 6px 14px;
  cursor: pointer;
  font-size: 13px;
  color: #eee;
}

li:hover {
  background: #444;
}
</style>
