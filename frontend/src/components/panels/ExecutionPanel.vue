<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import ProgressBar from 'primevue/progressbar'
import SelectButton from 'primevue/selectbutton'
import Tag from 'primevue/tag'
import ExecutionRetryDialog from '@/components/execution/ExecutionRetryDialog.vue'
import {
  applyExecutionCleanup,
  downloadExecutionResults,
  executionErrorCode,
  executionErrorDetails,
  executionErrorMessage,
  executionResultErrorMessage,
  planExecutionCleanup,
  type ExecutionActionAvailability,
  type ExecutionCleanupPlan,
  type ExecutionActions,
  type ExecutionJobSnapshot,
  type ExecutionRetryPlan,
  type RecomputeRequest,
} from '@/api/executions'
import { useExecutionRegistryStore } from '@/stores/executionRegistry'
import { useUIStore } from '@/stores/ui'

const registry = useExecutionRegistryStore()
const ui = useUIStore()
const scope = ref<'workflow' | 'workspace'>('workflow')
const selectedJobId = ref<string | null>(null)
const retryDialogVisible = ref(false)
const retryInitialMode = ref<'retry' | 'recompute'>('retry')
const retryInitialNodePath = ref<string | null>(null)
const retryParentId = ref<string | null>(null)
const retryPlan = ref<ExecutionRetryPlan | null>(null)
const retryPlanning = ref(false)
const retryStarting = ref(false)
const retryError = ref<string | null>(null)
const resultDownloadingId = ref<string | null>(null)
const resultError = ref<string | null>(null)
const cleanupPlan = ref<ExecutionCleanupPlan | null>(null)
const cleanupPlanning = ref(false)
const cleanupApplying = ref(false)
const cleanupError = ref<string | null>(null)
const cleanupMessage = ref<string | null>(null)
let reloadTimer: ReturnType<typeof setInterval> | null = null

const unavailableAction: ExecutionActionAvailability = {
  available: false,
  reason: 'The retained execution is unavailable.',
}

const retryParentRun = computed(() => (
  registry.runs.find(run => run.id === retryParentId.value) ?? null
))

const selectedJob = computed(() => (
  registry.selectedRun?.jobs.find(job => job.id === selectedJobId.value) ?? null
))

watch(() => registry.selectedRunId, () => {
  selectedJobId.value = null
  resultError.value = null
  cleanupError.value = null
  cleanupMessage.value = null
})
watch([scope, () => ui.activeWorkflowId], () => void loadRuns())
onMounted(() => {
  void loadRuns()
  reloadTimer = setInterval(() => void reloadActiveRuns(), 5000)
})
onUnmounted(() => {
  if (reloadTimer !== null) clearInterval(reloadTimer)
})

async function loadRuns(): Promise<void> {
  await registry.loadRuns(scope.value === 'workflow' ? ui.activeWorkflowId : null)
}

async function reloadActiveRuns(): Promise<void> {
  if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
  await Promise.allSettled(registry.activeRuns.map(run => registry.refreshRun(run.id)))
}

function stateSeverity(state: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' {
  if (state === 'succeeded' || state === 'cached') return 'success'
  if (state === 'failed' || state === 'lost') return 'danger'
  if (state === 'running') return 'info'
  if (state.includes('cancel')) return 'warn'
  return 'secondary'
}

function progressValue(job: ExecutionJobSnapshot): number | null {
  const progress = job.progress
  if (!progress || progress.total <= 0) return null
  return Math.round((progress.current / progress.total) * 100)
}

function indent(job: ExecutionJobSnapshot): number {
  return Math.max(0, job.scoped_node_path.split('/').length - 1)
}

function duration(job: ExecutionJobSnapshot): string {
  if (job.duration_seconds == null) return '—'
  if (job.duration_seconds < 60) return `${job.duration_seconds.toFixed(1)}s`
  return `${Math.floor(job.duration_seconds / 60)}m ${Math.round(job.duration_seconds % 60)}s`
}

