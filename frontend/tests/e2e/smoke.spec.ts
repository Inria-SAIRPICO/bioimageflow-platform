import { test, expect } from '@playwright/test';

test('app shell renders', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#bioimageflow-app')).toBeVisible();
  await expect(page.locator('[data-testid="app-menubar"]')).toBeVisible();
});
