/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8081",
        changeOrigin: true,
      },
    },
  },
  build: {
    // Charts load as their own chunk so the budget in package.json ("bundleBudgetKb") can be checked per chunk.
    rollupOptions: { output: { manualChunks: { charts: ["recharts"] } } },
    chunkSizeWarningLimit: 600,
  },
  test: {
    include: ["tests/unit/**/*.test.{ts,tsx}"],
    exclude: ["tests/e2e/**", "node_modules/**"],
  },
});
