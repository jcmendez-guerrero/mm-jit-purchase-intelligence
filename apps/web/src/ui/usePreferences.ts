import { useSyncExternalStore } from "react";

export type Appearance = "system" | "light" | "dark";
export type Density = "comfortable" | "compact";
export interface Preferences {
  appearance: Appearance;
  density: Density;
}

export const APPEARANCE_KEY = "mmi.ui.appearance";
export const DENSITY_KEY = "mmi.ui.density";

const APPEARANCES: readonly Appearance[] = ["system", "light", "dark"];
const DENSITIES: readonly Density[] = ["comfortable", "compact"];

function read<T extends string>(storage: Storage | undefined, key: string, allowed: readonly T[], fallback: T): T {
  try {
    const value = storage?.getItem(key);
    return allowed.includes(value as T) ? (value as T) : fallback;
  } catch {
    return fallback;
  }
}

/** Browser-local UI preferences (contracts §3). No other storage, no business or personal data. */
export function createPreferencesStore(storage: Storage | undefined) {
  let state: Preferences = {
    appearance: read(storage, APPEARANCE_KEY, APPEARANCES, "system"),
    density: read(storage, DENSITY_KEY, DENSITIES, "comfortable"),
  };
  const listeners = new Set<() => void>();

  const persist = (key: string, value: string) => {
    try {
      storage?.setItem(key, value);
    } catch {
      /* storage blocked: keep the choice for this page view only */
    }
  };
  const emit = () => listeners.forEach((l) => l());

  return {
    get: (): Preferences => state,
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    setAppearance(value: Appearance) {
      if (!APPEARANCES.includes(value)) return;
      state = { ...state, appearance: value };
      persist(APPEARANCE_KEY, value);
      emit();
    },
    setDensity(value: Density) {
      if (!DENSITIES.includes(value)) return;
      state = { ...state, density: value };
      persist(DENSITY_KEY, value);
      emit();
    },
  };
}

function browserStorage(): Storage | undefined {
  try {
    return typeof window !== "undefined" ? window.localStorage : undefined;
  } catch {
    return undefined;
  }
}

export const preferencesStore = createPreferencesStore(browserStorage());

export function usePreferences() {
  const prefs = useSyncExternalStore(preferencesStore.subscribe, preferencesStore.get, preferencesStore.get);
  return { ...prefs, setAppearance: preferencesStore.setAppearance, setDensity: preferencesStore.setDensity };
}
