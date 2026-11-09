import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../src/api/client";
import { saveKeys } from "../../src/features/suppliers/termsModel";

/** T022 (FR-014): a save carries an Idempotency-Key, and a retry of the same save carries the same one. */

function capture() {
  const sent: Headers[] = [];
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init: RequestInit) => {
    sent.push(new Headers(init.headers));
    return new Response(JSON.stringify({ version: 2 }), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
  return sent;
}

afterEach(() => vi.unstubAllGlobals());

describe("the terms saves send the key", () => {
  it("adds Idempotency-Key next to If-Match on a supplier save", async () => {
    const sent = capture();
    await api.putSupplierTerms("s1", { lead_time_days: 3 }, 1, "key-1");
    expect(sent[0]?.get("Idempotency-Key")).toBe("key-1");
    expect(sent[0]?.get("If-Match")).toBe('"1"');
  });

  it("adds it on a product override save too", async () => {
    const sent = capture();
    await api.putOverrideTerms(1, "s1", { lead_time_days: 3 }, 0, "key-2");
    expect(sent[0]?.get("Idempotency-Key")).toBe("key-2");
    expect(sent[0]?.get("If-Match")).toBeNull();
  });

  it("sends no header when there is no key", async () => {
    const sent = capture();
    await api.putSupplierTerms("s1", {}, 0);
    expect(sent[0]?.has("Idempotency-Key")).toBe(false);
  });
});

describe("one key per distinct save", () => {
  it("keeps the key while the save is unchanged and issues a new one when it changes", () => {
    let n = 0;
    const keyFor = saveKeys(() => `k${++n}`);
    expect(keyFor("form-a|v1")).toBe("k1");
    expect(keyFor("form-a|v1")).toBe("k1");          // the retry of the same click
    expect(keyFor("form-b|v1")).toBe("k2");          // the user changed something
    expect(keyFor("form-b|v2")).toBe("k3");          // the saved version moved on
  });
});
