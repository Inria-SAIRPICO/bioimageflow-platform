<script setup lang="ts">
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import type { WorkflowInfo } from '@/api/types'

defineProps<{
  visible: boolean
  workflow: WorkflowInfo | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: []
}>()
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    header="Delete workflow"
    :style="{ width: '420px' }"
    data-testid="delete-workflow-dialog"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="delete-body">
      <i class="pi pi-exclamation-triangle" aria-hidden="true" />
      <div>
        <p>
          Delete
          <strong>{{ workflow?.display_name ?? workflow?.name }}</strong>?
        </p>
        <small>
          The workflow file and server-managed output cache will be removed.
          Browser auto-save for this workflow is cleared after the server confirms deletion.
        </small>
      </div>
    </div>

    <template #footer>
      <Button label="Cancel" text @click="emit('update:visible', false)" />
      <Button
        label="Delete"
        severity="danger"
        icon="pi pi-trash"
        data-testid="delete-workflow-confirm"
        @click="emit('confirm')"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.delete-body {
  align-items: flex-start;
  display: flex;
  gap: 1rem;
}
.delete-body i {
  color: var(--p-red-500);
  font-size: 1.5rem;
  margin-top: 0.25rem;
}
.delete-body p {
  margin-top: 0;
}
.delete-body small {
  color: var(--p-text-muted-color);
}
</style>
