<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import ProgressBar from 'primevue/progressbar'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import type { Settings } from '@/stores/settings'
import { selectFolder } from '@/utils/nativeDialogs'
import { useNapariStore } from '@/stores/napari'
import { useSettingsPanel } from '@/composables/useSettingsPanel'

const FIJI_DOWNLOAD_URL = 'https://imagej.net/software/fiji/downloads'
const props = defineProps<{ modelValue: Settings }>()
const emit = defineEmits<{ (e: 'update:field', payload: { field: keyof Settings; value: unknown }): void }>()
const napari = useNapariStore()
const settingsPanel = useSettingsPanel()
const error = ref<string | null>(null)
const external = reactive({ name: '', path: '' })
const create = reactive({ name: '', preset: 'default' as 'default' | 'legacy' | 'advanced', python: '==3.12.*', napari: '0.9.1', qt: 'PyQt6' as 'PyQt5' | 'PyQt6', packages: '' })
const rule = reactive({ mode: 'extension' as 'extension' | 'pattern', value: '', environmentId: '', readerId: '' })
const lifecycle = reactive<Record<string, string>>({})
const renameTarget = ref<{ id: string; name: string } | null>(null)
const renameOpen = ref(false)
const renameDraft = ref('')
const removalTarget = ref<{ id: string; name: string; managed: boolean; adopted: boolean } | null>(null)
const removalOpen = ref(false)
const setupGroupId = ref('')
const selectedRecommendations = ref<string[]>([])
const sourceConfirmed = ref(false)
const editingRuleId = ref<string | null>(null)
const ruleEdit = reactive({ pattern: '', environmentId: '', readerId: '' })
const fijiPath = ref(props.modelValue.fiji_path ?? '')
watch(() => props.modelValue.fiji_path, value => { fijiPath.value = value ?? '' })

const visibleOperations = computed(() => napari.operations.filter(item => item.state !== 'completed'))
const environmentOptions = computed(() => napari.environments.map(item => ({ label: item.name, value: item.id })))
const defaultOptions = computed(() => [{ label: 'Automatic', value: null }, ...environmentOptions.value])
const recipeOptions = [
  { label: 'Default — napari 0.9.1 / PyQt6', value: 'default' },
  { label: 'Legacy smoke — napari 0.6.6 / PyQt5', value: 'legacy' },
  { label: 'Advanced', value: 'advanced' },
]
const qtOptions = [{ label: 'PyQt6', value: 'PyQt6' }, { label: 'PyQt5', value: 'PyQt5' }]
const ruleModeOptions = [{ label: 'Extension', value: 'extension' }, { label: 'Filename pattern', value: 'pattern' }]
const extensionPreview = computed(() => {
  const value = rule.value.trim()
  if (rule.mode !== 'extension' || !value) return value
  return `*.${value.replace(/^\.+/, '')}`
})
const selectedSetupGroup = computed(() => settingsPanel.napariCreatePrefills.value.find(group => group.id === setupGroupId.value) ?? null)
const setupGroupOptions = computed(() => settingsPanel.napariCreatePrefills.value.map((group, index) => ({
  label: `Set ${index + 1} — ${group.members?.length ?? 0} output${group.members?.length === 1 ? '' : 's'}`,
  value: group.id,
})))
const recommendedPackages = computed(() => selectedSetupGroup.value?.managed_create_prefill.recommended_packages ?? [])
const activeOperationStates = new Set(['pending', 'resolving', 'installing', 'validating', 'removing'])
const catchAllWarning = computed(() => {
  const newCatchAll = rule.mode === 'pattern' && rule.value.trim() === '*'
  const existingCatchAll = napari.filenameRules.findIndex(item => item.enabled && item.pattern === '*')
  if (!newCatchAll && (existingCatchAll < 0 || existingCatchAll === napari.filenameRules.length - 1)) return null
  return 'A catch-all * rule wins before every later rule. A global default is usually clearer.'
})

watch(settingsPanel.napariCreatePrefills, groups => {
  if (groups.length === 0) return
  if (!groups.some(group => group.id === setupGroupId.value)) setupGroupId.value = groups[0]!.id
}, { immediate: true })

