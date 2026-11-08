import React from "react";

interface Props {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** Called when the user leaves the field, so the form can validate it then. */
  onBlur?: () => void;
  disabled?: boolean;
  type?: "text" | "date";
  inputMode?: "decimal" | "numeric" | "text";
  hint?: string;
  /** Validation message in Spanish, shown beside the field and linked to it for assistive technology. */
  error?: string | undefined;
}

/** Labelled input with hint and error wired through aria-describedby and aria-invalid (FR-016). */
export const FormField: React.FC<Props> = ({ id, label, value, onChange, onBlur, disabled, type = "text", inputMode = "text", hint, error }) => {
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const described = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ");
  return (
    <div className={`mmi-field${error ? " mmi-field--invalid" : ""}`}>
      <label htmlFor={id} className="mmi-field__label">
        {label}
      </label>
      <input
        id={id}
        type={type}
        inputMode={inputMode}
        value={value}
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        aria-describedby={described || undefined}
        onChange={(e) => onChange(e.target.value)}
        {...(onBlur ? { onBlur } : {})}
        className="mmi-input"
      />
      {hint && (
        <span id={hintId} className="mmi-field__hint">
          {hint}
        </span>
      )}
      {error && (
        <span id={errorId} className="mmi-field__error">
          {error}
        </span>
      )}
    </div>
  );
};

/** Moves focus to the first control marked invalid inside `root`; returns whether one was found. */
export function focusFirstInvalid(root: ParentNode = document): boolean {
  const el = root.querySelector<HTMLElement>('[aria-invalid="true"]');
  el?.focus();
  return el !== null;
}
