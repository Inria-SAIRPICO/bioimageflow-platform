import { describe, expect, it } from 'vitest'

import type { ValidationResult } from '@/api/types'
import { validationAfterCacheClear } from '@/utils/cacheClearValidation'

function corruptValidation(): ValidationResult {
  return {
    valid: false,
    node_statuses: {
      download: {
        node_id: 'download',
        status: 'failed',
        cached: false,
        error: 'Record dataframe logical digest mismatch.',
      },
      analyze: {
        node_id: 'analyze',
        status: 'unexecuted',
        cached: false,
      },
    },
    errors: [
      {
        type: 'cache_corrupt',
        node: 'download',
        detail: 'Record dataframe logical digest mismatch.',
      },
      {
        type: 'parameter_invalid',
        node: 'analyze',
        detail: 'Threshold is invalid.',
      },
    ],
    node_tools: {},
  }
}

describe('validationAfterCacheClear', () => {
  it('removes repaired cache diagnostics and merges refreshed statuses', () => {
    const result = validationAfterCacheClear(
      corruptValidation(),
      ['download'],
      {
        download: {
          node_id: 'download',
          status: 'unexecuted',
          cached: false,
        },
        analyze: {
          node_id: 'analyze',
          status: 'out_of_date',
          cached: false,
        },
      },
    )

    expect(result).toMatchObject({
      valid: false,
      errors: [
        {
          type: 'parameter_invalid',
          node: 'analyze',
          detail: 'Threshold is invalid.',
        },
      ],
      node_statuses: {
        download: { status: 'unexecuted', cached: false },
        analyze: { status: 'out_of_date', cached: false },
      },
    })
  })

  it('clears a nested corruption attributed to a repaired root workflow node', () => {
    const validation = corruptValidation()
    validation.errors = [{
      type: 'cache_corrupt',
      node: 'nested/download',
      detail: 'Record dataframe logical digest mismatch.',
    }]

    const result = validationAfterCacheClear(validation, ['nested'], {
      nested: {
        node_id: 'nested',
        status: 'unexecuted',
        cached: false,
      },
    })

    expect(result.valid).toBe(true)
    expect(result.errors).toEqual([])
  })

  it('retains the corruption when clearing did not repair the selected node', () => {
    const validation = corruptValidation()

    const result = validationAfterCacheClear(validation, ['download'], {
      download: {
        node_id: 'download',
        status: 'failed',
        cached: false,
        error: 'Record dataframe logical digest mismatch.',
      },
    })

    expect(result.valid).toBe(false)
    expect(result.errors[0]).toMatchObject({
      type: 'cache_corrupt',
      node: 'download',
    })
  })
})
