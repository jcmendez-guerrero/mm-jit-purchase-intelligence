import React from "react";
import { useTranslation } from "react-i18next";
import { Button } from "./Button";
import { Icon } from "./Icon";

interface Props {
  title?: string;
  hint?: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<Props> = ({ title, hint, onRetry }) => {
  const { t } = useTranslation();
  return (
    <div className="mmi-state mmi-state--error" role="alert">
      <p className="mmi-state__title">
        <Icon name="error" />
        {title ?? t("ui.error.title")}
      </p>
      <p className="mmi-state__hint">{hint ?? t("ui.error.hint")}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          {t("ui.error.retry")}
        </Button>
      )}
    </div>
  );
};
