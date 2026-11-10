import { expect, test, type Page } from "@playwright/test";
import { json, overview } from "./dashboard-mock";
import { signInAs } from "./ui-helpers";

/**
 * T035 — every data screen provides a loading placeholder, an empty state and an error state with retry (SC-008, FR-013),
 * and long names do not break the layout. Synthetic data; each screen's own endpoints are mocked.
 */

interface Screen {
  name: string;
  path: string;
  /** Registers the endpoints of the screen. `mode` picks the answer. */
  mock: (page: Page, mode: "ok" | "empty" | "error" | "slow") => Promise<void>;
  /** Text the empty state shows; absent for screens that always show their sections (no empty list to show). */
  empty?: RegExp;
  /** Something visible once data has loaded (in the "ok" mode). */
  ready: (page: Page) => ReturnType<Page["getByText"]>;
}

const fail = { detail: "unavailable" };

async function answer(page: Page, glob: string, mode: "ok" | "empty" | "error" | "slow", ok: unknown, empty: unknown) {
  await page.route(glob, async (r) => {
    if (r.request().method() !== "GET") return r.fulfill(json({}));
    if (mode === "slow") await new Promise((res) => setTimeout(res, 900));
    if (mode === "error") return r.fulfill(json(fail, 500));
    return r.fulfill(json(mode === "empty" ? empty : ok));
  });
}

const SCREENS: Screen[] = [
  {
    name: "dashboard",
    path: "/panel",
    mock: async (page, mode) => {
      await answer(page, "**/api/dashboard/overview**", mode, overview(2), overview(0, { risks: { ok: true, data: [] } }));
    },
    empty: /No se detectaron riesgos de inventario hoy/,
    ready: (page) => page.getByText("Valor del stock").first(),
  },
  {
    name: "quality",
    path: "/calidad",
    mock: async (page, mode) => {
      const longName = "Z".repeat(240);
      await answer(page, "**/api/data-quality/import-errors", mode, { count: 1, items: [{ id: 1, variant_id: 5, movement_reason_raw: longName, anomaly_codes: ["negative_quantity"], created_at: "2026-11-01T10:00:00Z" }] }, { count: 0, items: [] });
    },
    empty: /No hay movimientos pendientes de revisión/,
    ready: (page) => page.getByText("negative_quantity"),
  },
  {
    name: "proposals",
    path: "/propuestas",
    mock: async (page, mode) => {
      await answer(page, "**/api/proposals", mode, [], []);
    },
    empty: /No hay propuestas activas/,
    ready: (page) => page.getByText(/No hay propuestas activas/),
  },
  {
    name: "suppliers",
    path: "/proveedores",
    mock: async (page, mode) => {
      await answer(page, "**/api/suppliers", mode, [{ id: "s1", name: "Proveedor Sintético A", terms: null, version: 1 }], []);
    },
    empty: /No hay proveedores todavía/,
    ready: (page) => page.getByRole("button", { name: "Proveedor Sintético A" }),
  },
  {
    name: "costs",
    path: "/costes",
    mock: async (page, mode) => {
      await answer(page, "**/api/costs", mode, [], []);
      await answer(page, "**/api/cost-writes", mode, [], []);
    },
    empty: /No hay costes de proveedor registrados/,
    ready: (page) => page.getByText(/No hay costes de proveedor registrados/),
  },
  {
    name: "scenarios",
    path: "/escenarios",
    mock: async (page, mode) => {
      await answer(page, "**/api/scenarios", mode, { scenarios: [] }, { scenarios: [] });
      await answer(page, "**/api/suppliers", "ok", [], []);
    },
    empty: /Todavía no hay escenarios/,
    ready: (page) => page.getByText(/Todavía no hay escenarios/),
  },
  {
    name: "imports",
    path: "/importaciones",
    mock: async (page, mode) => {
      await answer(page, "**/api/imports", mode, { datasets: [] }, { datasets: [] });
      await answer(page, "**/api/imports/jobs", "ok", { jobs: [], background_over_rows: 0 }, { jobs: [], background_over_rows: 0 });
    },
    empty: /Todavía no hay conjuntos de datos/,
    ready: (page) => page.getByText(/Todavía no hay conjuntos de datos/),
  },
  {
    name: "policies",
    path: "/configuracion",
    mock: async (page, mode) => {
      const console_ = {
        purchasing: { ok: true, data: { as_of: "2026-11-09", weekly_budget: null, policies: [{ scope: "global", key: "*", revision: 1, in_force: null }] } },
        demand: { ok: true, data: { exclusions: [], rules: [] } },
        forecast: { ok: true, data: { as_of: "2026-11-09", parameters: [] } },
      };
      await answer(page, "**/api/policy-console", mode, console_, console_);
    },
    ready: (page) => page.getByRole("tabpanel"),
  },
  {
    name: "administration",
    path: "/administracion",
    mock: async (page, mode) => {
      const status = {
        freshness: { ok: true, data: { stock_snapshots: { latest_day: "2026-11-09", rows: 40 }, movements: { rows: 900, quarantined: 3, latest_at: new Date().toISOString() }, aggregates: { refreshed_at: new Date().toISOString() } } },
        import_jobs: { ok: true, data: { jobs: [] } },
        model_runs: { ok: true, data: { runs: [] } },
        policy_history: { ok: true, data: [] },
        role_mirror: { ok: true, data: { pending: 0, failed: 0, sent: 1, oldest_pending_seconds: 0 } },
        cost: { budget_eur: 120, estimate_eur: 0, guardrails: { min_replicas: 0, max_replicas: 1, job_parallelism: 1 } },
      };
      await answer(page, "**/api/admin/status", mode, status, status);
      await answer(page, "**/api/admin/roles", "ok", { users: [], eligible_approvers_count: 2, valid_roles: ["viewer", "buyer", "approver", "admin"] }, {});
      await answer(page, "**/api/admin/roles/mirror", "ok", { pending: 0, failed: 0, sent: 1, oldest_pending_seconds: 0, items: [] }, {});
    },
    ready: (page) => page.getByRole("heading", { name: /Estado del sistema/ }),
  },
];

