import { expect, test, type Page } from "@playwright/test";

/**
 * Feature 011 (FR-010, FR-015): proposals and scenarios against the real services, in Spanish, with the stack's synthetic data.
 * Run only against the local compose stack (it uses the local demo sign-in):
 *   PLAYWRIGHT_BASE_URL=http://localhost:8080 npx playwright test --config playwright.live.config.ts procurement-journey
 * The stack has no forecast service and the gateway has no proposal-generation route, so generation, approval and the file contents
 * are covered by the service tests; this journey proves the screens and the role gate on the real gateway.
 */

const signInAs = async (page: Page, role: "Lector" | "Comprador" | "Aprobador" | "Administrador") => {
  await page.goto("/panel");
  await page.getByRole("button", { name: `Entrar como ${role}` }).click();
  await expect(page.getByRole("navigation", { name: "Menú principal de navegación" })).toBeVisible();
};

test("a viewer reads the proposals and scenarios screens in Spanish and the real gateway refuses the export", async ({ page }) => {
  await signInAs(page, "Lector");
  await expect(page.locator("html")).toHaveAttribute("lang", /^es/);
  const nav = page.getByRole("navigation", { name: "Menú principal de navegación" });

  await nav.getByRole("link", { name: "Propuestas de compra" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Propuestas de compra" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Exportar/ })).toHaveCount(0);

  await nav.getByRole("link", { name: "Escenarios" }).click();
  await expect(page.getByRole("heading", { name: "Escenarios de compra" }).first()).toBeVisible();

  const proposal = await page.request.get("/api/proposals/does-not-exist/export?format=csv");
  expect(proposal.status()).toBe(403);
  expect((await proposal.json()).detail).toBe("auth_forbidden_role");
  const scenario = await page.request.get("/api/scenarios/does-not-exist/export?format=xlsx");
  expect(scenario.status()).toBe(403);
  expect((await scenario.json()).detail).toBe("auth_forbidden_role");
});

test("a buyer passes the role gate: the export of an unknown proposal is a not-found or state answer, never a permission refusal", async ({ page }) => {
  await signInAs(page, "Comprador");
  const res = await page.request.get("/api/proposals/does-not-exist/export?format=csv");
  expect([404, 409]).toContain(res.status());
  const approver = await page.request.get("/api/scenarios/does-not-exist/export?format=csv");
  expect([404, 409]).toContain(approver.status());
});

/**
 * T035/T048 (option A): the stack plans from a synthetic stock and forecast and seeds one draft proposal (MMI_DEMO_SEED=1, local only).
 * "Generate" is therefore proven by the service tests, not by this journey; everything from opening the proposal on is real.
 * A promoted scenario makes a fresh draft each run, so the journey can be repeated on the same stack.
 */
test("a buyer opens the proposal, reads why, edits a line, compares a scenario within three minutes, promotes and submits it", async ({ page, browser, baseURL }) => {
  test.setTimeout(Number(process.env.JOURNEY_TIMEOUT_MS ?? 180_000));
  // Sending for approval needs a second person with the approver role in the user directory, so the approver signs in first.
  const approverContext = await browser.newContext(baseURL ? { baseURL } : {});
  const approver = await approverContext.newPage();
  await signInAs(approver, "Aprobador");

  await signInAs(page, "Comprador");
  const nav = page.getByRole("navigation", { name: "Menú principal de navegación" });
  await nav.getByRole("link", { name: "Propuestas de compra" }).click();
  const started = Date.now();

  await expect(page.getByText("Creada por demo-seed").or(page.getByText(/Creada por/)).first()).toBeVisible();
  await page.getByRole("button", { name: "Ver justificación" }).first().click();
  await expect(page.getByText("Por qué esta cantidad").first()).toBeVisible();

  const charge = (10 + (Date.now() % 9000) / 100).toFixed(2).replace(".", ",");   // a different scenario each run: the same inputs would return the proposal that already exists
  const name = `Envío de pago ${Date.now()}`;
  await nav.getByRole("link", { name: "Escenarios" }).click();
  await page.getByLabel("Nombre del escenario").fill(name);
  await page.getByLabel("Gastos de envío (€)").first().fill(String(charge));
  await page.getByRole("button", { name: "Calcular escenario" }).click();
  await page.getByRole("row", { name: new RegExp(name) }).getByRole("button", { name: "Abrir" }).click();
  await expect(page.getByText(`Diferencia de coste: ${charge} €`)).toBeVisible({ timeout: 60_000 });
  const seconds = (Date.now() - started) / 1000;
  expect(seconds, "SC-005: opening a proposal to a compared scenario, under 3 minutes").toBeLessThan(180);
  console.log(`proposal opened to compared scenario: ${seconds.toFixed(1)} s`);

  await page.getByRole("button", { name: "Convertir en propuesta" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Convertir en propuesta" }).click();
  await expect(page.getByText(/Propuesta creada como borrador/)).toBeVisible();

  await nav.getByRole("link", { name: "Propuestas de compra" }).click();
  await page.getByRole("button", { name: "Descartar cambios" }).click();   // the scenario form still holds what was typed, so leaving it asks first
  await expect(page.getByText("Borrador").first()).toBeVisible();   // the promoted scenario is a fresh draft, so the journey can repeat on the same stack
  const qty = page.getByLabel("Cantidad para Producto sintetico A");
  await qty.fill(String(Number(await qty.inputValue()) + 6));   // always a change, so the save button shows on a repeated run
  await page.getByRole("button", { name: "Guardar cantidad" }).first().click();
  await expect(page.getByText("Cantidad modificada manualmente").first()).toBeVisible();

  await page.getByRole("button", { name: "Enviar a aprobación" }).first().click();
  await page.getByRole("dialog").getByRole("button", { name: "Enviar a aprobación" }).click();
  await expect(page.getByText("Enviada para aprobación").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Aprobar propuesta/ })).toHaveCount(0);   // the creator cannot approve their own proposal

  await approver.getByRole("navigation", { name: "Menú principal de navegación" }).getByRole("link", { name: "Propuestas de compra" }).click();
  await expect(approver.getByRole("button", { name: /Aprobar propuesta/ }).first()).toBeVisible();
  await approverContext.close();
});
