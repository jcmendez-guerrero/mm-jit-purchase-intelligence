import { describe, expect, it } from "vitest";
import esJson from "../../src/i18n/es-ES.json";
import register from "../../src/i18n/register.json";

// T064 (feature 012): the catalogue addresses the person as "tú". No value may use the formal "usted" forms.

const catalogue = esJson as Record<string, string>;
const words = (text: string) =>
  text.toLowerCase().match(/[a-záéíóúüñ]+/g) ?? [];

describe("register (tú)", () => {
  it("records the choice", () => {
    expect(register.address).toBe("tú");
  });

  it("no catalogue value uses usted or a formal imperative", () => {
    const forbidden = new Set([
      ...register.forbidden_words,
      ...register.forbidden_imperatives,
    ]);
    // After "se" or "que" the same form is the correct subjunctive ("hasta que se confirme"), not an order.
    const hits = Object.entries(catalogue).flatMap(([key, value]) =>
      words(value)
        .filter(
          (w, i, all) =>
            forbidden.has(w) && !["se", "que"].includes(all[i - 1] ?? ""),
        )
        .map((w) => `${key}: ${w}`),
    );
    expect(hits).toEqual([]);
  });

  it("the word list has no duplicates and no tú form", () => {
    const all = [
      ...register.forbidden_words,
      ...register.forbidden_imperatives,
    ];
    expect(new Set(all).size).toBe(all.length);
    expect(all).not.toContain("tú");
  });
});
