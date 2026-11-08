// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, LocalLoadDifference, LocalLoadResult } from "../../src/api/client";
import { LocalLoadScreen } from "../../src/features/localload/LocalLoadScreen";
import { balanced, canLoad, canUse, fileProblem, MAX_BYTES } from "../../src/features/localload/localLoadModel";
import "../../src/i18n";

const result = (over: Partial<LocalLoadResult> = {}): LocalLoadResult => ({
  run_id: "r1", kind: "inventory", rows: 10, loaded: 7, updated: 1, unchanged: 1, quarantined: 1, excluded: 0, services: 0, differences: 0, review: [],
  interpretations: { tax_included_rows: 2, tax_excluded_rows: 7, timezone: "Europe/Madrid" }, ...over,
});
const file = (name = "inventario.csv", size = 10) => new File([new Uint8Array(size)], name, { type: "text/csv" });
const checkButton = (i: number) => screen.getAllByRole("button", { name: "Comprobar archivo" })[i] as HTMLElement;
const pick = (label: RegExp, f: File) => fireEvent.change(screen.getByLabelText(label), { target: { files: [f] } });

beforeEach(() => {
  vi.spyOn(api, "getLocalLoadReview").mockResolvedValue([]);
  vi.spyOn(api, "getLocalLoadDifferences").mockResolvedValue([]);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("local load model", () => {
  it("accepts csv and xlsx files within the size limit only", () => {
    expect(fileProblem(file("a.csv"))).toBeNull();
    expect(fileProblem(file("a.XLSX"))).toBeNull();
    expect(fileProblem(file("a.xlsm"))).toBe("localLoad.problem.type");
    expect(fileProblem(file("a.csv", MAX_BYTES + 1))).toBe("localLoad.problem.size");
    expect(fileProblem(file("a.csv", 0))).toBe("localLoad.problem.empty");
  });

  it("needs a check first, and the acknowledgement for inventory", () => {
    expect(canLoad("inventory", null, true)).toBe(false);
    expect(canLoad("inventory", result(), false)).toBe(false);
    expect(canLoad("inventory", result(), true)).toBe(true);
    expect(canLoad("movements", result({ kind: "movements" }), false)).toBe(true);
  });

  it("limits the screen to buyers and admins and checks the count balance", () => {
    expect(canUse(["viewer"])).toBe(false);
    expect(canUse(["viewer", "buyer"])).toBe(true);
    expect(canUse(["admin"])).toBe(true);
    expect(balanced(result())).toBe(true);
    expect(balanced(result({ loaded: 3 }))).toBe(false);
  });
});

describe("LocalLoadScreen", () => {
  it("shows nothing actionable to a viewer", () => {
    render(<LocalLoadScreen userRoles={["viewer"]} />);
    expect(screen.getByText("Solo los compradores y administradores pueden cargar datos.")).toBeTruthy();
    expect(screen.queryByLabelText(/Archivo de inventario/)).toBeNull();
  });

  it("refuses a wrong type locally without calling the server", async () => {
    const check = vi.spyOn(api, "checkLocalLoad");
    render(<LocalLoadScreen userRoles={["buyer"]} />);
    pick(/Archivo de inventario/, file("datos.xlsm"));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText("Solo se admiten archivos CSV o XLSX.")).toBeTruthy();
    expect((screen.getAllByRole("button", { name: "Comprobar archivo" })[0] as HTMLButtonElement).disabled).toBe(true);
    expect(check).not.toHaveBeenCalled();
  });

  it("checks, shows the counts and the interpretation, and loads only after the acknowledgement", async () => {
    const check = vi.spyOn(api, "checkLocalLoad").mockResolvedValue(result());
    const run = vi.spyOn(api, "runLocalLoad").mockResolvedValue(result());
    render(<LocalLoadScreen userRoles={["buyer"]} />);
    pick(/Archivo de inventario/, file());
    fireEvent.click(checkButton(1));
    expect(await screen.findByText(/Impuesto incluido en 2 filas y no incluido en 7/)).toBeTruthy();
    expect(check).toHaveBeenCalledWith("inventory", expect.any(File));
    const load = screen.getByRole("button", { name: "Cargar datos" }) as HTMLButtonElement;
    expect(load.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("Confirmo la interpretación de impuestos y precios"));
    expect(load.disabled).toBe(false);
    fireEvent.click(load);
    await waitFor(() => expect(run).toHaveBeenCalledTimes(1));
    expect(run).toHaveBeenCalledWith("inventory", expect.any(File), true, expect.stringMatching(/.+/));
    expect(await screen.findByText("Resultado de la carga")).toBeTruthy();
  });

  it("lists the missing columns when the file has the wrong layout", async () => {
    vi.spyOn(api, "checkLocalLoad").mockRejectedValue(new ApiError(422, "local_load_signature_mismatch", undefined, ["Lote", "Estado"]));
    render(<LocalLoadScreen userRoles={["buyer"]} />);
    pick(/Archivo de inventario/, file());
    fireEvent.click(checkButton(1));
    expect(await screen.findByText(/Faltan:.*Lote, Estado/)).toBeTruthy();
  });

  it("shows the review rows and lets the buyer accept or ignore a difference", async () => {
    const diff: LocalLoadDifference = { id: "d-123", sku: "SYN-000001", field: "reorder_point", app_value: "9", file_value: "5", status: "open" };
    vi.spyOn(api, "getLocalLoadReview").mockResolvedValue([{ kind: "movements", row: 4, code: "unknown_sku", source: "loader" }]);
    vi.spyOn(api, "getLocalLoadDifferences").mockResolvedValue([diff]);
    const decide = vi.spyOn(api, "decideLocalLoadDifference").mockResolvedValue();
    render(<LocalLoadScreen userRoles={["admin"]} />);
    expect(await screen.findByText("SKU no presente en el inventario")).toBeTruthy();
    expect(screen.getByText("SYN-000001")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Usar el del archivo" }));
    await waitFor(() => expect(decide).toHaveBeenCalledWith("d-123", "accept"));
  });

  it("keeps the idempotency key for the same file and uses a new one after another file is chosen", async () => {
    vi.spyOn(api, "checkLocalLoad").mockResolvedValue(result({ kind: "movements" }));
    const run = vi.spyOn(api, "runLocalLoad").mockResolvedValue(result({ kind: "movements" }));
    render(<LocalLoadScreen userRoles={["buyer"]} />);
    const loadOnce = async (expectedCalls: number) => {
      fireEvent.click(checkButton(2));
      fireEvent.click(await screen.findByRole("button", { name: "Cargar datos" }));
      await waitFor(() => expect(run).toHaveBeenCalledTimes(expectedCalls));
    };
    pick(/Archivo de movimientos/, file("m.xlsx"));
    await loadOnce(1);
    await loadOnce(2);                                                    // a retry of the same file
    pick(/Archivo de movimientos/, file("otro.xlsx"));
    await loadOnce(3);
    const keys = run.mock.calls.map((c) => c[3]);
    expect(keys[0]).toBe(keys[1]);
    expect(keys[2]).not.toBe(keys[0]);
  });
});
