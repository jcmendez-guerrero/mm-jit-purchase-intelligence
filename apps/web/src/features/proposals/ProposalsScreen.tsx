import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, Proposal, ProposalLine } from "../../api/client";
import { formatCurrencyEUR, formatDate } from "../../i18n/formatters";

interface Props {
  userRoles: string[];
}

export const ProposalsScreen: React.FC<Props> = ({ userRoles }) => {
  const { t } = useTranslation();
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const canEdit = userRoles.includes("buyer") || userRoles.includes("admin");
  const canApprove = userRoles.includes("approver") || userRoles.includes("admin");

  const loadProposals = async () => {
    try {
      setLoading(true);
      setError(null);
      const list = await api.getProposals();
      setProposals(list || []);
      if (list && list.length > 0) {
        setSelectedProposal(list[0] || null);
      }
    } catch (err: any) {
      setError(err.message || t("common.error"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProposals();
  }, []);

  const handleEditLine = async (lineId: string, currentQty: number) => {
    const input = window.prompt("Nueva cantidad:", currentQty.toString());
    if (input === null) return;
    const newQty = parseInt(input, 10);
    if (isNaN(newQty) || newQty < 0) return;

    if (!selectedProposal) return;
    try {
      await api.editProposalLine(selectedProposal.id, lineId, newQty);
      const updated = await api.getProposal(selectedProposal.id);
      setSelectedProposal(updated);
    } catch (err: any) {
      alert(err.message || t("common.error"));
    }
  };

  const handleSubmit = async () => {
    if (!selectedProposal) return;
    try {
      await api.submitProposal(selectedProposal.id);
      const updated = await api.getProposal(selectedProposal.id);
      setSelectedProposal(updated);
      await loadProposals();
    } catch (err: any) {
      alert(err.message || t("common.error"));
    }
  };

  const handleApprove = async () => {
    if (!selectedProposal) return;
    try {
      await api.approveProposal(selectedProposal.id);
      const updated = await api.getProposal(selectedProposal.id);
      setSelectedProposal(updated);
      await loadProposals();
    } catch (err: any) {
      alert(err.message || t("common.error"));
    }
  };

  return (
    <section aria-labelledby="proposals-title">
      <div className="mmi-card">
        <h2 id="proposals-title" style={{ fontSize: "1.3rem", marginBottom: "0.5rem" }}>
          {t("proposals.title")}
        </h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "0.9rem", marginTop: 0, marginBottom: "1.5rem" }}>
          Propuestas semanales generadas por el motor de aprovisionamiento Just-in-Time
        </p>

        {loading && <p style={{ color: "var(--color-text-muted)" }}>{t("common.loading")}</p>}
        {error && <p role="alert" style={{ color: "var(--color-danger)" }}>{error}</p>}

        {!loading && proposals.length === 0 && (
          <div style={{ padding: "2rem", textAlign: "center", color: "var(--color-text-muted)" }}>
            <p style={{ margin: 0 }}>✓ {t("proposals.empty")}</p>
          </div>
        )}

        {!loading && proposals.length > 0 && (
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "1.5rem" }}>
            {proposals.map((p) => (
              <button
                key={p.id}
                onClick={() => setSelectedProposal(p)}
                className={`mmi-btn ${selectedProposal?.id === p.id ? "mmi-btn-primary" : "mmi-btn-secondary"}`}
              >
                Propuesta #{p.id.slice(0, 8)} ({t(`proposals.status.${p.status}`)})
              </button>
            ))}
          </div>
        )}

        {selectedProposal && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem", marginBottom: "1rem" }}>
              <div>
                <h3 style={{ margin: "0 0 0.25rem", fontSize: "1.1rem" }}>
                  Propuesta {selectedProposal.id}
                </h3>
                <span className="mmi-badge mmi-badge-petroleo">
                  {t(`proposals.status.${selectedProposal.status}`)}
                </span>
                <span style={{ marginLeft: "1rem", color: "var(--color-text-muted)", fontSize: "0.85rem" }}>
                  Ciclo: {formatDate(selectedProposal.cycle_date)} | Creador: {selectedProposal.creator}
                </span>
              </div>

              <div style={{ display: "flex", gap: "0.5rem" }}>
                {canEdit && selectedProposal.status === "draft" && (
                  <button onClick={handleSubmit} className="mmi-btn mmi-btn-primary">
                    {t("proposals.submit")}
                  </button>
                )}
                {canApprove && selectedProposal.status === "submitted" && (
                  <button onClick={handleApprove} className="mmi-btn mmi-btn-primary">
                    {t("proposals.approve")}
                  </button>
                )}
                <a
                  href={`/api/proposals/${selectedProposal.id}/export?format=csv`}
                  download
                  className="mmi-btn mmi-btn-secondary"
                >
                  {t("proposals.export_csv")}
                </a>
              </div>
            </div>

            <div className="mmi-table-wrapper">
              <table aria-label={t("a11y.proposals_table")} className="mmi-table">
                <thead>
                  <tr>
                    <th>{t("common.variant")}</th>
                    <th>{t("common.product")}</th>
                    <th>{t("common.supplier")}</th>
                    <th>{t("common.quantity")}</th>
                    <th>{t("common.cost")}</th>
                    <th>{t("common.total")}</th>
                    <th>{t("proposals.explanation")}</th>
                    {canEdit && selectedProposal.status === "draft" && <th>{t("common.actions")}</th>}
                  </tr>
                </thead>
                <tbody>
                  {selectedProposal.lines.map((l: ProposalLine) => (
                    <tr key={l.id}>
                      <td style={{ fontWeight: 600 }}>#{l.variant_id}</td>
                      <td>
                        <strong>{l.sku}</strong> — {l.product_name}
                      </td>
                      <td style={{ color: "var(--color-text-muted)" }}>{l.supplier_name || l.supplier_id}</td>
                      <td style={{ fontWeight: 600, color: "var(--color-primary)" }}>{l.order_qty}</td>
                      <td>{formatCurrencyEUR(l.unit_cost_net)}</td>
                      <td style={{ fontWeight: 600 }}>{formatCurrencyEUR(l.line_total)}</td>
                      <td style={{ color: "var(--color-text-muted)", fontSize: "0.85rem" }}>
                        {typeof l.explanation === "string" ? l.explanation : JSON.stringify(l.explanation)}
                      </td>
                      {canEdit && selectedProposal.status === "draft" && (
                        <td>
                          <button
                            onClick={() => handleEditLine(l.id, l.order_qty)}
                            className="mmi-btn mmi-btn-secondary mmi-btn-sm"
                          >
                            {t("proposals.edit_line")}
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};
