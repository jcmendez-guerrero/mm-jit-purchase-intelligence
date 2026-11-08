import React from "react";

interface Props {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}

/** One h1 per page; title, context line and primary actions always in the same place (FR-005). */
export const PageHeader: React.FC<Props> = ({ title, description, actions }) => (
  <header className="mmi-page-header">
    <div>
      <h1 className="mmi-page-header__title">{title}</h1>
      {description && <p className="mmi-page-header__description">{description}</p>}
    </div>
    {actions && <div className="mmi-page-header__actions">{actions}</div>}
  </header>
);
