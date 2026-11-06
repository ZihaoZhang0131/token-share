import { expect, test, type Page, type Route } from '@playwright/test';
import type { AnalyticsData, AnalyticsPeriod } from '../src/types';

function statistics(period: AnalyticsPeriod = 'month', tokens = 1_500_000): AnalyticsData {
  const input = Math.round(tokens * 0.8);
  const output = tokens - input;
  const requests = tokens ? 4 : 0;
  return {
    period, start: '2026-10-31T16:00:00Z', end: '2026-11-06T08:00:00Z', timezone: 'Asia/Shanghai',
    summary: { requests, input_tokens: input, output_tokens: output, total_tokens: tokens, successes: requests ? 3 : 0, failures: requests ? 1 : 0, success_rate: requests ? 75 : null, avg_latency_ms: requests ? 1250 : null },
    daily: [
      { date: '2026-11-05', requests, input_tokens: input, output_tokens: output, total_tokens: tokens, successes: requests ? 3 : 0, failures: requests ? 1 : 0, avg_latency_ms: requests ? 1250 : null },
      { date: '2026-11-06', requests: 0, input_tokens: 0, output_tokens: 0, total_tokens: 0, successes: 0, failures: 0, avg_latency_ms: null }
    ],
    models: tokens ? [{ id: 'test-model', label: 'test-model', total_tokens: tokens, requests }] : []
  };
}

async function userPage(page: Page, analytics: (route: Route, period: AnalyticsPeriod) => Promise<void>) {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const json = (body: unknown) => route.fulfill({ json: body });
    if (url.pathname === '/api/auth/session') return json({
      csrf_token: 'fixture-csrf',
      user: { id: 'fixture-user', email: 'fixture@example.com', display_name: '测试农场主', role: 'user', must_change_password: false, active: true, monthly_token_limit: 10_000_000, rpm_limit: 20, tpm_limit: 100_000, allowed_models: ['test-model'], created_at: '2026-11-01T00:00:00Z' }
    });
    if (url.pathname === '/api/me/usage') return json({ month: '2026-11', used_tokens: 1_500_000, remaining_tokens: 8_500_000, monthly_token_limit: 10_000_000, request_count: 4, input_tokens: 1_200_000, output_tokens: 300_000, daily: [] });
    if (url.pathname === '/api/me/keys' || url.pathname === '/api/me/models') return json([]);
    if (url.pathname === '/api/me/analytics') return analytics(route, url.searchParams.get('period') as AnalyticsPeriod);
    return route.fulfill({ status: 404, json: { detail: 'Unknown fixture endpoint' } });
  });
  await page.goto('/');
}

test('a slower prior period cannot overwrite the latest selection', async ({ page }) => {
  let releaseSeven!: () => void;
  let markSevenRequested!: () => void;
  let markSevenSettled!: () => void;
  const sevenRequested = new Promise<void>((resolve) => { markSevenRequested = resolve; });
  const sevenSettled = new Promise<void>((resolve) => { markSevenSettled = resolve; });
  const sevenGate = new Promise<void>((resolve) => { releaseSeven = resolve; });
  await userPage(page, async (route, period) => {
    if (period === '7d') {
      markSevenRequested();
      await sevenGate;
      try { await route.fulfill({ json: statistics(period, 7_000_000) }); }
      catch { /* The component intentionally aborts an obsolete request. */ }
      finally { markSevenSettled(); }
      return;
    }
    return route.fulfill({ json: statistics(period, period === '30d' ? 3_000_000 : 1_000_000) });
  });
  const total = page.locator('.analytics-summary .stat-card').first().locator('strong');
  await expect(total).toHaveText('1 M');
  await page.getByRole('button', { name: '近 7 天', exact: true }).click();
  await sevenRequested;
  await page.getByRole('button', { name: '近 30 天', exact: true }).click();
  await expect(total).toHaveText('3 M');
  releaseSeven();
  await sevenSettled;
  await expect(total).toHaveText('3 M');
  await expect(page.locator('.analytics-status')).toContainText('近 30 天');
  await expect(page.getByRole('button', { name: '近 30 天', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('.usage-hero')).toContainText('1.5 M');
});

test('empty analytics does not invent success or latency measurements', async ({ page }) => {
  await userPage(page, (route, period) => route.fulfill({ json: statistics(period, 0) }));
  const cards = page.locator('.analytics-summary .stat-card');
  await expect(cards.nth(0).locator('strong')).toHaveText('0 M');
  await expect(cards.nth(1).locator('strong')).toHaveText('0');
  await expect(cards.nth(2).locator('strong')).toHaveText('—');
  await expect(cards.nth(3).locator('strong')).toHaveText('—');
  await expect(page.getByText('暂无 Token 消耗')).toBeVisible();
  await expect(page.locator('.chart-svg')).toHaveCount(0);
});

test('failed period preserves truthfully labelled prior data and can retry', async ({ page }) => {
  let failSeven = true;
  await userPage(page, (route, period) => {
    if (period === '7d' && failSeven) return route.fulfill({ status: 500, json: { detail: '统计暂时不可用' } });
    return route.fulfill({ json: statistics(period, period === '7d' ? 2_000_000 : 1_000_000) });
  });
  const total = page.locator('.analytics-summary .stat-card').first().locator('strong');
  await expect(total).toHaveText('1 M');
  await page.getByRole('button', { name: '近 7 天', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('下方仍显示上次成功加载的本月数据');
  await expect(total).toHaveText('1 M');
  await expect(page.locator('.analytics-status')).toContainText('本月');
  failSeven = false;
  await page.getByRole('button', { name: '重新加载', exact: true }).click();
  await expect(total).toHaveText('2 M');
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.locator('.analytics-status')).toContainText('近 7 天');
});

test('keyboard navigation exposes exact chart values and zero-call days', async ({ page }) => {
  await userPage(page, (route, period) => route.fulfill({ json: statistics(period) }));
  const days = page.locator('.chart-day');
  await expect(days).toHaveCount(2);
  await days.first().focus();
  await expect(days.first()).toBeFocused();
  await expect(page.locator('.chart-tooltip')).toHaveText('2026-11-05 · 输入 1,200,000 Token · 输出 300,000 Token');
  await page.keyboard.press('Tab');
  await expect(days.nth(1)).toBeFocused();
  await expect(page.locator('.chart-tooltip')).toHaveText('2026-11-06 · 输入 0 Token · 输出 0 Token');
});
