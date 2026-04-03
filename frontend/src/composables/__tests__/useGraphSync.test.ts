import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { GraphState, ValidationResult } from '@/api/types'

vi.mock('@/api/client', () => ({
  api: {
    put: vi.fn(),
    patch: vi.fn(),
  },
}))

import { api } from '@/api/client'
import { useGraphSync } from '../useGraphSync'

const mockedPut = vi.mocked(api.put)
const mockedPatch = vi.mocked(api.patch)

const makeGraph = (id = '1'): GraphState => ({
  nodes: [{ id, name: 'n', tool_name: 't', position: [0, 0], parameters: {} }],
  edges: [],
})

const makeValidation = (valid = true): ValidationResult => ({
  valid,
  node_statuses: {},
  errors: [],
})

describe('useGraphSync', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockedPut.mockReset()
    mockedPatch.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('debounces multiple rapid syncGraph calls into one PUT', async () => {
    mockedPut.mockResolvedValue({ data: makeValidation() })
    const { syncGraph } = useGraphSync()

    syncGraph(makeGraph('1'))
    syncGraph(makeGraph('2'))
    syncGraph(makeGraph('3'))

    expect(mockedPut).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(300)

    expect(mockedPut).toHaveBeenCalledTimes(1)
    // Should use the last graph passed
    expect(mockedPut).toHaveBeenCalledWith('/api/v1/graph', makeGraph('3'))
  })

  it('supersedes in-flight requests', async () => {
    let resolveFirst!: (v: unknown) => void
    let resolveSecond!: (v: unknown) => void

    mockedPut
      .mockReturnValueOnce(new Promise(r => { resolveFirst = r }))
      .mockReturnValueOnce(new Promise(r => { resolveSecond = r }))

    const { syncGraph, validationResult } = useGraphSync()

    // First call
    syncGraph(makeGraph('1'))
    await vi.advanceTimersByTimeAsync(300)
    expect(mockedPut).toHaveBeenCalledTimes(1)

    // Second call while first is in-flight
    syncGraph(makeGraph('2'))
    await vi.advanceTimersByTimeAsync(300)
    expect(mockedPut).toHaveBeenCalledTimes(2)

    // Resolve first request (stale)
    resolveFirst({ data: makeValidation(false) })
    await vi.advanceTimersByTimeAsync(0)
    // Stale result should be ignored
    expect(validationResult.value).toBeNull()

    // Resolve second request (current)
    resolveSecond({ data: makeValidation(true) })
    await vi.advanceTimersByTimeAsync(0)
    expect(validationResult.value).toEqual(makeValidation(true))
  })

  it('returns validation result', async () => {
    mockedPut.mockResolvedValue({ data: makeValidation(true) })
    const { syncGraph, validationResult } = useGraphSync()

    syncGraph(makeGraph())
    await vi.advanceTimersByTimeAsync(300)

    expect(validationResult.value).toEqual(makeValidation(true))
  })

  it('flushNow sends immediately', async () => {
    mockedPut.mockResolvedValue({ data: makeValidation() })
    const { syncGraph, flushNow } = useGraphSync()

    syncGraph(makeGraph())
    expect(mockedPut).not.toHaveBeenCalled()

    await flushNow()
    expect(mockedPut).toHaveBeenCalledTimes(1)
  })

  it('isPending is true while request is in-flight', async () => {
    let resolve!: (v: unknown) => void
    mockedPut.mockReturnValue(new Promise(r => { resolve = r }))

    const { syncGraph, isPending, flushNow } = useGraphSync()

    expect(isPending.value).toBe(false)

    syncGraph(makeGraph())
    flushNow() // fire immediately, don't await

    await vi.advanceTimersByTimeAsync(0)
    expect(isPending.value).toBe(true)

    resolve({ data: makeValidation() })
    await vi.advanceTimersByTimeAsync(0)
    expect(isPending.value).toBe(false)
  })

  it('patchParameters uses PATCH endpoint', async () => {
    mockedPatch.mockResolvedValue({ data: {} })
    const { patchParameters } = useGraphSync()

    await patchParameters('node_1', { threshold: 0.5 })

    expect(mockedPatch).toHaveBeenCalledWith(
      '/api/v1/graph/nodes/node_1/parameters',
      { threshold: 0.5 },
    )
  })
})
