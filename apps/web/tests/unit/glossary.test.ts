import { describe, expect, it } from "vitest";
import esJson from "../../src/i18n/es-ES.json";
import glossary from "../../src/i18n/glossary.json";

// T008 (feature 012): one Spanish term per business concept; no forbidden variant in any catalogue value.

const catalogue = esJson as Record<string, string>;
const entries = Object.entries(glossary as Record<string, { term: string; forbidden: string[] }>);

describe("glossary", () => {
  it("has a term and forbidden variants, and a Spanish definition in the catalogue, for every concept", () => {
    expect(entries.length).toBeGreaterThan(0);
    for (const [concept, g] of entries) {
      expect(g.term, concept).toBeTruthy();
      expect(Array.isArray(g.forbidden) && g.forbidden.length > 0, concept).toBe(true);
      const definition = catalogue[`glossary.${concept}`];
      expect(definition, `glossary.${concept} missing in es-ES.json`).toBeTruthy();
      expect(definition!.length, concept).toBeGreaterThan(20);
      expect(definition!.endsWith("."), concept).toBe(true);
    }
  });

  it("never lists a term as its own forbidden variant, and no variant is used twice", () => {
    const seen = new Set<string>();
    for (const [concept, g] of entries) {
      for (const f of g.forbidden) {
        expect(f.toLowerCase(), concept).not.toBe(g.term.toLowerCase());
        expect(seen.has(f.toLowerCase()), `${f} repeated`).toBe(false);
        seen.add(f.toLowerCase());
      }
    }
  });

  it("no catalogue value contains a forbidden variant", () => {
    const hits: string[] = [];
    for (const [key, value] of Object.entries(catalogue)) {
      for (const [concept, g] of entries) {
        for (const f of g.forbidden) {
          const re = new RegExp(`(^|[^\\p{L}_])${f.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}($|[^\\p{L}_])`, "iu");
          if (re.test(value)) hits.push(`${key}: "${f}" (use "${g.term}" for ${concept})`);
        }
      }
    }
    expect(hits).toEqual([]);
  });
});
