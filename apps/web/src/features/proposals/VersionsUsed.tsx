import React from "react";
import { useTranslation } from "react-i18next";

interface Props {
  dataset: string | null | undefined;
  forecastRun: string | null | undefined;
}

/** The exact forecast run and imported dataset behind a proposal or scenario (FR-026), short enough to read and to quote to someone else. */
export const VersionsUsed: React.FC<Props> = ({ dataset, forecastRun }) => {
  const { t } = useTranslation();
  const short = (id: string) => id.slice(0, 8);
  return (
    <p className="mmi-muted" aria-label={t("versions.title")}>
      {t("versions.title")}: {forecastRun ? t("versions.run", { id: short(forecastRun) }) : t("versions.run_unknown")} · {dataset ? t("versions.dataset", { id: short(dataset) }) : t("versions.dataset_none")}
    </p>
  );
};
