import React from "react";
import { useTranslation } from "react-i18next";
import type { SegmentHistoryRow } from "../../api/client";
import { formatDate } from "../../i18n/formatters";

/** A product's category changes with the reason for each (FR-045): in the policy console and in the product detail. */
export const CategoryHistory: React.FC<{ history: SegmentHistoryRow[] | null }> = ({ history }) => {
  const { t } = useTranslation();
  if (history === null) return <p>{t("common.loading")}</p>;
  if (history.length === 0) return <p>{t("safety.history_empty")}</p>;
  return (
    <ul>
      {history.map((h, i) => (
        <li key={i}>
          {t("safety.history_row", {
            when: formatDate(h.changed_at), abc: h.abc, xyz: h.xyz, pattern: h.pattern, critical: h.critical ? t("safety.critical_suffix") : "",
            reason: t(`safety.reason_key.${h.reason_key}`, { defaultValue: h.reason_key }),
          })}
        </li>
      ))}
    </ul>
  );
};
