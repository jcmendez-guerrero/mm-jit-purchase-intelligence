import { expect, test } from "@playwright/test";
import { signInAs } from "./ui-helpers";

/** T065 — the appearance follows the device by default, a choice persists across reloads, nothing flashes, motion is respected (FR-024, FR-025). */

const theme = (page: import("@playwright/test").Page) => page.evaluate(() => document.documentElement.getAttribute("data-theme"));
const background = (page: import("@playwright/test").Page) => page.evaluate(() => getComputedStyle(document.body).backgroundColor);

test("with no saved choice the app follows the device preference", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await signInAs(page, "buyer");
  await page.goto("/panel");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(await theme(page)).toBe("dark");
  expect(await background(page)).toBe("rgb(0, 32, 40)"); // Azul noche
  await page.emulateMedia({ colorScheme: "light" });
  await expect.poll(() => theme(page)).toBe("light");
  expect(await background(page)).toBe("rgb(242, 248, 249)"); // Blanco hielo
});

test("a choice made in the app wins over the device and survives a reload", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await signInAs(page, "buyer");
  await page.goto("/panel");
  await page.getByRole("group", { name: "Apariencia" }).getByRole("button", { name: "Claro" }).click();
  expect(await theme(page)).toBe("light");
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(await theme(page)).toBe("light");
  await expect(page.getByRole("group", { name: "Apariencia" }).getByRole("button", { name: "Claro" })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("group", { name: "Apariencia" }).getByRole("button", { name: "Sistema" }).click();
  expect(await theme(page)).toBe("dark");
});

test("the right theme is set before the application code runs (no flash)", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.addInitScript(() => localStorage.setItem("mmi.ui.appearance", "dark"));
  await page.route("**/src/main.tsx*", (r) => r.abort()); // only the head script may run
  await page.goto("/panel");
  expect(await theme(page)).toBe("dark");
  await page.addInitScript(() => localStorage.setItem("mmi.ui.appearance", "light"));
  await page.reload();
  expect(await theme(page)).toBe("light");
});

test("the logo keeps its original colours on a white plate in the dark appearance", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await signInAs(page, "buyer");
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/panel");
  const plate = await page.locator(".mmi-rail .mmi-logo-plate").evaluate((el) => getComputedStyle(el).backgroundColor);
  expect(plate).toBe("rgb(255, 255, 255)");
});
