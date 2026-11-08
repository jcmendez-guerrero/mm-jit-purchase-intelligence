import React from "react";
import { ICON_PATHS, type IconName } from "./icons/paths";

interface Props {
  name: IconName;
  /** Accessible name. Omit for decorative icons, which are hidden from assistive technology. */
  label?: string;
  className?: string;
}

export const Icon: React.FC<Props> = ({ name, label, className }) => (
  <svg
    className={`mmi-icon${className ? ` ${className}` : ""}`}
    viewBox="0 0 24 24"
    role={label ? "img" : undefined}
    aria-label={label}
    aria-hidden={label ? undefined : true}
    focusable="false"
    dangerouslySetInnerHTML={{ __html: ICON_PATHS[name] }}
  />
);
