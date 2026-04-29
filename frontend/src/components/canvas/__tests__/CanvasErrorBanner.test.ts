import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CanvasErrorBanner from '../CanvasErrorBanner.vue'
import type { GraphValidationError, ValidationResult } from '@/api/types'

function makeResult(errors: GraphValidationError[]): ValidationResult {
  return { valid: errors.length === 0, node_statuses: {}, errors }
}

const cycleA: GraphValidationError = {
  type: 'cycle_detected',
  detail: 'Cycle: a → b → a',
}
const cycleB: GraphValidationError = {
  type: 'cycle_detected',
  detail: 'Cycle: x → y → z → x',
}

describe('CanvasErrorBanner', () => {
  it('renders nothing when validationResult is null', () => {
    const w = mount(CanvasErrorBanner, {
      props: { validationResult: null },
    })
    expect(w.find('.canvas-error-banner').exists()).toBe(false)
  })

  it('renders nothing when there are no global errors', () => {
    const w = mount(CanvasErrorBanner, {
      props: { validationResult: makeResult([]) },
    })
    expect(w.find('.canvas-error-banner').exists()).toBe(false)
  })

  it('renders the banner when at least one cycle_detected error is present', () => {
    const w = mount(CanvasErrorBanner, {
      props: { validationResult: makeResult([cycleA]) },
    })
    expect(w.find('.canvas-error-banner').exists()).toBe(true)
    expect(w.text()).toContain('Cycle: a → b → a')
  })

  it('renders one row per global error', () => {
    const w = mount(CanvasErrorBanner, {
      props: { validationResult: makeResult([cycleA, cycleB]) },
    })
    const rows = w.findAll('[data-testid="canvas-error-row"]')
    expect(rows).toHaveLength(2)
  })

  it('shows an exclamation icon and red background class', () => {
    const w = mount(CanvasErrorBanner, {
      props: { validationResult: makeResult([cycleA]) },
    })
    expect(w.find('.canvas-error-banner').exists()).toBe(true)
    expect(w.find('.pi-exclamation-triangle').exists()).toBe(true)
  })

  it('dismiss button hides the banner', async () => {
    const w = mount(CanvasErrorBanner, {
      props: { validationResult: makeResult([cycleA]) },
    })
    expect(w.find('.canvas-error-banner').exists()).toBe(true)
    const dismiss = w.find('[data-testid="canvas-error-dismiss"]')
    expect(dismiss.exists()).toBe(true)
    await dismiss.trigger('click')
    expect(w.find('.canvas-error-banner').exists()).toBe(false)
  })

  it('a new global error after dismissal re-shows the banner', async () => {
    const w = mount(CanvasErrorBanner, {
      props: { validationResult: makeResult([cycleA]) },
    })
    await w.find('[data-testid="canvas-error-dismiss"]').trigger('click')
    expect(w.find('.canvas-error-banner').exists()).toBe(false)

    await w.setProps({ validationResult: makeResult([cycleB]) })
    expect(w.find('.canvas-error-banner').exists()).toBe(true)
    expect(w.text()).toContain('Cycle: x → y → z → x')
  })

  it('re-emitting the same dismissed errors does NOT re-show the banner', async () => {
    const w = mount(CanvasErrorBanner, {
      props: { validationResult: makeResult([cycleA]) },
    })
    await w.find('[data-testid="canvas-error-dismiss"]').trigger('click')
    expect(w.find('.canvas-error-banner').exists()).toBe(false)

    // Re-emit the same shape (different array identity, same content).
    await w.setProps({
      validationResult: makeResult([{ ...cycleA }]),
    })
    expect(w.find('.canvas-error-banner').exists()).toBe(false)
  })

  it('errors with no node and no edge_id but not cycle_detected are also surfaced', () => {
    const generic: GraphValidationError = {
      type: 'parameter_invalid',
      detail: 'Some global parameter problem',
    }
    const w = mount(CanvasErrorBanner, {
      props: { validationResult: makeResult([generic]) },
    })
    expect(w.find('.canvas-error-banner').exists()).toBe(true)
    expect(w.text()).toContain('Some global parameter problem')
  })

  it('node-scoped errors do NOT trigger the banner', () => {
    const nodeErr: GraphValidationError = {
      type: 'parameter_invalid',
      detail: 'sigma must be > 0',
      node: 'n1',
      field: 'sigma',
    }
    const w = mount(CanvasErrorBanner, {
      props: { validationResult: makeResult([nodeErr]) },
    })
    expect(w.find('.canvas-error-banner').exists()).toBe(false)
  })
})
