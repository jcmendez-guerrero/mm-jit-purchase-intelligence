import i18n from "../i18n";
/**
 * Frontend API client communicating with api-bff.
 * Handles cookie session and passes X-CSRF-Token on mutating requests.
 */

let csrfToken: string | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

export interface UserSession {
  user_id: string;
  roles: string[];
  mfa_auth_time: string;
  csrf_token: string;
}

/** A JSON object whose members are not described by an interface here. */
export type JsonRecord = Record<string, unknown>;

export interface CostRecord {
  id: string;
  product_id: number;
  supplier_id: string;
  variant_id: number | null;
  version: number;
  cost_net: string | null;
  cost_with_recargo: string;
  recargo_rate: string | null;
  source: string;
  verified_at: string;
  status: string;
}

export interface CostWriteLot {
  variant_id: number;
  lot: string;
  quantity: number;
  unit_cost: string;
}

export interface CostWriteRecord {
  id: string;
  product_id: number;
  supplier_id: string;
  trigger: string;
  proposed_value: string;
  previous_siweb_value: string | null;
  status: string;
  attempts: number;
  last_error: string | null;
  median_cost: string | null;
  lots: CostWriteLot[];
  pvp_used: string | null;
  pvp_source: string;
  margin_before: string | null;
  margin_after: string | null;
  rule_flags: string[];
  tips: { cap: string; cost_at_minimum: string; cost_at_cap: string } | null;
  override: { value: string; reason: string; by: string; at: string | null } | null;
}

export interface LotCostCorrection {
  variant_id: number;
  supplier_id: string;
  lot: string;
  amount: string;
  includes_recargo: boolean;
  source: "receipt_correction" | "buyer_entry";
}

export interface ImportErrorItem {
  id: number;
  variant_id: number;
  movement_reason_raw?: string | null;
  anomaly_codes?: string[];
  created_at: string;
}

export interface ServiceLevelEntry {
  scope: string;
  scope_key: string;
  target_level: string;
  updated_by?: string;
}

export interface RolesListing {
  users: Array<UserRoles & { active: boolean; revision: number }>;
  eligible_approvers_count: number;
  valid_roles: string[];
}

export interface RoleMirrorStatus {
  pending: number;
  failed: number;
  sent: number;
  oldest_pending_seconds: number;
  items: Array<{ id: number; user_id: string; status: string; attempts: number; last_error_key: string | null }>;
}

export interface DiscountDoc {
  kind: "percent" | "amount";
  basis: "order_value" | "order_units";
  threshold: string;
  value: string;
}

export interface TermsDoc {
  min_order_value: string | null;
  min_qty_for_delivery: number | null;
  free_delivery_threshold: string | null;
  delivery_charge: string | null;
  order_days: number[];
  delivery_schedule: string | null;
  lead_time_days: number | null;
  order_cutoff_time: string | null;
  delivery_weekdays: number[];
  discounts: DiscountDoc[];
  payment_terms_days: number | null;
  preferred: boolean;
  reliability: number | null;
  disabled: boolean;
  valid_to: string | null;
}

export interface TermsHistoryItem {
  version: number;
  valid_from: string;
  valid_to: string | null;
  source: "erp" | "import" | "manual";
  reason: string | null;
  changed_by: string;
  terms: TermsDoc;
}

export interface SupplierTermsView {
  supplier_id: string;
  version: number;
  current: TermsDoc | null;
  history: TermsHistoryItem[];
}

export interface SupplierSummary {
  id: string;
  name: string;
  terms: TermsDoc | null;
  version: number;
}

export interface OverrideDoc {
  pack_multiple: number | null;
  min_qty_units: number | null;
  lead_time_days: number | null;
  payment_terms_days: number | null;
  preferred: boolean | null;
  reliability: number | null;
  disabled: boolean | null;
}

export interface EffectiveTerms {
  lead_time_days: number;
  pack_multiple: number | null;
  min_qty_units: number | null;
  payment_terms_days: number | null;
  preferred: boolean;
  reliability: number | null;
  disabled: boolean;
  sources: Record<string, "override" | "supplier" | "cost" | "default">;
  conflicts: Array<{ field: string; erp_value: number; local_value: number; winner: string }>;
  supplier_version: number | null;
  override_version: number | null;
  flags: string[];
}

export interface OverrideView {
  variant_id: number;
  supplier_id: string;
  version: number;
  override: OverrideDoc | null;
  history: Array<{ version: number; valid_from: string; source: string; reason: string | null; changed_by: string; terms: OverrideDoc }>;
  effective: EffectiveTerms;
}

export interface UserRoles {
  user_id: string;
  roles: string[];
}

/** The message of a caught value, or the fallback when it is not an Error. */
/** An API refusal. ``code`` is the stable snake_case code services return; it is never shown to the user as it is. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    public readonly currentVersion?: number,
  ) {
    super(code);
    this.name = "ApiError";
  }
}

/** The Spanish message for an error. Unknown codes and technical errors fall back to the generic message, never to raw text. */
export function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    const key = `errors.${err.code}`;
    if (i18n.exists(key)) return i18n.t(key);
  }
  return fallback;
}

