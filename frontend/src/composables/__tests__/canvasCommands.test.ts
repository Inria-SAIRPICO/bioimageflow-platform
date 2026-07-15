import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  _resetCanvasCommandsForTest,
  useCanvasCommands,
} from '../useCanvasCommands'
import { canvasIdFromPanelId } from '@/sessions/canvasSessionRegistry'
import { graphSyncCanvasSessions } from '../useGraphSync'

afterEach(() => {
  _resetCanvasCommandsForTest()
})

describe('active canvas commands', () => {
  it('routes Save to the active nested canvas command', async () => {
    const rootId = canvasIdFromPanelId('workflow:root')
    const nestedId = canvasIdFromPanelId('sub-workflow:nested')
    const saveNested = vi.fn()
    useCanvasCommands({
      descriptor: {
        kind: 'root',
        canvasId: rootId,
        workflowId: 'root',
      },
      updateParameter: vi.fn(),
    })
    useCanvasCommands({
      descriptor: {
        kind: 'nested',
        canvasId: nestedId,
        sessionId: 'nested',
        parentCanvasId: rootId,
      },
      save: saveNested,
      updateParameter: vi.fn(),
    })
    const active = useCanvasCommands()

    graphSyncCanvasSessions.activate(nestedId)

    await expect(active.routeSave()).resolves.toBe('nested')
    expect(saveNested).toHaveBeenCalledOnce()
  })

  it('identifies active root and unavailable routing without falling through', async () => {
    const rootId = canvasIdFromPanelId('workflow:root')
    useCanvasCommands({
      descriptor: {
        kind: 'root',
        canvasId: rootId,
        workflowId: 'root',
      },
      updateParameter: vi.fn(),
    })
    const active = useCanvasCommands()

    await expect(active.routeSave()).resolves.toBe('unavailable')

    graphSyncCanvasSessions.activate(rootId)
    await expect(active.routeSave()).resolves.toBe('root')
  })

  it('routes a shared node id only to the explicitly active fixed canvas', () => {
    const rootId = canvasIdFromPanelId('workflow:root')
    const nestedId = canvasIdFromPanelId('sub-workflow:nested')
    const updateRoot = vi.fn(() => true)
    const updateNested = vi.fn(() => true)
    const root = useCanvasCommands({
      descriptor: {
        kind: 'root',
        canvasId: rootId,
        workflowId: 'root',
      },
      updateParameter: updateRoot,
    })
    useCanvasCommands({
      descriptor: {
        kind: 'nested',
        canvasId: nestedId,
        sessionId: 'nested',
        parentCanvasId: rootId,
      },
      save: vi.fn(),
      updateParameter: updateNested,
    })
    const active = useCanvasCommands()

    graphSyncCanvasSessions.activate(nestedId)
    expect(active.updateParameter('shared', 'sigma', 2)).toBe(true)
    expect(updateNested).toHaveBeenCalledWith('shared', 'sigma', 2)
    expect(updateRoot).not.toHaveBeenCalled()

    expect(root.updateParameter('shared', 'sigma', 3)).toBe(true)
    expect(updateRoot).toHaveBeenCalledWith('shared', 'sigma', 3)
    expect(updateNested).toHaveBeenCalledOnce()
  })

  it('does not infer a parameter target when sessions exist without an active canvas', () => {
    const rootId = canvasIdFromPanelId('workflow:root')
    const updateParameter = vi.fn(() => true)
    useCanvasCommands({
      descriptor: {
        kind: 'root',
        canvasId: rootId,
        workflowId: 'root',
      },
      updateParameter,
    })

    expect(useCanvasCommands().updateParameter('node', 'sigma', 2)).toBe(false)
    expect(updateParameter).not.toHaveBeenCalled()
  })
})
