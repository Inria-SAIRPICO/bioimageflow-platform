import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, nextTick, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { automaticColumnWidth, readColumnWidths, useTableColumnWidths } from '../useTableColumnWidths'

describe('table column widths', () => {
  let notifyResize: () => void
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback: () => void) { notifyResize = callback }
      observe() {}
      disconnect() {}
    })
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ measureText: (text: string) => ({ width: text.length * 8 }) } as unknown as CanvasRenderingContext2D)
  })
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

  it('accounts for header controls and bounded content samples', () => {
    const measure = (text: string) => text.length * 8
    expect(automaticColumnWidth({ id: 'x', label: 'X', type: 'bool' }, [true], measure)).toBe(120)
    expect(automaticColumnWidth({ id: 'x', label: 'A long numerical result', type: 'int' }, [1], measure)).toBeGreaterThan(240)
    expect(automaticColumnWidth({ id: 'x', label: 'X', type: 'str' }, ['x'.repeat(500)], measure)).toBe(480)
    expect(automaticColumnWidth({ id: 'x', label: 'X', type: 'Path' }, [], measure)).toBe(320)
    expect(automaticColumnWidth({ id: 'x', label: 'X', type: 'str' }, [...Array(50).fill('x'), 'x'.repeat(500)], measure)).toBe(120)
  })

  it('rejects malformed, zero, undersized and unreasonable saved measurements', () => {
    expect(readColumnWidths('bad')).toEqual({})
    expect(readColumnWidths('[200]')).toEqual({})
    expect(readColumnWidths('{"a":0,"b":50,"c":200,"d":99999,"e":"200"}')).toEqual({ c: 200 })
  })

  it('waits for visibility, keeps automatic widths stable and persists only user choices', async () => {
    const scope = ref('workflow-one')
    const column = { id: 'x', label: 'A long numerical result', type: 'int' }
    const columns = ref([column])
    const rows = ref([{ x: 'short' }])
    let sizing!: ReturnType<typeof useTableColumnWidths>
    const wrapper = mount(defineComponent({
      setup() { sizing = useTableColumnWidths(scope, columns, rows); return { root: sizing.root } },
      template: '<div ref="root" />',
    }))
    let visible = false
    vi.spyOn(wrapper.element, 'getBoundingClientRect').mockImplementation(() => ({ width: visible ? 600 : 0, height: visible ? 300 : 0 }) as DOMRect)
    const frame = async () => { await nextTick(); await flushPromises(); await new Promise(resolve => requestAnimationFrame(resolve)) }
    await frame()
    expect(sizing.width(column)).toBe(120)
    expect(localStorage.length).toBe(0)
    visible = true
    notifyResize!()
    await frame()
    const initial = sizing.width(column)
    expect(initial).toBeGreaterThan(240)
    rows.value = [{ x: 'long'.repeat(200) }]
    await frame()
    expect(sizing.width(column)).toBe(initial)
    sizing.resize(column, 600)
    expect(localStorage.length).toBe(0)
    sizing.cancelResize()
    expect(sizing.width(column)).toBe(initial)
    sizing.resize(column, 600, true)
    expect(localStorage.length).toBe(1)
    scope.value = 'workflow-two'
    await frame()
    expect(sizing.width(column)).toBe(480)
    scope.value = 'workflow-one'
    await frame()
    expect(sizing.width(column)).toBe(600)
    sizing.autoSize(column)
    await frame()
    expect(sizing.width(column)).toBe(480)
    expect(localStorage.length).toBe(0)
    wrapper.unmount()
  })
})
