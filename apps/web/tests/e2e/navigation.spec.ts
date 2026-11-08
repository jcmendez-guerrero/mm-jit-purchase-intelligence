import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { ROLES, ROUTES, recordCrossOrigin, signInAs, type RoleName } from "./ui-helpers";

/** T019 — navigation, shareable addresses, quick-jump, skip link, no-access (SC-001, FR-001–004, FR-020). Synthetic data. */

const LABELS: Record<string, string> = {
  "/panel": "Panel de control",
  "/calidad": "Calidad y datos",
  "/propuestas": "Propuestas de compra",
  "/escenarios": "Escenarios",
  "/costes": "Costes y proveedores",
  "/proveedores": "Proveedores",
  "/importaciones": "Datos predictivos",
  "/configuracion": "Configuración",
  "/administracion": "Administración",
};

const palette = (page: import("@playwright/test").Page) => page.getByPlaceholder("Escribe el nombre de una pantalla");
const nav = (page: import("@playwright/test").Page) => page.getByRole("navigation", { name: "Menú principal de navegación" });

for (const role of Object.keys(ROLES) as RoleName[]) {
  test(`${role} reaches every permitted screen in at most two interactions`, async ({ page }) => {
    await signInAs(page, role);
    await page.goto("/");
    await expect(page).toHaveURL(/\/panel$/);
    const allowed = role === "admin" ? ROUTES : ROUTES.filter((r) => r !== "/administracion");
    for (const path of allowed) {
      // one interaction: the navigation link
      await nav(page).getByRole("link", { name: LABELS[path]!, exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`${path}$`));
      await expect(page.getByRole("heading", { level: 1, name: LABELS[path]! })).toBeVisible();
      await expect(nav(page).getByRole("link", { name: LABELS[path]!, exact: true })).toHaveAttribute("aria-current", "page");
    }
    if (role !== "admin") {
      await expect(nav(page).getByRole("link", { name: "Administración", exact: true })).toHaveCount(0);
    }
  });
}

test("the quick-jump reaches a screen with the keyboard (two interactions)", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.goto("/panel");
  await expect(page.getByRole("heading", { level: 1, name: "Panel de control" })).toBeVisible();
  await page.keyboard.press("Control+k");
  await palette(page).fill("proveedores");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/proveedores$/);
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("the quick-jump ignores accents and does not offer the administration screen to a buyer", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.goto("/panel");
  await page.getByRole("button", { name: "Ir a una pantalla" }).click();
  await palette(page).fill("configuracion");
  await expect(page.getByRole("listbox").getByRole("option", { name: /Configuración/ })).toBeVisible();
  await palette(page).fill("administracion");
  await expect(page.getByRole("listbox").getByRole("option")).toHaveCount(0);
});

test("reload, deep link and back/forward return to the same screen", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.goto("/costes");
  await expect(page.getByRole("heading", { level: 1, name: "Costes y proveedores" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Costes y proveedores" })).toBeVisible();
  await nav(page).getByRole("link", { name: "Escenarios", exact: true }).click();
  await expect(page).toHaveURL(/\/escenarios$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/costes$/);
  await page.goForward();
  await expect(page).toHaveURL(/\/escenarios$/);
});

test("the selected warehouse is part of the address and survives a reload", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.goto("/panel?almacen=2");
  await expect(page.getByLabel("Almacén")).toHaveValue("2");
  await page.reload();
  await expect(page.getByLabel("Almacén")).toHaveValue("2");
  await page.getByLabel("Almacén").selectOption("all");
  await expect(page).not.toHaveURL(/almacen=/);
});

test("the skip link is the first stop and moves focus to the content", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.goto("/panel");
  await expect(page.locator("#contenido")).toBeAttached();   // the shell appears once the session check is done
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Ir al contenido" });
  await expect(skip).toBeFocused();
  await expect(skip).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page.locator("#contenido")).toBeFocused();
});

test("a viewer opening the administration address sees a no-access explanation", async ({ page }) => {
  await signInAs(page, "viewer");
  await page.goto("/administracion");
  await expect(page.getByText("Tu rol no permite ver esta sección.")).toBeVisible();
  await page.getByRole("link", { name: "Ir al panel de control" }).click();
  await expect(page).toHaveURL(/\/panel$/);
});

test("an unknown address shows a not-found state with a way back", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.goto("/no-existe");
  await expect(page.getByText("Esta página no existe.")).toBeVisible();
  await page.getByRole("link", { name: "Ir al panel de control" }).click();
  await expect(page).toHaveURL(/\/panel$/);
});

test("an expired session explains itself and offers no stale screen state", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.goto("/costes");
  await expect(page.getByRole("heading", { level: 1, name: "Costes y proveedores" })).toBeVisible();
  // from now on the session probe and every call answer 401
  await page.route("**/api/me", (r) => r.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "unauthenticated" }) }));
  await page.route(/^https?:\/\/[^/]+\/api\/(?!me$)/, (r) => r.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "unauthenticated" }) }));
  await nav(page).getByRole("link", { name: "Propuestas de compra", exact: true }).click();
  await expect(page.getByText("La sesión ha caducado.")).toBeVisible();
  await expect(page.getByText("Inicia sesión de nuevo para continuar.")).toBeVisible();
});

test("every route loads without third-party requests and without serious accessibility violations in the shell", async ({ page, baseURL }) => {
  test.setTimeout(90_000); // nine routes with an axe run each
  const external = recordCrossOrigin(page, new URL(baseURL ?? "http://localhost:5173").origin);
  await signInAs(page, "admin");
  for (const path of ROUTES) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: LABELS[path]! })).toBeVisible();
    const results = await new AxeBuilder({ page }).include("aside").include("header").withTags(["wcag2a", "wcag2aa"]).analyze();
    const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad.map((v) => `${path}: ${v.id}`)).toEqual([]);
  }
  expect(external, `third-party requests: ${external.join(", ")}`).toEqual([]);
});

test("a screen the server refuses mid-session explains it and offers a way forward", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.goto("/panel");
  await expect(page.getByRole("heading", { level: 1, name: "Panel de control" })).toBeVisible();
  await page.route("**/api/costs", (r) => r.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "auth_forbidden_role" }) }));
  await page.route("**/api/cost-writes", (r) => r.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "auth_forbidden_role" }) }));
  await nav(page).getByRole("link", { name: "Costes y proveedores", exact: true }).click();
  await expect(page.getByText("No tiene permiso para realizar esta acción.").first()).toBeVisible();
  await page.getByRole("link", { name: "Ir al panel de control" }).first().click();
  await expect(page).toHaveURL(/\/panel$/);
});
