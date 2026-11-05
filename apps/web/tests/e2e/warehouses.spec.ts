import { expect, test } from "@playwright/test";

test.describe("Warehouse breakdown and company-wide views (T108)", () => {
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
  });

  test("buyer can switch between company-wide view and specific warehouses", async ({ page }) => {
    let requestedWarehouseId: string | null = null;

    await page.route("**/api/dashboard/risk*", async (route) => {
      const url = new URL(route.request().url());
      requestedWarehouseId = url.searchParams.get("warehouse_id");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            variant_id: 101,
            risk_type: "stockout",
            explanation_key: "risk.stockout.imminent",
            params: { sku: "AMX-500", available: 2 },
          },
        ]),
      });
    });

    await page.goto("/");

    // Default selection is company-wide (all warehouses)
    const select = page.locator("#warehouse-select");
    await expect(select).toBeVisible();
    await expect(select).toHaveValue("all");
    expect(requestedWarehouseId).toBeNull();

    // Switch to Warehouse 1
    await select.selectOption("1");
    await expect(select).toHaveValue("1");
    expect(requestedWarehouseId).toBe("1");

    // Switch to Warehouse 2
    await select.selectOption("2");
    await expect(select).toHaveValue("2");
    expect(requestedWarehouseId).toBe("2");

    // Switch to Unassigned (Warehouse 0)
    await select.selectOption("0");
    await expect(select).toHaveValue("0");
    expect(requestedWarehouseId).toBe("0");
  });
});
