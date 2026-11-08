import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import esJson from "../../../src/i18n/es-ES.json";
import { STATUS_VOCABULARY, statusInfo, type StatusDomain } from "../../../src/ui/statusVocabulary";
import { ICON_NAMES } from "../../../src/ui/icons/paths";

/** T033 — one vocabulary for every status; never colour alone; text/tint pairs readable (design.md §4). */

const catalogue = esJson as Record<string, string>;
const tokens = readFileSync(join(__dirname, "../../../src/styles/tokens.css"), "utf8");

function token(name: string): string {
  const m = tokens.match(new RegExp(`--mmi-${name}:\\s*([^;]+);`));
  if (!m) throw new Error(`token ${name} not found`);
  const value = m[1]!.trim();
  const ref = value.match(/^var\(--mmi-([\w-]+)\)$/);
  return ref ? token(ref[1]!) : value;
}
function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!;
}
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
}

describe("status vocabulary", () => {
  const domains = Object.keys(STATUS_VOCABULARY) as StatusDomain[];

  it("covers the documented domains", () => {
    expect(domains.sort()).toEqual(["approval", "cost_write", "import", "quarantine", "risk", "scenario", "tag"].sort());
  });

  it("gives every known code a label key that exists, a tone and an icon", () => {
    for (const domain of domains) {
      for (const [code, info] of Object.entries(STATUS_VOCABULARY[domain])) {
        if (info.labelKey) expect(catalogue[info.labelKey], `${domain}.${code} → ${info.labelKey}`).toBeTruthy();
        expect(["neutral", "info", "success", "warning", "danger"]).toContain(info.tone);
        expect(ICON_NAMES, `${domain}.${code} icon`).toContain(info.icon);
      }
    }
  });

  it("renders unknown codes as a neutral badge with an icon", () => {
    const info = statusInfo("approval", "something_new");
    expect(info.tone).toBe("neutral");
    expect(ICON_NAMES).toContain(info.icon);
    expect(info.labelKey).toBe("ui.status.unknown");
  });

  it("shows raw quarantine codes as warnings", () => {
    const info = statusInfo("quarantine", "negative_quantity");
    expect(info.tone).toBe("warning");
    expect(info.labelKey).toBeUndefined();
  });

  it("keeps each tone's text and tint at 4.5:1 or better", () => {
    for (const tone of ["danger", "warning", "success", "info", "neutral"]) {
      const text = token(tone);
      const bg = token(`${tone}-bg`);
      expect(contrast(text, bg), `${tone} ${text} on ${bg}`).toBeGreaterThanOrEqual(4.5);
    }
  });
});
