import { expect, test } from "@playwright/test";
import { recordCrossOrigin, signInAs } from "./ui-helpers";

/** T006 — SC-006 / FR-009: no request leaves the app's own origin. Extended to every route in T031. */

test("the app root makes no cross-origin request", async ({ page, baseURL }) => {
  const external = recordCrossOrigin(page, new URL(baseURL ?? "http://localhost:5173").origin);
  await signInAs(page, "buyer");
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
  expect(external, `third-party requests: ${external.join(", ")}`).toEqual([]);
});
