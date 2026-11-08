import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { json, overview } from "./dashboard-mock";

/** Sign-in page: shown without a session; role chooser locally, Microsoft in Azure. Mocked backend, synthetic data. */

const unauthenticated = (page: import("@playwright/test").Page) =>
  page.route("**/api/me", (r) => r.fulfill(json({ detail: "unauthenticated" }, 401)));

test("without a session the role chooser signs in and opens the app (local)", async ({ page }) => {
  await unauthenticated(page);
  await page.route("**/api/auth/config", (r) => r.fulfill(json({ mode: "dev" })));
  await page.route("**/api/auth/dev-login", async (r) => {
    await page.unroute("**/api/me");
    await page.route("**/api/me", (m) => m.fulfill(json({ user_id: "approver-1", roles: ["viewer", "approver"], mfa_auth_time: new Date().toISOString(), csrf_token: "t" })));
    await r.fulfill(json({ user_id: "approver-1", roles: ["viewer", "approver"], mfa_auth_time: new Date().toISOString(), csrf_token: "t" }));
  });
  await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
  await page.goto("/panel");
  await expect(page.getByRole("heading", { level: 1, name: "Inicia sesión" })).toBeVisible();
  await expect(page.getByRole("navigation")).toHaveCount(0);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id)).toEqual([]);
  await page.getByRole("button", { name: "Entrar como Aprobador" }).click();
  await expect(page.getByText("approver-1")).toBeVisible();
});

test("in Azure the page offers Microsoft sign-in only", async ({ page }) => {
  await unauthenticated(page);
  await page.route("**/api/auth/config", (r) => r.fulfill(json({ mode: "entra" })));
  await page.goto("/?login_error=denied");
  await expect(page.getByRole("link", { name: "Iniciar sesión con Microsoft" })).toHaveAttribute("href", "/api/auth/login");
  await expect(page.getByRole("button", { name: /Entrar como/ })).toHaveCount(0);
  await expect(page.getByRole("alert")).toContainText("No se completó el inicio de sesión");
});
