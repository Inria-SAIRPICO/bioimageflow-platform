import { describe, expect, it, vi } from 'vitest'
import {
  CanvasSessionRegistry,
  canvasIdFromPanelId,
  type CanvasSessionDescriptor,
} from '../canvasSessionRegistry'

function rootSession(panelId: string, workflowId: string): CanvasSessionDescriptor {
  return {
    kind: 'root',
    canvasId: canvasIdFromPanelId(panelId),
    workflowId,
  }
}

describe('CanvasSessionRegistry', () => {
  it('uses the Dockview panel id as the stable branded canvas id', () => {
    expect(canvasIdFromPanelId('workflow:folder%2Fexample')).toBe(
      'workflow:folder%2Fexample',
    )
    expect(() => canvasIdFromPanelId('')).toThrow('Dockview panel id')
  })

  it('does not activate as a side effect of registration, lookup, or coordinator creation', () => {
    const dispose = vi.fn()
    const registry = new CanvasSessionRegistry()
    const descriptor = rootSession('workflow:a', 'a')

    registry.register(descriptor)
    expect(registry.activeCanvasId.value).toBeNull()

    registry.get(descriptor.canvasId)
    expect(registry.activeCanvasId.value).toBeNull()

    registry.getOrCreateCoordinator(descriptor.canvasId, () => ({ dispose }))
    expect(registry.activeCanvasId.value).toBeNull()

    registry.activate(descriptor.canvasId)
    expect(registry.activeCanvasId.value).toBe(descriptor.canvasId)
  })

  it('does not expose mutable descriptor identity', () => {
    const registry = new CanvasSessionRegistry()
    const descriptor = rootSession('workflow:a', 'a')
    const registered = registry.register(descriptor)

    expect(() => {
      ;(registered.descriptor as any).workflowId = 'corrupted'
    }).toThrow()
    expect(registry.get(descriptor.canvasId)?.descriptor).toEqual(descriptor)
  })

  it('disposes resources belonging only to the unregistered canvas', () => {
    const disposeA = vi.fn()
    const disposeB = vi.fn()
    const registry = new CanvasSessionRegistry()
    const a = rootSession('workflow:a', 'a')
    const b = rootSession('workflow:b', 'b')

    registry.register(a)
    registry.register(b)
    registry.getOrCreateCoordinator(a.canvasId, () => ({ dispose: disposeA }))
    registry.getOrCreateCoordinator(b.canvasId, () => ({ dispose: disposeB }))
    registry.activate(a.canvasId)

    registry.unregister(a.canvasId)

    expect(disposeA).toHaveBeenCalledOnce()
    expect(disposeB).not.toHaveBeenCalled()
    expect(registry.get(b.canvasId)?.descriptor).toEqual(b)
    expect(registry.activeCanvasId.value).toBeNull()
  })
})
