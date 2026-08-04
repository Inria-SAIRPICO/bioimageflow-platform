<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import SelectButton from 'primevue/selectbutton'
import ToggleSwitch from 'primevue/toggleswitch'
import type {
  ExecutionJobSnapshot,
  ExecutionRetryPlan,
  RecomputeRequest,
} from '@/api/executions'

const props = defineProps<{
  visible: boolean
  jobs: ExecutionJobSnapshot[]
  initialMode: 'retry' | 'recompute'
  initialNodePath?: string | null
  plan: ExecutionRetryPlan | null
  planning?: boolean
  starting?: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  cancel: []
  preview: [recompute: RecomputeRequest | null]
  confirm: [planDigest: string]
}>()

const mode = ref<'retry' | 'recompute'>('retry')
const selectedNodePaths = ref<string[]>([])
const cascade = ref(true)
const editing = ref(false)

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    mode.value = props.initialMode
    selectedNodePaths.value = props.initialNodePath ? [props.initialNodePath] : []
    cascade.value = true
    editing.value = props.initialMode === 'recompute'
  },
  { immediate: true },
)

watch(
  () => props.plan?.plan_digest,
  (digest) => {
    if (digest) editing.value = false
  },
)

const sortedJobs = computed(() => [...props.jobs].sort((left, right) => (
  left.scoped_node_path.localeCompare(right.scoped_node_path)
)))
const canPreview = computed(() => (
  mode.value === 'retry' || selectedNodePaths.value.length > 0
))
const showEditor = computed(() => editing.value || (!props.plan && !props.planning))

function toggleNode(path: string, checked: boolean): void {
  const selected = new Set(selectedNodePaths.value)
  if (checked) selected.add(path)
  else selected.delete(path)
  selectedNodePaths.value = [...selected]
}

