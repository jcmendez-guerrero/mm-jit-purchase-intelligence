import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, Proposal, ProposalSummary, errorMessage } from "../../api/client";
import { formatCurrencyEUR, formatDate } from "../../i18n/formatters";
import { VersionsUsed } from "./VersionsUsed";
import { ProposalLineExplanation } from "./ProposalLineExplanation";
import { canApprove, canEditLines, canSubmit, groupLinesBySupplier, pageLineGroups, parseQty } from "./proposalModel";
import { ScreenState } from "../../ui/ScreenState";
import { EmptyState } from "../../ui/EmptyState";
import { StatusBadge } from "../../ui/StatusBadge";
import { ConfirmDialog } from "../../ui/ConfirmDialog";
import { Card } from "../../ui/Card";
import { Button } from "../../ui/Button";
import { PageActions } from "../../ui/PageActions";
import { DataTable } from "../../ui/DataTable";

interface Props {
  userRoles: string[];
}

const LINES_PER_PAGE = 50;

export const ProposalsScreen: React.FC<Props> = ({ userRoles }) => {
  const { t } = useTranslation();
  const [list, setList] = useState<ProposalSummary[]>([]);
  const [current, setCurrent] = useState<Proposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [open, setOpen] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<"submit" | "approve" | null>(null);
  const [linePage, setLinePage] = useState(0);

  const fail = useCallback((err: unknown) => setError(errorMessage(err, t("common.error"))), [t]);

  const select = useCallback(
    async (id: string) => {
      try {
        setCurrent(await api.getProposal(id));
        setDrafts({});
        setOpen(null);
        setLinePage(0);
      } catch (err) {
        fail(err);
      }
    },
    [fail],
  );

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const items = await api.getProposals();
      setList(items);
      if (items[0]) await select(items[0].id);
    } catch (err) {
      fail(err);
    } finally {
      setLoading(false);
    }
  }, [fail, select]);

  useEffect(() => {
    void load();
  }, [load]);

  /** Runs an action against the version on screen, then reloads so the user sees what the server now holds. */
  const act = async (run: (p: Proposal) => Promise<unknown>) => {
    if (!current) return;
    try {
      setError(null);
      await run(current);
    } catch (err) {
      fail(err);
    }
    try {
      setList(await api.getProposals());
      setCurrent(await api.getProposal(current.id));
      setDrafts({});
    } catch (err) {
      fail(err);
    }
  };

  const saveQty = (lineId: string) =>
    act((p) => {
      const qty = parseQty(drafts[lineId] ?? "");
      if (qty === null) return Promise.reject(new ApiError(422, "invalid_quantity"));
      return api.editProposalLine(p.id, lineId, qty, p.version);
    });

  const editable = current ? canEditLines(userRoles, current.status) : false;
  const pagedLines = pageLineGroups(current ? groupLinesBySupplier(current.lines, current.supplier_groups) : [], linePage, LINES_PER_PAGE);

  return (
    <section aria-labelledby="proposals-title">
      <ConfirmDialog
        open={confirming !== null && current !== null}
        title={confirming === "approve" ? t("proposals.confirm.approve.title") : t("proposals.confirm.submit.title")}
        objectLabel={current ? t("proposals.confirm.object", { week: current.week, count: current.lines.length }) : ""}
        effect={confirming === "approve" ? t("proposals.confirm.approve.effect") : t("proposals.confirm.submit.effect", { status: t("proposals.status.submitted") })}
        confirmLabel={confirming === "approve" ? t("proposals.approve") : t("proposals.submit")}
        onCancel={() => setConfirming(null)}
        onConfirm={() => {
          const kind = confirming;
          setConfirming(null);
          if (kind === "submit") void act((p) => api.submitProposal(p.id, p.version));
          if (kind === "approve") void act((p) => api.approveProposal(p.id, p.version));
        }}
      />
      <Card as="div">
        <h2 id="proposals-title">{t("proposals.title")}</h2>
        <p className="mmi-muted">{t("proposals.subtitle")}</p>
        {loading && <ScreenState state="loading" skeletonShape="table" skeletonLines={4} />}
        {error && <ScreenState state="error" errorHint={error} onRetry={() => void load()} />}
        {!loading && !error && list.length === 0 && <EmptyState title={t("proposals.empty")} hint="" />}
        {list.length > 0 && (
          <div role="group" aria-label={t("proposals.title")}>
            {list.map((p) => (
              <Button variant="secondary" key={p.id} aria-pressed={current?.id === p.id} onClick={() => void select(p.id)}>
                {t("proposals.item", { week: p.week, status: t(`proposals.status.${p.status}`) })}
              </Button>
            ))}
          </div>
        )}

        {current && (
          <div>
            <h3>{t("proposals.week", { week: current.week })}</h3>
            <VersionsUsed dataset={current.dataset_version_id} forecastRun={current.forecast_run_id} />
            <StatusBadge domain="approval" code={current.status} />
            <span className="mmi-muted"> {t("proposals.created_by", { user: current.created_by })}</span>
            <PageActions>
              {canSubmit(userRoles, current.status) && (
                <Button onClick={() => setConfirming("submit")}>
                  {t("proposals.submit")}
                </Button>
              )}
              {canApprove(userRoles, current.status) && (
                <Button onClick={() => setConfirming("approve")}>
                  {t("proposals.approve")}
                </Button>
              )}
              <a href={`/api/proposals/${current.id}/export?format=csv`} download className="mmi-button mmi-button--secondary">
                {t("proposals.export_csv")}
              </a>
              <a href={`/api/proposals/${current.id}/export?format=xlsx`} download className="mmi-button mmi-button--secondary">
                {t("proposals.export_excel")}
              </a>
            </PageActions>

            {current.supplier_groups.length > 0 && (
              <DataTable
                ariaLabel={t("proposals.groups")}
                rows={current.supplier_groups}
                rowKey={(g) => g.supplier_id}
                columns={[
                  { id: "supplier", header: t("common.supplier"), cell: (g) => g.supplier_name ?? g.supplier_id, sortValue: (g) => g.supplier_name ?? g.supplier_id },
                  { id: "subtotal", header: t("proposals.group.subtotal"), cell: (g) => formatCurrencyEUR(g.subtotal), sortValue: (g) => Number(g.subtotal), align: "end" },
                  { id: "discount", header: t("proposals.group.discount"), cell: (g) => formatCurrencyEUR(g.discount), sortValue: (g) => Number(g.discount), align: "end" },
                  { id: "delivery", header: t("proposals.group.delivery"), cell: (g) => formatCurrencyEUR(g.delivery_charge), sortValue: (g) => Number(g.delivery_charge), align: "end" },
                  { id: "total", header: t("proposals.group.total"), cell: (g) => formatCurrencyEUR(g.total_cost), sortValue: (g) => Number(g.total_cost), align: "end" },
                  { id: "expected", header: t("proposals.group.expected"), cell: (g) => (g.expected_delivery_date ? formatDate(g.expected_delivery_date) : "—"), sortValue: (g) => g.expected_delivery_date ?? null },
                  {
                    id: "status",
                    header: t("common.status"),
                    cell: (g) => (
                      <>
                        {g.free_delivery && <span>{t("proposals.group.free_delivery")} </span>}
                        {g.minimum_status === "shortfall" && <span role="note">{t("proposals.group.minimum_shortfall")}</span>}
                      </>
                    ),
                  },
                ]}
              />
            )}

            <div className="mmi-table-wrapper"><table aria-label={t("a11y.proposals_table")} className="mmi-table">
              <thead>
                <tr>
                  <th>{t("common.product")}</th>
                  <th>{t("common.supplier")}</th>
                  <th>{t("common.quantity")}</th>
                  <th>{t("common.cost")}</th>
                  <th>{t("common.total")}</th>
                  <th>{t("common.actions")}</th>
                </tr>
              </thead>
              {pagedLines.groups.map((g) => (
              <tbody key={g.id}>
                <tr className="mmi-group-row">
                  <th scope="colgroup" colSpan={6}>{g.continued ? t("proposals.group.continued", { supplier: g.name }) : g.name}</th>
                </tr>
                {g.lines.map((l) => {
                  const name = l.product_name ?? `#${l.variant_id}`;
                  return (
                    <React.Fragment key={l.id}>
                      <tr>
                        <td>
                          <strong>{l.sku ?? l.variant_id}</strong> — {name}
                          {l.manual_override && <span role="note"> · {t("proposals.warning.manual")}</span>}
                          {l.explanation.forecast_basis === "imported_estimates" && <span role="note"> <StatusBadge domain="tag" code="estimate" /></span>}
                        </td>
                        <td>{l.supplier_name ?? l.supplier_id}</td>
                        <td>
                          {editable ? (
                            <>
                              <input
                                type="text"
                                inputMode="numeric"
                                aria-label={t("proposals.qty_input", { product: name })}
                                value={drafts[l.id] ?? String(l.qty)}
                                onChange={(ev) => setDrafts({ ...drafts, [l.id]: ev.target.value })}
                              />
                              {drafts[l.id] !== undefined && drafts[l.id] !== String(l.qty) && (
                                <Button variant="secondary" small onClick={() => void saveQty(l.id)}>
                                  {t("proposals.qty_save")}
                                </Button>
                              )}
                            </>
                          ) : (
                            l.qty
                          )}
                        </td>
                        <td>{formatCurrencyEUR(l.unit_cost_with_recargo)}</td>
                        <td>{formatCurrencyEUR(l.line_total)}</td>
                        <td>
                          <Button variant="secondary" small aria-expanded={open === l.id} onClick={() => setOpen(open === l.id ? null : l.id)}>
                            {open === l.id ? t("proposals.explain_hide") : t("proposals.explain")}
                          </Button>
                        </td>
                      </tr>
                      {open === l.id && (
                        <tr>
                          <td colSpan={6}>
                            <ProposalLineExplanation line={l} />
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
                {g.complete && g.subtotal !== null && (
                  <tr className="mmi-group-foot">
                    <th scope="row" colSpan={4}>{t("proposals.group.subtotal_of", { supplier: g.name })}</th>
                    <td className="mmi-table__cell--end">{formatCurrencyEUR(g.subtotal)}</td>
                    <td />
                  </tr>
                )}
              </tbody>
              ))}
            </table></div>
            {pagedLines.pages > 1 && (
              <nav className="mmi-pagination" aria-label={t("ui.table.pagination")}>
                <span>{t("ui.table.rows", { count: pagedLines.total })}</span>
                <Button variant="quiet" small disabled={linePage === 0} onClick={() => setLinePage(linePage - 1)}>
                  {t("ui.table.prev")}
                </Button>
                <span>{t("ui.table.page", { page: Math.min(linePage, pagedLines.pages - 1) + 1, pages: pagedLines.pages })}</span>
                <Button variant="quiet" small disabled={linePage >= pagedLines.pages - 1} onClick={() => setLinePage(linePage + 1)}>
                  {t("ui.table.next")}
                </Button>
              </nav>
            )}
          </div>
        )}
      </Card>
    </section>
  );
};
