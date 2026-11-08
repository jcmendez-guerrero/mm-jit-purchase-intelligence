import { useCallback, useState } from "react";
import { focusFirstInvalid } from "./FormField";

/**
 * Field-level validation messages for a form: `flag` shows them beside their fields and moves focus to the first invalid
 * one; `clear(id)` removes a message as soon as its field changes (FR-016). Keys are the ids of the inputs.
 */
export function useFieldErrors() {
  const [errors, setErrors] = useState<Record<string, string>>({});

  const flag = useCallback((next: Record<string, string>) => {
    setErrors(next);
    if (Object.keys(next).length > 0) setTimeout(() => focusFirstInvalid(document), 0);
  }, []);

  const clear = useCallback((id?: string) => {
    setErrors((prev) => {
      if (id === undefined) return Object.keys(prev).length === 0 ? prev : {};
      if (!(id in prev)) return prev;
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }, []);

  return { errors, flag, clear };
}
