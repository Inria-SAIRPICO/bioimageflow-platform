import { useToast } from 'primevue/usetoast'
import { hasInjectionContext } from 'vue'
import {
  ERROR_KIND_LABELS,
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
  dataset_upload_rejected: {
    severity: 'error',
    once: false,
    recordHistory: true,
    toast: true,
    lifeMs: 8000,
  },
  unknown: {
    severity: 'info',
    once: false,
    recordHistory: true,
    toast: false,
    lifeMs: 5000,
  },
}

const _toastedKinds = new Set<ErrorKind>()

type ErrorReportingInput = ErrorReportInput & {
  /** Command failures need feedback for each explicit user attempt. */
  alwaysToast?: boolean
}

export function __resetErrorReportingForTests(): void {
  _toastedKinds.clear()
}

export function useErrorReporting() {
  const errorStore = useErrorStore()
  // Store actions and background coordinators can report errors outside a
  // component setup context. In that case there is no Vue injection scope,
  // so history remains authoritative and toast feedback is simply omitted.
  let toast: ReturnType<typeof useToast> | null = null
  if (hasInjectionContext()) {
    try {
      toast = useToast()
    } catch {
      toast = null
    }
  }

  function reportError(input: ErrorReportingInput): string | undefined {
    const policy = TOAST_POLICY[input.kind] ?? TOAST_POLICY.unknown

    let id: string | undefined
    if (policy.recordHistory) {
      id = errorStore.report(input)
    }

    if (
      policy.toast
      && (input.alwaysToast || !policy.once || !_toastedKinds.has(input.kind))
    ) {
      if (!input.alwaysToast) _toastedKinds.add(input.kind)
      if (toast) {
        try {
          toast.add({
            severity: policy.severity,
            summary: ERROR_KIND_LABELS[input.kind],
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

  return { reportError }
}
