import React from "react";
import { useTranslation } from "react-i18next";

type Variant = "primary" | "secondary" | "quiet" | "danger";

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  small?: boolean;
  /** Shows a spinner, keeps the label, and ignores clicks. */
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, Props>(function Button({ variant = "primary", small, loading, className, children, onClick, type = "button", disabled, ...rest }, ref) {
  const { t } = useTranslation();
  const classes = ["mmi-button", `mmi-button--${variant}`, small ? "mmi-button--small" : "", className ?? ""].filter(Boolean).join(" ");
  return (
    <button
      {...rest}
      ref={ref}
      type={type}
      className={classes}
      disabled={disabled}
      aria-busy={loading ? true : undefined}
      onClick={(e) => {
        if (loading) return e.preventDefault();
        onClick?.(e);
      }}
    >
      {loading && <span className="mmi-spinner" aria-hidden="true" />}
      {children}
      {loading && <span className="mmi-visually-hidden">{t("ui.loading")}</span>}
    </button>
  );
});
