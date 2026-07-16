import { reactive } from 'vue'
import { defineStore } from 'pinia'
import type { CanvasId } from '@/sessions/canvasSessionRegistry'

export type CanvasLifecycleOperation = 'saving' | 'discarding' | 'deleting'

export const useCanvasLifecycleStore = defineStore('canvasLifecycle', () => {
  const operations = reactive(new Map<CanvasId, CanvasLifecycleOperation>())

  function begin(canvasId: CanvasId, operation: CanvasLifecycleOperation): boolean {
    if (operations.has(canvasId)) return false
    operations.set(canvasId, operation)
    return true
  }

  function finish(canvasId: CanvasId): void {
    operations.delete(canvasId)
  }

  function operationFor(canvasId: CanvasId): CanvasLifecycleOperation | null {
    return operations.get(canvasId) ?? null
  }

  function isBusy(canvasId: CanvasId): boolean {
    return operations.has(canvasId)
  }

  return {
    operations,
    begin,
    finish,
    operationFor,
    isBusy,
  }
})
