import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// ---- Mock stores the composable dispatches to --------------------------------

const executionStoreMock = {
  applyProgress: vi.fn(),
  applyNodeState: vi.fn(),
  applyExecutionComplete: vi.fn(),
  fetchStatus: vi.fn(async () => {}),
}

const toolRegistryStoreMock = {
  applyToolReload: vi.fn(),
  applyPackageInstall: vi.fn(),
  applyEnvironmentStatus: vi.fn(),
  fetchTools: vi.fn(async () => {}),
}

const loggerStoreMock = {
  addEntry: vi.fn(),
  clearEntries: vi.fn(),
  getLastSubscription: vi.fn(() => null as { nodeId?: string; level?: string } | null),
  setLastSubscription: vi.fn(),
}

const errorStoreMock = {
  report: vi.fn(),
}

vi.mock('@/stores/execution', () => ({
  useExecutionStore: () => executionStoreMock,
}))
vi.mock('@/stores/toolRegistry', () => ({
  useToolRegistryStore: () => toolRegistryStoreMock,
}))
vi.mock('@/stores/logger', () => ({
  useLoggerStore: () => loggerStoreMock,
}))
vi.mock('@/stores/errors', () => ({
  useErrorStore: () => errorStoreMock,
}))

// ---- Mock WebSocket ----------------------------------------------------------

class MockWebSocket {
  static instances: MockWebSocket[] = []
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  url: string
  readyState = MockWebSocket.CONNECTING
  sent: string[] = []
  onopen: ((ev: Event) => void) | null = null
  onclose: ((ev: CloseEvent) => void) | null = null
  onerror: ((ev: Event) => void) | null = null
  onmessage: ((ev: MessageEvent) => void) | null = null

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  send(payload: string) {
    this.sent.push(payload)
  }

  close(_code?: number, _reason?: string) {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.({ code: 1000, reason: '', wasClean: true } as CloseEvent)
  }

  // Test helpers
  open() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }

  receive(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent)
  }

  triggerClose() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.({ code: 1006, reason: 'abnormal', wasClean: false } as CloseEvent)
  }

  triggerError() {
    this.onerror?.(new Event('error'))
  }
}

// Install global WebSocket mock
;(globalThis as unknown as { WebSocket: typeof WebSocket }).WebSocket =
  MockWebSocket as unknown as typeof WebSocket

// ---- Shared helpers ----------------------------------------------------------

function latestSocket() {
  return MockWebSocket.instances[MockWebSocket.instances.length - 1]
}

async function flushMicrotasks() {
  await Promise.resolve()
  await Promise.resolve()
}

// ---- Tests -------------------------------------------------------------------

