import React from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Icon } from "../ui/Icon";
import { DEFAULT_PATH } from "./routes";

export const NotFound: React.FC = () => {
  const { t } = useTranslation();
  return (
    <div className="mmi-state">
      <p className="mmi-state__title">
        <Icon name="info" />
        {t("shell.not_found.title")}
      </p>
      <p className="mmi-state__hint">{t("shell.not_found.hint")}</p>
      <Link className="mmi-button mmi-button--secondary" to={DEFAULT_PATH}>
        {t("shell.no_access.action")}
      </Link>
    </div>
  );
};
