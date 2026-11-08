import React, { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { DensityToggle } from "./DensityToggle";
import { EmptyState } from "./EmptyState";
import { Icon } from "./Icon";
import { usePreferences } from "./usePreferences";
import type { Tone } from "./statusVocabulary";

export interface Column<T> {
  id: string;
  header: string;
  cell: (row: T) => React.ReactNode;
  /** Present when ordering by this column is meaningful. */
  sortValue?: (row: T) => string | number | null;
  align?: "start" | "end";
}

interface Props<T> {
  /** Names the table and its scroll region. */
  ariaLabel: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  pageSize?: number;
  /** Colours the row's leading edge: risk is shown by position and tone, never by colour alone elsewhere in the row. */
  rowTone?: (row: T) => Tone | undefined;
  emptyTitle?: string;
  emptyHint?: string;
  hideToolbar?: boolean;
}

type Sort = { column: string; dir: "ascending" | "descending" } | null;

function compare(a: string | number | null, b: string | number | null): number {
  if (a === b) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), "es", { numeric: true, sensitivity: "base" });
}

/** Shared table: sticky header, sortable columns, density, pagination, own scroll region (FR-010 to FR-012). */
export function DataTable<T>({ ariaLabel, columns, rows, rowKey, pageSize = 50, rowTone, emptyTitle, emptyHint, hideToolbar }: Props<T>) {
  const { t } = useTranslation();
  const { density } = usePreferences();
  const [sort, setSort] = useState<Sort>(null);
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.id === sort.column);
    if (!col?.sortValue) return rows;
    const get = col.sortValue;
    const factor = sort.dir === "ascending" ? 1 : -1;
    return rows.map((row, i) => ({ row, i })).sort((x, y) => factor * compare(get(x.row), get(y.row)) || x.i - y.i).map((x) => x.row);
  }, [rows, columns, sort]);

  const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const current = Math.min(page, pages - 1);
  useEffect(() => {
    if (page !== current) setPage(current);
  }, [page, current]);
  const visible = sorted.slice(current * pageSize, current * pageSize + pageSize);

  const toggle = (id: string) =>
    setSort((prev) => (prev?.column === id ? { column: id, dir: prev.dir === "ascending" ? "descending" : "ascending" } : { column: id, dir: "ascending" }));

  if (rows.length === 0) {
    return <EmptyState {...(emptyTitle ? { title: emptyTitle } : {})} {...(emptyHint ? { hint: emptyHint } : {})} />;
  }

  return (
    <div className="mmi-table-block">
      {!hideToolbar && (
        <div className="mmi-table-toolbar">
          <span className="mmi-table-toolbar__count" aria-live="polite">
            {t("ui.table.rows", { count: sorted.length })}
          </span>
          <DensityToggle />
        </div>
      )}
      <div className="mmi-table-region" role="region" tabIndex={0} aria-label={t("ui.table.scroll_region", { name: ariaLabel })}>
        <table aria-label={ariaLabel} className={`mmi-table mmi-table--data${density === "compact" ? " mmi-table--compact" : ""}`}>
          <thead className="mmi-table__head">
            <tr>
              {columns.map((c, i) => {
                const sortable = !!c.sortValue;
                const active = sort?.column === c.id ? sort.dir : "none";
                return (
                  <th
                    key={c.id}
                    scope="col"
                    className={`mmi-table__th${i === 0 ? " mmi-table__cell--sticky" : ""}${c.align === "end" ? " mmi-table__cell--end" : ""}`}
                    {...(sortable ? { "aria-sort": active } : {})}
                  >
                    {sortable ? (
                      <button type="button" className="mmi-table__sort" title={t("ui.table.sort_by", { column: c.header })} onClick={() => toggle(c.id)}>
                        {c.header}
                        <Icon name={active === "ascending" ? "chevron-up" : active === "descending" ? "chevron-down" : "sort"} />
                      </button>
                    ) : (
                      c.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => {
              const tone = rowTone?.(row);
              return (
                <tr key={rowKey(row)} className={tone ? `mmi-row--${tone}` : undefined}>
                  {columns.map((c, i) => (
                    <td key={c.id} className={`mmi-table__cell${i === 0 ? " mmi-table__cell--sticky" : ""}${c.align === "end" ? " mmi-table__cell--end" : ""}`}>
                      {c.cell(row)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <nav className="mmi-pagination" aria-label={t("ui.table.pagination")}>
          <button type="button" className="mmi-button mmi-button--quiet mmi-button--small" disabled={current === 0} onClick={() => setPage(current - 1)}>
            {t("ui.table.prev")}
          </button>
          <span>{t("ui.table.page", { page: current + 1, pages })}</span>
          <button type="button" className="mmi-button mmi-button--quiet mmi-button--small" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>
            {t("ui.table.next")}
          </button>
        </nav>
      )}
    </div>
  );
}
