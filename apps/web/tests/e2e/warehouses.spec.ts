import { expect, test } from "@playwright/test";
import { json, overview, signIn } from "./dashboard-mock";

test.describe("Warehouse breakdown and company-wide views (T108)", () => {
  test("options come from the data and the choice is sent on to every card", async ({ page }) => {
    await signIn(page);
    const seen: Array<string | null> = [];
    await page.route("**/api/dashboard/overview*", (r) => {
      seen.push(new URL(r.request().url()).searchParams.get("warehouse_id"));
      return r.fulfill(json(overview()));
    });
    await page.goto("/");
    const select = page.locator("#f-warehouse");
    await expect(select).toHaveValue("all");
    await expect(select.locator("option")).toHaveText(["Todos los almacenes (visión global)", "Almacén sintético A", "Almacén sintético B"]);
    expect(seen[0]).toBeNull();
    await select.selectOption("1");
    await expect.poll(() => seen.at(-1)).toBe("1");
    await select.selectOption("2");
    await expect.poll(() => seen.at(-1)).toBe("2");
  });
});
