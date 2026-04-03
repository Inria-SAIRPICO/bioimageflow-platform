import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import NodeContextMenu from '../NodeContextMenu.vue'

describe('NodeContextMenu', () => {
  function factory(enabled = true) {
    return mount(NodeContextMenu, {
      props: {
        nodeId: 'node-1',
        position: { x: 100, y: 200 },
        enabled,
      },
    })
  }

  it('renders three menu items', () => {
    const w = factory()
    const items = w.findAll('li')
    expect(items).toHaveLength(3)
  })

  it('shows "Disable" when enabled', () => {
    const w = factory(true)
    expect(w.findAll('li')[0].text()).toBe('Disable')
  })

  it('shows "Enable" when disabled', () => {
    const w = factory(false)
    expect(w.findAll('li')[0].text()).toBe('Enable')
  })

  it('shows "Create Sub-workflow" item', () => {
    const w = factory()
    expect(w.findAll('li')[1].text()).toBe('Create Sub-workflow')
  })

  it('shows "Delete" item', () => {
    const w = factory()
    expect(w.findAll('li')[2].text()).toBe('Delete')
  })

  it('emits enable-toggle on first item click', async () => {
    const w = factory()
    await w.findAll('li')[0].trigger('click')
    expect(w.emitted('enable-toggle')).toBeTruthy()
  })

  it('emits create-sub-workflow on second item click', async () => {
    const w = factory()
    await w.findAll('li')[1].trigger('click')
    expect(w.emitted('create-sub-workflow')).toBeTruthy()
  })

  it('emits delete on third item click', async () => {
    const w = factory()
    await w.findAll('li')[2].trigger('click')
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

  it('positions menu at given coordinates', () => {
    const w = factory()
    const menu = w.find('.node-context-menu')
    expect(menu.attributes('style')).toContain('left: 100px')
    expect(menu.attributes('style')).toContain('top: 200px')
  })
})
