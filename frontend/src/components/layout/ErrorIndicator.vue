<script setup lang="ts">
import { computed } from 'vue'
import { useErrorStore } from '@/stores/errors'

const errorStore = useErrorStore()

const visible = computed(() => errorStore.errors.length > 0)
const unread = computed(() => errorStore.unreadCount)
const state = computed<'unread' | 'dismissed'>(() =>
  unread.value > 0 ? 'unread' : 'dismissed',
)
const badgeText = computed(() => (unread.value > 9 ? '9+' : String(unread.value)))
const tooltip = computed(() =>
  unread.value > 0 ? `Errors (${unread.value})` : 'Error history',
)

const emit = defineEmits<{
  open: []
}>()

function onClick() {
  emit('open')
}
</script>

<template>
  <button
    v-if="visible"
    class="error-indicator"
    :data-state="state"
    :title="tooltip"
    type="button"
    @click="onClick"
  >
    <i class="pi pi-exclamation-circle" />
    <span v-if="unread > 0" class="unread-badge">{{ badgeText }}</span>
  </button>
</template>

<style scoped>
.error-indicator {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  position: relative;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  border-radius: 6px;
  color: var(--p-yellow-500, #ca8a04);
}

.error-indicator[data-state='unread'] {
  color: var(--p-red-500, #dc2626);
}

.error-indicator:hover {
  background: var(--p-surface-100, rgba(0, 0, 0, 0.05));
}

.error-indicator .pi {
  font-size: 1.1rem;
}

.unread-badge {
  position: absolute;
  top: -2px;
  right: -2px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: var(--p-red-500, #dc2626);
  color: white;
  font-size: 0.7rem;
  line-height: 16px;
  text-align: center;
  font-weight: 600;
}
</style>
