import { computed, shallowRef } from 'vue'

function deepClone<T>(value: T): T {
  try {
    return structuredClone(value)
  } catch {
    // Fallback for non-cloneable objects (e.g., Vue reactive proxies in tests)
    return JSON.parse(JSON.stringify(value))
  }
}

export function useUndoRedo<T>(maxSize = 100) {
  const undoStack = shallowRef<T[]>([])
  const redoStack = shallowRef<T[]>([])

  const canUndo = computed(() => undoStack.value.length > 1)
  const canRedo = computed(() => redoStack.value.length > 0)

  function push(state: T): void {
    const next = [...undoStack.value, deepClone(state)]
    if (next.length > maxSize) {
      next.shift()
    }
    undoStack.value = next
    redoStack.value = []
  }

  function undo(): T | undefined {
    if (undoStack.value.length <= 1) return undefined
    const stack = [...undoStack.value]
    const current = stack.pop()!
    undoStack.value = stack
    redoStack.value = [...redoStack.value, current]
    return deepClone(stack[stack.length - 1])
  }

  function redo(): T | undefined {
    if (redoStack.value.length === 0) return undefined
    const stack = [...redoStack.value]
    const state = stack.pop()!
    redoStack.value = stack
    undoStack.value = [...undoStack.value, state]
    return deepClone(state)
  }

  function clear(): void {
    undoStack.value = []
    redoStack.value = []
  }

  return { push, undo, redo, canUndo, canRedo, clear }
}
