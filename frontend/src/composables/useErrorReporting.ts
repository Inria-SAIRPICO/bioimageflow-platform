import { useToast } from 'primevue/usetoast'
import {
  useErrorStore,
  type ErrorKind,
  type ErrorReportInput,
} from '@/stores/errors'

interface KindPolicy {
  severity: 'info' | 'warn' | 'error'
  /** Toast only the first time this kind fires per session. */
  once: boolean
  /** Whether to also record an entry in the error history. */
  recordHistory: boolean
  /** Whether this kind emits a toast at all. */
  toast: boolean
  /** PrimeVue Toast `life` in ms (undefined keeps it sticky). */
  lifeMs: number | undefined
}

const TOAST_POLICY: Record<ErrorKind, KindPolicy> = {
  graph_sync_error: {
    severity: 'warn',
    once: true,
    recordHistory: true,
    toast: true,
    lifeMs: 5000,
  },
  websocket_error: {
    severity: 'warn',
    once: false,
    recordHistory: true,
    toast: false,
    lifeMs: 5000,
  },
  log_subscription_failed: {
    severity: 'warn',
    once: true,
    recordHistory: true,
    toast: true,
    lifeMs: 5000,
  },
  execution_failed: {
    severity: 'error',
    once: false,
    recordHistory: true,
    toast: true,
    lifeMs: 8000,
  },
  network_unreachable: {
    severity: 'warn',
    once: false,
    recordHistory: true,
    toast: false,
    lifeMs: 5000,
  },
  edge_rejected: {
    severity: 'warn',
    once: false,
    recordHistory: false,
    toast: true,
    lifeMs: 5000,
  },
  unknown: {
    severity: 'info',
    once: false,
    recordHistory: true,
    toast: false,
    lifeMs: 5000,
  },
}

const KIND_LABELS: Record<ErrorKind, string> = {
  graph_sync_error: 'Graph sync error',
  websocket_error: 'Connection error',
  log_subscription_failed: 'Log subscription error',
  execution_failed: 'Execution failed',
  network_unreachable: 'Network unreachable',
  edge_rejected: 'Edge rejected',
  unknown: 'Error',
}

const _toastedKinds = new Set<ErrorKind>()

export function __resetErrorReportingForTests(): void {
  _toastedKinds.clear()
}

export function useErrorReporting() {
  const errorStore = useErrorStore()
  // useToast throws when no ToastService provider is mounted (unit tests
  // that don't go through the App root). Toasts are nice-to-have so we
  // proceed without them.
  let toast: ReturnType<typeof useToast> | null = null
  try {
    toast = useToast()
  } catch {
    toast = null
  }

  function reportError(input: ErrorReportInput): string | undefined {
    const policy = TOAST_POLICY[input.kind] ?? TOAST_POLICY.unknown

    let id: string | undefined
    if (policy.recordHistory) {
      id = errorStore.report(input)
    }

    if (policy.toast && (!policy.once || !_toastedKinds.has(input.kind))) {
      _toastedKinds.add(input.kind)
      if (toast) {
        try {
          toast.add({
            severity: policy.severity,
            summary: KIND_LABELS[input.kind],
            detail: input.detail,
            life: policy.lifeMs,
          })
        } catch {
          // Provider went away mid-call; swallow.
        }
      }
    }

    return id
  }

  return { reportError, __resetErrorReportingForTests }
}
