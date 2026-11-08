import { expect, test, type Page } from "@playwright/test";
import { json } from "./dashboard-mock";
import { ROUTES, VIEWPORTS, expectNoHorizontalScroll, signInAs } from "./ui-helpers";

/**
 * T047 — every screen is usable from 768 px up without horizontal page scrolling; navigation collapses to a drawer
 * below 1024 px; zoom, enlarged text and reduced motion (SC-004, FR-021, FR-022, FR-025). Synthetic data.
 */

async function open(page: Page, path: string) {
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.waitForLoadState("networkidle");
}

for (const vp of VIEWPORTS) {
  test.describe(`${vp.name} ${vp.width}x${vp.height}`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });

    for (const path of ROUTES) {
      test(`${path} does not scroll horizontally`, async ({ page }) => {
        await signInAs(page, "admin");
        await open(page, path);
        await expectNoHorizontalScroll(page);
      });
    }
  });
}

test.describe("navigation collapses below 1024 px", () => {
  test.use({ viewport: { width: 768, height: 1024 } });

  test("the drawer offers the same destinations and closes after a choice", async ({ page }) => {
    await signInAs(page, "admin");
    await open(page, "/panel");
    await expect(page.getByRole("navigation")).toHaveCount(0); // the rail is not shown at this width
    const menu = page.getByRole("button", { name: "Abrir menú" });
    await expect(menu).toBeVisible();
    await menu.click();
    const nav = page.getByRole("dialog").getByRole("navigation", { name: "Menú principal de navegación" });
    await expect(nav.getByRole("link")).toHaveCount(9);
    await nav.getByRole("link", { name: "Escenarios", exact: true }).click();
    await expect(page).toHaveURL(/\/escenarios$/);
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  test("the drawer closes with Escape and returns focus to the menu button", async ({ page }) => {
    await signInAs(page, "buyer");
    await open(page, "/panel");
    const menu = page.getByRole("button", { name: "Abrir menú" });
    await menu.click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(menu).toBeFocused();
  });

  test("the header shows the isotipo instead of the horizontal logo", async ({ page }) => {
    await signInAs(page, "buyer");
    await open(page, "/panel");
    await expect(page.locator("header img[src*='isotipo']")).toBeVisible();
    await expect(page.locator("img[src*='logo-horizontal']:visible")).toHaveCount(0);
  });

  test("a wide table scrolls inside its own region and keeps its first column visible", async ({ page }) => {
    await signInAs(page, "buyer");
    const items = Array.from({ length: 6 }, (_, i) => ({ id: i + 1, variant_id: 100 + i, movement_reason_raw: "Motivo sintético largo ".repeat(6), anomaly_codes: ["negative_quantity", "unknown_reason"], created_at: "2026-11-01T10:00:00Z" }));
    await page.route("**/api/data-quality/import-errors", (r) => r.fulfill(json({ count: items.length, items })));
    await open(page, "/calidad");
    const region = page.getByRole("region", { name: /Tabla desplazable/ });
    await expect(region).toBeVisible();
    await expectNoHorizontalScroll(page);
    const result = await region.evaluate((el) => {
      el.scrollLeft = 400;
      const first = el.querySelector("tbody td") as HTMLElement;
      return { overflow: el.scrollWidth - el.clientWidth, offset: first.getBoundingClientRect().left - el.getBoundingClientRect().left };
    });
    expect(result.overflow).toBeGreaterThan(0);
    expect(Math.abs(result.offset)).toBeLessThanOrEqual(2);
  });
});

test.describe("wide layouts", () => {
  test("the rail and the menu button swap at 1024 px", async ({ page }) => {
    await signInAs(page, "buyer");
    await page.setViewportSize({ width: 1024, height: 768 });
    await open(page, "/panel");
    await expect(page.getByRole("navigation", { name: "Menú principal de navegación" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Abrir menú" })).toBeHidden();
  });

  test("on a very wide screen the content keeps a readable maximum width", async ({ page }) => {
    await signInAs(page, "buyer");
    await page.setViewportSize({ width: 2560, height: 1200 });
    await open(page, "/panel");
    const width = await page.locator("#contenido").evaluate((el) => el.getBoundingClientRect().width);
    expect(width).toBeLessThanOrEqual(1440 + 1);
  });
});

test.describe("zoom, enlarged text and reduced motion", () => {
  test("content reflows at 200 % zoom (a 1280 px window shows 640 CSS px)", async ({ page }) => {
    await signInAs(page, "buyer");
    await page.setViewportSize({ width: 640, height: 512 });
    for (const path of ["/panel", "/propuestas", "/proveedores"]) {
      await open(page, path);
      await expectNoHorizontalScroll(page);
    }
  });

  test("content reflows with a doubled base text size", async ({ page }) => {
    await signInAs(page, "buyer");
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.addInitScript(() => {
      document.addEventListener("DOMContentLoaded", () => (document.documentElement.style.fontSize = "200%"));
    });
    for (const path of ["/panel", "/proveedores"]) {
      await open(page, path);
      await expectNoHorizontalScroll(page);
    }
  });

  test("with reduced motion the ruler does not animate", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await signInAs(page, "buyer");
    await open(page, "/panel");
    const names = await page.locator(".mmi-ruler").evaluateAll((els) => els.map((e) => getComputedStyle(e).animationName));
    for (const n of names) expect(n).toBe("none");
  });
});

test("printing hides the navigation and the top bar and removes sticky positioning", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.setViewportSize({ width: 1280, height: 800 });
  await open(page, "/panel");
  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".mmi-rail")).toBeHidden();
  await expect(page.locator(".mmi-topbar")).toBeHidden();
  const position = await page.locator("main table th").first().evaluate((el) => getComputedStyle(el).position).catch(() => "static");
  expect(position).not.toBe("sticky");
});

test("a proposal prints without the shell, sticky headers or clipped tables", async ({ page }) => {
  await signInAs(page, "buyer");
  const summary = { id: "prop-1", week: "2026-W45", status: "draft", version: 3, created_by: "buyer-1", updated_at: "2026-11-04T10:00:00Z" };
  const line = {
    id: "l1", variant_id: 101, sku: "SYN-101", product_name: "Producto sintético", supplier_id: "s1", supplier_name: "Proveedor Sintético A", qty: 10, unit_cost_with_recargo: "5.2600", line_total: "52.6000",
    risk: "low", confidence: "high", manual_override: false, topup: false, constraints_applied: [],
    explanation: { policy: "forecast", forecast_eligible: true, service_level: "95", horizon_days: 14, expected_demand: 8, safety_stock: 2, order_up_to: 12, reorder_point: 5, need: 10, top_up: false, clinical_critical: false, position: { on_hand: 0, expiring: 0, usable: 0, inbound: 0, total: 0 }, supplier: { chosen: "s1", reason: "lowest_cost", alternatives: [], rejected: [] }, cost: { unit: "5.2600", source: "manual", status: "ok" }, constraints: [] },
  };
  await page.route("**/api/proposals", (r) => r.fulfill(json([summary])));
  await page.route("**/api/proposals/prop-1", (r) => r.fulfill(json({ ...summary, last_edited_by: null, terms_version_ids: null, approval: null, supplier_groups: [], lines: [line] })));
  await page.setViewportSize({ width: 1280, height: 800 });
  await open(page, "/propuestas");
  await expect(page.getByText("Producto sintético")).toBeVisible();
  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".mmi-rail")).toBeHidden();
  await expect(page.locator(".mmi-topbar")).toBeHidden();
  const table = await page.locator('table[aria-label="Tabla de propuestas de compra"]').evaluate((el) => {
    const wrapper = el.closest(".mmi-table-wrapper") as HTMLElement;
    return { sticky: getComputedStyle(el.querySelector("th")!).position, overflow: getComputedStyle(wrapper).overflow, maxHeight: getComputedStyle(wrapper).maxHeight };
  });
  expect(table.sticky).not.toBe("sticky");
  expect(table.overflow).toBe("visible");
  expect(table.maxHeight).toBe("none");
});

