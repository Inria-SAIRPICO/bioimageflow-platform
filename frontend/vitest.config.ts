import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

const backendPort = process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'
const backendHttpUrl = `http://localhost:${backendPort}`
const allTestFiles = ['tests/unit/**/*.test.ts', 'src/**/__tests__/*.test.ts']
const nodeTestFiles = [
  'src/api/__tests__/napari.test.ts',
  'src/api/__tests__/nestedWorkflowSnapshots.test.ts',
  'src/composables/__tests__/canvasCommands.test.ts',
  'src/composables/__tests__/canvasGraphSyncRouting.test.ts',
  'src/composables/__tests__/canvasPersistenceRouting.test.ts',
  'src/composables/__tests__/canvasStatusProjection.test.ts',
  'src/composables/__tests__/useErrorReporting.test.ts',
  'src/composables/__tests__/useExecutionLock.test.ts',
  'src/composables/__tests__/useGraphSync.test.ts',
  'src/composables/__tests__/useGraphSyncNestedRetention.test.ts',
  'src/composables/__tests__/useUndoRedo.test.ts',
  'src/composables/__tests__/useValidationErrors.test.ts',
  'src/services/__tests__/*.test.ts',
  'src/sessions/__tests__/*.test.ts',
  'src/stores/__tests__/execution.test.ts',
  'src/stores/__tests__/napari.test.ts',
  'src/stores/__tests__/subWorkflowSessions.test.ts',
  'src/stores/__tests__/workflowDraft.test.ts',
  'src/utils/__tests__/dataTableSources.test.ts',
  'src/utils/__tests__/imagePaths.test.ts',
  'src/utils/__tests__/nodeIdGenerator.test.ts',
  'src/utils/__tests__/typeColors.test.ts',
  'tests/unit/api/*.test.ts',
  'tests/unit/composables/useConnectionStatus.test.ts',
  'tests/unit/composables/useFieldFocusTracker.test.ts',
  'tests/unit/composables/useWebSocket.test.ts',
  'tests/unit/stores/errors.test.ts',
  'tests/unit/stores/execution.test.ts',
  'tests/unit/stores/logger.test.ts',
  'tests/unit/stores/settings.test.ts',
]
const indexedDbTestFiles = [
  'src/components/layout/__tests__/AppShell.test.ts',
  'src/composables/__tests__/useIndexedDB.test.ts',
]

export default defineConfig({
  plugins: [vue()],
  define: {
    'import.meta.env.VITE_BIOIMAGEFLOW_BACKEND_HTTP_URL': JSON.stringify(backendHttpUrl),
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    globals: true,
    onConsoleLog(log, type) {
      if (type === 'stderr') {
        throw new Error(`Unexpected console warning or error:\n${log}`)
      }
    },
    coverage: {
      provider: 'v8',
      reportsDirectory: 'test-results/coverage',
      reporter: ['text', 'html', 'lcov', 'json-summary'],
      include: ['src/**/*.{ts,vue}'],
      exclude: [
        'src/api/types.ts',
        'src/test-utils/**',
        'src/**/__tests__/**',
        'src/**/*.d.ts',
      ],
    },
    projects: [
      {
        extends: true,
        test: {
          name: 'node',
          environment: 'node',
          include: nodeTestFiles,
        },
      },
      {
        extends: true,
        test: {
          name: 'jsdom',
          environment: 'jsdom',
          include: allTestFiles,
          exclude: [...nodeTestFiles, ...indexedDbTestFiles],
          setupFiles: ['./tests/setup.ts'],
        },
      },
      {
        extends: true,
        test: {
          name: 'indexeddb',
          environment: 'jsdom',
          include: indexedDbTestFiles,
          setupFiles: ['./tests/setup.ts', './tests/setup-indexeddb.ts'],
        },
      },
    ],
  },
})
