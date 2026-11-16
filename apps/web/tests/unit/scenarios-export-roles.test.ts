import { describe, expect, it } from "vitest";
import { canExportScenario } from "../../src/features/scenarios/scenariosModel";

describe("scenario export roles (FR-010)", () => {
  it("allows buyers, approvers and admins and refuses a viewer", () => {
    expect(canExportScenario(["viewer"])).toBe(false);
    expect(canExportScenario(["viewer", "buyer"])).toBe(true);
    expect(canExportScenario(["viewer", "approver"])).toBe(true);
    expect(canExportScenario(["viewer", "admin"])).toBe(true);
  });
});
