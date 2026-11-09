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
  pvp_age_days?: number | null;
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


export interface PolicyFields {
  service_level: string | null;
  safety_stock_units: string | null;
  min_units: string | null;
  max_units: string | null;
  replenishment_cadence_days: string | null;
}

export interface PolicySummary {
  scope: string;
  key: string;
  revision: number;
  in_force: (PolicyFields & { valid_from: string }) | null;
}

export interface PolicyDetail {
  scope: string;
  key: string;
  revision: number;
  current: (PolicyFields & { valid_from: string; revision: number; changed_by: string }) | null;
  history: Array<PolicyFields & { revision: number; valid_from: string; changed_by: string }>;
}

export interface PolicyPreview {
  as_of: string;
  affected_count: number;
  affected: Array<{ variant_id: number; qty_before: number; qty_after: number }>;
  spend_before: string;
  spend_after: string;
  spend_delta: string;
  saved: false;
}

export interface DemandExclusion {
  id: number;
  variant_id: number | null;
  from_day: string;
  to_day: string;
  reason: string;
  active: boolean;
  revision: number;
}

export interface CensoringRule {
  rule: string;
  value: number;
  min: number;
  max: number;
  default: number;
}

export interface ForecastParameter {
  key: string;
  value: string;
  default: string;
  min: string;
  max: string;
  kind: string;
  revision: number;
  in_force_revision: number | null;
}

export interface Section<T> {
  ok: boolean;
  data?: T;
  error?: string;
}

export interface PolicyConsole {
  purchasing: Section<{ as_of: string; policies: PolicySummary[]; weekly_budget: string | null }>;
  demand: Section<{ exclusions: DemandExclusion[]; rules: CensoringRule[] }>;
  forecast: Section<{ as_of: string; parameters: ForecastParameter[] }>;
}

export interface StockingSetting {
  variant_id: number;
  stocking_mode: "standard" | "always_stocked" | "on_request";
  min_floor_units: number;
  revision: number;
}

export interface OverrideRequest {
  id: string;
  variant_id: number;
  field: "safety_stock" | "min" | "max";
  recommended_value: number;
  requested_value: number;
  reason: string;
  status: "pending" | "approved" | "rejected" | "reverted";
  requested_by: string;
  decided_by: string | null;
  recommendation_changed: boolean;
  current_recommended?: number | null;
}

export interface EffectiveValue {
  value: number | null;
  source: "recommendation" | "approved_override" | "none";
  request_id: string | null;
}

export interface Recommendation {
  variant_id: number;
  safety_stock: number | null;
  effective?: { safety_stock: EffectiveValue; min: EffectiveValue; max: EffectiveValue };
}

export interface CriticalProduct {
  product_id: number;
  name: string;
  clinical_critical: boolean;
  variants: number;
}

export interface SegmentHistoryRow {
  changed_at: string;
  abc: string;
  xyz: string;
  pattern: string;
  critical: boolean;
  reason_key: string;
}


export interface SeedDataset {
  id: string;
  version: number;
  name: string;
  status: "uploaded" | "validated" | "active" | "superseded" | "rolled_back" | "rejected";
  origin: "synthetic" | "real";
  uploader: string;
  uploaded_at: string;
  activated_by: string | null;
  activated_at: string | null;
  accepted: number;
  quarantined: number;
  kinds: Record<string, number>;
  validated_by?: string | null;
  rollback_reason_code?: string | null;
  self_activation_reason_code?: string | null;
  /** Free-text details: the server sends them to admins only. */
  rollback_reason_detail?: string | null;
  self_activation_reason_detail?: string | null;
  self_activated?: boolean;
}

/** A reason for a rollback or a self-activation: a choice from a fixed list and an optional short detail (FR-033). */
export interface SeedReason {
  code: string;
  detail?: string | undefined;
}

export interface SeedUpload {
  id: string;
  version: number;
  format: string;
  headers: string[];
  row_count: number;
  suggested_mapping: Record<string, string>;
  missing: string[];
  preview: Array<Record<string, string>>;
  duplicate_of: string | null;
}

