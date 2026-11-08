import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Icon } from "../ui/Icon";
import { closeDialog, openDialog } from "../ui/dialog";
import { normalizeText, type NavItem } from "./routes";

interface Props {
  /** Screens already filtered for the signed-in role. The palette searches screens only (no product search). */
  items: NavItem[];
}

const isMac = () => typeof navigator !== "undefined" && /mac/i.test(navigator.platform);

/** Quick-jump (FR-003): opens with Ctrl/Cmd+K or the visible button; combobox + listbox on a native dialog. */
export const CommandPalette: React.FC<Props> = ({ items }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(-1);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const wasOpen = useRef(false);

  const results = useMemo(() => {
    const q = normalizeText(query);
    if (q === "") return items;
    // exact label first, then labels starting with the text, then labels containing it (stable within each rank)
    const rank = (i: NavItem) => {
      const label = normalizeText(t(i.labelKey));
      return label === q ? 0 : label.startsWith(q) ? 1 : label.includes(q) ? 2 : 3;
    };
    return items.filter((i) => rank(i) < 3).sort((a, b) => rank(a) - rank(b));
  }, [items, query, t]);

  const show = useCallback(() => {
    setQuery("");
    setActive(-1);
    setOpen(true);
  }, []);

  const close = useCallback(() => {
    closeDialog(dialogRef.current);
    setOpen(false);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        show();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [show]);

  useEffect(() => {
    if (open) {
      openDialog(dialogRef.current);
      inputRef.current?.focus();
      wasOpen.current = true;
    } else if (wasOpen.current) {
      wasOpen.current = false;
      triggerRef.current?.focus();
    }
  }, [open]);

  const choose = (item: NavItem | undefined) => {
    if (!item) return;
    close();
    navigate(item.path);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => (results.length === 0 ? -1 : (a + 1) % results.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => (results.length === 0 ? -1 : (a <= 0 ? results.length - 1 : a - 1)));
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(results[active >= 0 ? active : 0]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  };

  const optionId = (i: NavItem) => `palette-option-${i.id}`;
  const activeItem = active >= 0 ? results[active] : undefined;

  return (
    <>
      <button ref={triggerRef} type="button" className="mmi-palette-trigger" aria-label={t("shell.palette.open")} aria-haspopup="dialog" onClick={show}>
        <Icon name="search" />
        <span className="mmi-palette-trigger__label">{t("shell.palette.open")}</span>
        <kbd aria-hidden="true">{isMac() ? "⌘ K" : "Ctrl K"}</kbd>
      </button>
      {open && (
        <dialog
          ref={dialogRef}
          className="mmi-palette"
          aria-label={t("shell.palette.title")}
          onCancel={(e) => {
            e.preventDefault();
            close();
          }}
          onClick={(e) => {
            if (e.target === dialogRef.current) close();
          }}
        >
          <div className="mmi-palette__box">
            <input
              ref={inputRef}
              className="mmi-palette__input"
              type="text"
              role="combobox"
              aria-expanded="true"
              aria-controls="palette-listbox"
              aria-autocomplete="list"
              {...(activeItem ? { "aria-activedescendant": optionId(activeItem) } : {})}
              aria-label={t("shell.palette.placeholder")}
              placeholder={t("shell.palette.placeholder")}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setActive(-1);
              }}
              onKeyDown={onKeyDown}
            />
            <ul id="palette-listbox" role="listbox" aria-label={t("shell.palette.results")} className="mmi-palette__list">
              {results.map((item, idx) => (
                <li
                  key={item.id}
                  id={optionId(item)}
                  role="option"
                  aria-selected={idx === active}
                  className={`mmi-palette__option${idx === active ? " mmi-palette__option--active" : ""}`}
                  onMouseMove={() => setActive(idx)}
                  onClick={() => choose(item)}
                >
                  <Icon name={item.icon} />
                  <span>{t(item.labelKey)}</span>
                  <span className="mmi-palette__group">{t(`nav.group.${item.group}`)}</span>
                </li>
              ))}
            </ul>
            {results.length === 0 && <p className="mmi-palette__empty">{t("shell.palette.empty")}</p>}
          </div>
        </dialog>
      )}
    </>
  );
};
