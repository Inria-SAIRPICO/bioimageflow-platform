<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import { useExecutionProfilesStore } from '@/stores/executionProfiles'
import type {
  ExecutionProfile,
  ExecutionProfileDraft,
  ExecutionProfileMode,
  PreLaunchSource,
} from '@/api/executionProfiles'
import { selectFile } from '@/utils/nativeDialogs'

const props = defineProps<{
  trustedFactories: string[]
  editable: boolean
}>()

const profiles = useExecutionProfilesStore()
const editorOpen = ref(false)
const editing = ref<ExecutionProfile | null>(null)
const formError = ref<string | null>(null)
const testMessage = ref<string | null>(null)

const modes: Array<{ label: string; value: ExecutionProfileMode }> = [
  { label: 'Attached Parsl', value: 'attached' },
  { label: 'Submitted locally', value: 'submitted_local' },
  { label: 'Submitted to cluster', value: 'submitted_remote' },
]

const preLaunchKinds = [
  { label: 'None', value: 'none' },
  { label: 'Inline script', value: 'inline' },
  { label: 'Local script file', value: 'local_file' },
  { label: 'Cluster script file', value: 'cluster_file' },
]

const form = reactive({
  name: '',
  enabled: true,
  mode: 'attached' as ExecutionProfileMode,
  factory: '',
  kwargs: '{}',
  secretRefs: '{}',
  executorBindings: '{}',
  environmentRoutes: '{}',
  sharedRuntimeRoot: '',
  rowChunkSize: '1',
  maxInFlight: '32',
  localWorkDir: '',
  scheduler: 'slurm',
  walltimeSeconds: '3600',
  queue: '',
  project: '',
  cpuCores: '1',
  clusterWorkDir: '',
  hardCancelAfter: '',
  host: '',
  stagingRoot: '',
  remoteExecutable: '',
  connectTimeout: '15',
  remoteWorkflowRoot: '',
  preLaunchKind: 'none',
  preLaunchText: '',
  preLaunchPath: '',
  preLaunchDigest: '',
})

const remote = computed(() => form.mode === 'submitted_remote')
const submitted = computed(() => form.mode !== 'attached')

function jsonObject(text: string, label: string): Record<string, unknown> {
  const value: unknown = JSON.parse(text)
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error(`${label} must be a JSON object`)
  }
  return value as Record<string, unknown>
}

function optionalNumber(value: string): number | null {
  return value.trim() ? Number(value) : null
}

function preLaunch(): PreLaunchSource {
  if (!remote.value || form.preLaunchKind === 'none') return null
  if (form.preLaunchKind === 'inline') {
    return { kind: 'inline', text: form.preLaunchText }
  }
  if (form.preLaunchKind === 'local_file') {
    return { kind: 'local_file', path: form.preLaunchPath }
  }
  return {
    kind: 'cluster_file',
    path: form.preLaunchPath,
    expected_digest: form.preLaunchDigest.trim() || null,
  }
}

