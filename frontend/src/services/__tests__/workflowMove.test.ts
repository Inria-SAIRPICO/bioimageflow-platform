import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { canvasIdFromPanelId, canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'
import { useUIStore } from '@/stores/ui'
import { useCanvasLifecycleStore } from '@/stores/canvasLifecycle'
import { useNestedWorkflowSessionsStore } from '@/stores/nestedWorkflowSessions'
import { withWorkflowMove } from '../workflowMove'

const mocks = vi.hoisted(() => ({ fresh: vi.fn(), flushNested: vi.fn() }))
vi.mock('@/composables/useCanvasPersistence', () => ({ getRootCanvasPersistenceResource: () => ({ ensureFreshForCriticalOperation: mocks.fresh }) }))
vi.mock('@/composables/useGraphSync', () => ({ flushRetainedNestedSnapshot: mocks.flushNested }))

const workflowId = '767935bb-8dd2-4e0e-a4ab-878e7c3c64bf'
const root = canvasIdFromPanelId(`workflow:${workflowId}`)
const child = canvasIdFromPanelId('nested-workflow:child')

describe('workflow move editing barrier', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    mocks.fresh.mockReset().mockResolvedValue(true)
    mocks.flushNested.mockReset().mockResolvedValue(undefined)
    canvasSessionRegistry.register({ kind: 'root', canvasId: root, workflowId })
    canvasSessionRegistry.register({ kind: 'nested', canvasId: child, sessionId: 'child', parentCanvasId: root })
    useUIStore().setCanvasWorkflow(root, workflowId, 'Workflow')
    useUIStore().markCanvasDirty(root)
    useNestedWorkflowSessionsStore().sessions = [{ id: 'child', parentWorkflowName: workflowId }] as any
  })

  it('locks affected editors and flushes private state without replacing their registrations or dirty state', async () => {
    const rootToken = canvasSessionRegistry.get(root)!.registrationToken
    const childToken = canvasSessionRegistry.get(child)!.registrationToken
    const move = vi.fn(async () => {
      expect(mocks.fresh).toHaveBeenCalledOnce()
      expect(mocks.flushNested).toHaveBeenCalledWith('child')
      expect(useCanvasLifecycleStore().operationFor(root)).toBe('moving')
      expect(useCanvasLifecycleStore().operationFor(child)).toBe('moving')
      return 'moved'
    })
    await expect(withWorkflowMove([workflowId], move)).resolves.toBe('moved')
    expect(canvasSessionRegistry.get(root)!.registrationToken).toBe(rootToken)
    expect(canvasSessionRegistry.get(child)!.registrationToken).toBe(childToken)
    expect(useUIStore().canvasHasUnsavedChanges(root)).toBe(true)
    expect(useCanvasLifecycleStore().isBusy(root)).toBe(false)
    expect(useCanvasLifecycleStore().isBusy(child)).toBe(false)
  })

  it('does not move while a root draft has an unresolved conflict', async () => {
    mocks.fresh.mockResolvedValueOnce(false)
    const move = vi.fn()
    await expect(withWorkflowMove([workflowId], move)).rejects.toThrow('Resolve the workflow draft conflict')
    expect(move).not.toHaveBeenCalled()
    expect(mocks.flushNested).not.toHaveBeenCalled()
    expect(useCanvasLifecycleStore().isBusy(root)).toBe(false)
  })

  it('refuses a replaced canvas after persistence and releases the owned lifecycle gates', async () => {
    mocks.flushNested.mockImplementationOnce(async () => {
      canvasSessionRegistry.unregister(root)
      canvasSessionRegistry.register({ kind: 'root', canvasId: root, workflowId })
    })
    const move = vi.fn()
    await expect(withWorkflowMove([workflowId], move)).rejects.toThrow('canvas changed')
    expect(move).not.toHaveBeenCalled()
    expect(useCanvasLifecycleStore().isBusy(root)).toBe(false)
  })
})
