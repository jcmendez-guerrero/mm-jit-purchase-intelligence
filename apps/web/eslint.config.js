import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "src/api/generated/**"] }, // generated from the JSON Schemas
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    // Browser script served as is from public/ (sets the theme before first paint)
    files: ["public/**/*.js"],
    languageOptions: { sourceType: "script", globals: { window: "readonly", document: "readonly" } },
  },
  {
    // Node build scripts (bundle budget check)
    files: ["scripts/**/*.mjs"],
    languageOptions: { globals: { URL: "readonly", console: "readonly", process: "readonly" } },
  },
);
