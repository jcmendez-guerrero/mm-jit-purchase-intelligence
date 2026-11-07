import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, Proposal, ProposalSummary, errorMessage } from "../../api/client";
import { formatCurrencyEUR, formatDate } from "../../i18n/formatters";
import { VersionsUsed } from "./VersionsUsed";
import { ProposalLineExplanation } from "./ProposalLineExplanation";
import { canApprove, canEditLines, canSubmit, parseQty } from "./proposalModel";

interface Props {
  userRoles: string[];
}

export const ProposalsScreen: React.FC<Props> = ({ userRoles }) => {
  const { t } = useTranslation();
  const [list, setList] = useState<ProposalSummary[]>([]);
  const [current, setCurrent] = useState<Proposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [open, setOpen] = useState<string | null>(null);

  const fail = useCallback((err: unknown) => setError(errorMessage(err, t("common.error"))), [t]);

  const select = useCallback(
    async (id: string) => {
      try {
        setCurrent(await api.getProposal(id));
        setDrafts({});
        setOpen(null);
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

  return (
    <section aria-labelledby="proposals-title">
      <div className="mmi-card">
        <h2 id="proposals-title">{t("proposals.title")}</h2>
        <p className="mmi-muted">{t("proposals.subtitle")}</p>
        {loading && <p>{t("common.loading")}</p>}
        {error && <p role="alert">{error}</p>}
        {!loading && list.length === 0 && <p>{t("proposals.empty")}</p>}
        {list.length > 0 && (
          <div role="group" aria-label={t("proposals.title")}>
            {list.map((p) => (
              <button key={p.id} type="button" aria-pressed={current?.id === p.id} className="mmi-btn mmi-btn-secondary" onClick={() => void select(p.id)}>
                {t("proposals.item", { week: p.week, status: t(`proposals.status.${p.status}`) })}
              </button>
            ))}
          </div>
        )}

        {current && (
          <div>
            <h3>{t("proposals.week", { week: current.week })}</h3>
            <VersionsUsed dataset={current.dataset_version_id} forecastRun={current.forecast_run_id} />
            <span className="mmi-badge">{t(`proposals.status.${current.status}`)}</span>
            <span className="mmi-muted"> {t("proposals.created_by", { user: current.created_by })}</span>
            <div>
              {canSubmit(userRoles, current.status) && (
                <button type="button" className="mmi-btn mmi-btn-primary" onClick={() => void act((p) => api.submitProposal(p.id, p.version))}>
                  {t("proposals.submit")}
                </button>
              )}
              {canApprove(userRoles, current.status) && (
                <button type="button" className="mmi-btn mmi-btn-primary" onClick={() => void act((p) => api.approveProposal(p.id, p.version))}>
                  {t("proposals.approve")}
                </button>
              )}
              <a href={`/api/proposals/${current.id}/export?format=csv`} download className="mmi-btn mmi-btn-secondary">
                {t("proposals.export_csv")}
              </a>
              <a href={`/api/proposals/${current.id}/export?format=xlsx`} download className="mmi-btn mmi-btn-secondary">
                {t("proposals.export_excel")}
              </a>
            </div>

            {current.supplier_groups.length > 0 && (
              <table aria-label={t("proposals.groups")} className="mmi-table">
                <caption>{t("proposals.groups")}</caption>
                <thead>
                  <tr>
                    <th>{t("common.supplier")}</th>
                    <th>{t("proposals.group.subtotal")}</th>
                    <th>{t("proposals.group.discount")}</th>
                    <th>{t("proposals.group.delivery")}</th>
                    <th>{t("proposals.group.total")}</th>
                    <th>{t("proposals.group.expected")}</th>
                    <th>{t("common.status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {current.supplier_groups.map((g) => (
                    <tr key={g.supplier_id}>
                      <td>{g.supplier_name ?? g.supplier_id}</td>
                      <td>{formatCurrencyEUR(g.subtotal)}</td>
                      <td>{formatCurrencyEUR(g.discount)}</td>
                      <td>{formatCurrencyEUR(g.delivery_charge)}</td>
                      <td>{formatCurrencyEUR(g.total_cost)}</td>
                      <td>{g.expected_delivery_date ? formatDate(g.expected_delivery_date) : "—"}</td>
                      <td>
                        {g.free_delivery && <span>{t("proposals.group.free_delivery")} </span>}
                        {g.minimum_status === "shortfall" && <span role="note">{t("proposals.group.minimum_shortfall")}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <table aria-label={t("a11y.proposals_table")} className="mmi-table">
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
              <tbody>
                {current.lines.map((l) => {
                  const name = l.product_name ?? `#${l.variant_id}`;
                  return (
                    <React.Fragment key={l.id}>
                      <tr>
                        <td>
                          <strong>{l.sku ?? l.variant_id}</strong> — {name}
                          {l.manual_override && <span role="note"> · {t("proposals.warning.manual")}</span>}
                          {l.explanation.forecast_basis === "imported_estimates" && <span role="note" className="mmi-badge mmi-badge-warning"> {t("proposals.badge.estimate")}</span>}
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
                                <button type="button" className="mmi-btn mmi-btn-sm" onClick={() => void saveQty(l.id)}>
                                  {t("proposals.qty_save")}
                                </button>
                              )}
                            </>
                          ) : (
                            l.qty
                          )}
                        </td>
                        <td>{formatCurrencyEUR(l.unit_cost_with_recargo)}</td>
                        <td>{formatCurrencyEUR(l.line_total)}</td>
                        <td>
                          <button type="button" className="mmi-btn mmi-btn-secondary mmi-btn-sm" aria-expanded={open === l.id} onClick={() => setOpen(open === l.id ? null : l.id)}>
                            {open === l.id ? t("proposals.explain_hide") : t("proposals.explain")}
                          </button>
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
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
};
