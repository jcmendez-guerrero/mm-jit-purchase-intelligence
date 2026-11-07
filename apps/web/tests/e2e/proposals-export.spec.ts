import { expect, test } from "@playwright/test";
import { json, overview, signIn } from "./dashboard-mock";

/** T180 (FR-032): a proposal offers a CSV and an Excel download. */

test("a proposal offers a CSV and an Excel download", async ({ page }) => {
  await signIn(page);
  const summary = { id: "prop-12345678", week: "2026-W45", status: "draft", version: 3, created_by: "buyer-1", updated_at: "2026-11-04T10:00:00Z" };
  await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
  await page.route("**/api/proposals", (r) => r.fulfill(json([summary])));
  await page.route("**/api/proposals/prop-12345678", (r) => r.fulfill(json({ ...summary, last_edited_by: null, terms_version_ids: null, approval: null, supplier_groups: [], lines: [] })));
  await page.goto("/");
  await page.click("button:has-text('Propuestas de compra')");
  // A link with the download attribute is handled by the browser's download manager, which Playwright can neither stub nor observe as a request;
  // so the links are checked here, and the file content by the service tests for the proposal export (CSV and Excel, es-ES).
  for (const [label, fmt] of [["Exportar CSV (formato es-ES)", "csv"], ["Exportar Excel", "xlsx"]] as const) {
    const link = page.getByRole("link", { name: label });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", `/api/proposals/prop-12345678/export?format=${fmt}`);
    await expect(link).toHaveAttribute("download", "");
  }
});
