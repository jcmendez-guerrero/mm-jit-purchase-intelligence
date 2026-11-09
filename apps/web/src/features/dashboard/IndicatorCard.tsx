import React, { useId } from "react";
import { useTranslation } from "react-i18next";
import type { Indicator } from "../../api/client";
import { formatCurrencyEUR, formatDate, formatDateTime, formatNumber } from "../../i18n/formatters";
import { Button } from "../../ui/Button";

interface Props {
  indicator: Indicator;
  /** The date range the figure covers, when the screen has one. */
  period?: { from: string; to: string } | undefined;
  /** Opens the products behind the figure; offered only when there is a figure. */
  onDrill?: (() => void) | undefined;
}

const DECIMALS: Record<Indicator["unit"], number> = { EUR: 2, days: 1, units: 0, count: 0, percent: 1 };
const day = (d: string) => formatDate(`${d}T12:00:00`);          // noon, so the local date never shifts

/** One indicator: the figure in es-ES, what it rests on, where and when it came from, and what it leaves out. Every state is told in words. */
export const IndicatorCard: React.FC<Props> = ({ indicator: i, period, onDrill }) => {
  const { t } = useTranslation();
  const titleId = useId();
  const show = (value: string): string => (i.unit === "EUR" ? formatCurrencyEUR(value) : t(`dashboard.ind.${i.unit}`, { n: formatNumber(value, DECIMALS[i.unit]) }));
  const hasFigure = i.value !== null && (i.state === "ok" || i.state === "stale");
  const hidden = i.state === "hidden_by_role";
  const unsupported = (i.filters_unsupported ?? []).map((f) => t(f === "date" ? "dashboard.filter.days" : `dashboard.filter.${f}`)).join(", ");

  return (
    <article className="mmi-figure" aria-labelledby={titleId}>
      <h3 id={titleId} className="mmi-figure__label">
        {t(`dashboard.ind.title.${i.key}`)}
      </h3>
      {hasFigure && <p className="mmi-figure__value">{show(i.value as string)}</p>}
      {hidden && <p className="mmi-figure__value">{t("dashboard.kpi.hidden_by_role")}</p>}
      {i.state === "no_data" && <p className="mmi-figure__value">{t("dashboard.ind.state.no_data")}</p>}
      {i.state === "error" && <p role="alert">{t("dashboard.ind.state.error")}</p>}
      {i.state === "stale" && <p className="mmi-figure__note">{t("dashboard.ind.state.stale")}</p>}
      {!hidden && (
        <>
          <p className="mmi-figure__note">{t(i.basis)}</p>
          {period && <p className="mmi-figure__note">{t("dashboard.ind.period", { from: day(period.from), to: day(period.to) })}</p>}
          <p className="mmi-figure__note">
            {i.freshness.refreshed_at ? t("dashboard.ind.refreshed", { when: formatDateTime(i.freshness.refreshed_at) }) : t("dashboard.ind.refreshed_none")} · {t(`dashboard.ind.origin.${i.freshness.origin}`)}
          </p>
        </>
      )}
      {hasFigure && i.parts && i.parts.length > 0 && (
        <ul aria-label={t("dashboard.ind.parts")}>
          {i.parts.map((p, n) => (
            <li key={`${p.key}-${n}`}>
              {t(p.label_key)}: {p.value === null ? t("dashboard.ind.state.no_data") : show(p.value)}
              {p.period ? ` (${day(p.period.from)} – ${day(p.period.to)})` : ""}
            </li>
          ))}
        </ul>
      )}
      {!hidden && i.incomplete_count !== undefined && i.incomplete_count > 0 && <p className="mmi-figure__note">{t("dashboard.ind.incomplete", { n: i.incomplete_count })}</p>}
      {unsupported && <p className="mmi-figure__note">{t("dashboard.ind.unsupported", { filters: unsupported })}</p>}
      <details>
        <summary>{t("dashboard.ind.definition")}</summary>
        <p>{t(i.definition_key)}</p>
      </details>
      {hasFigure && onDrill && (
        <Button variant="secondary" small onClick={onDrill}>
          {t("dashboard.drill.view")}
        </Button>
      )}
    </article>
  );
};
