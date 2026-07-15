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
    })
    useCanvasCommands({
      descriptor: {
        kind: 'nested',
        canvasId: nestedId,
        sessionId: 'nested',
        parentCanvasId: rootId,
      },
      save: saveNested,
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
    })
    const active = useCanvasCommands()

    await expect(active.routeSave()).resolves.toBe('unavailable')

    graphSyncCanvasSessions.activate(rootId)
    await expect(active.routeSave()).resolves.toBe('root')
  })
})
