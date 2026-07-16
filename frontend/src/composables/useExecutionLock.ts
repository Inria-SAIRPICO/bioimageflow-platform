import { computed, watch, type Ref } from 'vue'

import { api } from '@/api/client'
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
  graphSync: ExecutionGraphSync
  workflowName: string
  canvasId?: CanvasId | null
  acceptedDraftRevision?: Readonly<Ref<number | null>>
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
    const { nodes, graphSync, workflowName } = options
    // 1. Flush any pending debounced PUT /graph so the server has the
    //    latest state and its validation result is fresh.
    await graphSync.flushNow()
    if (options.isTargetActive?.() === false) return false
    const graph = graphSync.currentGraph?.value ?? options.graph

    // 2. If validation failed, abort the run. The caller (F5 Run button)
    //    is responsible for surfacing this to the user via a toast.
    const result = graphSync.validationResult.value
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

    // 3. Kick off the run.
    if (
      options.canvasId !== undefined
      || options.acceptedDraftRevision !== undefined
    ) {
      await exec.run(graph, nodes, workflowName, {
        canvasId: options.canvasId ?? null,
        draftRevision: options.acceptedDraftRevision?.value ?? null,
      })
    } else {
      await exec.run(graph, nodes, workflowName)
    }
    return true
  }

  async function unlockAfterExecution(
    graph: GraphState,
    workflowName?: string | null,
  ): Promise<void> {
    // After execution completes, re-validate the full graph so node
    // statuses reflect the cached/executed outputs authoritatively.
    await api.put('/api/v1/graph', {
      graph,
      workflow_name: workflowName ?? null,
    })
  }

  return {
    isLocked,
    lockForExecution,
    unlockAfterExecution,
  }
}
