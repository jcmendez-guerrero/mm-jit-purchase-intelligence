import React, { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "../ui/Icon";
import { closeDialog, openDialog } from "../ui/dialog";

interface Props {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}

/** Navigation drawer for viewports below 1024 px, on a native modal dialog (focus trap, Escape, inert page). */
export const Drawer: React.FC<Props> = ({ open, onClose, children }) => {
  const { t } = useTranslation();
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (open) openDialog(ref.current);
  }, [open]);

  // The drawer only exists on narrow viewports: close it when the window becomes wide.
  useEffect(() => {
    if (!open || typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(min-width: 64rem)");
    const onChange = () => mq.matches && onClose();
    mq.addEventListener?.("change", onChange);
    return () => mq.removeEventListener?.("change", onChange);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <dialog
      ref={ref}
      className="mmi-drawer"
      aria-label={t("shell.drawer")}
      onCancel={(e) => {
        e.preventDefault();
        closeDialog(ref.current);
        onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      <button type="button" className="mmi-drawer__close" aria-label={t("shell.menu_close")} onClick={onClose}>
        <Icon name="close" />
      </button>
      {children}
    </dialog>
  );
};
