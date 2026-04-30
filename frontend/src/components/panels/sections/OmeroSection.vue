<script setup lang="ts">
import { ref, watch } from 'vue'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Tag from 'primevue/tag'
import { useConfirm } from 'primevue/useconfirm'
import type { OMEROInstancePatch, SettingsResponse } from '@/api/types'

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

function toPatch(passwordIndex: number | null = null): OMEROInstancePatch[] {
  return rows.value.map((row, index) => {
    const patch: OMEROInstancePatch = {
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
    <div class="omero-table" role="table" aria-label="OMERO instances">
      <div class="omero-row omero-header" role="row">
        <span>Name</span>
        <span>Host</span>
        <span>Port</span>
        <span>Username</span>
        <span>Password</span>
        <span>Actions</span>
      </div>
      <div
        v-for="(row, index) in rows"
        :key="index"
        class="omero-row"
        role="row"
        :data-testid="`omero-row-${index}`"
      >
        <InputText v-model="row.name" aria-label="Name" />
        <InputText v-model="row.host" aria-label="Host" />
        <InputNumber
          v-model="row.port"
          aria-label="Port"
          :min="1"
          :max="65535"
          :use-grouping="false"
        />
        <InputText v-model="row.username" aria-label="Username" />
        <div class="password-cell">
          <Password
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
        <div class="actions-cell">
          <Button
            icon="pi pi-save"
            text
            rounded
            aria-label="Save OMERO instance"
            @click="emitRows(index)"
          />
          <Button
            icon="pi pi-copy"
            text
            rounded
            aria-label="Duplicate OMERO instance"
            @click="duplicateRow(index)"
          />
          <Button
            icon="pi pi-trash"
            text
            rounded
            severity="danger"
            aria-label="Remove OMERO instance"
            @click="removeRow(index)"
          />
        </div>
      </div>
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
.omero-table {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  overflow-x: auto;
}
.omero-row {
  display: grid;
  grid-template-columns: minmax(8rem, 1fr) minmax(10rem, 1.3fr) 6rem minmax(8rem, 1fr) minmax(12rem, 1.2fr) auto;
  gap: 0.5rem;
  align-items: center;
  min-width: 760px;
}
.omero-header {
  color: var(--p-text-muted-color, #777);
  font-size: 0.85rem;
  font-weight: 600;
}
.password-cell,
.actions-cell {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.actions-cell {
  justify-content: flex-end;
}
.error-text {
  color: var(--p-red-600, #dc2626);
  margin: 0;
  font-size: 0.9rem;
}
</style>
