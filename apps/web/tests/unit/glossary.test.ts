import { describe, expect, it } from "vitest";
import esJson from "../../src/i18n/es-ES.json";
import glossary from "../../src/i18n/glossary.json";

// T008 (feature 012): one Spanish term per business concept; no forbidden variant in any catalogue value.

const catalogue = esJson as Record<string, string>;
/**
 * Known gaps that cannot be closed inside this feature. A key may only leave this list.
 * suppliers.override.variant: the override screen still asks for the Siweb variant id because the gateway has no
 * SKU-to-variant lookup; adding one is a contract change for Agent 00 (see audit-inventory.md, "Journeys").
 */
const KNOWN_EXCEPTIONS: Record<string, string> = { "suppliers.override.variant": "id de variante" };

const entries = Object.entries(glossary as Record<string, { term: string; forbidden: string[] }>);

describe("glossary", () => {
  it("known exceptions still exist and still violate the glossary (remove them when fixed)", () => {
    for (const [key, variant] of Object.entries(KNOWN_EXCEPTIONS)) {
      expect(catalogue[key], key).toBeTruthy();
      expect(catalogue[key]!.toLowerCase()).toContain(variant);
    }
  });

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
          if (re.test(value) && KNOWN_EXCEPTIONS[key]?.toLowerCase() !== f.toLowerCase()) hits.push(`${key}: "${f}" (use "${g.term}" for ${concept})`);
        }
      }
    }
    expect(hits).toEqual([]);
  });
});
