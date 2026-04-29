import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

import {
  useFieldFocusTracker,
  __resetForTests,
} from '@/composables/useFieldFocusTracker'

describe('useFieldFocusTracker', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    __resetForTests()
  })

  it('tracks focus on a single field', () => {
    const { trackFocus, isAnyFocused } = useFieldFocusTracker()
    trackFocus('node1.diameter')
    expect(isAnyFocused('node1')).toBe(true)
  })

  it('clears focus on blur', () => {
    const { trackFocus, trackBlur, isAnyFocused } = useFieldFocusTracker()
    trackFocus('node1.diameter')
    trackBlur('node1.diameter')
    expect(isAnyFocused('node1')).toBe(false)
  })

  it('isAnyFocused considers all fields on the node', () => {
    const { trackFocus, trackBlur, isAnyFocused } = useFieldFocusTracker()
    trackFocus('node1.diameter')
    trackFocus('node1.threshold')
    expect(isAnyFocused('node1')).toBe(true)
    trackBlur('node1.diameter')
    expect(isAnyFocused('node1')).toBe(true)
    trackBlur('node1.threshold')
    expect(isAnyFocused('node1')).toBe(false)
  })

  it('isolates focus tracking between nodes', () => {
    const { trackFocus, isAnyFocused } = useFieldFocusTracker()
    trackFocus('nodeA.x')
    expect(isAnyFocused('nodeA')).toBe(true)
    expect(isAnyFocused('nodeB')).toBe(false)
  })

  it('onBlurOnce fires when the field next blurs', async () => {
    const { trackFocus, trackBlur, onBlurOnce } = useFieldFocusTracker()
    const cb = vi.fn()
    trackFocus('node1.diameter')
    onBlurOnce('node1.diameter', cb)
    expect(cb).not.toHaveBeenCalled()
    trackBlur('node1.diameter')
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('onBlurOnce only fires once', () => {
    const { trackFocus, trackBlur, onBlurOnce } = useFieldFocusTracker()
    const cb = vi.fn()
    trackFocus('node1.diameter')
    onBlurOnce('node1.diameter', cb)
    trackBlur('node1.diameter')
    trackFocus('node1.diameter')
    trackBlur('node1.diameter')
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('onBlurOnce on already-unfocused field fires on next microtask', async () => {
    const { onBlurOnce } = useFieldFocusTracker()
    const cb = vi.fn()
    onBlurOnce('node1.diameter', cb)
    expect(cb).not.toHaveBeenCalled()
    await Promise.resolve()
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('multiple onBlurOnce callbacks all fire', () => {
    const { trackFocus, trackBlur, onBlurOnce } = useFieldFocusTracker()
    const a = vi.fn()
    const b = vi.fn()
    trackFocus('node1.diameter')
    onBlurOnce('node1.diameter', a)
    onBlurOnce('node1.diameter', b)
    trackBlur('node1.diameter')
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
    trackFocus('node1.diameter')
    trackFocus('node1.threshold')
    const cb = vi.fn()
    onBlurOnce('node1.diameter', cb)

    clearTracking('node1')

    expect(isAnyFocused('node1')).toBe(false)
    // Pending callbacks for the cleared node are dropped — they won't fire.
    trackFocus('node1.diameter')
    trackFocus('node2.diameter')
    expect(isAnyFocused('node2')).toBe(true)
  })

  it('returns a stable singleton across calls', () => {
    const a = useFieldFocusTracker()
    const b = useFieldFocusTracker()
    a.trackFocus('node1.diameter')
    expect(b.isAnyFocused('node1')).toBe(true)
  })
})
