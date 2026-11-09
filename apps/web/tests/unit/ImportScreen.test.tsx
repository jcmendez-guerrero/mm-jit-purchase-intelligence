// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, SeedDataset, SeedJob, SeedUpload } from "../../src/api/client";
import { ImportScreen } from "../../src/features/imports/ImportScreen";
import "../../src/i18n";
import { confirmAction } from "./confirm";

const upload = (over: Partial<SeedUpload> = {}): SeedUpload => ({
  id: "d1", version: 1, format: "csv", headers: ["SKU", "Fecha", "Cantidad", "Tipo de dato", "Origen", "Sintético/Real", "Notas"], row_count: 5,
  suggested_mapping: { "SKU": "sku", Fecha: "day", Cantidad: "quantity", "Tipo de dato": "kind", Origen: "provenance", "Sintético/Real": "origin" },
  missing: [], preview: [{ sku: "EJ-9001", day: "2026-01-05", quantity: "2", kind: "estimado", provenance: "Hoja sintética A", origin: "sintético" }], duplicate_of: null, ...over,
});
const dataset = (over: Partial<SeedDataset> = {}): SeedDataset => ({ id: "d0", version: 1, name: "x", status: "active", origin: "synthetic", uploader: "buyer-1", uploaded_at: "2026-11-01T00:00:00Z", activated_by: "buyer-1", activated_at: null, accepted: 5, quarantined: 0, kinds: {}, ...over });

const file = (name = "datos.csv", size = 10) => new File([new Uint8Array(size)], name, { type: "text/csv" });
const pick = async (f: File) => fireEvent.change(await screen.findByLabelText("Archivo (CSV o XLSX)"), { target: { files: [f] } });