for (const screen of SCREENS) {
  test.describe(screen.name, () => {
    test("shows a skeleton while data is on its way, then the content", async ({ page }) => {
      await signInAs(page, screen.name === "administration" ? "admin" : "buyer");
      await screen.mock(page, "slow");
      await page.goto(screen.path);
      await expect(page.getByRole("status", { name: "Cargando datos" }).first()).toBeVisible();
      await expect(screen.ready(page)).toBeVisible({ timeout: 8000 });
    });

    test("shows a designed empty state", async ({ page }) => {
      test.skip(!screen.empty, "this screen always shows its sections");
      await signInAs(page, "buyer");
      await screen.mock(page, "empty");
      await page.goto(screen.path);
      await expect(page.getByText(screen.empty!).first()).toBeVisible();
    });

    test("shows an error with a retry that recovers", async ({ page }) => {
      await signInAs(page, screen.name === "administration" ? "admin" : "buyer");
      await screen.mock(page, "error");
      await page.goto(screen.path);
      await expect(page.getByRole("alert").first()).toBeVisible();
      const retry = page.getByRole("button", { name: "Reintentar" });
      await expect(retry.first()).toBeVisible();
      await screen.mock(page, "ok");
      await retry.first().click();
      await expect(screen.ready(page)).toBeVisible({ timeout: 8000 });
    });
  });
}

test("very long names truncate or wrap without breaking the layout", async ({ page }) => {
  await signInAs(page, "buyer");
  await answer(page, "**/api/data-quality/import-errors", "ok", { count: 1, items: [{ id: 1, variant_id: 5, movement_reason_raw: "Z".repeat(400), anomaly_codes: ["negative_quantity"], created_at: "2026-11-01T10:00:00Z" }] }, {});
  await page.goto("/calidad");
  await expect(page.getByText("negative_quantity")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
