import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, DrillRequest, DrillResponse, errorMessage } from "../../api/client";
import { formatCurrencyEUR, formatNumber } from "../../i18n/formatters";
import { figureColumnKey } from "./dashboardModel";
import { ScreenState } from "../../ui/ScreenState";
import { EmptyState } from "../../ui/EmptyState";
import { DataTable, type Column } from "../../ui/DataTable";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";

interface Props {
  request: DrillRequest;
  title: string;
  onOpenProduct: (variantId: number) => void;
  onClose: () => void;
}

const PAGE_SIZE = 50;

/** The products behind one dashboard figure (FR-007). Each row opens the product detail; the list says when it was cut. */
export const DrillDownPanel: React.FC<Props> = ({ request, title, onOpenProduct, onClose }) => {
  const { t } = useTranslation();
  const [data, setData] = useState<DrillResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState<"" | "sku" | "name" | "figure">("");
  const [desc, setDesc] = useState(false);
  const key = JSON.stringify(request);
  useEffect(() => setOffset(0), [key]);

  useEffect(() => {
    let live = true;
    setData(null);
    setError(null);
    api
      .getDrilldown({ ...request, limit: PAGE_SIZE, offset, ...(sort ? { sort, order: desc ? "desc" : "asc" } : {}) })
      .then((d) => live && setData(d))
      .catch((err) => live && setError(errorMessage(err, t("common.error"))));
    return () => {
      live = false;
    };
  }, [key, offset, sort, desc, t]);
  useEffect(() => closeRef.current?.focus(), [key]);

  const shown = (figure: string | null) => {
    if (figure === null) return "—";
    if (request.kind === "inventory_value") return formatCurrencyEUR(figure);
    return formatNumber(figure, request.kind === "coverage" ? 1 : 0);
  };

  const columns: Column<DrillResponse["rows"][number]>[] = [
    {
      id: "variant",
      header: t("common.variant"),
      cell: (r) => `${r.sku ?? t("dashboard.drill.no_sku")}${r.name ? ` · ${r.name}` : ""}`,
    },
    ...(request.kind !== "stockout_risk" && request.kind !== "expiry_risk"
      ? [{ id: "figure", header: t(figureColumnKey(request.kind)), cell: (r: DrillResponse["rows"][number]) => shown(r.figure), align: "end" as const }]
      : []),
    {
      id: "actions",
      header: t("common.actions"),
      cell: (r) => (
        <Button variant="secondary" small onClick={() => onOpenProduct(r.variant_id)} aria-label={`${t("dashboard.risk_open")} ${r.sku ?? t("dashboard.drill.no_sku")}`}>
          {t("dashboard.risk_open")}
        </Button>
      ),
    },
  ];

  return (
    <Card as="aside" aria-label={title} onKeyDown={(e) => e.key === "Escape" && onClose()}>
      <h3>{title}</h3>
      <Button variant="secondary" small ref={closeRef} onClick={onClose}>
        {t("dashboard.drill.close")}
      </Button>
      <div className="mmi-filterbar__field">
        <label htmlFor="drill-sort">{t("dashboard.drill.sort_by")}</label>
        <select id="drill-sort" value={sort} onChange={(e) => { setSort(e.target.value as typeof sort); setOffset(0); }}>
          <option value="">{t("dashboard.drill.sort_default")}</option>
          <option value="sku">{t("dashboard.drill.sort_sku")}</option>
          <option value="name">{t("dashboard.drill.sort_name")}</option>
          {request.kind !== "stockout_risk" && request.kind !== "expiry_risk" && <option value="figure">{t("dashboard.drill.sort_figure")}</option>}
        </select>
        {sort && (
          <Button variant="secondary" small onClick={() => { setDesc(!desc); setOffset(0); }}>
            {desc ? t("dashboard.drill.sort_asc") : t("dashboard.drill.sort_desc")}
          </Button>
        )}
      </div>
      {error && <ScreenState state="error" errorHint={error} />}
      {!data && !error && <ScreenState state="loading" skeletonLines={4} />}
      {data && data.rows.length === 0 && <EmptyState title={t("dashboard.drill.empty")} hint="" />}
      {data && data.rows.length > 0 && (
        <>
          <DataTable ariaLabel={title} columns={columns} rows={data.rows} rowKey={(r) => r.variant_id} hideToolbar />
          {data.total > data.rows.length && (
            <nav aria-label={t("dashboard.drill.pages")}>
              <p className="mmi-muted" role="status">{t("dashboard.drill.range", { from: offset + 1, to: offset + data.rows.length, total: data.total })}</p>
              <Button variant="secondary" small disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>{t("dashboard.drill.prev")}</Button>
              <Button variant="secondary" small disabled={!data.truncated} onClick={() => setOffset(offset + PAGE_SIZE)}>{t("dashboard.drill.next")}</Button>
            </nav>
          )}
        </>
      )}
    </Card>
  );
};