watch(selectedSetupGroup, group => {
  if (!group) return
  create.packages = (group.managed_create_prefill.requested_packages ?? []).join('\n')
  selectedRecommendations.value = []
  sourceConfirmed.value = false
  if (!create.name.trim()) create.name = `Viewer environment ${settingsPanel.napariCreatePrefills.value.indexOf(group) + 1}`
}, { immediate: true })

function detail(exc: any): string {
  return exc?.response?.data?.detail?.detail ?? exc?.response?.data?.detail ?? exc?.message ?? String(exc)
}

async function run(action: () => Promise<void>): Promise<boolean> {
  error.value = null
  try { await action(); return true } catch (exc) { error.value = detail(exc); return false }
}

async function addExisting() {
  await run(async () => {
    await napari.registerEnvironment(external)
    external.name = ''; external.path = ''
  })
}

async function browseEnvironment() {
  const selected = await selectFolder('Choose a Conda or virtual environment')
  if (selected) external.path = selected
}

function packageList(): string[] {
  return [...new Set([
    ...create.packages.split(/[\n,]/).map(value => value.trim()).filter(Boolean),
    ...selectedRecommendations.value,
  ])]
}

async function createManaged() {
  if (selectedSetupGroup.value?.managed_create_prefill.requires_source_confirmation && !sourceConfirmed.value) return
  await run(async () => {
    const recipe = create.preset === 'advanced'
      ? { preset: create.preset, python: create.python, napari: create.napari, qt: create.qt, requested_packages: packageList() }
      : { preset: create.preset, requested_packages: packageList() }
    const operation = await napari.createManagedEnvironment({ name: create.name, recipe })
    if (setupGroupId.value) settingsPanel.consumeNapariCreatePrefill(setupGroupId.value)
    void napari.watchOperation(operation.environment_id, operation.id).catch(exc => { error.value = detail(exc) })
  })
}

function openRename(id: string, name: string) {
  error.value = null
  renameTarget.value = { id, name }
  renameDraft.value = name
  renameOpen.value = true
}

async function saveRename() {
  const target = renameTarget.value
  const name = renameDraft.value.trim()
  if (!target || !name || name === target.name) return
  if (await run(async () => napari.updateEnvironment(target.id, { name }))) {
    renameOpen.value = false
    renameTarget.value = null
  }
}

async function locate(id: string) {
  const path = await selectFolder('Locate the environment')
  if (!path) return
  await run(async () => napari.updateEnvironment(id, { path }))
}

async function refresh(id: string) {
  await run(async () => napari.probeEnvironment(id))
}

async function launch(id: string) {
  await run(async () => {
    await napari.launchEmpty(id)
    lifecycle[id] = napari.environmentState(id).status ?? 'running'
  })
}

function askForget(environment: typeof napari.environments[number]) {
  error.value = null
  removalTarget.value = {
    id: environment.id,
    name: environment.name,
    managed: false,
    adopted: environment.managed?.recipe.source === 'adopted',
  }
  removalOpen.value = true
}

function askDeleteManaged(environment: typeof napari.environments[number]) {
  error.value = null
  removalTarget.value = { id: environment.id, name: environment.name, managed: true, adopted: false }
  removalOpen.value = true
}

async function confirmRemoval() {
  const target = removalTarget.value
  if (!target) return
  const succeeded = await run(async () => {
    if (!target.managed) {
      await napari.forgetEnvironment(target.id)
      return
    }
    const operation = await napari.deleteManagedEnvironment(target.id)
    void napari.watchOperation(operation.environment_id, operation.id).catch(exc => { error.value = detail(exc) })
  })
  if (succeeded) {
    removalOpen.value = false
    removalTarget.value = null
  }
}

async function retry(id: string) {
  await run(async () => {
    const operation = await napari.retryManagedEnvironment(id)
    void napari.watchOperation(operation.environment_id, operation.id).catch(exc => { error.value = detail(exc) })
  })
}

async function setDefault(value: string | null) {
  await run(async () => napari.setDefaultEnvironment(value))
}

async function addRule() {
  if (!rule.value || !rule.environmentId) return
  await run(async () => {
    await napari.addFilenameRule({ value: rule.value, mode: rule.mode, environment_id: rule.environmentId, reader_id: rule.readerId || null, enabled: true })
    rule.value = ''; rule.readerId = ''
  })
}

