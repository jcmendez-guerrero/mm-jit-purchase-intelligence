import React, { createContext, useContext } from "react";
import { createPortal } from "react-dom";

/** The element in the page header where the screen's primary actions go; null until the header has rendered it. */
type Slot = { element: HTMLElement | null };

export const PageActionsContext = createContext<Slot | undefined>(undefined);

/**
 * Renders a screen's primary actions in the page header, the same place on every screen (FR-005). Handlers stay with the
 * screen: only the position changes. Outside the app shell (isolated tests) the actions render where they are written.
 */
export const PageActions: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const slot = useContext(PageActionsContext);
  if (slot === undefined) return <>{children}</>;
  return slot.element ? createPortal(children, slot.element) : null;
};
