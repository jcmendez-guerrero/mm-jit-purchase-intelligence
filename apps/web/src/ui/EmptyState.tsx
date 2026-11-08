import React from "react";
import { useTranslation } from "react-i18next";
import { Button } from "./Button";
import { Icon } from "./Icon";

interface Props {
  title?: string;
  hint?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<Props> = ({ title, hint, actionLabel, onAction }) => {
  const { t } = useTranslation();
  return (
    <div className="mmi-state">
      <p className="mmi-state__title">
        <Icon name="info" />
        {title ?? t("ui.empty.title")}
      </p>
      {hint !== "" && <p className="mmi-state__hint">{hint ?? t("ui.empty.hint")}</p>}
      {actionLabel && onAction && (
        <Button variant="secondary" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
};
