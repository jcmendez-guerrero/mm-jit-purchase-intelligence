import React, { useContext } from "react";
import { useTranslation } from "react-i18next";
import { UNSAFE_DataRouterContext, useBlocker } from "react-router-dom";
import { ConfirmDialog } from "./ConfirmDialog";
import { useUnsavedChanges } from "./useUnsavedChanges";

const Guard: React.FC<{ dirty: boolean }> = ({ dirty }) => {
  const { t } = useTranslation();
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirty && (currentLocation.pathname !== nextLocation.pathname || currentLocation.search !== nextLocation.search));
  return (
    <ConfirmDialog
      open={blocker.state === "blocked"}
      tone="danger"
      title={t("ui.unsaved.title")}
      effect={t("ui.unsaved.effect")}
      confirmLabel={t("ui.unsaved.leave")}
      cancelLabel={t("ui.unsaved.stay")}
      onConfirm={() => blocker.state === "blocked" && blocker.proceed()}
      onCancel={() => blocker.state === "blocked" && blocker.reset()}
    />
  );
};

/**
 * Put this next to a form: it warns before the tab closes and asks before an in-app navigation discards edits.
 * In-app blocking needs the data router; without one (isolated component tests) only the tab-close warning applies.
 */
export const UnsavedChangesPrompt: React.FC<{ dirty: boolean }> = ({ dirty }) => {
  useUnsavedChanges(dirty);
  const router = useContext(UNSAFE_DataRouterContext);
  // A router supports one blocker at a time, so only a form with edits to lose registers one.
  return router && dirty ? <Guard dirty={dirty} /> : null;
};
