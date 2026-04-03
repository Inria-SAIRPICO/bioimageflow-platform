import { describe, it, expect } from 'vitest'
import { useUndoRedo } from '../useUndoRedo'

describe('useUndoRedo', () => {
  it('starts with canUndo and canRedo false', () => {
    const { canUndo, canRedo } = useUndoRedo<string>()
    expect(canUndo.value).toBe(false)
    expect(canRedo.value).toBe(false)
  })

  it('push enables undo', () => {
    const { push, canUndo } = useUndoRedo<string>()
    push('a')
    push('b')
    expect(canUndo.value).toBe(true)
  })

  it('undo/redo round-trip', () => {
    const { push, undo, redo, canUndo, canRedo } = useUndoRedo<string>()
    push('a')
    push('b')

    const prev = undo()
    expect(prev).toBe('a')
    expect(canRedo.value).toBe(true)

    const next = redo()
    expect(next).toBe('b')
    expect(canRedo.value).toBe(false)
  })

  it('push after undo clears redo stack', () => {
    const { push, undo, canRedo } = useUndoRedo<string>()
    push('a')
    push('b')
    undo()
    expect(canRedo.value).toBe(true)

    push('c')
    expect(canRedo.value).toBe(false)
  })

  it('max size eviction', () => {
    const { push, undo, canUndo } = useUndoRedo<number>(3)
    push(1)
    push(2)
    push(3)
    push(4) // should evict 1

    // Can undo 3 times (4->3, 3->2, 2->oldest remaining)
    expect(undo()).toBe(3)
    expect(undo()).toBe(2)
    expect(undo()).toBeUndefined()
    expect(canUndo.value).toBe(false)
  })

  it('undo on empty stack returns undefined', () => {
    const { undo } = useUndoRedo<string>()
    expect(undo()).toBeUndefined()
  })

  it('redo on empty stack returns undefined', () => {
    const { redo } = useUndoRedo<string>()
    expect(redo()).toBeUndefined()
  })

  it('clear resets both stacks', () => {
    const { push, undo, clear, canUndo, canRedo } = useUndoRedo<string>()
    push('a')
    push('b')
    push('c')
    undo()
    expect(canUndo.value).toBe(true)
    expect(canRedo.value).toBe(true)

    clear()
    expect(canUndo.value).toBe(false)
    expect(canRedo.value).toBe(false)
  })

  it('uses structuredClone for isolation', () => {
    const { push, undo } = useUndoRedo<{ x: number }>()
    const obj = { x: 1 }
    push(obj)
    push({ x: 2 })
    obj.x = 999 // mutate original

    const prev = undo()
    expect(prev).toEqual({ x: 1 }) // should be isolated
  })
})
