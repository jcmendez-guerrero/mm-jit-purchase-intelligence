// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, DashboardFreshness } from "../../src/api/client";
import { TrustBanner } from "../../src/features/dashboard/TrustBanner";
import { latestRefresh, NEWER_DATA_POLL_MS, useNewerDataNotice } from "../../src/features/dashboard/useNewerDataNotice";
import "../../src/i18n";

const fresh = (refreshed: string | null, over: Partial<DashboardFreshness> = {}): DashboardFreshness => ({
  sources: [{ source: "inventory_snapshot", refreshed_at: refreshed, refreshed_at_original: null, origin: "erp_sync", state: refreshed ? "ok" : "no_data", stale_after_hours: 48 }],
  excluded_records: 0,
  local_load_excluded: 0,
  review_list_link: "/calidad",
  ...over,
});

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

/** A stand-in for the screen: the "figures" are whatever was loaded last, and only the button reloads them. */
const Harness: React.FC<{ onReload: () => void }> = ({ onReload }) => {
  const [loaded, setLoaded] = React.useState(1);
  const { newer, loadedAt } = useNewerDataNotice(loaded);
  return (
    <div>
      <p data-testid="figures">figures v{loaded}</p>
      <p data-testid="loaded-at">{loadedAt ?? "none"}</p>
      {newer && (
        <button
          onClick={() => {
            onReload();
            setLoaded((n) => n + 1);
          }}
        >
          Actualizar
        </button>
      )}
    </div>
  );
};

describe("newer data notice", () => {
  it("picks the newest refresh time and none when there is no data", () => {
    expect(latestRefresh(fresh("2026-11-09T08:00:00Z"))).toBe("2026-11-09T08:00:00Z");
    expect(latestRefresh(fresh(null))).toBeNull();
    const two = fresh("2026-11-09T08:00:00Z");
    two.sources.push({ ...two.sources[0]!, source: "movements", refreshed_at: "2026-11-10T08:00:00Z" });
    expect(latestRefresh(two)).toBe("2026-11-10T08:00:00Z");
  });

  it("offers newer data once something newer than what was loaded exists, and the figures stay as they are until the user accepts", async () => {
    const spy = vi.spyOn(api, "getDashboardFreshness").mockResolvedValue(fresh("2026-11-09T08:00:00Z"));
    const reload = vi.fn();
    render(<Harness onReload={reload} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(NEWER_DATA_POLL_MS);
    });
    expect(screen.queryByRole("button", { name: "Actualizar" })).toBeNull();                       // nothing newer yet
    expect(screen.getByTestId("loaded-at").textContent).toBe("2026-11-09T08:00:00Z");                // the time the screen's data was current, for an export's header

    spy.mockResolvedValue(fresh("2026-11-09T09:00:00Z"));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(NEWER_DATA_POLL_MS);
    });
    expect(screen.getByRole("button", { name: "Actualizar" })).toBeTruthy();
    expect(screen.getByTestId("figures").textContent).toBe("figures v1");                           // the figures did not move by themselves

    fireEvent.click(screen.getByRole("button", { name: "Actualizar" }));
    expect(reload).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByTestId("figures").textContent).toBe("figures v2");
    expect(screen.queryByRole("button", { name: "Actualizar" })).toBeNull();                       // the new baseline is what was just loaded
    expect(screen.getByTestId("loaded-at").textContent).toBe("2026-11-09T09:00:00Z");
  });

  it("ignores a failing poll and keeps asking", async () => {
    const spy = vi.spyOn(api, "getDashboardFreshness").mockRejectedValue(new Error("down"));
    render(<Harness onReload={() => {}} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(NEWER_DATA_POLL_MS * 2);
    });
    expect(spy.mock.calls.length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByRole("button", { name: "Actualizar" })).toBeNull();
  });
});

describe("trust banner", () => {
  const show = (f: DashboardFreshness | null, newer = false, onRefresh = () => {}) =>
    render(
      <MemoryRouter>
        <TrustBanner freshness={f} newer={newer} onRefresh={onRefresh} />
      </MemoryRouter>,
    );

  it("says nothing when the data is fresh and nothing was left out", () => {
    const { container } = show(fresh("2026-11-09T08:00:00Z"));
    expect(container.textContent).toBe("");
  });

  it("shows a prominent alert with the last refresh when a source is stale", () => {
    const f = fresh("2026-11-01T08:00:00Z");
    f.sources[0]!.state = "stale";
    show(f);
    expect(screen.getByRole("alert").textContent).toMatch(/Los datos están desactualizados: la última actualización fue el 1\/11\/26, \d{1,2}:\d{2} y debería haber una cada 48 horas/);
  });

  it("counts the records left out and links to the review list; and counts local products kept apart", () => {
    show(fresh("2026-11-09T08:00:00Z", { excluded_records: 4, local_load_excluded: 2 }));
    expect(screen.getByText(/4 registros se han dejado fuera de las cifras/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Revisarlos" }).getAttribute("href")).toBe("/calidad");
    expect(screen.getByText("2 productos de carga local no se suman a las cifras del ERP.")).toBeTruthy();
  });

  it("offers the newer data with a button that reloads and says the figures do not change by themselves", () => {
    const onRefresh = vi.fn();
    show(fresh("2026-11-09T08:00:00Z"), true, onRefresh);
    expect(screen.getByRole("status").textContent).toMatch(/Las cifras no cambian hasta que los cargues/);
    fireEvent.click(screen.getByRole("button", { name: "Actualizar datos" }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});
