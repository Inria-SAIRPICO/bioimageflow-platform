import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, ref, type EffectScope } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '@/api/client'
import { makeGraph, makeGraphNode, makeValidationResult } from '@/test-utils/graphFixtures'
import { makeOutputPlanningReport } from '@/test-utils/outputPlanningFixtures'
import { deferred } from '@/test-utils/asyncFixtures'
import { canvasIdFromPanelId, canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'
import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'
import { getRootCanvasPersistenceResource } from '@/composables/useCanvasPersistence'
import { useOutputPlanningRecovery } from '../useOutputPlanningRecovery'

const { setTemplates } = vi.hoisted(() => ({ setTemplates: vi.fn() }))
vi.mock('@/api/client', () => ({ api: { get: vi.fn(), post: vi.fn() } }))
vi.mock('@/composables/useCanvasCommands', () => ({ useCanvasCommands: () => ({ setOutputTemplates: setTemplates }) }))
vi.mock('@/composables/useCanvasPersistence', () => ({ getRootCanvasPersistenceResource: vi.fn() }))

const canvasId = canvasIdFromPanelId('workflow:collision')
const context = { execution_id: 'run-collision', workflow_id: 'Demo', draft_revision: 7 }
let scope: EffectScope

function setup() {
  const graph = makeGraph({ nodes: [makeGraphNode({ id: 'atlas', output_templates: { output_image: 'old.tif' } })] })
  const persistence = {
    workflowId: ref('Demo'), acceptedDraftRevision: ref<number | null>(7), currentGraph: ref(graph),
    validationResult: ref(makeValidationResult()),
    ensureFreshForCriticalOperation: vi.fn(async () => true),
    flush: vi.fn(async () => { persistence.acceptedDraftRevision.value = 8 }),
  }
  vi.mocked(getRootCanvasPersistenceResource).mockReturnValue(persistence as never)
  canvasSessionRegistry.register({ kind: 'root', canvasId, workflowId: 'Demo' })
  canvasSessionRegistry.activate(canvasId)
  useUIStore().setCanvasWorkflow(canvasId, 'Demo', 'Demo')
  const exec = useExecutionStore()
  exec.applyStatusSnapshot({
    ...context, state: 'idle', progress: null, node_statuses: {},
    last_result: { success: false, errors: [], node_statuses: {}, output_planning_reports: [makeOutputPlanningReport()] },
  })
  exec.originCanvasId = canvasId
  exec.originGraph = JSON.parse(JSON.stringify(graph))
  exec.requestedNodes = ['atlas']
  setTemplates.mockImplementation((_node: string, templates: Record<string, string>) => {
    persistence.currentGraph.value = {
      ...persistence.currentGraph.value,
      nodes: [makeGraphNode({ id: 'atlas', output_templates: templates })],
    }
    return true
  })
  scope = effectScope()
  const recovery = scope.run(() => useOutputPlanningRecovery())!
  return { persistence, exec, recovery }
}

beforeEach(() => {
  setActivePinia(createPinia())
  canvasSessionRegistry.dispose()
  sessionStorage.clear()
  vi.mocked(api.post).mockReset()
  vi.mocked(getRootCanvasPersistenceResource).mockReset()
  setTemplates.mockReset()
})
afterEach(() => { scope?.stop(); canvasSessionRegistry.dispose() })

describe('output planning recovery', () => {
  it('cancel keeps the draft unchanged and prevents repeated snapshot dialogs', () => {
    const { recovery, persistence, exec } = setup()
    expect(recovery.report.value?.node_id).toBe('atlas')
    recovery.dismiss()
    exec.lastResult = { ...exec.lastResult! }
    expect(recovery.report.value).toBeNull()
    expect(persistence.acceptedDraftRevision.value).toBe(7)
    expect(setTemplates).not.toHaveBeenCalled()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('checks, makes one ordinary edit, persists and restarts the original targets with a new revision', async () => {
    const { recovery, persistence } = setup()
    vi.mocked(api.post).mockResolvedValueOnce({ data: { valid: true, reports: [] } })
      .mockResolvedValueOnce({ data: { status: 'started', execution_id: 'run-corrected', workflow_id: 'Demo', draft_revision: 8 } })
    await recovery.submit({ output_image: 'new_{row_index}.tif' })
    expect(api.post).toHaveBeenNthCalledWith(1, '/api/v1/execution/output-templates/check', {
      ...context, node_id: 'atlas', templates: { output_image: 'new_{row_index}.tif' },
    })
    expect(setTemplates).toHaveBeenCalledExactlyOnceWith('atlas', { output_image: 'new_{row_index}.tif' }, canvasId)
    expect(persistence.flush).toHaveBeenCalledOnce()
    expect(api.post).toHaveBeenNthCalledWith(2, '/api/v1/execution/run', {
      nodes: ['atlas'], workflow_id: 'Demo', draft_revision: 8, mode: 'normal',
    })
    expect(recovery.report.value).toBeNull()
  })

  it('keeps an invalid custom correction in the dialog without editing or starting', async () => {
    const { recovery } = setup()
    const report = makeOutputPlanningReport({ detail: 'The custom filename still collides.' })
    vi.mocked(api.post).mockResolvedValue({ data: { valid: false, reports: [report] } })
    await recovery.submit({ output_image: 'still-shared.tif' })
    expect(recovery.error.value).toContain('custom filename still collides')
    expect(recovery.validationReports.value).toEqual([report])
    expect(setTemplates).not.toHaveBeenCalled()
    expect(api.post).toHaveBeenCalledTimes(1)
  })

  it('rejects duplicate submissions and a canvas replaced during checking', async () => {
    const { recovery } = setup()
    const checking = deferred<{ data: { valid: boolean; reports: [] } }>()
    vi.mocked(api.post).mockReturnValueOnce(checking.promise)
    const first = recovery.submit({ output_image: 'safe.tif' })
    await Promise.resolve()
    await recovery.submit({ output_image: 'duplicate.tif' })
    canvasSessionRegistry.unregister(canvasId)
    canvasSessionRegistry.register({ kind: 'root', canvasId, workflowId: 'Demo' })
    canvasSessionRegistry.activate(canvasId)
    checking.resolve({ data: { valid: true, reports: [] } })
    await first
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(setTemplates).not.toHaveBeenCalled()
  })

  it('keeps the accepted edit and reports a restart failure without repeating submission', async () => {
    const { recovery, persistence } = setup()
    vi.mocked(api.post).mockResolvedValueOnce({ data: { valid: true, reports: [] } })
      .mockRejectedValueOnce(new Error('Backend unavailable'))
    await recovery.submit({ output_image: 'safe_{row_index}.tif' })
    expect(persistence.acceptedDraftRevision.value).toBe(8)
    expect(recovery.error.value).toContain('template change was kept')
    expect(recovery.correctionUnavailableReason.value).toContain('remains in your workflow')
    await recovery.submit({ output_image: 'another.tif' })
    expect(api.post).toHaveBeenCalledTimes(2)
  })

  it('does not restart when draft persistence fails', async () => {
    const { recovery, persistence } = setup()
    vi.mocked(api.post).mockResolvedValueOnce({ data: { valid: true, reports: [] } })
    persistence.flush.mockRejectedValueOnce(new Error('Draft revision conflict'))
    await recovery.submit({ output_image: 'safe.tif' })
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(recovery.error.value).toContain('Draft revision conflict')
    expect(persistence.acceptedDraftRevision.value).toBe(7)
  })
})
