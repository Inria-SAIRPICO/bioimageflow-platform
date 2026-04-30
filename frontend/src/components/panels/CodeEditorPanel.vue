<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useUIStore } from '@/stores/ui'

const uiStore = useUIStore()
const { codeEditorUrl, codeEditorPath } = storeToRefs(uiStore)
const failed = ref(false)

const available = computed(() => Boolean(codeEditorUrl.value) && !failed.value)
</script>

<template>
  <section class="code-editor-panel" data-testid="code-editor-panel">
    <iframe
      v-if="available"
      class="code-editor-panel__frame"
      data-testid="code-editor-iframe"
      :src="codeEditorUrl ?? undefined"
      :title="codeEditorPath ? `Code editor - ${codeEditorPath}` : 'Code editor'"
      @error="failed = true"
    />
    <div v-else class="code-editor-panel__unavailable" data-testid="code-editor-unavailable">
      code-server is not available. Configure an external editor in Settings.
    </div>
  </section>
</template>

<style scoped>
.code-editor-panel {
  width: 100%;
  height: 100%;
  min-height: 240px;
  background: var(--p-surface-0);
}

.code-editor-panel__frame {
  display: block;
  width: 100%;
  height: 100%;
  border: 0;
}

.code-editor-panel__unavailable {
  height: 100%;
  display: grid;
  place-items: center;
  padding: 1rem;
  color: var(--p-text-muted-color);
  text-align: center;
}
</style>
