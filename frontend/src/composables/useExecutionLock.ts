import { computed, watch, type Ref } from 'vue'

import { api } from '@/api/client'
import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'
import { validationErrorsForExecution } from '@/utils/executionSelection'
import type { GraphState, ValidationResult } from '@/api/types'

export interface ExecutionGraphSync {
  flushNow: () => Promise<void>
  validationResult: Ref<ValidationResult | null>
  draft_id?: Ref<string | null>
  revision?: Ref<number>
}

export interface LockForExecutionOptions {
  graph: GraphState
  nodes?: string[]
  graphSync: ExecutionGraphSync
  workflowName?: string | null
}

export function useExecutionLock() {
  const exec = useExecutionStore()
  const ui = useUIStore()

  // Sync uiStore.isExecutionLocked with executionStore.isRunning.
  watch(
    () => exec.isRunning,
    (running) => {
      ui.setExecutionLocked(running)
    },
    { immediate: true },
  )

  const isLocked = computed(() => ui.isExecutionLocked)

  async function lockForExecution(
    options: LockForExecutionOptions,
  ): Promise<void> {
    const { graph, nodes, graphSync, workflowName } = options
    // 1. Flush any pending debounced PUT /graph so the server has the
    //    latest state and its validation result is fresh.
    await graphSync.flushNow()

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
    const draftId = graphSync.draft_id?.value ?? null
    const revision = graphSync.revision?.value ?? null
    if (draftId) {
      await exec.run(graph, nodes, workflowName, {
        draft_id: draftId,
        revision,
      })
      return
    }
    await exec.run(graph, nodes, workflowName)
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
