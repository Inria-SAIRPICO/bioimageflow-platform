<script setup lang="ts">
import { computed, ref } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import { useToast } from 'primevue/usetoast'
import { useExecutionStore } from '@/stores/execution'
import { useToolRegistryStore } from '@/stores/toolRegistry'

const executionStore = useExecutionStore()
const toolRegistry = useToolRegistryStore()

let toast: ReturnType<typeof useToast> | null = null
try {
  toast = useToast()
} catch {
  toast = null
}

const deleting = ref(false)
const deleteError = ref<string | null>(null)

const action = computed(() => executionStore.environmentRecoveryAction)
const visible = computed(() => executionStore.isEnvironmentRecoveryDialogVisible)

function dismiss() {
  deleteError.value = null
  executionStore.dismissEnvironmentRecovery()
}

function onVisibilityChange(nextVisible: boolean) {
  if (!nextVisible) dismiss()
}

async function deleteEnvironment() {
  if (action.value === null || deleting.value) return
  deleting.value = true
  deleteError.value = null
  try {
    await toolRegistry.deleteEnvironment(action.value)
    executionStore.dismissEnvironmentRecovery()
    toast?.add({
      severity: 'success',
      summary: 'Environment deleted',
      detail: 'Retry the run to recreate the environment with the requested recipe.',
      life: 6000,
    })
  } catch (e: unknown) {
    deleteError.value = e instanceof Error ? e.message : String(e)
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    header="Recreate environment?"
    :style="{ width: '34rem' }"
    data-testid="environment-recovery-dialog"
    @update:visible="onVisibilityChange"
  >
    <div v-if="action" class="environment-recovery-dialog__body">
      <p>
        Environment <strong>{{ action.envName }}</strong> already exists, but it
        was created from a different recipe than this run requested.
      </p>
      <p>
        Delete the existing environment. Retry the run and BioImageFlow will
        recreate it with the requested recipe.
      </p>
      <dl class="environment-recovery-dialog__details">
        <template v-if="action.path">
          <dt>Path</dt>
          <dd>{{ action.path }}</dd>
        </template>
        <template v-if="action.existingHash">
          <dt>Existing hash</dt>
          <dd>{{ action.existingHash }}</dd>
        </template>
        <template v-if="action.requestedHash">
          <dt>Requested hash</dt>
          <dd>{{ action.requestedHash }}</dd>
        </template>
      </dl>
      <p
        v-if="deleteError"
        class="environment-recovery-dialog__error"
        data-testid="environment-recovery-error"
      >
        {{ deleteError }}
      </p>
    </div>

    <template #footer>
      <Button
        label="Cancel"
        severity="secondary"
        data-testid="environment-recovery-cancel"
        :disabled="deleting"
        @click="dismiss"
      />
      <Button
        label="Delete environment"
        severity="danger"
        data-testid="environment-recovery-delete"
        :loading="deleting"
        @click="deleteEnvironment"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.environment-recovery-dialog__body {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.environment-recovery-dialog__body p {
  margin: 0;
}

.environment-recovery-dialog__details {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: 0.35rem 0.75rem;
  margin: 0;
  font-size: 0.85rem;
}

.environment-recovery-dialog__details dt {
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}

.environment-recovery-dialog__details dd {
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
  font-family: ui-monospace, monospace;
}

.environment-recovery-dialog__error {
  color: var(--p-red-700, #b91c1c);
}
</style>
