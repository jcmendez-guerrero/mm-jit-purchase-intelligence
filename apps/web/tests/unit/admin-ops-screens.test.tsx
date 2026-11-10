// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AlertsListing, api, ApiError, OpsSummary, OpsThresholds } from "../../src/api/client";
import { AlertsPanel } from "../../src/features/admin/AlertsPanel";
import { AuditScreen } from "../../src/features/admin/AuditScreen";
import { OpsCards } from "../../src/features/admin/OpsCards";
import { QueuePanel } from "../../src/features/admin/QueuePanel";
import "../../src/i18n";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const thresholds: OpsThresholds = { source_stale_hours: 36, backup_max_age_hours: 26, budget_warn_pct: 80, budget_critical_pct: 100, mirror_lag_minutes: 15, alert_repeat_hours: 24 };

describe("OpsCards (Spanish)", () => {
  it("says unavailable instead of showing a number", async () => {
    vi.spyOn(api, "getOpsSummary").mockResolvedValue({ backup: { ok: false, error: "snapshot_unavailable" }, cost: { ok: false, error: "snapshot_unavailable" } });
    render(<OpsCards />);
    expect((await screen.findAllByText(/No disponible/)).length).toBe(2);
  });
  it("shows spend in EUR with the level, an estimate label, and an old backup as an alert", async () => {
    const summary: OpsSummary = {
      backup: { ok: true, data: { last_success_at: "2026-11-08T10:00:00Z", last_restore_drill_at: null, captured_at: "2026-11-10T10:00:00Z", stale_snapshot: false, old: true } },
      cost: { ok: true, data: { currency: "EUR", budget: "120.00", month_to_date: "40.00", projected: "96.00", partial_month: true, captured_at: "2026-11-10T10:00:00Z", stale_snapshot: true, projected_pct: "80.0", level: "warning", projection_is_estimate: true } },
    };
    vi.spyOn(api, "getOpsSummary").mockResolvedValue(summary);
    render(<OpsCards />);
    expect(await screen.findByText(/Proyección: 96,00/)).toBeTruthy();
    expect(screen.getByText("Aviso: la proyección se acerca al presupuesto")).toBeTruthy();
    expect(screen.getByText("Es una estimación: el mes aún no ha terminado.")).toBeTruthy();
    expect(screen.getByText("La copia es más antigua que el límite acordado.")).toBeTruthy();
    expect(screen.getByText("Sin simulacro de restauración registrado.")).toBeTruthy();
  });
});

describe("QueuePanel (Spanish)", () => {
  it("offers a retry only on failed items and reports it", async () => {
    vi.spyOn(api, "getQueue").mockResolvedValue({ items: [
      { kind: "import", id: "job-1", state: "failed", attempts: 0, reason_code: "import_failed" },
      { kind: "message", id: "inventory.projections", state: "dead_lettered", attempts: 2, reason_code: "poison", stale: true },
      { kind: "forecast", id: "run-1", state: "running", attempts: 0, reason_code: null },
    ] });
    const retry = vi.spyOn(api, "retryQueueItem").mockResolvedValue({});
    render(<QueuePanel />);
    expect(await screen.findByText(/cifra antigua/)).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /Reintentar/ })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Reintentar job-1" }));
    await waitFor(() => expect(retry).toHaveBeenCalledWith("import", "job-1"));
  });
  it("shows a stale-MFA refusal in Spanish, never the code", async () => {
    vi.spyOn(api, "getQueue").mockResolvedValue({ items: [{ kind: "mirror", id: "7", state: "dead_lettered", attempts: 8, reason_code: "role_mirror_failed" }] });
    vi.spyOn(api, "retryQueueItem").mockRejectedValue(new ApiError(403, "auth_mfa_stale"));
    render(<QueuePanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Reintentar 7" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Debe volver a verificar su segundo factor");
    expect(document.body.textContent).not.toContain("auth_mfa_stale");
  });
});

