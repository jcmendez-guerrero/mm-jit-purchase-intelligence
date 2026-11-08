import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage } from "../api/client";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Icon } from "../ui/Icon";
import { ScreenState } from "../ui/ScreenState";

const DEV_ROLES = ["viewer", "buyer", "approver", "admin"] as const;
type Mode = "dev" | "entra" | "none";

interface Props {
  sessionExpired: boolean;
  onDevLogin: (role: string) => Promise<void>;
}

/** Shown whenever there is no session. The server says how to sign in: a role chooser locally, Microsoft Entra ID in Azure. */
export const LoginScreen: React.FC<Props> = ({ sessionExpired, onDevLogin }) => {
  const { t } = useTranslation();
  const [mode, setMode] = useState<Mode | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const redirectError = new URLSearchParams(window.location.search).get("login_error");

  useEffect(() => {
    setError(null);
    api
      .getAuthConfig()
      .then((c) => setMode(c.mode))
      .catch((err) => setError(errorMessage(err, t("common.error"))));
  }, [attempt, t]);

  useEffect(() => {
    document.title = `${t("login.title")} · ${t("app.title")}`;
  }, [t]);

  const pick = async (role: string) => {
    setBusy(role);
    setError(null);
    try {
      await onDevLogin(role);
    } catch (err) {
      setError(errorMessage(err, t("login.error.generic")));
      setBusy(null);
    }
  };

  const redirectMessage = redirectError ? t(`login.error.${redirectError === "denied" || redirectError === "forbidden" ? redirectError : "generic"}`) : null;

  return (
    <main className="mmi-login" id="contenido">
      <Card as="div" className="mmi-login__panel">
        <img className="mmi-login__logo" src="/logo-horizontal.jpg" alt={t("shell.logo_alt")} />
        <h1 className="mmi-title-lg mmi-mt-0 mmi-mb-2">{t("login.title")}</h1>
        <p className="mmi-muted mmi-mt-0">{t("login.subtitle")}</p>

        {sessionExpired && (
          <div className="mmi-banner" role="alert">
            <Icon name="warning" />
            <div>
              <p className="mmi-banner__title">{t("shell.session_expired.title")}</p>
              <p>{t("shell.session_expired.hint")}</p>
            </div>
          </div>
        )}
        {redirectMessage && <p className="mmi-error" role="alert">{redirectMessage}</p>}
        {error && <ScreenState state="error" errorHint={error} onRetry={() => setAttempt((n) => n + 1)} />}
        {mode === null && !error && <p role="status">{t("login.loading")}</p>}

        {mode === "entra" && (
          <>
            <a className="mmi-button mmi-button--primary" href="/api/auth/login">
              {t("login.entra.action")}
            </a>
            <p className="mmi-muted mmi-text-sm mmi-mt-0">{t("login.entra.hint")}</p>
          </>
        )}

        {mode === "dev" && (
          <section aria-labelledby="login-dev-title">
            <h2 className="mmi-title-md mmi-mt-0" id="login-dev-title">{t("login.dev.title")}</h2>
            <p className="mmi-muted mmi-text-sm">{t("login.dev.hint")}</p>
            <ul className="mmi-login__roles">
              {DEV_ROLES.map((r) => (
                <li key={r} className="mmi-login__role">
                  <p>{t(`login.dev.role.${r}`)}</p>
                  <Button variant={r === "buyer" ? "primary" : "secondary"} loading={busy === r} disabled={busy !== null} onClick={() => void pick(r)}>
                    {t("login.dev.pick", { role: t(`roles.${r}`) })}
                  </Button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {mode === "none" && <p role="alert">{t("login.none")}</p>}
      </Card>
    </main>
  );
};
