import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, computed } from 'vue'
import InputPin from '../InputPin.vue'

let mockEdges: any[] = []

vi.mock('@vue-flow/core', () => ({
  Handle: defineComponent({
    name: 'Handle',
    props: ['type', 'position', 'id'],
    template: '<div class="mock-handle vue-flow__handle" />',
  }),
  Position: { Left: 'left', Right: 'right', Top: 'top', Bottom: 'bottom' },
  useVueFlow: () => ({
    getEdges: computed(() => mockEdges),
  }),
}))

describe('InputPin', () => {
  beforeEach(() => {
    mockEdges = []
  })

  function factory(props: Record<string, unknown>, disconnectEdge?: (id: string) => void) {
    return mount(InputPin, {
      props: { nodeId: 'node-1', ...props } as any,
      global: {
        provide: disconnectEdge
          ? { 'bioimageflow:disconnectEdge': disconnectEdge }
          : undefined,
      },
    })
  }

  it('renders field name as label when disconnected', () => {
    const w = factory({ fieldName: 'image', fieldType: 'ImageFile', connected: false })
    expect(w.find('.pin-label').text()).toBe('image')
  })

  it('renders the display name without changing the handle field name', () => {
    const w = factory({
      fieldName: 'input_image',
      displayName: 'Input image',
      fieldType: 'ImageFile',
      connected: false,
    })
    expect(w.find('.pin-label').text()).toBe('Input image')
  })

  it('shows field type in tooltip (title attribute)', () => {
    const w = factory({ fieldName: 'image', fieldType: 'ImageFile', connected: false })
    expect(w.find('.input-pin').attributes('title')).toBe('ImageFile')
  })

  it('adds .connected class when connected', () => {
    const w = factory({ fieldName: 'image', fieldType: 'ImageFile', connected: true })
    expect(w.find('.pin-handle').classes()).toContain('connected')
  })

  it('does not add .connected class when disconnected', () => {
    const w = factory({ fieldName: 'image', fieldType: 'ImageFile', connected: false })
    expect(w.find('.pin-handle').classes()).not.toContain('connected')
  })

  it('shows sourceLabel when connected', () => {
    const w = factory({
      fieldName: 'image',
      fieldType: 'ImageFile',
      connected: true,
      sourceLabel: 'Output image of Loader',
    })
    expect(w.find('.pin-label').text()).toBe('Output image of Loader')
  })

  it('applies correct border-color from getTypeColor', () => {
    const w = factory({ fieldName: 'image', fieldType: 'ImageFile', connected: false })
    const handle = w.find('.pin-handle')
    expect(handle.attributes('style')).toContain('border-color: rgb(74, 144, 217)')
  })

  it('fills background when connected', () => {
    const w = factory({ fieldName: 'image', fieldType: 'ImageFile', connected: true })
    const handle = w.find('.pin-handle')
    expect(handle.attributes('style')).toContain('background-color: rgb(74, 144, 217)')
  })

  it('transparent background when disconnected', () => {
    const w = factory({ fieldName: 'image', fieldType: 'ImageFile', connected: false })
    const handle = w.find('.pin-handle')
    expect(handle.attributes('style')).toContain('background-color: transparent')
  })

  it('shows positional index number in positional mode', () => {
    const w = factory({
      fieldName: 'bif:v1:dataframe-position:0',
      fieldType: 'DataFrame',
      connected: false,
      positional: true,
      positionalIndex: 0,
    })
    expect(w.find('.pin-label').text()).toBe('1')
  })

  it('shows positional index 3 as "4"', () => {
    const w = factory({
      fieldName: 'bif:v1:dataframe-position:3',
      fieldType: 'DataFrame',
      connected: false,
      positional: true,
      positionalIndex: 3,
    })
    expect(w.find('.pin-label').text()).toBe('4')
  })

  // --- Drag-to-disconnect gesture ---

  describe('pointerdown gesture', () => {
    it('disconnects the incoming edge when a connected handle is grabbed', async () => {
      mockEdges = [
        {
          id: 'e_src_node-1',
          source: 'src',
          target: 'node-1',
          sourceHandle: 'output',
          targetHandle: 'image',
        },
      ]
      // Provide a fake source handle the component can find and dispatch onto
      const sourceNode = document.createElement('div')
      sourceNode.className = 'vue-flow__node'
      sourceNode.setAttribute('data-id', 'src')
      const sourceHandle = document.createElement('div')
      sourceHandle.className = 'vue-flow__handle'
      sourceHandle.setAttribute('data-handleid', 'output')
      sourceNode.appendChild(sourceHandle)
      document.body.appendChild(sourceNode)

      const disconnectEdge = vi.fn()
      const w = factory(
        {
          fieldName: 'image',
          fieldType: 'ImageFile',
          connected: true,
          sourceLabel: 'Src.output',
        },
        disconnectEdge,
      )

      const handleEl = w.find('.pin-handle').element as HTMLElement
      handleEl.dispatchEvent(
        new PointerEvent('pointerdown', {
          bubbles: true,
          cancelable: true,
          clientX: 50,
          clientY: 50,
          pointerId: 1,
          isPrimary: true,
        }),
      )

      expect(disconnectEdge).toHaveBeenCalledWith('e_src_node-1')
      document.body.removeChild(sourceNode)
    })

    it('does not call disconnect when the pin is not connected', () => {
      const disconnectEdge = vi.fn()
      const w = factory(
        { fieldName: 'image', fieldType: 'ImageFile', connected: false },
        disconnectEdge,
      )

      const handleEl = w.find('.pin-handle').element as HTMLElement
      handleEl.dispatchEvent(
        new PointerEvent('pointerdown', {
          bubbles: true,
          cancelable: true,
          clientX: 50,
          clientY: 50,
          pointerId: 1,
          isPrimary: true,
        }),
      )

      expect(disconnectEdge).not.toHaveBeenCalled()
    })
  })

  // --- Phase 3: variant prop ---

  describe('variant prop', () => {
    it('defaults to body variant with round pin styling', () => {
      const w = factory({ fieldName: 'image', fieldType: 'ImageFile', connected: false })
      const handle = w.find('.pin-handle')
      // Body variant: round (border-radius: 50%)
      expect(handle.exists()).toBe(true)
      expect(w.find('.input-pin').classes()).not.toContain('input-pin--header')
    })

    it('header variant adds input-pin--header class', () => {
      const w = factory({ fieldName: 'bif:v1:dataframe-position:0', fieldType: 'DataFrame', connected: false, variant: 'header' })
      expect(w.find('.input-pin').classes()).toContain('input-pin--header')
    })

    it('header variant renders square pin (no border-radius 50%)', () => {
      const w = factory({ fieldName: 'bif:v1:dataframe-position:0', fieldType: 'DataFrame', connected: false, variant: 'header' })
      const handle = w.find('.pin-handle')
      expect(handle.classes()).toContain('pin-handle--header')
    })

    it('body variant does not add header class', () => {
      const w = factory({ fieldName: 'image', fieldType: 'ImageFile', connected: false, variant: 'body' })
      expect(w.find('.input-pin').classes()).not.toContain('input-pin--header')
    })
  })
})
