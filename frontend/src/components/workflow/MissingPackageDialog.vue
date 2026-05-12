<script setup lang="ts">
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import type { MissingPackage, MissingTool } from '@/api/types'

defineProps<{
  visible: boolean
  packages: MissingPackage[]
  tools: MissingTool[]
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  rebind: []
}>()
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    header="Workflow dependencies"
    :style="{ width: '640px' }"
    data-testid="missing-package-dialog"
    @update:visible="emit('update:visible', $event)"
  >
    <section v-if="packages.length" class="dependency-section">
      <h3>Missing package versions</h3>
      <div
        v-for="pkg in packages"
        :key="`${pkg.package_name}-${pkg.required_version}`"
        class="dependency-card"
      >
        <strong>{{ pkg.package_name }} {{ pkg.required_version }}</strong>
        <span>
          Installed: {{ pkg.installed_versions?.length ? pkg.installed_versions.join(', ') : 'none' }}
        </span>
        <small>Affected nodes: {{ pkg.affected_nodes?.join(', ') || 'unknown' }}</small>
      </div>
    </section>

    <section v-if="tools.length" class="dependency-section">
      <h3>Missing tools</h3>
      <div
        v-for="tool in tools"
        :key="tool.node_id"
        class="dependency-card"
      >
        <strong>{{ tool.tool_name }}</strong>
        <span>Node: {{ tool.node_id }}</span>
        <small v-if="tool.package_name">
          {{ tool.package_name }} {{ tool.required_version ?? '' }}
        </small>
      </div>
    </section>

    <p v-if="!packages.length && !tools.length" class="empty">
      This workflow has no missing package or tool metadata.
    </p>

    <template #footer>
      <Button label="Close" text @click="emit('update:visible', false)" />
      <Button
        label="Use installed versions"
        icon="pi pi-refresh"
        :disabled="packages.length === 0"
        data-testid="missing-package-rebind"
        @click="emit('rebind')"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.dependency-section {
  display: grid;
  gap: 0.6rem;
  margin-bottom: 1rem;
}
.dependency-section h3 {
  margin: 0;
}
.dependency-card {
  background: var(--bif-surface-muted);
  border: 1px solid var(--p-content-border-color);
  border-left: 4px solid var(--p-orange-500);
  border-radius: 10px;
  display: grid;
  gap: 0.15rem;
  padding: 0.75rem 0.9rem;
}
.dependency-card span,
.dependency-card small,
.empty {
  color: var(--p-text-muted-color);
}
</style>
