import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** T119 (web side): warehouse, category and supplier options come from the API, never from the source. */
const DIR = join(__dirname, "../../src/features/dashboard");

describe("dashboard options", () => {
  it("contains no warehouse names or ids in the source", () => {
    for (const f of readdirSync(DIR).filter((n) => n.endsWith(".tsx") || n.endsWith(".ts"))) {
      const text = readFileSync(join(DIR, f), "utf8");
      expect(text, f).not.toMatch(/Almac[eé]n (Central|Norte)/);
      expect(text, f).not.toMatch(/<option value="\d+"/);
    }
  });
});
