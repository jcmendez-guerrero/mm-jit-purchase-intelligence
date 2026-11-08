// Fails when the built JavaScript exceeds the budgets in package.json ("bundleBudgetKb"), gzip sizes.
// Run after `npm run build`: `npm run check:bundle`.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";

const root = new URL("..", import.meta.url).pathname;
const budget = JSON.parse(readFileSync(join(root, "package.json"), "utf8")).bundleBudgetKb;
const dir = join(root, "dist", "assets");

let files;
try {
  files = readdirSync(dir).filter((f) => f.endsWith(".js"));
} catch {
  console.error(`No build output in ${dir}; run "npm run build" first.`);
  process.exit(2);
}

let total = 0;
let charts = 0;
for (const f of files) {
  if (!statSync(join(dir, f)).isFile()) continue;
  const size = gzipSync(readFileSync(join(dir, f))).length;
  total += size;
  if (f.startsWith("charts")) charts += size;
}
const kb = (n) => (n / 1024).toFixed(1);
console.log(`JS gzip total ${kb(total)} kB (budget ${budget.total_js_gzip}), charts chunk ${kb(charts)} kB (budget ${budget.charts_chunk_gzip})`);
if (total / 1024 > budget.total_js_gzip || charts / 1024 > budget.charts_chunk_gzip) {
  console.error("Bundle budget exceeded.");
  process.exit(1);
}
