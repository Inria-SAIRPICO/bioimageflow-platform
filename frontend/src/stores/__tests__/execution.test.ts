import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

import { useExecutionStore } from '../execution'
import { useLoggerStore } from '../logger'
import { useErrorStore } from '../errors'

describe('execution store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('mirrors execution failures into the logger and preserves full error details', () => {
    const execution = useExecutionStore()
    const logger = useLoggerStore()
    const errors = useErrorStore()

    execution.state = 'running'
    execution.applyExecutionComplete({
      success: false,
      errors: [{ type: 'RuntimeError', detail: 'top-level failure' }],
      node_statuses: {
        node_a: {
          node_id: 'node_a',
          status: 'failed',
          cached: false,
          error: 'segmentation failed',
          traceback: 'Traceback...\nValueError: bad image',
        },
      },
    })

    expect(logger.entries).toEqual([
      expect.objectContaining({
        level: 'ERROR',
        nodeId: 'node_a',
        message: expect.stringContaining('segmentation failed'),
      }),
    ])
    expect(errors.errors[0]).toMatchObject({
      kind: 'execution_failed',
      detail: 'node_a: segmentation failed',
      nodeId: 'node_a',
      fullDetail: expect.stringContaining('ValueError: bad image'),
    })
  })
})