export interface SeedValidation {
  id: string;
  origin: string;
  accepted: number;
  quarantined: number;
  kinds: Record<string, number>;
}

export interface SeedQueued {
  id: string;
  queued: true;
  job_id: string;
  rows: number;
  background_over_rows: number;
}

export interface SeedJob {
  id: string;
  dataset_id: string;
  version: number;
  name: string;
  rows: number;
  stage: string;
  state: "queued" | "running" | "done" | "failed";
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_key: string | null;
  requested_by: string | null;
}

export interface SeedQuarantineRow {
  row_no: number;
  reason_key: string;
  params: Record<string, unknown>;
}

export interface SeedDryRun {
  dataset_id: string;
  compared_with: string | null;
  rows: { added: number; removed: number; changed: number; unchanged: number };
  variants_gaining_history: number[];
  variants_losing_history: number[];
  skipped_sparse: number[];
  overlap?: { variants: number; days: number };
  backtest: SeedBacktest;
}

export interface SeedBacktest {
  status: "ok" | "insufficient_history";
  basis: string;
  before: { variants: number; windows: number; cost: string };
  after: { variants: number; windows: number; cost: string };
  delta_cost: string | null;
}

export interface MappingInfo {
  mappings: Array<{ id: string; name: string; column_map: Record<string, string> }>;
  fields: string[];
  required: string[];
}


export type StatusCard<T> = { ok: true; data: T } | { ok: false; error: string };

export interface AdminStatus {
  freshness: StatusCard<{ stock_snapshots: { latest_day: string | null; rows: number }; movements: { rows: number; quarantined: number; latest_at: string | null }; aggregates: { refreshed_at: string | null } }>;
  import_jobs: StatusCard<{ jobs: SeedJob[] }>;
  model_runs: StatusCard<{ runs: Array<{ id: string; started_at: string; status: string; through_day: string; total: number; eligible: number; dataset_version_id: string | null }> }>;
  policy_history: StatusCard<Array<{ id: string; status: string; variant_id: number; [k: string]: unknown }>>;
  role_mirror: StatusCard<{ pending: number; failed: number; sent: number; oldest_pending_seconds: number }>;
  cost: { budget_eur: number; estimate_eur: number; guardrails: { min_replicas: number; max_replicas: number; job_parallelism: number } };
}

export interface ScenarioSummary {
  baseline: { total: string; over_budget: string; lines: number };
  scenario: { total: string; over_budget: string; lines: number; budget: string | null; utilisation: string | null };
  delta_total: string;
  changes: Array<{ variant_id: number; supplier_before: string | null; supplier_after: string | null; qty_before: number; qty_after: number; reasons: string[] }>;
  binding: Array<{ key: string; params: Record<string, string> }>;
  infeasible: { over_by: string; clinical_critical_variants: number[] } | null;
  notes: string[];
}

export interface ScenarioDetail {
  id: string;
  name: string;
  status: "computing" | "ready" | "failed" | "promoted";
  parameters: Record<string, unknown>;
  result_hash: string | null;
  input_versions?: { dataset?: string | null; forecast_run?: string | null } & Record<string, unknown>;
  created_by: string;
  created_at: string;
  summary: ScenarioSummary | null;
  results: Array<{ supplier_id: string; supplier_name: string | null; order_total: string; subtotal?: string | null; delivery_charge?: string | null; discount?: string | null; free_delivery?: boolean | null;
    expected_delivery: string | null; budget_utilisation: string | null;
    lines: Array<{ variant_id: number; qty: number; unit_cost: string; line_total: string; clinical_critical: boolean }> }>;
  sensitivity: Array<{ constraint_key: string; delta: string; cost_impact: string }>;
}

export interface ScenarioListItem {
  id: string;
  name: string;
  status: string;
  created_by: string;
  created_at: string;
  delta_total: string | null;
}

