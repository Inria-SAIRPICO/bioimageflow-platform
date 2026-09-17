import { describe, expect, it } from 'vitest'
import { apiErrorMessage, apiGraphValidationErrors } from '../apiError'

describe('apiErrorMessage', () => {
  it('prefers a server detail over the generic HTTP client message', () => {
    const error = Object.assign(new Error('Request failed with status code 422'), {
      response: {
        status: 422,
        data: { detail: "Workflow output 'result' references unknown node 'increment'" },
      },
    })

    expect(apiErrorMessage(error)).toBe(
      "Workflow output 'result' references unknown node 'increment'",
    )
  })

  it('renders structured validation issues with copyable field locations', () => {
    const error = Object.assign(new Error('Request failed with status code 422'), {
      response: {
        status: 422,
        data: {
          detail: [
            {
              type: 'value_error',
              loc: ['body', 'graph', 'interface', 'outputs', 0, 'source', 'node'],
              msg: 'Value error, referenced node does not exist',
            },
            {
              type: 'missing',
              loc: ['body', 'expected_revision'],
              msg: 'Field required',
            },
          ],
        },
      },
    })

    expect(apiErrorMessage(error)).toBe([
      'graph.interface.outputs[0].source.node: referenced node does not exist',
      'expected_revision: Field required',
    ].join('\n'))
  })

  it('falls back to ordinary errors and strings', () => {
    expect(apiErrorMessage(new Error('Local failure'))).toBe('Local failure')
    expect(apiErrorMessage('Plain failure')).toBe('Plain failure')
  })
})

describe('apiGraphValidationErrors', () => {
  it('retains node-scoped errors from a failed cache clear', () => {
    const errors = [
      { type: 'parameter_invalid', node: 'extract_ch2_nuclei', field: 'input_image', detail: 'Unknown input' },
      { type: 'missing_connection', node: 'cellpose3_nuclei', detail: 'Missing upstream input' },
    ]
    const failure = { response: { data: { detail: 'Failed to build workflow: 2 error(s)', errors } } }

    expect(apiGraphValidationErrors(failure)).toEqual(errors)
    expect(apiGraphValidationErrors(new Error('Network failure'))).toEqual([])
  })
})
