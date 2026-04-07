import { test, expect } from '@playwright/test';

test.describe('full stack smoke', () => {
  test('app renders and backend health check responds via proxy', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Navigate to the app
    await page.goto('/');

    // Verify the app shell renders
    await expect(page.locator('#bioimageflow-app')).toBeVisible();
    await expect(page.locator('[data-testid="app-menubar"]')).toBeVisible();

    // Fetch health endpoint through Vite proxy
    const health = await page.evaluate(() =>
      fetch('/api/v1/health').then((r) => r.json()),
    );
    expect(health).toHaveProperty('status', 'ok');

    // Confirm no console errors
    expect(consoleErrors).toEqual([]);
  });
});
