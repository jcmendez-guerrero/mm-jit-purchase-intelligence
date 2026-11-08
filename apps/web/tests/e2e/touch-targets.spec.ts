import { expect, test, type Page } from "@playwright/test";
import { signInAs } from "./ui-helpers";

/** T048 — with a coarse pointer (touch), interactive controls are large enough to hit reliably (FR-023). */

test.use({ hasTouch: true, isMobile: true, viewport: { width: 768, height: 1024 } });

const MIN = 43.5; // 44 px less rounding
const MIN_TICK = 23.5; // checkboxes and radios: WCAG 2.2 minimum target size is 24 px

async function undersized(page: Page) {
  return page.evaluate(
    ({ min, minTick }) => {
      const out: string[] = [];
      const visible = (el: Element) => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
      };
      for (const el of document.querySelectorAll<HTMLElement>("button, select, input:not([type=hidden]), summary, [role=button]")) {
        if (!visible(el)) continue;
        if (el.classList.contains("mmi-visually-hidden") || el.closest(".mmi-visually-hidden")) continue;
        const r = el.getBoundingClientRect();
        const tick = el instanceof HTMLInputElement && (el.type === "checkbox" || el.type === "radio");
        if (r.height < (tick ? minTick : min) || (tick && r.width < minTick)) out.push(`${el.tagName.toLowerCase()} "${(el.getAttribute("aria-label") ?? el.textContent ?? "").trim().slice(0, 40)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
      }
      return out;
    },
    { min: MIN, minTick: MIN_TICK },
  );
}

test("the shell and the dashboard have touch-sized controls", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.goto("/panel");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.waitForLoadState("networkidle");
  expect(await undersized(page)).toEqual([]);
});

test("the open drawer has touch-sized links and buttons", async ({ page }) => {
  await signInAs(page, "admin");
  await page.goto("/panel");
  await page.getByRole("button", { name: "Abrir menú" }).tap();
  const sizes = await page.getByRole("dialog").getByRole("link").evaluateAll((els) => els.map((e) => e.getBoundingClientRect().height));
  for (const h of sizes) expect(h).toBeGreaterThanOrEqual(MIN);
  expect(await undersized(page)).toEqual([]);
});

test("a form screen has touch-sized controls", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.route("**/api/suppliers", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([{ id: "s1", name: "Proveedor Sintético A", terms: null, version: 1 }]) }));
  await page.goto("/proveedores");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.waitForLoadState("networkidle");
  expect(await undersized(page)).toEqual([]);
});
