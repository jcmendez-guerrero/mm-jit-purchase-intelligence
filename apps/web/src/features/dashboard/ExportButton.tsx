import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, DashboardExportView, DashFilters } from "../../api/client";
import { Button } from "../../ui/Button";

/** Roles that may put the dashboard in a file: the ones that may see costs. A viewer is not offered the action (and the server refuses it anyway). */
export const EXPORT_ROLES = ["buyer", "approver", "admin"] as const;
export const canExportDashboard = (roles: readonly string[] | undefined): boolean => (roles ?? []).some((r) => (EXPORT_ROLES as readonly string[]).includes(r));

interface Props {
  view: DashboardExportView;
  filters: DashFilters;
  label: string;
  ariaLabel?: string | undefined;
}

/** Downloads one view of the dashboard as CSV and says, in a status message, what happened: preparing, done with the row count, or the reason it was refused. */
export const ExportButton: React.FC<Props> = ({ view, filters, label, ariaLabel }) => {
  const { t } = useTranslation();
  const [state, setState] = useState<{ kind: "idle" } | { kind: "working" } | { kind: "done"; rows: number } | { kind: "error"; code: string }>({ kind: "idle" });

  const run = async () => {
    setState({ kind: "working" });
    try {
      const { blob, filename, rows } = await api.exportDashboard(view, filters);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      setState({ kind: "done", rows });
    } catch (err) {
      setState({ kind: "error", code: err instanceof ApiError ? err.code : "default" });
    }
  };

  return (
    <>
      <Button variant="secondary" small onClick={() => void run()} disabled={state.kind === "working"} aria-label={ariaLabel ?? label}>
        {label}
      </Button>
      <span role="status" aria-live="polite" className="mmi-muted">
        {state.kind === "working" && t("dashboard.export.working")}
        {state.kind === "done" && t("dashboard.export.done", { rows: state.rows })}
        {state.kind === "error" && t(`dashboard.export.error.${state.code}`, { defaultValue: t("dashboard.export.error.default") })}
      </span>
    </>
  );
};
