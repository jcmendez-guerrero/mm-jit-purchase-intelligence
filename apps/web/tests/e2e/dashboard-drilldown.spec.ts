import { expect, test } from "@playwright/test";
import { json, overview, signIn } from "./dashboard-mock";

/** T027 (US3): a figure opens the products behind it, with their total, sorting and paging; each product opens its own page by SKU, reachable by keyboard, and that page survives a reload. The services are simulated. */

const sku = (n: number) => `SYN-${String(n).padStart(3, "0")}`;
const row = (n: number) => ({ sku: sku(n), name: `Variante ${n}`, figure: "10.00" });
const SKU_PAGE = {
  sku: "SYN-001", name: "Variante 1", stock: { on_hand: 15 }, coverage: { days: "5.00", basis: "actual_90d" }, demand: { units: 84, days: 28 }, forecast: null, supplier: { id: "sup-a" },
  expiry_lots: [{ batch: "L1", quantity: 10, expiry_date: "2027-12-20", band: "later" }], states: [], cost: { value: "40.00", estimated: false, unit_cost: "2.00" },
};

test.describe("Dashboard drill-down", () => {
  let drills: URL[];

  test.beforeEach(async ({ page }) => {
    drills = [];
    await signIn(page);
    await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
    await page.route("**/api/dashboard/drilldown*", (r) => {
      const q = new URL(r.request().url()).searchParams;
      drills.push(new URL(r.request().url()));
      const offset = Number(q.get("offset") ?? 0);
      const start = q.get("sort") === "sku" && q.get("order") === "desc" ? 120 - offset : offset + 1;
      const step = q.get("sort") === "sku" && q.get("order") === "desc" ? -1 : 1;
      const rows = Array.from({ length: Math.min(50, 120 - offset) }, (_, i) => row(start + i * step));
      return r.fulfill(json({ kind: q.get("kind"), truncated: offset + rows.length < 120, total: 120, offset, sum: "1200.00", rows }));
    });
    await page.route("**/api/dashboard/skus/SYN-001", (r) => r.fulfill(json(SKU_PAGE)));
  });

  const open = async (page: import("@playwright/test").Page) => {
    await page.goto("/panel");
    await page.getByRole("heading", { name: "Valor del stock", exact: true }).locator("xpath=ancestor::article").getByRole("button", { name: "Ver productos" }).click();
    return page.getByRole("complementary", { name: "Productos que forman el valor del inventario" });
  };

  test("a card opens its products by SKU with the total of every row, not only the page", async ({ page }) => {
    const panel = await open(page);
    await expect(panel).toContainText("SYN-001");
    await expect(panel).toContainText("Total: 1.200,00");
    await expect(panel).toContainText("Mostrando 1–50 de 120 productos.");
    await expect(panel).not.toContainText("900001");                                       // no internal id
    expect(drills[0]!.searchParams.get("kind")).toBe("inventory_value");
  });

  test("sorting by SKU descending asks the server for the whole list in that order", async ({ page }) => {
    const panel = await open(page);
    await panel.locator("#drill-sort").selectOption("sku");
    await panel.getByRole("button", { name: /descendente|Descendente/ }).click();
    await expect.poll(() => drills.some((d) => d.searchParams.get("sort") === "sku" && d.searchParams.get("order") === "desc")).toBe(true);
    await expect(panel).toContainText("SYN-120");
  });

  test("the next page asks for the next 50 and the first page has no previous", async ({ page }) => {
    const panel = await open(page);
    await expect(panel.getByRole("button", { name: "Anterior" })).toBeDisabled();
    await panel.getByRole("button", { name: "Siguiente" }).click();
    await expect(panel).toContainText("Mostrando 51–100 de 120 productos.");
    expect(drills.some((d) => d.searchParams.get("offset") === "50")).toBe(true);
    await expect(panel).toContainText("SYN-051");
  });

  test("Escape closes the panel, and a product page opens by keyboard and survives a reload", async ({ page }) => {
    const panel = await open(page);
    await page.keyboard.press("Escape");
    await expect(panel).toHaveCount(0);
    const again = await open(page);
    const link = again.getByRole("link", { name: "Ver ficha" }).first();
    await link.focus();
    await expect(link).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/panel\/skus\/SYN-001$/);
    await expect(page.getByRole("heading", { name: "Ficha del producto SYN-001" })).toBeVisible();
    await page.reload();                                                                    // the page has its own address: a reload or a shared link shows the same product
    await expect(page.getByRole("heading", { name: "Ficha del producto SYN-001" })).toBeVisible();
    await expect(page.getByText("Existencias totales: 15")).toBeVisible();
  });
});
