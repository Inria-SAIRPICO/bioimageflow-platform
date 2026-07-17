<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type {
  CanvasPersistenceIssue,
  CanvasPersistenceState,
} from '@/composables/useCanvasPersistence'

const props = withDefaults(defineProps<{
  state: CanvasPersistenceState
  issue: CanvasPersistenceIssue | null
  conflictActionLabel?: string
  conflictSecondaryActionLabel?: string | null
  conflictReopenLabel?: string | null
  conflictActionsDisabled?: boolean
}>(), {
  conflictActionLabel: 'Review conflict',
  conflictSecondaryActionLabel: null,
  conflictReopenLabel: null,
  conflictActionsDisabled: false,
})

const emit = defineEmits<{
  retry: [issueId: string]
  dismiss: [issueId: string]
  'resolve-conflict': [issueId: string]
  'use-latest': [issueId: string]
  'reopen-conflict': [issueId: string]
}>()

const visibleIssue = computed(() => (
  props.issue?.dismissed === false ? props.issue : null
))
const collapsedConflict = computed(() => (
  props.conflictReopenLabel !== null
  && props.issue?.kind === 'conflict'
  && props.issue.dismissed
    ? props.issue
    : null
))
const issueElement = ref<HTMLElement | null>(null)
const collapsedConflictButton = ref<HTMLButtonElement | null>(null)
let focusCollapsedIssueId: string | null = null
let focusReopenedIssueId: string | null = null

watch(collapsedConflict, (issue) => {
  if (issue === null || issue.id !== focusCollapsedIssueId) return
  focusCollapsedIssueId = null
  collapsedConflictButton.value?.focus()
}, { flush: 'post' })

watch(visibleIssue, (issue) => {
  if (issue === null || issue.id !== focusReopenedIssueId) return
  focusReopenedIssueId = null
  issueElement.value?.focus()
}, { flush: 'post' })

function dismissIssue(issue: CanvasPersistenceIssue): void {
  if (issue.kind === 'conflict' && props.conflictReopenLabel !== null) {
    focusCollapsedIssueId = issue.id
  }
  emit('dismiss', issue.id)
}

function reopenConflict(issue: CanvasPersistenceIssue): void {
  focusReopenedIssueId = issue.id
  emit('reopen-conflict', issue.id)
}

const SAVING_FEEDBACK_DELAY_MS = 200
const showSaving = ref(false)
let savingTimer: ReturnType<typeof setTimeout> | null = null

function cancelSavingTimer(): void {
  if (savingTimer === null) return
  clearTimeout(savingTimer)
  savingTimer = null
}

watch(
  () => props.state,
  (state) => {
    cancelSavingTimer()
    showSaving.value = false
    if (state !== 'saving') return
    savingTimer = setTimeout(() => {
      savingTimer = null
      showSaving.value = true
    }, SAVING_FEEDBACK_DELAY_MS)
  },
  { immediate: true },
)

onBeforeUnmount(cancelSavingTimer)
</script>