describe("AlertsPanel (Spanish)", () => {
  const listing: AlertsListing = { delivery_configured: false, items: [
    { id: 1, condition_key: "backup_old", subject: "backup", severity: "warning", state: "open", opened_at: "2026-11-10T08:00:00Z", last_seen_at: "2026-11-10T08:00:00Z", acknowledged_by: null, acknowledged_at: null, reason_code: "backup_old" },
  ] };
  it("lists the alert, says no channel exists, and acknowledges it", async () => {
    vi.spyOn(api, "getAlerts").mockResolvedValue(listing);
    vi.spyOn(api, "getOpsSettings").mockResolvedValue(thresholds);
    const ack = vi.spyOn(api, "acknowledgeAlert").mockResolvedValue(listing.items[0]!);
    render(<AlertsPanel />);
    expect(await screen.findByText("Copia de seguridad antigua")).toBeTruthy();
    expect(screen.getByText(/No hay canal de correo configurado/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Reconocer/ }));
    await waitFor(() => expect(ack).toHaveBeenCalledWith(1));
  });
  it("refuses inconsistent thresholds before calling the server", async () => {
    vi.spyOn(api, "getAlerts").mockResolvedValue({ ...listing, delivery_configured: true });
    vi.spyOn(api, "getOpsSettings").mockResolvedValue(thresholds);
    const save = vi.spyOn(api, "saveOpsSettings").mockResolvedValue(thresholds);
    render(<AlertsPanel />);
    fireEvent.change(await screen.findByLabelText(/Aviso de presupuesto/), { target: { value: "120" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    expect((await screen.findByRole("alert")).textContent).toContain("fuera de su rango");
    expect(save).not.toHaveBeenCalled();
  });
});

describe("AuditScreen (Spanish)", () => {
  const page = { items: [
    { id: 3, ts: "2026-11-10T09:00:00Z", actor: "buyer-1", action: "access.refused", entity: "access", entity_id: "PUT /x", outcome: "refused" as const, reason_code: "forbidden_missing_role" },
    { id: 2, ts: "2026-11-10T08:00:00Z", actor: "admin-1", action: "roles.changed", entity: "user_roles", entity_id: "buyer-3", outcome: "allowed" as const, reason_code: null },
  ], next_cursor: "2" };
  it("filters, pages, verifies and reports a broken chain in Spanish", async () => {
    const get = vi.spyOn(api, "getAudit").mockResolvedValue(page);
    vi.spyOn(api, "verifyAudit").mockResolvedValue({ ok: false, checked: 5, first_broken_id: 2 });
    render(<AuditScreen />);
    expect(await screen.findByText("roles.changed")).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/Resultado/), { target: { value: "refused" } });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() => expect(get).toHaveBeenLastCalledWith({ outcome: "refused" }, undefined));
    fireEvent.click(screen.getByRole("button", { name: "Cargar más" }));
    await waitFor(() => expect(get).toHaveBeenLastCalledWith({ outcome: "refused" }, "2"));
    fireEvent.click(screen.getByRole("button", { name: "Verificar integridad" }));
    expect((await screen.findByRole("alert")).textContent).toContain("La cadena está rota en la entrada 2");
  });
  it("downloads the export", async () => {
    vi.spyOn(api, "getAudit").mockResolvedValue({ items: [], next_cursor: null });
    const exp = vi.spyOn(api, "exportAudit").mockResolvedValue({ blob: new Blob(["x"]), truncated: true });
    (URL as unknown as { createObjectURL: () => string }).createObjectURL = () => "blob:x";
    (URL as unknown as { revokeObjectURL: () => void }).revokeObjectURL = () => undefined;
    render(<AuditScreen />);
    fireEvent.click(await screen.findByRole("button", { name: "Exportar CSV" }));
    await waitFor(() => expect(exp).toHaveBeenCalled());
  });
});
