import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, DrillRequest, DrillResponse, errorMessage } from "../../api/client";
import { formatCurrencyEUR, formatNumber } from "../../i18n/formatters";
import { figureColumnKey } from "./dashboardModel";

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

  return (
    <aside className="mmi-card" aria-label={title} onKeyDown={(e) => e.key === "Escape" && onClose()}>
      <h3>{title}</h3>
      <button type="button" ref={closeRef} className="mmi-btn mmi-btn-sm mmi-btn-secondary" onClick={onClose}>
        {t("dashboard.drill.close")}
      </button>
      {error && <p role="alert">{error}</p>}
      {!data && !error && <p>{t("dashboard.loading_state")}</p>}
      {data && data.rows.length === 0 && <p>{t("dashboard.drill.empty")}</p>}
      {data && data.rows.length > 0 && (
        <>
          <div className="mmi-table-wrapper">
            <table className="mmi-table" aria-label={title}>
              <thead>
                <tr>
                  <th scope="col">{t("common.variant")}</th>
                  {request.kind !== "stockout_risk" && request.kind !== "expiry_risk" && <th scope="col">{t(figureColumnKey(request.kind))}</th>}
                  <th scope="col">{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.variant_id}>
                    <td>
                      #{r.variant_id}
                      {r.name ? ` · ${r.name}` : ""}
                      {r.sku ? ` (${r.sku})` : ""}
                    </td>
                    {request.kind !== "stockout_risk" && request.kind !== "expiry_risk" && <td>{shown(r.figure)}</td>}
                    <td>
                      <button type="button" className="mmi-btn mmi-btn-sm mmi-btn-secondary" onClick={() => onOpenProduct(r.variant_id)} aria-label={`${t("dashboard.risk_open")} #${r.variant_id}`}>
                        {t("dashboard.risk_open")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.truncated && <p className="mmi-muted">{t("dashboard.drill.truncated", { shown: data.rows.length, total: data.total })}</p>}
        </>
      )}
    </aside>
  );
};
