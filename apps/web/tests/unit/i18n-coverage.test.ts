import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";
import esJson from "../../src/i18n/es-ES.json";

// T015: every stable error code has a Spanish message, and no NEW hard-coded user-facing text enters the SPA.
// Existing hard-coded text (found in the unreviewed web code) is recorded in a baseline that may only shrink.

const webRoot = join(__dirname, "..", "..");
const codesFile = join(webRoot, "..", "..", "packages", "contracts", "errors", "error_codes.json");
const baselineFile = join(__dirname, "hardcoded-strings.baseline.json");

const catalogue = esJson as Record<string, string>;
const codes = Object.keys(JSON.parse(readFileSync(codesFile, "utf8")).codes as Record<string, unknown>);

function tsxFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return name === "generated" ? [] : tsxFiles(p);
    return p.endsWith(".tsx") ? [p] : [];
  });
}

const JSX_TEXT = />\s*([^<>{}\n]*[A-Za-zÁÉÍÓÚáéíóúñÑ]{2}[^<>{}\n]*)</g;
const ATTR_TEXT = /\b(?:aria-label|placeholder|title|alt)="[^"{]*[A-Za-zÁÉÍÓÚáéíóúñÑ]{2}[^"]*"/g;

export function hardcodedCount(source: string): number {
  const noArrows = source.replace(/=>/g, "=_").replace(/->/g, "-_");
  const text = [...noArrows.matchAll(JSX_TEXT)].filter((m) => !/^\s*(?:\/\/|\/\*)/.test(m[1] ?? ""));
  return text.length + (noArrows.match(ATTR_TEXT)?.length ?? 0);
}

describe("error codes are localised (es-ES)", () => {
  it.each(codes)("code %s has a Spanish message", (code) => {
    const msg = catalogue[`errors.${code}`];
    expect(msg, `missing errors.${code} in es-ES.json`).toBeTruthy();
    expect(msg!.length).toBeGreaterThan(10);
  });

  it("codes are snake_case", () => {
    for (const c of codes) expect(c).toMatch(/^[a-z][a-z0-9_]*$/);
  });
});

describe("no new hard-coded user-facing text in the SPA", () => {
  const baseline = JSON.parse(readFileSync(baselineFile, "utf8")) as Record<string, number>;
  const files = tsxFiles(join(webRoot, "src"));

  it("counts per file never exceed the baseline", () => {
    const over: string[] = [];
    for (const f of files) {
      const rel = relative(webRoot, f);
      const n = hardcodedCount(readFileSync(f, "utf8"));
      if (n > (baseline[rel] ?? 0)) over.push(`${rel}: ${n} > ${baseline[rel] ?? 0}`);
    }
    expect(over, "use t('...') and add the key to es-ES.json").toEqual([]);
  });

  it("the scanner finds hard-coded text (self-check)", () => {
    expect(hardcodedCount('<p>Hola mundo</p>')).toBe(1);
    expect(hardcodedCount('<button aria-label="Cerrar">x</button>')).toBe(1);
    expect(hardcodedCount("<p>{t('common.error')}</p>")).toBe(0);
    expect(hardcodedCount("const f = () => 1; const g = (a) => a > 2;")).toBe(0);
  });

  it("the baseline only lists files that still exist and still have text", () => {
    for (const [rel, n] of Object.entries(baseline)) {
      const f = join(webRoot, rel);
      expect(() => statSync(f), `${rel} no longer exists; remove it from the baseline`).not.toThrow();
      expect(hardcodedCount(readFileSync(f, "utf8")), `${rel} improved; lower its baseline`).toBeGreaterThanOrEqual(n);
    }
  });
});
