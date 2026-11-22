import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

// Feature 014 (T088, FR-008a): the browser identifies products by SKU only. The internal id stays between services,
// so the web source (outside the generated service-level types) never names it, and no Spanish text shows a numeric product id.

const src = join(__dirname, "..", "..", "src");

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return p.includes(join("src", "api", "generated")) ? [] : files(p);
    return /\.(ts|tsx)$/.test(p) ? [p] : [];
  });
}

describe("the web app never names the internal product id", () => {
  it("has no variant_id or variantId in the source", () => {
    const hits = files(src).flatMap((f) => readFileSync(f, "utf8").split("\n").flatMap((l, i) => (/variant_id|variantId/.test(l) ? [`${relative(src, f)}:${i + 1}`] : [])));
    expect(hits).toEqual([]);
  });

  it("shows no numeric product id in the Spanish catalogue", () => {
    const catalogue = JSON.parse(readFileSync(join(src, "i18n", "es-ES.json"), "utf8")) as Record<string, string>;
    const bad = Object.entries(catalogue).filter(([, v]) => /variante\s*(#|n\.º)?\s*\{\{\s*(id|variant)\s*\}\}|ID de variante|Variante \(número\)/i.test(v));
    expect(bad).toEqual([]);
  });
});
