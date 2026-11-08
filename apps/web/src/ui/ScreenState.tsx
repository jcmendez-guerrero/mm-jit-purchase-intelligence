import React from "react";
import { useTranslation } from "react-i18next";
import { Link, useInRouterContext } from "react-router-dom";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { Skeleton, type SkeletonShape } from "./Skeleton";

export type ScreenStateName = "loading" | "ready" | "empty" | "error" | "no_access";

interface Props {
  state: ScreenStateName;
  children?: React.ReactNode;
  /** A refetch is in flight: keep the current content visible and show a subtle busy indicator. */
  refreshing?: boolean;
  onRetry?: () => void;
  /** Specific explanation shown in the error state (for example the API's Spanish message). */
  errorHint?: string;
  emptyTitle?: string;
  emptyHint?: string;
  emptyActionLabel?: string;
  onEmptyAction?: () => void;
  skeletonLines?: number;
  /** Shape of the content that is coming. */
  skeletonShape?: SkeletonShape;
  /** Rendered by the "no access" state as the way forward. */
  noAccessAction?: React.ReactNode;
}

/** Renders exactly one of loading / empty / error / no-access, or the children when ready (FR-013, data-model.md). */
export const ScreenState: React.FC<Props> = ({ state, children, refreshing, onRetry, errorHint, emptyTitle, emptyHint, emptyActionLabel, onEmptyAction, skeletonLines, skeletonShape, noAccessAction }) => {
  const { t } = useTranslation();
  const inRouter = useInRouterContext();
  // A refusal for lack of permission is an access problem, not a failure to retry: explain it and offer a way forward.
  const forbidden = state === "error" && errorHint === t("errors.auth_forbidden_role");
  if (forbidden) {
    return (
      <div className="mmi-state" role="alert">
        <p className="mmi-state__title">{errorHint}</p>
        <p className="mmi-state__hint">{t("ui.no_access.hint")}</p>
        {inRouter ? (
          <Link className="mmi-button mmi-button--secondary" to="/panel">
            {t("shell.no_access.action")}
          </Link>
        ) : (
          <a className="mmi-button mmi-button--secondary" href="/panel">
            {t("shell.no_access.action")}
          </a>
        )}
      </div>
    );
  }

  if (state === "loading") {
    return (
      <div role="status" aria-busy="true" aria-label={t("ui.loading")}>
        <Skeleton lines={skeletonLines ?? 5} shape={skeletonShape ?? "lines"} />
      </div>
    );
  }
  if (state === "error") return <ErrorState {...(errorHint ? { hint: errorHint } : {})} {...(onRetry ? { onRetry } : {})} />;
  if (state === "empty") {
    return <EmptyState {...(emptyTitle ? { title: emptyTitle } : {})} {...(emptyHint ? { hint: emptyHint } : {})} {...(emptyActionLabel ? { actionLabel: emptyActionLabel } : {})} {...(onEmptyAction ? { onAction: onEmptyAction } : {})} />;
  }
  if (state === "no_access") {
    return (
      <div className="mmi-state">
        <p className="mmi-state__title">{t("ui.no_access.title")}</p>
        {noAccessAction}
      </div>
    );
  }
  return (
    <>
      {refreshing && (
        <div role="status" aria-label={t("ui.loading")} className="mmi-refreshing">
          <span className="mmi-spinner" aria-hidden="true" />
          {t("ui.refreshing")}
        </div>
      )}
      {children}
    </>
  );
};
