<script setup lang="ts">
import { ref, watch } from 'vue'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Tag from 'primevue/tag'
import { useConfirm } from 'primevue/useconfirm'
import type { OmeroInstanceResponse, SettingsResponse } from '@/api/types'

type OmeroInstancePatch = Omit<OmeroInstanceResponse, 'password_stored'> & {
  password?: string | null
}

type LocalOmeroInstance = {
  name: string
  host: string
  port: number
  username: string
  password: string
  password_stored: boolean
}

const props = defineProps<{ modelValue: SettingsResponse }>()
const emit = defineEmits<{
  (e: 'update:field', payload: { field: keyof SettingsResponse; value: unknown }): void
}>()

let confirm: ReturnType<typeof useConfirm> | null = null
try {
  confirm = useConfirm()
} catch {
  confirm = null
}

const rows = ref<LocalOmeroInstance[]>([])
const validationError = ref<string | null>(null)

function syncRows() {
  rows.value = props.modelValue.omero_instances.map((instance) => ({
    name: instance.name ?? '',
    host: instance.host,
    port: instance.port,
    username: instance.username,
    password: '',
    password_stored: instance.password_stored,
  }))
  validationError.value = null
}

watch(() => props.modelValue.omero_instances, syncRows, { immediate: true })

function displayName(row: LocalOmeroInstance): string {
  const explicit = row.name.trim()
  if (explicit) return explicit
  return `${row.host.trim()}:${row.username.trim()}`
}

function cardTitle(row: LocalOmeroInstance, index: number): string {
  const explicit = row.name.trim()
  if (explicit) return explicit
  const host = row.host.trim()
  const username = row.username.trim()
  if (host && username) return `${host}:${username}`
  return `OMERO instance ${index + 1}`
}

function validateRows(): boolean {
  const names = new Set<string>()
  for (const row of rows.value) {
    if (!row.host.trim()) {
      validationError.value = 'Host is required.'
      return false
    }
    if (!row.username.trim()) {
      validationError.value = 'Username is required.'
      return false
    }
    if (!Number.isInteger(row.port) || row.port < 1 || row.port > 65535) {
      validationError.value = 'Port must be between 1 and 65535.'
      return false
    }
    const name = displayName(row)
    if (names.has(name)) {
      validationError.value = 'OMERO instance names must be unique.'
      return false
    }
    names.add(name)
  }
  validationError.value = null
  return true
}

function toPatch(passwordIndex: number | null = null): OmeroInstancePatch[] {
  return rows.value.map((row, index) => {
    const patch: OmeroInstancePatch = {
      name: row.name.trim() || null,
      host: row.host.trim(),
      port: row.port,
      username: row.username.trim(),
    }
    if (passwordIndex === index && row.password !== '') {
      patch.password = row.password
    }
    return patch
  })
}

function emitRows(passwordIndex: number | null = null) {
  if (!validateRows()) return
  emit('update:field', { field: 'omero_instances', value: toPatch(passwordIndex) })
}

function addRow() {
  rows.value.push({
    name: '',
    host: '',
    port: 4064,
    username: '',
    password: '',
    password_stored: false,
  })
  validationError.value = null
}

function duplicateRow(index: number) {
  const row = rows.value[index]
  rows.value.splice(index + 1, 0, { ...row, password: '', password_stored: false })
  validationError.value = null
}

function removeRow(index: number) {
  const row = rows.value[index]
  const apply = () => {
    rows.value.splice(index, 1)
    emitRows()
  }
  const message = `Remove OMERO instance '${displayName(row)}'? Stored credentials will be deleted.`
  if (confirm) {
    confirm.require({
      message,
      header: 'Remove OMERO instance',
      icon: 'pi pi-exclamation-triangle',
      accept: apply,
    })
  } else {
    apply()
  }
}
</script>

