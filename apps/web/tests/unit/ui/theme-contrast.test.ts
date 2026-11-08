import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * T063 — every text/background and graphic pair the primitives use meets WCAG 2.2 AA in each shipped theme
 * (text 4.5:1, large text and meaningful graphics 3:1), computed from src/styles/tokens.css.
 */

const css = readFileSync(join(__dirname, "../../../src/styles/tokens.css"), "utf8");

function block(selector: RegExp): Record<string, string> {
  const m = css.match(selector);
  if (!m) throw new Error(`block ${selector} not found`);
  const out: Record<string, string> = {};
  for (const d of m[1]!.matchAll(/--mmi-([\w-]+):\s*([^;]+);/g)) out[d[1]!] = d[2]!.trim();
  return out;
}

const light = block(/:root\s*\{([\s\S]*?)\n\}/);
const dark = block(/:root\[data-theme="dark"\]\s*\{([\s\S]*?)\n\}/);

function resolve(theme: Record<string, string>, name: string): string {
  const raw = theme[name] ?? light[name];
  if (!raw) throw new Error(`token ${name} missing`);
  const ref = raw.match(/^var\(--mmi-([\w-]+)\)$/);
  return ref ? resolve(theme, ref[1]!) : raw;
}

function luminance(input: string): number {
  const hex = /^#[0-9a-fA-F]{3}$/.test(input) ? `#${[...input.slice(1)].map((c) => c + c).join("")}` : input;
  if (!/^#[0-9a-fA-F]{6}$/.test(hex)) throw new Error(`not a hex colour: ${input}`);
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!;
}
const ratio = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
};

const TEXT: Array<[string, string]> = [
  ["text", "bg"], ["text", "surface"], ["title", "bg"], ["title", "surface"],
  ["text-note", "bg"], ["text-note", "surface"], ["text-note", "surface-sunken"],
  ["link", "surface"], ["on-primary", "primary"], ["on-primary", "primary-hover"],
  ["danger", "danger-bg"], ["warning", "warning-bg"], ["success", "success-bg"], ["info", "info-bg"], ["neutral", "neutral-bg"],
  ["text", "selected"], ["text", "hover"], ["link", "selected"], ["link", "hover"],
];
const LARGE_TEXT: Array<[string, string]> = [["subtitle", "bg"], ["subtitle", "surface"]];
const GRAPHICS: Array<[string, string]> = [["primary", "surface"], ["border-control", "surface"], ["border-control", "bg"], ["focus", "surface"], ["focus", "bg"], ["danger", "surface"], ["warning", "surface"], ["info", "surface"]];

describe.each([["light", light], ["dark", dark]] as const)("%s theme", (name, theme) => {
  it.each(TEXT)("text %s on %s is at least 4.5:1", (fg, bg) => {
    expect(ratio(resolve(theme, fg), resolve(theme, bg)), `${name}: ${fg} on ${bg}`).toBeGreaterThanOrEqual(4.5);
  });
  it.each(LARGE_TEXT)("large text %s on %s is at least 3:1", (fg, bg) => {
    expect(ratio(resolve(theme, fg), resolve(theme, bg)), `${name}: ${fg} on ${bg}`).toBeGreaterThanOrEqual(3);
  });
  it.each(GRAPHICS)("graphic %s against %s is at least 3:1", (fg, bg) => {
    expect(ratio(resolve(theme, fg), resolve(theme, bg)), `${name}: ${fg} against ${bg}`).toBeGreaterThanOrEqual(3);
  });
});

describe("dark theme coverage", () => {
  it("overrides every colour role, so no light-only colour leaks through", () => {
    const roles = ["bg", "surface", "surface-sunken", "text", "text-note", "title", "subtitle", "link", "primary", "primary-hover", "on-primary", "border", "border-control", "focus", "selected", "hover", "overlay", "danger", "danger-bg", "warning", "warning-bg", "success", "success-bg", "info", "info-bg", "neutral", "neutral-bg"];
    for (const r of roles) expect(Object.keys(dark), `dark must set --mmi-${r}`).toContain(r);
  });

  it("leaves the brand colours untouched (the logo keeps its original colours on a white plate)", () => {
    for (const k of ["petroleo", "azul-medio", "azul-medio-texto", "turquesa", "azul-noche", "blanco-hielo", "blanco"]) expect(Object.keys(dark)).not.toContain(k);
  });
});
