import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";
import type { IconName } from "./icons/paths";

export type NoticeTone = "success" | "info" | "warning" | "error";
interface Notice {
  id: number;
  tone: NoticeTone;
  message: string;
}
interface NoticeApi {
  notify: (tone: NoticeTone, message: string) => void;
  dismiss: (id: number) => void;
  /** True inside a provider; screens fall back to inline text when there is none. */
  present: boolean;
}

const AUTO_DISMISS_MS = 6000;
const ICON: Record<NoticeTone, IconName> = { success: "check", info: "info", warning: "warning", error: "error" };

const NoticeContext = createContext<NoticeApi>({ notify: () => undefined, dismiss: () => undefined, present: false });

/** Non-blocking confirmations (FR-018). Without a provider, notices are simply not shown. */
export const useNotices = (): NoticeApi => useContext(NoticeContext);

const NoticeItem: React.FC<{ notice: Notice; onDismiss: (id: number) => void }> = ({ notice, onDismiss }) => {
  const { t } = useTranslation();
  const [paused, setPaused] = useState(false);
  const remaining = useRef(AUTO_DISMISS_MS);

  useEffect(() => {
    if (paused) return;
    const started = Date.now();
    const timer = setTimeout(() => onDismiss(notice.id), remaining.current);
    return () => {
      clearTimeout(timer);
      remaining.current = Math.max(0, remaining.current - (Date.now() - started));
    };
  }, [paused, notice.id, onDismiss]);

  return (
    <div
      className={`mmi-notice mmi-notice--${notice.tone}`}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      onKeyDown={(e) => {
        if (e.key === "Escape") onDismiss(notice.id);
      }}
    >
      <Icon name={ICON[notice.tone]} />
      <span className="mmi-notice__message">{notice.message}</span>
      <button type="button" className="mmi-notice__close" aria-label={t("ui.notices.dismiss")} onClick={() => onDismiss(notice.id)}>
        <Icon name="close" />
      </button>
    </div>
  );
};

export const NoticeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { t } = useTranslation();
  const [notices, setNotices] = useState<Notice[]>([]);
  const next = useRef(1);

  const dismiss = useCallback((id: number) => setNotices((n) => n.filter((x) => x.id !== id)), []);
  const notify = useCallback((tone: NoticeTone, message: string) => setNotices((n) => [...n, { id: next.current++, tone, message }]), []);
  const api = useMemo(() => ({ notify, dismiss, present: true }), [notify, dismiss]);

  return (
    <NoticeContext.Provider value={api}>
      {children}
      <div role="region" aria-label={t("ui.notices.region")} aria-live="polite" className="mmi-notices mmi-no-print">
        {notices.map((n) => (
          <NoticeItem key={n.id} notice={n} onDismiss={dismiss} />
        ))}
      </div>
    </NoticeContext.Provider>
  );
};

/**
 * Drop-in for the old `[notice, setNotice] = useState` of a screen: confirmations become non-blocking notices when a
 * provider is present; without one (isolated tests) the text is returned so the screen can render it inline.
 */
export function useActionNotice(): readonly [string | null, (message: string | null, tone?: NoticeTone) => void] {
  const api = useNotices();
  const [local, setLocal] = useState<string | null>(null);
  const { notify, present } = api;
  const set = useCallback(
    (message: string | null, tone: NoticeTone = "success") => {
      if (present) {
        if (message) notify(tone, message);
      } else setLocal(message);
    },
    [notify, present],
  );
  return [present ? null : local, set] as const;
}
