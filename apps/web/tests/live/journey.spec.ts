import { expect, test } from "@playwright/test";

/**
 * Feature 005 (FR-011): one journey in the Spanish UI against the real services, with the stack's synthetic data.
 * Run only against the local compose stack (it uses the local demo sign-in). Set LIVE_SCREENSHOT_DIR to keep screenshots.
 */

const shot = async (page: import("@playwright/test").Page, name: string) => {
  if (process.env.LIVE_SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.LIVE_SCREENSHOT_DIR}/${name}.png`, fullPage: true });
};

test("a user signs in, sees the dashboard from the real API and reaches another screen, all in Spanish", async ({ page }) => {
  await page.goto("/panel");
  await expect(page.getByRole("heading", { level: 1, name: "Inicia sesión" })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", /^es/);
  await shot(page, "01-inicio-de-sesion");

  const overview = page.waitForResponse((r) => r.url().includes("/api/dashboard/overview") && r.request().method() === "GET");
  await page.getByRole("button", { name: "Entrar como Aprobador" }).click();
  expect((await overview).status()).toBe(200);

  const nav = page.getByRole("navigation", { name: "Menú principal de navegación" });
  await expect(nav).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: "Panel de control" })).toBeVisible();
  await shot(page, "02-panel-de-control");

  await nav.getByRole("link", { name: "Propuestas de compra" }).click();
  await expect(page).toHaveURL(/\/propuestas/);
  await expect(page.getByRole("heading", { level: 1, name: "Propuestas de compra" })).toBeVisible();
  await shot(page, "03-propuestas-de-compra");
});
