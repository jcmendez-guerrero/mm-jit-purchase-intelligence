import React from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";
import type { IconName } from "./icons/paths";

export type Severity = "out_of_stock" | "imminent" | "below_reorder_point";
export type SeverityCounts = Record<Severity, number>;

const ORDER: Severity[] = ["out_of_stock", "imminent", "below_reorder_point"];
const ICON: Record<Severity, IconName> = { out_of_stock: "cross", imminent: "warning", below_reorder_point: "info" };

interface Props {
  counts: SeverityCounts;
  /** The summary's stockout total; shown alone when the severity split cannot be trusted. */
  total?: number;
  splitReliable?: boolean;
  active: Severity | null;
  onSelect: (next: Severity | null) => void;
  /** Play the one-time growth (first load of the dashboard only). */
  animate?: boolean;
  /** Quiet action beside the ruler, for example the existing "view products" drill-down. */
  action?: React.ReactNode;
  /** Accessible name of the whole block; defaults to its title. */
  label?: string;
}

/** Stockout severity as one proportional bar (design.md §6). Segments filter the risk list; the table is the full alternative. */
export const SeverityRuler: React.FC<Props> = ({ counts, total, splitReliable = true, active, onSelect, animate, action, label }) => {
  const { t } = useTranslation();
  const present = ORDER.filter((k) => counts[k] > 0);
  const sum = ORDER.reduce((n, k) => n + counts[k], 0);
  const shown = splitReliable ? sum : (total ?? sum);

  return (
    <section className="mmi-ruler-block" {...(label ? { "aria-label": label } : { "aria-labelledby": "ruler-title" })}>
      <div className="mmi-ruler-block__head">
        <h2 id="ruler-title" className="mmi-ruler-block__title">
          {t("ui.ruler.title")}
        </h2>
        {action}
      </div>

      {shown === 0 ? (
        <p className="mmi-ruler-none">
          <Icon name="check" />
          {t("ui.ruler.none")}
        </p>
      ) : !splitReliable ? (
        <p className="mmi-ruler-total">{t("ui.ruler.total_only", { total: shown })}</p>
      ) : (
        <>
          <p className="mmi-visually-hidden">
            {t("ui.ruler.summary", { total: sum, detail: present.map((k) => t("ui.ruler.segment", { count: counts[k], label: t(`ui.severity.${k}`) })).join("; ") })}
          </p>
          <p className="mmi-ruler-total" aria-hidden="true">
            {t("ui.ruler.total_only", { total: sum })}
          </p>
          <ul className={`mmi-ruler${animate ? " mmi-ruler--animate" : ""}`}>
            {present.map((k) => (
              <li key={k} className="mmi-ruler__segment" style={{ flexGrow: counts[k] }}>
                <button
                  type="button"
                  className={`mmi-ruler__bar mmi-ruler__bar--${k}`}
                  aria-pressed={active === k}
                  aria-label={t("ui.ruler.segment", { count: counts[k], label: t(`ui.severity.${k}`) })}
                  onClick={() => onSelect(active === k ? null : k)}
                >
                  <Icon name={ICON[k]} />
                </button>
                <span className="mmi-ruler__caption" aria-hidden="true">
                  <span className="mmi-ruler__count">{counts[k]}</span>
                  <span>{t(`ui.severity.${k}`)}</span>
                </span>
              </li>
            ))}
          </ul>
          {active && (
            <p className="mmi-ruler-filter">
              {t("ui.ruler.filter_active", { label: t(`ui.severity.${active}`) })}{" "}
              <button type="button" className="mmi-link-button" onClick={() => onSelect(null)}>
                {t("ui.ruler.clear")}
              </button>
            </p>
          )}
        </>
      )}
    </section>
  );
};
