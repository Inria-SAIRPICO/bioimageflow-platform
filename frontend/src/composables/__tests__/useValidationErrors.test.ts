import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { useValidationErrors } from '../useValidationErrors'
import type { GraphValidationError, ValidationResult } from '@/api/types'

const makeResult = (
  valid: boolean,
  errors: GraphValidationError[] = [],
): ValidationResult => ({
  valid,
  node_statuses: {},
  errors,
})

describe('useValidationErrors', () => {
  it('handles null validation result', () => {
    const r = ref<ValidationResult | null>(null)
    const { nodeErrors, hasErrors, globalErrors, edgeErrors } =
      useValidationErrors(r)
    expect(nodeErrors.value).toEqual({})
    expect(edgeErrors.value).toEqual({})
    expect(globalErrors.value).toEqual([])
    expect(hasErrors.value).toBe(false)
  })

  it('hasErrors is false when valid=true', () => {
    const r = ref<ValidationResult | null>(makeResult(true))
    const { hasErrors } = useValidationErrors(r)
    expect(hasErrors.value).toBe(false)
  })

  it('hasErrors is true when valid=false', () => {
    const r = ref<ValidationResult | null>(makeResult(false))
    const { hasErrors } = useValidationErrors(r)
    expect(hasErrors.value).toBe(true)
  })

  it('groups parameter_invalid errors under the correct node', () => {
    const err: GraphValidationError = {
      type: 'parameter_invalid',
      detail: 'bad value',
      node: 'n1',
      field: 'threshold',
    }
    const r = ref<ValidationResult | null>(makeResult(false, [err]))
    const { nodeErrors } = useValidationErrors(r)
    expect(nodeErrors.value['n1']).toEqual([err])
  })

  it('getFieldErrors filters by node and field', () => {
    const err: GraphValidationError = {
      type: 'parameter_invalid',
      detail: 'bad',
      node: 'n1',
      field: 'x',
    }
    const r = ref<ValidationResult | null>(makeResult(false, [err]))
    const { getFieldErrors } = useValidationErrors(r)
    expect(getFieldErrors('n1', 'x')).toEqual([err])
    expect(getFieldErrors('n1', 'other')).toEqual([])
    expect(getFieldErrors('other', 'x')).toEqual([])
  })

  it('routes type_incompatible (edge_id) into edgeErrors, not nodeErrors', () => {
    const err: GraphValidationError = {
      type: 'type_incompatible',
      detail: 'bad types',
      edge_id: 'e1',
    }
    const r = ref<ValidationResult | null>(makeResult(false, [err]))
    const { edgeErrors, nodeErrors, globalErrors, getEdgeErrors } =
      useValidationErrors(r)
    expect(edgeErrors.value['e1']).toEqual([err])
    expect(nodeErrors.value).toEqual({})
    expect(globalErrors.value).toEqual([])
    expect(getEdgeErrors('e1')).toEqual([err])
  })

  it('routes cycle_detected to globalErrors regardless of node field', () => {
    const err: GraphValidationError = {
      type: 'cycle_detected',
      detail: 'Cycle: a -> b -> a',
      node: 'a',
    }
    const r = ref<ValidationResult | null>(makeResult(false, [err]))
    const { globalErrors, nodeErrors } = useValidationErrors(r)
    expect(globalErrors.value).toEqual([err])
    expect(nodeErrors.value).toEqual({})
  })

  it('routes error with neither node nor edge_id to globalErrors', () => {
    const err: GraphValidationError = {
      type: 'missing_tool',
      detail: 'something wrong',
    }
    const r = ref<ValidationResult | null>(makeResult(false, [err]))
    const { globalErrors } = useValidationErrors(r)
    expect(globalErrors.value).toEqual([err])
  })

  it('collects multiple errors for the same node', () => {
    const e1: GraphValidationError = {
      type: 'parameter_invalid',
      detail: 'a',
      node: 'n1',
      field: 'x',
    }
    const e2: GraphValidationError = {
      type: 'missing_connection',
      detail: 'b',
      node: 'n1',
      field: 'y',
    }
    const r = ref<ValidationResult | null>(makeResult(false, [e1, e2]))
    const { nodeErrors } = useValidationErrors(r)
    expect(nodeErrors.value['n1']).toEqual([e1, e2])
  })

  it('routes source_tool_upstream with edge_id to edgeErrors', () => {
    const err: GraphValidationError = {
      type: 'source_tool_upstream',
      detail: 'This tool is a source and does not accept DataFrame inputs.',
      edge_id: 'e_pos_1',
      node: 'files_1',
    }
    const r = ref<ValidationResult | null>(makeResult(false, [err]))
    const { edgeErrors, nodeErrors, getEdgeErrors } = useValidationErrors(r)
    expect(edgeErrors.value['e_pos_1']).toEqual([err])
    expect(nodeErrors.value).toEqual({})
    expect(getEdgeErrors('e_pos_1')).toEqual([err])
  })
})
