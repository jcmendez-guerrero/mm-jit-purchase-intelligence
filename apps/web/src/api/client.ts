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

export interface RiskItem {
  variant_id: number;
  risk_type: "stockout" | "expiry" | "data_quality";
  explanation_key: string;
  params?: Record<string, any>;
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
    metrics: Record<string, any>;
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
      const err = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(err.detail || `Error HTTP ${response.status}`);
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

  async getImportErrors(): Promise<{ count: number; items: any[] }> {
    return this.request<{ count: number; items: any[] }>("/data-quality/import-errors");
  }

  async resolveImportError(id: number, decision: "release" | "ignore"): Promise<void> {
    await this.request<void>(`/data-quality/import-errors/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    });
  }

  async getSuppliers(): Promise<any[]> {
    return this.request<any[]>("/suppliers");
  }

  async getCosts(): Promise<any[]> {
    return this.request<any[]>("/costs");
  }

  async getCostWrites(): Promise<any[]> {
    return this.request<any[]>("/cost-writes");
  }

  async approveCostWrite(writeId: string): Promise<any> {
    return this.request<any>(`/cost-writes/${writeId}/approve`, { method: "POST" });
  }

  async getProposals(): Promise<Proposal[]> {
    return this.request<Proposal[]>("/proposals");
  }

  async getProposal(id: string): Promise<Proposal> {
    return this.request<Proposal>(`/proposals/${id}`);
  }

  async editProposalLine(proposalId: string, lineId: string, orderQty: number): Promise<any> {
    return this.request<any>(`/proposals/${proposalId}/lines/${lineId}`, {
      method: "PUT",
      body: JSON.stringify({ order_qty: orderQty }),
    });
  }

  async submitProposal(proposalId: string): Promise<any> {
    return this.request<any>(`/proposals/${proposalId}/submit`, { method: "POST" });
  }

  async approveProposal(proposalId: string): Promise<any> {
    return this.request<any>(`/proposals/${proposalId}/approve`, { method: "POST" });
  }

  async getServiceLevels(): Promise<any> {
    return this.request<any>("/config/service-levels");
  }

  async getRoles(): Promise<any> {
    return this.request<any>("/admin/roles");
  }

  async updateRoles(userId: string, roles: string[]): Promise<any> {
    return this.request<any>(`/admin/roles/${userId}`, {
      method: "PUT",
      body: JSON.stringify({ roles }),
    });
  }
}

export const api = new ApiClient();
