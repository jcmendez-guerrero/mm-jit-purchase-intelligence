import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

// T048 (feature 012, FR-004, project rule 5): people see the SKU, never the Siweb variant id.
// Screens that still render it are listed in a baseline that may only shrink; a new one fails the build.

const webRoot = join(__dirname, "..", "..");
const baselineFile = join(__dirname, "variant-id-display.baseline.json");

/** An interpolation (`{ variant: x.variant_id }`), a table cell, a `#id` label or a `?? variant_id` fallback. */
export const DISPLAYS_VARIANT_ID = /\w+:\s*[\w.]+\.variant_id\s*[,}]|cell:\s*\([^)]*\)\s*=>\s*[\w.]+\.variant_id\b|#\$?\{[\w.]*variant_id\}|\?\?\s*[\w.]*variant_id/g;

function tsx(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return tsx(p);
    return p.endsWith(".tsx") ? [p] : [];
  });
}

export const count = (source: string) => source.split("\n").reduce((n, l) => n + (l.match(DISPLAYS_VARIANT_ID)?.length ?? 0), 0);

describe("the Siweb variant id is not shown to people", () => {
  const baseline = JSON.parse(readFileSync(baselineFile, "utf8")) as Record<string, number>;

  it("detects each way of showing it (self-check)", () => {
    expect(count("t('x', { variant: a.variant_id, y: 1 })")).toBe(1);
    expect(count("{ id: 'v', cell: (r) => r.variant_id }")).toBe(1);
    expect(count("<td>#{ln.variant_id}</td>")).toBe(1);
    expect(count("<b>{l.sku ?? l.variant_id}</b>")).toBe(1);
    expect(count("setDetail(r.variant_id); const key = `${w.id}:${l.variant_id}`; rowKey={(r) => r.variant_id}")).toBe(0);
  });

  it("no screen shows it beyond the baseline", () => {
    const over: string[] = [];
    for (const f of tsx(join(webRoot, "src", "features"))) {
      const rel = relative(webRoot, f);
      const n = count(readFileSync(f, "utf8"));
      if (n > (baseline[rel] ?? 0)) over.push(`${rel}: ${n} > ${baseline[rel] ?? 0}; show the SKU (the payload needs a sku field)`);
    }
    expect(over).toEqual([]);
  });

  it("the baseline only lists files that still show it (lower it when one is fixed)", () => {
    for (const [rel, n] of Object.entries(baseline)) {
      expect(count(readFileSync(join(webRoot, rel), "utf8")), `${rel} improved; lower or remove its baseline`).toBeGreaterThanOrEqual(n);
    }
  });
});
