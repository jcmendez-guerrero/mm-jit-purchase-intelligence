import { expect, type Page } from "@playwright/test";
import { json, overview, signIn } from "./dashboard-mock";

/** MMI 003 helpers: role sign-in, viewport matrix, cross-origin recorder, horizontal-scroll check. Synthetic data only. */

export const ROLES = {
  viewer: ["viewer"],
  buyer: ["viewer", "buyer"],
  approver: ["viewer", "approver"],
  admin: ["viewer", "admin"],
} as const;

export type RoleName = keyof typeof ROLES;

export const VIEWPORTS = [
  { name: "tablet-portrait", width: 768, height: 1024 },
  { name: "tablet-landscape", width: 1024, height: 768 },
  { name: "half-desktop", width: 1280, height: 800 },
  { name: "large-monitor", width: 1920, height: 1080 },
] as const;

/** Every route of the app (contracts/ui-contracts.md §1). */
export const ROUTES = [
  "/panel",
  "/calidad",
  "/propuestas",
  "/escenarios",
  "/costes",
  "/proveedores",
  "/importaciones",
  "/configuracion",
  "/administracion",
] as const;

/** Sign in as a role; calls without a mock answer 404, so screens render their own error states instead of crashing. */
export async function signInAs(page: Page, role: RoleName = "buyer") {
  await signIn(page, [...ROLES[role]]);
  await page.route("**/api/dashboard/overview**", (r) => r.fulfill(json(overview(3))));
  await page.route(/^https?:\/\/[^/]+\/api\/(?!me$|dashboard\/overview)/, (r) => r.fulfill(json({ detail: "not_found" }, 404)));
}

/** Records every request whose origin differs from the app's origin. */
export function recordCrossOrigin(page: Page, appOrigin: string): string[] {
  const external: string[] = [];
  page.on("request", (req) => {
    const url = req.url();
    if (url.startsWith("data:") || url.startsWith("blob:") || url.startsWith("about:")) return;
    if (new URL(url).origin !== appOrigin) external.push(url);
  });
  return external;
}

/** Fails when the page scrolls horizontally (FR-021). */
export async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "page must not scroll horizontally").toBeLessThanOrEqual(1);
}
