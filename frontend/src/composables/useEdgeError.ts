import { computed, type Ref } from 'vue'
import type { GraphValidationError } from '@/api/types'

/**
 * Derive `hasError` and a joined-detail tooltip string for a Vue Flow custom
 * edge whose `data.errors` is populated by `CanvasView`. Used by both edge
 * variants (column-ref and positional).
 */
export function useEdgeError(
  data: Ref<{ errors?: GraphValidationError[] } | undefined>,
) {
  const hasError = computed(() => (data.value?.errors?.length ?? 0) > 0)
  const errorTitle = computed(() =>
    (data.value?.errors ?? []).map((e) => e.detail).join('\n'),
  )
  return { hasError, errorTitle }
}
