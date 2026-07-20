import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import NodeContextMenu from '../NodeContextMenu.vue'

describe('NodeContextMenu', () => {
  function factory(options: {
    enabled?: boolean
    canOpenNestedWorkflow?: boolean
    hasWorkspaceSource?: boolean
  } = {}) {
    return mount(NodeContextMenu, {
      props: {
        nodeId: 'node-1',
        position: { x: 100, y: 200 },
        enabled: options.enabled ?? true,
        canOpenNestedWorkflow: options.canOpenNestedWorkflow ?? false,
        hasWorkspaceSource: options.hasWorkspaceSource ?? false,
      },
    })
  }

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

  it('shows "Group into workflow" item', () => {
    const w = factory()
    expect(w.findAll('li')[2].text()).toBe('Group into workflow')
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

  it('emits group-into-workflow on third item click', async () => {
    const w = factory()
    await w.findAll('li')[2].trigger('click')
    expect(w.emitted('group-into-workflow')).toBeTruthy()
  })

  it('emits open-workflow when the target is a workflow', async () => {
    const w = factory({ canOpenNestedWorkflow: true })
    await w.findAll('li')[2].trigger('click')
    expect(w.text()).toContain('Open workflow')
    expect(w.emitted('open-workflow')).toBeTruthy()
    expect(w.emitted('group-into-workflow')).toBeFalsy()
  })

  it('offers explicit source actions for a provenance-linked workflow', async () => {
    const w = factory({ canOpenNestedWorkflow: true, hasWorkspaceSource: true })
    expect(w.text()).toContain('Open source workflow')
    expect(w.text()).toContain('Update from source')
    expect(w.text()).toContain('Detach from source')

    await w.findAll('li')[3].trigger('click')
    await w.findAll('li')[4].trigger('click')
    await w.findAll('li')[5].trigger('click')

    expect(w.emitted('open-source-workflow')).toBeTruthy()
    expect(w.emitted('update-from-source')).toBeTruthy()
    expect(w.emitted('detach-source')).toBeTruthy()
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
