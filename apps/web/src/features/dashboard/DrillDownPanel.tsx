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

/** The products behind one dashboard figure (FR-007). Each row opens the product detail; the list says when it was cut. */
export const DrillDownPanel: React.FC<Props> = ({ request, title, onOpenProduct, onClose }) => {
  const { t } = useTranslation();
  const [data, setData] = useState<DrillResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const key = JSON.stringify(request);

  useEffect(() => {
    let live = true;
    setData(null);
    setError(null);
    api
      .getDrilldown(request)
      .then((d) => live && setData(d))
      .catch((err) => live && setError(errorMessage(err, t("common.error"))));
    return () => {
      live = false;
    };
  }, [key, t]);
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
      cell: (r) => `#${r.variant_id}${r.name ? ` · ${r.name}` : ""}${r.sku ? ` (${r.sku})` : ""}`,
      sortValue: (r) => r.variant_id,
    },
    ...(request.kind !== "stockout_risk" && request.kind !== "expiry_risk"
      ? [{ id: "figure", header: t(figureColumnKey(request.kind)), cell: (r: DrillResponse["rows"][number]) => shown(r.figure), align: "end" as const }]
      : []),
    {
      id: "actions",
      header: t("common.actions"),
      cell: (r) => (
        <Button variant="secondary" small onClick={() => onOpenProduct(r.variant_id)} aria-label={`${t("dashboard.risk_open")} #${r.variant_id}`}>
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
      {error && <ScreenState state="error" errorHint={error} />}
      {!data && !error && <ScreenState state="loading" skeletonLines={4} />}
      {data && data.rows.length === 0 && <EmptyState title={t("dashboard.drill.empty")} hint="" />}
      {data && data.rows.length > 0 && (
        <>
          <DataTable ariaLabel={title} columns={columns} rows={data.rows} rowKey={(r) => r.variant_id} hideToolbar />
          {data.truncated && <p className="mmi-muted">{t("dashboard.drill.truncated", { shown: data.rows.length, total: data.total })}</p>}
        </>
      )}
    </Card>
  );
};
