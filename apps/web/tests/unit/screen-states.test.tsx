// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../../src/api/client";
import { AuditScreen } from "../../src/features/admin/AuditScreen";
import "../../src/i18n";

// T011 (feature 012, FR-011): every data screen has loading, empty and error states with a retry.

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const featuresDir = join(__dirname, "..", "..", "src", "features");

/** Screens that handle their own state on purpose. A name may only leave this list. */
const OWN_STATE_SCREENS: Record<string, string> = {
  "localload/LocalLoadScreen.tsx": "local-only loader: state is per file kind (busy, error, empty) and the screen is absent in cloud",
};

function screens(): string[] {
  return readdirSync(featuresDir, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .flatMap((d) => readdirSync(join(featuresDir, d.name)).filter((f) => f.endsWith("Screen.tsx")).map((f) => `${d.name}/${f}`));
}

describe("every screen presents its states through the shared component", () => {
  it.each(screens())("%s uses ScreenState (or is a documented exception)", (rel) => {
    const source = readFileSync(join(featuresDir, rel), "utf8");
    if (OWN_STATE_SCREENS[rel]) return;
    expect(source.includes("ScreenState"), `${rel} must render loading, empty and error through ui/ScreenState`).toBe(true);
  });

  it("documented exceptions still exist and still bypass the shared component", () => {
    for (const rel of Object.keys(OWN_STATE_SCREENS)) {
      expect(screens()).toContain(rel);
      expect(readFileSync(join(featuresDir, rel), "utf8").includes("ScreenState"), `${rel} now uses ScreenState: remove it from the exceptions`).toBe(false);
    }
  });
});

describe("AuditScreen states (Spanish)", () => {
  it("shows a placeholder while loading", () => {
    vi.spyOn(api, "getAudit").mockReturnValue(new Promise(() => undefined));
    render(<AuditScreen />);
    expect(screen.getByRole("status").getAttribute("aria-label")).toBe("Cargando datos");
  });

  it("shows a Spanish error with a working retry", async () => {
    const get = vi.spyOn(api, "getAudit").mockRejectedValueOnce(new ApiError(500, "internal_error")).mockResolvedValue({ items: [], next_cursor: null });
    render(<AuditScreen />);
    expect((await screen.findByRole("alert")).textContent).toContain("No se han podido cargar los datos");
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("No hay entradas para estos filtros.")).toBeTruthy();
  });
});
