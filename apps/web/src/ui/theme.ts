import { preferencesStore, type Appearance } from "./usePreferences";

export type Theme = "light" | "dark";

const QUERY = "(prefers-color-scheme: dark)";

export function resolveTheme(appearance: Appearance, prefersDark: boolean): Theme {
  if (appearance === "light" || appearance === "dark") return appearance;
  return prefersDark ? "dark" : "light";
}

function devicePrefersDark(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(QUERY).matches;
}

export function applyTheme(root: HTMLElement = document.documentElement): void {
  root.setAttribute("data-theme", resolveTheme(preferencesStore.get().appearance, devicePrefersDark()));
}

/**
 * Keeps data-theme in step with the saved choice and, for "system", with the device. public/theme-init.js sets the
 * first value before paint; this takes over once the app runs. Returns a function that stops the sync.
 */
export function startThemeSync(): () => void {
  applyTheme();
  const off = preferencesStore.subscribe(() => applyTheme());
  const mq = typeof window !== "undefined" && typeof window.matchMedia === "function" ? window.matchMedia(QUERY) : null;
  const onChange = () => applyTheme();
  mq?.addEventListener?.("change", onChange);
  return () => {
    off();
    mq?.removeEventListener?.("change", onChange);
  };
}