function preview(): void {
  if (!canPreview.value) return
  emit('preview', mode.value === 'retry'
    ? null
    : { node_paths: [...selectedNodePaths.value], cascade: cascade.value })
}
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    header="Retry execution"
    :closable="!planning && !starting"
    :style="{ width: 'min(46rem, 95vw)' }"
    data-testid="execution-retry-dialog"
    @update:visible="(next: boolean) => { if (!next) emit('cancel') }"
  >
    <div v-if="error" class="retry-alert" role="alert" data-testid="retry-plan-error">
      {{ error }}
    </div>

    <div v-if="planning" class="retry-loading" data-testid="retry-plan-loading">
      <i class="pi pi-spin pi-spinner" /> Preparing an immutable retry preview…
    </div>

    <template v-else-if="showEditor">
      <p>Choose an ordinary retry or explicitly invalidate selected node results before retrying.</p>
      <SelectButton
        v-model="mode"
        :options="[
          { label: 'Retry cached work', value: 'retry' },
          { label: 'Recompute nodes', value: 'recompute' },
        ]"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        data-testid="retry-mode"
      />

      <section v-if="mode === 'recompute'" class="recompute-options">
        <strong>Scoped nodes</strong>
        <div class="node-choices" data-testid="recompute-node-choices">
          <label v-for="job in sortedJobs" :key="job.scoped_node_path">
            <input
              type="checkbox"
              :checked="selectedNodePaths.includes(job.scoped_node_path)"
              :value="job.scoped_node_path"
              @change="toggleNode(job.scoped_node_path, ($event.target as HTMLInputElement).checked)"
            />
            <code>{{ job.scoped_node_path }}</code>
          </label>
        </div>
        <label class="cascade-choice">
          <ToggleSwitch v-model="cascade" input-id="retry-cascade" />
          Recompute downstream dependants
        </label>
      </section>
    </template>

    <template v-else-if="plan">
      <div class="immutable-warning" data-testid="retry-immutable-warning">
        This child run uses the parent’s original immutable workflow, inputs, resources, and target.
        Later draft or target edits are not included.
      </div>
      <dl class="retry-summary">
        <dt>New execution</dt><dd><code>{{ plan.child_execution_id }}</code></dd>
        <dt>Target</dt><dd>{{ plan.target.label }} · {{ plan.target.mode }}</dd>
        <dt>Mode</dt><dd>{{ plan.mode }}</dd>
        <dt>Plan digest</dt><dd><code>{{ plan.plan_digest }}</code></dd>
      </dl>

      <section v-if="plan.recompute" data-testid="retry-recompute-summary">
        <strong>Recompute</strong>
        <p>
          {{ plan.recompute.node_paths.join(', ') }}
          <span v-if="plan.recompute.cascade">and downstream dependants</span>
        </p>
      </section>

      <section>
        <strong>Cache selections to invalidate</strong>
        <p v-if="plan.invalidations.length === 0">None. Valid cached work will be reused.</p>
        <ul v-else class="invalidation-list" data-testid="retry-invalidations">
          <li v-for="item in plan.invalidations" :key="`${item.node_path}-${item.result_key}`">
            <code>{{ item.node_path }}</code>
            <span>{{ item.selection_status }}</span>
            <small>{{ item.result_key }}</small>
          </li>
        </ul>
      </section>

      <div
        v-if="plan.conflicting_run_ids.length > 0"
        class="retry-alert"
        role="alert"
        data-testid="retry-conflicts"
      >
        Active conflicting executions: {{ plan.conflicting_run_ids.join(', ') }}
      </div>
      <div v-else-if="!plan.confirmable" class="retry-alert" role="alert">
        {{ plan.disabled_reason ?? 'This retry plan cannot be confirmed.' }}
      </div>
    </template>

    <template #footer>
      <Button label="Cancel" text :disabled="planning || starting" @click="emit('cancel')" />
      <Button
        v-if="plan && !showEditor"
        label="Change selection"
        text
        :disabled="starting"
        @click="editing = true"
      />
      <Button
        v-if="showEditor"
        label="Preview"
        icon="pi pi-search"
        :disabled="!canPreview || planning"
        data-testid="preview-execution-retry"
        @click="preview"
      />
      <Button
        v-else-if="plan"
        label="Confirm and start"
        icon="pi pi-play"
        :loading="starting"
        :disabled="!plan.confirmable || plan.conflicting_run_ids.length > 0"
        data-testid="confirm-execution-retry"
        @click="emit('confirm', plan.plan_digest)"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.retry-alert { margin-bottom: 0.75rem; padding: 0.65rem; border-radius: 6px; color: var(--p-red-600); background: var(--p-red-50); }
.immutable-warning { margin-bottom: 0.75rem; padding: 0.65rem; border-radius: 6px; color: var(--p-orange-700); background: var(--p-orange-50); }
.retry-loading { display: flex; align-items: center; justify-content: center; gap: 0.5rem; min-height: 8rem; }
.recompute-options { margin-top: 1rem; display: grid; gap: 0.65rem; }
.node-choices { max-height: 13rem; overflow: auto; border: 1px solid var(--p-content-border-color); border-radius: 6px; }
.node-choices label { display: flex; align-items: center; gap: 0.5rem; padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--p-content-border-color); }
.cascade-choice { display: flex; align-items: center; gap: 0.5rem; }
.retry-summary { display: grid; grid-template-columns: 8rem minmax(0, 1fr); gap: 0.45rem; }
.retry-summary dt { color: var(--p-text-muted-color); }
.retry-summary dd { margin: 0; overflow-wrap: anywhere; }
.invalidation-list { padding: 0; list-style: none; }
.invalidation-list li { display: grid; grid-template-columns: minmax(8rem, 1fr) auto; gap: 0.25rem 0.75rem; padding: 0.4rem 0; border-bottom: 1px solid var(--p-content-border-color); }
.invalidation-list small { grid-column: 1 / -1; overflow-wrap: anywhere; color: var(--p-text-muted-color); }
</style>
