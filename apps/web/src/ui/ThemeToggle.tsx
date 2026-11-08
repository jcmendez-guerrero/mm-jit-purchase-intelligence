import React from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";
import { usePreferences, type Appearance } from "./usePreferences";

const OPTIONS: Array<{ id: Appearance; icon?: "sun" | "moon" }> = [{ id: "system" }, { id: "light", icon: "sun" }, { id: "dark", icon: "moon" }];

/** Light, dark or follow the device; the choice is kept in this browser (FR-024). */
export const ThemeToggle: React.FC = () => {
  const { t } = useTranslation();
  const { appearance, setAppearance } = usePreferences();
  return (
    <div role="group" aria-label={t("ui.appearance.label")} className="mmi-segmented">
      {OPTIONS.map((o) => (
        <button key={o.id} type="button" aria-pressed={appearance === o.id} className="mmi-segmented__option" onClick={() => setAppearance(o.id)}>
          {o.icon && <Icon name={o.icon} />}
          {t(`ui.appearance.${o.id}`)}
        </button>
      ))}
    </div>
  );
};