function buildDraft(): ExecutionProfileDraft {
  const secretRefs = jsonObject(form.secretRefs, 'Secret references')
  const launch = form.mode === 'attached'
    ? null
    : form.mode === 'submitted_local'
      ? {
          backend: 'local',
          work_dir: form.localWorkDir.trim() || null,
          hard_cancel_after: optionalNumber(form.hardCancelAfter),
        }
      : {
          backend: 'psij',
          executor: form.scheduler,
          walltime_seconds: Number(form.walltimeSeconds),
          queue: form.queue.trim() || null,
          project: form.project.trim() || null,
          cpu_cores: Number(form.cpuCores),
          work_dir: form.clusterWorkDir.trim() || null,
          hard_cancel_after: optionalNumber(form.hardCancelAfter),
        }
  return {
    schema: 'bioimageflow.platform.execution-profile.v1',
    name: form.name.trim(),
    enabled: form.enabled,
    mode: form.mode,
    parsl_config: {
      factory: form.factory,
      kwargs: jsonObject(form.kwargs, 'Factory arguments'),
      secret_refs: Object.keys(secretRefs).length > 0
        ? secretRefs as Record<string, string>
        : null,
    },
    executor_bindings: jsonObject(form.executorBindings, 'Executor bindings'),
    environment_routes: jsonObject(form.environmentRoutes, 'Environment routes') as Record<string, string>,
    shared_runtime_root: form.sharedRuntimeRoot.trim() || null,
    task_policy: {
      schema: 'bioimageflow.parsl.task_policy.v1',
      row_chunk_size: Number(form.rowChunkSize),
      max_in_flight: Number(form.maxInFlight),
    },
    launch,
    transport: remote.value
      ? {
          host: form.host,
          staging_root: form.stagingRoot,
          remote_executable: form.remoteExecutable,
          connect_timeout: Number(form.connectTimeout),
        }
      : null,
    remote_workflow_root: remote.value ? form.remoteWorkflowRoot : null,
    pre_launch: preLaunch(),
  }
}

function resetForm(): void {
  Object.assign(form, {
    name: '', enabled: true, mode: 'attached', factory: props.trustedFactories[0] ?? '',
    kwargs: '{}', secretRefs: '{}', executorBindings: '{}', environmentRoutes: '{}',
    sharedRuntimeRoot: '', rowChunkSize: '1', maxInFlight: '32', localWorkDir: '',
    scheduler: 'slurm', walltimeSeconds: '3600', queue: '', project: '', cpuCores: '1',
    clusterWorkDir: '', hardCancelAfter: '', host: '', stagingRoot: '', remoteExecutable: '',
    connectTimeout: '15', remoteWorkflowRoot: '', preLaunchKind: 'none', preLaunchText: '',
    preLaunchPath: '', preLaunchDigest: '',
  })
}

function openNew(): void {
  editing.value = null
  resetForm()
  formError.value = null
  editorOpen.value = true
}

function openEdit(profile: ExecutionProfile): void {
  editing.value = profile
  resetForm()
  const launch = profile.launch ?? {}
  const transport = profile.transport ?? {}
  Object.assign(form, {
    name: profile.name,
    enabled: profile.enabled,
    mode: profile.mode,
    factory: profile.parsl_config.factory,
    kwargs: JSON.stringify(profile.parsl_config.kwargs, null, 2),
    secretRefs: JSON.stringify(profile.parsl_config.secret_refs ?? {}, null, 2),
    executorBindings: JSON.stringify(profile.executor_bindings, null, 2),
    environmentRoutes: JSON.stringify(profile.environment_routes, null, 2),
    sharedRuntimeRoot: profile.shared_runtime_root ?? '',
    rowChunkSize: String(profile.task_policy.row_chunk_size ?? 1),
    maxInFlight: String(profile.task_policy.max_in_flight ?? 32),
    localWorkDir: String(launch.work_dir ?? ''),
    scheduler: String(launch.executor ?? 'slurm'),
    walltimeSeconds: String(launch.walltime_seconds ?? 3600),
    queue: String(launch.queue ?? ''),
    project: String(launch.project ?? ''),
    cpuCores: String(launch.cpu_cores ?? 1),
    clusterWorkDir: String(launch.work_dir ?? ''),
    hardCancelAfter: String(launch.hard_cancel_after ?? ''),
    host: String(transport.host ?? ''),
    stagingRoot: String(transport.staging_root ?? ''),
    remoteExecutable: String(transport.remote_executable ?? ''),
    connectTimeout: String(transport.connect_timeout ?? 15),
    remoteWorkflowRoot: profile.remote_workflow_root ?? '',
    preLaunchKind: profile.pre_launch?.kind ?? 'none',
    preLaunchText: profile.pre_launch?.kind === 'inline' ? profile.pre_launch.text : '',
    preLaunchPath: profile.pre_launch?.kind !== 'inline' ? profile.pre_launch?.path ?? '' : '',
    preLaunchDigest: profile.pre_launch?.kind === 'cluster_file'
      ? profile.pre_launch.expected_digest ?? ''
      : '',
  })
  formError.value = null
  editorOpen.value = true
}