test("when the font files cannot be loaded the text stays legible and the layout stable", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/*.woff2", (r) => r.abort());
  await signInAs(page, "buyer");
  await page.setViewportSize({ width: 1280, height: 800 });
  await open(page, "/panel");
  const title = page.getByRole("heading", { level: 1, name: "Panel de control" });
  await expect(title).toBeVisible();
  const box = await title.boundingBox();
  expect(box!.height).toBeGreaterThan(10);
  const fallback = await title.evaluate((el) => getComputedStyle(el).fontFamily);
  expect(fallback).toMatch(/sans-serif/); // the stack ends in system fonts
  await expectNoHorizontalScroll(page);
  expect(errors).toEqual([]);
});

test("a plain scroll-region table keeps its first column visible when it scrolls sideways", async ({ page }) => {
  await signInAs(page, "buyer");
  const summary = { id: "prop-1", week: "2026-W45", status: "draft", version: 3, created_by: "buyer-1", updated_at: "2026-11-04T10:00:00Z" };
  const line = {
    id: "l1", variant_id: 101, sku: "SYN-101", product_name: "Producto sintético con un nombre bastante largo", supplier_id: "s1", supplier_name: "Proveedor Sintético A", qty: 10, unit_cost_with_recargo: "5.2600", line_total: "52.6000",
    risk: "low", confidence: "high", manual_override: false, topup: false, constraints_applied: [],
    explanation: { policy: "forecast", forecast_eligible: true, service_level: "95", horizon_days: 14, expected_demand: 8, safety_stock: 2, order_up_to: 12, reorder_point: 5, need: 10, top_up: false, clinical_critical: false, position: { on_hand: 0, expiring: 0, usable: 0, inbound: 0, total: 0 }, supplier: { chosen: "s1", reason: "lowest_cost", alternatives: [], rejected: [] }, cost: { unit: "5.2600", source: "manual", status: "ok" }, constraints: [] },
  };
  await page.route("**/api/proposals", (r) => r.fulfill(json([summary])));
  await page.route("**/api/proposals/prop-1", (r) => r.fulfill(json({ ...summary, last_edited_by: null, terms_version_ids: null, approval: null, supplier_groups: [], lines: [line] })));
  await page.setViewportSize({ width: 420, height: 800 });
  await open(page, "/propuestas");
  const wrapper = page.locator('.mmi-table-wrapper:has(table[aria-label="Tabla de propuestas de compra"])');
  await expect(wrapper).toBeVisible();
  const result = await wrapper.evaluate((el) => {
    el.scrollLeft = 300;
    const first = el.querySelector("tbody td") as HTMLElement;
    return { overflow: el.scrollWidth - el.clientWidth, offset: first.getBoundingClientRect().left - el.getBoundingClientRect().left };
  });
  expect(result.overflow).toBeGreaterThan(0);
  expect(Math.abs(result.offset)).toBeLessThanOrEqual(2);
  await expectNoHorizontalScroll(page);
});
