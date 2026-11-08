import React, { useId } from "react";

type Props = Omit<React.HTMLAttributes<HTMLElement>, "title"> & {
  /** Renders a heading and names the card by it. */
  title?: string;
  /** The element to render; a card that holds a form or a list is a section by default. */
  as?: "section" | "div" | "aside" | "article" | "form";
};

/** Working surface for forms and data. Not a wrapper for everything (design.md §3). */
export const Card = React.forwardRef<HTMLElement, Props>(function Card({ title, as = "section", className, children, ...rest }, ref) {
  const id = useId();
  const Tag = as as React.ElementType;
  return (
    <Tag ref={ref} {...rest} className={`mmi-card${className ? ` ${className}` : ""}`} {...(title ? { "aria-labelledby": id } : {})}>
      {title && (
        <h2 id={id} className="mmi-card__title">
          {title}
        </h2>
      )}
      {children}
    </Tag>
  );
});