function resourceSummary(job: ExecutionJobSnapshot): string {
  const value = job.resources
  if (!value) return '—'
  return [
    value.cpu != null ? `${value.cpu} CPU` : null,
    value.gpu != null && value.gpu > 0 ? `${value.gpu} GPU` : null,
    value.memory_bytes != null ? formatBytes(value.memory_bytes) : null,
    value.gpu_memory_bytes != null ? `${formatBytes(value.gpu_memory_bytes)} GPU` : null,
    value.max_concurrent != null && value.max_concurrent > 0
      ? `max ${value.max_concurrent}`
      : null,
  ].filter(Boolean).join(' · ') || '—'
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`
  const units = ['KiB', 'MiB', 'GiB', 'TiB']
  let normalized = value / 1024
  let index = 0
  while (normalized >= 1024 && index < units.length - 1) {
    normalized /= 1024
    index += 1
  }
  return `${normalized.toFixed(normalized >= 10 ? 0 : 1)} ${units[index]}`
}

function action(name: keyof ExecutionActions): ExecutionActionAvailability {
  return registry.selectedRun?.actions[name] ?? {
    available: false,
    reason: 'This action is unavailable for the retained execution.',
  }
}

function selectOnCanvas(job: ExecutionJobSnapshot): void {
  const segments = job.scoped_node_path.split('/')
  ui.setSelectedNodes([segments[segments.length - 1]!])
  ui.panels.nodePanel = true
}

function openLogs(job: ExecutionJobSnapshot): void {
  selectOnCanvas(job)
  ui.openLoggerPanel()
}

async function previewCleanup(): Promise<void> {
  const run = registry.selectedRun
  if (!run || !action('cleanup').available) return
  cleanupPlanning.value = true
  cleanupError.value = null
  cleanupMessage.value = null
  try {
    cleanupPlan.value = await planExecutionCleanup(run.id)
  } catch (cause) {
    cleanupError.value = executionErrorMessage(cause, 'Cluster cleanup could not be planned.')
  } finally {
    cleanupPlanning.value = false
  }
}

async function confirmCleanup(): Promise<void> {
  const plan = cleanupPlan.value
  if (!plan) return
  cleanupApplying.value = true
  cleanupError.value = null
  try {
    await applyExecutionCleanup(plan.execution_id, plan.plan_digest)
    cleanupPlan.value = null
    cleanupMessage.value = 'Managed cluster artifacts were cleaned up. The platform history entry is retained.'
  } catch (cause) {
    cleanupError.value = executionErrorMessage(cause, 'Cluster cleanup could not be applied.')
  } finally {
    cleanupApplying.value = false
  }
}

async function downloadResults(id: string): Promise<void> {
  resultDownloadingId.value = id
  resultError.value = null
  try {
    const blob = await downloadExecutionResults(id)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${id}-results.zip`
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (cause) {
    const message = await executionResultErrorMessage(
      cause,
      'The execution results could not be downloaded.',
    )
    if (registry.selectedRunId === id) resultError.value = message
  } finally {
    resultDownloadingId.value = null
  }
}

function openRetry(): void {
  const run = registry.selectedRun
  if (!run || !run.actions.retry.available) return
  retryParentId.value = run.id
  retryInitialMode.value = 'retry'
  retryInitialNodePath.value = null
  retryPlan.value = null
  retryError.value = null
  retryDialogVisible.value = true
  void previewRetry(null)
}

function openRecompute(): void {
  const run = registry.selectedRun
  if (!run || !run.actions.recompute.available || !selectedJob.value) return
  retryParentId.value = run.id
  retryInitialMode.value = 'recompute'
  retryInitialNodePath.value = selectedJob.value.scoped_node_path
  retryPlan.value = null
  retryError.value = null
  retryDialogVisible.value = true
}

async function previewRetry(
  recompute: RecomputeRequest | null,
  preserveError = false,
): Promise<void> {
  const parentId = retryParentId.value
  if (!parentId) return
  retryPlanning.value = true
  if (!preserveError) retryError.value = null
  try {
    retryPlan.value = await registry.planRetry(parentId, recompute)
  } catch (cause) {
    retryPlan.value = null
    retryError.value = executionErrorMessage(cause, 'The retry preview could not be created.')
  } finally {
    retryPlanning.value = false
  }
}

