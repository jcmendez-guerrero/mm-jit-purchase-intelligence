import { expect, test } from "@playwright/test";
import { json, overview, signIn } from "./dashboard-mock";

/** T030 (US2): filter chips, removing one, clearing all, and restoring the filters from the address. The services are simulated; only the requests the screen makes are checked. */

test.describe("Dashboard filters", () => {
  let calls: URL[];

  test.beforeEach(async ({ page }) => {
    calls = [];
    await signIn(page);
    await page.route("**/api/dashboard/overview*", (r) => {
      calls.push(new URL(r.request().url()));
      return r.fulfill(json(overview()));
    });
  });

  const last = () => calls[calls.length - 1]!.searchParams;
  const chips = (page: import("@playwright/test").Page) => page.getByRole("list", { name: "Filtros" });

  test("choosing a filter shows its chip, asks for the filtered figures and writes it to the address", async ({ page }) => {
    await page.goto("/panel");
    await expect(chips(page)).toHaveCount(0);
    await page.getByLabel("Categoría").selectOption("A");
    await expect(chips(page).getByRole("listitem")).toHaveCount(1);
    await expect.poll(() => last().get("category")).toBe("A");
    expect(new URL(page.url()).searchParams.get("categoria")).toBe("A");
  });

  test("removing one chip drops only that filter", async ({ page }) => {
    await page.goto("/panel?categoria=A&proveedor=s1");
    await expect(chips(page).getByRole("listitem")).toHaveCount(2);
    await chips(page).getByRole("listitem").first().getByRole("button").click();
    await expect(chips(page).getByRole("listitem")).toHaveCount(1);
    await expect.poll(() => [last().get("category"), last().get("supplier_id")]).toEqual([null, "s1"]);
    expect(new URL(page.url()).searchParams.get("categoria")).toBeNull();
  });

  test("clearing removes every filter, chips and address parameters", async ({ page }) => {
    await page.goto("/panel?categoria=A&proveedor=s1&desde=2026-10-01&hasta=2026-10-10");
    await page.getByRole("button", { name: "Quitar filtros" }).click();
    await expect(chips(page)).toHaveCount(0);
    await expect.poll(() => [last().get("category"), last().get("supplier_id"), last().get("date_from")]).toEqual([null, null, null]);
    expect(new URL(page.url()).search).toBe("");
  });

  test("a shared link restores the filters in the controls, the chips and the request", async ({ page }) => {
    await page.goto("/panel?categoria=A&proveedor=s1&desde=2026-10-01&hasta=2026-10-10");
    await expect(page.getByLabel("Categoría")).toHaveValue("A");
    await expect(page.getByLabel("Proveedor")).toHaveValue("s1");
    await expect(page.getByLabel("Desde")).toHaveValue("2026-10-01");
    await expect(page.getByLabel("Hasta")).toHaveValue("2026-10-10");
    await expect(chips(page).getByRole("listitem")).toHaveCount(4);
    await expect.poll(() => Object.fromEntries(["category", "supplier_id", "date_from", "date_to"].map((k) => [k, last().get(k)]))).toEqual({ category: "A", supplier_id: "s1", date_from: "2026-10-01", date_to: "2026-10-10" });
  });

  test("an invalid value in the link is ignored and the user is told", async ({ page }) => {
    await page.goto("/panel?categoria=Z");
    await expect(page.getByText(/Se han ignorado filtros no válidos/)).toBeVisible();
    await expect(chips(page)).toHaveCount(0);
  });

  /** T103 (FR-025, FR-026): the capital card without a total still lists both parts, and the budget card lists the proposed spend and the spend as separate parts. */
  test("the capital card shows no total but both parts under a filter, and the budget lists proposed spend and spend apart", async ({ page }) => {
    const part = (key: string, value: string) => ({ key, label_key: `dashboard.part.${key}`, value });
    const base = overview().indicators as Array<Record<string, unknown>>;
    const withParts = base.map((i) =>
      i.key === "capital_tied_up"
        ? { ...i, value: null, state: "no_data", filters_unsupported: ["category"], parts: [part("stock_at_cost", "40.00"), part("open_orders", "30.00")] }
        : i.key === "purchasing_budget"
          ? { ...i, parts: [part("proposed", "50.50"), part("spend", "90.00")] }
          : i);
    await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview(1, { indicators: withParts }))));
    await page.goto("/panel?categoria=A");
    const capital = page.getByRole("article").filter({ hasText: "Capital inmovilizado" });
    await expect(capital.getByText("Sin datos")).toBeVisible();
    await expect(capital.getByRole("list", { name: "Composición" }).getByRole("listitem")).toHaveCount(2);
    await expect(capital.getByText(/No aplica a: Categoría/)).toBeVisible();
    const budget = page.getByRole("article").filter({ hasText: "Presupuesto de compras" }).getByRole("list", { name: "Composición" });
    await expect(budget.getByText(/Gasto propuesto \(pedido sin confirmar\): 50,50/)).toBeVisible();
    await expect(budget.getByText(/Gasto \(pedidos confirmados\): 90,00/)).toBeVisible();
  });
});
