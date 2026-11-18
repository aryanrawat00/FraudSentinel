import { expect, test } from '@playwright/test';

const base = '/api/v1/intelligence';
const headers = { 'X-FraudSentinel-Sandbox': 'synthetic-only' };

test('real PostgreSQL workflow reaches the UI, timeline, evidence and JSON report', async ({
  page,
  request,
}) => {
  const prefix = `browser_${Date.now()}`;
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  for (const account of [`${prefix}_a`, `${prefix}_b`]) {
    expect(
      (
        await request.post(base + '/accounts', {
          headers,
          data: {
            account_id: account,
            data_source: 'browser_synthetic_fixture',
            is_synthetic: true,
          },
        })
      ).status(),
    ).toBe(201);
  }
  for (let i = 0; i < 6; i++) {
    expect(
      (
        await request.post(base + '/transactions', {
          headers,
          data: {
            transaction_id: `${prefix}_${i}`,
            source_account_id: `${prefix}_a`,
            destination_account_id: `${prefix}_b`,
            amount: i === 5 ? '10000.00' : '100.00',
            currency: 'INR',
            occurred_at: `2026-12-${String(i + 1).padStart(2, '0')}T12:00:00Z`,
            transaction_type: 'transfer',
            status: 'completed',
            data_source: 'browser_synthetic_fixture',
            is_synthetic: true,
          },
        })
      ).status(),
    ).toBe(201);
  }
  await page.goto('/#investigations');
  await page.getByRole('button', { name: 'Transactions', exact: true }).click();
  await page.getByRole('button', { name: `${prefix}_5`, exact: true }).click();
  await page.getByRole('button', { name: 'Analyze transaction', exact: true }).click();
  await expect(page.getByRole('heading', { name: /25.00 \/ 100/ })).toBeVisible();
  await expect(page.getByText('AMOUNT_SPIKE · +25')).toBeVisible();
  await page.getByRole('button', { name: 'Collect evidence', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Supporting evidence' })).toBeVisible();
  const collected = await (await request.get(base + `/evidence?transaction_id=${prefix}_5`)).json();
  expect(collected).toHaveLength(1);
  await page.getByRole('button', { name: 'Create investigation from transaction' }).click();
  await page.getByLabel('Case title', { exact: true }).fill(`Investigation ${prefix}`);
  await page
    .getByLabel('Description', { exact: true })
    .fill('Synthetic end-to-end browser verification');
  await page.getByRole('button', { name: 'Create case', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: `Investigation ${prefix}`, exact: true }),
  ).toBeVisible();
  await page.getByLabel('Case status', { exact: true }).selectOption('under_investigation');
  await page.getByRole('button', { name: 'Save case changes' }).click();
  await expect(page.getByLabel('Case status', { exact: true })).toHaveValue('under_investigation');
  await page
    .getByLabel('Investigation note', { exact: true })
    .fill('Analyst note: verify the synthetic source records.');
  await page.getByRole('button', { name: 'Add analyst note' }).click();
  await expect(
    page.getByText('Analyst note: verify the synthetic source records.', { exact: true }),
  ).toBeVisible();
  await page.getByLabel('Link evidence IDs', { exact: true }).fill(collected[0].evidence_id);
  await page.getByRole('button', { name: 'Link records', exact: true }).click();
  await page.getByRole('button', { name: 'Generate investigation report' }).click();
  const report = page.getByRole('article', { name: 'Investigation report' });
  await expect(report.getByRole('heading', { name: 'recorded facts' })).toBeVisible();
  await expect(report).toContainText(`${prefix}_5`);
  await expect(report).toContainText(collected[0].evidence_id);
  await expect(report).toContainText('Rule scores are review indicators');
  await expect(report.getByRole('heading', { name: 'analyst notes' })).toBeVisible();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download JSON report' }).click();
  expect((await downloadPromise).suggestedFilename()).toMatch(/^report_.*\.json$/);
  expect(errors).toEqual([]);
});

test('dashboard uses actual API totals and account graph exposes source references', async ({
  page,
  request,
}) => {
  const dashboard = await (await request.get(base + '/dashboard')).json();
  await page.goto('/#investigations');
  await expect(
    page.locator('.metrics article').filter({ hasText: 'Total transactions' }).locator('strong'),
  ).toHaveText(String(dashboard.transaction_count));
  await page.getByRole('button', { name: 'Relationships', exact: true }).click();
  await page.getByLabel('Root account', { exact: true }).selectOption('scenario_sender');
  await expect(
    page.getByRole('img', { name: 'Directed recorded transaction connections' }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: 'directed cycle' })).toBeVisible();
  await expect(page.getByText('scenario_cycle_b', { exact: false }).first()).toBeVisible();
});

test('evidence filtering displays empty results without invented evidence', async ({ page }) => {
  await page.goto('/#investigations');
  await page.getByRole('button', { name: 'Evidence', exact: true }).click();
  await page.getByLabel('Transaction filter').fill('scenario_normal');
  await page.getByRole('button', { name: 'Filter evidence' }).click();
  await expect(page.getByText('No evidence records in this selection.')).toBeVisible();
});

test('case form validation prevents an empty title mutation', async ({ page }) => {
  let writes = 0;
  page.on('request', (r) => {
    if (r.method() === 'POST' && r.url().endsWith('/intelligence/cases')) writes++;
  });
  await page.goto('/#investigations');
  await page.getByRole('button', { name: 'Cases', exact: true }).click();
  await page.getByText('Create investigation', { exact: true }).click();
  await page.getByRole('button', { name: 'Create case', exact: true }).click();
  expect(
    await page
      .getByLabel('Case title', { exact: true })
      .evaluate((input: HTMLInputElement) => input.validity.valueMissing),
  ).toBeTruthy();
  expect(writes).toBe(0);
});

test('malformed dashboard response is recoverable without leaking its body', async ({ page }) => {
  await page.route('**/intelligence/dashboard', (r) =>
    r.fulfill({ json: { transaction_count: 'private-invalid-value' } }),
  );
  await page.goto('/#investigations');
  await expect(page.getByRole('alert')).toContainText('invalid response');
  await expect(page.getByRole('alert')).not.toContainText('private-invalid-value');
  await page.unroute('**/intelligence/dashboard');
  await page.getByRole('button', { name: 'Refresh investigation data' }).click();
  await expect(page.getByRole('heading', { name: 'Risk distribution' })).toBeVisible();
});

test('loading blocks navigation while a request is pending', async ({ page }) => {
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/intelligence/dashboard', async (r) => {
    await gate;
    await r.continue();
  });
  try {
    await page.goto('/#investigations');
    await expect(page.getByRole('button', { name: 'Refresh investigation data' })).toBeDisabled();
    await expect(page.getByText('Loading investigation data…')).toBeVisible();
  } finally {
    release();
  }
  await expect(page.getByRole('button', { name: 'Refresh investigation data' })).toBeEnabled();
});

test('mobile investigation workspace fits and remains navigable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#investigations');
  await expect(page.getByRole('heading', { name: 'Risk distribution' })).toBeVisible();
  await page.getByRole('button', { name: 'Transactions', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Stored transactions' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
