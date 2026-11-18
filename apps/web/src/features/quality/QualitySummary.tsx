import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { AnomalyFlag, QualitySummaryData, api, errorMessage } from "../../api/client";
import { formatDate, formatDateTime, formatPercent } from "../../i18n/formatters";
import { Button } from "../../ui/Button";
import { ConfirmDialog } from "../../ui/ConfirmDialog";
import { DataTable, type Column } from "../../ui/DataTable";
import { EmptyState } from "../../ui/EmptyState";
import { FormField } from "../../ui/FormField";
import { ScreenState } from "../../ui/ScreenState";

/** Reasons a buyer may give when excluding a day: a fixed list, never free text. */
export const EXCLUSION_REASONS = ["data_error", "one_off_event", "stock_miscount", "other"] as const;

export interface DayRow {
  day: string;
  rules: string[];
  value: string;
  decision: AnomalyFlag["decision"];
}

/** One row per day: several rules can flag the same day, and a decision applies to the whole day. */
export function groupByDay(flags: AnomalyFlag[]): DayRow[] {
  const byDay = new Map<string, AnomalyFlag[]>();
  for (const f of flags) byDay.set(f.day, [...(byDay.get(f.day) ?? []), f]);
  return [...byDay.entries()].map(([day, list]) => ({
    day,
    rules: list.map((f) => f.rule_id),
    value: list[0]?.original_value ?? "",
    decision: list.some((f) => f.decision === "excluded") ? "excluded" : list.every((f) => f.decision === "accepted") ? "accepted" : "pending",
  }));
}

interface Props {
  userRoles: string[];
}