<template>
  <div class="settings-section" data-testid="omero-section">
    <p v-if="rows.length === 0" class="empty-state" data-testid="omero-empty-state">
      No OMERO instances configured.
    </p>

    <div v-else class="omero-list" role="list" aria-label="OMERO instances">
      <section
        v-for="(row, index) in rows"
        :key="index"
        class="omero-card"
        role="listitem"
        :aria-labelledby="`omero-card-title-${index}`"
        :data-testid="`omero-card-${index}`"
      >
        <h3 :id="`omero-card-title-${index}`" class="omero-card-title">
          {{ cardTitle(row, index) }}
        </h3>

        <div class="omero-fields">
          <div class="omero-field">
            <label :for="`omero-name-${index}`">Name</label>
            <InputText
              :id="`omero-name-${index}`"
              v-model="row.name"
              aria-label="Name"
            />
          </div>
          <div class="omero-field">
            <label :for="`omero-host-${index}`">Host</label>
            <InputText
              :id="`omero-host-${index}`"
              v-model="row.host"
              aria-label="Host"
            />
          </div>
          <div class="omero-field">
            <label :for="`omero-port-${index}`">Port</label>
            <InputNumber
              :input-id="`omero-port-${index}`"
              v-model="row.port"
              aria-label="Port"
              :min="1"
              :max="65535"
              :use-grouping="false"
            />
          </div>
          <div class="omero-field">
            <label :for="`omero-username-${index}`">Username</label>
            <InputText
              :id="`omero-username-${index}`"
              v-model="row.username"
              aria-label="Username"
            />
          </div>
          <div class="omero-field password-field">
            <label :for="`omero-password-${index}`">Password</label>
            <div class="password-control">
              <Password
                :input-id="`omero-password-${index}`"
                v-model="row.password"
                aria-label="Password"
                :feedback="false"
                toggle-mask
              />
              <Tag
                :severity="row.password_stored ? 'success' : 'secondary'"
                :value="row.password_stored ? 'Stored' : 'Not stored'"
              />
            </div>
          </div>
        </div>

        <div class="actions-cell">
          <Button
            label="Save"
            icon="pi pi-save"
            aria-label="Save OMERO instance"
            title="Save OMERO instance"
            @click="emitRows(index)"
          />
          <Button
            label="Duplicate"
            icon="pi pi-copy"
            severity="secondary"
            aria-label="Duplicate OMERO instance"
            title="Duplicate OMERO instance"
            @click="duplicateRow(index)"
          />
          <Button
            label="Remove"
            icon="pi pi-trash"
            severity="danger"
            outlined
            aria-label="Remove OMERO instance"
            title="Remove OMERO instance"
            @click="removeRow(index)"
          />
        </div>
      </section>
    </div>

    <p v-if="validationError" class="error-text" data-testid="omero-validation-error">
      {{ validationError }}
    </p>

    <Button
      label="Add instance"
      icon="pi pi-plus"
      severity="secondary"
      data-testid="omero-add-button"
      @click="addRow"
    />
  </div>
</template>

<style scoped>
.settings-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.omero-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.omero-card {
  min-width: 0;
  padding: 1rem;
  border: 1px solid var(--p-content-border-color, #d1d5db);
  border-radius: var(--p-border-radius-md, 6px);
  background: var(--p-content-background, #fff);
}
.omero-card-title {
  margin: 0 0 1rem;
  font-size: 1rem;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.omero-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem 1rem;
}
.omero-field {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 0.35rem;
}
.omero-field label {
  font-weight: 600;
  font-size: 0.9rem;
}
.omero-field :deep(.p-inputtext),
.omero-field :deep(.p-inputnumber),
.omero-field :deep(.p-password) {
  width: 100%;
  min-width: 0;
}
.password-field {
  grid-column: 1 / -1;
}
.password-control,
.actions-cell {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.password-control {
  min-width: 0;
}
.password-control :deep(.p-password) {
  flex: 1 1 auto;
}
.actions-cell {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--p-content-border-color, #d1d5db);
  flex-wrap: wrap;
  justify-content: flex-end;
}
.empty-state {
  margin: 0;
  color: var(--p-text-muted-color, #777);
}
.error-text {
  color: var(--p-red-600, #dc2626);
  margin: 0;
  font-size: 0.9rem;
}

@media (max-width: 520px) {
  .omero-fields {
    grid-template-columns: minmax(0, 1fr);
  }

  .actions-cell {
    justify-content: flex-start;
  }
}
</style>
