import React from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";
import { statusInfo, type StatusDomain } from "./statusVocabulary";

interface Props {
  domain: StatusDomain;
  code: string;
  /** Overrides the vocabulary text, for badges whose sentence carries values (the icon and tone still come from the vocabulary). */
  label?: string;
}

/** Pill with tone, icon and word. The only way statuses are rendered (FR-008). */
export const StatusBadge: React.FC<Props> = ({ domain, code, label }) => {
  const { t } = useTranslation();
  const info = statusInfo(domain, code);
  return (
    <span className={`mmi-status mmi-status--${info.tone}`}>
      <Icon name={info.icon} />
      {label ?? (info.labelKey ? t(info.labelKey, { defaultValue: code }) : code)}
    </span>
  );
};
