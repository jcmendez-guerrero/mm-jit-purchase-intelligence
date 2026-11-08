import React from "react";

export type SkeletonShape = "lines" | "table" | "dashboard";

interface Props {
  lines?: number;
  className?: string;
  /** Shape of the content that is coming, so the page does not jump when it arrives (FR-013). */
  shape?: SkeletonShape;
}

const bar = (key: string | number, className = "") => <div key={key} className={`mmi-skeleton__line ${className}`} />;

/** Placeholder shapes matching the final layout; hidden from assistive technology (the wrapper announces loading). */
export const Skeleton: React.FC<Props> = ({ lines = 4, className, shape = "lines" }) => {
  const cls = `mmi-skeleton mmi-skeleton--${shape}${className ? ` ${className}` : ""}`;

  if (shape === "table") {
    return (
      <div className={cls} aria-hidden="true">
        <div className="mmi-skeleton__head">{bar("h", "mmi-skeleton__line--head")}</div>
        {Array.from({ length: lines }, (_, i) => (
          <div key={i} className="mmi-skeleton__row">
            {bar("a")}
            {bar("b")}
            {bar("c")}
            {bar("d")}
          </div>
        ))}
      </div>
    );
  }

  if (shape === "dashboard") {
    return (
      <div className={cls} aria-hidden="true">
        <div className="mmi-skeleton__ruler">{bar("r", "mmi-skeleton__line--ruler")}</div>
        <div className="mmi-skeleton__figures">
          {[0, 1, 2, 3].map((i) => (
            <div key={i}>
              {bar(`l${i}`, "mmi-skeleton__line--label")}
              {bar(`v${i}`, "mmi-skeleton__line--value")}
              {bar(`n${i}`)}
            </div>
          ))}
        </div>
        <div className="mmi-skeleton__table">
          {bar("th", "mmi-skeleton__line--head")}
          {Array.from({ length: lines }, (_, i) => bar(`t${i}`))}
        </div>
      </div>
    );
  }

  return (
    <div className={cls} aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => bar(i))}
    </div>
  );
};