export interface ScenarioRequest {
  name: string;
  budget?: string;
  disabled_suppliers: string[];
  supplier_deltas: Record<string, Record<string, string | number>>;
  service_level_delta: string;
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
  /** Version of the terms (the If-Match of the terms editor). */
  version: number;
  /** MMI 004: supplier management fields. Older servers omit them. */
  supplier_version?: number;
  status?: "active" | "deactivated";
  classification?: "purchasing" | "non_purchasing" | "unclassified";
  origin?: "platform" | "imported" | "erp";
  erp_link_state?: "none" | "unverified" | "linked" | "pending_link";
  fiscal_type?: "national" | "intracommunity" | "foreign";
  country?: string;
  currency?: string;
  payment_terms_days?: number | null;
  order_channel?: "email" | "phone" | "web" | "other" | null;
  merged_into?: string | null;
}

export interface SupplierInputDoc {
  name: string;
  fiscal_type: string;
  country: string;
  currency: string;
  payment_terms_days?: number | null;
  order_channel?: string | null;
  classification?: string;
}

export interface SupplierLinkRow {
  sku: string | null;
  name: string | null;
  cost: string;
  currency: string;
  cost_source: string;
  includes_recargo: boolean;
  pack_size: number | null;
  min_qty: number | null;
  verified_at: string;
  erp_link: "no_link" | "link_without_cost" | "link_with_cost";
}

export interface LinkInputDoc {
  cost?: string;
  includes_recargo?: boolean;
  cost_source?: "manual" | "inventory_export";
  pack_size?: number;
  min_qty?: number;
}

export interface DeactivationPreview {
  deactivated: boolean;
  open_proposal_lines: number;
  lines: Array<{ proposal_id: string; variant_id: number }>;
}

export interface BulkPreview {
  batch_id: string;
  matched: number;
  new: number;
  existing: number;
  conflicts: number;
  conflict_skus: string[];
  unknown: string[];
  expires_at: string;
}

export interface BulkFileResult {
  groups: Record<string, string[]>;
  errors: Array<{ row: number; code: string }>;
  rows: number;
}

export interface SupplierReviewItem {
  id: string;
  kind: string;
  supplier_id: string | null;
  detail: string;
  status: string;
  created_at: string;
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
    /** Columns the loader found missing in an export file (local load only). */
    public readonly missing?: string[],
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
    // A refusal for lack of permission always gets the no-permission sentence, whatever code the server used.
    if (err.status === 403) return i18n.t("errors.auth_forbidden_role");
  }
  return fallback;
}

export interface RiskItem {
  variant_id: number;
  risk_type: "stockout" | "expiry" | "data_quality";
  explanation_key: string;
  params?: JsonRecord;
}


export interface DashCard<T> {
  ok: boolean;
  data?: T;
  error?: string;
}

export interface DashSummary {
  day: string;
  inventory_value: string | null;
  valued_with_estimate: number;
  unvalued_lots: number;
  value_basis: string;
  expiring_value: string | null;
  stockout_risk: number;
  expiry_risk: number;
  coverage_days_avg: string | null;
  variants_without_demand: number;
  coverage_basis: { forecast: number; actual_90d: number };
  variant_count: number;
  forecast_available: boolean;
}

export interface DashTrend {
  from: string;
  to: string;
  series: Array<{ day: string; actual: number; censored_rows: number; kind: string }>;
  estimated: Array<{ day: string; mean: string; upper: string; kind: string }>;
  estimated_basis?: { variants: number; seed_assisted: number; reason: "no_forecast" | "company_wide_only" | null; upper_level: string };
}

export interface DashOverview {
  summary: DashCard<DashSummary>;
  trend: DashCard<DashTrend>;
  abc_xyz: DashCard<{ cells: Array<{ abc: string; xyz: string; variant_count: number; value: string }> }>;
  risks: DashCard<RiskItem[]>;
  options: DashCard<{ warehouses: Array<{ id: number; name: string }>; categories: Array<{ id: string; kind: string }>; families?: Array<{ id: string }>; family_available: boolean }>;
  accuracy: DashCard<{ run_id: string | null; window_days: number; metrics: Record<string, Record<string, string>> }>;
  spend: DashCard<{ proposal_id: string | null; week: string | null; status: string | null; total: string; by_supplier: Array<{ supplier_id: string; supplier_name: string | null; total: string }>; budget: string | null; over_budget: boolean }>;
  suppliers: DashCard<Array<{ id: string; name: string }>>;
}

