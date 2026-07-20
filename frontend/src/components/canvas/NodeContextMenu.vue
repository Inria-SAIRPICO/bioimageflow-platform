<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

const props = defineProps<{
  nodeId: string
  position: { x: number; y: number }
  enabled: boolean
  canOpenNestedWorkflow?: boolean
  hasWorkspaceSource?: boolean
}>()

const emit = defineEmits<{
  'enable-toggle': []
  'rename': []
  'delete': []
  'group-into-workflow': []
  'open-workflow': []
  'open-source-workflow': []
  'update-from-source': []
  'detach-source': []
  'close': []
}>()

function onNestedWorkflowAction() {
  if (props.canOpenNestedWorkflow) {
    emit('open-workflow')
  } else {
    emit('group-into-workflow')
  }
}

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
  // Canvas controls may stop bubbling mouse events, so observe outside clicks
  // during capture before they can be intercepted.
  document.addEventListener('mousedown', onClickOutside, true)
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  document.removeEventListener('mousedown', onClickOutside, true)
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
      <li @click="emit('rename')">
        Rename
      </li>
      <li @click="emit('enable-toggle')">
        {{ enabled ? 'Disable' : 'Enable' }}
      </li>
      <li @click="onNestedWorkflowAction">
        {{ canOpenNestedWorkflow ? 'Open workflow' : 'Group into workflow' }}
      </li>
      <template v-if="hasWorkspaceSource">
        <li @click="emit('open-source-workflow')">
          Open source workflow
        </li>
        <li @click="emit('update-from-source')">
          Update from source
        </li>
        <li @click="emit('detach-source')">
          Detach from source
        </li>
      </template>
      <li @click="emit('delete')">
        Delete
      </li>
    </ul>
  </div>
</template>

<style scoped>
.node-context-menu {
  position: absolute;
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  padding: 4px 0;
  z-index: 100;
  min-width: 160px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
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
  color: var(--p-text-color);
}

li:hover {
  background: var(--bif-surface-hover);
}
</style>
