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

// T009 (feature 012): catalogue quality and text that hides in `.ts` files. The unused-key list may only shrink.

const unusedBaselineFile = join(__dirname, "unused-keys.baseline.json");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return name === "generated" ? [] : sourceFiles(p);
    return /\.tsx?$/.test(p) ? [p] : [];
  });
}

const SENTENCE_LITERAL = /"([A-ZÁÉÍÓÚ][a-záéíóúñ]+(?: [a-záéíóúñ,.]+){2,})"/g;

export function sentenceLiterals(source: string): string[] {
  return [...source.matchAll(SENTENCE_LITERAL)].map((m) => m[1]!);
}

describe("catalogue quality", () => {
  const all = sourceFiles(join(webRoot, "src"));
  const text = all.map((f) => readFileSync(f, "utf8")).join("\n");

  it("has no empty values", () => {
    expect(Object.entries(catalogue).filter(([, v]) => !String(v).trim()).map(([k]) => k)).toEqual([]);
  });

  it("no `.ts` file builds a Spanish sentence outside the catalogue (models return keys)", () => {
    const hits = all
      .filter((f) => f.endsWith(".ts"))
      .flatMap((f) => sentenceLiterals(readFileSync(f, "utf8")).map((s) => `${relative(webRoot, f)}: "${s}"`));
    expect(hits, "move the text to es-ES.json and return its key").toEqual([]);
  });

  it("the sentence scanner finds a hard-coded sentence (self-check)", () => {
    expect(sentenceLiterals('const m = "No se pudo guardar el cambio";')).toEqual(["No se pudo guardar el cambio"]);
    expect(sentenceLiterals('const k = "suppliers.form.err.name_required";')).toEqual([]);
  });

  it("every literal key passed to t() exists in the catalogue (a missing key would show only the fallback text)", () => {
    // Literal keys only: `t("a.b")`. Template keys such as t(`a.${x}`) are covered by the code that builds them.
    const keys = new Set([...text.matchAll(/\bt\(\s*["']([a-z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)+)["']/g)].map((m) => m[1]!));
    expect(keys.size).toBeGreaterThan(500);
    expect([...keys].filter((k) => !(k in catalogue)).sort(), "add the key to es-ES.json or fix the typo").toEqual([]);
  });

  it("the key scanner finds a literal key and ignores a template (self-check)", () => {
    const re = /\bt\(\s*["']([a-z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)+)["']/g;
    expect([..."t('a.b') t(`a.${x}`) t(\"c.d_e\")".matchAll(re)].map((m) => m[1])).toEqual(["a.b", "c.d_e"]);
  });

  it("catalogue keys that nothing references never grow", () => {
    // Used when the key appears literally, a template prefix covers it, or a dotted string in the code is its prefix
    // (props such as prefix="imports.reason.activate" and helpers such as known("proposals.why.constraint", code)).
    const literals = new Set([...text.matchAll(/[`"']([a-z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)+)[`"']/g)].map((m) => m[1]!));
    const prefixes = [...text.matchAll(/[`"']([a-zA-Z0-9_.-]+[._])\$\{/g)].map((m) => m[1]!);
    const used = (k: string) => text.includes(k) || prefixes.some((p) => k.startsWith(p)) || [...literals].some((l) => k.startsWith(`${l}.`) || k.startsWith(`${l}_`));
    const unused = Object.keys(catalogue).filter((k) => !used(k));
    // The baseline holds keys the server builds itself, with the reason; it may only shrink.
    const baseline = JSON.parse(readFileSync(unusedBaselineFile, "utf8")) as Record<string, string>;
    expect(unused.filter((k) => !(k in baseline)), "new unused key: use it or remove it").toEqual([]);
    expect(Object.keys(baseline).filter((k) => !unused.includes(k)), "now used or gone: remove it from unused-keys.baseline.json").toEqual([]);
    expect(Object.values(baseline).every((r) => r.length > 0), "every baseline key needs a reason").toBe(true);
  });
});
