import { test, expect, type Page } from "@playwright/test";

const user = {
  id: "u1",
  email: "preview@example.com",
  display_name: "林间工作室",
  role: "user",
  must_change_password: false,
  active: true,
  monthly_token_limit: 20000000,
  rpm_limit: 60,
  tpm_limit: 100000,
  allowed_models: ["gpt-6.1-sol-high", "deepseek-flash"],
  created_at: "2026-11-01T00:00:00Z",
};
const models = ["gpt-6.1-sol-high", "deepseek-flash"].map((name, i) => ({
  id: `m${i}`,
  public_name: name,
  upstream_model: name,
  provider_id: "p1",
  max_output_tokens: 4096,
  tokenizer: "cl100k_base",
  api_mode: "both",
  reasoning_effort: i ? null : "high",
  active: true,
}));
const daily = Array.from({ length: 6 }, (_, i) => ({
  date: `2026-11-0${i + 1}`,
  input_tokens: [1100000, 620000, 890000, 430000, 1250000, 680000][i],
  output_tokens: [400000, 240000, 380000, 160000, 460000, 320000][i],
  total_tokens: 0,
  requests: 26 + i * 13,
  successes: 25 + i * 13,
  failures: 1,
  avg_latency_ms: 2800,
})).map((d) => ({ ...d, total_tokens: d.input_tokens + d.output_tokens }));
const total = daily.reduce((s, d) => s + d.total_tokens, 0);
async function seed(page: Page, role: "admin" | "user" | "guest") {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = {};
    if (path === "/api/auth/session") {
      if (role === "guest")
        return route.fulfill({ status: 401, json: { detail: "未登录" } });
      body = { user: { ...user, role }, csrf_token: "fixture-csrf" };
    } else if (path.endsWith("/analytics"))
      body = {
        period: new URL(route.request().url()).searchParams.get("period"),
        start: "2026-10-31T16:00:00Z",
        end: "2026-11-06T08:00:00Z",
        timezone: "Asia/Shanghai",
        summary: {
          requests: 351,
          input_tokens: 4970000,
          output_tokens: 1960000,
          total_tokens: total,
          successes: 345,
          failures: 6,
          success_rate: 98.29,
          avg_latency_ms: 2800,
        },
        daily,
        models: [
          {
            id: "m1",
            label: "gpt-6.1-sol-high",
            total_tokens: total * 0.7,
            requests: 260,
          },
          {
            id: "m2",
            label: "deepseek-flash",
            total_tokens: total * 0.3,
            requests: 91,
          },
        ],
        users: [
          {
            id: "u1",
            label: "林间工作室",
            total_tokens: total * 0.6,
            requests: 211,
          },
          {
            id: "u2",
            label: "松果实验室",
            total_tokens: total * 0.4,
            requests: 140,
          },
        ],
      };
    else if (path.endsWith("/dashboard"))
      body = {
        period_days: 30,
        requests: 351,
        tokens: total,
        success_rate: 98.29,
        avg_latency_ms: 2800,
        users: 2,
        providers: 1,
        models: 2,
      };
    else if (path.endsWith("/usage"))
      body = {
        month: "2026-11",
        used_tokens: total,
        remaining_tokens: 20000000 - total,
        monthly_token_limit: 20000000,
        request_count: 351,
        input_tokens: 4970000,
        output_tokens: 1960000,
        daily: daily.map((d) => ({
          date: d.date.slice(5),
          tokens: d.total_tokens,
        })),
      };
    else if (path.endsWith("/models")) body = models;
    else if (path.endsWith("/users")) body = [user];
    else if (path.endsWith("/providers"))
      body = [
        {
          id: "p1",
          name: "主力模型上游",
          base_url: "https://provider.example.com/v1",
          key_last4: "test",
          timeout_seconds: 120,
          supports_stream_usage: true,
          active: true,
        },
      ];
    else if (path.endsWith("/logs"))
      body = [
        {
          request_id: "req_fixture_preview_not_real",
          user_id: "u1",
          access_key_id: "k1",
          model_alias: "gpt-6.1-sol-high",
          total_tokens: 14500,
          input_tokens: 10000,
          output_tokens: 4500,
          status_code: 200,
          latency_ms: 2800,
          created_at: "2026-11-06T07:22:00Z",
        },
      ];
    else if (path.endsWith("/keys"))
      body = [
        {
          id: "k1",
          name: "工作电脑",
          prefix: "preview",
          last4: "demo",
          rpm_limit: 60,
          tpm_limit: 100000,
          active: true,
          created_at: "2026-11-01T00:00:00Z",
          last_used_at: "2026-11-06T07:22:00Z",
        },
      ];
    else if (path.endsWith("/audit")) body = [];
    await route.fulfill({ json: body });
  });
}
async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
}
async function screenshot(page: Page, name: string) {
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: `../artifacts/${name}.png`, fullPage: true });
}
for (const width of [1440, 1280, 1024])
  test(`desktop administrator ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await seed(page, "admin");
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "站点用量手账" }),
    ).toBeVisible();
    await expect(page.getByText("6.93 M").first()).toBeVisible();
    await noOverflow(page);
    await screenshot(page, `admin-${width}`);
    for (const label of ["上游", "模型", "用户", "调用日志", "审计日志"]) {
      await page
        .getByRole("navigation")
        .getByRole("button", { name: label, exact: true })
        .click();
      await expect(
        page.getByRole("heading", { name: label, exact: true, level: 1 }),
      ).toBeVisible();
      await noOverflow(page);
    }
  });
test("user pages and Codex guide", async ({ page }) => {
  await seed(page, "user");
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "用量手账", exact: true }),
  ).toBeVisible();
  await screenshot(page, "user-1440");
  await noOverflow(page);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "访问 Key", exact: true })
    .click();
  await screenshot(page, "keys-1440");
  await noOverflow(page);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "接入指南", exact: true })
    .click();
  await page.getByRole("button", { name: "CC Switch + Codex" }).click();
  await expect(
    page.getByRole("heading", { name: "在 CC Switch 添加本站" }),
  ).toBeVisible();
  await screenshot(page, "guide-1440");
  await noOverflow(page);
});
test("guest and login", async ({ page }) => {
  await seed(page, "guest");
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "登录", exact: true }),
  ).toBeVisible();
  await screenshot(page, "guest-1440");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await screenshot(page, "login-1440");
});

test("long names and zero quota remain usable in a narrow desktop window", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 900 });
  await seed(page, "user");
  const longName = "gpt-6.1-sol-high-" + "long-model-alias-".repeat(6);
  await page.route("**/api/me/models", (route) =>
    route.fulfill({ json: [{ ...models[0], public_name: longName }] }),
  );
  await page.route("**/api/auth/session", (route) =>
    route.fulfill({
      json: {
        user: {
          ...user,
          email: "a".repeat(64) + "@" + "company.".repeat(8) + "example.com",
        },
        csrf_token: "fixture",
      },
    }),
  );
  await page.route("**/api/me/usage", (route) =>
    route.fulfill({
      json: {
        month: "2026-11",
        used_tokens: 0,
        remaining_tokens: 0,
        monthly_token_limit: 0,
        request_count: 0,
        input_tokens: 0,
        output_tokens: 0,
        daily: [],
      },
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "本月用量" })).toBeVisible();
  await expect(page.getByText("0.0% / 0 M")).toBeVisible();
  await noOverflow(page);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "接入指南", exact: true })
    .click();
  await page.getByRole("button", { name: "CC Switch + Codex" }).click();
  await expect(
    page.getByRole("heading", { name: "在 CC Switch 添加本站" }),
  ).toBeVisible();
  await noOverflow(page);
  await screenshot(page, "guide-long-1024");
});

test("an admin resource failure does not suppress independent analytics", async ({
  page,
}) => {
  await seed(page, "admin");
  await page.route("**/api/admin/users", (route) =>
    route.fulfill({
      status: 500,
      json: { detail: "测试：用户列表暂时不可用" },
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("用户列表暂时不可用");
  await expect(page.getByText("6.93 M").first()).toBeVisible();
  await page.getByRole("button", { name: "刷新", exact: true }).click();
  await expect(page.getByText("6.93 M").first()).toBeVisible();
  await noOverflow(page);
});