export interface ForecastBasis {
  run_id: string;
  variant_id: number;
  eligible: boolean;
  policy: string;
  seed_used: boolean;
  horizons?: Array<{ days: number; mean: number; upper: number }>;
  upper_level?: string;
}

export type DrillKind = "inventory_value" | "coverage" | "stockout_risk" | "expiry_risk" | "abc_xyz" | "trend_day";

export interface DrillRequest {
  kind: DrillKind;
  abc?: string | undefined;
  xyz?: string | undefined;
  day?: string | undefined;
  warehouse_id?: number | undefined;
  category?: string | undefined;
  family?: string | undefined;
}

export interface DrillResponse {
  kind: DrillKind;
  truncated: boolean;
  total: number;
  rows: Array<{ variant_id: number; sku: string | null; name: string | null; figure: string | null }>;
}

export interface DashFilters {
  warehouse_id?: number | undefined;
  category?: string | undefined;
  family?: string | undefined;
  days?: number | undefined;
  supplier_id?: string | undefined;
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
  risks?: Array<{ risk_type: string; explanation_key: string; params: Record<string, unknown> }>;
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
  forecast_basis?: "imported_estimates" | "actual_demand";
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
  policy_version_ids?: Record<string, unknown> | null;
  dataset_version_id?: string | null;
  forecast_run_id?: string | null;
  approval: { approver: string; decision: string; version: number; valid: boolean } | null;
  warnings?: string[];
}

/** Local export loader (MMI 004): present only in the local environment. */
export type LocalLoadKind = "suppliers" | "inventory" | "movements";

export interface LocalLoadReviewItem {
  row: number;
  code: string;
  detail?: string;
  source?: "loader" | "platform";
  kind?: LocalLoadKind;
}

export interface LocalLoadResult {
  run_id: string;
  kind: LocalLoadKind;
  rows: number;
  loaded: number;
  updated: number;
  unchanged: number;
  quarantined: number;
  excluded: number;
  services: number;
  differences?: number;
  review: LocalLoadReviewItem[];
  interpretations?: { tax_included_rows?: number; tax_excluded_rows?: number; timezone?: string };
}

export interface LocalLoadDifference {
  id: string;
  sku: string;
  field: string;
  app_value: string;
  file_value: string;
  status: "open" | "accepted" | "ignored";
}

let unauthorizedListener: (() => void) | null = null;

