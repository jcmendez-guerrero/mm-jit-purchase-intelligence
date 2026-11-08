import type { IconName } from "./icons/paths";

/**
 * One vocabulary for every status in the app (FR-008, data-model.md "Status vocabulary").
 * Every status has a label, a tone and an icon, so meaning never rests on colour alone.
 * Codes are the values the existing APIs already return.
 */

export type Tone = "neutral" | "info" | "success" | "warning" | "danger";
export type StatusDomain = "risk" | "cost_write" | "approval" | "import" | "scenario" | "quarantine" | "tag";

export interface StatusInfo {
  /** Translation key. Absent only for raw data codes (quarantine anomaly codes), which are shown as they are. */
  labelKey?: string;
  tone: Tone;
  icon: IconName;
}

const s = (labelKey: string, tone: Tone, icon: IconName): StatusInfo => ({ labelKey, tone, icon });

export const STATUS_VOCABULARY: Record<StatusDomain, Record<string, StatusInfo>> = {
  risk: {
    stockout: s("dashboard.risk_stockout", "danger", "error"),
    expiry: s("dashboard.risk_expiry", "warning", "warning"),
    data_quality: s("dashboard.risk_quality", "info", "info"),
    out_of_stock: s("ui.severity.out_of_stock", "danger", "error"),
    imminent: s("ui.severity.imminent", "warning", "warning"),
    below_reorder_point: s("ui.severity.below_reorder_point", "info", "info"),
  },
  cost_write: {
    pending_review: s("costs.status.pending_review", "warning", "warning"),
    pending_link: s("costs.status.pending_link", "warning", "warning"),
    approved_by_buyer: s("costs.status.approved_by_buyer", "info", "check"),
    sent: s("costs.status.sent", "info", "info"),
    retrying: s("costs.status.retrying", "warning", "warning"),
    failed: s("costs.status.failed", "danger", "error"),
    succeeded: s("costs.status.succeeded", "success", "check"),
    cancelled: s("costs.status.cancelled", "neutral", "close"),
  },
  approval: {
    draft: s("proposals.status.draft", "neutral", "info"),
    submitted: s("proposals.status.submitted", "info", "info"),
    approved: s("proposals.status.approved", "success", "check"),
    confirmed: s("proposals.status.confirmed", "success", "check"),
  },
  import: {
    uploaded: s("imports.status.uploaded", "neutral", "info"),
    validated: s("imports.status.validated", "info", "check"),
    active: s("imports.status.active", "success", "check"),
    superseded: s("imports.status.superseded", "neutral", "info"),
    rolled_back: s("imports.status.rolled_back", "warning", "warning"),
    rejected: s("imports.status.rejected", "danger", "error"),
    queued: s("imports.job.state.queued", "neutral", "info"),
    running: s("imports.job.state.running", "info", "info"),
    done: s("imports.job.state.done", "success", "check"),
    failed: s("imports.job.state.failed", "danger", "error"),
  },
  scenario: {
    computing: s("scenarios.status.computing", "info", "info"),
    ready: s("scenarios.status.ready", "success", "check"),
    failed: s("scenarios.status.failed", "danger", "error"),
    promoted: s("scenarios.status.promoted", "success", "check"),
  },
  // Tags that are not workflow statuses but still need an icon and a word: supplier flags, where a value comes from, caveats.
  tag: {
    preferred: s("suppliers.badge.preferred", "info", "check"),
    disabled: s("suppliers.badge.disabled", "neutral", "close"),
    source_erp: s("suppliers.source.erp", "neutral", "info"),
    source_import: s("suppliers.source.import", "neutral", "imports"),
    source_manual: s("suppliers.source.manual", "info", "user"),
    source_override: s("suppliers.source.override", "info", "config"),
    source_supplier: s("suppliers.source.supplier", "neutral", "suppliers"),
    source_cost: s("suppliers.source.cost", "neutral", "costs"),
    source_default: s("suppliers.source.default", "neutral", "info"),
    estimate: s("proposals.badge.estimate", "warning", "warning"),
    changed: s("ui.tag.changed", "warning", "warning"),
    required: s("imports.mapping.required", "success", "check"),
  },
  // Anomaly codes come from the data itself and are shown as they are, always as a warning.
  quarantine: {},
};

export function statusInfo(domain: StatusDomain, code: string): StatusInfo {
  const known = STATUS_VOCABULARY[domain][code];
  if (known) return known;
  if (domain === "quarantine") return { tone: "warning", icon: "warning" };
  return { labelKey: "ui.status.unknown", tone: "neutral", icon: "info" };
}