const REPLAN_REQUIRED_CODES = new Set([
  'retry-plan-not-found',
  'retry-plan-integrity-error',
  'retry-child-conflict',
  'retry-conflict',
  'invalid-retry',
  'run-not-found',
  'workflow-run-retry-error',
])

async function confirmRetry(planDigest: string): Promise<void> {
  const parentId = retryParentId.value
  if (!parentId) return
  retryStarting.value = true
  retryError.value = null
  try {
    await registry.startRetry(parentId, planDigest)
    retryDialogVisible.value = false
    retryPlan.value = null
  } catch (cause) {
    const code = executionErrorCode(cause)
    if (code?.includes('uncertain')) {
      const details = executionErrorDetails(cause)
      const retryRunId = details.retry_run_id ?? details.child_execution_id ?? details.run_id
      const plannedRunId = retryPlan.value?.child_execution_id
      if (typeof retryRunId !== 'string' || retryRunId !== plannedRunId) {
        retryError.value = 'The uncertain submission did not identify the confirmed child execution. Do not submit another retry.'
        return
      }
      try {
        await registry.selectExecution(retryRunId)
        retryDialogVisible.value = false
      } catch {
        retryError.value = `Submission of ${retryRunId} is uncertain. Keep this confirmed plan and reload that exact execution; do not submit another retry.`
      }
      return
    }
    if (code && REPLAN_REQUIRED_CODES.has(code)) {
      retryPlan.value = null
      retryError.value = 'The retained execution or cache selection changed. Select Preview to create and review a new plan.'
      return
    }
    retryError.value = executionErrorMessage(cause, 'The retry could not be started.')
  } finally {
    retryStarting.value = false
  }
}

function retryKind(command: string | null | undefined): 'Retry' | 'Recompute' {
  return command === 'recompute' ? 'Recompute' : 'Retry'
}

function childKind(childId: string): string {
  const child = registry.runs.find(run => run.id === childId)
  return child ? retryKind(child.command) : 'Child'
}

function closeRetryDialog(): void {
  if (retryPlanning.value || retryStarting.value) return
  retryDialogVisible.value = false
  retryPlan.value = null
  retryError.value = null
}
</script>

