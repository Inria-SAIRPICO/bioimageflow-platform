<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import SelectButton from 'primevue/selectbutton'
import { usePathPicker } from '@/composables/usePathPicker'
import type {
  RemoteNodePathInput,
  RemoteNodePathLeaf,
  RemoteNodePathResolution,
} from '@/api/executions'

interface LeafDraft {
  source: 'upload' | 'cluster' | 'none' | null
  path: string
}

const props = defineProps<{
  visible: boolean
  unresolved: RemoteNodePathInput[]
  busy?: boolean
}>()

const emit = defineEmits<{
  resolve: [resolutions: RemoteNodePathResolution[]]
  cancel: []
}>()

const { pickFile, pickFolder, isDesktop } = usePathPicker()
const drafts = ref<Record<string, LeafDraft[]>>({})

function key(input: RemoteNodePathInput): string {
  return `${input.node_path}\n${input.input_name}`
}

watch(
  () => props.unresolved,
  (inputs) => {
    drafts.value = Object.fromEntries(inputs.map(input => [
      key(input),
      input.values.map(value => ({ source: null, path: value ?? '' })),
    ]))
  },
  { immediate: true },
)

function draftFor(input: RemoteNodePathInput, index: number): LeafDraft {
  return drafts.value[key(input)]![index]!
}

function choices(input: RemoteNodePathInput) {
  return [
    { label: 'Upload', value: 'upload' },
    { label: 'Cluster', value: 'cluster' },
    ...(input.nullable ? [{ label: 'None', value: 'none' }] : []),
  ]
}

async function chooseUpload(input: RemoteNodePathInput, index: number): Promise<void> {
  const selected = isDesktop() && input.path_picker === 'folder'
    ? await pickFolder({ parameterName: input.input_name })
    : await pickFile({ parameterName: input.input_name })
  if (selected !== null) draftFor(input, index).path = selected
}

function leafValid(draft: LeafDraft): boolean {
  if (draft.source === 'none') return true
  if (draft.source === 'upload') return draft.path.trim().length > 0
  return draft.source === 'cluster' && draft.path.startsWith('/')
}

const canResolve = computed(() => props.unresolved.every(input => (
  drafts.value[key(input)]?.every(leafValid) === true
)))

function resolve(): void {
  if (!canResolve.value) return
  emit('resolve', props.unresolved.map(input => ({
    node_path: input.node_path,
    input_name: input.input_name,
    value_shape: input.value_shape,
    values: drafts.value[key(input)]!.map((draft): RemoteNodePathLeaf => {
      if (draft.source === 'none') return { source: 'none' }
      if (draft.source === 'upload') return { source: 'upload', path: draft.path }
      return { source: 'cluster', path: draft.path }
    }),
  })))
}

</script>

<template>
  <Dialog
    :visible="visible"
    modal
    :closable="!busy"
    header="Resolve cluster paths"
    :style="{ width: 'min(52rem, 95vw)' }"
    data-testid="remote-execution-dialog"
    @update:visible="(next: boolean) => { if (!next) emit('cancel') }"
  >
    <template>
      <p class="dialog-intro">Choose explicitly whether each path is uploaded from this computer or already exists on the cluster. The resolved invocation is submitted directly through the managed cluster API.</p>
      <div v-for="input in unresolved" :key="key(input)" class="path-input-card">
        <div class="path-input-title">
          <code>{{ input.node_path }}</code>
          <strong>{{ input.input_name }}</strong>
          <small>{{ input.value_shape }}</small>
        </div>
        <div v-for="(_, index) in input.values" :key="index" class="path-leaf">
          <span v-if="input.values.length > 1" class="path-index">{{ index + 1 }}</span>
          <SelectButton
            v-model="draftFor(input, index).source"
            :options="choices(input)"
            option-label="label"
            option-value="value"
            :allow-empty="false"
            :data-testid="`remote-path-source-${input.node_path}-${input.input_name}-${index}`"
          />
          <InputText
            v-if="draftFor(input, index).source !== 'none'"
            v-model="draftFor(input, index).path"
            :placeholder="draftFor(input, index).source === 'cluster' ? '/absolute/cluster/path' : 'Select a local file'"
            class="path-value"
          />
          <Button
            v-if="draftFor(input, index).source === 'upload'"
            icon="pi pi-folder-open"
            text
            aria-label="Choose local path"
            title="Choose local path"
            @click="chooseUpload(input, index)"
          />
          <small
            v-if="draftFor(input, index).source === 'cluster' && !leafValid(draftFor(input, index))"
            class="path-error"
          >Absolute POSIX path required</small>
        </div>
      </div>
    </template>

    <template #footer>
      <Button label="Cancel" text :disabled="busy" @click="emit('cancel')" />
      <Button
        label="Resolve and submit"
        icon="pi pi-play"
        :disabled="!canResolve || busy"
        data-testid="prepare-remote-execution"
        @click="resolve"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.dialog-intro { color: var(--p-text-muted-color); }
.path-input-card { border: 1px solid var(--p-content-border-color); border-radius: 6px; padding: 0.75rem; margin: 0.6rem 0; }
.path-input-title { display: flex; gap: 0.6rem; align-items: center; margin-bottom: 0.55rem; }
.path-input-title small { color: var(--p-text-muted-color); margin-left: auto; }
.path-leaf { display: grid; grid-template-columns: auto auto minmax(10rem, 1fr) auto; gap: 0.45rem; align-items: center; margin-top: 0.45rem; }
.path-index { color: var(--p-text-muted-color); }
.path-value { min-width: 0; width: 100%; }
.path-error { color: var(--p-red-500); grid-column: 3 / -1; }
</style>