describe('useWebSocket', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    MockWebSocket.instances = []
    vi.useFakeTimers()
    const mod = await import('@/composables/useWebSocket')
    mod.__resetForTests()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('connect sets connectionState to connecting, then connected on open', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    const { connectionState, connect } = useWebSocket()
    connect('ws://test/ws')
    expect(connectionState.value).toBe('connecting')

    latestSocket().open()
    expect(connectionState.value).toBe('connected')
  })

  it('dispatches progress to executionStore.applyProgress', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()

    latestSocket().receive({
      type: 'progress',
      node_id: 'n1',
      status: 'running',
      row: 3,
      total_rows: 10,
      timestamp: 1.0,
    })

    expect(executionStoreMock.applyProgress).toHaveBeenCalledTimes(1)
  })

  it('dispatches node_state to executionStore.applyNodeState (single target)', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()

    latestSocket().receive({
      type: 'node_state',
      node_id: 'n1',
      status: 'executed',
      cached: true,
    })

    expect(executionStoreMock.applyNodeState).toHaveBeenCalledTimes(1)
    expect(executionStoreMock.applyNodeState).toHaveBeenCalledWith(
      expect.objectContaining({ node_id: 'n1', status: 'executed' }),
    )
  })

  it('dispatches log to loggerStore.addEntry with mapped field names', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()

    latestSocket().receive({
      type: 'log',
      level: 'INFO',
      message: 'hi',
      node_id: 'n1',
      timestamp: 1.5,
    })

    expect(loggerStoreMock.addEntry).toHaveBeenCalledWith({
      level: 'INFO',
      message: 'hi',
      nodeId: 'n1',
      timestamp: 1.5,
    })
  })

  it('dispatches execution_complete to executionStore.applyExecutionComplete', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()

    latestSocket().receive({
      type: 'execution_complete',
      success: true,
      errors: [],
      node_statuses: {},
    })

    expect(executionStoreMock.applyExecutionComplete).toHaveBeenCalledTimes(1)
  })

  it('dispatches tool_reload to toolRegistryStore.applyToolReload', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()

    latestSocket().receive({
      type: 'tool_reload',
      tool_name: 't1',
      tool_metadata: { name: 't1' },
    })

    expect(toolRegistryStoreMock.applyToolReload).toHaveBeenCalledTimes(1)
  })

  it('dispatches package_install to toolRegistryStore.applyPackageInstall', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()

    latestSocket().receive({
      type: 'package_install',
      package_name: 'pkg',
      status: 'installing',
    })

    expect(toolRegistryStoreMock.applyPackageInstall).toHaveBeenCalledTimes(1)
  })

  it('dispatches environment_status to toolRegistryStore.applyEnvironmentStatus', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()

    latestSocket().receive({
      type: 'environment_status',
      env_name: 'napari',
      status: 'running',
    })

    expect(toolRegistryStoreMock.applyEnvironmentStatus).toHaveBeenCalledTimes(1)
  })

  it('ack resolves the pending Promise for the matching message_id', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    const { sendSubscribeLogs } = useWebSocket()
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()

    const promise = sendSubscribeLogs({ level: 'INFO' })

    // Extract the message_id from the sent payload
    const sent = JSON.parse(latestSocket().sent[0])
    expect(sent.type).toBe('subscribe_logs')
    expect(sent.message_id).toBeTruthy()

    latestSocket().receive({ type: 'ack', ref: sent.message_id })
    await expect(promise).resolves.toBeUndefined()
  })

  it('ack persists the applied filter to loggerStore for reconnect replay', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()

    const promise = useWebSocket().sendSubscribeLogs({
      nodeId: 'n42',
      level: 'WARNING',
    })
    const sent = JSON.parse(latestSocket().sent[0])
    latestSocket().receive({ type: 'ack', ref: sent.message_id })
    await promise

    expect(loggerStoreMock.setLastSubscription).toHaveBeenCalledWith({
      nodeId: 'n42',
      level: 'WARNING',
    })
  })

  it('error with ref rejects the pending Promise', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    const { sendSubscribeLogs } = useWebSocket()
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()

    const promise = sendSubscribeLogs({ level: 'INFO' })
    const sent = JSON.parse(latestSocket().sent[0])

    latestSocket().receive({
      type: 'error',
      ref: sent.message_id,
      code: 'invalid_payload',
      detail: 'nope',
    })
    await expect(promise).rejects.toThrow()
  })

  it('sendSubscribeLogs sends correct JSON', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()

    void useWebSocket().sendSubscribeLogs({ nodeId: 'n1', level: 'WARNING' })
    const sent = JSON.parse(latestSocket().sent[0])
    expect(sent.type).toBe('subscribe_logs')
    expect(sent.node_id).toBe('n1')
    expect(sent.level).toBe('WARNING')
    expect(typeof sent.message_id).toBe('string')
  })

  it('sendSubscribeLogs rejects on timeout and reports to errorStore', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()

    const promise = useWebSocket().sendSubscribeLogs({ level: 'INFO' })
    // Capture the rejection
    const rejection = expect(promise).rejects.toThrow()
    vi.advanceTimersByTime(6000)
    await rejection

    expect(errorStoreMock.report).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'log_subscription_failed' }),
    )
  })

  it('close event sets connectionState to disconnected', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    const { connectionState, connect } = useWebSocket()
    connect('ws://test/ws')
    latestSocket().open()
    expect(connectionState.value).toBe('connected')

    latestSocket().triggerClose()
    expect(connectionState.value).toBe('disconnected')
  })

  it('reconnects after close with 1s delay', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()
    latestSocket().triggerClose()

    expect(MockWebSocket.instances.length).toBe(1)
    vi.advanceTimersByTime(1000)
    await flushMicrotasks()
    expect(MockWebSocket.instances.length).toBe(2)
  })

  it('exponential backoff doubles to 2, 4, 8, 16, then caps at 30', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')

    // First connection opens successfully so attempt counter starts at 0,
    // then every subsequent reconnect fails (never calls .open()) so the
    // delay should double each time.
    latestSocket().open()
    latestSocket().triggerClose()

    const expectedDelays = [1000, 2000, 4000, 8000, 16000, 30000, 30000]
    for (const delay of expectedDelays) {
      const before = MockWebSocket.instances.length
      vi.advanceTimersByTime(delay - 1)
      await flushMicrotasks()
      expect(MockWebSocket.instances.length).toBe(before)
      vi.advanceTimersByTime(1)
      await flushMicrotasks()
      expect(MockWebSocket.instances.length).toBe(before + 1)
      // New socket in 'connecting' state — simulate failure by closing it.
      latestSocket().triggerClose()
    }
  })

  it('successful reconnect executes recovery sequence', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()

    // Drop
    latestSocket().triggerClose()
    executionStoreMock.fetchStatus.mockClear()
    toolRegistryStoreMock.fetchTools.mockClear()

    vi.advanceTimersByTime(1000)
    await flushMicrotasks()
    // New socket opens
    latestSocket().open()
    await flushMicrotasks()

    expect(executionStoreMock.fetchStatus).toHaveBeenCalled()
    expect(toolRegistryStoreMock.fetchTools).toHaveBeenCalled()
  })

  it('reconnect re-subscribes logs with last subscription', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()

    loggerStoreMock.getLastSubscription.mockReturnValue({
      nodeId: 'n1',
      level: 'INFO',
    })
    latestSocket().triggerClose()
    vi.advanceTimersByTime(1000)
    await flushMicrotasks()
    latestSocket().open()
    await flushMicrotasks()

    const sub = latestSocket().sent.find((s) => JSON.parse(s).type === 'subscribe_logs')
    expect(sub).toBeTruthy()
    const parsed = JSON.parse(sub!)
    expect(parsed.node_id).toBe('n1')
    expect(parsed.level).toBe('INFO')
  })

  it('disconnect() prevents reconnection', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()
    useWebSocket().disconnect()

    vi.advanceTimersByTime(30000)
    await flushMicrotasks()
    // Only the first socket exists; no reconnect attempt
    expect(MockWebSocket.instances.length).toBe(1)
  })

  it('multiple calls to useWebSocket return the same connectionState ref (singleton)', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    const a = useWebSocket()
    const b = useWebSocket()
    expect(a.connectionState).toBe(b.connectionState)
  })

  it('__resetForTests clears singleton state', async () => {
    const mod = await import('@/composables/useWebSocket')
    mod.useWebSocket().connect('ws://test/ws')
    latestSocket().open()
    expect(mod.useWebSocket().connectionState.value).toBe('connected')

    mod.__resetForTests()
    expect(mod.useWebSocket().connectionState.value).toBe('disconnected')
  })

  it('unknown message type is ignored without crashing', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    useWebSocket().connect('ws://test/ws')
    latestSocket().open()

    expect(() => {
      latestSocket().receive({ type: 'bogus_type', foo: 'bar' })
    }).not.toThrow()
  })

  it('connect() while a previous socket exists detaches it (no ghost reconnects)', async () => {
    // Regression: a stale onclose handler on the first socket would overwrite
    // the new socket's connectionState back to 'disconnected', wipe the new
    // pending-ack map, and spawn a ghost reconnect cycle.
    const { useWebSocket } = await import('@/composables/useWebSocket')
    const { connectionState, connect } = useWebSocket()

    connect('ws://test/ws')
    const first = latestSocket()
    first.open()
    expect(connectionState.value).toBe('connected')

    // Caller (or pending reconnect) opens a second socket without the first
    // having been intentionally disconnected. Ghost handlers on `first`
    // must not bleed into the new singleton state.
    connect('ws://test/ws')
    const second = latestSocket()
    expect(second).not.toBe(first)
    second.open()
    expect(connectionState.value).toBe('connected')

    // Simulate the first socket's late close arriving on the wire — its
    // handlers should already be detached, so connectionState stays
    // 'connected' and no extra reconnect socket is created.
    const beforeCount = MockWebSocket.instances.length
    first.triggerClose()
    expect(connectionState.value).toBe('connected')

    vi.advanceTimersByTime(2000)
    await flushMicrotasks()
    expect(MockWebSocket.instances.length).toBe(beforeCount)
  })
})