export interface RiskItem {
  variant_id: number;
  risk_type: "stockout" | "expiry" | "data_quality";
  explanation_key: string;
  params?: JsonRecord;
}

export interface VariantDetail {
  variant: {
    id: number;
    sku: string;
    name: string;
    pack_size: number;
    uom: string;
    product: { id: number; status?: string };
  };
  stock?: {
    on_hand: number;
    available: number;
    reserved: number;
    as_of: string;
  };
  demand: Array<{ day: string; warehouse_id: number; qty: number; censored: boolean }>;
  flows: Array<{ day: string; warehouse_id: number; flow: string; qty: number }>;
  history: Array<{ day: string; on_hand: number; censored: boolean }>;
  segment?: {
    abc: string;
    xyz: string;
    pattern: string;
    forecast_eligible: boolean;
    reasons: string[];
    metrics: JsonRecord;
  };
  history_reconciled?: boolean;
}

export interface ProposalExplanation {
  policy: string;
  forecast_eligible: boolean;
  service_level: string;
  horizon_days: number;
  expected_demand: number;
  safety_stock: number;
  order_up_to: number;
  reorder_point: number;
  need: number;
  top_up: boolean;
  clinical_critical: boolean;
  position: { on_hand: number; expiring: number; usable: number; inbound: number; total: number };
  supplier: {
    chosen: string;
    reason: string;
    alternatives: Array<{ supplier_id: string; unit_cost: string; qty: number; line_total: string; lead_time_days: number; chosen: boolean }>;
    rejected: Array<{ supplier_id: string; reason: string }>;
  };
  cost: { unit: string; source: string; status: string };
  constraints: string[];
  terms?: {
    supplier_version: number | null;
    override_version: number | null;
    sources: Record<string, string>;
    conflicts: Array<{ field: string; erp_value: unknown; local_value: unknown; winner: string }>;
    preferred: boolean;
    supplier_discount: string;
  };
}

export interface ProposalLine {
  id: string;
  variant_id: number;
  sku: string | null;
  product_name: string | null;
  supplier_id: string;
  supplier_name: string | null;
  qty: number;
  unit_cost_with_recargo: string;
  line_total: string;
  risk: string;
  confidence: string;
  manual_override: boolean;
  topup: boolean;
  constraints_applied: string[];
  explanation: ProposalExplanation;
}

export interface SupplierGroup {
  supplier_id: string;
  supplier_name: string | null;
  subtotal: string;
  discount: string;
  delivery_charge: string;
  total_cost: string;
  expected_delivery_date: string | null;
  minimum_status: string;
  free_delivery: boolean;
}

export type ProposalStatus = "draft" | "submitted" | "approved" | "confirmed";

export interface ProposalSummary {
  id: string;
  week: string;
  status: ProposalStatus;
  version: number;
  created_by: string;
  updated_at: string;
}

export interface Proposal extends Omit<ProposalSummary, "updated_at"> {
  last_edited_by: string | null;
  lines: ProposalLine[];
  supplier_groups: SupplierGroup[];
  terms_version_ids: Record<string, unknown> | null;
  approval: { approver: string; decision: string; version: number; valid: boolean } | null;
  warnings?: string[];
}

export class ApiClient {
  private baseUrl = "/api";

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");

