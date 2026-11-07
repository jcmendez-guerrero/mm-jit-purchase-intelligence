import React, { useState } from "react";
import { useTranslation } from "react-i18next";

interface Props {
  title: string;
  summary: string;
  columns: string[];
  rows: Array<Array<string | number>>;
  rowAction?: ((rowIndex: number) => { label: string; onClick: () => void }) | undefined;   // drill-down from a table row (keyboard path)
  children: React.ReactNode;
}

/** Every chart has a text summary and a table alternative reachable by keyboard (FR-009). */
export const ChartWithTable: React.FC<Props> = ({ title, summary, columns, rows, rowAction, children }) => {
  const { t } = useTranslation();
  const [asTable, setAsTable] = useState(false);
  return (
    <figure aria-label={title} style={{ margin: 0 }}>
      <figcaption>
        <h3>{title}</h3>
        <p className="mmi-muted">{summary}</p>
        <button type="button" className="mmi-btn mmi-btn-sm mmi-btn-secondary" aria-pressed={asTable} onClick={() => setAsTable(!asTable)}>
          {asTable ? t("dashboard.chart.chart_toggle") : t("dashboard.chart.table_toggle")}
        </button>
      </figcaption>
      {asTable ? (
        <div className="mmi-table-wrapper">
          <table aria-label={title} className="mmi-table">
            <thead>
              <tr>
                {columns.map((c) => (
                  <th key={c} scope="col">
                    {c}
                  </th>
                ))}
                {rowAction && <th scope="col">{t("common.actions")}</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  {r.map((c, j) => (
                    <td key={j}>{c}</td>
                  ))}
                  {rowAction && (
                    <td>
                      <button type="button" className="mmi-btn mmi-btn-sm mmi-btn-secondary" onClick={rowAction(i).onClick}>
                        {rowAction(i).label}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div role="img" aria-label={summary} style={{ width: "100%", height: 260 }}>
          {children}
        </div>
      )}
    </figure>
  );
};