/** Registers a callback for HTTP 401 answers from any call except the session probe and sign-in (FR-020). */
export function onUnauthorized(listener: (() => void) | null): void {
  unauthorizedListener = listener;
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

    if (response.status === 401 && path !== "/me" && !path.startsWith("/auth/")) unauthorizedListener?.();

    if (!response.ok) {
      const err = await response.json().catch(() => ({}) as { detail?: unknown });
      const detail = (err as { detail?: unknown }).detail;
      const code = typeof detail === "string" && /^[a-z][a-z0-9_:]*$/.test(detail) ? detail : Array.isArray(detail) ? "request_invalid" : "unknown";
      const current = (err as { current_version?: unknown }).current_version;
      const missing = (err as { missing?: unknown }).missing;
      throw new ApiError(response.status, code, typeof current === "number" ? current : undefined,
        Array.isArray(missing) ? missing.filter((m): m is string => typeof m === "string") : undefined);
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

  async getAuthConfig(): Promise<{ mode: "dev" | "entra" | "none" }> {
    return this.request("/auth/config");
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

  async getForecastBasis(variantId: number): Promise<ForecastBasis> {
    return this.request(`/dashboard/variants/${variantId}/forecast-basis`);
  }

  async getDrilldown(r: DrillRequest): Promise<DrillResponse> {
    const q = new URLSearchParams({ kind: r.kind });
    if (r.abc) q.set("abc", r.abc);
    if (r.xyz) q.set("xyz", r.xyz);
    if (r.day) q.set("day", r.day);
    if (r.warehouse_id !== undefined) q.set("warehouse_id", String(r.warehouse_id));
    if (r.category) q.set("category", r.category);
    if (r.family) q.set("family", r.family);
    return this.request<DrillResponse>(`/dashboard/drilldown?${q.toString()}`);
  }

  async getDashboardOverview(f: DashFilters = {}): Promise<DashOverview> {
    const q = new URLSearchParams();
    if (f.warehouse_id !== undefined) q.set("warehouse_id", String(f.warehouse_id));
    if (f.category) q.set("category", f.category);
    if (f.family) q.set("family", f.family);
    if (f.days) q.set("days", String(f.days));
    if (f.supplier_id) q.set("supplier_id", f.supplier_id);
    const qs = q.toString();
    return this.request<DashOverview>(`/dashboard/overview${qs ? `?${qs}` : ""}`);
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

  /** The buyer's opening cost for a pair whose ERP record has none. It becomes a lot entry, never a free supplier cost. */
  async addOpeningCost(body: { variant_id: number; supplier_id: string; amount: string; includes_recargo: boolean }): Promise<JsonRecord> {
    return this.request<JsonRecord>("/lot-costs", { method: "POST", body: JSON.stringify({ ...body, lot: "opening", source: "buyer_entry", quantity: 0 }) });
  }

  /** Builds the review request carrying the median of the lots in stock (or the opening entry). Nothing is sent to the ERP from here. */
  async requestCostUpdate(productId: number, supplierId: string): Promise<{ status: string; warnings: string[]; request_id: string | null }> {
    return this.request<{ status: string; warnings: string[]; request_id: string | null }>("/cost-updates", {
      method: "POST", body: JSON.stringify({ product_id: productId, supplier_id: supplierId }),
    });
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


  async getPolicyConsole(): Promise<PolicyConsole> {
    return this.request<PolicyConsole>("/policy-console");
  }

  async getPolicy(scope: string, key: string): Promise<PolicyDetail> {
    return this.request<PolicyDetail>(`/policies/${scope}/${encodeURIComponent(key)}`);
  }

  async putPolicy(scope: string, key: string, body: Record<string, unknown>, version: number): Promise<{ revision: number }> {
    return this.request<{ revision: number }>(`/policies/${scope}/${encodeURIComponent(key)}`, {
      method: "PUT",
      headers: version > 0 ? { "If-Match": `"${version}"` } : {},
      body: JSON.stringify(body),
    });
  }

  async previewPolicy(scope: string, key: string, body: Record<string, unknown>): Promise<PolicyPreview> {
    return this.request<PolicyPreview>(`/policies/${scope}/${encodeURIComponent(key)}/preview`, { method: "POST", body: JSON.stringify(body) });
  }

  async putBudgetCap(body: Record<string, unknown>): Promise<{ weekly_budget: string | null }> {
    return this.request<{ weekly_budget: string | null }>("/budget-caps", { method: "PUT", body: JSON.stringify(body) });
  }

  async getStocking(variantId: number): Promise<StockingSetting> {
    return this.request<StockingSetting>(`/stocking/${variantId}`);
  }

  async putStocking(variantId: number, body: { stocking_mode: string; min_floor_units: number }, version: number): Promise<{ revision: number }> {
    return this.request<{ revision: number }>(`/stocking/${variantId}`, {
      method: "PUT",
      headers: version > 0 ? { "If-Match": `"${version}"` } : {},
      body: JSON.stringify(body),
    });
  }

  async getOverrides(status: string = "pending"): Promise<OverrideRequest[]> {
    return this.request<OverrideRequest[]>(`/policy-overrides?status=${status}`);
  }

  async getRecommendation(variantId: number): Promise<Recommendation> {
    return this.request<Recommendation>(`/policy-overrides/recommendation/${variantId}`);
  }

  async createOverride(body: { variant_id: number; field: string; requested_value: number; reason: string }): Promise<OverrideRequest> {
    return this.request<OverrideRequest>("/policy-overrides", { method: "POST", body: JSON.stringify(body) });
  }

  async decideOverride(id: string, action: "approve" | "reject" | "revert"): Promise<OverrideRequest> {
    return this.request<OverrideRequest>(`/policy-overrides/${id}/${action}`, { method: "POST", body: JSON.stringify({}) });
  }

  async getCriticality(): Promise<{ products: CriticalProduct[] }> {
    return this.request<{ products: CriticalProduct[] }>("/criticality");
  }

  async setCriticality(productId: number, critical: boolean): Promise<JsonRecord> {
    return this.request<JsonRecord>(`/products/${productId}/criticality`, { method: "PUT", body: JSON.stringify({ critical }) });
  }

  async addExclusion(body: { variant_id: number | null; from_day: string; to_day: string; reason: string }): Promise<{ id: number }> {
    return this.request<{ id: number }>("/demand-rules/exclusions", { method: "POST", body: JSON.stringify(body) });
  }

  async toggleExclusion(id: number, active: boolean): Promise<JsonRecord> {
    return this.request<JsonRecord>(`/demand-rules/exclusions/${id}`, { method: "PUT", body: JSON.stringify({ active }) });
  }

  async putCensoringRule(rule: string, value: number): Promise<JsonRecord> {
    return this.request<JsonRecord>(`/demand-rules/rules/${rule}`, { method: "PUT", body: JSON.stringify({ value }) });
  }

  async getSegmentHistory(variantId: number): Promise<{ variant_id: number; history: SegmentHistoryRow[] }> {
    return this.request<{ variant_id: number; history: SegmentHistoryRow[] }>(`/segments/${variantId}/history`);
  }

  async putParameter(key: string, value: string, version: number): Promise<{ revision: number }> {
    return this.request<{ revision: number }>(`/parameters/${encodeURIComponent(key)}`, {
      method: "PUT",
      headers: version > 0 ? { "If-Match": `"${version}"` } : {},
      body: JSON.stringify({ value }),
    });
  }

  async requestForecast(): Promise<{ run_id: string; reused: boolean }> {
    return this.request<{ run_id: string; reused: boolean }>("/forecast/runs", { method: "POST", body: JSON.stringify({}) });
  }


  async getSeedDatasets(): Promise<{ datasets: SeedDataset[] }> {
    return this.request<{ datasets: SeedDataset[] }>("/imports");
  }

  async getSuppliersFiltered(filter: { status?: string; classification?: string; q?: string }): Promise<SupplierSummary[]> {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(filter)) if (v) params.set(k, v);
    const qs = params.toString();
    return this.request<SupplierSummary[]>(`/suppliers${qs ? `?${qs}` : ""}`);
  }

  async createSupplier(body: SupplierInputDoc, confirmDuplicate = false): Promise<SupplierSummary> {
    return this.request<SupplierSummary>(`/suppliers${confirmDuplicate ? "?confirm_duplicate=true" : ""}`, { method: "POST", body: JSON.stringify(body) });
  }

  async updateSupplier(id: string, changes: Partial<SupplierInputDoc>, version: number, confirmDuplicate = false): Promise<SupplierSummary> {
    return this.request<SupplierSummary>(`/suppliers/${encodeURIComponent(id)}${confirmDuplicate ? "?confirm_duplicate=true" : ""}`, {
      method: "PATCH",
      headers: { "If-Match": `"${version}"` },
      body: JSON.stringify(changes),
    });
  }

  async deactivateSupplier(id: string, confirm: boolean): Promise<DeactivationPreview> {
    return this.request<DeactivationPreview>(`/suppliers/${encodeURIComponent(id)}/deactivate`, { method: "POST", body: JSON.stringify({ confirm }) });
  }

  async reactivateSupplier(id: string): Promise<SupplierSummary> {
    return this.request<SupplierSummary>(`/suppliers/${encodeURIComponent(id)}/reactivate`, { method: "POST" });
  }

  async getSupplierLinks(id: string): Promise<SupplierLinkRow[]> {
    return this.request<SupplierLinkRow[]>(`/suppliers/${encodeURIComponent(id)}/links`);
  }

  async putSupplierLink(id: string, sku: string, body: LinkInputDoc): Promise<{ cost: string; erp_link: string; write_case: string | null; warnings: string[] }> {
    return this.request(`/suppliers/${encodeURIComponent(id)}/links/${encodeURIComponent(sku)}`, { method: "PUT", body: JSON.stringify(body) });
  }

  async deleteSupplierLink(id: string, sku: string): Promise<void> {
    await this.request<unknown>(`/suppliers/${encodeURIComponent(id)}/links/${encodeURIComponent(sku)}`, { method: "DELETE" });
  }

  async previewBulkLinks(id: string, criteria: { skus?: string[]; q?: string }): Promise<BulkPreview> {
    return this.request<BulkPreview>(`/suppliers/${encodeURIComponent(id)}/links/bulk/preview`, { method: "POST", body: JSON.stringify(criteria) });
  }

  async applyBulkLinks(id: string, batchId: string, skipConflicts: boolean): Promise<{ changed: number; skipped_conflicts: number; no_cost: number }> {
    return this.request(`/suppliers/${encodeURIComponent(id)}/links/bulk/apply`, { method: "POST", body: JSON.stringify({ batch_id: batchId, skip_conflicts: skipConflicts }) });
  }

  async parseAssignmentFile(file: File): Promise<BulkFileResult> {
    const form = new FormData();
    form.append("file", file);
    return this.request<BulkFileResult>("/links/bulk/file", { method: "POST", body: form });
  }

  async getSupplierReviewItems(): Promise<SupplierReviewItem[]> {
    return this.request<SupplierReviewItem[]>("/suppliers/review-items");
  }

  async resolveSupplierReviewItem(id: string, decision: "merge_into" | "keep_both" | "ignore", mergeInto?: string): Promise<void> {
    await this.request<unknown>(`/suppliers/review-items/${encodeURIComponent(id)}/resolve`, {
      method: "POST",
      body: JSON.stringify(mergeInto ? { decision, merge_into: mergeInto } : { decision }),
    });
  }

  async getLocalLoadCapability(): Promise<{ enabled: boolean }> {
    return this.request<{ enabled: boolean }>("/local-load/capability");
  }

  async checkLocalLoad(kind: LocalLoadKind, file: File): Promise<LocalLoadResult> {
    const form = new FormData();
    form.append("file", file);
    return this.request<LocalLoadResult>(`/local-load/${kind}/check`, { method: "POST", body: form });
  }

  async runLocalLoad(kind: LocalLoadKind, file: File, acknowledgeInterpretation: boolean, idempotencyKey: string): Promise<LocalLoadResult> {
    const form = new FormData();
    form.append("file", file);
    return this.request<LocalLoadResult>(`/local-load/${kind}?acknowledge_interpretation=${acknowledgeInterpretation ? "true" : "false"}`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: form,
    });
  }

  async getLocalLoadRuns(): Promise<LocalLoadResult[]> {
    return this.request<LocalLoadResult[]>("/local-load/runs");
  }

  async getLocalLoadReview(): Promise<LocalLoadReviewItem[]> {
    return this.request<LocalLoadReviewItem[]>("/local-load/review");
  }

  async getLocalLoadDifferences(): Promise<LocalLoadDifference[]> {
    return this.request<LocalLoadDifference[]>("/local-load/differences");
  }

  async decideLocalLoadDifference(id: string, decision: "accept" | "ignore"): Promise<void> {
    await this.request<unknown>(`/local-load/differences/${encodeURIComponent(id)}/${decision}`, { method: "POST" });
  }

  async getMappings(): Promise<MappingInfo> {
    return this.request<MappingInfo>("/imports/mappings");
  }

  async saveMapping(name: string, columnMap: Record<string, string>): Promise<{ id: string }> {
    return this.request<{ id: string }>("/imports/mappings", { method: "POST", body: JSON.stringify({ name, column_map: columnMap }) });
  }

  async uploadSeed(file: File, name: string): Promise<SeedUpload> {
    const form = new FormData();
    form.append("file", file);
    form.append("name", name);
    return this.request<SeedUpload>("/imports", { method: "POST", body: form });
  }

  /** Returns the result, or ``queued`` when a large file was sent to the background (the status section then shows it). */
  async validateSeed(id: string, columnMap: Record<string, string>): Promise<SeedValidation | SeedQueued> {
    return this.request<SeedValidation | SeedQueued>(`/imports/${id}/validate`, { method: "POST", body: JSON.stringify({ column_map: columnMap }) });
  }

  async getSeedJobs(): Promise<{ jobs: SeedJob[]; background_over_rows: number }> {
    return this.request<{ jobs: SeedJob[]; background_over_rows: number }>("/imports/jobs");
  }

  async getSeedQuarantine(id: string): Promise<{ rows: SeedQuarantineRow[] }> {
    return this.request<{ rows: SeedQuarantineRow[] }>(`/imports/${id}/quarantine`);
  }

  async dryRunSeed(id: string): Promise<SeedDryRun> {
    return this.request<SeedDryRun>(`/imports/${id}/dry-run`, { method: "POST", body: JSON.stringify({}) });
  }

  async activateSeed(id: string, acknowledgeDuplicate: boolean, reason?: SeedReason): Promise<JsonRecord> {
    return this.request<JsonRecord>(`/imports/${id}/activate`, {
      method: "POST",
      body: JSON.stringify({ acknowledge_duplicate: acknowledgeDuplicate, ...(reason ? { reason_code: reason.code, ...(reason.detail ? { reason_detail: reason.detail } : {}) } : {}) }),
    });
  }

  async rollbackSeed(reason: SeedReason): Promise<JsonRecord> {
    return this.request<JsonRecord>("/imports/rollback", { method: "POST", body: JSON.stringify({ reason_code: reason.code, ...(reason.detail ? { reason_detail: reason.detail } : {}) }) });
  }

  async rejectSeed(id: string): Promise<void> {
    await this.request<void>(`/imports/${id}/reject`, { method: "POST", body: JSON.stringify({}) });
  }


  async createScenario(body: ScenarioRequest, idempotencyKey: string): Promise<ScenarioDetail> {
    return this.request<ScenarioDetail>("/scenarios", { method: "POST", body: JSON.stringify(body), headers: { "Idempotency-Key": idempotencyKey } });
  }

  async getScenarios(): Promise<{ scenarios: ScenarioListItem[] }> {
    return this.request<{ scenarios: ScenarioListItem[] }>("/scenarios");
  }

  async getScenario(id: string): Promise<ScenarioDetail> {
    return this.request<ScenarioDetail>(`/scenarios/${id}`);
  }

  async promoteScenario(id: string): Promise<{ proposal_id: string; week: string; superseded: string[] }> {
    return this.request<{ proposal_id: string; week: string; superseded: string[] }>(`/scenarios/${id}/promote`, { method: "POST", body: JSON.stringify({}) });
  }

  async getServiceLevels(): Promise<{ history?: ServiceLevelEntry[] }> {
    return this.request<{ history?: ServiceLevelEntry[] }>("/config/service-levels");
  }


  async getAdminStatus(): Promise<AdminStatus> {
    return this.request<AdminStatus>("/admin/status");
  }

  async rerunForecast(): Promise<{ run_id: string; reused: boolean }> {
    return this.request<{ run_id: string; reused: boolean }>("/admin/rerun/forecast", { method: "POST", body: JSON.stringify({}) });
  }

  async rerunImportJob(jobId: string): Promise<{ job_id: string; reused: boolean }> {
    return this.request<{ job_id: string; reused: boolean }>(`/admin/rerun/import/${encodeURIComponent(jobId)}`, { method: "POST", body: JSON.stringify({}) });
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
