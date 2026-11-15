import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

// T028 (feature 012, FR-016, project rule 7): free-text ERP notes are never shown; only a has_note flag may exist.
// Structural check: the API client declares no free-text note field and no screen reads one.

const webRoot = join(__dirname, "..", "..");
const src = join(webRoot, "src");

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return n === "generated" ? [] : files(p);
    return /\.tsx?$/.test(p) ? [p] : [];
  });
}

/** ScenarioSummary.notes is a list of codes produced by the scenario engine, not ERP text; it is the only allowed array. */
const ENGINE_CODES = /\bnotes\s*:\s*string\[\]/;

/** A declared field such as `notes: string` or `supplier_note?: string` (the boolean flag is allowed). */
export const NOTE_FIELD = /\b(?:supplier_)?(?:notes?|observaciones|free_text|remarks?)\s*\??\s*:\s*(?!boolean)/;
/** A property read such as `x.note`, `s.notes` or `row["note"]`. */
export const NOTE_READ = /\.(?:supplier_)?(?:notes?|observaciones|free_text|remarks?)\b(?!\s*\()|\[\s*["'](?:notes?|observaciones)["']\s*\]/;

describe("free-text ERP notes are never declared or read in the web app", () => {
  it("the detectors catch a note field and a note read, and allow the flag (self-check)", () => {
    expect(NOTE_FIELD.test("supplier_note: string | null;")).toBe(true);
    expect(NOTE_FIELD.test("has_note: boolean;")).toBe(false);
    expect(NOTE_READ.test("<p>{supplier.note}</p>")).toBe(true);
    expect(NOTE_READ.test("<p>{t('x')}</p>")).toBe(false);
  });

  it("the API client declares no free-text note field", () => {
    const text = readFileSync(join(src, "api", "client.ts"), "utf8");
    const hits = text.split("\n").map((l, i) => [i + 1, l] as const).filter(([, l]) => NOTE_FIELD.test(l) && !ENGINE_CODES.test(l)).map(([i, l]) => `client.ts:${i} ${l.trim()}`);
    expect(hits).toEqual([]);
  });

  it("no screen or model reads a note property", () => {
    const hits = files(join(src, "features")).concat(files(join(src, "app")), files(join(src, "ui"))).flatMap((f) =>
      readFileSync(f, "utf8").split("\n").map((l, i) => [i + 1, l] as const).filter(([, l]) => NOTE_READ.test(l)).map(([i, l]) => `${relative(webRoot, f)}:${i} ${l.trim()}`),
    );
    expect(hits).toEqual([]);
  });

  it("the catalogue never mentions showing supplier note text", () => {
    const cat = JSON.parse(readFileSync(join(src, "i18n", "es-ES.json"), "utf8")) as Record<string, string>;
    const hits = Object.entries(cat).filter(([, v]) => /nota del proveedor|notas? libres?|texto libre del erp/i.test(v)).map(([k]) => k);
    expect(hits).toEqual([]);
  });
});
