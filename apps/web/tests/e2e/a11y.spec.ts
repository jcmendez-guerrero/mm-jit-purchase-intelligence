import { expect, test } from "@playwright/test";

test.describe("Accessibility labels and keyboard navigation (T119)", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          user_id: "buyer-1",
          roles: ["viewer", "buyer"],
          mfa_auth_time: new Date().toISOString(),
          csrf_token: "mock-csrf-token",
        }),
      });
    });

    await page.route("**/api/dashboard/risk*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            variant_id: 101,
            risk_type: "stockout",
            explanation_key: "risk.stockout.imminent",
            params: { sku: "AMX-500" },
          },
        ]),
      });
    });
  });

  test("main navigation and tables have proper aria labels and headings", async ({ page }) => {
    await page.goto("/");

    // Check accessible landmark and headings
    await expect(page.locator("nav[aria-label='Menú principal de navegación']")).toBeVisible();
    await expect(page.locator("h1").first()).toBeVisible();
    await expect(page.locator("h2#dashboard-title")).toBeVisible();

    // Check risk table accessibility label
    await expect(page.locator("table[aria-label='Tabla de riesgos detectados']")).toBeVisible();
  });

  test("supports keyboard tab navigation across menu tabs", async ({ page }) => {
    await page.goto("/");

    // Tab through the navigation buttons
    await page.keyboard.press("Tab");
    // Ensure focus is on an interactive element
    const activeElement = await page.evaluate(() => document.activeElement?.tagName);
    expect(["BUTTON", "A", "SELECT", "INPUT"]).toContain(activeElement);
  });
});
