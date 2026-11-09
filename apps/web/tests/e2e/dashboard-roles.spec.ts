import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { json, overview, signIn } from "./dashboard-mock";

/** FR-017: a viewer sees counts and a role message on the dashboard, never an amount. Responses are simulated as the services send them to a viewer. */

const AMOUNT = /\d[\d.]*,\d{2}\s?€/;
const HIDDEN = "No disponible para tu rol";

test.describe("Dashboard for a viewer", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page, ["viewer"]);
    const base = overview();
    const summary: Record<string, unknown> = { ...base.summary.data };
    delete summary.inventory_value;
    delete summary.expiring_value;
    summary.hidden_by_role = ["inventory_value", "expiring_value"];
    await page.route("**/api/dashboard/overview*", (r) =>
      r.fulfill(json({
        ...base,
        summary: { ok: true, data: summary },
        abc_xyz: { ok: true, data: { cells: [{ abc: "A", xyz: "X", variant_count: 4 }, { abc: "B", xyz: "Y", variant_count: 6 }] } },
        spend: { ok: false, error: "hidden_by_role" },
      })));
    await page.route("**/api/dashboard/drilldown*", (r) =>
      r.fulfill(json({ kind: "inventory_value", truncated: false, total: 1, offset: 0, sum: null, rows: [{ variant_id: 100, sku: "SYN-100", name: "Variante sintética", figure: null }] })));
  });

  test("shows the role message instead of amounts and keeps the counts", async ({ page }) => {
    await page.goto("/");
    for (const card of ["Valor del inventario", "Valor que caduca en 60 días", "Gasto propuesto"]) {
      await expect(page.getByLabel(card, { exact: true })).toContainText(HIDDEN);
    }
    await expect(page.getByLabel("Variantes con riesgo de rotura")).toContainText("3");
    await expect(page.getByLabel("Cobertura media")).toContainText("5,8 días");
    expect(await page.locator("body").innerText()).not.toMatch(AMOUNT);
  });

  test("the products behind a money figure are listed by SKU without amounts", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Valor del inventario").getByRole("button", { name: "Ver productos" }).click();
    const panel = page.getByRole("complementary", { name: "Productos que forman el valor del inventario" });
    await expect(panel).toContainText("SYN-100 · Variante sintética");
    await expect(panel).not.toContainText("#100");
    expect(await panel.innerText()).not.toMatch(AMOUNT);
  });

  test("has no serious or critical accessibility violations", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByLabel("Valor del inventario")).toContainText(HIDDEN);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
    const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
  });
});