async function moveRule(index: number, delta: number) {
  const rules = [...napari.filenameRules]
  const target = index + delta
  if (target < 0 || target >= rules.length) return
  ;[rules[index], rules[target]] = [rules[target]!, rules[index]!]
  await run(async () => napari.replaceFilenameRules(rules))
}

async function deleteRule(index: number) {
  const rules = napari.filenameRules.filter((_, item) => item !== index)
  await run(async () => napari.replaceFilenameRules(rules))
}

async function toggleRule(index: number) {
  const rules = napari.filenameRules.map((item, itemIndex) => itemIndex === index
    ? { ...item, enabled: !item.enabled }
    : item)
  await run(async () => napari.replaceFilenameRules(rules))
}

async function cancel(environmentId: string, operationId: string) {
  await run(async () => napari.cancelManagedOperation(environmentId, operationId))
}

async function loadRegistry() {
  await napari.fetchRegistry()
  for (const operation of napari.operations.filter(item => activeOperationStates.has(item.state))) {
    void napari.watchOperation(operation.environment_id, operation.id).catch(exc => { error.value = detail(exc) })
  }
  await Promise.all(napari.environments.map(async (environment) => {
    try {
      lifecycle[environment.id] = (await napari.refreshEnvironmentStatus(environment.id)).status ?? environment.state
    } catch {
      lifecycle[environment.id] = environment.state
    }
  }))
}

function isPlatformManaged(environment: typeof napari.environments[number]): boolean {
  return environment.managed?.recipe.source === 'managed'
}

function ownershipLabel(environment: typeof napari.environments[number]): string {
  if (isPlatformManaged(environment)) return 'Managed by BioImageFlow'
  return environment.ownership === 'external' ? 'External' : 'Adopted installation'
}

function canLaunch(environment: typeof napari.environments[number]): boolean {
  return !['setup_needed', 'creating', 'failed', 'cancelled', 'removing', 'missing', 'replaced', 'probe_failed'].includes(environment.state)
}

function beginRuleEdit(item: typeof napari.filenameRules[number]) {
  editingRuleId.value = item.id
  ruleEdit.pattern = item.pattern
  ruleEdit.environmentId = item.environment_id
  ruleEdit.readerId = item.reader_id ?? ''
}

function cancelRuleEdit() {
  editingRuleId.value = null
}

async function saveRuleEdit(index: number) {
  const rules = napari.filenameRules.map((item, itemIndex) => itemIndex === index
    ? {
        ...item,
        pattern: ruleEdit.pattern,
        environment_id: ruleEdit.environmentId,
        reader_id: ruleEdit.readerId || null,
      }
    : item)
  await run(async () => {
    await napari.replaceFilenameRules(rules)
    editingRuleId.value = null
  })
}

function stateLabel(state: string): string {
  return state.replace(/_/g, ' ').replace(/^./, (value: string) => value.toUpperCase())
}

function commitFiji() {
  emit('update:field', { field: 'fiji_path', value: fijiPath.value.trim() || null })
}

async function browseFiji() {
  const path = await selectFolder('Choose the Fiji.app folder')
  if (path) {
    fijiPath.value = path
    commitFiji()
  }
}

function clearFiji() {
  fijiPath.value = ''
  commitFiji()
}

onMounted(() => {
  void loadRegistry().catch(exc => { error.value = detail(exc) })
})
</script>

