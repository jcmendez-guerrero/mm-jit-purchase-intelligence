import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { charts, json, overview, signIn } from "./dashboard-mock";

/** T035 (US4): the analytical charts are reachable and usable by keyboard: toggle to the table, read the same rows, open the products of an expiry band. The services are simulated. */

test.describe("Dashboard charts", () => {
  let calls: URL[];
  let drills: URL[];

  test.beforeEach(async ({ page }) => {
    calls = [];
    drills = [];
    await signIn(page);
    await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
    await page.route("**/api/dashboard/charts*", (r) => {
      calls.push(new URL(r.request().url()));
      return r.fulfill(json(charts()));
    });
    await page.route("**/api/dashboard/drilldown*", (r) => {
      drills.push(new URL(r.request().url()));
      return r.fulfill(json({ kind: "expiry_band", truncated: false, total: 0, offset: 0, sum: "20.00", rows: [] }));
    });
  });

  test("shows the four analytical charts besides the two existing ones, each with a title", async ({ page }) => {
    await page.goto("/panel");
    for (const name of ["Valor que caduca por tramo", "Productos por días de cobertura", "Capital en stock por grupo ABC", "Evolución del inventario valorado"]) {
      await expect(page.getByRole("heading", { name })).toBeVisible();
    }
    await expect(page.getByRole("heading", { name: "Demanda diaria real y previsión" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Variantes por grupo ABC/XYZ" })).toBeVisible();
  });

  test("the table toggle is reached with the keyboard and shows the same rows as the chart data", async ({ page }) => {
    await page.goto("/panel");
    const figure = page.getByRole("figure", { name: "Valor que caduca por tramo" });
    const toggle = figure.getByRole("button", { name: "Ver como tabla" });
    await toggle.focus();
    await expect(toggle).toBeFocused();
    await page.keyboard.press("Enter");
    const table = figure.getByRole("table", { name: "Valor que caduca por tramo" });
    await expect(table.getByRole("row")).toHaveCount(4);                       // header and the three bands
    await expect(table).toContainText("0 a 30 días");
    await expect(table).toContainText("40,00");
    await page.keyboard.press("Enter");
    await expect(figure.getByRole("table")).toHaveCount(0);                    // back to the chart
  });

  test("opens the products of an expiry band from the table by keyboard", async ({ page }) => {
    await page.goto("/panel");
    const figure = page.getByRole("figure", { name: "Valor que caduca por tramo" });
    await figure.getByRole("button", { name: "Ver como tabla" }).press("Enter");
    const open = figure.getByRole("button", { name: "Ver productos: 0 a 30 días" });
    await open.focus();
    await page.keyboard.press("Enter");
    await expect.poll(() => drills.length).toBeGreaterThan(0);
    expect([drills[0]!.searchParams.get("kind"), drills[0]!.searchParams.get("band")]).toEqual(["expiry_band", "d0_30"]);
  });

  test("sends the dashboard filters with the chart request and asks again when one changes", async ({ page }) => {
    await page.goto("/panel?proveedor=s1&desde=2026-10-01");
    await expect.poll(() => calls.length).toBeGreaterThan(0);
    expect([calls[0]!.searchParams.get("supplier_id"), calls[0]!.searchParams.get("date_from")]).toEqual(["s1", "2026-10-01"]);
    const before = calls.length;
    await page.getByLabel("Categoría").selectOption("A");
    await expect.poll(() => calls.length).toBeGreaterThan(before);
    expect(calls[calls.length - 1]!.searchParams.get("category")).toBe("A");
  });

  test("a failing chart request shows an error with a retry and does not take the cards down", async ({ page }) => {
    await page.unroute("**/api/dashboard/charts*");
    let n = 0;
    await page.route("**/api/dashboard/charts*", (r) => (++n === 1 ? r.fulfill(json({ detail: "x" }, 502)) : r.fulfill(json(charts()))));
    await page.goto("/panel");
    await expect(page.getByRole("heading", { name: "Valor del stock" })).toBeVisible();   // the cards are still there
    await page.getByRole("button", { name: "Reintentar" }).last().click();
    await expect(page.getByRole("heading", { name: "Valor que caduca por tramo" })).toBeVisible();
  });

  test("a viewer sees no amounts in the charts and is told why the value history is missing", async ({ page }) => {
    await page.unroute("**/api/me");
    await signIn(page, ["viewer"]);
    await page.goto("/panel");
    const figure = page.getByRole("figure", { name: "Valor que caduca por tramo" });
    await figure.getByRole("button", { name: "Ver como tabla" }).press("Enter");
    await expect(figure.getByRole("table")).not.toContainText("€");
    await expect(page.getByText("Tu rol no puede ver los importes de este gráfico.")).toBeVisible();
  });

  test("has no serious accessibility violations with the charts shown", async ({ page }) => {
    await page.goto("/panel");
    await expect(page.getByRole("heading", { name: "Evolución del inventario valorado" })).toBeVisible();
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(results.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
  });
});
