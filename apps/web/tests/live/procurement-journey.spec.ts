import { expect, test, type Page } from "@playwright/test";

/**
 * Feature 011 (FR-010, FR-015): proposals and scenarios against the real services, in Spanish, with the stack's synthetic data.
 * Run only against the local compose stack (it uses the local demo sign-in):
 *   PLAYWRIGHT_BASE_URL=http://localhost:8080 npx playwright test --config playwright.live.config.ts procurement-journey
 * The stack has no forecast service and the gateway has no proposal-generation route, so generation, approval and the file contents
 * are covered by the service tests; this journey proves the screens and the role gate on the real gateway.
 */

const signInAs = async (page: Page, role: "Lector" | "Comprador" | "Aprobador" | "Administrador") => {
  await page.goto("/panel");
  await page.getByRole("button", { name: `Entrar como ${role}` }).click();
  await expect(page.getByRole("navigation", { name: "Menú principal de navegación" })).toBeVisible();
};

test("a viewer reads the proposals and scenarios screens in Spanish and the real gateway refuses the export", async ({ page }) => {
  await signInAs(page, "Lector");
  await expect(page.locator("html")).toHaveAttribute("lang", /^es/);
  const nav = page.getByRole("navigation", { name: "Menú principal de navegación" });

  await nav.getByRole("link", { name: "Propuestas de compra" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Propuestas de compra" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Exportar/ })).toHaveCount(0);

  await nav.getByRole("link", { name: "Escenarios" }).click();
  await expect(page.getByRole("heading", { name: "Escenarios de compra" }).first()).toBeVisible();

  const proposal = await page.request.get("/api/proposals/does-not-exist/export?format=csv");
  expect(proposal.status()).toBe(403);
  expect((await proposal.json()).detail).toBe("auth_forbidden_role");
  const scenario = await page.request.get("/api/scenarios/does-not-exist/export?format=xlsx");
  expect(scenario.status()).toBe(403);
  expect((await scenario.json()).detail).toBe("auth_forbidden_role");
});

test("a buyer passes the role gate: the export of an unknown proposal is a not-found or state answer, never a permission refusal", async ({ page }) => {
  await signInAs(page, "Comprador");
  const res = await page.request.get("/api/proposals/does-not-exist/export?format=csv");
  expect([404, 409]).toContain(res.status());
  const approver = await page.request.get("/api/scenarios/does-not-exist/export?format=csv");
  expect([404, 409]).toContain(approver.status());
});
