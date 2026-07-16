import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Select from 'primevue/select'
import ToggleButton from 'primevue/togglebutton'
import LoggerPanel from '../LoggerPanel.vue'
import { useLoggerStore } from '@/stores/logger'
import { useUIStore } from '@/stores/ui'

const require = createRequire(import.meta.url)
const primeIconsCss = readFileSync(require.resolve('primeicons/primeicons.css'), 'utf8')

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(LoggerPanel, {
    global: {
      plugins: [pinia, PrimeVue],
    },
  })
}

describe('LoggerPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders the panel and four level toggles with plan test ids', () => {
    const w = mountPanel()
    expect(w.find('[data-testid="panel-logger"]').exists()).toBe(true)
    for (const level of ['DEBUG', 'INFO', 'WARNING', 'ERROR']) {
      expect(w.find(`[data-testid="log-level-${level}"]`).exists()).toBe(true)
    }

    const toggles = w.findAllComponents(ToggleButton).slice(0, 4)
    expect(toggles.map((toggle) => toggle.props('modelValue'))).toEqual([
      false,
      true,
      true,
      true,
    ])
  })

  it('clicking level buttons updates the logger store only locally', async () => {
    const w = mountPanel()
    const store = useLoggerStore()

    await w.find('[data-testid="log-level-DEBUG"]').trigger('click')
    expect(store.filter.levels.has('DEBUG')).toBe(true)

    await w.find('[data-testid="log-level-INFO"]').trigger('click')
    expect(store.filter.levels.has('INFO')).toBe(false)
  })

  it('renders node filter options from graph nodes and orphan log entries', async () => {
    const w = mountPanel()
    const ui = useUIStore()
    const store = useLoggerStore()
    ui.setGraphNodes([{ id: 'n1', data: { name: 'Segmenter' } }])
    store.addEntry({ level: 'INFO', message: 'orphan', nodeId: 'old-node', timestamp: 1 })
    await w.vm.$nextTick()

    const select = w.findComponent(Select)
    expect(select.props('options')).toEqual([
      { label: 'All nodes', value: null },
      { label: 'Segmenter', value: 'n1' },
      { label: 'old-node', value: 'old-node' },
    ])
  })

  it('node dropdown updates the display filter', async () => {
    const w = mountPanel()
    const store = useLoggerStore()
    await w.findComponent(Select).vm.$emit('update:modelValue', 'n1')
    expect(store.filter.nodeId).toBe('n1')
  })

  it('auto-scopes to a single canvas selection and clears on multi-select', async () => {
    const w = mountPanel()
    const ui = useUIStore()
    const store = useLoggerStore()

    ui.setSelectedNodes(['n1'])
    await w.vm.$nextTick()
    expect(store.filter.nodeId).toBe('n1')

    ui.setSelectedNodes(['n1', 'n2'])
    await w.vm.$nextTick()
    expect(store.filter.nodeId).toBeNull()
  })

  it('auto-scope toggle disables selection-driven filtering', async () => {
    const w = mountPanel()
    const ui = useUIStore()
    const store = useLoggerStore()

    await w.find('[data-testid="log-auto-scope"]').trigger('click')
    ui.setSelectedNodes(['n1'])
    await w.vm.$nextTick()
    expect(store.filter.nodeId).toBeNull()
  })

  it('renders a visible active state for the auto-scope toggle', async () => {
    const w = mountPanel()
    const button = w.find('[data-testid="log-auto-scope"]')

    expect(button.classes()).toContain('logger-panel__auto-scope--active')
    let icon = button.find('.logger-panel__auto-scope-icon')
    expect(icon.exists()).toBe(true)
    expect(icon.classes()).toEqual(
      expect.arrayContaining([
        'pi',
        'pi-filter',
        'logger-panel__auto-scope-icon--active',
      ]),
    )
    expect(primeIconsCss).toContain('.pi-filter:before')
    await button.trigger('click')
    expect(button.classes()).not.toContain('logger-panel__auto-scope--active')
    expect(button.classes()).toContain('logger-panel__auto-scope--inactive')
    icon = button.find('.logger-panel__auto-scope-icon')
    expect(icon.classes()).toEqual(
      expect.arrayContaining([
        'pi',
        'pi-filter-slash',
        'logger-panel__auto-scope-icon--inactive',
      ]),
    )
    expect(primeIconsCss).toContain('.pi-filter-slash:before')
  })

  it('manual node filters are not overridden by canvas selection', async () => {
    const w = mountPanel()
    const ui = useUIStore()
    const store = useLoggerStore()

    await w.findComponent(Select).vm.$emit('update:modelValue', 'manual')
    ui.setSelectedNodes(['selected'])
    await w.vm.$nextTick()
    expect(store.filter.nodeId).toBe('manual')
  })

  it('debounces search input and can clear it', async () => {
    vi.useFakeTimers()
    const w = mountPanel()
    const store = useLoggerStore()
    const input = w.find('[data-testid="log-search"]')

    await input.setValue('needle')
    expect(store.filter.searchText).toBe('')
    vi.advanceTimersByTime(300)
    expect(store.filter.searchText).toBe('needle')

    await w.find('[data-testid="log-search-clear"]').trigger('click')
    expect(store.filter.searchText).toBe('')
  })

  it('renders log entries with timestamp, level badge, node name, and escaped text', async () => {
    const w = mountPanel()
    const ui = useUIStore()
    const store = useLoggerStore()
    ui.setGraphNodes([{ id: 'n1', data: { name: 'Blur 1' } }])
    store.setFilter({ levels: new Set(['DEBUG', 'INFO', 'WARNING', 'ERROR']) })
    store.addEntry({
      level: 'ERROR',
      message: '<script>alert(1)</script>\nline two',
      nodeId: 'n1',
      timestamp: 1.234,
    })
    await w.vm.$nextTick()

    const row = w.find('[data-testid="log-entry"]')
    expect(row.classes()).toContain('log-entry--error')
    expect(row.find('[data-testid="log-timestamp"]').text()).toMatch(/00:00:01\.234|01:00:01\.234/)
    expect(row.find('[data-testid="log-level-badge"]').text()).toBe('ERR')
    expect(row.find('[data-testid="log-node-name"]').text()).toBe('Blur 1')
    expect(row.find('[data-testid="log-message"]').text()).toContain('<script>alert(1)</script>')
    expect(row.find('script').exists()).toBe(false)
  })

  it('labels each log column and exposes resizable column boundaries', async () => {
    const w = mountPanel()
    const store = useLoggerStore()
    store.addEntry({ level: 'INFO', message: 'system', nodeId: null, timestamp: 1 })
    await w.vm.$nextTick()
    const headers = w.findAll('[role="columnheader"]')

    expect(headers.map((header) => header.text())).toEqual([
      'Timestamp',
      'Level',
      'Node',
      'Message',
    ])

    const timestampHandle = w.find('[aria-label="Resize Timestamp column"]')
    expect(timestampHandle.attributes('aria-valuenow')).toBe('120')

    await timestampHandle.trigger('keydown', { key: 'ArrowRight' })
    expect(timestampHandle.attributes('aria-valuenow')).toBe('128')
    expect(w.find('[data-testid="log-header"]').attributes('style')).toContain('128px')

    timestampHandle.element.dispatchEvent(
      new MouseEvent('pointerdown', { bubbles: true, clientX: 100 }),
    )
    timestampHandle.element.dispatchEvent(
      new MouseEvent('pointermove', { bubbles: true, clientX: 132 }),
    )
    timestampHandle.element.dispatchEvent(new MouseEvent('pointerup', { bubbles: true }))
    await w.vm.$nextTick()
    expect(timestampHandle.attributes('aria-valuenow')).toBe('160')
    expect(w.find('[data-testid="log-header"]').attributes('style')).toBe(
      w.find('[data-testid="log-entry"]').attributes('style'),
    )
  })

  it('hides the node name cell for framework logs', async () => {
    const w = mountPanel()
    const store = useLoggerStore()
    store.addEntry({ level: 'INFO', message: 'system', nodeId: null, timestamp: 1 })
    await w.vm.$nextTick()
    expect(w.find('[data-testid="log-node-name"]').exists()).toBe(false)
  })

  it('toggles auto-scroll and renders empty state', async () => {
    const w = mountPanel()
    const store = useLoggerStore()
    expect(w.find('[data-testid="log-empty"]').text()).toContain('No log messages')
    expect(store.autoScroll).toBe(true)

    await w.find('[data-testid="log-auto-scroll"]').trigger('click')
    expect(store.autoScroll).toBe(false)
  })

  it('renders a large capped buffer without throwing', async () => {
    const w = mountPanel()
    const store = useLoggerStore()
    store.setFilter({ levels: new Set(['DEBUG', 'INFO', 'WARNING', 'ERROR']) })
    for (let i = 0; i < 5000; i += 1) {
      store.addEntry({ level: 'INFO', message: `entry ${i}`, nodeId: null, timestamp: i })
    }
    await w.vm.$nextTick()
    expect(w.findAll('[data-testid="log-entry"]')).toHaveLength(5000)
  })
})
