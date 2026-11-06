export const REQUIRED_FIELDS = ["variant_id", "day", "quantity", "kind", "provenance", "origin"] as const;
export const ALL_FIELDS = ["variant_id", "sku", "day", "quantity", "warehouse", "kind", "provenance", "origin"] as const;
export const ACCEPTED_EXTENSIONS = [".csv", ".xlsx"];

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

export const statusTone = (status: string): "ok" | "warn" | "off" => (status === "active" ? "ok" : status === "validated" || status === "uploaded" ? "warn" : "off");

export const isQueued = (r: object): r is { queued: true; rows: number; background_over_rows: number } => "queued" in r;
export const hasLiveJob = (jobs: Array<{ state: string }>): boolean => jobs.some((j) => j.state === "queued" || j.state === "running");
