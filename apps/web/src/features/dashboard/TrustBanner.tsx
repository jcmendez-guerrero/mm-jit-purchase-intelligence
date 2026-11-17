import React from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import type { DashboardFreshness } from "../../api/client";
import { formatDateTime } from "../../i18n/formatters";
import { Button } from "../../ui/Button";

interface Props {
  freshness: DashboardFreshness | null;
  /** Data newer than the figures on screen exists; the figures stay as they are until the user asks. */
  newer: boolean;
  onRefresh: () => void;
}

/** Tells the user how far to trust the figures: stale data, what was left out and where to review it, local loads kept apart, and newer data on offer (never applied by itself). */
export const TrustBanner: React.FC<Props> = ({ freshness, newer, onRefresh }) => {
  const { t } = useTranslation();
  const stale = (freshness?.sources ?? []).filter((s) => s.state === "stale" && s.refreshed_at !== null).sort((a, b) => (a.refreshed_at ?? "").localeCompare(b.refreshed_at ?? ""));
  const oldest = stale[0];
  return (
    <div className="mmi-trust">
      {oldest && (
        <p className="mmi-banner" role="alert">
          {t("dashboard.trust.stale", { when: formatDateTime(oldest.refreshed_at as string), hours: oldest.stale_after_hours })}
        </p>
      )}
      {freshness && freshness.excluded_records > 0 && (
        <p role="note">
          {t("dashboard.trust.excluded", { n: freshness.excluded_records })}{" "}
          <Link to={freshness.review_list_link}>{t("dashboard.trust.review")}</Link>
        </p>
      )}
      {freshness && freshness.local_load_excluded > 0 && <p role="note">{t("dashboard.trust.local_excluded", { n: freshness.local_load_excluded })}</p>}
      {newer && (
        <p className="mmi-banner" role="status">
          {t("dashboard.trust.newer")}{" "}
          <Button variant="secondary" small onClick={onRefresh}>
            {t("dashboard.trust.refresh")}
          </Button>
        </p>
      )}
    </div>
  );
};
