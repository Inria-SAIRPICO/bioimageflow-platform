import { reactive } from 'vue'
import type { CanvasId } from '@/sessions/canvasSessionRegistry'

/**
 * Tracks focused parameter fields across the active NodePanel and mounted
 * canvases. Canvas identity is part of every key because node ids are only
 * unique within a graph.
 */

export interface FieldFocusTarget {
  canvasId: CanvasId
  nodeId: string
  fieldName: string
}

interface State {
  focused: Map<string, FieldFocusTarget>
  blurOnceCallbacks: Map<string, Array<() => void>>
}

function createState(): State {
  return {
    focused: reactive(new Map<string, FieldFocusTarget>()),
    blurOnceCallbacks: new Map<string, Array<() => void>>(),
  }
}

let state: State = createState()

function targetKey(target: FieldFocusTarget): string {
  return JSON.stringify([target.canvasId, target.nodeId, target.fieldName])
}

function belongsToNode(
  target: FieldFocusTarget,
  canvasId: CanvasId,
  nodeId: string,
): boolean {
  return target.canvasId === canvasId && target.nodeId === nodeId
}

export function useFieldFocusTracker() {
  function trackFocus(target: FieldFocusTarget): void {
    state.focused.set(targetKey(target), { ...target })
  }

  function trackBlur(target: FieldFocusTarget): void {
    const key = targetKey(target)
    state.focused.delete(key)
    const cbs = state.blurOnceCallbacks.get(key)
    if (cbs && cbs.length > 0) {
      state.blurOnceCallbacks.delete(key)
      for (const cb of cbs) {
        try {
          cb()
        } catch (err) {
          console.error('[useFieldFocusTracker] onBlurOnce callback threw', err)
        }
      }
    }
  }

  function focusedFields(canvasId: CanvasId, nodeId: string): FieldFocusTarget[] {
    return [...state.focused.values()]
      .filter(target => belongsToNode(target, canvasId, nodeId))
      .map(target => ({ ...target }))
  }

  function isAnyFocused(canvasId: CanvasId, nodeId: string): boolean {
    return focusedFields(canvasId, nodeId).length > 0
  }

  function onBlurOnce(target: FieldFocusTarget, cb: () => void): void {
    const key = targetKey(target)
    if (state.focused.has(key)) {
      const existing = state.blurOnceCallbacks.get(key) ?? []
      existing.push(cb)
      state.blurOnceCallbacks.set(key, existing)
    } else {
      // Already unfocused — fire on the next microtask to keep callers'
      // ordering predictable (no synchronous side effects).
      void Promise.resolve().then(() => {
        try {
          cb()
        } catch (err) {
          console.error('[useFieldFocusTracker] onBlurOnce callback threw', err)
        }
      })
    }
  }

  function clearTracking(canvasId: CanvasId, nodeId: string): void {
    for (const [key, target] of [...state.focused.entries()]) {
      if (belongsToNode(target, canvasId, nodeId)) {
        state.focused.delete(key)
        state.blurOnceCallbacks.delete(key)
      }
    }
  }

  return {
    trackFocus,
    trackBlur,
    focusedFields,
    isAnyFocused,
    onBlurOnce,
    clearTracking,
  }
}

export function __resetForTests(): void {
  state = createState()
}
