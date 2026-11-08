import { useEffect, useState } from "react";
import { preferencesStore } from "./usePreferences";

export interface ChartColors {
  /** Main data series (actuals, bars). */
  primary: string;
  /** Forecast and secondary series. */
  secondary: string;
  grid: string;
}

const NAMES: Record<keyof ChartColors, string> = { primary: "--mmi-primary", secondary: "--mmi-text-note", grid: "--mmi-border" };

function read(): ChartColors {
  const style = typeof document !== "undefined" ? getComputedStyle(document.documentElement) : undefined;
  const get = (k: keyof ChartColors) => style?.getPropertyValue(NAMES[k]).trim() || `var(${NAMES[k]})`;
  return { primary: get("primary"), secondary: get("secondary"), grid: get("grid") };
}

/** Chart colours come from the design tokens, so charts follow the theme instead of carrying their own literals. */
export function useChartColors(): ChartColors {
  const [colors, setColors] = useState<ChartColors>(read);
  useEffect(() => {
    const update = () => setColors(read());
    update();
    const off = preferencesStore.subscribe(update);
    const mq = typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    mq?.addEventListener?.("change", update);
    return () => {
      off();
      mq?.removeEventListener?.("change", update);
    };
  }, []);
  return colors;
}
