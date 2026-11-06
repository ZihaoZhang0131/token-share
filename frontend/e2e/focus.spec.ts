import { expect, test, type Page } from "@playwright/test";

const user = {
  id: "test-admin", email: "admin@example.com", display_name: "测试管理员", role: "admin",
  must_change_password: false, active: true, monthly_token_limit: 1000000,
  rpm_limit: 60, tpm_limit: 100000, allowed_models: [], created_at: "2026-11-01T00:00:00Z",
};
const summary = {
  requests: 0, input_tokens: 0, output_tokens: 0, total_tokens: 0,
  successes: 0, failures: 0, success_rate: null, avg_latency_ms: null,
};
const analytics = {
  period: "month", start: "2026-10-31T16:00:00Z", end: "2026-11-06T07:00:00Z",
  timezone: "Asia/Shanghai", summary, daily: [], models: [], users: [],
};

async function mockApi(page: Page, identity: typeof user | null = null) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/auth/session") {
      await route.fulfill(identity
        ? { status: 200, json: { user: identity, csrf_token: "test-csrf" } }
        : { status: 401, json: { detail: "未登录" } });
    } else if (path === "/api/auth/login") {
      await route.fulfill({ status: 401, json: { detail: "邮箱或密码错误" } });
    } else if (path === "/api/admin/dashboard") {
      await route.fulfill({ json: { period_days: 30, requests: 0, tokens: 0, success_rate: 100, avg_latency_ms: 0, users: 0, providers: 0, models: 0 } });
    } else if (path.endsWith("/analytics")) {
      await route.fulfill({ json: analytics });
    } else {
      await route.fulfill({ json: [] });
    }
  });
}

async function openLogin(page: Page) {
  await mockApi(page);
  await page.goto("/");
  const opener = page.getByRole("button", { name: "登录", exact: true });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "登录控制台" });
  await expect(dialog).toBeVisible();
  return { opener, dialog };
}

test("login password keeps focus during sequential input and paste", async ({ page }) => {
  const { dialog } = await openLogin(page);
  const email = dialog.getByLabel("邮箱", { exact: true });
  const password = dialog.getByLabel("密码", { exact: true });
  await expect(email).toBeFocused();
  await email.fill("tester@example.com");
  await password.click();
  await password.pressSequentially("Secret!123456", { delay: 25 });
  await expect(password).toBeFocused();
  await expect(password).toHaveValue("Secret!123456");
  await expect(email).toHaveValue("tester@example.com");
  await page.keyboard.insertText("-pasted-value");
  await expect(password).toBeFocused();
  await expect(password).toHaveValue("Secret!123456-pasted-value");
});

test("login traps Tab in both directions and Escape restores the opener", async ({ page }) => {
  const { dialog } = await openLogin(page);
  const close = dialog.getByRole("button", { name: "关闭", exact: true });
  const submit = dialog.getByRole("button", { name: "登录", exact: true });
  await close.focus();
  await page.keyboard.press("Shift+Tab");
  await expect(submit).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(close).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(dialog.getByLabel("邮箱", { exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("button", { name: "登录", exact: true })).toBeFocused();
});

test("a rejected login allows editing the password without jumping to the email", async ({ page }) => {
  const { dialog } = await openLogin(page);
  await dialog.getByLabel("邮箱", { exact: true }).fill("tester@example.com");
  const password = dialog.getByLabel("密码", { exact: true });
  await password.fill("WrongPassword!123");
  await dialog.getByRole("button", { name: "登录", exact: true }).click();
  await expect(dialog.getByRole("alert")).toHaveText("邮箱或密码错误");
  await password.click();
  await password.press("End");
  await password.pressSequentially("Fixed", { delay: 25 });
  await expect(password).toBeFocused();
  await expect(password).toHaveValue("WrongPassword!123Fixed");
});

test("the initial-password gate preserves focus through validation and correction", async ({ page }) => {
  await mockApi(page, { ...user, must_change_password: true });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "请先设置新密码" })).toBeVisible();
  await page.getByLabel("当前临时密码", { exact: true }).fill("Temporary!123");
  await page.getByLabel("新密码", { exact: true }).fill("NewPassword!123");
  const confirm = page.getByLabel("确认新密码", { exact: true });
  await confirm.fill("NewPassword!12");
  await page.getByRole("button", { name: "保存并进入控制台" }).click();
  await expect(page.getByRole("alert")).toHaveText("两次输入的新密码不一致");
  await confirm.click();
  await confirm.press("End");
  await page.keyboard.insertText("3");
  await expect(confirm).toBeFocused();
  await expect(confirm).toHaveValue("NewPassword!123");
});

test("administrator modal retains focus in later form fields and returns to its trigger", async ({ page }) => {
  await mockApi(page, user);
  await page.goto("/");
  await page.getByRole("navigation", { name: "管理控制台" }).getByRole("button", { name: "用户", exact: true }).click();
  const opener = page.getByRole("button", { name: "新增用户", exact: true });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "新增用户", exact: true });
  await expect(dialog.getByLabel("显示名称", { exact: true })).toBeFocused();
  await dialog.getByLabel("显示名称", { exact: true }).fill("新用户");
  await dialog.getByLabel("邮箱", { exact: true }).fill("new@example.com");
  const password = dialog.getByLabel(/^临时密码/);
  await password.click();
  await password.pressSequentially("InitialPassword!123", { delay: 25 });
  await expect(password).toBeFocused();
  await expect(password).toHaveValue("InitialPassword!123");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
});
