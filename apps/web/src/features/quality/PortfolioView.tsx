import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { PortfolioBucket, PortfolioFilters, PortfolioList, PortfolioSummary, api, errorMessage } from "../../api/client";
import { formatPercent } from "../../i18n/formatters";
import { Button } from "../../ui/Button";
import { DataTable, type Column } from "../../ui/DataTable";
import { FormField } from "../../ui/FormField";
import { ScreenState } from "../../ui/ScreenState";

type Kind = "class" | "eligibility" | "confidence";
const CATEGORIES = ["A", "B", "C", "critical"] as const;
const PAGE = 50;

interface OpenList {
  kind: Kind;
  key: string;
  label: string;
  page: PortfolioList;
  offset: number;
}

/**
 * The whole catalogue at a glance (feature 018, FR-019, SC-007): products by demand class, by eligibility for a forecast and by confidence, plus the
 * ones with the weakest data. Every count opens the list of its products. Read-only, so every signed-in role sees it.
 */
export const PortfolioView: React.FC = () => {
  const { t } = useTranslation();
  const [category, setCategory] = useState("");
  const [supplier, setSupplier] = useState("");
  const [origin, setOrigin] = useState<"" | "local_export">("");              // empty means ERP; the two origins are never summed
  const [applied, setApplied] = useState<PortfolioFilters>({});
  const [data, setData] = useState<PortfolioSummary | null>(null);
  const [open, setOpen] = useState<OpenList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    const filters: PortfolioFilters = { ...(category ? { category } : {}), ...(supplier.trim() ? { supplier_id: supplier.trim() } : {}), ...(origin ? { origin } : {}) };
    try {
      setLoading(true);
      setError(null);
      setOpen(null);
      setData(await api.getPortfolio(filters));
      setApplied(filters);
    } catch (err) {
      setData(null);
      setError(errorMessage(err, t("common.error")));
    } finally {
      setLoading(false);
    }
  };

  const label = (kind: Kind, key: string) =>
    kind === "class" ? (key === "sin_clasificar" ? t("quality.portfolio.class.sin_clasificar") : key) : kind === "eligibility" ? t(`quality.eligibility.${key}`) : t(`quality.confidence.${key}`);

  const show = async (kind: Kind, key: string, offset = 0) => {
    try {
      setError(null);
      setOpen({ kind, key, label: label(kind, key), page: await api.getPortfolioProducts(kind, key, applied, offset, PAGE), offset });
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  };

  const section = (kind: Kind, titleKey: string, buckets: PortfolioBucket[]) => (
    <div key={kind}>
      <h4>{t(titleKey)}</h4>
      <ul className="mmi-actions">
        {buckets.map((b) => (
          <li key={b.key}>
            <Button variant="quiet" small disabled={b.count === 0} aria-label={t("quality.portfolio.open_list", { n: b.count, label: label(kind, b.key) })} onClick={() => void show(kind, b.key)}>
              {label(kind, b.key)}: {b.count}
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );

  const worstColumns: Column<PortfolioSummary["worst_quality"][number]>[] = [
    { id: "sku", header: t("quality.portfolio.col_sku"), cell: (r) => r.sku, sortValue: (r) => r.sku },
    { id: "coverage", header: t("quality.portfolio.col_coverage"), cell: (r) => formatPercent(r.coverage_ratio, 1), sortValue: (r) => Number(r.coverage_ratio), align: "end" },
    { id: "rejected", header: t("quality.portfolio.col_rejected"), cell: (r) => (r.rejected_share === null ? "—" : formatPercent(r.rejected_share, 1)), align: "end" },
    { id: "anomalies", header: t("quality.portfolio.col_anomalies"), cell: (r) => (r.anomaly_share === null ? "—" : formatPercent(r.anomaly_share, 1)), align: "end" },
  ];

  return (
    <section aria-labelledby="quality-portfolio-title" className="mmi-section">
      <h3 id="quality-portfolio-title">{t("quality.portfolio.title")}</h3>
      <p className="mmi-muted">{t("quality.portfolio.hint")}</p>
      <form
        className="mmi-actions"
        onSubmit={(e) => {
          e.preventDefault();
          void load();
        }}
      >
        <label className="mmi-field__label" htmlFor="portfolio-category">
          {t("quality.portfolio.category")}
          <select id="portfolio-category" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">{t("quality.portfolio.category_all")}</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {t(`quality.portfolio.category_${c.toLowerCase()}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="mmi-field__label" htmlFor="portfolio-origin">
          {t("quality.portfolio.origin")}
          <select id="portfolio-origin" value={origin} onChange={(e) => setOrigin(e.target.value as "" | "local_export")}>
            <option value="">{t("quality.portfolio.origin_erp")}</option>
            <option value="local_export">{t("quality.portfolio.origin_local")}</option>
          </select>
        </label>
        <FormField id="portfolio-supplier" label={t("quality.portfolio.supplier")} value={supplier} onChange={setSupplier} maxLength={36} />
        <Button type="submit" loading={loading}>
          {t("quality.portfolio.load")}
        </Button>
      </form>

      {loading && <ScreenState state="loading" skeletonShape="table" skeletonLines={3} />}
      {error && <ScreenState state="error" errorHint={error} />}

      {data && !loading && (
        <>
          <p role="status">{t("quality.portfolio.active", { n: data.active_products })}</p>
          {section("class", "quality.portfolio.by_class", data.by_class)}
          {section("eligibility", "quality.portfolio.by_eligibility", data.by_eligibility)}
          {section("confidence", "quality.portfolio.by_confidence", data.by_confidence)}

          {open && (
            <div role="region" aria-label={t("quality.portfolio.list_title", { label: open.label })}>
              <h4>{t("quality.portfolio.list_title", { label: open.label })}</h4>
              {open.page.skus.length === 0 ? (
                <p>{t("quality.portfolio.list_empty")}</p>
              ) : (
                <>
                  <ul>
                    {open.page.skus.map((sku) => (
                      <li key={sku}>{sku}</li>
                    ))}
                  </ul>
                  <p className="mmi-muted">{t("quality.portfolio.showing", { from: open.offset + 1, to: open.offset + open.page.skus.length, total: open.page.total })}</p>
                  <div className="mmi-actions">
                    <Button small variant="secondary" disabled={open.offset === 0} onClick={() => void show(open.kind, open.key, Math.max(0, open.offset - PAGE))}>
                      {t("quality.portfolio.prev")}
                    </Button>
                    <Button small variant="secondary" disabled={open.offset + PAGE >= open.page.total} onClick={() => void show(open.kind, open.key, open.offset + PAGE)}>
                      {t("quality.portfolio.next")}
                    </Button>
                  </div>
                </>
              )}
            </div>
          )}

          {data.worst_quality.length > 0 && (
            <>
              <h4>{t("quality.portfolio.worst")}</h4>
              <DataTable ariaLabel={t("quality.portfolio.worst")} columns={worstColumns} rows={data.worst_quality} rowKey={(r) => r.sku} hideToolbar />
            </>
          )}
        </>
      )}
    </section>
  );
};