<template>
  <div class="settings-section" data-testid="image-viewers-section">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <section>
      <div class="heading">
        <h3>napari environments</h3>
      </div>
      <p class="help-text">Register an existing installation or create an isolated napari environment. Each environment has its own viewer and installed plugins.</p>
      <div class="field">
        <label for="napari-default-environment">Default environment</label>
        <Select id="napari-default-environment" aria-label="Default environment" :model-value="napari.defaultEnvironmentId" :options="defaultOptions" option-label="label" option-value="value" @update:model-value="setDefault" />
        <small class="help-text">Used when no favorite or filename rule selects a compatible environment. Automatic chooses an available compatible environment.</small>
      </div>
      <p v-if="napari.environments.length === 0" class="help-text">No napari environments are registered.</p>
      <article
        v-for="environment in napari.environments"
        :key="environment.id"
        class="environment"
        :data-testid="`napari-environment-card-${environment.id}`"
      >
        <div class="heading">
          <strong>{{ environment.name }}</strong>
          <span>napari {{ environment.inventory?.napari_version ?? 'unknown' }} · {{ stateLabel(lifecycle[environment.id] ?? environment.state) }}</span>
        </div>
        <p v-if="environment.state === 'replaced'" class="environment-warning" role="status">
          The Python executable at this saved path changed since registration, so the previous package check may no longer apply.
          <template v-if="environment.ownership === 'external'">Use <strong>Locate environment</strong> to verify the current installation, then <strong>Refresh</strong> its packages.</template>
          <template v-else-if="!isPlatformManaged(environment)">This legacy installation cannot be relocated here. You can forget its registration and add it as an existing environment, or create a new one.</template>
          <template v-else>Create a new managed environment, then delete this installation when it is no longer needed.</template>
        </p>
        <p v-else-if="environment.state === 'missing'" class="environment-warning" role="status">
          The saved Python executable is missing.
          <template v-if="environment.ownership === 'external'">Use <strong>Locate environment</strong> to reconnect this registration.</template>
          <template v-else-if="!isPlatformManaged(environment)">You can forget this legacy registration and add an existing installation, or create a new environment.</template>
          <template v-else>Create a new managed environment if this installation is gone.</template>
        </p>
        <details>
          <summary>Details</summary>
          <dl>
            <dt>Path</dt><dd><code>{{ environment.root }}</code></dd>
            <dt>Ownership</dt><dd>{{ ownershipLabel(environment) }}</dd>
            <dt>Kind</dt><dd>{{ environment.kind }}</dd>
            <dt>Recipe</dt><dd>{{ environment.managed?.recipe.preset ?? 'User managed' }}</dd>
            <dt>Python</dt><dd>{{ environment.inventory?.python_version ?? 'Not detected' }}</dd>
            <dt>Qt</dt><dd>{{ environment.inventory?.qt_distribution ? `${environment.inventory.qt_distribution} ${environment.inventory.qt_version ?? ''}` : 'Not detected' }}</dd>
            <dt>Lifecycle</dt><dd>{{ stateLabel(lifecycle[environment.id] ?? 'stopped') }}</dd>
            <dt>Last check</dt><dd>{{ environment.inventory?.probed_at ?? 'Never' }}</dd>
            <template v-if="environment.last_error">
              <dt>Last error</dt><dd class="error">{{ environment.last_error }}</dd>
            </template>
          </dl>
          <p v-if="lifecycle[environment.id] === 'restart_required'">Running viewer restart required to use the current installed packages.</p>
          <h4>{{ ['missing', 'replaced'].includes(environment.state) ? 'Installed packages (last checked)' : 'Installed packages' }}</h4>
          <p v-if="!environment.inventory?.distributions.length" class="help-text">No inventory is available.</p>
          <ul v-else class="packages">
            <li v-for="pkg in environment.inventory.distributions" :key="pkg.name">{{ pkg.name }} {{ pkg.version }}</li>
          </ul>
          <div class="actions">
            <Button label="Refresh" size="small" @click="refresh(environment.id)" />
            <Button label="Launch empty viewer" size="small" :disabled="!canLaunch(environment)" @click="launch(environment.id)" />
            <Button label="Rename" size="small" @click="openRename(environment.id, environment.name)" />
            <Button v-if="environment.ownership === 'external' && (environment.state === 'missing' || environment.state === 'replaced')" label="Locate environment" size="small" @click="locate(environment.id)" />
            <Button v-if="!isPlatformManaged(environment)" label="Forget" severity="secondary" size="small" @click="askForget(environment)" />
            <Button v-if="isPlatformManaged(environment) && ['failed', 'cancelled', 'setup_needed'].includes(environment.state)" label="Retry" size="small" @click="retry(environment.id)" />
            <Button v-if="isPlatformManaged(environment)" label="Delete managed installation" severity="danger" size="small" @click="askDeleteManaged(environment)" />
          </div>
        </details>
      </article>
      <div v-for="operation in visibleOperations" :key="operation.id" class="operation">
        <span>{{ operation.message }}<small v-if="operation.error" class="error"> — {{ operation.error.detail }}</small></span>
        <ProgressBar :value="operation.progress" />
        <Button v-if="activeOperationStates.has(operation.state)" label="Cancel" text size="small" @click="cancel(operation.environment_id, operation.id)" />
      </div>
    </section>

    <section class="form">
      <h4>Add existing environment</h4>
      <p class="help-text">Connect a Conda or Python virtual environment that you already manage. BioImageFlow checks its installed packages without changing them.</p>
      <div class="field">
        <label for="existing-environment-name">Name</label>
        <InputText id="existing-environment-name" v-model="external.name" aria-label="Existing environment name" placeholder="My napari" />
      </div>
      <div class="field">
        <label for="existing-environment-path">Environment folder or Python executable</label>
        <div class="path-row">
          <InputText id="existing-environment-path" v-model="external.path" aria-label="Environment path" placeholder="Choose an environment folder" />
          <Button label="Browse…" @click="browseEnvironment" />
        </div>
      </div>
      <Button label="Add existing" :disabled="!external.name.trim() || !external.path.trim()" @click="addExisting" />
    </section>
    <section class="form">
      <h4>Create a napari environment</h4>
      <p class="help-text">Create a separate installation with napari, Qt, and any requested plugin packages. Existing environments are left in place.</p>
      <div v-if="setupGroupOptions.length" class="field">
        <label for="napari-requirement-set">Workflow package requirements</label>
        <Select id="napari-requirement-set" v-model="setupGroupId" aria-label="Workflow package requirements" :options="setupGroupOptions" option-label="label" option-value="value" />
      </div>
      <p v-if="selectedSetupGroup" class="help-text">Prefilled from portable workflow requirements. Package availability on PyPI is not yet verified.</p>
      <div class="field">
        <label for="managed-environment-name">Name</label>
        <InputText id="managed-environment-name" v-model="create.name" aria-label="Managed environment name" placeholder="My napari" />
      </div>
      <div class="field">
        <label for="managed-environment-recipe">Recipe</label>
        <Select id="managed-environment-recipe" v-model="create.preset" aria-label="Managed environment recipe" :options="recipeOptions" option-label="label" option-value="value" />
        <small class="help-text">Choose Default for a new installation. Use Legacy only for plugins that need the older napari and Qt versions.</small>
      </div>
      <template v-if="create.preset === 'advanced'">
        <div class="field">
          <label for="managed-python-constraint">Python version constraint</label>
          <InputText id="managed-python-constraint" v-model="create.python" aria-label="Python constraint" />
        </div>
        <div class="field">
          <label for="managed-napari-version">napari version</label>
          <InputText id="managed-napari-version" v-model="create.napari" aria-label="napari version" />
        </div>
        <div class="field">
          <label for="managed-qt-distribution">Qt distribution</label>
          <Select id="managed-qt-distribution" v-model="create.qt" aria-label="Qt distribution" :options="qtOptions" option-label="label" option-value="value" />
        </div>
      </template>
      <div class="field">
        <label for="managed-packages">Plugin packages to install</label>
        <Textarea id="managed-packages" v-model="create.packages" aria-label="Required Python distributions" placeholder="One Python distribution per line, for example napari-nninteractive" rows="4" />
        <small class="help-text">Enter Python distribution names and optional version constraints. These packages are installed from PyPI.</small>
      </div>
      <fieldset v-if="recommendedPackages.length">
        <legend>Optional recommended distributions</legend>
        <label v-for="requirement in recommendedPackages" :key="requirement">
          <input v-model="selectedRecommendations" type="checkbox" :value="requirement"> {{ requirement }}
        </label>
      </fieldset>
      <label v-if="selectedSetupGroup?.managed_create_prefill.requires_source_confirmation" class="source-confirmation">
        <input v-model="sourceConfirmed" type="checkbox">
        I confirmed these workflow-declared requirements are available from PyPI. Unknown or private packages must be installed manually in an external environment.
      </label>
      <Button label="Create environment" :disabled="!create.name.trim() || (Boolean(selectedSetupGroup?.managed_create_prefill.requires_source_confirmation) && !sourceConfirmed)" @click="createManaged()" />
    </section>

    <section class="form">
      <h4>File opening rules</h4>
      <p class="help-text">Use these optional rules to prefer an environment for particular filenames, including files without workflow viewer requirements. BioImageFlow checks the complete file or folder name from top to bottom and uses the first matching enabled rule. Put specific patterns such as <code>*_labels.tif</code> above broad ones such as <code>*.tif</code>. If none matches, the default or another compatible environment is used.</p>
      <p class="help-text">A rule selects an environment; it does not prove that a reader can open the file or override a workflow's required plugin packages.</p>
      <p v-if="napari.filenameRules.length === 0" class="help-text">No filename rules yet.</p>
      <div v-for="(item, index) in napari.filenameRules" :key="item.id" class="rule">
        <label><input type="checkbox" :checked="item.enabled" @change="toggleRule(index)"> Enabled</label>
        <template v-if="editingRuleId === item.id">
          <InputText v-model="ruleEdit.pattern" class="rule-value" aria-label="Edit filename pattern" />
          <Select v-model="ruleEdit.environmentId" class="rule-environment" aria-label="Edit preferred environment" :options="environmentOptions" option-label="label" option-value="value" />
          <InputText v-model="ruleEdit.readerId" class="rule-reader" aria-label="Edit reader plugin ID" placeholder="Automatic reader" />
          <Button icon="pi pi-check" title="Save rule" text :disabled="!ruleEdit.pattern.trim() || !ruleEdit.environmentId" @click="saveRuleEdit(index)" />
          <Button icon="pi pi-times" title="Cancel rule editing" text @click="cancelRuleEdit" />
        </template>
        <template v-else>
          <code class="rule-value">{{ item.pattern }}</code>
          <span class="rule-environment">{{ napari.environments.find(env => env.id === item.environment_id)?.name }}</span>
          <span class="rule-reader">{{ item.reader_id ? `Reader: ${item.reader_id}` : 'Automatic reader' }}</span>
          <Button icon="pi pi-pencil" title="Edit rule" text @click="beginRuleEdit(item)" />
          <Button icon="pi pi-arrow-up" title="Move rule up" text :disabled="index === 0" @click="moveRule(index, -1)" />
          <Button icon="pi pi-arrow-down" title="Move rule down" text :disabled="index === napari.filenameRules.length - 1" @click="moveRule(index, 1)" />
          <Button icon="pi pi-trash" title="Delete rule" text @click="deleteRule(index)" />
        </template>
      </div>
      <div class="form rule-form">
        <div class="field">
          <label for="filename-rule-mode">Match by</label>
          <Select id="filename-rule-mode" v-model="rule.mode" aria-label="Filename rule mode" :options="ruleModeOptions" option-label="label" option-value="value" />
        </div>
        <div class="field">
          <label for="filename-rule-value">{{ rule.mode === 'extension' ? 'Extension' : 'Filename pattern' }}</label>
          <InputText id="filename-rule-value" v-model="rule.value" aria-label="Extension or filename pattern" :placeholder="rule.mode === 'extension' ? '.tif' : '*_labels.tif'" />
          <small v-if="extensionPreview" class="help-text">Saves as <code>{{ extensionPreview }}</code></small>
        </div>
        <div class="field">
          <label for="filename-rule-environment">Preferred environment</label>
          <Select id="filename-rule-environment" v-model="rule.environmentId" aria-label="Preferred environment" :options="environmentOptions" option-label="label" option-value="value" placeholder="Choose an environment" />
        </div>
        <div class="field">
          <label for="filename-rule-reader">Reader plugin ID (optional)</label>
          <InputText id="filename-rule-reader" v-model="rule.readerId" aria-label="Reader plugin ID (optional)" placeholder="Let napari choose" />
          <small class="help-text">Leave blank for napari to choose. Use a napari reader ID only when one specific plugin must read matching files. This does not install the plugin; declare its Python distribution as a required package when needed.</small>
        </div>
        <Button label="Add rule" :disabled="!rule.value.trim() || !rule.environmentId" @click="addRule" />
      </div>
      <p v-if="catchAllWarning" class="warning">{{ catchAllWarning }}</p>
    </section>

    <section>
      <h3>Fiji</h3>
      <p class="help-text">Fiji is installed separately. <a :href="FIJI_DOWNLOAD_URL" target="_blank" rel="noopener noreferrer">Download Fiji</a></p>
      <div class="path-row">
        <InputText v-model="fijiPath" aria-label="Fiji installation folder" placeholder="/Applications/Fiji.app" data-testid="fiji-path-input" @blur="commitFiji" @keydown.enter="commitFiji" />
        <Button label="Browse…" data-testid="fiji-path-browse" @click="browseFiji" />
        <Button label="Clear" data-testid="fiji-path-clear" @click="clearFiji" />
      </div>
    </section>
    <Dialog v-model:visible="renameOpen" modal header="Rename napari environment" :style="{ width: 'min(28rem, calc(100vw - 2rem))' }">
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="field">
        <label for="rename-environment-name">Environment name</label>
        <InputText id="rename-environment-name" v-model="renameDraft" autofocus @keydown.enter="saveRename" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="renameOpen = false" />
        <Button label="Save name" :disabled="!renameDraft.trim() || renameDraft.trim() === renameTarget?.name" @click="saveRename" />
      </template>
    </Dialog>
    <Dialog v-model:visible="removalOpen" modal :header="removalTarget?.managed ? 'Delete managed installation' : 'Forget napari environment'" :style="{ width: 'min(30rem, calc(100vw - 2rem))' }">
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-if="removalTarget?.managed">Delete <strong>{{ removalTarget.name }}</strong> and close its running viewer? This removes the BioImageFlow-managed installation.</p>
      <p v-else>Forget <strong>{{ removalTarget?.name }}</strong>? This removes its default, filename rules, and saved favorites. It does not delete the installation.</p>
      <p v-if="removalTarget?.adopted" class="help-text">This legacy installation will not be registered automatically again on startup. You can still add it later as an existing environment.</p>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="removalOpen = false" />
        <Button :label="removalTarget?.managed ? 'Delete installation' : 'Forget environment'" severity="danger" @click="confirmRemoval" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.settings-section,
