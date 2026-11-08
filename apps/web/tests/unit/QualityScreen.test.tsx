// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../src/api/client";
import { QualityScreen } from "../../src/features/quality/QualityScreen";
import { formatDateTime } from "../../src/i18n/formatters";
import "../../src/i18n";
import { confirmAction } from "./confirm";

const item = { id: 7, variant_id: 42, movement_reason_raw: "Ajuste", anomaly_codes: ["negative_quantity"], created_at: "2026-11-01T10:30:00Z" };

beforeEach(() => {
  vi.spyOn(api, "getImportErrors").mockResolvedValue({ count: 1, items: [item] });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("QualityScreen decisions", () => {
  it("shows the creation time with the shared es-ES formatter", async () => {
    render(<QualityScreen userRoles={["viewer", "buyer"]} />);
    expect(await screen.findByText(formatDateTime(item.created_at))).toBeTruthy();
  });

  it("asks before ignoring a quarantined movement, names it, and sends nothing on cancel", async () => {
    const spy = vi.spyOn(api, "resolveImportError").mockResolvedValue();
    render(<QualityScreen userRoles={["viewer", "buyer"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Descartar / Ignorar" }));
    const dialog = screen.getByRole("dialog", { name: "Ignorar el movimiento retenido" });
    expect(dialog.textContent).toContain("Variante #42");
    expect(dialog.textContent).toContain("no se deshace desde esta pantalla");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancelar" }));
    expect(spy).not.toHaveBeenCalled();
    expect(screen.getByText("#7")).toBeTruthy();
  });

  it("sends the same decision on confirm and removes the row", async () => {
    const spy = vi.spyOn(api, "resolveImportError").mockResolvedValue();
    render(<QualityScreen userRoles={["viewer", "buyer"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Descartar / Ignorar" }));
    confirmAction();
    await waitFor(() => expect(spy).toHaveBeenCalledWith(7, "ignore"));
    await waitFor(() => expect(screen.queryByText("#7")).toBeNull());
  });

  it("asks before releasing too", async () => {
    const spy = vi.spyOn(api, "resolveImportError").mockResolvedValue();
    render(<QualityScreen userRoles={["viewer", "admin"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Liberar movimiento" }));
    expect(screen.getByRole("dialog", { name: "Confirmar el movimiento retenido" })).toBeTruthy();
    confirmAction();
    await waitFor(() => expect(spy).toHaveBeenCalledWith(7, "release"));
  });

  it("offers no decision buttons to a viewer", async () => {
    render(<QualityScreen userRoles={["viewer"]} />);
    await screen.findByText("#7");
    expect(screen.queryByRole("button", { name: "Descartar / Ignorar" })).toBeNull();
  });
});
