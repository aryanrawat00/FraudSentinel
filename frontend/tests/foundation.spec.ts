import { expect, test } from '@playwright/test';

test('real backend data reaches the React workspace', async ({ page, request }) => {
  const health = await request.get('/api/v1/health');
  expect(health.ok()).toBeTruthy();
  expect((await health.json()).service).toBe('fraudsentinel-api');
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByText('Connected · schema ready')).toBeVisible();
  await expect(page.getByTestId('transaction-count')).toHaveText('6');
  await expect(page.getByText('txn_demo_006')).toBeVisible();
  await expect(page.getByRole('cell', { name: '₹95,000.00', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: /16 Nov.*02:14/ })).toBeVisible();
  await page.getByRole('button', { name: 'Refresh connection' }).click();
  await expect(page.getByText('Connected · schema ready')).toBeVisible();
  expect(errors).toEqual([]);
});

test('database outage shows an actionable state without fabricated counts', async ({ page }) => {
  await page.route('**/api/v1/health/ready', (route) => route.fulfill({
    status: 503, contentType: 'application/json',
    body: JSON.stringify({ status: 'not_ready', database: 'unavailable', schema_ready: false }),
  }));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Database unavailable');
  await expect(page.getByTestId('transaction-count')).toHaveText('—');
  await expect(page.getByText('txn_demo_006')).toHaveCount(0);
});

test('API outage can be retried', async ({ page }) => {
  await page.route('**/api/v1/health', (route) => route.abort());
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('API unavailable');
  await page.unroute('**/api/v1/health');
  await page.getByRole('button', { name: 'Refresh connection' }).click();
  await expect(page.getByTestId('transaction-count')).toHaveText('6');
});

test('mobile workspace fits the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByTestId('transaction-count')).toHaveText('6');
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await expect(page.getByRole('button', { name: 'Refresh connection' })).toBeVisible();
});
