import React from "react";
import { useTranslation } from "react-i18next";
import { Button } from "./Button";
import { Icon } from "./Icon";

export interface FilterChip {
  key: string;
  /** Already formatted, for example "Almacén: Almacén sintético A". */
  label: string;
  /** Short name used in the remove button's accessible name. */
  name: string;
  onRemove: () => void;
}

interface Props {
  children: React.ReactNode;
  chips?: FilterChip[];
  onClear?: () => void;
}

/** Grouped filter controls with removable chips and a single "clear filters" action (design.md §7). */
export const FilterBar: React.FC<Props> = ({ children, chips = [], onClear }) => {
  const { t } = useTranslation();
  return (
    <>
      <div role="group" aria-label={t("dashboard.filters")} className="mmi-filterbar">
        {children}
        {chips.length > 0 && onClear && (
          <Button variant="quiet" small onClick={onClear}>
            {t("ui.filters.clear")}
          </Button>
        )}
      </div>
      {chips.length > 0 && (
        <ul className="mmi-chips" aria-label={t("ui.filters.label")}>
          {chips.map((c) => (
            <li key={c.key} className="mmi-chip">
              <span id={`chip-${c.key}`}>{c.label}</span>
              <button type="button" aria-label={t("ui.filters.remove")} aria-describedby={`chip-${c.key}`} onClick={c.onRemove}>
                <Icon name="close" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
};
