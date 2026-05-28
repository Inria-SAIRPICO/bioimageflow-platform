<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'

const props = defineProps<{
  visible: boolean
  mode: 'new' | 'save-as'
  initialName?: string
  initialDisplayName?: string
  initialDescription?: string | null
  suggestedName?: string | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [payload: {
    name: string
    display_name: string
    description: string | null
  }]
}>()

const name = ref('')
const displayName = ref('')
const description = ref('')

const title = computed(() => (
  props.mode === 'new' ? 'Create workflow' : 'Save workflow as'
))
const subtitle = computed(() => (
  props.mode === 'new'
    ? 'Start with an empty canvas and a dedicated workflow file.'
    : 'Create a copy of the current workflow and continue editing it.'
))
function deriveWorkflowId(value: string): string {
  return value
    .trim()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .replace(/_+/g, '_')
    .toLowerCase()
}

const generatedName = computed(() => props.suggestedName || deriveWorkflowId(displayName.value))
const displayNameError = computed(() => {
  if (!displayName.value.trim()) return 'A workflow name is required.'
  if (!generatedName.value) return 'Use at least one letter or number.'
  return null
})
const canSubmit = computed(() => displayNameError.value === null)

watch(
  () => [
    props.visible,
    props.initialName,
    props.initialDisplayName,
    props.suggestedName,
    props.initialDescription,
  ],
  ([visible]) => {
    if (!visible) return
    const nextName = props.suggestedName || props.initialName || ''
    name.value = nextName || deriveWorkflowId(props.initialDisplayName || '')
    displayName.value = props.initialDisplayName || nextName || ''
    description.value = props.initialDescription ?? ''
  },
  { immediate: true },
)

function onCancel() {
  emit('update:visible', false)
}

function onSubmit() {
  if (!canSubmit.value) return
  const trimmedDisplayName = displayName.value.trim()
  const trimmedName = (props.suggestedName || generatedName.value || name.value).trim()
  emit('submit', {
    name: trimmedName,
    display_name: trimmedDisplayName || trimmedName,
    description: description.value.trim() || null,
  })
}
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    :style="{ width: '460px' }"
    class="workflow-dialog"
    data-testid="workflow-dialog"
    @update:visible="emit('update:visible', $event)"
  >
    <template #header>
      <div class="dialog-title">
        <span class="dialog-kicker">Workflow</span>
        <h2>{{ title }}</h2>
        <p>{{ subtitle }}</p>
      </div>
    </template>

    <div class="workflow-form">
      <label class="field">
        <span>Name</span>
        <InputText
          v-model="displayName"
          autofocus
          autocomplete="off"
          data-testid="workflow-display-name-input"
          placeholder="My workflow"
        />
        <small
          v-if="displayNameError"
          class="error"
          data-testid="workflow-display-name-error"
        >
          {{ displayNameError }}
        </small>
        <small v-else class="generated-name" data-testid="workflow-generated-name">
          ID: {{ generatedName }}
        </small>
      </label>
      <label class="field">
        <span>Description</span>
        <Textarea
          v-model="description"
          auto-resize
          rows="3"
          data-testid="workflow-description-input"
          placeholder="What does this workflow do?"
        />
      </label>
    </div>

    <template #footer>
      <Button label="Cancel" text data-testid="workflow-dialog-cancel" @click="onCancel" />
      <Button
        :label="mode === 'new' ? 'Create' : 'Save copy'"
        icon="pi pi-check"
        :disabled="!canSubmit"
        data-testid="workflow-dialog-submit"
        @click="onSubmit"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.dialog-title {
  padding-right: 1rem;
}
.dialog-kicker {
  color: var(--p-primary-color);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.dialog-title h2 {
  margin: 0.2rem 0;
}
.dialog-title p {
  color: var(--p-text-muted-color);
  margin: 0;
}
.workflow-form {
  display: grid;
  gap: 1rem;
}
.field {
  display: grid;
  gap: 0.35rem;
}
.field span {
  font-weight: 700;
}
.error {
  color: var(--p-red-500);
}
.generated-name {
  color: var(--p-text-muted-color);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
</style>
