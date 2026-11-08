// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ThemeToggle } from "../../../src/ui/ThemeToggle";
import { resolveTheme, startThemeSync } from "../../../src/ui/theme";
import { preferencesStore } from "../../../src/ui/usePreferences";
import "../../../src/i18n";

/** T064 — appearance control: three labelled options, persisted, applied to the document; "system" follows the device. */

let prefersDark = false;
let listener: (() => void) | null = null;
let stop: () => void;

beforeEach(() => {
  localStorage.clear();
  prefersDark = false;
  listener = null;
  vi.stubGlobal("matchMedia", (q: string) => ({
    matches: q.includes("dark") ? prefersDark : false,
    addEventListener: (_: string, l: () => void) => (listener = l),
    removeEventListener: () => (listener = null),
  }));
  document.documentElement.removeAttribute("data-theme");
  preferencesStore.setAppearance("system");
  stop = startThemeSync();
});
afterEach(() => {
  stop();
  cleanup();
  vi.unstubAllGlobals();
});

describe("resolveTheme", () => {
  it("follows the device for system and obeys an explicit choice", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });
});

describe("ThemeToggle", () => {
  it("offers system, light and dark as a labelled group with the current one pressed", () => {
    render(<ThemeToggle />);
    const group = screen.getByRole("group", { name: "Apariencia" });
    expect(group).toBeTruthy();
    expect(screen.getByRole("button", { name: "Sistema" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Claro" }).getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByRole("button", { name: "Oscuro" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("persists the choice and applies data-theme", () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Oscuro" }));
    expect(localStorage.getItem("mmi.ui.appearance")).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(screen.getByRole("button", { name: "Oscuro" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Claro" }));
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("system follows the device, including a change while the app is open", () => {
    prefersDark = true;
    stop();
    stop = startThemeSync();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    prefersDark = false;
    act(() => listener?.());
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("an explicit choice ignores the device", () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Claro" }));
    prefersDark = true;
    act(() => listener?.());
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
});