<template>
  <div class="execution-panel" data-testid="panel-execution">
    <header class="execution-toolbar">
      <SelectButton
        v-model="scope"
        :options="[{ label: 'Workflow', value: 'workflow' }, { label: 'Workspace', value: 'workspace' }]"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        size="small"
        data-testid="execution-scope"
      />
      <Button icon="pi pi-refresh" text rounded aria-label="Reload retained runs" title="Reload latest retained observations" :loading="registry.loadingRuns" @click="loadRuns" />
    </header>

    <div v-if="registry.error && registry.runs.length === 0" class="execution-empty">
      {{ registry.error }}
    </div>
    <div v-else-if="registry.runs.length === 0" class="execution-empty">No executions yet.</div>
    <div v-else class="execution-layout">
      <aside class="run-history" aria-label="Execution history">
        <button
          v-for="run in registry.runs"
          :key="run.id"
          type="button"
          :class="['run-card', { 'run-card--active': registry.selectedRun?.id === run.id }]"
          @click="registry.selectedRunId = run.id"
        >
          <span class="run-card__title">{{ run.workflow_name ?? run.workflow_id }}</span>
          <Tag :value="run.state" :severity="stateSeverity(run.state)" />
          <small>{{ run.target_label ?? run.target_id }} · {{ new Date(run.created_at).toLocaleString() }}</small>
          <small v-if="run.retry_of_execution_id" data-testid="execution-history-provenance">
            {{ retryKind(run.command) }} of {{ run.retry_of_execution_id }}
          </small>
        </button>
        <Button
          v-if="registry.hasMoreRuns"
          label="Load more"
          text
          size="small"
          class="load-more"
          :loading="registry.loadingRuns"
          data-testid="execution-load-more"
          @click="registry.loadMoreRuns()"
        />
      </aside>

      <main v-if="registry.selectedRun" class="run-detail">
        <div class="run-summary">
          <div>
            <strong>{{ registry.selectedRun.workflow_name ?? registry.selectedRun.workflow_id }}</strong>
            <small>{{ registry.selectedRun.target_label ?? registry.selectedRun.target_id }}</small>
          </div>
          <Tag :value="registry.selectedRun.state" :severity="stateSeverity(registry.selectedRun.state)" />
          <span><code>{{ registry.selectedRun.id }}</code></span>
          <span v-if="registry.selectedRun.backend">{{ registry.selectedRun.backend.replace(/_/g, ' ') }}</span>
          <span v-if="registry.selectedRun.scheduler_job_id">Scheduler {{ registry.selectedRun.scheduler_job_id }}</span>
          <span v-if="registry.selectedRun.observation_error" class="observation-warning">
            <i class="pi pi-wifi" /> {{ registry.selectedRun.observation_error }}
          </span>
          <div v-if="registry.selectedRun.retry_of_execution_id" class="run-provenance">
            {{ retryKind(registry.selectedRun.command) }} of
            <button type="button" @click="registry.selectExecution(registry.selectedRun.retry_of_execution_id!)">
              {{ registry.selectedRun.retry_of_execution_id }}
            </button>
          </div>
          <div v-if="registry.selectedRun.child_execution_ids.length" class="run-provenance">
            Child runs
            <button
              v-for="childId in registry.selectedRun.child_execution_ids"
              :key="childId"
              type="button"
              @click="registry.selectExecution(childId)"
            >{{ childKind(childId) }} {{ childId }}</button>
          </div>
          <div class="run-actions">
            <Button
              label="Cancel"
              icon="pi pi-stop"
              text
              size="small"
              :disabled="!action('cancel').available"
              :title="action('cancel').reason ?? 'Cancel this execution'"
              data-testid="execution-cancel"
              @click="registry.cancel(registry.selectedRun.id)"
            />
            <Button
              label="Retry"
              icon="pi pi-refresh"
              text
              size="small"
              :disabled="!action('retry').available"
              :title="action('retry').reason ?? 'Retry using retained immutable inputs'"
              data-testid="execution-retry"
              @click="openRetry"
            />
            <Button
              label="Recompute"
              icon="pi pi-replay"
              text
              size="small"
              :disabled="!action('recompute').available || selectedJob === null"
              :title="!action('recompute').available
                ? action('recompute').reason ?? 'Recompute is unavailable'
                : selectedJob === null
                  ? 'Select a job to recompute'
                  : 'Recompute the selected job'"
              data-testid="execution-recompute"
              @click="openRecompute"
            />
            <Button
              label="Results"
              icon="pi pi-download"
              text
              size="small"
              :disabled="!action('download_results').available"
              :title="action('download_results').reason ?? 'Download verified execution results'"
              :loading="resultDownloadingId === registry.selectedRun.id"
              data-testid="execution-results"
              @click="downloadResults(registry.selectedRun.id)"
            />
            <Button
              label="Cleanup"
              icon="pi pi-trash"
              text
              size="small"
              :disabled="!action('cleanup').available"
              :title="action('cleanup').reason ?? 'Plan cleanup of this run’s managed cluster artifacts'"
              :loading="cleanupPlanning"
              data-testid="execution-cleanup"
              @click="previewCleanup"
            />
          </div>
        </div>
        <div v-if="resultError" class="action-error" role="alert" data-testid="execution-result-error">
          {{ resultError }}
        </div>
        <div v-if="cleanupError" class="action-error" role="alert" data-testid="execution-cleanup-error">{{ cleanupError }}</div>
        <div v-if="cleanupMessage" class="action-message" role="status">{{ cleanupMessage }}</div>
        <section v-if="registry.selectedRun.diagnostics?.length" class="cluster-diagnostics" data-testid="execution-cluster-diagnostics">
          <article v-for="(diagnostic, index) in registry.selectedRun.diagnostics" :key="index">
            <strong>{{ diagnostic.phase }} · {{ diagnostic.category }}</strong>
            <span>{{ diagnostic.message }}</span>
            <small v-if="diagnostic.allocation_state">Allocation: {{ diagnostic.allocation_state }}</small>
            <small v-if="diagnostic.retry_safety">Retry safety: {{ diagnostic.retry_safety }}</small>
            <small v-if="diagnostic.next_action">Next action: {{ diagnostic.next_action }}</small>
          </article>
        </section>

        <div class="jobs-table" role="table" aria-label="Execution jobs">
          <div class="job-row job-header" role="row">
            <span>Job</span><span>Status</span><span>Progress</span><span>Executor</span><span>Resources</span><span>Duration</span>
          </div>
          <button
            v-for="job in registry.selectedRun.jobs"
            :key="job.id"
            type="button"
            :class="['job-row', { 'job-row--active': selectedJobId === job.id }]"
            role="row"
            @click="selectedJobId = job.id"
          >
            <span :style="{ paddingLeft: `${indent(job) * 1.1}rem` }" class="job-name">
              {{ job.display_name ?? job.scoped_node_path }}
            </span>
            <Tag :value="job.state" :severity="stateSeverity(job.state)" />
            <span>
              <ProgressBar v-if="progressValue(job) !== null" :value="progressValue(job)!" class="job-progress" />
              <span v-else>—</span>
            </span>
            <span>{{ job.executor_label ?? '—' }}</span>
            <span>{{ resourceSummary(job) }}</span>
            <span>{{ duration(job) }}</span>
          </button>
        </div>

        <aside v-if="selectedJob" class="job-details" data-testid="execution-job-details">
          <header>
            <strong>{{ selectedJob.scoped_node_path }}</strong>
            <div>
              <Button label="Canvas" icon="pi pi-sitemap" text size="small" @click="selectOnCanvas(selectedJob)" />
              <Button v-if="registry.selectedRun.backend !== 'managed_remote'" label="Logs" icon="pi pi-list" text size="small" data-testid="execution-job-logs" @click="openLogs(selectedJob)" />
            </div>
          </header>
          <p v-if="selectedJob.route_reason"><strong>Route:</strong> {{ selectedJob.route_reason }}</p>
          <p v-if="selectedJob.diagnostic" class="diagnostic-message">
            <strong>{{ selectedJob.diagnostic.exception_type ?? selectedJob.diagnostic.category ?? 'Failure' }}:</strong>
            {{ selectedJob.diagnostic.message }}
          </p>
          <pre v-if="selectedJob.diagnostic?.traceback">{{ selectedJob.diagnostic.traceback }}</pre>
          <dl>
            <dt>Result key</dt><dd>{{ selectedJob.result_key ?? '—' }}</dd>
            <dt>Record ID</dt><dd>{{ selectedJob.record_id ?? '—' }}</dd>
          </dl>
        </aside>
      </main>
    </div>
    <ExecutionRetryDialog
      :visible="retryDialogVisible"
      :jobs="retryParentRun?.jobs ?? []"
      :initial-mode="retryInitialMode"
      :initial-node-path="retryInitialNodePath"
      :retry-action="retryParentRun?.actions.retry ?? unavailableAction"
      :recompute-action="retryParentRun?.actions.recompute ?? unavailableAction"
      :plan="retryPlan"
      :planning="retryPlanning"
      :starting="retryStarting"
      :error="retryError"
      @cancel="closeRetryDialog"
      @preview="previewRetry"
      @confirm="confirmRetry"
    />
    <Dialog
      :visible="cleanupPlan !== null"
      modal
      header="Confirm managed cluster cleanup"
      :closable="!cleanupApplying"
      :style="{ width: 'min(46rem, 95vw)' }"
      data-testid="execution-cleanup-dialog"
      @update:visible="(visible: boolean) => { if (!visible && !cleanupApplying) cleanupPlan = null }"
    >
      <p>This applies the server-created cleanup plan for the exact durable run identity. It does not remove the platform history entry.</p>
      <dl v-if="cleanupPlan" class="cleanup-summary">
        <dt>Execution</dt><dd>{{ cleanupPlan.execution_id }}</dd>
        <dt>Plan digest</dt><dd><code>{{ cleanupPlan.plan_digest }}</code></dd>
      </dl>
      <pre v-if="cleanupPlan" class="cleanup-plan">{{ JSON.stringify(cleanupPlan.plan, null, 2) }}</pre>
      <template #footer>
        <Button label="Cancel" severity="secondary" :disabled="cleanupApplying" @click="cleanupPlan = null" />
        <Button label="Apply cleanup" severity="danger" :loading="cleanupApplying" data-testid="confirm-execution-cleanup" @click="confirmCleanup" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.execution-panel { height: 100%; display: flex; flex-direction: column; min-width: 0; font-size: 0.8rem; }
