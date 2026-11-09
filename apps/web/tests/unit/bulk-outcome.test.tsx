// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, BulkPreview, SupplierSummary } from "../../src/api/client";
import { BulkAssign } from "../../src/features/suppliers/BulkAssign";
import "../../src/i18n";

/** T035 (FR-018): after applying a bulk assignment the buyer sees what happened to each product, by SKU. */

const sup = (): SupplierSummary => ({
  id: "s1", name: "Proveedor Sintético Uno", terms: null, version: 0, supplier_version: 3, status: "active", classification: "purchasing", origin: "platform",
  erp_link_state: "none", fiscal_type: "national", country: "ES", currency: "EUR", payment_terms_days: 30, order_channel: "email",
});
const preview = (): BulkPreview => ({ batch_id: "b1", matched: 4, new: 3, existing: 1, conflicts: 0, conflict_skus: [], unknown: [], expires_at: "x" });

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

async function applyWith(result: Awaited<ReturnType<typeof api.applyBulkLinks>>) {
  vi.spyOn(api, "previewBulkLinks").mockResolvedValue(preview());
  vi.spyOn(api, "applyBulkLinks").mockResolvedValue(result);
  render(<BulkAssign supplier={sup()} onDone={() => undefined} />);
  fireEvent.change(screen.getByLabelText("Lista de SKU (uno por línea)"), { target: { value: "SYN-000001\nSYN-000002" } });
  fireEvent.click(screen.getByRole("button", { name: "Vista previa" }));
  fireEvent.click(await screen.findByRole("button", { name: "Aplicar asignación" }));
}

describe("bulk assignment outcome per product", () => {
  it("lists every SKU with its outcome in Spanish", async () => {
    await applyWith({
      changed: 1, skipped_conflicts: 1, no_cost: 1,
      rows: [
        { sku: "SYN-000001", outcome: "already_linked" }, { sku: "SYN-000002", outcome: "linked" },
        { sku: "SYN-000003", outcome: "conflict_skipped" }, { sku: "SYN-000004", outcome: "no_cost" },
      ],
    });
    const table = await screen.findByRole("table", { name: "Resultado por producto" });
    const rows = within(table).getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell").map((c) => c.textContent));
    expect(rows).toEqual([
      ["SYN-000001", "Ya estaba asignado"], ["SYN-000002", "Asignado"], ["SYN-000003", "Omitido por conflicto"], ["SYN-000004", "Sin coste utilizable"],
    ]);
  });

  it("still shows the summary sentence", async () => {
    await applyWith({ changed: 2, skipped_conflicts: 0, no_cost: 0, rows: [{ sku: "SYN-000001", outcome: "linked" }, { sku: "SYN-000002", outcome: "linked" }] });
    expect(await screen.findByText(/Se asignaron 2 productos/)).toBeTruthy();
  });

  it("shows no table when an older server sends no rows", async () => {
    await applyWith({ changed: 2, skipped_conflicts: 0, no_cost: 0 });
    expect(await screen.findByText(/Se asignaron 2 productos/)).toBeTruthy();
    await waitFor(() => expect(screen.queryByRole("table", { name: "Resultado por producto" })).toBeNull());
  });
});
