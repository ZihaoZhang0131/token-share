import { expect, test } from '@playwright/test';

test('model ceiling and default budget can be edited independently or reset to automatic', async ({ page }) => {
  let model = {
    id: 'budget-model', public_name: 'deepseek-flash', upstream_model: 'deepseek-flash',
    provider_id: 'provider', max_output_tokens: 393216, default_output_tokens: null as number | null,
    tokenizer: 'cl100k_base', api_mode: 'both', reasoning_effort: null, active: true,
  };
  const saved: Record<string, unknown>[] = [];
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/session') return route.fulfill({ json: {
      csrf_token: 'fixture', user: { id: 'admin', email: 'admin@example.com', display_name: '管理员',
        role: 'admin', must_change_password: false, active: true, allowed_models: [] },
    } });
    if (path === '/api/admin/providers') return route.fulfill({ json: [{ id: 'provider', name: 'DeepSeek', active: true }] });
    if (path === '/api/admin/models/budget-model') {
      const body = route.request().postDataJSON();
      saved.push(body);
      model = { ...model, ...body };
      return route.fulfill({ json: model });
    }
    if (path === '/api/admin/models') return route.fulfill({ json: [model] });
    if (path.endsWith('/analytics')) return route.fulfill({ status: 503, json: { detail: '测试无统计' } });
    return route.fulfill({ json: [] });
  });
  await page.goto('/');
  await page.getByRole('navigation', { name: '管理控制台' }).getByRole('button', { name: '模型', exact: true }).click();
  await expect(page.getByText('默认：自动 · 按模式')).toBeVisible();
  await page.getByRole('button', { name: '编辑', exact: true }).click();
  let dialog = page.getByRole('dialog');
  await expect(dialog.getByLabel(/^模型允许上限 Token/)).toHaveValue('393216');
  await expect(dialog.getByLabel(/^默认输出额度 Token/)).toHaveValue('');
  await dialog.getByLabel(/^默认输出额度 Token/).fill('65536');
  await page.screenshot({ path: 'test-results/output-budgets-form.png', fullPage: true });
  await dialog.getByRole('button', { name: '保存映射' }).click();
  await expect(dialog).toHaveCount(0);
  expect(saved[0].max_output_tokens).toBe(393216);
  expect(saved[0].default_output_tokens).toBe(65536);
  await page.getByRole('button', { name: '编辑', exact: true }).click();
  dialog = page.getByRole('dialog');
  await expect(dialog.getByLabel(/^默认输出额度 Token/)).toHaveValue('65536');
  await dialog.getByLabel(/^默认输出额度 Token/).fill('');
  await dialog.getByRole('button', { name: '保存映射' }).click();
  await expect(dialog).toHaveCount(0);
  expect(saved[1].default_output_tokens).toBeNull();
  expect(saved[1].max_output_tokens).toBe(393216);
});
