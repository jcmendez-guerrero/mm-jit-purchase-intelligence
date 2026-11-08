import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * MMI 003 (T003): colour literals live in src/styles/tokens.css. Existing literals in legacy files are recorded in
 * a baseline that may only shrink, mirroring hardcoded-strings.baseline.json.
 */

const srcRoot = join(__dirname, "..", "..", "src");
const baselineFile = join(__dirname, "hardcoded-colors.baseline.json");
const ALLOWED = new Set(["src/styles/tokens.css"]);
const COLOUR = /#[0-9a-fA-F]{3,8}\b|\brgba?\(/g;

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return name === "generated" ? [] : sources(p);
    return /\.(css|tsx|ts)$/.test(p) ? [p] : [];
  });
}

export function colourCount(source: string): number {
  return source.match(COLOUR)?.length ?? 0;
}

describe("colour literals", () => {
  const baseline = JSON.parse(readFileSync(baselineFile, "utf8")) as Record<string, number>;
  const found: Record<string, number> = {};
  for (const file of sources(srcRoot)) {
    const rel = join("src", relative(srcRoot, file)).split("\\").join("/");
    if (ALLOWED.has(rel)) continue;
    const n = colourCount(readFileSync(file, "utf8"));
    if (n > 0) found[rel] = n;
  }

  it("adds no new colour literals outside tokens.css", () => {
    for (const [file, n] of Object.entries(found)) {
      expect(baseline[file] ?? 0, `${file} has ${n} colour literals; use tokens from src/styles/tokens.css`).toBeGreaterThanOrEqual(n);
    }
  });

  it("keeps the baseline honest (entries only shrink)", () => {
    for (const [file, allowed] of Object.entries(baseline)) {
      expect(found[file] ?? 0, `${file} improved: lower its baseline to ${found[file] ?? 0} (or remove it)`).toBe(allowed);
    }
  });
});

describe("inline styles", () => {
  // Layout and text come from classes in styles/components.css. The ruler's segment width is data, not design.
  const ALLOWED = new Set(["src/ui/SeverityRuler.tsx"]);

  it("keeps style props out of the screens, the shell and the primitives", () => {
    const offenders: string[] = [];
    for (const file of sources(srcRoot)) {
      const rel = join("src", relative(srcRoot, file)).split("\\").join("/");
      if (!rel.endsWith(".tsx") || ALLOWED.has(rel)) continue;
      if (/style=\{\{/.test(readFileSync(file, "utf8"))) offenders.push(rel);
    }
    expect(offenders, "use a class from src/styles/components.css instead of an inline style").toEqual([]);
  });
});

describe("shared primitives", () => {
  it("keeps the legacy button and card classes out of the screens", () => {
    const offenders: string[] = [];
    for (const file of sources(join(srcRoot, "features"))) {
      if (!file.endsWith(".tsx")) continue;
      const text = readFileSync(file, "utf8");
      if (/className="[^"]*\bmmi-btn\b/.test(text) || /className="[^"]*\bmmi-card\b/.test(text)) offenders.push(relative(srcRoot, file));
    }
    expect(offenders, "use Button and Card from src/ui").toEqual([]);
  });
});
