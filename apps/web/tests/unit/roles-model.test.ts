import { describe, expect, it } from "vitest";
import { mirrorState, needsSecondApprover, oldestPendingMinutes, toggleRole } from "../../src/features/admin/rolesModel";

describe("roles view-model", () => {
  it("adds and removes a role and always keeps viewer", () => {
    expect(toggleRole(["viewer"], "buyer")).toEqual(["buyer", "viewer"]);
    expect(toggleRole(["buyer", "viewer"], "buyer")).toEqual(["viewer"]);
    expect(toggleRole(["buyer"], "approver")).toEqual(["approver", "buyer", "viewer"]);
  });

  it("reports the mirror state, failures first", () => {
    expect(mirrorState({ pending: 0, failed: 0 })).toBe("ok");
    expect(mirrorState({ pending: 2, failed: 0 })).toBe("pending");
    expect(mirrorState({ pending: 2, failed: 1 })).toBe("failed");
  });

  it("rounds the oldest pending change down to whole minutes", () => {
    expect(oldestPendingMinutes({ oldest_pending_seconds: 119 })).toBe(1);
  });

  it("flags fewer than two approvers", () => {
    expect(needsSecondApprover(1)).toBe(true);
    expect(needsSecondApprover(2)).toBe(false);
  });
});
