import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import NodeContextMenu from '../NodeContextMenu.vue'

describe('NodeContextMenu', () => {
  function factory(options: { enabled?: boolean; canOpenSubWorkflow?: boolean } = {}) {
    return mount(NodeContextMenu, {
      props: {
        nodeId: 'node-1',
        position: { x: 100, y: 200 },
        enabled: options.enabled ?? true,
        canOpenSubWorkflow: options.canOpenSubWorkflow ?? false,
      },
    })
  }

  it('renders four menu items', () => {
    const w = factory()
    const items = w.findAll('li')
    expect(items).toHaveLength(4)
  })

  it('shows "Rename" as first item', () => {
    const w = factory()
    expect(w.findAll('li')[0].text()).toBe('Rename')
  })

  it('shows "Disable" when enabled', () => {
    const w = factory({ enabled: true })
    expect(w.findAll('li')[1].text()).toBe('Disable')
  })

  it('shows "Enable" when disabled', () => {
    const w = factory({ enabled: false })
    expect(w.findAll('li')[1].text()).toBe('Enable')
  })

  it('shows "Create Sub-workflow" item', () => {
    const w = factory()
    expect(w.findAll('li')[2].text()).toBe('Create Sub-workflow')
  })

  it('shows "Delete" item', () => {
    const w = factory()
    expect(w.findAll('li')[3].text()).toBe('Delete')
  })

  it('emits rename on first item click', async () => {
    const w = factory()
    await w.findAll('li')[0].trigger('click')
    expect(w.emitted('rename')).toBeTruthy()
  })

  it('emits enable-toggle on second item click', async () => {
    const w = factory()
    await w.findAll('li')[1].trigger('click')
    expect(w.emitted('enable-toggle')).toBeTruthy()
  })

  it('emits create-sub-workflow on third item click', async () => {
    const w = factory()
    await w.findAll('li')[2].trigger('click')
    expect(w.emitted('create-sub-workflow')).toBeTruthy()
  })

  it('emits open-sub-workflow when the target already has a sub-workflow', async () => {
    const w = factory({ canOpenSubWorkflow: true })
    await w.findAll('li')[2].trigger('click')
    expect(w.text()).toContain('Open Sub-workflow')
    expect(w.emitted('open-sub-workflow')).toBeTruthy()
    expect(w.emitted('create-sub-workflow')).toBeFalsy()
  })

  it('emits delete on fourth item click', async () => {
    const w = factory()
    await w.findAll('li')[3].trigger('click')
    expect(w.emitted('delete')).toBeTruthy()
  })

  it('emits close on Escape key', async () => {
    const w = factory()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(w.emitted('close')).toBeTruthy()
  })

  it('emits close on click outside', async () => {
    const w = factory()
    // Simulate click outside
    document.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    expect(w.emitted('close')).toBeTruthy()
  })

  it('emits close when an outside canvas element stops event propagation', () => {
    const outside = document.createElement('div')
    outside.addEventListener('mousedown', (event) => event.stopPropagation())
    document.body.appendChild(outside)
    const w = factory()

    outside.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))

    expect(w.emitted('close')).toBeTruthy()
    w.unmount()
    outside.remove()
  })

  it('positions menu at given coordinates', () => {
    const w = factory()
    const menu = w.find('.node-context-menu')
    expect(menu.attributes('style')).toContain('left: 100px')
    expect(menu.attributes('style')).toContain('top: 200px')
  })
})
