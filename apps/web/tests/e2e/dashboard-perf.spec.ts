import { expect, test } from "@playwright/test";
import { json, overview, signIn } from "./dashboard-mock";

/** T125: the screen shows its first meaningful content within 3 s for a payload of about 1,000 variants. This measures the browser side; the services are timed in their own suites. */

test("first meaningful content is visible within 3 seconds with 1,000 alerts", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview(1000))));
  const t0 = Date.now();
  await page.goto("/");
  await expect(page.getByLabel("Valor del inventario")).toContainText("1.234,50");
  await expect(page.getByRole("table", { name: "Tabla de riesgos detectados" })).toBeVisible();
  expect(Date.now() - t0).toBeLessThan(3000);
});
