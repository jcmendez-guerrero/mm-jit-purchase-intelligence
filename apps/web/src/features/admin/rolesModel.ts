import type { RoleMirrorStatus } from "../../api/client";

/** Roles an admin can assign; "viewer" is implicit for every user and cannot be removed. */
export const ASSIGNABLE_ROLES = ["buyer", "approver", "admin"] as const;

export function toggleRole(current: string[], role: string): string[] {
  const next = current.includes(role) ? current.filter((r) => r !== role) : [...current, role];
  if (!next.includes("viewer")) next.push("viewer");
  return [...new Set(next)].sort();
}

export type MirrorState = "ok" | "pending" | "failed";

export function mirrorState(status: Pick<RoleMirrorStatus, "pending" | "failed">): MirrorState {
  if (status.failed > 0) return "failed";
  return status.pending > 0 ? "pending" : "ok";
}

export function oldestPendingMinutes(status: Pick<RoleMirrorStatus, "oldest_pending_seconds">): number {
  return Math.floor(status.oldest_pending_seconds / 60);
}

export function needsSecondApprover(approvers: number): boolean {
  return approvers < 2;
}
