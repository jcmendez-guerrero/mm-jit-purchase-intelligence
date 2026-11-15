import React, { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import glossary from "../i18n/glossary.json";

export type GlossaryConcept = keyof typeof glossary;

interface Props {
  concept: GlossaryConcept;
}

/**
 * Contextual help for a business term (FR-012): a button that opens a short Spanish definition from the glossary.
 * Escape or a second press closes it and focus stays on the button; it never shows free-text ERP notes.
 */
export const HelpHint: React.FC<Props> = ({ concept }) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const term = glossary[concept].term;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.stopPropagation();
      setOpen(false);
      button.current?.focus();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <span className="mmi-help">
      <button
        ref={button}
        type="button"
        className="mmi-help__button"
        aria-expanded={open}
        aria-controls={id}
        aria-label={t(open ? "ui.help.close" : "ui.help.open", { term })}
        onClick={() => setOpen((v) => !v)}
      >
        ?
      </button>
      {open && (
        <span id={id} role="note" className="mmi-help__text">
          {t(`glossary.${concept}`)}
        </span>
      )}
    </span>
  );
};
