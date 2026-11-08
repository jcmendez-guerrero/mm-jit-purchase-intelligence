import { describe, expect, it } from "vitest";
import { canApprove, canEditLines, canSubmit, parseQty } from "../../src/features/proposals/proposalModel";

describe("proposal permissions", () => {
  it("only buyers edit and submit drafts", () => {
    expect(canEditLines(["viewer", "buyer"], "draft")).toBe(true);
    expect(canSubmit(["buyer"], "draft")).toBe(true);
    expect(canEditLines(["buyer"], "submitted")).toBe(false);
    expect(canEditLines(["admin", "approver"], "draft")).toBe(false);
  });
  it("only approvers approve submitted proposals; admin alone cannot", () => {
    expect(canApprove(["approver"], "submitted")).toBe(true);
    expect(canApprove(["admin"], "submitted")).toBe(false);
    expect(canApprove(["approver"], "draft")).toBe(false);
  });
});

describe("parseQty", () => {
  it("accepts whole non-negative numbers", () => {
    expect(parseQty(" 12 ")).toBe(12);
    expect(parseQty("0")).toBe(0);
  });
  it("rejects anything else", () => {
    for (const bad of ["", "-1", "1.5", "1,5", "abc", "1e3", "99999999999999999999"]) expect(parseQty(bad)).toBeNull();
  });
});
