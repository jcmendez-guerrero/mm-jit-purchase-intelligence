import React from "react";

interface Props {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  type?: "text" | "date";
  inputMode?: "decimal" | "numeric" | "text";
  hint?: string;
}

/** A labelled text input; the label is tied to the input so screen readers and tests can find it by name. */
export const Field: React.FC<Props> = ({ id, label, value, onChange, disabled, type = "text", inputMode = "text", hint }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: "0.2rem", minWidth: "11rem" }}>
    <label htmlFor={id} style={{ fontSize: "0.85rem", fontWeight: 600 }}>
      {label}
    </label>
    <input
      id={id}
      type={type}
      inputMode={inputMode}
      value={value}
      disabled={disabled}
      aria-describedby={hint ? `${id}-hint` : undefined}
      onChange={(e) => onChange(e.target.value)}
      className="mmi-input"
    />
    {hint && (
      <span id={`${id}-hint`} style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
        {hint}
      </span>
    )}
  </div>
);
