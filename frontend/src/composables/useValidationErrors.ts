import { computed, type Ref } from 'vue'
import type { GraphValidationError, ValidationResult } from '@/api/types'

/**
 * Derive per-node, per-edge, per-field, and global error state from a
 * {@link ValidationResult}. Intended for consumption by Node Panel and
 * Canvas components.
 */
export function useValidationErrors(
  validationResult: Ref<ValidationResult | null>,
) {
  const errors = computed<GraphValidationError[]>(
    () => validationResult.value?.errors ?? [],
  )

  const nodeErrors = computed<Record<string, GraphValidationError[]>>(() => {
    const by: Record<string, GraphValidationError[]> = {}
    for (const err of errors.value) {
      if (err.type === 'cycle_detected') continue
      if (err.edge_id) continue
      if (!err.node) continue
      ;(by[err.node] ??= []).push(err)
    }
    return by
  })

  const edgeErrors = computed<Record<string, GraphValidationError[]>>(() => {
    const by: Record<string, GraphValidationError[]> = {}
    for (const err of errors.value) {
      if (!err.edge_id) continue
      ;(by[err.edge_id] ??= []).push(err)
    }
    return by
  })

  const globalErrors = computed<GraphValidationError[]>(() =>
    errors.value.filter(
      (e) => e.type === 'cycle_detected' || (!e.node && !e.edge_id),
    ),
  )

  function getFieldErrors(
    nodeId: string,
    fieldName: string,
  ): GraphValidationError[] {
    return errors.value.filter(
      (e) => e.node === nodeId && e.field === fieldName,
    )
  }

  function getEdgeErrors(edgeId: string): GraphValidationError[] {
    return errors.value.filter((e) => e.edge_id === edgeId)
  }

  const hasErrors = computed(() => validationResult.value?.valid === false)

  return {
    nodeErrors,
    edgeErrors,
    globalErrors,
    getFieldErrors,
    getEdgeErrors,
    hasErrors,
  }
}