    if (["POST", "PUT", "DELETE", "PATCH"].includes(options.method?.toUpperCase() || "")) {
      if (csrfToken) {
        headers.set("X-CSRF-Token", csrfToken);
      }
      if (options.body && !(options.body instanceof FormData)) {
        headers.set("Content-Type", "application/json");
      }
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
      credentials: "same-origin",
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}) as { detail?: unknown });
      const detail = (err as { detail?: unknown }).detail;
      const code = typeof detail === "string" && /^[a-z][a-z0-9_:]*$/.test(detail) ? detail : Array.isArray(detail) ? "request_invalid" : "unknown";
      const current = (err as { current_version?: unknown }).current_version;
      throw new ApiError(response.status, code, typeof current === "number" ? current : undefined);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  async getMe(): Promise<UserSession> {
    const data = await this.request<UserSession>("/me");
    if (data.csrf_token) {
      setCsrfToken(data.csrf_token);
    }
    return data;
  }

  async devLogin(userId: string, roles: string[]): Promise<UserSession> {
    const data = await this.request<UserSession>("/auth/dev-login", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, roles }),
    });
    setCsrfToken(data.csrf_token);
    return data;
  }

  async logout(): Promise<void> {
    await this.request<void>("/auth/logout", { method: "POST" });
    setCsrfToken(null);
  }

  async getRisks(warehouseId?: number): Promise<RiskItem[]> {
    const query = warehouseId !== undefined ? `?warehouse_id=${warehouseId}` : "";
    return this.request<RiskItem[]>(`/dashboard/risk${query}`);
  }

  async getVariant(variantId: number): Promise<VariantDetail> {
    return this.request<VariantDetail>(`/inventory/variants/${variantId}`);
  }

  async getImportErrors(): Promise<{ count: number; items: ImportErrorItem[] }> {
    return this.request<{ count: number; items: ImportErrorItem[] }>("/data-quality/import-errors");
  }

  async resolveImportError(id: number, decision: "release" | "ignore"): Promise<void> {
    await this.request<void>(`/data-quality/import-errors/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    });
  }

  async getSuppliers(): Promise<SupplierSummary[]> {
    return this.request<SupplierSummary[]>("/suppliers");
  }

  async getCosts(): Promise<CostRecord[]> {
    return this.request<CostRecord[]>("/costs");
  }

  async getCostWrites(): Promise<CostWriteRecord[]> {
    return this.request<CostWriteRecord[]>("/cost-writes");
  }

  async approveCostWrite(writeId: string): Promise<JsonRecord> {
    return this.request<JsonRecord>(`/cost-writes/${writeId}/approve`, { method: "POST" });
  }

  /** Admin only: replaces the median with their own value. It still has to be released by a different buyer. */
  async overrideCostWrite(writeId: string, value: string, reason: string): Promise<JsonRecord> {
    return this.request<JsonRecord>(`/cost-writes/${writeId}/override`, { method: "POST", body: JSON.stringify({ value, reason }) });
  }

  /** Correction of what a lot cost, on arrival of the goods. There is no way to type a free supplier cost. */
  async correctLotCost(body: LotCostCorrection): Promise<JsonRecord> {
    return this.request<JsonRecord>("/lot-costs", { method: "POST", body: JSON.stringify(body) });
  }

  async getProposals(): Promise<ProposalSummary[]> {
    return this.request<ProposalSummary[]>("/proposals");
  }

  async getProposal(id: string): Promise<Proposal> {
    return this.request<Proposal>(`/proposals/${id}`);
  }

  /** Every change carries the version the user was looking at, so a stale view is refused instead of overwritten. */
  async editProposalLine(proposalId: string, lineId: string, qty: number, version: number): Promise<Proposal> {
    return this.request<Proposal>(`/proposals/${proposalId}/lines/${lineId}`, {
      method: "PUT",
      body: JSON.stringify({ qty }),
      headers: { "If-Match": `"${version}"` },
    });
  }

  async submitProposal(proposalId: string, version: number): Promise<JsonRecord> {
    return this.request<JsonRecord>(`/proposals/${proposalId}/submit`, { method: "POST", headers: { "If-Match": `"${version}"` } });
  }

  async approveProposal(proposalId: string, version: number): Promise<JsonRecord> {
    return this.request<JsonRecord>(`/proposals/${proposalId}/approve`, { method: "POST", headers: { "If-Match": `"${version}"` } });
  }

  async getServiceLevels(): Promise<{ history?: ServiceLevelEntry[] }> {
    return this.request<{ history?: ServiceLevelEntry[] }>("/config/service-levels");
  }

  async getRoles(): Promise<RolesListing> {
    return this.request<RolesListing>("/admin/roles");
  }

  async getRoleMirror(): Promise<RoleMirrorStatus> {
    return this.request<RoleMirrorStatus>("/admin/roles/mirror");
  }

  async retryRoleMirror(): Promise<{ requeued: number }> {
    return this.request<{ requeued: number }>("/admin/roles/mirror/retry", { method: "POST" });
  }

  async updateRoles(userId: string, roles: string[], active = true): Promise<JsonRecord> {
    return this.request<JsonRecord>(`/admin/roles/${encodeURIComponent(userId)}`, {
      method: "PUT",
      body: JSON.stringify({ roles, active }),
    });
  }

  async getSupplierTerms(supplierId: string): Promise<SupplierTermsView> {
    return this.request<SupplierTermsView>(`/suppliers/${encodeURIComponent(supplierId)}/terms`);
  }

  async putSupplierTerms(supplierId: string, payload: Record<string, unknown>, version: number): Promise<{ version: number }> {
    return this.request<{ version: number }>(`/suppliers/${encodeURIComponent(supplierId)}/terms`, {
      method: "PUT",
      headers: version > 0 ? { "If-Match": `"${version}"` } : {},
      body: JSON.stringify(payload),
    });
  }

  async getOverrideTerms(variantId: number, supplierId: string): Promise<OverrideView> {
    return this.request<OverrideView>(`/product-suppliers/${variantId}/${encodeURIComponent(supplierId)}/terms`);
  }

  async putOverrideTerms(variantId: number, supplierId: string, payload: Record<string, unknown>, version: number): Promise<{ version: number }> {
    return this.request<{ version: number }>(`/product-suppliers/${variantId}/${encodeURIComponent(supplierId)}/terms`, {
      method: "PUT",
      headers: version > 0 ? { "If-Match": `"${version}"` } : {},
      body: JSON.stringify(payload),
    });
  }
}

export const api = new ApiClient();
