import { defineConfig, devices } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const e2eRoot = process.env.BIOIMAGEFLOW_E2E_ROOT
  ?? mkdtempSync(join(tmpdir(), 'bioimageflow-platform-playwright-'));
const frontendPort = process.env.BIOIMAGEFLOW_E2E_FRONTEND_PORT ?? '5173';
const backendPort = process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000';
const hotReloadFixture = join(
  e2eRoot,
  'tool_packages',
  'e2e_hot_reload_tools',
  '1.0.0',
  'e2e_hot_reload_tools',
  'files.py',
);

process.env.BIOIMAGEFLOW_E2E_ROOT = e2eRoot;
process.env.BIOIMAGEFLOW_HOT_RELOAD_FIXTURE = hotReloadFixture;

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  use: {
    baseURL: `http://localhost:${frontendPort}`,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
  ],
  webServer: [
    {
      command: `cd ../backend && uv run --frozen uvicorn tests.e2e_app:create_app --factory --host 127.0.0.1 --port ${backendPort}`,
      url: `http://127.0.0.1:${backendPort}/api/v1/health`,
      reuseExistingServer: false,
      env: {
        BIOIMAGEFLOW_E2E_ROOT: e2eRoot,
        BIOIMAGEFLOW_HOT_RELOAD_FIXTURE: hotReloadFixture,
      },
    },
    {
      command: `bun run dev -- --port ${frontendPort}`,
      url: `http://localhost:${frontendPort}`,
      reuseExistingServer: false,
      env: {
        BIOIMAGEFLOW_E2E_BACKEND_PORT: backendPort,
      },
    },
  ],
});