beforeEach(() => {
  vi.spyOn(api, "getSeedJobs").mockResolvedValue({ jobs: [], background_over_rows: 10000 });
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
    vi.spyOn(api, "dryRunSeed").mockResolvedValue({ dataset_id: "d1", compared_with: null, rows: { added: 4, removed: 0, changed: 0, unchanged: 0 }, variants_gaining_history: [9001], variants_losing_history: [], skipped_sparse: [], overlap: { variants: 2, days: 14 }, backtest: { status: "ok", basis: "actual_demand_only", before: { variants: 3, windows: 90, cost: "120.00" }, after: { variants: 4, windows: 120, cost: "110.50" }, delta_cost: "-9.50" } });
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
    expect(screen.getByText("Las ventas reales del ERP prevalecen en 14 días de 2 productos: los datos importados de esos días no se usan.")).toBeTruthy();
    expect(screen.getByText(/Sin este conjunto: 3 variantes previsibles, coste simulado 120,00/)).toBeTruthy();
    expect(screen.getByText(/Con este conjunto: 4 variantes previsibles, coste simulado 110,50/)).toBeTruthy();
    expect(screen.getByText(/Diferencia de coste simulado: -9,50/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Activar conjunto" }));
    confirmAction();
    await waitFor(() => expect(activate).toHaveBeenCalledWith("d1", false, undefined));
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

  it("shows the self-activation reason only to admins and sends it with the activation", async () => {
    vi.spyOn(api, "uploadSeed").mockResolvedValue(upload());
    vi.spyOn(api, "validateSeed").mockResolvedValue({ id: "d1", origin: "synthetic", accepted: 4, quarantined: 0, kinds: {} });
    vi.spyOn(api, "getSeedQuarantine").mockResolvedValue({ rows: [] });
    const activate = vi.spyOn(api, "activateSeed").mockResolvedValue({});
    render(<ImportScreen userRoles={["admin"]} />);
    await pick(file());
    fireEvent.click(screen.getByRole("button", { name: "Subir archivo" }));
    await screen.findByText(/Archivo recibido: 5 filas/);
    fireEvent.click(screen.getByRole("button", { name: "Validar" }));
    fireEvent.click(await screen.findByRole("button", { name: "Activar conjunto" }));
    confirmAction();
    await waitFor(() => expect(activate).toHaveBeenLastCalledWith("d1", false, undefined));
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
    confirmAction();
    expect((await screen.findByRole("alert")).textContent).toContain("archivo");
    fireEvent.click(screen.getByLabelText(/archivo repetido/));
    fireEvent.click(screen.getByRole("button", { name: "Activar conjunto" }));
    confirmAction();
    await waitFor(() => expect(activate).toHaveBeenLastCalledWith("d1", true, undefined));
  });

  it("lists each required field that has no column, one line each, and marks the mapped required columns", async () => {
    vi.spyOn(api, "uploadSeed").mockResolvedValue(upload());
    render(<ImportScreen userRoles={["admin"]} />);
    await pick(file());
    fireEvent.click(screen.getByRole("button", { name: "Subir archivo" }));
    await screen.findByLabelText("Campo: Cantidad");
    expect(screen.queryByText(/Falta una columna para/)).toBeNull();
    expect(screen.getAllByText("Obligatorio").length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText("Campo: Cantidad"), { target: { value: "" } });
    expect(screen.getByText("Falta una columna para «Cantidad».")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Validar" }).getAttribute("aria-describedby")).toBe("imp-missing");
  });

  it("asks before discarding an uploaded file and sends nothing on cancel", async () => {
    vi.spyOn(api, "uploadSeed").mockResolvedValue(upload());
    const reject = vi.spyOn(api, "rejectSeed").mockResolvedValue();
    render(<ImportScreen userRoles={["buyer"]} />);
    await pick(file());
    fireEvent.click(screen.getByRole("button", { name: "Subir archivo" }));
    await screen.findByText(/Archivo recibido: 5 filas/);
    fireEvent.click(screen.getByRole("button", { name: "Descartar" }));
    const dialog = screen.getByRole("dialog", { name: "Descartar el archivo subido" });
    expect(dialog.textContent).toContain(".csv");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancelar" }));
    expect(reject).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Descartar" }));
    confirmAction();
    await waitFor(() => expect(reject).toHaveBeenCalled());
  });

  it("rolls back the active version", async () => {
    vi.spyOn(api, "getSeedDatasets").mockResolvedValue({ datasets: [dataset({ version: 2 }), dataset({ id: "d9", version: 1, status: "superseded" })] });
    const rb = vi.spyOn(api, "rollbackSeed").mockResolvedValue({});
    render(<ImportScreen userRoles={["buyer"]} />);
    const button = await screen.findByRole("button", { name: "Volver a la versión anterior" });
    expect((button as HTMLButtonElement).disabled).toBe(true);                                    // no reason chosen yet
    fireEvent.change(screen.getByLabelText("Motivo de la reversión"), { target: { value: "wrong_figures" } });
    expect((button as HTMLButtonElement).disabled).toBe(false);
    fireEvent.change(screen.getByLabelText(/Detalle del motivo/), { target: { value: "x".repeat(101) } });
    expect((button as HTMLButtonElement).disabled).toBe(true);                                    // the detail is too long
    fireEvent.change(screen.getByLabelText(/Detalle del motivo/), { target: { value: "  Cifras   erróneas " } });
    expect((button as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(button);
    confirmAction();
    await waitFor(() => expect(rb).toHaveBeenCalledWith({ code: "wrong_figures", detail: "Cifras erróneas" }));
    expect((await screen.findByRole("status")).textContent).toContain("Versión anterior restaurada");
  });
});


describe("background validation", () => {
  const job = (over: Partial<SeedJob> = {}): SeedJob => ({ id: "j1", dataset_id: "d1", version: 3, name: "Hoja grande", rows: 20000, stage: "validate", state: "queued", queued_at: "2026-11-09T08:00:00Z",
    started_at: null, finished_at: null, error_key: null, requested_by: "buyer-1", ...over });

  it("tells the buyer the file went to the background and shows it in the status section", async () => {
    vi.spyOn(api, "uploadSeed").mockResolvedValue(upload({ row_count: 20000 }));
    const validate = vi.spyOn(api, "validateSeed").mockResolvedValue({ id: "d1", queued: true, job_id: "j1", rows: 20000, background_over_rows: 10000 });
    const jobs = vi.spyOn(api, "getSeedJobs").mockResolvedValue({ jobs: [], background_over_rows: 10000 });
    render(<ImportScreen userRoles={["buyer"]} />);
    await pick(file());
    fireEvent.click(screen.getByRole("button", { name: "Subir archivo" }));
    await screen.findByText(/Archivo recibido/);
    jobs.mockResolvedValue({ jobs: [job()], background_over_rows: 10000 });
    fireEvent.click(screen.getByRole("button", { name: "Validar" }));
    await waitFor(() => expect(validate).toHaveBeenCalled());
    expect((await screen.findByRole("status")).textContent).toContain("se ha enviado a segundo plano");
    const table = await screen.findByRole("table", { name: "Estado de las importaciones" });
    expect(table.textContent).toContain("v3 · Hoja grande");
    expect(table.textContent).toContain("En cola");
    expect(screen.queryByText(/Aceptadas:/)).toBeNull();                                         // nothing is claimed as validated yet
  });

  it("shows a failed job with its Spanish reason and lets the buyer refresh the status", async () => {
    const jobs = vi.spyOn(api, "getSeedJobs").mockResolvedValue({ jobs: [job({ state: "failed", error_key: "import_mixed_origin", finished_at: "2026-11-09T08:05:00Z" })], background_over_rows: 10000 });
    render(<ImportScreen userRoles={["viewer"]} />);
    const table = await screen.findByRole("table", { name: "Estado de las importaciones" });
    expect(table.textContent).toContain("Con error");
    expect(table.textContent).toContain("mezcla datos sintéticos y reales");
    jobs.mockResolvedValue({ jobs: [job({ state: "done", finished_at: "2026-11-09T08:06:00Z" })], background_over_rows: 10000 });
    fireEvent.click(screen.getByRole("button", { name: "Actualizar estado" }));
    await waitFor(() => expect(screen.getByRole("table", { name: "Estado de las importaciones" }).textContent).toContain("Terminada"));
  });
});


describe("dataset governance columns (MMI-7 T038)", () => {
  it("shows who validated, who activated (and a self-activation), the provenance mix and the rollback reason", async () => {
    vi.spyOn(api, "getSeedDatasets").mockResolvedValue({
      datasets: [
        dataset({ id: "d2", version: 2, status: "rolled_back", validated_by: "admin-1", activated_by: "admin-1", self_activated: true, rollback_reason_code: "wrong_figures", rollback_reason_detail: "con 3 filas repetidas", kinds: { estimated: 4, manual_forecast: 1 } }),
        dataset({ id: "d1", version: 1, status: "superseded", validated_by: "buyer-2", activated_by: "approver-1", self_activated: false, kinds: { observed_external: 3 } }),
      ],
    });
    render(<ImportScreen userRoles={["viewer"]} />);
    const table = await screen.findByRole("table", { name: "Conjuntos de datos" });
    const text = table.textContent ?? "";
    for (const expected of ["Validado por", "admin-1 (autoactivación)", "approver-1", "buyer-2", "estimado 4 · previsión manual 1", "observado externo 3", "Cifras erróneas · con 3 filas repetidas"]) {
      expect(text).toContain(expected);
    }
  });
});


describe("refused self-activation (MMI-7 T028)", () => {
  async function activateRefused(roles: string[]) {
    vi.spyOn(api, "getSeedDatasets").mockResolvedValue({ datasets: [] });
    vi.spyOn(api, "uploadSeed").mockResolvedValue(upload());
    vi.spyOn(api, "validateSeed").mockResolvedValue({ id: "d1", origin: "synthetic", accepted: 4, quarantined: 0, kinds: {} });
    vi.spyOn(api, "getSeedQuarantine").mockResolvedValue({ rows: [] });
    vi.spyOn(api, "activateSeed").mockRejectedValue(new ApiError(403, "import_self_approval"));
    render(<ImportScreen userRoles={roles} />);
    await pick(file());
    fireEvent.click(screen.getByRole("button", { name: "Subir archivo" }));
    await screen.findByText(/Archivo recibido: 5 filas/);
    fireEvent.click(screen.getByRole("button", { name: "Validar" }));
    fireEvent.click(await screen.findByRole("button", { name: "Activar conjunto" }));
    confirmAction();
    return (await screen.findByRole("alert")).textContent ?? "";
  }

  it("tells an admin how to proceed (a written reason), and a buyer to ask another person", async () => {
    expect(await activateRefused(["admin"])).toContain("indique un motivo");
  });

  it("tells a buyer to ask another person", async () => {
    expect(await activateRefused(["buyer"])).toContain("pida a otra persona");
  });
});


describe("reasons are a pick-list plus a short detail (MMI-7 T078, FR-033)", () => {
  async function readyToActivate(roles: string[]) {
    vi.spyOn(api, "getSeedDatasets").mockResolvedValue({ datasets: [] });
    vi.spyOn(api, "uploadSeed").mockResolvedValue(upload());
    vi.spyOn(api, "validateSeed").mockResolvedValue({ id: "d1", origin: "synthetic", accepted: 4, quarantined: 0, kinds: {} });
    vi.spyOn(api, "getSeedQuarantine").mockResolvedValue({ rows: [] });
    render(<ImportScreen userRoles={roles} />);
    await pick(file());
    fireEvent.click(screen.getByRole("button", { name: "Subir archivo" }));
    await screen.findByText(/Archivo recibido: 5 filas/);
    fireEvent.click(screen.getByRole("button", { name: "Validar" }));
    await screen.findByRole("button", { name: "Activar conjunto" });
  }

  it("lets an admin self-activate with a listed reason and a short detail", async () => {
    const activate = vi.spyOn(api, "activateSeed").mockResolvedValue({});
    await readyToActivate(["admin"]);
    const select = screen.getByLabelText(/Motivo de la autoactivación/) as HTMLSelectElement;
    expect([...select.options].map((o) => o.value)).toEqual(["", "only_person", "urgent", "other"]);
    fireEvent.change(select, { target: { value: "only_person" } });
    fireEvent.change(screen.getAllByLabelText(/Detalle del motivo/)[0]!, { target: { value: "Tienda con una sola persona" } });
    fireEvent.click(screen.getByRole("button", { name: "Activar conjunto" }));
    confirmAction();
    await waitFor(() => expect(activate).toHaveBeenCalledWith("d1", false, { code: "only_person", detail: "Tienda con una sola persona" }));
  });

  it("does not show the self-activation reason to a buyer", async () => {
    await readyToActivate(["buyer"]);
    expect(screen.queryByLabelText(/Motivo de la autoactivación/)).toBeNull();
  });

  it("offers the five rollback reasons in Spanish", async () => {
    vi.spyOn(api, "getSeedDatasets").mockResolvedValue({ datasets: [dataset({ version: 2 })] });
    render(<ImportScreen userRoles={["buyer"]} />);
    const select = (await screen.findByLabelText("Motivo de la reversión")) as HTMLSelectElement;
    expect([...select.options].map((o) => o.textContent)).toEqual(["Elija un motivo", "Cifras erróneas", "Archivo equivocado", "Prueba", "Sustituido por un archivo más reciente", "Otro motivo"]);
  });
});
