import { computed, watch, type Ref } from 'vue'

import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'
import { validationErrorsForExecution } from '@/utils/executionSelection'
import type { GraphState, ValidationResult } from '@/api/types'
import type { CanvasId } from '@/sessions/canvasSessionRegistry'

export interface ExecutionGraphSync {
  flushNow: () => Promise<unknown>
  validationResult: Ref<ValidationResult | null>
  currentGraph?: Ref<GraphState>
}

export interface LockForExecutionOptions {
  graph: GraphState
  nodes?: string[]
  validationResult: ValidationResult | null
  workflowName: string
  canvasId?: CanvasId | null
  acceptedDraftRevision?: number | null
  isTargetActive?: () => boolean
}

export function useExecutionLock() {
  const exec = useExecutionStore()
  const ui = useUIStore()

  // Sync the global canvas lock with every non-idle execution phase.
  watch(
    () => exec.isMutationLocked,
    (locked) => {
      ui.setExecutionLocked(locked)
    },
    { immediate: true, flush: 'sync' },
  )

  const isLocked = computed(() => ui.isExecutionLocked)

  async function lockForExecution(
    options: LockForExecutionOptions,
  ): Promise<boolean> {
    const { graph, nodes, validationResult, workflowName } = options
    // Preparation already flushed and captured an immutable graph,
    // validation result, and accepted draft revision. Keep this final step
    // synchronous until exec.run() enters `starting`, so no newer graph can
    // inherit a confirmation made for the prepared snapshot.
    if (options.isTargetActive?.() === false) return false

    // If validation failed, abort the run. The caller (F5 Run button)
    // is responsible for surfacing this to the user via a toast.
    const result = validationResult
    const blockingErrors = result
      ? validationErrorsForExecution(result.errors ?? [], graph, nodes)
      : []
    if (
      result &&
      result.valid === false &&
      (blockingErrors.length > 0 || (result.errors ?? []).length === 0)
    ) {
      throw new Error(
        'Validation errors found — fix them before running',
      )
    }

    // Kick off the exact prepared input.
    if (
      options.canvasId !== undefined
      || options.acceptedDraftRevision !== undefined
    ) {
      await exec.run(graph, nodes, workflowName, {
        canvasId: options.canvasId ?? null,
        draftRevision: options.acceptedDraftRevision ?? null,
      })
    } else {
      await exec.run(graph, nodes, workflowName)
    }
    return true
  }

  return {
    isLocked,
    lockForExecution,
  }
}
