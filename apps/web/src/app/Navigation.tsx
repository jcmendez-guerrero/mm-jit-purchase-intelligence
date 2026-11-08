import React from "react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";
import { Icon } from "../ui/Icon";
import type { NavGroup, NavItem } from "./routes";

interface Props {
  groups: Array<NavGroup & { items: NavItem[] }>;
  /** Called after a destination is chosen (the drawer closes itself). */
  onNavigate?: () => void;
}

/** Grouped navigation driven by the registry; the current screen carries aria-current="page" (FR-001). */
export const Navigation: React.FC<Props> = ({ groups, onNavigate }) => {
  const { t } = useTranslation();
  return (
    <nav aria-label={t("a11y.menu")} className="mmi-nav">
      {groups.map((g) => (
        <div key={g.id} className="mmi-nav__group">
          <h2 className="mmi-nav__group-title">{t(g.labelKey)}</h2>
          <ul className="mmi-nav__list">
            {g.items.map((item) => (
              <li key={item.id}>
                <NavLink to={item.path} end className="mmi-nav__link" {...(onNavigate ? { onClick: onNavigate } : {})}>
                  <Icon name={item.icon} />
                  {t(item.labelKey)}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
};
