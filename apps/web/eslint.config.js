import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "src/api/generated/**"] }, // generated from the JSON Schemas
  js.configs.recommended,
  ...tseslint.configs.recommended,
);
