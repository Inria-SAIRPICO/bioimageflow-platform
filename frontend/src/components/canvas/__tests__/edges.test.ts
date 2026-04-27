import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ColumnRefEdge from '../ColumnRefEdge.vue'
import PositionalEdge from '../PositionalEdge.vue'

vi.mock('@vue-flow/core', () => ({
  getBezierPath: () => ['M 0 0 C 50 0 50 100 100 100', 50, 50, 0, 0],
  Position: { Left: 'left', Right: 'right', Top: 'top', Bottom: 'bottom' },
}))

const baseEdgeProps = {
  id: 'edge-1',
  sourceX: 0,
  sourceY: 0,
  targetX: 100,
  targetY: 100,
  sourcePosition: 'right',
  targetPosition: 'left',
}

describe('ColumnRefEdge', () => {
  it('renders an SVG path element', () => {
    const w = mount(ColumnRefEdge, {
      props: { ...baseEdgeProps, data: { type: 'ImagePath' } } as any,
    })
    const path = w.find('.vue-flow__edge-path')
    expect(path.exists()).toBe(true)
    expect(path.attributes('d')).toBe('M 0 0 C 50 0 50 100 100 100')
  })

  it('applies stroke color from getTypeColor for ImagePath', () => {
    const w = mount(ColumnRefEdge, {
      props: { ...baseEdgeProps, data: { type: 'ImagePath' } } as any,
    })
    expect(w.find('.vue-flow__edge-path').attributes('stroke')).toBe('#4A90D9')
  })

  it('applies default stroke color for unknown type', () => {
    const w = mount(ColumnRefEdge, {
      props: { ...baseEdgeProps, data: { type: 'Unknown' } } as any,
    })
    expect(w.find('.vue-flow__edge-path').attributes('stroke')).toBe('#8E8E93')
  })

  it('uses stroke-width 2', () => {
    const w = mount(ColumnRefEdge, {
      props: { ...baseEdgeProps, data: { type: 'str' } } as any,
    })
    expect(w.find('.vue-flow__edge-path').attributes('stroke-width')).toBe('2')
  })

  it('renders an invisible interaction path for easier clicking', () => {
    const w = mount(ColumnRefEdge, {
      props: { ...baseEdgeProps, data: { type: 'str' } } as any,
    })
    const interaction = w.find('.vue-flow__edge-interaction')
    expect(interaction.exists()).toBe(true)
    expect(interaction.attributes('stroke-width')).toBe('12')
    expect(interaction.attributes('stroke')).toBe('transparent')
  })
})

describe('PositionalEdge', () => {
  it('renders an SVG path element', () => {
    const w = mount(PositionalEdge, {
      props: baseEdgeProps as any,
    })
    const path = w.find('.vue-flow__edge-path')
    expect(path.exists()).toBe(true)
    expect(path.attributes('d')).toBe('M 0 0 C 50 0 50 100 100 100')
  })

  it('uses neutral gray stroke color (#7A7A80)', () => {
    const w = mount(PositionalEdge, {
      props: baseEdgeProps as any,
    })
    expect(w.find('.vue-flow__edge-path').attributes('stroke')).toBe('#7A7A80')
  })

  it('has solid stroke (no dash array)', () => {
    const w = mount(PositionalEdge, {
      props: baseEdgeProps as any,
    })
    expect(w.find('.vue-flow__edge-path').attributes('stroke-dasharray')).toBeUndefined()
  })

  it('uses thicker stroke-width 2.5', () => {
    const w = mount(PositionalEdge, {
      props: baseEdgeProps as any,
    })
    expect(w.find('.vue-flow__edge-path').attributes('stroke-width')).toBe('2.5')
  })

  it('renders an invisible interaction path for easier clicking', () => {
    const w = mount(PositionalEdge, {
      props: baseEdgeProps as any,
    })
    const interaction = w.find('.vue-flow__edge-interaction')
    expect(interaction.exists()).toBe(true)
    expect(interaction.attributes('stroke-width')).toBe('14')
  })
})