<template>
  <div class="canvas-persistence-feedback" aria-atomic="true">
    <div
      v-if="showSaving && visibleIssue === null"
      class="canvas-persistence-feedback__saving"
      data-testid="canvas-persistence-saving"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <i class="pi pi-spin pi-spinner" aria-hidden="true" />
      <span>Saving…</span>
    </div>

    <div
      v-else-if="visibleIssue !== null"
      ref="issueElement"
      class="canvas-persistence-feedback__issue"
      :class="`canvas-persistence-feedback__issue--${visibleIssue.kind}`"
      data-testid="canvas-persistence-issue"
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
      tabindex="0"
    >
      <i
        class="pi pi-exclamation-triangle canvas-persistence-feedback__icon"
        aria-hidden="true"
      />
      <div class="canvas-persistence-feedback__copy">
        <strong>{{ visibleIssue.summary }}</strong>
        <span>{{ visibleIssue.detail }}</span>
      </div>
      <div class="canvas-persistence-feedback__actions">
        <button
          v-if="visibleIssue.kind === 'error'"
          type="button"
          data-testid="canvas-persistence-retry"
          @click="emit('retry', visibleIssue.id)"
        >
          Retry
        </button>
        <slot
          v-else
          name="conflict-actions"
          :issue="visibleIssue"
        >
          <button
            v-if="conflictSecondaryActionLabel !== null"
            type="button"
            data-testid="canvas-persistence-use-latest"
            :disabled="conflictActionsDisabled"
            @click="emit('use-latest', visibleIssue.id)"
          >
            {{ conflictSecondaryActionLabel }}
          </button>
          <button
            type="button"
            data-testid="canvas-persistence-resolve-conflict"
            :disabled="conflictActionsDisabled"
            @click="emit('resolve-conflict', visibleIssue.id)"
          >
            {{ conflictActionLabel }}
          </button>
        </slot>
        <button
          type="button"
          data-testid="canvas-persistence-dismiss"
          :aria-label="conflictReopenLabel !== null && visibleIssue.kind === 'conflict'
            ? 'Hide persistence conflict details'
            : 'Dismiss persistence message'"
          @click="dismissIssue(visibleIssue)"
        >
          {{ conflictReopenLabel !== null && visibleIssue.kind === 'conflict'
            ? 'Hide details'
            : 'Dismiss' }}
        </button>
      </div>
    </div>

    <button
      v-else-if="collapsedConflict !== null"
      ref="collapsedConflictButton"
      type="button"
      class="canvas-persistence-feedback__collapsed-conflict"
      data-testid="canvas-persistence-reopen-conflict"
      :disabled="conflictActionsDisabled"
      @click="reopenConflict(collapsedConflict)"
    >
      <i class="pi pi-exclamation-triangle" aria-hidden="true" />
      <span>{{ conflictReopenLabel }}</span>
    </button>
  </div>
</template>

<style scoped>
.canvas-persistence-feedback {
  pointer-events: none;
}

.canvas-persistence-feedback__saving,
.canvas-persistence-feedback__issue,
.canvas-persistence-feedback__collapsed-conflict {
  align-items: center;
  background: color-mix(in srgb, var(--bif-surface) 94%, transparent);
  border: 1px solid var(--bif-border-muted);
  border-radius: 0.375rem;
  display: flex;
  gap: 0.5rem;
  padding: 0.4rem 0.65rem;
  pointer-events: auto;
}

.canvas-persistence-feedback__collapsed-conflict {
  background: color-mix(in srgb, var(--p-amber-50, #fffbeb) 96%, transparent);
  border-color: var(--p-amber-600, #d97706);
  color: var(--p-text-color, #111827);
  cursor: pointer;
  font: inherit;
  width: max-content;
}

.canvas-persistence-feedback__saving {
  color: var(--p-text-muted-color, #64748b);
  font-size: 0.8rem;
  width: max-content;
}

.canvas-persistence-feedback__issue {
  background: color-mix(in srgb, var(--p-red-50, #fef2f2) 96%, transparent);
  border-color: var(--p-red-500, #dc2626);
  color: var(--p-text-color, #111827);
}

.canvas-persistence-feedback__issue--conflict {
  background: color-mix(in srgb, var(--p-amber-50, #fffbeb) 96%, transparent);
  border-color: var(--p-amber-600, #d97706);
}

.canvas-persistence-feedback__icon {
  color: var(--p-red-600, #b91c1c);
}

.canvas-persistence-feedback__issue--conflict .canvas-persistence-feedback__icon {
  color: var(--p-amber-700, #b45309);
}

.canvas-persistence-feedback__copy {
  display: flex;
  flex: 1;
  flex-direction: column;
  font-size: 0.9rem;
  gap: 0.15rem;
  line-height: 1.35;
  min-width: 0;
}

.canvas-persistence-feedback__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.canvas-persistence-feedback__actions button {
  background: var(--bif-surface, #fff);
  border: 1px solid currentColor;
  border-radius: 0.375rem;
  color: inherit;
  cursor: pointer;
  font: inherit;
  padding: 0.35rem 0.6rem;
}

.canvas-persistence-feedback__actions button:focus-visible,
.canvas-persistence-feedback__issue:focus-visible,
.canvas-persistence-feedback__collapsed-conflict:focus-visible {
  outline: 2px solid var(--p-primary-color, #2563eb);
  outline-offset: 2px;
}

.canvas-persistence-feedback__collapsed-conflict:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
</style>
