import { expect, test } from "@playwright/test";

const line = {
  id: "line-1", variant_id: 101, sku: "AMX-500", product_name: "Amoxicilina", supplier_id: "supp-1", supplier_name: "Farmax", qty: 10,
  unit_cost_with_recargo: "5.2600", line_total: "52.6000", risk: "low", confidence: "high", manual_override: false, topup: false, constraints_applied: [],
  explanation: {
    policy: "forecast", forecast_eligible: true, service_level: "95", horizon_days: 14, expected_demand: 8, safety_stock: 2, order_up_to: 12, reorder_point: 5, need: 10, top_up: false,
    clinical_critical: false, position: { on_hand: 0, expiring: 0, usable: 0, inbound: 0, total: 0 }, supplier: { chosen: "supp-1", reason: "lowest_cost", alternatives: [], rejected: [] },
    cost: { unit: "5.2600", source: "manual", status: "ok" }, constraints: [],
  },
};

async function mockProposal(page: import("@playwright/test").Page, status: string) {
  const summary = { id: "prop-12345678", week: "2026-W45", status, version: 3, created_by: "buyer-1", updated_at: "2026-11-04T10:00:00Z" };
  const detail = { ...summary, last_edited_by: null, terms_version_ids: null, approval: null, supplier_groups: [], lines: status === "draft" ? [line] : [] };
  await page.route("**/api/proposals", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([summary]) }));
  await page.route("**/api/proposals/prop-12345678", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(detail) }));
}

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

    await mockProposal(page, "draft");
  });

  test("viewer has read-only access and cannot edit or approve proposals", async ({ page }) => {
    await page.goto("/");
    // Navigate to proposals
    await page.getByRole("navigation").getByRole("link", { name: "Propuestas de compra", exact: true }).click();

    // Viewer should see the proposal table
    await expect(page.locator("text=Amoxicilina")).toBeVisible();

    // Viewer should NOT see edit or approve buttons
    await expect(page.getByLabel("Cantidad para Amoxicilina")).toHaveCount(0);
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
    await page.getByRole("navigation").getByRole("link", { name: "Propuestas de compra", exact: true }).click();

    await expect(page.getByLabel("Cantidad para Amoxicilina")).toBeVisible();
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

    await mockProposal(page, "submitted");

    await page.goto("/");
    await page.getByRole("navigation").getByRole("link", { name: "Propuestas de compra", exact: true }).click();

    await expect(page.locator("button:has-text('Aprobar propuesta')")).toBeVisible();
    // Approver cannot edit
    await expect(page.getByLabel(/Cantidad para/)).toHaveCount(0);
  });

  test("admin can see user roles management in the administration area", async ({ page }) => {
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
          users: [{ user_id: "buyer-1", roles: ["viewer", "buyer"], active: true, revision: 1 }],
          eligible_approvers_count: 2,
          valid_roles: ["viewer", "buyer", "approver", "admin"],
        }),
      });
    });

    await page.route("**/api/admin/roles/mirror", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ pending: 0, failed: 0, sent: 1, oldest_pending_seconds: 0, items: [] }) });
    });

    await page.goto("/");
    await page.getByRole("navigation").getByRole("link", { name: "Administración", exact: true }).click();

    await expect(page.locator("text=Usuarios y roles")).toBeVisible();
    await expect(page.locator("text=buyer-1")).toBeVisible();
  });
});
