import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  _resetCanvasCommandsForTest,
  useCanvasCommands,
} from '../useCanvasCommands'
import { canvasIdFromPanelId } from '@/sessions/canvasSessionRegistry'
import { graphSyncCanvasSessions } from '../useGraphSync'

function makeNodeEditHandlers() {
  return {
    renameNode: vi.fn(() => true),
    setNodeEnabled: vi.fn(() => true),
    setInputPinned: vi.fn(() => true),
    setOutputTemplate: vi.fn(() => true),
  }
}

type CanvasCommands = ReturnType<typeof useCanvasCommands>
type NodeEditHandlers = ReturnType<typeof makeNodeEditHandlers>

const nodeEditCases: Array<{
  name: string
  invoke: (commands: CanvasCommands) => boolean
  spy: (handlers: NodeEditHandlers) => ReturnType<typeof vi.fn>
  expectedArgs: unknown[]
}> = [
  {
    name: 'node rename',
    invoke: commands => commands.renameNode('shared', 'Renamed'),
    spy: handlers => handlers.renameNode,
    expectedArgs: ['shared', 'Renamed'],
  },
  {
    name: 'enabled state',
    invoke: commands => commands.setNodeEnabled('shared', false),
    spy: handlers => handlers.setNodeEnabled,
    expectedArgs: ['shared', false],
  },
  {
    name: 'input-pin visibility',
    invoke: commands => commands.setInputPinned('shared', 'image', false),
    spy: handlers => handlers.setInputPinned,
    expectedArgs: ['shared', 'image', false],
  },
  {
    name: 'output template',
    invoke: commands => commands.setOutputTemplate('shared', 'result', '/tmp/out.tif'),
    spy: handlers => handlers.setOutputTemplate,
    expectedArgs: ['shared', 'result', '/tmp/out.tif'],
  },
]

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
      ...makeNodeEditHandlers(),
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
      ...makeNodeEditHandlers(),
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
      ...makeNodeEditHandlers(),
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
      ...makeNodeEditHandlers(),
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
      ...makeNodeEditHandlers(),
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

  it.each(nodeEditCases)(
    'routes $name only to the explicitly active canvas with shared node ids',
    ({ invoke, spy, expectedArgs }) => {
      const rootId = canvasIdFromPanelId('workflow:root')
      const nestedId = canvasIdFromPanelId('sub-workflow:nested')
      const rootHandlers = makeNodeEditHandlers()
      const nestedHandlers = makeNodeEditHandlers()
      const root = useCanvasCommands({
        descriptor: {
          kind: 'root',
          canvasId: rootId,
          workflowId: 'root',
        },
        ...rootHandlers,
        updateParameter: vi.fn(() => true),
      })
      useCanvasCommands({
        descriptor: {
          kind: 'nested',
          canvasId: nestedId,
          sessionId: 'nested',
          parentCanvasId: rootId,
        },
        save: vi.fn(),
        ...nestedHandlers,
        updateParameter: vi.fn(() => true),
      })

      graphSyncCanvasSessions.activate(nestedId)
      expect(invoke(useCanvasCommands())).toBe(true)
      expect(spy(nestedHandlers)).toHaveBeenCalledWith(...expectedArgs)
      expect(spy(rootHandlers)).not.toHaveBeenCalled()

      expect(invoke(root)).toBe(true)
      expect(spy(rootHandlers)).toHaveBeenCalledWith(...expectedArgs)
      expect(spy(nestedHandlers)).toHaveBeenCalledOnce()
    },
  )

  it('does not infer a parameter target when sessions exist without an active canvas', () => {
    const rootId = canvasIdFromPanelId('workflow:root')
    const updateParameter = vi.fn(() => true)
    useCanvasCommands({
      descriptor: {
        kind: 'root',
        canvasId: rootId,
        workflowId: 'root',
      },
      ...makeNodeEditHandlers(),
      updateParameter,
    })

    expect(useCanvasCommands().updateParameter('node', 'sigma', 2)).toBe(false)
    expect(updateParameter).not.toHaveBeenCalled()
  })

  it.each(nodeEditCases)(
    'does not infer a $name target when sessions exist without an active canvas',
    ({ invoke, spy }) => {
      const rootId = canvasIdFromPanelId('workflow:root')
      const handlers = makeNodeEditHandlers()
      useCanvasCommands({
        descriptor: {
          kind: 'root',
          canvasId: rootId,
          workflowId: 'root',
        },
        ...handlers,
        updateParameter: vi.fn(() => true),
      })

      expect(invoke(useCanvasCommands())).toBe(false)
      expect(spy(handlers)).not.toHaveBeenCalled()
    },
  )

  it('rejects late calls through a disposed fixed-canvas resource', () => {
    const rootId = canvasIdFromPanelId('workflow:root')
    const updateParameter = vi.fn(() => true)
    const fixed = useCanvasCommands({
      descriptor: {
        kind: 'root',
        canvasId: rootId,
        workflowId: 'root',
      },
      ...makeNodeEditHandlers(),
      updateParameter,
    })

    fixed.dispose()

    expect(() => fixed.updateParameter('node', 'sigma', 2)).toThrow(
      'Canvas commands have been disposed',
    )
    expect(updateParameter).not.toHaveBeenCalled()
  })

  it.each(nodeEditCases)(
    'rejects late $name calls through a disposed fixed-canvas resource',
    ({ invoke, spy }) => {
      const rootId = canvasIdFromPanelId('workflow:root')
      const handlers = makeNodeEditHandlers()
      const fixed = useCanvasCommands({
        descriptor: {
          kind: 'root',
          canvasId: rootId,
          workflowId: 'root',
        },
        ...handlers,
        updateParameter: vi.fn(() => true),
      })

      fixed.dispose()

      expect(() => invoke(fixed)).toThrow('Canvas commands have been disposed')
      expect(spy(handlers)).not.toHaveBeenCalled()
    },
  )
})
