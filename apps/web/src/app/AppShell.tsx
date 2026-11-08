import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, Outlet, useLocation } from "react-router-dom";
import type { UserSession } from "../api/client";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icon";
import { PageActionsContext } from "../ui/PageActions";
import { PageHeader } from "../ui/PageHeader";
import { ThemeToggle } from "../ui/ThemeToggle";
import { CommandPalette } from "./CommandPalette";
import { Drawer } from "./Drawer";
import { Navigation } from "./Navigation";
import { DEFAULT_PATH, findItem, groupedItems, itemsFor } from "./routes";

interface Props {
  session: UserSession | null;
  roles: string[];
  sessionExpired: boolean;
  onLogout: () => void;
  /** Optional capabilities the application reports (for example ``localLoad``). */
  features?: string[];
}

/** Layout route: skip link, rail with grouped navigation, top bar, page header and the content outlet. */
export const AppShell: React.FC<Props> = ({ session, roles, sessionExpired, onLogout, features = [] }) => {
  const { t } = useTranslation();
  const location = useLocation();
  const item = findItem(location.pathname);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [actionsSlot, setActionsSlot] = useState<HTMLElement | null>(null);
  const slot = React.useMemo(() => ({ element: actionsSlot }), [actionsSlot]);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);
  const menuRef = React.useRef<HTMLButtonElement>(null);
  const wasOpen = React.useRef(false);

  useEffect(() => {
    if (wasOpen.current && !drawerOpen) menuRef.current?.focus();
    wasOpen.current = drawerOpen;
  }, [drawerOpen]);

  useEffect(() => {
    document.title = item ? `${t(item.labelKey)} · ${t("app.title")}` : t("app.title");
  }, [item, t]);

  const groups = groupedItems(roles, features);

  return (
    <div className="mmi-app">
      <a className="mmi-skip-link" href="#contenido">
        {t("shell.skip")}
      </a>

      <aside className="mmi-rail">
        <div className="mmi-logo-plate">
          <img src="/logo-horizontal.jpg" alt={t("shell.logo_alt")} />
        </div>
        <Navigation groups={groups} />
      </aside>

      <Drawer open={drawerOpen} onClose={closeDrawer}>
        <div className="mmi-logo-plate">
          <img src="/logo-horizontal.jpg" alt={t("shell.logo_alt")} />
        </div>
        <Navigation groups={groups} onNavigate={closeDrawer} />
      </Drawer>

      <div className="mmi-main-col">
        <header className="mmi-topbar" aria-label={t("a11y.user_profile")}>
          <button ref={menuRef} type="button" className="mmi-menu-button" aria-label={t("shell.menu_open")} aria-haspopup="dialog" onClick={() => setDrawerOpen(true)}>
            <Icon name="menu" />
          </button>
          <Link to={DEFAULT_PATH} className="mmi-isotipo" aria-label={t("shell.home")}>
            <img src="/isotipo.png" alt="" />
          </Link>
          <span className="mmi-topbar__spacer" />
          <ThemeToggle />
          <CommandPalette items={itemsFor(roles, features)} />
          <div className="mmi-user">
            <Icon name="user" />
            {session ? (
              <>
                <span>{session.user_id}</span>
                <span className="mmi-user__roles">{(session.roles ?? []).join(", ")}</span>
                <Button variant="quiet" small onClick={onLogout}>
                  <Icon name="logout" />
                  {t("nav.logout")}
                </Button>
              </>
            ) : (
              <span className="mmi-user__roles">{t("shell.not_signed_in")}</span>
            )}
          </div>
        </header>

        <main id="contenido" tabIndex={-1} className="mmi-content">
          {sessionExpired && (
            <div className="mmi-banner" role="alert">
              <Icon name="warning" />
              <div>
                <p className="mmi-banner__title">{t("shell.session_expired.title")}</p>
                <p>{t("shell.session_expired.hint")}</p>
              </div>
            </div>
          )}
          {item && <PageHeader title={t(item.labelKey)} description={t(item.descriptionKey)} actions={<span ref={setActionsSlot} className="mmi-page-header__slot" />} />}
          <PageActionsContext.Provider value={slot}>
            <Outlet />
          </PageActionsContext.Provider>
        </main>
      </div>
    </div>
  );
};
