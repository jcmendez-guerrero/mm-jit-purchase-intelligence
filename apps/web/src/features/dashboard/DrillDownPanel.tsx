import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useInRouterContext } from "react-router-dom";
import { api, DashFilters, DrillRequest, DrillResponse, errorMessage } from "../../api/client";
import { ExportButton } from "./ExportButton";
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
  onOpenProduct: (sku: string) => void;
  onClose: () => void;
  /** Offer "Exportar productos" (roles that may see costs); the date range of the screen travels with it. */
  canExport?: boolean | undefined;
  range?: Pick<DashFilters, "date_from" | "date_to"> | undefined;
  loadedAt?: string | null | undefined;
  onForbidden?: (() => void) | undefined;
}

const PAGE_SIZE = 50;
/** The kinds whose figure is an amount of money: shown in euros, and removed by the server for a role without cost access. */
const MONEY_KINDS: readonly DrillRequest["kind"][] = ["inventory_value", "abc_xyz", "capital", "expiry_band"];

/** The products behind one dashboard figure (FR-007). Each row opens the product detail; the list says when it was cut. */
export const DrillDownPanel: React.FC<Props> = ({ request, title, onOpenProduct, onClose, canExport, range, loadedAt, onForbidden }) => {
  const { t } = useTranslation();
  const inRouter = useInRouterContext();                 // the panel is also rendered alone in tests; outside a router the link is a plain anchor
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
    if (MONEY_KINDS.includes(request.kind)) return formatCurrencyEUR(figure);
    return formatNumber(figure, request.kind === "coverage" ? 1 : request.kind === "forecast" ? 2 : 0);
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
        <Button variant="secondary" small disabled={!r.sku} onClick={() => r.sku && onOpenProduct(r.sku)} aria-label={`${t("dashboard.risk_open")} ${r.sku ?? t("dashboard.drill.no_sku")}`}>
          {t("dashboard.risk_open")}
        </Button>
      ),
    },
    {
      id: "page",
      header: t("dashboard.sku.link_header"),
      cell: (r) => {
        if (!r.sku) return null;
        const to = `/panel/skus/${encodeURIComponent(r.sku)}`;
        const cls = "mmi-button mmi-button--secondary mmi-button--small";
        return inRouter ? <Link className={cls} to={to}>{t("dashboard.sku.open")}</Link> : <a className={cls} href={to}>{t("dashboard.sku.open")}</a>;
      },
    },
  ];

  return (
    <Card as="aside" aria-label={title} onKeyDown={(e) => e.key === "Escape" && onClose()}>
      <h3>{title}</h3>
      <Button variant="secondary" small ref={closeRef} onClick={onClose}>
        {t("dashboard.drill.close")}
      </Button>
      {canExport && (
        <ExportButton
          view={{ kind: "drilldown", drill: { ...request, ...(sort ? { sort, order: desc ? "desc" : "asc" } : {}) } }}
          filters={range ?? {}}
          loadedAt={loadedAt}
          onForbidden={onForbidden}
          label={t("dashboard.export.drill")}
        />
      )}
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
          <DataTable ariaLabel={title} columns={columns} rows={data.rows} rowKey={(r) => `${r.sku ?? ""}|${r.name ?? ""}|${r.figure ?? ""}`} hideToolbar />
          {data.sum != null && <p><strong>{t("dashboard.drill.total", { value: shown(data.sum) })}</strong></p>}      {/* the sum of every row, not only this page: it equals the figure it came from */}
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
