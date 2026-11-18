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

test('invalid transaction timestamps produce a recoverable error instead of a render crash', async ({ page }) => {
  const crashes: string[] = [];
  page.on('pageerror', (error) => crashes.push(error.message));
  await page.route('**/api/v1/demo/overview', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.recent_transactions[0].occurred_at = 'invalid-date';
    await route.fulfill({ response, json: body });
  });
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('invalid response');
  await expect(page.getByTestId('transaction-count')).toHaveText('—');
  expect(crashes).toEqual([]);
  await page.unroute('**/api/v1/demo/overview');
  await page.getByRole('button', { name: 'Refresh connection' }).click();
  await expect(page.getByTestId('transaction-count')).toHaveText('6');
});

test('incorrect readiness payload is not mistaken for a migration problem', async ({ page }) => {
  await page.route('**/api/v1/health/ready', (route) => route.fulfill({
    status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'private-upstream-error' }),
  }));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('invalid response');
  await expect(page.getByRole('alert')).not.toContainText('private-upstream-error');
});

test('transaction currency comes from the API', async ({ page }) => {
  await page.route('**/api/v1/demo/overview', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.recent_transactions[0].currency = 'USD';
    await route.fulfill({ response, json: body });
  });
  await page.goto('/');
  await expect(page.getByRole('cell', { name: '$95,000.00', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: '₹95,000.00', exact: true })).toHaveCount(0);
});

test('a valid empty workspace displays zero counts and an empty state', async ({ page }) => {
  await page.route('**/api/v1/demo/overview', (route) => route.fulfill({ json: {
    mode: 'synthetic_demo', analyst_name: 'Demo analyst', transaction_count: 0,
    case_count: 0, assessment_count: 0, recent_transactions: [],
  } }));
  await page.goto('/');
  await expect(page.getByTestId('transaction-count')).toHaveText('0');
  await expect(page.getByRole('heading', { name: 'No transactions to display' })).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('loading state prevents duplicate refresh requests until data arrives', async ({ page }) => {
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route('**/api/v1/demo/overview', async (route) => {
    await gate;
    await route.continue();
  });
  try {
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'Checking connection…' })).toBeDisabled();
    await expect(page.getByTestId('transaction-count')).toHaveText('—');
  } finally {
    release();
  }
  await expect(page.getByRole('button', { name: 'Refresh connection' })).toBeEnabled();
  await expect(page.getByTestId('transaction-count')).toHaveText('6');
});

test('non-JSON upstream responses are reported without exposing their body', async ({ page }) => {
  await page.route('**/api/v1/demo/overview', (route) => route.fulfill({
    status: 200, contentType: 'text/html', body: '<h1>Private upstream diagnostics</h1>',
  }));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('invalid response');
  await expect(page.getByRole('alert')).not.toContainText('Private upstream diagnostics');
  await expect(page.getByTestId('transaction-count')).toHaveText('—');
});

test('missing optional context is labeled unavailable without inventing data', async ({ page }) => {
  await page.route('**/api/v1/demo/overview', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    Object.assign(body.recent_transactions[0], {
      customer_id: null, device_id: null, beneficiary_id: null,
    });
    await route.fulfill({ response, json: body });
  });
  await page.goto('/');
  await expect(page.getByTestId('transaction-count')).toHaveText('6');
  await expect(page.getByText('Customer unavailable', { exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'Unavailable', exact: true })).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
});