export const QualitySummary: React.FC<Props> = ({ userRoles }) => {
  const { t } = useTranslation();
  const [sku, setSku] = useState("");
  const [summary, setSummary] = useState<QualitySummaryData | null>(null);
  const [flags, setFlags] = useState<AnomalyFlag[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [reason, setReason] = useState<(typeof EXCLUSION_REASONS)[number]>("data_error");
  const [deciding, setDeciding] = useState<{ row: DayRow; decision: "accepted" | "excluded" } | null>(null);

  const canDecide = userRoles.includes("buyer") || userRoles.includes("admin");

  const load = async (code: string) => {
    try {
      setLoading(true);
      setError(null);
      const [s, a] = await Promise.all([api.getQualitySummary(code), api.getQualityAnomalies(code)]);
      setSummary(s);
      setFlags(a);
    } catch (err) {
      setSummary(null);
      setFlags([]);
      setError(errorMessage(err, t("common.error")));
    } finally {
      setLoading(false);
    }
  };

  const decide = async (row: DayRow, decision: "accepted" | "excluded") => {
    if (!summary) return;
    try {
      setDecisionError(null);
      await api.decideAnomaly(summary.sku, row.day, decision, decision === "excluded" ? reason : undefined);
      await load(summary.sku);
    } catch (err) {
      setDecisionError(errorMessage(err, t("common.error")));
    }
  };

  const rows = groupByDay(flags);
  const columns: Column<DayRow>[] = [
    { id: "day", header: t("quality.anomaly.day"), cell: (r) => formatDate(r.day), sortValue: (r) => r.day },
    { id: "rule", header: t("quality.anomaly.rule"), cell: (r) => r.rules.map((rule) => t(`quality.anomaly.rule.${rule}`)).join(", ") },
    { id: "value", header: t("quality.anomaly.value"), cell: (r) => r.value, sortValue: (r) => Number(r.value), align: "end" },
    { id: "decision", header: t("quality.anomaly.decision"), cell: (r) => t(`quality.anomaly.decision.${r.decision}`), sortValue: (r) => r.decision },
    ...(canDecide
      ? [
          {
            id: "actions",
            header: t("common.actions"),
            cell: (r: DayRow) => (
              <div className="mmi-actions">
                <Button small variant="secondary" disabled={r.decision === "excluded"} onClick={() => setDeciding({ row: r, decision: "excluded" })}>
                  {t("quality.anomaly.exclude")}
                </Button>
                <Button small variant="quiet" disabled={r.decision === "accepted"} onClick={() => setDeciding({ row: r, decision: "accepted" })}>
                  {t("quality.anomaly.accept")}
                </Button>
              </div>
            ),
          },
        ]
      : []),
  ];

  const excluding = deciding?.decision === "excluded";
  return (
    <section aria-labelledby="quality-product-title" className="mmi-section">
      <ConfirmDialog
        open={deciding !== null}
        title={excluding ? t("quality.anomaly.confirm.exclude.title") : t("quality.anomaly.confirm.accept.title")}
        objectLabel={deciding && summary ? t("quality.anomaly.confirm.object", { sku: summary.sku, day: formatDate(deciding.row.day) }) : ""}
        effect={excluding ? t("quality.anomaly.confirm.exclude.effect") : t("quality.anomaly.confirm.accept.effect")}
        confirmLabel={excluding ? t("quality.anomaly.exclude") : t("quality.anomaly.accept")}
        onCancel={() => setDeciding(null)}
        onConfirm={() => {
          const d = deciding;
          setDeciding(null);
          if (d) void decide(d.row, d.decision);
        }}
      />
      <h3 id="quality-product-title">{t("quality.product.title")}</h3>
      <p className="mmi-muted">{t("quality.product.hint")}</p>
      <form
        className="mmi-actions"
        onSubmit={(e) => {
          e.preventDefault();
          if (sku.trim()) void load(sku.trim());
        }}
      >
        <FormField id="quality-sku" label={t("quality.product.sku")} value={sku} onChange={setSku} maxLength={60} />
        <Button type="submit" loading={loading} disabled={!sku.trim()}>
          {t("quality.product.load")}
        </Button>
      </form>

      {loading && <ScreenState state="loading" skeletonShape="table" skeletonLines={3} />}
      {error && <ScreenState state="error" errorHint={error} onRetry={() => void load(sku.trim())} />}

      {summary && !loading && (
        <>
          <dl className="mmi-definition">
            <dt>{t("quality.product.coverage")}</dt>
            <dd>
              {formatPercent(summary.coverage_ratio, 1)} · {t("quality.product.coverage_days", { with: summary.days_with_data, total: summary.days_in_period })}
            </dd>
            <dt>{t("quality.product.gaps")}</dt>
            <dd>
              {summary.gap_days.length === 0
                ? t("quality.product.no_gaps")
                : summary.gap_days.map((g) => t("quality.product.gap_range", { from: formatDate(g.from), to: formatDate(g.to) })).join("; ")}
            </dd>
            <dt>{t("quality.product.quarantined")}</dt>
            <dd>{summary.quarantined_count}</dd>
            <dt>{t("quality.product.rejected")}</dt>
            <dd>{summary.rejected_count}</dd>
            <dt>{t("quality.product.ambiguous")}</dt>
            <dd>{summary.ambiguous_count}</dd>
            <dt>{t("quality.product.reasons")}</dt>
            <dd>{summary.reason_counts.length === 0 ? t("quality.product.none") : summary.reason_counts.map((r) => `${t(`localLoad.code.${r.key}`, { defaultValue: r.key })}: ${r.count}`).join("; ")}</dd>
            <dt>{t("quality.product.excluded_types")}</dt>
            <dd>{summary.excluded_by_type.length === 0 ? t("quality.product.none") : summary.excluded_by_type.map((r) => `${r.key}: ${r.count}`).join("; ")}</dd>
            <dt>{t("quality.product.anomalies")}</dt>
            <dd>{summary.anomaly_count}</dd>
            <dt>{t("quality.product.censored")}</dt>
            <dd>{summary.censored_days}</dd>
          </dl>
          <p className="mmi-muted">
            {t(`quality.product.origin.${summary.origin}`)} · {t("quality.product.built", { when: formatDateTime(summary.built_at) })}
          </p>

          <h4>{t("quality.anomaly.title")}</h4>
          {canDecide && (
            <label className="mmi-field__label" htmlFor="quality-reason">
              {t("quality.anomaly.reason_label")}
              <select id="quality-reason" value={reason} onChange={(e) => setReason(e.target.value as (typeof EXCLUSION_REASONS)[number])}>
                {EXCLUSION_REASONS.map((code) => (
                  <option key={code} value={code}>
                    {t(`quality.anomaly.reason.${code}`)}
                  </option>
                ))}
              </select>
            </label>
          )}
          {decisionError && (
            <p role="alert" className="mmi-error">
              {decisionError}
            </p>
          )}
          {rows.length === 0 ? (
            <EmptyState title={t("quality.anomaly.empty")} hint="" />
          ) : (
            <DataTable ariaLabel={t("quality.anomaly.title")} columns={columns} rows={rows} rowKey={(r) => r.day} />
          )}
        </>
      )}
    </section>
  );
};
