// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { APPEARANCE_KEY, DENSITY_KEY, createPreferencesStore } from "../../../src/ui/usePreferences";

/** T004 — contracts/ui-contracts.md §3: two keys, validated values, defaults, nothing else stored. */

beforeEach(() => localStorage.clear());

describe("preference store", () => {
  it("uses the documented keys", () => {
    expect(APPEARANCE_KEY).toBe("mmi.ui.appearance");
    expect(DENSITY_KEY).toBe("mmi.ui.density");
  });

  it("defaults to system appearance and comfortable density", () => {
    const store = createPreferencesStore(localStorage);
    expect(store.get()).toEqual({ appearance: "system", density: "comfortable" });
  });

  it("falls back to defaults for invalid stored values", () => {
    localStorage.setItem(APPEARANCE_KEY, "purple");
    localStorage.setItem(DENSITY_KEY, "tiny");
    expect(createPreferencesStore(localStorage).get()).toEqual({ appearance: "system", density: "comfortable" });
  });

  it("reads valid stored values", () => {
    localStorage.setItem(APPEARANCE_KEY, "dark");
    localStorage.setItem(DENSITY_KEY, "compact");
    expect(createPreferencesStore(localStorage).get()).toEqual({ appearance: "dark", density: "compact" });
  });

  it("persists changes, notifies subscribers and ignores invalid values", () => {
    const store = createPreferencesStore(localStorage);
    const seen = vi.fn();
    const off = store.subscribe(seen);
    store.setAppearance("light");
    store.setDensity("compact");
    // @ts-expect-error invalid on purpose
    store.setAppearance("neon");
    expect(localStorage.getItem(APPEARANCE_KEY)).toBe("light");
    expect(localStorage.getItem(DENSITY_KEY)).toBe("compact");
    expect(seen).toHaveBeenCalledTimes(2);
    off();
    store.setDensity("comfortable");
    expect(seen).toHaveBeenCalledTimes(2);
  });

  it("writes no other storage keys", () => {
    const store = createPreferencesStore(localStorage);
    store.setAppearance("dark");
    store.setDensity("compact");
    expect(Object.keys(localStorage).sort()).toEqual([APPEARANCE_KEY, DENSITY_KEY].sort());
  });

  it("keeps working when storage is unavailable", () => {
    const broken = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } } as unknown as Storage;
    const store = createPreferencesStore(broken);
    expect(store.get().appearance).toBe("system");
    store.setAppearance("dark");
    expect(store.get().appearance).toBe("dark");
  });
});
