import React from "react";
import { useTranslation } from "react-i18next";
import { usePreferences, type Density } from "./usePreferences";

/** Comfortable / compact row density, stored in the browser (FR-010). */
export const DensityToggle: React.FC = () => {
  const { t } = useTranslation();
  const { density, setDensity } = usePreferences();
  const options: Density[] = ["comfortable", "compact"];
  return (
    <div role="group" aria-label={t("ui.table.density")} className="mmi-segmented">
      {options.map((o) => (
        <button key={o} type="button" aria-pressed={density === o} className="mmi-segmented__option" onClick={() => setDensity(o)}>
          {t(`ui.table.density_${o}`)}
        </button>
      ))}
    </div>
  );
};
