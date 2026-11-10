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
});
