import { expect, test } from "@playwright/test";

test.describe("Role matrix UI permissions (T106)", () => {
  test.beforeEach(async ({ page }) => {
    // Mock the /api/me and /api/proposals endpoints
    await page.route("**/api/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          user_id: "viewer-1",
          roles: ["viewer"],
          mfa_auth_time: new Date().toISOString(),
          csrf_token: "mock-csrf-token",
        }),
      });
    });

    await page.route("**/api/dashboard/risk*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.route("**/api/proposals", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "prop-12345678",
            cycle_date: "2026-11-04",
            status: "draft",
            total_net: "1000.00",
            total_with_recargo: "1052.00",
            creator: "buyer-1",
            lines: [
              {
                id: "line-1",
                variant_id: 101,
                sku: "AMX-500",
                product_name: "Amoxicilina",
                supplier_id: "supp-1",
                supplier_name: "Farmax",
                warehouse_id: 1,
                order_qty: 10,
                unit_cost_net: "5.00",
                unit_cost_recargo: "5.26",
                line_total: "52.60",
                explanation: "Rotura de stock",
              },
            ],
          },
        ]),
      });
    });
  });

  test("viewer has read-only access and cannot edit or approve proposals", async ({ page }) => {
    await page.goto("/");
    // Navigate to proposals
    await page.click("button:has-text('Propuestas de compra')");

    // Viewer should see the proposal table
    await expect(page.locator("text=Propuesta #prop-123")).toBeVisible();

    // Viewer should NOT see edit or approve buttons
    await expect(page.locator("button:has-text('Modificar cantidad')")).not.toBeVisible();
    await expect(page.locator("button:has-text('Aprobar propuesta')")).not.toBeVisible();
    await expect(page.locator("button:has-text('Enviar a aprobación')")).not.toBeVisible();
  });

  test("buyer can see edit and submit buttons for draft proposals", async ({ page }) => {
    // Override /api/me to return buyer role
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

    await page.goto("/");
    await page.click("button:has-text('Propuestas de compra')");

    await expect(page.locator("button:has-text('Modificar cantidad')")).toBeVisible();
    await expect(page.locator("button:has-text('Enviar a aprobación')")).toBeVisible();
    // Buyer cannot approve
    await expect(page.locator("button:has-text('Aprobar propuesta')")).not.toBeVisible();
  });

  test("approver can see approve button for submitted proposals", async ({ page }) => {
    await page.route("**/api/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          user_id: "approver-1",
          roles: ["viewer", "approver"],
          mfa_auth_time: new Date().toISOString(),
          csrf_token: "mock-csrf-token",
        }),
      });
    });

    await page.route("**/api/proposals", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "prop-12345678",
            cycle_date: "2026-11-04",
            status: "submitted",
            total_net: "1000.00",
            total_with_recargo: "1052.00",
            creator: "buyer-1",
            lines: [],
          },
        ]),
      });
    });

    await page.goto("/");
    await page.click("button:has-text('Propuestas de compra')");

    await expect(page.locator("button:has-text('Aprobar propuesta')")).toBeVisible();
    // Approver cannot edit
    await expect(page.locator("button:has-text('Modificar cantidad')")).not.toBeVisible();
  });

  test("admin can see user roles management in config", async ({ page }) => {
    await page.route("**/api/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          user_id: "admin-1",
          roles: ["viewer", "admin"],
          mfa_auth_time: new Date().toISOString(),
          csrf_token: "mock-csrf-token",
        }),
      });
    });

    await page.route("**/api/config/service-levels", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ history: [] }),
      });
    });

    await page.route("**/api/admin/roles", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          users: [{ user_id: "buyer-1", roles: ["viewer", "buyer"] }],
          eligible_approvers_count: 2,
        }),
      });
    });

    await page.goto("/");
    await page.click("button:has-text('Configuración')");

    await expect(page.locator("text=Gestión de roles y accesos (Administrador)")).toBeVisible();
    await expect(page.locator("text=buyer-1")).toBeVisible();
  });
});
