import React from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ScreenState } from "../ui/ScreenState";
import { DEFAULT_PATH } from "./routes";

/** Shown when a role opens a section it may not use (FR-020); explains and offers the way forward. */
export const NoAccess: React.FC = () => {
  const { t } = useTranslation();
  return (
    <ScreenState
      state="no_access"
      noAccessAction={
        <Link className="mmi-button mmi-button--secondary" to={DEFAULT_PATH}>
          {t("shell.no_access.action")}
        </Link>
      }
    />
  );
};
