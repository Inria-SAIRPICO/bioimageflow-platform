import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

import {
  useFieldFocusTracker,
  __resetForTests,
} from '@/composables/useFieldFocusTracker'
import { canvasIdFromPanelId } from '@/sessions/canvasSessionRegistry'

const canvasA = canvasIdFromPanelId('workflow:a')
const canvasB = canvasIdFromPanelId('workflow:b')

function field(
  canvasId = canvasA,
  nodeId = 'node1',
  fieldName = 'diameter',
) {
  return { canvasId, nodeId, fieldName }
}

describe('useFieldFocusTracker', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    __resetForTests()
  })

  it('tracks focus on a single field', () => {
    const { trackFocus, isAnyFocused } = useFieldFocusTracker()
    trackFocus(field())
    expect(isAnyFocused(canvasA, 'node1')).toBe(true)
  })

  it('clears focus on blur', () => {
    const { trackFocus, trackBlur, isAnyFocused } = useFieldFocusTracker()
    trackFocus(field())
    trackBlur(field())
    expect(isAnyFocused(canvasA, 'node1')).toBe(false)
  })

  it('isAnyFocused considers all fields on the node', () => {
    const { trackFocus, trackBlur, isAnyFocused } = useFieldFocusTracker()
    trackFocus(field())
    trackFocus(field(canvasA, 'node1', 'threshold'))
    expect(isAnyFocused(canvasA, 'node1')).toBe(true)
    trackBlur(field())
    expect(isAnyFocused(canvasA, 'node1')).toBe(true)
    trackBlur(field(canvasA, 'node1', 'threshold'))
    expect(isAnyFocused(canvasA, 'node1')).toBe(false)
  })

  it('isolates focus tracking between nodes', () => {
    const { trackFocus, isAnyFocused } = useFieldFocusTracker()
    trackFocus(field(canvasA, 'nodeA', 'x'))
    expect(isAnyFocused(canvasA, 'nodeA')).toBe(true)
    expect(isAnyFocused(canvasA, 'nodeB')).toBe(false)
  })

  it('isolates identical node and field names between canvases', () => {
    const { trackFocus, isAnyFocused, focusedFields } = useFieldFocusTracker()
    trackFocus(field(canvasA, 'shared', 'diameter'))

    expect(isAnyFocused(canvasA, 'shared')).toBe(true)
    expect(isAnyFocused(canvasB, 'shared')).toBe(false)
    expect(focusedFields(canvasA, 'shared')).toEqual([
      field(canvasA, 'shared', 'diameter'),
    ])
    expect(focusedFields(canvasB, 'shared')).toEqual([])
  })

  it('onBlurOnce fires when the field next blurs', async () => {
    const { trackFocus, trackBlur, onBlurOnce } = useFieldFocusTracker()
    const cb = vi.fn()
    trackFocus(field())
    onBlurOnce(field(), cb)
    expect(cb).not.toHaveBeenCalled()
    trackBlur(field())
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('onBlurOnce only fires once', () => {
    const { trackFocus, trackBlur, onBlurOnce } = useFieldFocusTracker()
    const cb = vi.fn()
    trackFocus(field())
    onBlurOnce(field(), cb)
    trackBlur(field())
    trackFocus(field())
    trackBlur(field())
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('onBlurOnce on already-unfocused field fires on next microtask', async () => {
    const { onBlurOnce } = useFieldFocusTracker()
    const cb = vi.fn()
    onBlurOnce(field(), cb)
    expect(cb).not.toHaveBeenCalled()
    await Promise.resolve()
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('multiple onBlurOnce callbacks all fire', () => {
    const { trackFocus, trackBlur, onBlurOnce } = useFieldFocusTracker()
    const a = vi.fn()
    const b = vi.fn()
    trackFocus(field())
    onBlurOnce(field(), a)
    onBlurOnce(field(), b)
    trackBlur(field())
    expect(a).toHaveBeenCalled()
    expect(b).toHaveBeenCalled()
  })

  it('clearTracking removes all entries for a node', () => {
    const {
      trackFocus,
      isAnyFocused,
      clearTracking,
      onBlurOnce,
    } = useFieldFocusTracker()
    trackFocus(field())
    trackFocus(field(canvasA, 'node1', 'threshold'))
    const cb = vi.fn()
    onBlurOnce(field(), cb)

    clearTracking(canvasA, 'node1')

    expect(isAnyFocused(canvasA, 'node1')).toBe(false)
    // Pending callbacks for the cleared node are dropped — they won't fire.
    trackFocus(field())
    trackFocus(field(canvasA, 'node2'))
    expect(isAnyFocused(canvasA, 'node2')).toBe(true)
  })

  it('returns a stable singleton across calls', () => {
    const a = useFieldFocusTracker()
    const b = useFieldFocusTracker()
    a.trackFocus(field())
    expect(b.isAnyFocused(canvasA, 'node1')).toBe(true)
  })
})
