<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import ProgressBar from 'primevue/progressbar'
import SelectButton from 'primevue/selectbutton'
import Tag from 'primevue/tag'
import { downloadExecutionResults, type ExecutionJobSnapshot } from '@/api/executions'
import { useExecutionRegistryStore } from '@/stores/executionRegistry'
import { useUIStore } from '@/stores/ui'

const registry = useExecutionRegistryStore()
const ui = useUIStore()
const scope = ref<'workflow' | 'workspace'>('workflow')
const selectedJobId = ref<string | null>(null)

const selectedJob = computed(() => (
  registry.selectedRun?.jobs.find(job => job.id === selectedJobId.value) ?? null
))

watch(() => registry.selectedRunId, () => { selectedJobId.value = null })
watch([scope, () => ui.activeWorkflowId], () => void loadRuns())
onMounted(() => void loadRuns())

async function loadRuns(): Promise<void> {
  await registry.loadRuns(scope.value === 'workflow' ? ui.activeWorkflowId : null)
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
    value.memory_gb != null ? `${value.memory_gb} GB` : null,
  ].filter(Boolean).join(' · ') || '—'
}

function canCancel(state: string): boolean {
  return !['succeeded', 'failed', 'cancelled', 'lost'].includes(state)
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

async function downloadResults(id: string): Promise<void> {
  const blob = await downloadExecutionResults(id)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${id}-results.zip`
  anchor.click()
  URL.revokeObjectURL(url)
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
      <Button icon="pi pi-refresh" text rounded aria-label="Refresh runs" title="Refresh runs" :loading="registry.loadingRuns" @click="loadRuns" />
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
        </button>
      </aside>

      <main v-if="registry.selectedRun" class="run-detail">
        <div class="run-summary">
          <div>
            <strong>{{ registry.selectedRun.workflow_name ?? registry.selectedRun.workflow_id }}</strong>
            <small>{{ registry.selectedRun.target_label ?? registry.selectedRun.target_id }}</small>
          </div>
          <Tag :value="registry.selectedRun.state" :severity="stateSeverity(registry.selectedRun.state)" />
          <span v-if="registry.selectedRun.scheduler_job_id">Scheduler {{ registry.selectedRun.scheduler_job_id }}</span>
          <span v-if="registry.selectedRun.observation_error" class="observation-warning">
            <i class="pi pi-wifi" /> {{ registry.selectedRun.observation_error }}
          </span>
          <div class="run-actions">
            <Button
              label="Cancel"
              icon="pi pi-stop"
              text
              size="small"
              :disabled="!canCancel(registry.selectedRun.state)"
              @click="registry.cancel(registry.selectedRun.id)"
            />
            <Button label="Retry" icon="pi pi-refresh" text size="small" @click="registry.retry(registry.selectedRun.id)" />
            <Button label="Results" icon="pi pi-download" text size="small" @click="downloadResults(registry.selectedRun.id)" />
          </div>
        </div>

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
              <Button label="Logs" icon="pi pi-list" text size="small" @click="openLogs(selectedJob)" />
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
.run-detail { min-width: 0; overflow: auto; }
.run-summary { display: flex; align-items: center; flex-wrap: wrap; gap: 0.65rem; padding: 0.6rem; border-bottom: 1px solid var(--p-content-border-color); }
.run-summary > div:first-child { display: flex; flex-direction: column; }
.run-summary small { color: var(--p-text-muted-color); }
.run-actions { margin-left: auto; }
.observation-warning, .diagnostic-message { color: var(--p-orange-600); }
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