.form,
.field {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.field { gap: 0.35rem; min-width: 0; }
.field > label { font-weight: 600; }
.field > :is(input, textarea, .p-select) { width: 100%; }
.settings-section > section { display: flex; flex-direction: column; gap: 0.75rem; border-top: 1px solid var(--bif-border-muted); padding-top: 1rem; }
.heading,
.actions,
.rule,
.path-row { display: flex; align-items: center; flex-wrap: wrap; gap: 0.5rem; }
.heading { justify-content: space-between; }
.environment { padding: 0.6rem; border: 1px solid var(--bif-border-muted); border-radius: 0.4rem; margin: 0.5rem 0; }
.environment-warning { color: var(--p-orange-700); padding: 0.5rem 0.65rem; background: var(--p-orange-50); border-radius: 0.35rem; }
.environment dl { display: grid; grid-template-columns: auto 1fr; gap: 0.25rem 0.75rem; }
.environment dd { margin: 0; min-width: 0; overflow-wrap: anywhere; }
.packages { max-height: 10rem; overflow: auto; }
.rule { display: grid; grid-template-columns: auto minmax(6rem, 1fr) minmax(6rem, 1fr) minmax(5rem, 1fr) repeat(4, auto); margin: 0.25rem 0; }
.rule-value { min-width: 0; overflow-wrap: anywhere; }
.rule-form { margin-top: 0.5rem; padding-top: 0.75rem; border-top: 1px solid var(--bif-border-muted); }
.rule-form > button,
.form > button { align-self: flex-start; }
.path-row > :first-child { flex: 1; min-width: 10rem; }
.operation { display: grid; grid-template-columns: 1fr minmax(8rem, 1fr) auto; align-items: center; gap: 0.5rem; }
.help-text { color: var(--p-text-muted-color); }
.error { color: var(--p-red-600); }
.warning { color: var(--p-orange-600); }
.source-confirmation { display: flex; align-items: flex-start; gap: 0.5rem; }
h3,
h4,
p { margin: 0.25rem 0; }
@media (max-width: 520px) {
  .rule { grid-template-columns: 1fr repeat(4, auto); }
  .rule-value,
  .rule-environment,
  .rule-reader { grid-column: 1 / -1; width: 100%; }
  .operation { grid-template-columns: 1fr; }
  .operation > button { justify-self: start; }
}
</style>