async function save(): Promise<void> {
  formError.value = null
  try {
    const draft = buildDraft()
    if (editing.value) await profiles.update(editing.value, draft)
    else await profiles.create(draft)
    editorOpen.value = false
  } catch (errorValue) {
    formError.value = errorValue instanceof Error ? errorValue.message : String(errorValue)
  }
}

async function testProfile(profile: ExecutionProfile): Promise<void> {
  const result = await profiles.test(profile)
  testMessage.value = result.valid
    ? 'Profile validation passed. Pre-launch setup was not executed.'
    : result.diagnostics.map(item => item.message).join('\n')
}

async function chooseLocalPreLaunch(): Promise<void> {
  const selected = await selectFile('Select PSI/J pre-launch script', ['*.sh'])
  if (selected !== null) form.preLaunchPath = selected
}

onMounted(() => void profiles.refresh())
</script>

<template>
  <section class="profiles" data-testid="execution-profiles-section">
    <header>
      <div>
        <h3>Distributed profiles</h3>
        <p>Configure attached Parsl or durable cluster execution targets.</p>
      </div>
      <Button v-if="editable" label="Add profile" icon="pi pi-plus" size="small" @click="openNew" />
    </header>
    <p v-if="profiles.loading" role="status">Loading execution profiles…</p>
    <p v-if="profiles.error" class="error" role="alert">{{ profiles.error }}</p>
    <p v-if="testMessage" class="notice" role="status">{{ testMessage }}</p>
    <div v-for="profile in profiles.profiles" :key="profile.id" class="profile-card">
      <div>
        <strong>{{ profile.name }}</strong>
        <span>{{ profile.mode.replace(/_/g, ' ') }} · revision {{ profile.revision }}</span>
      </div>
      <div class="actions">
        <Button label="Test" severity="secondary" size="small" :loading="profiles.testing === profile.id" @click="testProfile(profile)" />
        <Button v-if="profile.editable" label="Edit" severity="secondary" size="small" @click="openEdit(profile)" />
        <Button v-if="profile.editable" label="Remove" severity="danger" text size="small" @click="profiles.remove(profile)" />
      </div>
    </div>
    <p v-if="!profiles.loading && profiles.profiles.length === 0" class="empty">
      No distributed profiles are configured. Local execution remains available.
    </p>

    <Dialog v-model:visible="editorOpen" modal :header="editing ? 'Edit execution profile' : 'Add execution profile'" :style="{ width: 'min(820px, calc(100vw - 2rem))' }">
      <div class="form-grid">
        <label>Name<InputText v-model="form.name" /></label>
        <label>Mode<Select v-model="form.mode" :options="modes" option-label="label" option-value="value" /></label>
        <label class="wide">Trusted configuration factory<Select v-model="form.factory" editable :options="trustedFactories" /></label>
        <label class="wide">Factory arguments (JSON)<Textarea v-model="form.kwargs" rows="4" /></label>
        <label class="wide">Secret argument → environment reference (JSON)<Textarea v-model="form.secretRefs" rows="3" /></label>
        <label class="wide">Executor bindings (BioImageFlow JSON)<Textarea v-model="form.executorBindings" rows="7" /></label>
        <label class="wide">Environment routes (JSON)<Textarea v-model="form.environmentRoutes" rows="3" /></label>
        <label>Shared runtime root<InputText v-model="form.sharedRuntimeRoot" /></label>
        <label>Row chunk size<InputText v-model="form.rowChunkSize" /></label>
        <label>Maximum in flight<InputText v-model="form.maxInFlight" /></label>
        <template v-if="submitted">
          <label>Hard-cancel grace (seconds)<InputText v-model="form.hardCancelAfter" /></label>
        </template>
        <template v-if="form.mode === 'submitted_local'">
          <label class="wide">Local orchestrator work directory<InputText v-model="form.localWorkDir" /></label>
        </template>
        <template v-if="remote">
          <label>OpenSSH host or alias<InputText v-model="form.host" /></label>
          <label>Transport staging root<InputText v-model="form.stagingRoot" /></label>
          <label class="wide">Cluster agent executable<InputText v-model="form.remoteExecutable" /></label>
          <label>Connection timeout<InputText v-model="form.connectTimeout" /></label>
          <label>Workflow storage root<InputText v-model="form.remoteWorkflowRoot" /></label>
          <label>Scheduler<Select v-model="form.scheduler" :options="['slurm', 'pbs', 'lsf']" /></label>
          <label>Walltime (seconds)<InputText v-model="form.walltimeSeconds" /></label>
          <label>Queue<InputText v-model="form.queue" /></label>
          <label>Project / account<InputText v-model="form.project" /></label>
          <label>Orchestrator CPU cores<InputText v-model="form.cpuCores" /></label>
          <label>Cluster work directory<InputText v-model="form.clusterWorkDir" /></label>
          <label class="wide">Pre-launch setup<Select v-model="form.preLaunchKind" :options="preLaunchKinds" option-label="label" option-value="value" /></label>
          <label v-if="form.preLaunchKind === 'inline'" class="wide">Inline UTF-8 shell source<Textarea v-model="form.preLaunchText" rows="8" /></label>
          <label v-if="form.preLaunchKind === 'local_file'" class="wide">
            Local script path
            <span class="path-row">
              <InputText v-model="form.preLaunchPath" />
              <Button label="Browse…" severity="secondary" @click="chooseLocalPreLaunch" />
            </span>
          </label>
          <template v-if="form.preLaunchKind === 'cluster_file'">
            <label class="wide">Cluster script path<InputText v-model="form.preLaunchPath" /></label>
            <label class="wide">Expected SHA-256 digest (recommended)<InputText v-model="form.preLaunchDigest" placeholder="sha256:…" /></label>
          </template>
          <p v-if="form.preLaunchKind !== 'none'" class="wide warning">
            The script is sourced once before the PSI/J orchestrator. Do not put credentials in it. It does not initialize Parsl workers or replace OpenSSH and cluster-agent setup.
          </p>
        </template>
        <label class="checkbox"><Checkbox v-model="form.enabled" binary />Enabled</label>
      </div>
      <p v-if="formError" class="error" role="alert">{{ formError }}</p>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="editorOpen = false" />
        <Button label="Save" @click="save" />
      </template>
    </Dialog>
  </section>
</template>

<style scoped>
.profiles { display: grid; gap: .75rem; }
header, .profile-card, .actions { display: flex; align-items: center; gap: .5rem; }
header, .profile-card { justify-content: space-between; }
h3, p { margin: 0; }
header p, .profile-card span, .empty { color: var(--p-text-muted-color, #666); }
.profile-card { padding: .75rem; border: 1px solid var(--p-content-border-color, #ddd); border-radius: 6px; }
.profile-card > div:first-child { display: grid; gap: .2rem; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .8rem; }
.form-grid label { display: grid; gap: .35rem; font-weight: 600; }
.form-grid .wide { grid-column: 1 / -1; }
.checkbox { display: flex !important; grid-auto-flow: column; justify-content: start; align-items: center; }
.warning { padding: .7rem; background: color-mix(in srgb, var(--p-yellow-500, #eab308) 14%, transparent); border-radius: 4px; }
.error { color: var(--p-red-600, #c00); white-space: pre-wrap; }
.notice { white-space: pre-wrap; }
.path-row { display: grid; grid-template-columns: 1fr auto; gap: .5rem; }
@media (max-width: 680px) { .form-grid { grid-template-columns: 1fr; } .form-grid .wide { grid-column: auto; } }
</style>
