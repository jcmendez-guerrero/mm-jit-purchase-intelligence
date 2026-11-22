import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Feature 014 (T064, 006 SC-004 and FR-002): the dashboard shows only figures that came from stored data. A number written straight into the markup, as text or as a `{12}` child,
 * would be a hard-coded figure. Array indexes, sizes, attribute values (`width={4}`) and test ids are not rendered as data and are not flagged.
 */

const DIR = join(__dirname, "..", "..", "src", "features", "dashboard");

export function literalNumbers(source: string): string[] {
  const found: string[] = [];
  // JSX text that is only a number: <p>42</p>, <td>1.234,50</td>
  for (const m of source.matchAll(/>\s*(-?\d[\d.,]*)\s*</g)) found.push(`text ${m[1]}`);
  // A numeric literal as a JSX child: <p>{42}</p> (not an attribute value, which follows "=")
  for (const m of source.matchAll(/(?<![=\w)\]])\{\s*(-?\d+(?:\.\d+)?)\s*\}(?=\s*<|\s*\n)/g)) found.push(`child ${m[1]}`);
  return found;
}

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : /\.tsx?$/.test(name) ? [path] : [];
  });
}

describe("dashboard renders no hard-coded figure", () => {
  it("catches a number written into the markup", () => {
    expect(literalNumbers("<p>42</p>")).toEqual(["text 42"]);
    expect(literalNumbers("<td>1.234,50</td>")).toEqual(["text 1.234,50"]);
    expect(literalNumbers("<p>{42}</p>")).toEqual(["child 42"]);
    expect(literalNumbers("<p>\n  {7}\n</p>")).toEqual(["child 7"]);
  });

  it("does not flag what is not a rendered figure", () => {
    expect(literalNumbers("<Bar width={4} />")).toEqual([]);
    expect(literalNumbers("rows.slice(0, 30).map((r) => <li key={r.id}>{r.name}</li>)")).toEqual([]);
    expect(literalNumbers("<p>{t('dashboard.ind.units', { n: 3 })}</p>")).toEqual([]);
    expect(literalNumbers("const PAGE_SIZE = 50;")).toEqual([]);
    expect(literalNumbers("<input maxLength={120} />")).toEqual([]);
  });

  it("finds none in any dashboard source file", () => {
    const all = files(DIR);
    expect(all.length).toBeGreaterThan(8);
    const bad = all.flatMap((f) => literalNumbers(readFileSync(f, "utf8")).map((hit) => `${f.slice(DIR.length + 1)}: ${hit}`));
    expect(bad).toEqual([]);
  });
});
