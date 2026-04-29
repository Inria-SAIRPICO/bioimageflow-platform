import { reactive } from 'vue'

/**
 * Tracks which input fields currently hold the user's focus, so callers
 * (e.g. useHotReload) can defer mutations to a node's parameter shape
 * until the field is no longer being edited. Field keys use the
 * convention `<nodeId>.<fieldName>`.
 *
 * The tracker is a process-wide singleton — every call to
 * useFieldFocusTracker() returns the same maps, so the parameter row
 * that fires `trackFocus` and the composable that observes
 * `isAnyFocused` see the same state without prop drilling.
 */

interface State {
  focused: Map<string, boolean>
  blurOnceCallbacks: Map<string, Array<() => void>>
}

function createState(): State {
  return {
    focused: reactive(new Map<string, boolean>()),
    blurOnceCallbacks: new Map<string, Array<() => void>>(),
  }
}

let state: State = createState()

function nodeIdOf(fieldKey: string): string {
  const idx = fieldKey.indexOf('.')
  return idx === -1 ? fieldKey : fieldKey.slice(0, idx)
}

export function useFieldFocusTracker() {
  function trackFocus(fieldKey: string): void {
    state.focused.set(fieldKey, true)
  }

  function trackBlur(fieldKey: string): void {
    state.focused.set(fieldKey, false)
    const cbs = state.blurOnceCallbacks.get(fieldKey)
    if (cbs && cbs.length > 0) {
      state.blurOnceCallbacks.delete(fieldKey)
      for (const cb of cbs) {
        try {
          cb()
        } catch (err) {
          console.error('[useFieldFocusTracker] onBlurOnce callback threw', err)
        }
      }
    }
  }

  function isAnyFocused(nodeId: string): boolean {
    for (const [key, focused] of state.focused) {
      if (focused && nodeIdOf(key) === nodeId) {
        return true
      }
    }
    return false
  }

  function onBlurOnce(fieldKey: string, cb: () => void): void {
    if (state.focused.get(fieldKey) === true) {
      const existing = state.blurOnceCallbacks.get(fieldKey) ?? []
      existing.push(cb)
      state.blurOnceCallbacks.set(fieldKey, existing)
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

  function clearTracking(nodeId: string): void {
    for (const key of [...state.focused.keys()]) {
      if (nodeIdOf(key) === nodeId) {
        state.focused.delete(key)
      }
    }
    for (const key of [...state.blurOnceCallbacks.keys()]) {
      if (nodeIdOf(key) === nodeId) {
        state.blurOnceCallbacks.delete(key)
      }
    }
  }

  return {
    trackFocus,
    trackBlur,
    isAnyFocused,
    onBlurOnce,
    clearTracking,
  }
}

export function __resetForTests(): void {
  state = createState()
}