.execution-toolbar { display: flex; justify-content: space-between; padding: 0.45rem; border-bottom: 1px solid var(--p-content-border-color); }
.execution-empty { margin: auto; color: var(--p-text-muted-color); }
.execution-layout { display: grid; grid-template-columns: 15rem minmax(32rem, 1fr); flex: 1; min-height: 0; }
.run-history { overflow: auto; border-right: 1px solid var(--p-content-border-color); }
.run-card { width: 100%; border: 0; border-bottom: 1px solid var(--p-content-border-color); background: transparent; color: inherit; text-align: left; padding: 0.65rem; display: grid; grid-template-columns: 1fr auto; gap: 0.35rem; cursor: pointer; }
.run-card--active { background: var(--p-highlight-background); }
.run-card small { grid-column: 1 / -1; color: var(--p-text-muted-color); }
.load-more { width: 100%; }
.run-detail { min-width: 0; overflow: auto; }
.run-summary { display: flex; align-items: center; flex-wrap: wrap; gap: 0.65rem; padding: 0.6rem; border-bottom: 1px solid var(--p-content-border-color); }
.run-summary > div:first-child { display: flex; flex-direction: column; }
.run-summary small { color: var(--p-text-muted-color); }
.run-actions { margin-left: auto; }
.run-provenance { display: flex; align-items: center; gap: 0.35rem; color: var(--p-text-muted-color); }
.run-provenance button { border: 0; padding: 0; background: transparent; color: var(--p-primary-color); cursor: pointer; font-family: monospace; }
.observation-warning, .diagnostic-message { color: var(--p-orange-600); }
.action-error { margin: 0.5rem; padding: 0.6rem; border-radius: 6px; color: var(--p-red-600); background: var(--p-red-50); }
.action-message { margin: 0.5rem; padding: 0.6rem; border-radius: 6px; color: var(--p-green-700); background: var(--p-green-50); }
.cluster-diagnostics { display: grid; gap: .45rem; margin: .6rem; }
.cluster-diagnostics article { display: grid; gap: .2rem; padding: .6rem; border-radius: 6px; background: var(--p-surface-100); }
.cluster-diagnostics small { color: var(--p-text-muted-color); }
.cleanup-summary { display: grid; grid-template-columns: 7rem minmax(0, 1fr); gap: .45rem; }
.cleanup-summary dt { color: var(--p-text-muted-color); }
.cleanup-summary dd { margin: 0; overflow-wrap: anywhere; }
.cleanup-plan { max-height: 18rem; overflow: auto; padding: .75rem; border-radius: 6px; background: var(--p-surface-100); }
.job-row { display: grid; grid-template-columns: minmax(11rem, 2fr) 6rem minmax(7rem, 1fr) 7rem 9rem 5rem; gap: 0.55rem; align-items: center; width: 100%; min-height: 2.4rem; padding: 0.35rem 0.65rem; border: 0; border-bottom: 1px solid var(--p-content-border-color); background: transparent; color: inherit; text-align: left; }
button.job-row { cursor: pointer; }
.job-row--active { background: var(--p-highlight-background); }
.job-header { color: var(--p-text-muted-color); font-size: 0.7rem; text-transform: uppercase; }
.job-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.job-progress { height: 0.6rem; }
.job-details { padding: 0.75rem; border-top: 1px solid var(--p-content-border-color); }
.job-details header { display: flex; justify-content: space-between; align-items: center; }
.job-details pre { overflow: auto; max-height: 14rem; background: var(--p-surface-100); padding: 0.6rem; white-space: pre-wrap; }
.job-details dl { display: grid; grid-template-columns: 6rem 1fr; }
.job-details dt { color: var(--p-text-muted-color); }
.job-details dd { margin: 0; font-family: monospace; }
</style>
