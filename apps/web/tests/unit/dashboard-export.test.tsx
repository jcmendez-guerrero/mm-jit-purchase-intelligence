// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../../src/api/client";
import { canExportDashboard, ExportButton } from "../../src/features/dashboard/ExportButton";
import "../../src/i18n";

let downloads: string[];

beforeEach(() => {
  downloads = [];
  URL.createObjectURL = vi.fn(() => "blob:synthetic");
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    downloads.push(this.download);
  });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const show = () => render(<ExportButton view={{ kind: "cards" }} filters={{ supplier_id: "sup-a" }} label="Exportar indicadores" />);

describe("export button", () => {
  it("only roles that may see costs are offered the export", () => {
    expect(["buyer", "approver", "admin"].every((r) => canExportDashboard([r]))).toBe(true);
    expect(canExportDashboard(["viewer"])).toBe(false);
    expect(canExportDashboard(undefined)).toBe(false);
  });

  it("downloads the file under the name the server gave and says how many rows it has", async () => {
    const spy = vi.spyOn(api, "exportDashboard").mockResolvedValue({ blob: new Blob(["x"]), filename: "panel-cards-20261109.csv", rows: 6 });
    show();
    fireEvent.click(screen.getByRole("button", { name: "Exportar indicadores" }));
    await screen.findByText("Archivo descargado: 6 filas.");
    expect(downloads).toEqual(["panel-cards-20261109.csv"]);
    expect(spy).toHaveBeenCalledWith({ kind: "cards" }, { supplier_id: "sup-a" });
  });

  it("says the file is being prepared and blocks a second click meanwhile", async () => {
    let finish: (v: { blob: Blob; filename: string; rows: number }) => void = () => {};
    vi.spyOn(api, "exportDashboard").mockReturnValue(new Promise((r) => (finish = r)));
    show();
    fireEvent.click(screen.getByRole("button", { name: "Exportar indicadores" }));
    await screen.findByText("Preparando el archivo…");
    expect((screen.getByRole("button", { name: "Exportar indicadores" }) as HTMLButtonElement).disabled).toBe(true);
    finish({ blob: new Blob(["x"]), filename: "a.csv", rows: 1 });
    await screen.findByText("Archivo descargado: 1 filas.");
  });

  it.each([
    [new ApiError(413, "export_too_large"), "El resultado es demasiado grande para exportarlo: acota los filtros o el periodo."],
    [new ApiError(403, "auth_forbidden_role"), "Tu rol no puede exportar datos."],
    [new ApiError(400, "format_unsupported"), "Solo se puede exportar en CSV."],
    [new ApiError(502, "unknown"), "No se ha podido preparar el archivo. Inténtalo de nuevo."],
  ])("explains a refusal in Spanish and downloads nothing (%#)", async (error, message) => {
    vi.spyOn(api, "exportDashboard").mockRejectedValue(error);
    show();
    fireEvent.click(screen.getByRole("button", { name: "Exportar indicadores" }));
    await screen.findByText(message);
    expect(downloads).toEqual([]);
  });
});
