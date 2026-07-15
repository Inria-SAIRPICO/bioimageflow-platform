import { describe, it, expect, beforeEach, vi } from 'vitest'
import { nextTick, ref } from 'vue'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn() },
}))

import { useExecutionLock } from '@/composables/useExecutionLock'
import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'
import type { ValidationResult } from '@/api/types'

describe('useExecutionLock', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('isLocked is false initially', () => {
    const { isLocked } = useExecutionLock()
    expect(isLocked.value).toBe(false)
  })

  it('isLocked becomes true when executionStore.isRunning becomes true', async () => {
    const { isLocked } = useExecutionLock()
    const exec = useExecutionStore()
    const ui = useUIStore()

    exec.state = 'running'
    await nextTick()
    expect(ui.isExecutionLocked).toBe(true)
    expect(isLocked.value).toBe(true)
  })

  it('isLocked becomes false when executionStore.isRunning becomes false', async () => {
    const { isLocked } = useExecutionLock()
    const exec = useExecutionStore()

    exec.state = 'running'
    await nextTick()
    expect(isLocked.value).toBe(true)

    exec.state = 'idle'
    await nextTick()
    expect(isLocked.value).toBe(false)
  })

  it.each(['starting', 'stopping'] as const)(
    'shares the global mutation lock across consumers while execution is %s',
    (phase) => {
      const firstCanvas = useExecutionLock()
      const secondCanvas = useExecutionLock()
      const exec = useExecutionStore()
      const ui = useUIStore()

      exec.state = phase as any

      expect(exec.isMutationLocked).toBe(true)
      expect(ui.isExecutionLocked).toBe(true)
      expect(firstCanvas.isLocked.value).toBe(true)
      expect(secondCanvas.isLocked.value).toBe(true)
    },
  )

  it('lockForExecution flushes graph sync, then calls run when valid', async () => {
    const { lockForExecution } = useExecutionLock()
    const exec = useExecutionStore()

    const flushNow = vi.fn(async () => {})
    const validationResult = ref<ValidationResult | null>({
      valid: true,
      node_statuses: {},
      errors: [],
    })
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()

    const graph = { nodes: [], edges: [] }
    await lockForExecution({
      graph,
      graphSync: { flushNow, validationResult },
      workflowName: 'wf_a',
    })

    expect(flushNow).toHaveBeenCalled()
    expect(runSpy).toHaveBeenCalledWith(graph, undefined, 'wf_a')
  })

  it('lockForExecution aborts if its canvas target changes while graph sync flushes', async () => {
    const { lockForExecution } = useExecutionLock()
    const exec = useExecutionStore()
    let resolveFlush!: () => void
    const flushNow = vi.fn(() => new Promise<void>((resolve) => {
      resolveFlush = resolve
    }))
    const validationResult = ref<ValidationResult | null>({
      valid: true,
      node_statuses: {},
      errors: [],
    })
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()
    let targetActive = true

    const result = lockForExecution({
      graph: { nodes: [], edges: [] },
      graphSync: { flushNow, validationResult },
      workflowName: 'wf_a',
      isTargetActive: () => targetActive,
    })
    targetActive = false
    resolveFlush()

    await expect(result).resolves.toBe(false)
    expect(runSpy).not.toHaveBeenCalled()
  })

  it('lockForExecution aborts if validation fails after flush', async () => {
    const { lockForExecution } = useExecutionLock()
    const exec = useExecutionStore()

    const flushNow = vi.fn(async () => {})
    const validationResult = ref<ValidationResult | null>({
      valid: false,
      node_statuses: {},
      errors: [
        {
          type: 'cycle_detected',
          detail: 'cycle',
          node: null,
          edge_id: null,
          field: null,
        },
      ],
    })
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()

    await expect(
      lockForExecution({
        graph: { nodes: [], edges: [] },
        graphSync: { flushNow, validationResult },
        workflowName: 'wf_a',
      }),
    ).rejects.toThrow(/validation/i)

    expect(flushNow).toHaveBeenCalled()
    expect(runSpy).not.toHaveBeenCalled()
  })

  it('lockForExecution passes nodes subset to run', async () => {
    const { lockForExecution } = useExecutionLock()
    const exec = useExecutionStore()

    const flushNow = vi.fn(async () => {})
    const validationResult = ref<ValidationResult | null>({
      valid: true,
      node_statuses: {},
      errors: [],
    })
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()

    const graph = { nodes: [], edges: [] }
    await lockForExecution({
      graph,
      nodes: ['n1', 'n2'],
      graphSync: { flushNow, validationResult },
      workflowName: 'wf_a',
    })

    expect(runSpy).toHaveBeenCalledWith(graph, ['n1', 'n2'], 'wf_a')
  })

  it('lockForExecution ignores validation errors outside the selected execution set', async () => {
    const { lockForExecution } = useExecutionLock()
    const exec = useExecutionStore()

    const flushNow = vi.fn(async () => {})
    const validationResult = ref<ValidationResult | null>({
      valid: false,
      node_statuses: {},
      errors: [
        {
          type: 'missing_connection',
          detail: 'downstream is not executable',
          node: 'downstream',
          edge_id: null,
          field: 'input_image',
        },
      ],
    })
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()
    const graph = {
      nodes: [
        { id: 'source' },
        { id: 'selected' },
        { id: 'downstream' },
      ],
      edges: [
        { id: 'e1', source_node: 'source', target_node: 'selected' },
        { id: 'e2', source_node: 'selected', target_node: 'downstream' },
      ],
    }

    await lockForExecution({
      graph: graph as never,
      nodes: ['selected'],
      graphSync: { flushNow, validationResult },
      workflowName: 'wf_a',
    })

    expect(runSpy).toHaveBeenCalledWith(graph, ['selected'], 'wf_a')
  })

  it('unlockAfterExecution triggers a graph re-validation via PUT /graph', async () => {
    const { unlockAfterExecution } = useExecutionLock()

    const { api } = await import('@/api/client')
    const mockedApi = api as unknown as { put: ReturnType<typeof vi.fn> }
    mockedApi.put.mockResolvedValueOnce({ data: { valid: true } })

    await unlockAfterExecution({ nodes: [], edges: [] })

    expect(mockedApi.put).toHaveBeenCalledWith('/api/v1/graph', {
      graph: { nodes: [], edges: [] },
      workflow_name: null,
    })
  })
})
