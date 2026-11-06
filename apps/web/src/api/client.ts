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
  variant_id: number;
  supplier_contact_id: number;
  net_cost: number | string;
  applies_recargo?: boolean;
  verified_at: string;
}

export interface CostWriteRecord {
  id: string;
  variant_id: number;
  new_cost: number | string;
  status: string;
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

export interface ProposalLine {
  id: string;
  variant_id: number;
  sku: string;
  product_name: string;
  supplier_id: string;
  supplier_name: string;
  warehouse_id: number;
  order_qty: number;
  unit_cost_net: string;
  unit_cost_recargo: string;
  line_total: string;
  explanation: string;
}

export interface Proposal {
  id: string;
  cycle_date: string;
  status: "draft" | "submitted" | "approved" | "confirmed";
  lines: ProposalLine[];
  total_net: string;
  total_with_recargo: string;
  creator: string;
  approver?: string;
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
      throw new ApiError(response.status, code);
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

  async getSuppliers(): Promise<JsonRecord[]> {
    return this.request<JsonRecord[]>("/suppliers");
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

  async getProposals(): Promise<Proposal[]> {
    return this.request<Proposal[]>("/proposals");
  }

  async getProposal(id: string): Promise<Proposal> {
    return this.request<Proposal>(`/proposals/${id}`);
  }

  async editProposalLine(proposalId: string, lineId: string, orderQty: number): Promise<JsonRecord> {
    return this.request<JsonRecord>(`/proposals/${proposalId}/lines/${lineId}`, {
      method: "PUT",
      body: JSON.stringify({ order_qty: orderQty }),
    });
  }

  async submitProposal(proposalId: string): Promise<JsonRecord> {
    return this.request<JsonRecord>(`/proposals/${proposalId}/submit`, { method: "POST" });
  }

  async approveProposal(proposalId: string): Promise<JsonRecord> {
    return this.request<JsonRecord>(`/proposals/${proposalId}/approve`, { method: "POST" });
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
}

export const api = new ApiClient();
