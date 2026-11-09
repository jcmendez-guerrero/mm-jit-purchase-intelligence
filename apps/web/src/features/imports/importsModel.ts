export const REQUIRED_FIELDS = ["sku", "day", "quantity", "kind", "provenance", "origin"] as const;
export const ALL_FIELDS = ["sku", "day", "quantity", "warehouse", "kind", "provenance", "origin"] as const;
export const ACCEPTED_EXTENSIONS = [".csv", ".xlsx"];

/** The fixed reason lists of FR-033 (the enums of seed_dataset.v1); the server checks them again. */
export const ROLLBACK_REASONS = ["wrong_figures", "wrong_file", "test", "replaced_by_newer", "other"] as const;
export const SELF_ACTIVATION_REASONS = ["only_person", "urgent", "other"] as const;
export const MAX_DETAIL = 100;

/** The detail with blanks collapsed, or undefined when there is none. */
export const tidyDetail = (text: string): string | undefined => {
  const tidy = text.split(/\s+/).filter(Boolean).join(" ");
  return tidy === "" ? undefined : tidy;
};

export const detailProblem = (text: string): boolean => (tidyDetail(text)?.length ?? 0) > MAX_DETAIL;

export const canSelfActivate = (roles: string[]): boolean => roles.includes("admin");

export const canImport = (roles: string[]): boolean => roles.includes("buyer") || roles.includes("admin");

/** The first reason a file should not even be sent; the server checks again. */
export function fileProblem(name: string, size: number, maxBytes: number): "type" | "size" | null {
  const lower = name.toLowerCase();
  if (!ACCEPTED_EXTENSIONS.some((e) => lower.endsWith(e))) return "type";
  return size > maxBytes ? "size" : null;
}

export function missingFields(map: Record<string, string>): string[] {
  const have = new Set(Object.values(map));
  return REQUIRED_FIELDS.filter((f) => !have.has(f));
}

/** One header per canonical field: choosing a field for a header frees it from any other header. */
export function setMapping(map: Record<string, string>, header: string, field: string): Record<string, string> {
  const next: Record<string, string> = {};
  for (const [h, f] of Object.entries(map)) if (h !== header && f !== field) next[h] = f;
  if (field !== "") next[header] = field;
  return next;
}

/** The provenance mix of a dataset as readable text: "estimado 4 · previsión manual 1" (labels come from the caller). */
export const kindMix = (kinds: Record<string, number>, label: (kind: string) => string): string =>
  Object.entries(kinds)
    .filter(([, n]) => n > 0)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, n]) => `${label(k)} ${n}`)
    .join(" · ") || "—";

export const statusTone = (status: string): "ok" | "warn" | "off" => (status === "active" ? "ok" : status === "validated" || status === "uploaded" ? "warn" : "off");

export const isQueued = (r: object): r is { queued: true; rows: number; background_over_rows: number } => "queued" in r;
export const hasLiveJob = (jobs: Array<{ state: string }>): boolean => jobs.some((j) => j.state === "queued" || j.state === "running");
