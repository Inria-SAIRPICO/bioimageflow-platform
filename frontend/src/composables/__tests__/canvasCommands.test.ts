import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  _resetCanvasCommandsForTest,
  useCanvasCommands,
} from '../useCanvasCommands'
import { canvasIdFromPanelId } from '@/sessions/canvasSessionRegistry'
import { graphSyncCanvasSessions } from '../useGraphSync'

function makeCanvasCommandHandlers() {
  return {
    renameNode: vi.fn(() => true),
    setNodeEnabled: vi.fn(() => true),
    setInputPinned: vi.fn(() => true),
    setOutputTemplate: vi.fn(() => true),
    togglePublishedInput: vi.fn(() => ({ status: 'changed' as const })),
    togglePublishedOutput: vi.fn(() => ({ status: 'changed' as const })),
    renamePublishedInput: vi.fn(() => ({ status: 'changed' as const })),
    renamePublishedOutput: vi.fn(() => ({ status: 'changed' as const })),
  }
}

type CanvasCommands = ReturnType<typeof useCanvasCommands>
type CommandHandlers = ReturnType<typeof makeCanvasCommandHandlers>

const nodeEditCases: Array<{
  name: string
  invoke: (commands: CanvasCommands) => boolean
  spy: (handlers: CommandHandlers) => ReturnType<typeof vi.fn>
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

const publicationCases: Array<{
  name: string
  invoke: (commands: CanvasCommands) => unknown
  spy: (handlers: CommandHandlers) => ReturnType<typeof vi.fn>
  expectedArgs: unknown[]
}> = [
  {
    name: 'input publication toggle',
    invoke: commands => commands.togglePublishedInput('shared', 'image'),
    spy: handlers => handlers.togglePublishedInput,
    expectedArgs: ['shared', 'image'],
  },
  {
    name: 'output publication toggle',
    invoke: commands => commands.togglePublishedOutput('shared', 'result'),
    spy: handlers => handlers.togglePublishedOutput,
    expectedArgs: ['shared', 'result'],
  },
  {
    name: 'published input rename',
    invoke: commands => commands.renamePublishedInput('shared', 'image', 'source'),
    spy: handlers => handlers.renamePublishedInput,
    expectedArgs: ['shared', 'image', 'source'],
  },
  {
    name: 'published output rename',
    invoke: commands => commands.renamePublishedOutput('shared', 'result', 'mask'),
    spy: handlers => handlers.renamePublishedOutput,
    expectedArgs: ['shared', 'result', 'mask'],
  },
]

afterEach(() => {
  _resetCanvasCommandsForTest()
})

describe('active canvas commands', () => {
  it('routes tool creation with parameter overrides to the active canvas', () => {
    const rootId = canvasIdFromPanelId('workflow:root')
    const addToolNode = vi.fn(() => 'files_1')
    useCanvasCommands({
      descriptor: { kind: 'root', canvasId: rootId, workflowId: 'root' },
      addToolNode,
      ...makeCanvasCommandHandlers(),
      updateParameter: vi.fn(),
    })
    const active = useCanvasCommands()
    graphSyncCanvasSessions.activate(rootId)

    expect(active.addToolNode('Files', { files: ['/data/a.tif'] })).toBe('files_1')
    expect(addToolNode).toHaveBeenCalledWith('Files', { files: ['/data/a.tif'] })
  })

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
      ...makeCanvasCommandHandlers(),
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
      ...makeCanvasCommandHandlers(),
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
      ...makeCanvasCommandHandlers(),
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
      ...makeCanvasCommandHandlers(),
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
      ...makeCanvasCommandHandlers(),
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
      const rootHandlers = makeCanvasCommandHandlers()
      const nestedHandlers = makeCanvasCommandHandlers()
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

  it.each(publicationCases)(
    'routes $name only to the explicitly active canvas with shared node ids',
    ({ invoke, spy, expectedArgs }) => {
      const rootId = canvasIdFromPanelId('workflow:root')
      const nestedId = canvasIdFromPanelId('sub-workflow:nested')
      const rootHandlers = makeCanvasCommandHandlers()
      const nestedHandlers = makeCanvasCommandHandlers()
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
      expect(invoke(useCanvasCommands())).toEqual({ status: 'changed' })
      expect(spy(nestedHandlers)).toHaveBeenCalledWith(...expectedArgs)
      expect(spy(rootHandlers)).not.toHaveBeenCalled()

      expect(invoke(root)).toEqual({ status: 'changed' })
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
      ...makeCanvasCommandHandlers(),
      updateParameter,
    })

    expect(useCanvasCommands().updateParameter('node', 'sigma', 2)).toBe(false)
    expect(updateParameter).not.toHaveBeenCalled()
  })

  it.each(nodeEditCases)(
    'does not infer a $name target when sessions exist without an active canvas',
    ({ invoke, spy }) => {
      const rootId = canvasIdFromPanelId('workflow:root')
      const handlers = makeCanvasCommandHandlers()
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

  it.each(publicationCases)(
    'rejects $name when sessions exist without an active canvas',
    ({ invoke, spy }) => {
      const rootId = canvasIdFromPanelId('workflow:root')
      const handlers = makeCanvasCommandHandlers()
      useCanvasCommands({
        descriptor: {
          kind: 'root',
          canvasId: rootId,
          workflowId: 'root',
        },
        ...handlers,
        updateParameter: vi.fn(() => true),
      })

      expect(invoke(useCanvasCommands())).toEqual({
        status: 'rejected',
        reason: 'unavailable',
      })
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
      ...makeCanvasCommandHandlers(),
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
      const handlers = makeCanvasCommandHandlers()
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

  it.each(publicationCases)(
    'rejects late $name calls through a disposed fixed-canvas resource',
    ({ invoke, spy }) => {
      const rootId = canvasIdFromPanelId('workflow:root')
      const handlers = makeCanvasCommandHandlers()
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
