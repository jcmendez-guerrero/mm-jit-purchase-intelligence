import React, { useEffect, useId, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "./Button";
import { closeDialog, openDialog } from "./dialog";

interface Props {
  open: boolean;
  /** What is about to happen, as a title. */
  title: string;
  /** The thing it happens to (item, supplier, amount), already formatted for es-ES. */
  objectLabel?: string;
  /** One sentence on the effect. */
  effect: string;
  confirmLabel: string;
  cancelLabel?: string;
  /** "danger" focuses the safe action first. */
  tone?: "default" | "danger";
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Explicit confirmation for hard-to-reverse or externally visible actions (FR-019). It only wraps the existing call. */
export const ConfirmDialog: React.FC<Props> = (props) => {
  if (!props.open) return null;
  return <Inner {...props} />;
};

const Inner: React.FC<Props> = ({ title, objectLabel, effect, confirmLabel, cancelLabel, tone = "default", busy, onConfirm, onCancel }) => {
  const { t } = useTranslation();
  const ref = useRef<HTMLDialogElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    openDialog(ref.current);
    (tone === "danger" ? cancelRef : confirmRef).current?.focus();
    return () => {
      closeDialog(ref.current);
      opener?.focus?.();
    };
  }, [tone]);

  return (
    <dialog
      ref={ref}
      className="mmi-confirm"
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault();
        onCancel();
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          onCancel();
        }
      }}
    >
      <h2 id={titleId} className="mmi-confirm__title">
        {title}
      </h2>
      {objectLabel && <p className="mmi-confirm__object">{objectLabel}</p>}
      <p className="mmi-confirm__effect">{effect}</p>
      <div className="mmi-confirm__actions">
        <button ref={cancelRef} type="button" className="mmi-button mmi-button--secondary" onClick={onCancel}>
          {cancelLabel ?? t("ui.confirm.cancel")}
        </button>
        <Button ref={confirmRef} variant={tone === "danger" ? "danger" : "primary"} loading={busy ?? false} onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </dialog>
  );
};
