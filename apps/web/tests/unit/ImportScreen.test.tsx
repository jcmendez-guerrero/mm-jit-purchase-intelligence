// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, SeedDataset, SeedUpload } from "../../src/api/client";
import { ImportScreen } from "../../src/features/imports/ImportScreen";
import "../../src/i18n";

const upload = (over: Partial<SeedUpload> = {}): SeedUpload => ({
  id: "d1", version: 1, format: "csv", headers: ["ID de variante Siweb", "Fecha", "Cantidad", "Tipo de dato", "Origen", "Sintético/Real", "Notas"], row_count: 5,
  suggested_mapping: { "ID de variante Siweb": "variant_id", Fecha: "day", Cantidad: "quantity", "Tipo de dato": "kind", Origen: "provenance", "Sintético/Real": "origin" },
  missing: [], preview: [{ variant_id: "9001", day: "2026-01-05", quantity: "2", kind: "estimado", provenance: "Hoja sintética A", origin: "sintético" }], duplicate_of: null, ...over,
});
const dataset = (over: Partial<SeedDataset> = {}): SeedDataset => ({ id: "d0", version: 1, name: "x", status: "active", origin: "synthetic", uploader: "buyer-1", uploaded_at: "2026-11-01T00:00:00Z", activated_by: "buyer-1", activated_at: null, accepted: 5, quarantined: 0, kinds: {}, ...over });

const file = (name = "datos.csv", size = 10) => new File([new Uint8Array(size)], name, { type: "text/csv" });
const pick = async (f: File) => fireEvent.change(await screen.findByLabelText("Archivo (CSV o XLSX)"), { target: { files: [f] } });

beforeEach(() => {
  vi.spyOn(api, "getSeedDatasets").mockResolvedValue({ datasets: [] });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ImportScreen", () => {
  it("is read-only for a viewer: the list, no upload", async () => {
    vi.spyOn(api, "getSeedDatasets").mockResolvedValue({ datasets: [dataset()] });
    render(<ImportScreen userRoles={["viewer"]} />);
    expect(await screen.findByText(/Solo lectura/)).toBeTruthy();
    expect(screen.queryByLabelText("Archivo (CSV o XLSX)")).toBeNull();
    expect(screen.queryByRole("button", { name: "Volver a la versión anterior" })).toBeNull();
  });

  it("refuses a wrong type or an oversized file locally without calling the server", async () => {
    const up = vi.spyOn(api, "uploadSeed");
    render(<ImportScreen userRoles={["buyer"]} />);
    await pick(file("datos.xlsm"));
    fireEvent.click(screen.getByRole("button", { name: "Subir archivo" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Solo se admiten archivos .csv y .xlsx");
    await pick(file("datos.csv", 6 * 1024 * 1024));
    fireEvent.click(screen.getByRole("button", { name: "Subir archivo" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("tamaño máximo"));
    expect(up).not.toHaveBeenCalled();
  });

  it("walks the wizard: upload, mapping with unmapped notes, validate, quarantine in Spanish, dry-run, activate", async () => {
    vi.spyOn(api, "uploadSeed").mockResolvedValue(upload());
    const validate = vi.spyOn(api, "validateSeed").mockResolvedValue({ id: "d1", origin: "synthetic", accepted: 4, quarantined: 1, kinds: { estimated: 4 } });
    vi.spyOn(api, "getSeedQuarantine").mockResolvedValue({ rows: [{ row_no: 3, reason_key: "import_unknown_variant", params: {} }] });
    vi.spyOn(api, "dryRunSeed").mockResolvedValue({ dataset_id: "d1", compared_with: null, rows: { added: 4, removed: 0, changed: 0, unchanged: 0 }, variants_gaining_history: [9001], variants_losing_history: [], skipped_sparse: [], backtest: "x" });
    const activate = vi.spyOn(api, "activateSeed").mockResolvedValue({});
    render(<ImportScreen userRoles={["buyer"]} />);
    await pick(file());
    fireEvent.click(screen.getByRole("button", { name: "Subir archivo" }));
    expect(await screen.findByText(/Archivo recibido: 5 filas/)).toBeTruthy();
    expect((screen.getByLabelText("Campo: Notas") as HTMLSelectElement).value).toBe("");           // notes are not mapped
    fireEvent.click(screen.getByRole("button", { name: "Validar" }));
    await waitFor(() => expect(validate).toHaveBeenCalledWith("d1", upload().suggested_mapping));
    expect(await screen.findByText(/Aceptadas: 4 · En cuarentena: 1 · Datos sintéticos/)).toBeTruthy();
    expect(screen.getByText(/Fila 3: La variante no existe en el catálogo/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Descargar cuarentena (CSV)" }).getAttribute("href")).toBe("/api/imports/d1/quarantine?format=csv");
    fireEvent.click(screen.getByRole("button", { name: "Comparar con el conjunto activo" }));
    expect(await screen.findByText(/Filas nuevas 4/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Activar conjunto" }));
    await waitFor(() => expect(activate).toHaveBeenCalledWith("d1", false));
    expect((await screen.findByRole("status")).textContent).toContain("Conjunto activado");
  });

  it("blocks validation while a required field is unmapped and names it", async () => {
    vi.spyOn(api, "uploadSeed").mockResolvedValue(upload());
    render(<ImportScreen userRoles={["admin"]} />);
    await pick(file());
    fireEvent.click(screen.getByRole("button", { name: "Subir archivo" }));
    fireEvent.change(await screen.findByLabelText("Campo: Cantidad"), { target: { value: "" } });
    expect(screen.getByRole("alert").textContent).toContain("Faltan campos obligatorios: Cantidad");
    expect((screen.getByRole("button", { name: "Validar" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("asks for an explicit decision on a repeated file and passes it on", async () => {
    vi.spyOn(api, "uploadSeed").mockResolvedValue(upload({ duplicate_of: "d0" }));
    vi.spyOn(api, "validateSeed").mockResolvedValue({ id: "d1", origin: "synthetic", accepted: 4, quarantined: 0, kinds: {} });
    vi.spyOn(api, "getSeedQuarantine").mockResolvedValue({ rows: [] });
    const activate = vi.spyOn(api, "activateSeed").mockRejectedValueOnce(new ApiError(409, "import_duplicate_file")).mockResolvedValueOnce({});
    render(<ImportScreen userRoles={["buyer"]} />);
    await pick(file());
    fireEvent.click(screen.getByRole("button", { name: "Subir archivo" }));
    expect(await screen.findByText(/Este archivo ya se subió antes/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Validar" }));
    fireEvent.click(await screen.findByRole("button", { name: "Activar conjunto" }));
    expect((await screen.findByRole("alert")).textContent).toContain("archivo");
    fireEvent.click(screen.getByLabelText(/archivo repetido/));
    fireEvent.click(screen.getByRole("button", { name: "Activar conjunto" }));
    await waitFor(() => expect(activate).toHaveBeenLastCalledWith("d1", true));
  });

  it("rolls back the active version", async () => {
    vi.spyOn(api, "getSeedDatasets").mockResolvedValue({ datasets: [dataset({ version: 2 }), dataset({ id: "d9", version: 1, status: "superseded" })] });
    const rb = vi.spyOn(api, "rollbackSeed").mockResolvedValue({});
    render(<ImportScreen userRoles={["buyer"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Volver a la versión anterior" }));
    await waitFor(() => expect(rb).toHaveBeenCalled());
    expect((await screen.findByRole("status")).textContent).toContain("Versión anterior restaurada");
  });
});
